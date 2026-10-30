import copy
import os
import sys
import threading

from aiprovider import AIProvider
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QScrollArea

from rework.theme import current_palette
from ui import ActionStore, ModelCatalog, ProviderPresets
from ui.AutostartManager import AutostartManager
from ui.CustomPopupWindow import ButtonEditDialog
from ui.UIUtils import UIUtils
from ui.design import (
    GAP,
    PAGE_MARGIN,
    divider,
    field_label,
    ghost_button,
    page_header,
    primary_button,
    section_card,
)

_ = lambda x: x

WINDOW_WIDTH = 680
MAX_WINDOW_HEIGHT = 720
SCREEN_HEIGHT_FRACTION = 0.85


class SettingsWindow(QtWidgets.QWidget):
    """
    The settings window for the application.

    Content scrolls above a sticky footer. In providers_only mode it shows
    only the AI provider section, used by first-run setup.
    """
    close_signal = QtCore.Signal()
    models_loaded = QtCore.Signal(list)
    models_failed = QtCore.Signal(str)

    def __init__(self, app, providers_only=False):
        super().__init__()
        self.app = app
        self.current_provider_layout = None
        self.providers_only = providers_only
        self.built_providers_only = providers_only
        self.provider_dropdown = None
        self.provider_container = None
        self.autostart_checkbox = None
        self.shortcut_input = None
        self.init_ui()
        self.retranslate_ui()
        self.models_loaded.connect(self._on_models_loaded)
        self.models_failed.connect(self._on_models_failed)


    def retranslate_ui(self):
        self.setWindowTitle(_("Settings"))

    def init_provider_ui(self, provider: AIProvider, layout):
        """
        Initialize the user interface for the provider, including logo, name, description and all settings.
        """
        if self.current_provider_layout:
            self.current_provider_layout.setParent(None)
            UIUtils.clear_layout(self.current_provider_layout)
            self.current_provider_layout.deleteLater()

        self.current_provider_layout = QtWidgets.QVBoxLayout()
        self.current_provider_layout.setSpacing(GAP)

        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setSpacing(8)

        if provider.logo:
            logo_path = os.path.join(os.path.dirname(sys.argv[0]), 'icons', f"provider_{provider.logo}.png")
            if os.path.exists(logo_path):
                targetPixmap = UIUtils.resize_and_round_image(QImage(logo_path), 30, 15)
                logo_label = QtWidgets.QLabel()
                logo_label.setPixmap(targetPixmap)
                header_layout.addWidget(logo_label)

        provider_name_label = QtWidgets.QLabel(provider.provider_name)
        provider_name_label.setObjectName("SectionTitle")
        header_layout.addWidget(provider_name_label)
        header_layout.addStretch()
        self.current_provider_layout.addLayout(header_layout)

        if provider.description:
            description_label = QtWidgets.QLabel(provider.description)
            description_label.setObjectName("Meta")
            description_label.setWordWrap(True)
            self.current_provider_layout.addWidget(description_label)

        actions = []
        if hasattr(provider, 'ollama_button_text'):
            actions.append((provider.ollama_button_text, provider.ollama_button_action))
            actions.append((provider.button_text, provider.button_action))
        elif provider.button_text:
            actions.append((provider.button_text, provider.button_action))

        self.provider_action_buttons = []
        if actions:
            button_layout = QtWidgets.QHBoxLayout()
            button_layout.setSpacing(8)
            for text, action in actions:
                button = QtWidgets.QPushButton(text)
                button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
                button.clicked.connect(action)
                button_layout.addWidget(button)
                self.provider_action_buttons.append(button)
            button_layout.addStretch()
            self.current_provider_layout.addLayout(button_layout)

        # Initialize config if needed
        if "providers" not in self.app.config:
            self.app.config["providers"] = {}
        if provider.provider_name not in self.app.config["providers"]:
            self.app.config["providers"][provider.provider_name] = {}

        self.preset_combo = None
        self.preset_note = None
        self._active_preset = ""
        self.model_combo = None
        self.model_button = None
        self.model_status = None
        self._model_loading = False
        if provider.provider_name == "OpenAI Compatible (For Experts)":
            self._build_preset_block()

        # Add provider settings
        for setting in provider.settings:
            setting.set_value(self.app.config["providers"][provider.provider_name].get(setting.name, setting.default_value))
            setting.render_to_layout(self.current_provider_layout)

        if self.preset_combo is not None:
            self._init_preset_state()
            self._build_model_picker()

        layout.addLayout(self.current_provider_layout)

    def _build_preset_block(self):
        self.current_provider_layout.addWidget(field_label(_("Quick setup")))
        self.preset_combo = QtWidgets.QComboBox()
        self.preset_combo.setAccessibleName(_("Service preset"))
        self.preset_combo.addItem(_("Choose a service..."), "")
        for preset in ProviderPresets.load():
            self.preset_combo.addItem(preset.name, preset.id)
        self.current_provider_layout.addWidget(self.preset_combo)

        self.preset_note = QtWidgets.QLabel("")
        self.preset_note.setObjectName("Meta")
        self.preset_note.setWordWrap(True)
        self.preset_note.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.preset_note.setOpenExternalLinks(True)
        self.current_provider_layout.addWidget(self.preset_note)

    def _init_preset_state(self):
        saved = ""
        if isinstance(self.app.config, dict):
            saved = self.app.config.get("provider_preset") or ""
        index = self.preset_combo.findData(saved)
        self.preset_combo.blockSignals(True)
        self.preset_combo.setCurrentIndex(index if index > 0 else 0)
        self.preset_combo.blockSignals(False)
        if index > 0:
            self._active_preset = saved
            self._show_preset_note(saved)
            self._set_provider_buttons_visible(False)
        self.preset_combo.currentIndexChanged.connect(self._apply_preset)

    def _set_provider_buttons_visible(self, visible: bool):
        for button in getattr(self, "provider_action_buttons", []):
            button.setVisible(visible)

    def _apply_preset(self, index):
        preset_id = self.preset_combo.currentData()
        self._active_preset = preset_id or ""
        self._set_provider_buttons_visible(not preset_id)
        if not preset_id:
            self.preset_note.setText("")
            return
        preset = ProviderPresets.get(preset_id)
        if preset is None:
            self.preset_note.setText("")
            return
        provider = self.app.providers[self.provider_dropdown.currentIndex()]
        for setting in provider.settings:
            if setting.name == "api_base" and getattr(setting, "input", None) is not None:
                setting.input.setText(preset.base_url)
            elif setting.name == "api_model" and getattr(setting, "input", None) is not None:
                setting.input.setText(preset.model)
        if self.model_combo is not None:
            self.model_combo.blockSignals(True)
            self.model_combo.clear()
            self.model_combo.setEnabled(False)
            self.model_combo.blockSignals(False)
        if self.model_status is not None:
            self.model_status.setText(
                _("Enter your API key, then load the list. The model field stays editable.")
            )
        self._show_preset_note(preset_id)

    def _show_preset_note(self, preset_id):
        preset = ProviderPresets.get(preset_id)
        if preset is None or self.preset_note is None:
            return
        parts = []
        if preset.note:
            parts.append(preset.note)
        if preset.key_url:
            parts.append(f'<a href="{preset.key_url}">Get an API key</a>')
        if preset.docs_url:
            parts.append(f'<a href="{preset.docs_url}">Docs</a>')
        self.preset_note.setText(" \u00b7 ".join(parts))

    def _build_model_picker(self):
        self.current_provider_layout.addWidget(field_label(_("Available models")))
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(8)
        self.model_combo = QtWidgets.QComboBox()
        self.model_combo.setAccessibleName(_("Available models"))
        self.model_combo.setEnabled(False)
        self.model_combo.currentTextChanged.connect(self._pick_model)
        row.addWidget(self.model_combo, 1)

        self.model_button = QtWidgets.QPushButton(_("Load models"))
        self.model_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.model_button.clicked.connect(self._load_models)
        row.addWidget(self.model_button)
        self.current_provider_layout.addLayout(row)

        self.model_status = QtWidgets.QLabel(
            _("Enter your API key, then load the list. The model field stays editable.")
        )
        self.model_status.setObjectName("Meta")
        self.model_status.setWordWrap(True)
        self.current_provider_layout.addWidget(self.model_status)

    def _provider_settings(self):
        provider = self.app.providers[self.provider_dropdown.currentIndex()]
        return {setting.name: setting for setting in provider.settings}

    def _setting_input(self, name):
        setting = self._provider_settings().get(name)
        return getattr(setting, "input", None)

    def _pick_model(self, model):
        if not model.strip():
            return
        field = self._setting_input("api_model")
        if field is not None:
            field.setText(model)

    def _load_models(self):
        if self._model_loading:
            return
        base = self._setting_input("api_base")
        key = self._setting_input("api_key")
        base_url = base.text() if base is not None else ""
        try:
            ModelCatalog.models_url(base_url)
        except ModelCatalog.ModelFetchError as error:
            self.model_status.setText(str(error))
            return

        self._model_loading = True
        self.model_button.setEnabled(False)
        self.model_status.setText(_("Loading models..."))
        api_key = key.text() if key is not None else ""

        def work():
            try:
                models = ModelCatalog.fetch_models(base_url, api_key)
            except Exception as error:
                try:
                    self.models_failed.emit(str(error))
                except RuntimeError:
                    pass
            else:
                try:
                    self.models_loaded.emit(models)
                except RuntimeError:
                    pass

        threading.Thread(target=work, daemon=True).start()

    def _on_models_loaded(self, models):
        self._model_loading = False
        if self.model_button is not None:
            self.model_button.setEnabled(True)
        self._apply_models(models)

    def _on_models_failed(self, message):
        self._model_loading = False
        if self.model_button is not None:
            self.model_button.setEnabled(True)
        if self.model_status is not None:
            self.model_status.setText(message)

    def _apply_models(self, models):
        if self.model_combo is None:
            return
        current = self._setting_input("api_model")
        current_text = current.text() if current is not None else ""
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItems(models)
        self.model_combo.setEnabled(bool(models))
        self.model_combo.setCurrentIndex(self.model_combo.findText(current_text))
        self.model_combo.blockSignals(False)
        if models and self.model_status is not None:
            free_count = sum(1 for model in models if model.endswith(":free"))
            note = _("{count} models.").format(count=len(models))
            if free_count:
                note += " " + _("Models marked :free may be limited to specific apps.")
            note += " " + _("Pick one to fill the model field.")
            self.model_status.setText(note)

    def init_ui(self):
        """
        Build the settings window: a scrollable body, then a sticky footer.
        """
        self.setWindowTitle(_('Settings'))
        self.setFixedWidth(WINDOW_WIDTH)

        UIUtils.setup_window_and_layout(self)
        p = current_palette()
        self.setStyleSheet(
            f"QFrame#Callout {{ background-color: {p.accent_soft}; border: none; border-radius: 8px; }}"
        )
        main_layout = QtWidgets.QVBoxLayout(self.background)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_content = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        content_layout.setSpacing(16)

        if self.providers_only:
            title = _("Set up an AI provider")
            subtitle = _("Step 2 of 2. Pick a provider and add its details.")
        else:
            title = _("Settings")
            subtitle = _("Shortcut, actions, and your AI provider.")
        content_layout.addWidget(page_header(title, subtitle))

        if not self.providers_only:
            general_card, general_layout = section_card(
                _("General"),
                _("The key that opens the popup, and whether Writing Tools starts with your computer."),
            )

            if AutostartManager.get_startup_path():
                self.autostart_checkbox = QtWidgets.QCheckBox(_("Start on Boot"))
                self.autostart_checkbox.setChecked(AutostartManager.check_autostart())
                self.autostart_checkbox.stateChanged.connect(self.toggle_autostart)
                general_layout.addWidget(self.autostart_checkbox)

            general_layout.addWidget(field_label(_("Shortcut Key:")))
            self.shortcut_input = QtWidgets.QLineEdit(self.app.config.get('shortcut', 'ctrl+space'))
            self.shortcut_input.setAccessibleName(_("Shortcut Key"))
            general_layout.addWidget(self.shortcut_input)

            content_layout.addWidget(general_card)
            self._build_actions_card(content_layout)

        provider_card, provider_layout = section_card(
            _("AI Provider"),
            _("The service that answers your rewrites."),
        )
        provider_layout.addWidget(field_label(_("Choose AI Provider:")))

        self.provider_dropdown = QtWidgets.QComboBox()
        self.provider_dropdown.setAccessibleName(_("AI Provider"))
        self.provider_dropdown.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)

        current_provider = self.app.config.get('provider', self.app.providers[0].provider_name)
        for provider in self.app.providers:
            self.provider_dropdown.addItem(provider.provider_name)
        self.provider_dropdown.setCurrentIndex(self.provider_dropdown.findText(current_provider))
        provider_layout.addWidget(self.provider_dropdown)

        self.provider_container = QtWidgets.QVBoxLayout()
        provider_layout.addLayout(self.provider_container)
        content_layout.addWidget(provider_card)
        content_layout.addStretch()

        provider_instance = self.app.providers[self.provider_dropdown.currentIndex()]
        self.init_provider_ui(provider_instance, self.provider_container)

        self.provider_dropdown.currentIndexChanged.connect(
            lambda: self.init_provider_ui(self.app.providers[self.provider_dropdown.currentIndex()], self.provider_container)
        )

        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area, 1)

        main_layout.addWidget(divider())
        footer = QtWidgets.QWidget()
        footer_layout = QtWidgets.QHBoxLayout(footer)
        footer_layout.setContentsMargins(PAGE_MARGIN, 16, PAGE_MARGIN, 16)
        footer_layout.setSpacing(GAP)

        if not self.providers_only:
            callout = QtWidgets.QFrame()
            callout.setObjectName("Callout")
            callout_layout = QtWidgets.QHBoxLayout(callout)
            callout_layout.setContentsMargins(12, 8, 12, 8)
            restart_notice = QtWidgets.QLabel(
                _("Provider and shortcut apply when you save. Actions apply right away.")
            )
            restart_notice.setWordWrap(True)
            callout_layout.addWidget(restart_notice)
            footer_layout.addWidget(callout, 1)
        else:
            footer_layout.addStretch()

        save_button = primary_button(_("Finish AI Setup") if self.providers_only else _("Save"))
        save_button.clicked.connect(self.save_settings)
        footer_layout.addWidget(save_button)
        main_layout.addWidget(footer)

        screen = QtWidgets.QApplication.primaryScreen().geometry()
        max_height = int(screen.height() * SCREEN_HEIGHT_FRACTION)
        self.resize(WINDOW_WIDTH, min(MAX_WINDOW_HEIGHT, max_height))

    def toggle_autostart(self, state):
        """Toggle the autostart setting, and say so when Windows refuses."""
        wanted = state == 2
        if AutostartManager.set_autostart(wanted):
            return
        self.autostart_checkbox.blockSignals(True)
        self.autostart_checkbox.setChecked(not wanted)
        self.autostart_checkbox.blockSignals(False)
        QtWidgets.QMessageBox.warning(
            self,
            _("Start on Boot"),
            _(
                "Windows did not accept the startup change. Try again, or add "
                "Writing Tools to your startup apps."
            ),
        )

    def _build_actions_card(self, content_layout):
        card, layout = section_card(
            _("Actions"),
            _("The choices in the popup. Edit what each one does, or add your own."),
        )
        self.actions_host = QtWidgets.QWidget()
        self.actions_layout = QtWidgets.QVBoxLayout(self.actions_host)
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(6)

        buttons = QtWidgets.QHBoxLayout()
        add_button = ghost_button(_("Add action"))
        add_button.clicked.connect(self._add_action)
        buttons.addWidget(add_button)
        reset_button = ghost_button(_("Reset actions"))
        reset_button.clicked.connect(self._reset_actions)
        buttons.addWidget(reset_button)
        buttons.addStretch()
        layout.addLayout(buttons)
        layout.addWidget(self.actions_host)
        content_layout.addWidget(card)
        self._refresh_actions()

    def _refresh_actions(self):
        while self.actions_layout.count():
            item = self.actions_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        data = ActionStore.load()
        entries = ActionStore.actions(data)
        if not entries:
            empty = QtWidgets.QLabel(
                _("No actions yet. Add one to fill the popup.")
            )
            empty.setObjectName("Meta")
            self.actions_layout.addWidget(empty)
            return
        for name, entry in entries:
            self.actions_layout.addWidget(self._action_row(name, entry))

    def _action_row(self, name: str, entry: dict) -> QtWidgets.QWidget:
        p = current_palette()
        row = QtWidgets.QFrame()
        row.setObjectName("ActionRow")
        row.setStyleSheet(
            f"""
            QFrame#ActionRow {{
                background: {p.surface_alt};
                border: 1px solid {p.hairline};
                border-radius: 8px;
            }}
            QLabel#actionName {{
                color: {p.ink};
                font-size: 13px;
                font-weight: 600;
            }}
            QLabel#actionSummary {{
                color: {p.muted};
                font-size: 12px;
            }}
            """
        )
        layout = QtWidgets.QHBoxLayout(row)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        icon_label = QtWidgets.QLabel()
        icon_label.setFixedSize(24, 24)
        icon_path = os.path.join(
            os.path.dirname(sys.argv[0]),
            (entry.get("icon") or "") + ("_dark" if p.mode == "dark" else "_light") + ".png",
        )
        if os.path.exists(icon_path):
            icon_label.setPixmap(
                QtGui.QPixmap(icon_path).scaled(
                    18,
                    18,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
            )
        layout.addWidget(icon_label)

        instruction = " ".join((entry.get("instruction") or "").split())
        if instruction:
            row.setToolTip(instruction[:300])

        text_column = QtWidgets.QVBoxLayout()
        text_column.setSpacing(1)
        title = QtWidgets.QLabel(name)
        title.setObjectName("actionName")
        text_column.addWidget(title)
        summary = QtWidgets.QLabel(ActionStore.summary(entry))
        summary.setObjectName("actionSummary")
        summary.setWordWrap(False)
        text_column.addWidget(summary)
        layout.addLayout(text_column, 1)

        hotkey = (entry.get("hotkey") or "").strip()
        if hotkey:
            hint = QtWidgets.QLabel(hotkey)
            hint.setObjectName("actionSummary")
            layout.addWidget(hint)

        edit = ghost_button(_("Edit"))
        edit.setMinimumHeight(28)
        edit.setAccessibleName(f"Edit {name}")
        edit.clicked.connect(lambda _=False, target=name: self._edit_action(target))
        layout.addWidget(edit)

        delete = ghost_button(_("Delete"))
        delete.setMinimumHeight(28)
        delete.setAccessibleName(f"Delete {name}")
        delete.clicked.connect(lambda _=False, target=name: self._delete_action(target))
        layout.addWidget(delete)
        return row

    def _validate_action(self, data, result, exclude=None):
        name = (result.get("name") or "").strip()
        if not name:
            return None, _("Give the action a name.")
        if name != exclude and name in data:
            return None, _("An action named '{name}' already exists.").format(name=name)
        error = ActionStore.validate_hotkey(
            (result.get("hotkey") or "").strip().lower(),
            data,
            self.app.config.get("shortcut") or "ctrl+space",
            self.app._to_pynput_hotkey,
            exclude=exclude,
        )
        return name, error

    def _edit_action(self, name: str):
        data = ActionStore.load()
        if name not in data:
            return
        existing = dict(data[name])
        seed = dict(existing)
        seed["name"] = name
        dialog = ButtonEditDialog(self, seed, title=_("Edit action"))
        while dialog.exec():
            result = dialog.get_button_data()
            new_name, error = self._validate_action(data, result, exclude=name)
            if error:
                QtWidgets.QMessageBox.warning(self, _("Action not saved"), error)
                continue
            entry = ActionStore.build_entry(result, existing=existing)
            data = ActionStore.replace_entry(data, name, new_name, entry)
            if not ActionStore.save(data):
                QtWidgets.QMessageBox.warning(
                    self,
                    _("Could not save"),
                    _("Writing Tools could not write options.json."),
                )
                return
            self._actions_changed()
            return

    def _add_action(self):
        dialog = ButtonEditDialog(self, title=_("Add action"))
        while dialog.exec():
            result = dialog.get_button_data()
            data = ActionStore.load()
            new_name, error = self._validate_action(data, result)
            if error:
                QtWidgets.QMessageBox.warning(self, _("Action not saved"), error)
                continue
            data[new_name] = ActionStore.build_entry(result)
            if not ActionStore.save(data):
                QtWidgets.QMessageBox.warning(
                    self,
                    _("Could not save"),
                    _("Writing Tools could not write options.json."),
                )
                return
            self._actions_changed()
            return

    def _delete_action(self, name: str):
        answer = QtWidgets.QMessageBox.question(
            self,
            _("Delete action"),
            _("Remove the '{name}' action from the popup?").format(name=name),
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        data = ActionStore.load()
        data.pop(name, None)
        if not ActionStore.save(data):
            QtWidgets.QMessageBox.warning(
                self,
                _("Could not save"),
                _("Writing Tools could not write options.json."),
            )
            return
        self._actions_changed()

    def _reset_actions(self):
        answer = QtWidgets.QMessageBox.question(
            self,
            _("Reset actions"),
            _("Restore the default actions and remove your custom ones?"),
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        if not ActionStore.save(ActionStore.defaults()):
            QtWidgets.QMessageBox.warning(
                self,
                _("Could not save"),
                _("Writing Tools could not write options.json."),
            )
            return
        self._actions_changed()

    def _actions_changed(self):
        self.app.load_options()
        self.app.register_hotkey()
        self._refresh_actions()

    def save_settings(self):
        """
        Persist the provider and general settings, then activate the provider.

        The candidate provider is validated on a copy before anything is written,
        so a rejected save leaves the config file, the live provider and the
        hotkey untouched.
        """
        shortcut = None
        if not self.providers_only:
            shortcut = self.shortcut_input.text().strip()
            error = self.app.validate_shortcut(shortcut)
            if error:
                QtWidgets.QMessageBox.warning(self, _("Shortcut not valid"), error)
                self.shortcut_input.setFocus()
                return

        provider = self.app.providers[self.provider_dropdown.currentIndex()]
        values = {setting.name: setting.get_value() for setting in provider.settings}

        try:
            copy.copy(provider).load_config(values)
        except Exception as error:
            QtWidgets.QMessageBox.warning(
                self,
                _("AI provider not ready"),
                _(
                    "{provider} could not start: {error}\n\n"
                    "Fix the provider's settings, then click {action} again."
                ).format(
                    provider=provider.provider_name,
                    error=error,
                    action=_("Finish AI Setup") if self.providers_only else _("Save"),
                ),
            )
            return

        provider.load_config(values)

        if not self.providers_only:
            self.app.config['shortcut'] = shortcut

        self.app.config['streaming'] = False
        self.app.config['provider'] = provider.provider_name

        # Mark config as updated for v8 (new users start with this flag set)
        self.app.config['is_config_file_updated_for_v8'] = True

        if provider.provider_name == "OpenAI Compatible (For Experts)":
            self.app.config["provider_preset"] = self._active_preset
        provider.save_config()

        # A successful save means the app is usable. The tray is created even
        # when setup was opened from the dashboard without one.
        self.app.create_tray_icon()

        self.app.current_provider = provider
        self.app.register_hotkey()
        was_setup = self.providers_only
        self.providers_only = False
        self.close()
        if was_setup or getattr(self.app, "dashboard_window", None) is not None:
            self.app.show_dashboard()

    def closeEvent(self, event):
        """Handle window close event."""
        if self.providers_only:
            self.close_signal.emit()
        super().closeEvent(event)
