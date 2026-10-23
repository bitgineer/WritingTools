import gettext
import json
import logging
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass

import pyperclip
import ui.AboutWindow
import ui.CustomPopupWindow
import ui.DashboardWindow
import ui.HistoryWindow
import ui.OnboardingWindow
import ui.ResponseWindow
import ui.SettingsWindow
import ui.WorkingPill
from aiprovider import GeminiProvider, OllamaProvider, OpenAICompatibleProvider, obfuscate_api_key
from pynput import keyboard as pykeyboard
from ui.design import apply_app_style
from PySide6 import QtCore, QtGui, QtWidgets
from rework.controller import ReworkController
from rework.history import HistoryStore
from rework.model import Rework
from rework.review_card import ReworkCard
from rework.undo import capture_foreground_window, focus_window, is_foreground, undo_last_paste
from PySide6.QtCore import QLocale, QStandardPaths, Signal, Slot
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox
from update_checker import UpdateChecker

_ = gettext.gettext


class _SelectedTextHolder:
    """
    Carries the result of an async clipboard capture from `_show_popup` to
    `process_option_thread`. The capture thread sets `text` and signals
    `ready` once done.
    """
    __slots__ = ("text", "ready")

    def __init__(self):
        self.text = ""
        self.ready = threading.Event()


@dataclass
class _RequestContext:
    """The option and captured text that belong to one provider request.

    `serial` identifies the request across the worker thread. `cancelled` lets
    the user drop a slow response without waiting for the SDK call to return.
    """
    option: str
    original: str
    serial: int = 0
    cancelled: bool = False


class WritingToolApp(QtWidgets.QApplication):
    """
    The main application class for Writing Tools.
    """
    output_ready_signal = Signal(str)
    show_message_signal = Signal(str, str)  # a signal for showing message boxes
    hotkey_triggered_signal = Signal()
    followup_response_signal = Signal(str)
    working_stage_signal = Signal(str)


    def __init__(self, argv):
        super().__init__(argv)
        QtCore.QCoreApplication.setApplicationName("Writing Tools")
        QtCore.QCoreApplication.setOrganizationName("Writing Tools")
        self.design_palette = apply_app_style(self)
        self.current_response_window = None
        logging.debug('Initializing WritingToolApp')
        self.output_ready_signal.connect(self.replace_text)
        self.show_message_signal.connect(self.show_message_box)
        self.working_stage_signal.connect(self._set_working_stage)
        self.hotkey_triggered_signal.connect(self.on_hotkey_pressed)
        self.config = None
        self.config_path = None
        self.load_config()

        # Run any pending config migrations in a single pass (single restart).
        self._migrate_config()

        self.history_enabled = (
            bool(self.config.get('history_enabled', True)) if self.config else True
        )
        try:
            history_limit = int(self.config.get('history_limit', 500)) if self.config else 500
        except (TypeError, ValueError):
            history_limit = 500
        try:
            self.history_store = HistoryStore(self._history_path(), limit=history_limit)
        except Exception:
            logging.exception("Could not open rewrite history; history is disabled")
            self.history_store = None
            self.history_enabled = False
        self.history_window = None

        self.options = None
        self.options_path = None
        self.load_options()
        self.onboarding_window = None
        self.dashboard_window = None
        self.popup_window = None
        self.tray_icon = None
        self.tray_menu = None
        self.settings_window = None
        self.about_window = None
        self.registered_hotkey = None
        self.output_queue = ""
        self.current_option = None
        self._active_request = None
        self._request_serial = 0
        self.working_pill = None
        self._rework_target = None
        self.rework_controller = ReworkController(
            self._make_rework_card,
            undo=self._undo_rework,
            save=self._save_rework_to_history,
        )
        self.last_replace = 0
        self.hotkey_listener = None
        self.paused = False
        self.toggle_action = None

        # Holder for the user's selected text. Populated asynchronously by a
        # background thread so the popup can show instantly — see `_show_popup`
        # and `_fire_ctrl_c_and_capture_async`. The lock serializes Ctrl+C
        # captures across rapid hotkey presses so two captures don't fight
        # over the clipboard at once.
        self.current_text_holder = None
        self._capture_lock = threading.Lock()

        self._ = gettext.gettext

        # Initialize the ctrl+c hotkey listener
        self.ctrl_c_timer = None
        self.setup_ctrl_c_listener()

        # Setup available AI providers
        self.providers = [GeminiProvider(self), OpenAICompatibleProvider(self), OllamaProvider(self)]

        if not self.config:
            logging.debug('No config found, showing onboarding')
            self.show_onboarding()
        else:
            logging.debug('Config found, setting up hotkey and tray icon')

            if self._activate_saved_provider():
                self.create_tray_icon()
                self.register_hotkey()

            try:
                lang = self.config['locale']
            except KeyError:
                lang = None
            self.change_language(lang)

            # Initialize update checker
            self.update_checker = UpdateChecker(self)
            self.update_checker.check_updates_async()

        self.recent_triggers = []  # Track recent hotkey triggers
        self.TRIGGER_WINDOW = 1.5  # Time window in seconds
        self.MAX_TRIGGERS = 3  # Max allowed triggers in window

        # Autostart passes --background so a boot login stays in the tray.
        if self.config and self.current_provider is not None and '--background' not in argv:
            self.show_dashboard()

    def setup_translations(self, lang=None):
        if not lang:
            lang = QLocale.system().name().split('_')[0]

        try:
            translation = gettext.translation(
                'messages',
                localedir=os.path.join(os.path.dirname(__file__), 'locales'),
                languages=[lang]
            )
        except FileNotFoundError:
            translation = gettext.NullTranslations()

        translation.install()
        # Update the translation function for all UI components.
        self._ = translation.gettext
        ui.AboutWindow._ = self._
        ui.SettingsWindow._ = self._
        ui.ResponseWindow._ = self._
        ui.OnboardingWindow._ = self._
        ui.CustomPopupWindow._ = self._

    def retranslate_ui(self):
        self.update_tray_menu()

    def change_language(self, lang):
        self.setup_translations(lang)
        self.retranslate_ui()

        # Update all other windows
        for widget in QApplication.topLevelWidgets():
            if widget != self and hasattr(widget, 'retranslate_ui'):
                widget.retranslate_ui()

    def check_trigger_spam(self):
        """
        Check if hotkey is being triggered too frequently (3+ times in 1.5 seconds).
        Returns True if spam is detected.
        """
        current_time = time.time()
        
        # Add current trigger
        self.recent_triggers.append(current_time)
        
        # Remove old triggers outside the window
        self.recent_triggers = [t for t in self.recent_triggers 
                            if current_time - t <= self.TRIGGER_WINDOW]
        
        # Check if we have too many triggers in the window
        return len(self.recent_triggers) >= self.MAX_TRIGGERS

    def load_config(self):
        """
        Load the configuration file.
        """
        self.config_path = os.path.join(os.path.dirname(sys.argv[0]), 'config.json')
        logging.debug(f'Loading config from {self.config_path}')
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    self.config = json.load(f)
                logging.debug('Config loaded successfully')
            except (OSError, ValueError):
                logging.exception(
                    'Config file could not be read; starting fresh so the app can open'
                )
                try:
                    os.replace(self.config_path, self.config_path + '.broken')
                except OSError:
                    pass
                self.config = None
        else:
            logging.debug('Config file not found')
            self.config = None

    def _migrate_config(self):
        """
        One-shot config migration. Catches any user up to the current schema
        (v9) regardless of where they started — v7, v8, or already current —
        in a single pass with at most one restart.

        Each version is gated on its own `is_config_file_updated_for_v{N}`
        flag, so re-running this is a no-op once everything's caught up.
        Bump CURRENT_CONFIG_VERSION and add a `# v{N}` block when adding a
        new migration step.

        v8 (introduced 2025):
          • Google removed Gemini 2.0 from the free API → bump model.
          • Obfuscate plaintext Gemini API keys (defeats Ctrl+F scanning).
          The custom-model input field didn't exist pre-v8, so any pre-v8
          model value is safe to overwrite — there's nothing custom to
          preserve.

        v9 (introduced 2026):
          • Google deprecated the Gemma 3 family. Migrate every v8 user on a
            now-deprecated preset to the new default (`gemini-flash-latest`)
            so they immediately land on the fast experience. They can opt
            into the unlimited-but-slow Gemma 4 options from the dropdown
            if they hit the 20/day Flash quota.
            Preserve custom model values (which DID exist by then) so a user
            who picked, say, `gemini-3.1-pro-preview` doesn't get reset.
          • SDK migration to `google-genai` is code-side only; nothing to
            do in config.
        """
        CURRENT_CONFIG_VERSION = 9
        # Default for new installs and migrating users.
        NEW_DEFAULT_MODEL = 'gemini-flash-latest'
        # v8 -> v9 model mapping. Every retired preset is bumped to the new
        # default so users get the fast Flash-tier experience by default.
        V8_TO_V9_MAP = {
            'gemma-3-27b-it':           NEW_DEFAULT_MODEL,
            'gemma-3-4b-it':            NEW_DEFAULT_MODEL,
            'gemini-flash-lite-latest': NEW_DEFAULT_MODEL,
            # 'gemini-flash-latest' itself is already current — no entry needed.
        }

        # New user (no config yet) — onboarding will create a fresh, current
        # config; nothing to migrate.
        if not self.config:
            logging.debug('No config to migrate (new user)')
            return

        needs_v8 = not self.config.get('is_config_file_updated_for_v8', False)
        needs_v9 = not self.config.get('is_config_file_updated_for_v9', False)

        if not needs_v8 and not needs_v9:
            logging.debug('Config already up-to-date, no migration needed')
            return

        logging.info(f'Running config migration (needs_v8={needs_v8}, needs_v9={needs_v9})...')

        config_changed = False
        gemini_config = (
            self.config.get('providers', {}).get('Gemini (Recommended)')
        )

        if gemini_config is not None:
            old_model = gemini_config.get('model_name', '')

            # v8: pre-v8 users didn't have a custom-model field, so we can
            # bump unconditionally. We skip the historical "v8 default of
            # gemma-3-27b-it" intermediate stop and jump straight to the
            # current default.
            if needs_v8:
                if old_model != NEW_DEFAULT_MODEL:
                    gemini_config['model_name'] = NEW_DEFAULT_MODEL
                    logging.info(f'[v8] Bumped Gemini model "{old_model}" -> "{NEW_DEFAULT_MODEL}"')
                    config_changed = True

                # Obfuscate the API key. The helper is idempotent — already-
                # obfuscated keys (with the `enc:` prefix) pass through
                # unchanged.
                api_key = gemini_config.get('api_key', '')
                if api_key:
                    new_key = obfuscate_api_key(api_key)
                    if new_key != api_key:
                        gemini_config['api_key'] = new_key
                        logging.info('[v8] Obfuscated plaintext Gemini API key')
                        config_changed = True

            # v9: only runs for users coming from v8. Preserve tier choice via
            # the V8_TO_V9_MAP so an unlimited-tier user doesn't get silently
            # downgraded to a daily-quota model. Custom values (anything not
            # in the map) are left alone.
            elif needs_v9:
                new_model = V8_TO_V9_MAP.get(old_model)
                if new_model is not None and new_model != old_model:
                    gemini_config['model_name'] = new_model
                    logging.info(f'[v9] Bumped Gemini model "{old_model}" -> "{new_model}"')
                    config_changed = True

        # Stamp every version flag up to current so we never re-run on
        # subsequent startups, even if no fields actually needed changing
        # (e.g., a v8 user who'd already picked a custom non-deprecated model).
        for n in range(8, CURRENT_CONFIG_VERSION + 1):
            self.config[f'is_config_file_updated_for_v{n}'] = True

        self.save_config(self.config)
        logging.info('Config migration complete')

        # Single restart popup, regardless of how many versions we jumped.
        if config_changed:
            # Use QMessageBox directly — signals aren't connected yet at this
            # point in __init__.
            QMessageBox.information(
                None,
                'Writing Tools Updated',
                'Writing Tools has just completed an internal update '
                '(your config.json was migrated to the current format).\n\n'
                'Please restart Writing Tools.'
            )
            sys.exit(0)

    def _activate_saved_provider(self):
        """
        Load the provider named in config. A saved config that cannot start
        opens providers-only setup instead of crashing, and leaves
        current_provider unset until the user saves a working provider.
        """
        provider_name = self.config.get('provider', 'Gemini')
        provider = next((p for p in self.providers if p.provider_name == provider_name), None)
        if not provider:
            logging.warning(f'Provider {provider_name} not found. Using default provider.')
            provider = self.providers[0]

        try:
            provider.load_config(self.config.get("providers", {}).get(provider.provider_name, {}))
        except Exception as error:
            logging.exception(f'Saved settings for {provider.provider_name} could not start; opening setup')
            self.current_provider = None
            self.show_message_signal.emit(
                self._("AI provider not ready"),
                self._(
                    "{provider} could not start: {error}\n\n"
                    "Fix the provider's settings, then click Finish AI Setup."
                ).format(provider=provider.provider_name, error=error),
            )
            self.show_settings(providers_only=True)
            return False

        self.current_provider = provider
        return True

    def _provider_ready(self):
        """
        Return True when an AI provider is loaded. Otherwise tell the user how to set one up.
        """
        if getattr(self, 'current_provider', None) is not None:
            return True
        self.show_message_signal.emit(
            self._("AI provider not set up"),
            self._("No AI provider is ready. Open Settings from the tray menu and finish AI setup."),
        )
        return False

    def load_options(self):
        """
        Load the options file.
        """
        self.options_path = os.path.join(os.path.dirname(sys.argv[0]), 'options.json')
        logging.debug(f'Loading options from {self.options_path}')
        try:
            with open(self.options_path, 'r') as f:
                self.options = json.load(f)
            logging.debug('Options loaded successfully')
        except (OSError, ValueError):
            logging.warning('Options file missing or unreadable; using the defaults')
            self.options = json.loads(ui.CustomPopupWindow.DEFAULT_OPTIONS_JSON)

    def save_config(self, config):
        """
        Save the configuration file.
        """
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=4)
            logging.debug('Config saved successfully')
        self.config = config

    def show_onboarding(self):
        """
        Show the onboarding window for first-time users.
        """
        logging.debug('Showing onboarding window')
        self.onboarding_window = ui.OnboardingWindow.OnboardingWindow(self)
        self.onboarding_window.close_signal.connect(self._abandon_setup)
        self.onboarding_window.show()

    @staticmethod
    def _to_pynput_hotkey(hotkey_str):
        """
        Convert a user-facing hotkey string ('ctrl+j', 'ctrl+alt+space') to
        pynput's `<ctrl>+j` / `<ctrl>+<alt>+<space>` format. Single-char keys
        stay as-is; multi-char keys (modifiers, named keys) get wrapped in <>.
        """
        return '+'.join(
            f'{t}' if len(t) <= 1 else f'<{t}>'
            for t in hotkey_str.split('+')
        )

    def validate_shortcut(self, shortcut):
        """Return an error message, or None when the shortcut is usable."""
        text = (shortcut or '').strip()
        if not text:
            return 'Enter a shortcut, for example ctrl+space.'
        try:
            pykeyboard.HotKey.parse(self._to_pynput_hotkey(text))
        except Exception as error:
            return (
                f"'{text}' is not a valid shortcut.\n\n"
                "Use '+' between keys, for example ctrl+space or ctrl+alt+j.\n"
                f"({error})"
            )
        return None

    def _abandon_setup(self):
        """Closing setup must not kill the tray app the writer just installed."""
        logging.debug('Setup closed before completion; keeping the app running')
        if self.tray_icon is None:
            self.create_tray_icon()
        if self.tray_icon is not None and self.tray_icon.isVisible():
            self.tray_icon.showMessage(
                "Writing Tools",
                "Setup is not finished. Open Settings from the tray when you are ready.",
                QtWidgets.QSystemTrayIcon.MessageIcon.Information,
                6000,
            )
        if self.config:
            self.show_dashboard()

    def start_hotkey_listener(self):
        """
        Build a single `GlobalHotKeys` listener that handles both the main
        Writing Tools shortcut AND any per-button direct hotkeys defined in
        options.json. Per-button hotkeys fire the corresponding option
        immediately, skipping the popup.

        On conflict between a button hotkey and the global shortcut (or
        between two button hotkeys), the first registration wins and the
        later one is logged and skipped — the listener can't dispatch to
        two callbacks for the same combination anyway.
        """
        try:
            if self.hotkey_listener is not None:
                self.hotkey_listener.stop()
                self.hotkey_listener = None

            hotkey_map = {}

            # --- Global Writing Tools hotkey ----------------------------------
            orig_shortcut = self.config.get('shortcut', 'ctrl+space')
            self.registered_hotkey = orig_shortcut
            try:
                global_parsed = self._to_pynput_hotkey(orig_shortcut)
                # Validate by parsing — raises if malformed.
                pykeyboard.HotKey.parse(global_parsed)

                def on_global_activate():
                    if self.paused:
                        return
                    logging.debug('triggered global hotkey')
                    self.hotkey_triggered_signal.emit()

                hotkey_map[global_parsed] = on_global_activate
                logging.debug(f'Registered global hotkey: {global_parsed}')
            except Exception as e:
                logging.error(f'Failed to parse global hotkey "{orig_shortcut}": {e}')

            # --- Per-button direct hotkeys ------------------------------------
            # Custom is excluded — it needs a typed instruction from the user,
            # so a "fire directly" hotkey doesn't make sense for it.
            if self.options:
                for button_name, button_cfg in self.options.items():
                    if button_name == 'Custom':
                        continue
                    raw = (button_cfg.get('hotkey') or '').strip()
                    if not raw:
                        continue
                    try:
                        parsed = self._to_pynput_hotkey(raw)
                        # Same validation path as the global shortcut.
                        pykeyboard.HotKey.parse(parsed)
                    except Exception as e:
                        logging.error(
                            f'Invalid hotkey "{raw}" for button "{button_name}": {e}'
                        )
                        continue
                    if parsed in hotkey_map:
                        logging.warning(
                            f'Hotkey "{raw}" for button "{button_name}" '
                            f'conflicts with an already-registered binding; skipping'
                        )
                        continue
                    hotkey_map[parsed] = self._make_button_hotkey_callback(button_name)
                    logging.debug(f'Registered button hotkey: {parsed} -> {button_name}')

            if not hotkey_map:
                logging.warning('No hotkeys to register')
                return

            self.hotkey_listener = pykeyboard.GlobalHotKeys(hotkey_map)
            self.hotkey_listener.start()
        except Exception as e:
            logging.error(f'Failed to register hotkey listener: {e}')

    def _make_button_hotkey_callback(self, button_name):
        """
        Build a callback that fires `button_name` directly, bypassing the
        popup. Closes over `button_name` so we can register many distinct
        callbacks in a single GlobalHotKeys map.

        The actual fire is bounced through the Qt event loop because pynput
        invokes callbacks on its listener thread; popup/clipboard work needs
        to happen on the main thread.
        """
        def callback():
            if self.paused:
                return
            logging.debug(f'Direct hotkey fired for button "{button_name}"')
            # Match the global hotkey's behaviour: cancel any in-flight
            # request so a new fire doesn't pile up on top of a previous one.
            if self.current_provider:
                self.current_provider.cancel()
                self.output_queue = ""
            # noinspection PyTypeChecker
            QtCore.QMetaObject.invokeMethod(
                self,
                "_fire_button_directly",
                QtCore.Qt.ConnectionType.QueuedConnection,
                QtCore.Q_ARG(str, button_name)
            )
        return callback

    @Slot(str)
    def _fire_button_directly(self, button_name):
        """
        Run a button's option without showing the popup — invoked by a
        per-button direct hotkey. Mirrors the relevant parts of
        `_show_popup`: set up the async clipboard capture, then hand off
        to the worker thread (`process_option`) which waits on the holder
        and dispatches the AI call.
        """
        logging.debug(f'Firing button "{button_name}" directly')

        if self.popup_window is None or not self.popup_window.isVisible():
            self._rework_target = capture_foreground_window()

        # If the popup is currently visible (e.g., user opened it then
        # pressed a button hotkey), close it so it doesn't compete.
        if self.popup_window is not None and self.popup_window.isVisible():
            self.popup_window.close()

        # Sanity check: button must still exist in options. Could be stale
        # if options.json was edited externally between registration and
        # fire — skip gracefully rather than crash.
        if not self.options or button_name not in self.options:
            logging.warning(f'Button "{button_name}" no longer exists; ignoring hotkey')
            return

        self.current_text_holder = _SelectedTextHolder()
        self._fire_ctrl_c_and_capture_async(self.current_text_holder)

        # Same worker path as a popup-button click. process_option_thread
        # waits on the holder, surfaces "Please select text…" if empty,
        # and routes window-mode options through the response window.
        self.process_option(button_name)

    def register_hotkey(self):
        """
        Register the global hotkey for activating Writing Tools.
        """
        logging.debug('Registering hotkey')
        self.start_hotkey_listener()
        logging.debug('Hotkey registered')

    def on_hotkey_pressed(self):
        """
        Handle the hotkey press event.
        """
        logging.debug('Hotkey pressed')
        
        # Check for spam triggers
        if self.check_trigger_spam():
            logging.warning('Hotkey spam detected - ignoring the extra trigger')
            return

        # Original hotkey handling continues...
        if self.current_provider:
            logging.debug("Cancelling current provider's request")
            self.current_provider.cancel()
            self.output_queue = ""
        self._supersede_request()

        # noinspection PyTypeChecker
        QtCore.QMetaObject.invokeMethod(self, "_show_popup", QtCore.Qt.ConnectionType.QueuedConnection)

    @Slot()
    def _show_popup(self):
        """
        Show the popup window the moment the hotkey fires, and capture the
        user's selected text in parallel — popup display no longer waits on
        the clipboard. The old behaviour gated popup show on a 0.2-0.5s
        clipboard read, which on slower systems would time out and
        incorrectly fall back to the chat-only "Ask your AI" UI even when
        text *was* selected. We now assume text is always selected;
        `process_option_thread` waits on the holder before kicking off the
        AI request.
        """
        logging.debug('Showing popup window')

        if self.popup_window is None or not self.popup_window.isVisible():
            self._rework_target = capture_foreground_window()

        # Fresh holder per popup. Fire Ctrl+C *before* we create the popup
        # so the keystroke is queued while focus is still on the user's
        # source app — the actual clipboard read happens in the background.
        self.current_text_holder = _SelectedTextHolder()
        self._fire_ctrl_c_and_capture_async(self.current_text_holder)

        try:
            if self.popup_window is not None:
                logging.debug('Existing popup window found')
                if self.popup_window.isVisible():
                    logging.debug('Closing existing visible popup window')
                    self.popup_window.close()
                self.popup_window = None
            logging.debug('Creating new popup window')
            self.popup_window = ui.CustomPopupWindow.CustomPopupWindow(self)

            # Set the window icon
            icon_path = os.path.join(os.path.dirname(sys.argv[0]), 'icons', 'app_icon.png')
            if os.path.exists(icon_path): self.setWindowIcon(QtGui.QIcon(icon_path))
            # Get the screen containing the cursor
            cursor_pos = QCursor.pos()
            screen = QGuiApplication.screenAt(cursor_pos)
            if screen is None:
                screen = QGuiApplication.primaryScreen()
            screen_geometry = screen.geometry()
            logging.debug(f'Cursor is on screen: {screen.name()}')
            logging.debug(f'Screen geometry: {screen_geometry}')
            # Show the popup to get its size
            self.popup_window.show()
            self.popup_window.adjustSize()
            # Ensure the popup it's focused, even on lower-end machines
            self.popup_window.activateWindow()
            QtCore.QTimer.singleShot(100, self.popup_window.custom_input.setFocus)

            popup_width = self.popup_window.width()
            popup_height = self.popup_window.height()
            # Calculate position
            x = cursor_pos.x()
            y = cursor_pos.y() + 20  # 20 pixels below cursor
            # Adjust if the popup would go off the right edge of the screen
            if x + popup_width > screen_geometry.right():
                x = screen_geometry.right() - popup_width
            # Adjust if the popup would go off the bottom edge of the screen
            if y + popup_height > screen_geometry.bottom():
                y = cursor_pos.y() - popup_height - 10  # 10 pixels above cursor
            self.popup_window.move(x, y)
            logging.debug(f'Popup window moved to position: ({x}, {y})')
        except Exception as e:
            logging.error(f'Error showing popup window: {e}', exc_info=True)

    def _fire_ctrl_c_and_capture_async(self, holder):
        """
        Inject Ctrl+C now (must happen while focus is still on the user's
        source app, before the popup is shown), then poll the clipboard
        for the result in a background thread. Returns immediately so the
        popup can display with no perceptible delay.

        Slow systems' clipboard subsystems can take a while to populate
        after Ctrl+C — that's the whole reason this is async. The polling
        timeout is generous; an empty result after timeout means the user
        pressed the hotkey without actually selecting anything, which
        `process_option_thread` reports as a normal error.
        """
        try:
            clipboard_backup = pyperclip.paste()
        except Exception:
            clipboard_backup = ''

        self.clear_clipboard()

        kbrd = pykeyboard.Controller()
        try:
            kbrd.press(pykeyboard.Key.ctrl.value)
            kbrd.press('c')
            kbrd.release('c')
            kbrd.release(pykeyboard.Key.ctrl.value)
        except Exception as e:
            logging.error(f'Error simulating Ctrl+C: {e}')

        def _poll_clipboard():
            # Lock so concurrent hotkey presses don't trample each other's
            # in-flight captures.
            with self._capture_lock:
                text = ''
                try:
                    deadline = time.time() + 2.0
                    while time.time() < deadline:
                        try:
                            text = pyperclip.paste() or ''
                        except Exception as e:
                            logging.error(f'Error reading clipboard during poll: {e}')
                            text = ''
                        if text:
                            break
                        time.sleep(0.05)
                    holder.text = text
                    logging.debug(f'Captured selected text (len={len(text)})')
                finally:
                    try:
                        pyperclip.copy(clipboard_backup)
                    except Exception as e:
                        logging.error(f'Error restoring clipboard: {e}')
                    holder.ready.set()

        threading.Thread(target=_poll_clipboard, daemon=True).start()

    @staticmethod
    def clear_clipboard():
        """
        Clear the system clipboard.
        """
        try:
            pyperclip.copy('')
        except Exception as e:
            logging.error(f'Error clearing clipboard: {e}')

    def process_option(self, option, custom_change=None):
        """
        Spawn a worker thread that waits for the asynchronous clipboard
        capture and then runs the chosen option. Kept as a thin wrapper so
        the popup's click handler returns immediately and the GUI thread
        is never blocked on the clipboard read.
        """
        logging.debug(f'Processing option: {option}')
        self.current_option = option

        if self.paused:
            self.show_message_signal.emit(
                'Writing Tools is paused',
                'Resume it from the tray or the app window, then try again.',
            )
            return

        # A new action supersedes any request still in flight. Without this,
        # two workers can race to overwrite the active original text and the
        # first response can be paired with the second selection.
        if getattr(self, 'current_provider', None):
            logging.debug("Cancelling current provider's request")
            self.current_provider.cancel()
            self.output_queue = ""

        # Drop any stale ref so a previous run's late-arriving response can't
        # land in a now-irrelevant window. The new window (if any) is created
        # by the worker via `_setup_response_window` once the text is in.
        if hasattr(self, 'current_response_window'):
            delattr(self, 'current_response_window')

        holder = self.current_text_holder

        # Every request gets a serial so a late response from a superseded or
        # cancelled request can never paste into the document.
        self._request_serial += 1
        context = _RequestContext(option, "", serial=self._request_serial)
        self._active_request = context

        self._show_working(option)
        threading.Thread(
            target=self.process_option_thread,
            args=(option, custom_change, holder, context),
            daemon=True
        ).start()

    @Slot(str, str)
    def _setup_response_window(self, option, selected_text):
        """
        Open the response window and seed its chat history. Called from
        `process_option_thread` via `BlockingQueuedConnection` so the
        worker can rely on the window existing before it dispatches the
        AI request.
        """
        self.current_response_window = self.show_response_window(option, selected_text)
        self.current_response_window.chat_history = [
            {
                "role": "user",
                "content": f"Original text to {option.lower()}:\n\n{selected_text}"
            }
        ]

    def process_option_thread(self, option, custom_change=None, holder=None, context=None):
        """
        Worker: wait for the background clipboard capture to land, then
        either open a response window (for window-mode options) or set up
        for inline replacement, and finally run the AI request.
        """
        logging.debug(f'Starting processing thread for option: {option}')

        # The holder is passed in from `process_option` so a later hotkey
        # cannot swap the selection underneath this request.
        if holder is None:
            holder = self.current_text_holder

        # Typically near-instant since the user took time to read the popup
        # and click. The 3s ceiling is a safety net for genuinely sluggish
        # systems; if the 2s polling deadline in the capture thread tripped
        # first, the event is already set and this returns immediately.
        if holder is None or not holder.ready.wait(timeout=3.0):
            logging.warning('Timed out waiting for selected text capture')
        selected_text = (holder.text if holder else '') or ''
        if context is not None:
            context.original = selected_text
        else:
            context = _RequestContext(option, selected_text)
            self._active_request = context

        if not selected_text.strip():
            # The chat-mode fallback that used to fire here was removed when
            # popup show became instant — we no longer have a way to detect
            # "user wants to chat" vs "capture failed", so we pick the safer
            # interpretation and surface the error.
            self._finish_working()
            self.show_message_signal.emit('Error', 'Please select text to use this option.')
            return

        if not self._provider_ready():
            self._finish_working()
            return

        self.working_stage_signal.emit('Thinking')

        if self.options[option]['open_in_window']:
            QtCore.QMetaObject.invokeMethod(
                self,
                '_setup_response_window',
                QtCore.Qt.ConnectionType.BlockingQueuedConnection,
                QtCore.Q_ARG(str, option),
                QtCore.Q_ARG(str, selected_text)
            )
            self._finish_working()

        try:
            selected_prompt = self.options.get(option, ('', ''))
            prompt_prefix = selected_prompt['prefix']
            system_instruction = selected_prompt['instruction']
            if option == 'Custom':
                prompt = f"{prompt_prefix}Described change: {custom_change}\n\nText: {selected_text}"
            else:
                prompt = f"{prompt_prefix}{selected_text}"

            self.output_queue = ""

            logging.debug(f'Getting response from provider for option: {option}')

            if self.options[option]['open_in_window']:
                logging.debug('Getting response for window display')
                response = self.current_provider.get_response(system_instruction, prompt, return_response=True)
                logging.debug(f'Got response of length: {len(response) if response else 0}')

                if hasattr(self, 'current_response_window'):
                    # noinspection PyTypeChecker
                    QtCore.QMetaObject.invokeMethod(
                        self.current_response_window,
                        'set_text',
                        QtCore.Qt.ConnectionType.QueuedConnection,
                        QtCore.Q_ARG(str, response)
                    )
                    logging.debug('Invoked set_text on response window')

                if response and not response.startswith("An error occurred"):
                    QtCore.QMetaObject.invokeMethod(
                        self,
                        '_save_window_rework',
                        QtCore.Qt.ConnectionType.QueuedConnection,
                        QtCore.Q_ARG(str, option),
                        QtCore.Q_ARG(str, selected_text),
                        QtCore.Q_ARG(str, response),
                    )
            else:
                logging.debug('Getting response for direct replacement')
                response = self.current_provider.get_response(
                    system_instruction, prompt, return_response=True
                )
                QtCore.QMetaObject.invokeMethod(
                    self,
                    '_deliver_response',
                    QtCore.Qt.ConnectionType.QueuedConnection,
                    QtCore.Q_ARG(int, context.serial),
                    QtCore.Q_ARG(str, response or ''),
                )
                logging.debug('Response processed')

        except Exception as e:
            logging.error(f'An error occurred: {e}', exc_info=True)
            self._finish_working()

            if "Resource has been exhausted" in str(e):
                self.show_message_signal.emit('Error - Rate Limit Hit', 'Whoops! You\'ve hit the per-minute rate limit of the Gemini API. Please try again in a few moments.\n\nIf this happens often, simply switch to a Gemini model with a higher usage limit in Settings.')
            else:
                self.show_message_signal.emit('Error', f'An error occurred: {e}')

    @Slot(str, str)
    def show_message_box(self, title, message):
        """
        Show a message box with the given title and message.
        """
        self._hide_working()
        self._active_request = None
        QMessageBox.warning(None, title, message)

    def _show_working(self, option):
        """Put a visible, non-activating progress pill on screen at once."""
        self._hide_working()
        anchor = QCursor.pos()
        popup = self.popup_window
        if popup is not None and popup.isVisible():
            anchor = popup.geometry().topLeft()
        pill = ui.WorkingPill.WorkingPill(option, palette=self.design_palette)
        pill.cancelled.connect(self._cancel_active_request)
        self.working_pill = pill
        pill.show_near(anchor)

    @Slot(str)
    def _set_working_stage(self, stage):
        if self.working_pill is not None:
            self.working_pill.set_stage(stage)

    def _hide_working(self):
        pill, self.working_pill = self.working_pill, None
        if pill is not None:
            pill.stop()

    def _finish_working(self):
        """Hide the pill from the worker thread without touching Qt directly."""
        QtCore.QMetaObject.invokeMethod(
            self, '_hide_working', QtCore.Qt.ConnectionType.QueuedConnection
        )

    def _cancel_active_request(self):
        context = self._active_request
        if context is not None:
            context.cancelled = True
        self._active_request = None
        self._request_serial += 1
        self.working_pill = None
        logging.debug('Rewrite cancelled by the user')

    def _supersede_request(self):
        """A fresh hotkey press or action drops the result still in flight."""
        self._request_serial += 1
        self._active_request = None
        self._hide_working()

    @Slot(int, str)
    def _deliver_response(self, serial, text):
        """Apply a response only if it belongs to the request still on screen."""
        context = self._active_request
        if context is None or context.cancelled or context.serial != serial:
            logging.debug('Dropping a response for a superseded request')
            return
        self._hide_working()
        if not text.strip():
            self._active_request = None
            self.show_message_signal.emit(
                'No response',
                'The AI returned nothing for that request. Try again, or check the provider in Settings.',
            )
            return
        self.replace_text(text)

    def show_response_window(self, option, text):
        """
        Show the response in a new window instead of pasting it.
        """
        response_window = ui.ResponseWindow.ResponseWindow(self, f"{option}")
        response_window.selected_text = text  # Store the text for regeneration
        response_window.show()
        return response_window

    def _history_path(self):
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        if not base:
            base = os.path.join(os.path.expanduser("~"), ".writingtools")
        return os.path.join(base, "history.db")

    def _save_rework_to_history(self, rework):
        if not self.history_enabled or self.history_store is None:
            return False
        try:
            self.history_store.add(rework)
        except Exception:
            logging.exception("Could not save the rewrite to history")
            return False
        if self.history_window is not None and self.history_window.isVisible():
            self.history_window.refresh()
        self._refresh_dashboard()
        return True

    def _history_config_changed(self, config):
        self.history_enabled = bool(config.get('history_enabled', True))
        self.save_config(config)
        self._refresh_dashboard()

    def _refresh_dashboard(self):
        if self.dashboard_window is not None and self.dashboard_window.isVisible():
            self.dashboard_window.refresh()

    @Slot(str, str, str)
    def _save_window_rework(self, option, original, revised):
        """Window results belong in History too, not only inline replacements."""
        rework = Rework.create(option, original, revised)
        if rework.has_changes:
            self._save_rework_to_history(rework)

    def show_history(self):
        logging.debug('Showing rewrite history')
        if self.history_store is None:
            self.show_message_signal.emit(
                'History unavailable',
                'Writing Tools could not open the local history database.',
            )
            return
        if self.history_window is None:
            self.history_window = ui.HistoryWindow.HistoryWindow(
                self.history_store,
                self.config or {},
                on_config_change=self._history_config_changed,
                on_entries_change=self._refresh_dashboard,
            )
        self.history_window.show_window()

    def show_dashboard(self):
        """Open the main window. It is the app, not a tray detour."""
        logging.debug('Showing the dashboard')
        if not self.config:
            if self.onboarding_window is not None:
                self.onboarding_window.show()
                self.onboarding_window.raise_()
                self.onboarding_window.activateWindow()
            else:
                self.show_onboarding()
            return
        if self.dashboard_window is None:
            self.dashboard_window = ui.DashboardWindow.DashboardWindow(
                self, self.history_store
            )
        if self.tray_icon is None:
            self.create_tray_icon()
        self.dashboard_window.show_window()

    def _make_rework_card(self, rework, on_undo, on_close, saved):
        return ReworkCard(
            rework,
            on_undo,
            on_close,
            saved_to_history=saved,
            on_history=self.show_history,
        )

    @staticmethod
    def _restore_clipboard(copy, backup):
        """Put the user's clipboard back after the target app reads the paste.

        The delay has to happen, but it does not have to happen on the UI
        thread. Blocking here delayed the receipt by a fifth of a second on
        every rewrite.
        """
        time.sleep(0.2)
        try:
            copy(backup)
        except Exception:
            logging.exception('Could not restore the clipboard')

    def _undo_rework(self, rework):
        target = self._rework_target
        self._rework_target = None
        logging.debug("Undoing rework in the source window")
        QtCore.QTimer.singleShot(120, lambda: undo_last_paste(target))

    def replace_text(self, new_text):
        """
        Replaces the text by pasting in the LLM generated text. With "Key Points" and "Summary", invokes a window with the output instead.
        """
        self._hide_working()
        error_message = 'ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST'

        # Confirm new_text exists and is a string
        if new_text and isinstance(new_text, str):
            self.output_queue += new_text
            current_output = self.output_queue.strip()  # Strip whitespace for comparison

            # If the new text is the error message, show a message box
            if current_output == error_message:
                self._active_request = None
                self.show_message_signal.emit('Error', 'The text is incompatible with the requested change.')
                return

            # Check if we're building up to the error message (to prevent partial pasting)
            if len(current_output) <= len(error_message):
                clean_current = ''.join(current_output.split())
                clean_error = ''.join(error_message.split())
                if clean_current == clean_error[:len(clean_current)]:
                    return

            logging.debug('Processing output text')
            try:
                # Window-mode responses are delivered through set_text. This
                # signal path only needs to turn a provider failure into the
                # window's error state instead of silently spinning.
                if hasattr(self, 'current_response_window'):
                    if current_output.startswith("An error occurred"):
                        window = self.current_response_window
                        self.output_queue = ""
                        self._active_request = None
                        if hasattr(window, 'show_failure'):
                            window.show_failure("Couldn't get a response", current_output)
                        else:
                            self.show_message_signal.emit('Error', current_output)
                    return
                else:
                    # For other options, use the original clipboard-based replacement
                    cleaned_text = self.output_queue.rstrip('\n')

                    if cleaned_text.startswith("An error occurred"):
                        self._active_request = None
                        self.show_message_signal.emit('Error', cleaned_text)
                        self.output_queue = ""
                        return

                    clipboard_backup = pyperclip.paste()
                    request = self._active_request
                    original_text = request.original if request else ""

                    # The result belongs in the window the writer started in.
                    # Without this, a rewrite that took a few seconds lands in
                    # whatever app or field happens to have focus.
                    target = self._rework_target
                    if target and not is_foreground(target):
                        focus_window(target)
                        time.sleep(0.08)

                    pyperclip.copy(cleaned_text)
                    
                    kbrd = pykeyboard.Controller()
                    def press_ctrl_v():
                        kbrd.press(pykeyboard.Key.ctrl.value)
                        kbrd.press('v')
                        kbrd.release('v')
                        kbrd.release(pykeyboard.Key.ctrl.value)

                    press_ctrl_v()
                    threading.Thread(
                        target=WritingToolApp._restore_clipboard,
                        args=(pyperclip.copy, clipboard_backup),
                        daemon=True,
                    ).start()

                    if (
                        original_text.strip()
                        and cleaned_text
                        and not cleaned_text.startswith("An error occurred")
                    ):
                        self.rework_controller.present(
                            request.option if request else "Rework",
                            original_text,
                            cleaned_text,
                        )
                        self._active_request = None

                if not hasattr(self, 'current_response_window'):
                    self.output_queue = ""

            except Exception as e:
                logging.error(f'Error processing output: {e}')
        else:
            logging.debug('No new text to process')

    def create_tray_icon(self):
        """
        Create the system tray icon for the application.
        """
        if self.tray_icon:
            logging.debug('Tray icon already exists')
            return

        logging.debug('Creating system tray icon')
        icon_path = os.path.join(os.path.dirname(sys.argv[0]), 'icons', 'app_icon.png')
        if not os.path.exists(icon_path):
            logging.warning(f'Tray icon not found at {icon_path}')
            # Use a default icon if not found
            self.tray_icon = QtWidgets.QSystemTrayIcon(self)
        else:
            self.tray_icon = QtWidgets.QSystemTrayIcon(QtGui.QIcon(icon_path), self)
        # Set the tooltip (hover name) for the tray icon
        self.tray_icon.setToolTip("Writing Tools")
        self.tray_menu = QtWidgets.QMenu()
        self.tray_icon.setContextMenu(self.tray_menu)

        self.update_tray_menu()
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()
        logging.debug('Tray icon displayed')

    def _on_tray_activated(self, reason):
        """A left click opens the app window, the way a tray app should behave."""
        if reason == QtWidgets.QSystemTrayIcon.ActivationReason.Trigger:
            self.show_dashboard()

    def update_tray_menu(self):
        """
        Update the tray menu with all menu items, including pause functionality
        and proper translations.
        """
        self.tray_menu.clear()

        self.apply_dark_mode_styles(self.tray_menu)

        open_action = self.tray_menu.addAction(self._('Open Writing Tools'))
        open_action.triggered.connect(self.show_dashboard)
        self.tray_menu.addSeparator()

        history_action = self.tray_menu.addAction(self._('Rewrite History'))
        history_action.triggered.connect(self.show_history)

        self.tray_menu.addSeparator()

        settings_action = self.tray_menu.addAction(self._('Settings'))
        settings_action.triggered.connect(self.show_settings)

        self.toggle_action = self.tray_menu.addAction(
            self._('Resume') if self.paused else self._('Pause')
        )
        self.toggle_action.triggered.connect(self.toggle_paused)

        self.tray_menu.addSeparator()

        about_action = self.tray_menu.addAction(self._('About'))
        about_action.triggered.connect(self.show_about)

        exit_action = self.tray_menu.addAction(self._('Exit'))
        exit_action.triggered.connect(self.exit_app)
        
    def toggle_paused(self):
        """Toggle the paused state of the application."""
        logging.debug('Toggle paused state')
        self.paused = not self.paused
        if self.toggle_action is not None:
            self.toggle_action.setText(self._('Resume') if self.paused else self._('Pause'))
        self._refresh_dashboard()
        logging.debug('App is paused' if self.paused else 'App is resumed')

    def apply_dark_mode_styles(self, menu):
        """Apply the current paper palette to the native tray menu."""
        p = self.design_palette
        palette = menu.palette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor(p.surface))
        palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(p.ink))
        palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(p.accent))
        palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(p.accent_text))
        menu.setPalette(palette)


    """
    The function below (process_followup_question) processes follow-up questions in the chat interface for Summary, Key Points, and Table operations.

    This method handles the complex interaction between the UI, chat history, and AI providers:

    1. Chat History Management:
    - Maintains a list of all messages (original text, summary, follow-ups)
    - Properly formats roles (user/assistant) for each message
    - Preserves conversation context across multiple questions (until the Window is closed)

    2. Provider-Specific Handling:
    a) Gemini:
        - Converts internal roles to Gemini's user/model format
        - Uses chat sessions with proper history formatting
        - Maintains context through chat.send_message()
    
    b) OpenAI-compatible:
        - Uses standard OpenAI message array format
        - Includes system instruction and full conversation history
        - Properly maps internal roles to OpenAI roles

    3. Flow:
    a) User asks follow-up question
    b) Question is added to chat history
    c) Full history is formatted for the current provider
    d) Response is generated while maintaining context
    e) Response is displayed in chat UI
    f) New response is added to history for future context

    4. Threading:
    - Runs in a separate thread to prevent UI freezing
    - Uses signals to safely update UI from background thread
    - Handles errors too

    Args:
        response_window: The ResponseWindow instance managing the chat UI
        question: The follow-up question from the user

    This implementation is a bit convoluted, but it allows us to manage chat history & model roles across both providers! :3
    """

    def process_followup_question(self, response_window, question):
        """
        Process a follow-up question in the chat window.
        """
        logging.debug(f'Processing follow-up question: {question}')
        
        def process_thread():
            logging.debug('Starting follow-up processing thread')
            if not self._provider_ready():
                self.followup_response_signal.emit("Sorry, no AI provider is set up. Open Settings to choose one.")
                return
            try:
                if not response_window.chat_history:
                    logging.error("No chat history found")
                    self.show_message_signal.emit('Error', 'Chat history not found')
                    return

                # Add current question to chat history
                response_window.chat_history.append({
                    "role": "user",
                    "content": question
                })
                
                # Get chat history
                history = response_window.chat_history.copy()
                
                # System instruction based on original option
                system_instruction = "You are a helpful AI assistant. Provide clear and direct responses, maintaining the same format and style as your previous responses. If appropriate, use Markdown formatting to make your response more readable."
                
                logging.debug('Sending request to AI provider')
                
                # Format conversation differently based on provider
                if isinstance(self.current_provider, GeminiProvider):
                    # Gemini takes the system instruction via its config object,
                    # not as an in-history message. We pass the raw chat history
                    # (user/assistant turns); GeminiProvider handles role mapping
                    # and drops any "system" entries internally.
                    response_text = self.current_provider.get_response(
                        system_instruction,
                        history,
                        return_response=True
                    )

                elif isinstance(self.current_provider, OllamaProvider):  #
                    # For Ollama, prepare messages with system instruction and history
                    messages = [{"role": "system", "content": system_instruction}]

                    for msg in history:
                        messages.append({
                            "role": msg["role"],
                            "content": msg["content"]
                        })

                    # Get response from Ollama
                    response_text = self.current_provider.get_response(
                        system_instruction,
                        messages,
                        return_response=True
                    )

                else:
                    # For OpenAI/compatible providers, prepare messages array, add system message
                    messages = [{"role": "system", "content": system_instruction}]

                    # Add history messages (including latest question)
                    for msg in history:
                        # Convert 'assistant' role to 'assistant' for OpenAI
                        role = "assistant" if msg["role"] == "assistant" else "user"
                        messages.append({"role": role, "content": msg["content"]})
                    
                    # Get response by passing the full messages array
                    response_text = self.current_provider.get_response(
                        system_instruction,
                        messages,  # Pass messages array directly
                        return_response=True
                    )

                logging.debug(f'Got response of length: {len(response_text)}')
                
                # Add response to chat history
                response_window.chat_history.append({
                    "role": "assistant",
                    "content": response_text
                })
                
                # Emit response via signal
                self.followup_response_signal.emit(response_text)

            except Exception as e:
                logging.error(f'Error processing follow-up question: {e}', exc_info=True)

                if "Resource has been exhausted" in str(e):
                    self.show_message_signal.emit('Error - Rate Limit Hit', 'Whoops! You\'ve hit the per-minute rate limit of the Gemini API. Please try again in a few moments.\n\nIf this happens often, simply switch to a Gemini model with a higher usage limit in Settings.')
                    self.followup_response_signal.emit("Sorry, an error occurred while processing your question.")
                else:
                    self.show_message_signal.emit('Error', f'An error occurred: {e}')
                    self.followup_response_signal.emit("Sorry, an error occurred while processing your question.")

        # Start the thread
        threading.Thread(target=process_thread, daemon=True).start()

    def show_settings(self, providers_only=False):

        """
        Show the settings window.
        """
        logging.debug('Showing settings window')

        if self.settings_window is not None:
            if self.settings_window.built_providers_only == providers_only:
                self.settings_window.show()
                self.settings_window.raise_()
                self.settings_window.activateWindow()
                return
            self.settings_window.close()
            self.settings_window.deleteLater()
            self.settings_window = None

        self.settings_window = ui.SettingsWindow.SettingsWindow(self, providers_only=providers_only)
        self.settings_window.close_signal.connect(self._abandon_setup)
        self.settings_window.retranslate_ui()
        self.settings_window.show()


    def show_about(self):
        """
        Show the about window.
        """
        logging.debug('Showing about window')
        if not self.about_window:
            self.about_window = ui.AboutWindow.AboutWindow()
        self.about_window.show()

    def setup_ctrl_c_listener(self):
        """
        Listener for Ctrl+C to exit the app.
        """
        signal.signal(signal.SIGINT, lambda signum, frame: self.handle_sigint(signum, frame))
        # This empty timer is needed to make sure that the sigint handler gets checked inside the main loop:
        # without it, the sigint handle would trigger only when an event is triggered, either by a hotkey combination
        # or by another GUI event like spawning a new window. With this we trigger it every 100ms with an empy lambda
        # so that the signal handler gets checked regularly.
        self.ctrl_c_timer = QtCore.QTimer()
        self.ctrl_c_timer.start(100)
        self.ctrl_c_timer.timeout.connect(lambda: None)
    def handle_sigint(self, signum, frame):
        """
        Handle the SIGINT signal (Ctrl+C) to exit the app gracefully.
        """
        logging.info("Received SIGINT. Exiting...")
        self.exit_app()

    def exit_app(self):
        """
        Exit the application.
        """
        logging.debug('Stopping the listener')
        if self.hotkey_listener is not None:
            self.hotkey_listener.stop()
        self.rework_controller.dismiss()
        if self.history_window is not None:
            self.history_window.close()
        logging.debug('Exiting application')
        self.quit()
