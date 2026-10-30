"""Shared fake host and temporary app files for the one-window shell tests.

These helpers never touch the real options.json, provider_presets.json, or the
user's history database. They build the real AppShell and views against a fake
app object, so the widgets under test are production widgets.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from PySide6 import QtCore

from aiprovider import TextSetting
from core.workflow import WorkflowController, WorkflowState
from rework.history import HistoryStore
from rework.model import Rework

OPTIONS_SEED = {
    "Custom": {
        "prefix": "Make this change to the following text:\n\n",
        "instruction": "Make the requested change.",
        "icon": "icons/summary",
        "open_in_window": False,
    },
    "Proofread": {
        "prefix": "Proofread this:\n\n",
        "instruction": "Correct the grammar and spelling.",
        "icon": "icons/magnifying-glass",
        "open_in_window": False,
    },
    "Rewrite": {
        "prefix": "Rewrite this:\n\n",
        "instruction": "Improve the phrasing.",
        "icon": "icons/rewrite",
        "open_in_window": False,
    },
    "Concise": {
        "prefix": "Make this more concise:\n\n",
        "instruction": "Shorten the text.",
        "icon": "icons/concise",
        "open_in_window": False,
    },
}


def isolate_app_files(directory) -> Path:
    """Point sys.argv[0] at a temp app directory and seed its data files."""
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    sys.argv[0] = str(target / "WritingToolApp.py")
    (target / "options.json").write_text(json.dumps(OPTIONS_SEED, indent=2), encoding="utf-8")
    presets = APP_DIR / "provider_presets.json"
    if presets.exists():
        shutil.copyfile(presets, target / "provider_presets.json")
    return target


def write_options(data: dict) -> None:
    target = Path(sys.argv[0]).parent / "options.json"
    target.write_text(json.dumps(data, indent=2), encoding="utf-8")


def read_options() -> dict:
    return json.loads((Path(sys.argv[0]).parent / "options.json").read_text(encoding="utf-8"))


class FakeProvider:
    """A provider with the real form surface, without any network call."""

    def __init__(self, app, name: str, settings, required=(), fail_test=False):
        self.app = app
        self.provider_name = name
        self.settings = settings
        self.required = tuple(required)
        self.fail_test = fail_test
        self.description = name
        self.loaded: dict = {}
        self.saved = 0
        self.tested = 0

    def _values(self) -> dict:
        values = {}
        for setting in self.settings:
            value = setting.get_value() if setting.input is not None else setting.get_value()
            values[setting.name] = value
        return values

    def load_config(self, values: dict) -> None:
        values = dict(values)
        for setting in self.settings:
            setting.set_value(values.get(setting.name, setting.default_value))
        missing = [name for name in self.required if not str(values.get(name, "")).strip()]
        if missing:
            raise ValueError(f"Enter {missing[0]} before saving.")
        self.loaded = values

    def save_config(self) -> None:
        self.app.config.setdefault("providers", {})[self.provider_name] = dict(self._values())
        self.saved += 1
        self.app.save_config(self.app.config)

    def test_connection(self) -> str:
        self.tested += 1
        if self.fail_test:
            raise RuntimeError("The provider rejected the key.")
        return "Connected. 3 models available."


def make_providers(host):
    return [
        FakeProvider(
            host,
            "Gemini (Recommended)",
            [
                TextSetting("api_key", "API Key", "", "Paste your Gemini API key", secret=True),
                TextSetting("model_name", "Model", "gemini-flash-latest", "Model id"),
            ],
            required=("api_key",),
        ),
        FakeProvider(
            host,
            "OpenAI Compatible (For Experts)",
            [
                TextSetting("api_key", "API Key", "", "API key", secret=True),
                TextSetting("api_base", "API Base URL", "https://api.openai.com/v1", "Base URL"),
                TextSetting("api_organisation", "API Organisation", "", "Optional"),
                TextSetting("api_project", "API Project", "", "Optional"),
                TextSetting("api_model", "API Model", "", "Model id"),
            ],
            required=("api_key", "api_model"),
        ),
        FakeProvider(
            host,
            "Ollama (For Experts)",
            [
                TextSetting("api_base", "API Base URL", "http://localhost:11434", "Base URL"),
                TextSetting("api_model", "API Model", "llama3.1:8b", "Model id"),
                TextSetting("keep_alive", "Keep Alive", "5", "Minutes"),
            ],
        ),
    ]


class FakeHost(QtCore.QObject):
    """The app contract the shell and views read, with no tray or hotkey side effect."""

    followup_response_signal = QtCore.Signal(str)
    show_message_signal = QtCore.Signal(str, str)
    output_ready_signal = QtCore.Signal(str)

    def __init__(self, directory, with_provider=True, entries=0):
        super().__init__()
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.config = {
            "shortcut": "ctrl+space",
            "history_enabled": True,
            "provider": "Gemini (Recommended)" if with_provider else "",
            "providers": {},
        }
        self.providers = make_providers(self)
        self.current_provider = self.providers[0] if with_provider else None
        self.history_enabled = True
        self.paused = False
        self.workflow = WorkflowController(self)
        self.history_store = HistoryStore(self.directory / "history.db")
        self.shell = None
        self.dashboard_window = None
        self.history_window = None
        self.settings_window = None
        self.about_window = None
        self.onboarding_window = None
        self.startup_error = None
        self.selected_text = "The cat sat on the mat today and looked outside."
        self.calls: list[str] = []
        self.saved_configs: list[dict] = []
        self.processed: list[tuple[str, str]] = []
        self.followups: list[str] = []
        self.receipt_entry_id = None
        self.undo_calls = 0
        self.rework_controller = self._build_rework_controller()
        if entries:
            self.seed_history(entries)

    def _build_rework_controller(self):
        from rework.controller import ReworkController
        from rework.review_card import ReworkCard

        def factory(rework, on_undo, on_close, saved):
            return ReworkCard(
                rework,
                on_undo,
                on_close,
                saved_to_history=saved,
                on_history=self.open_receipt_history,
            )

        return ReworkController(factory, undo=self._undo_rework, save=self._save_rework)

    def _save_rework(self, rework):
        if not self.history_enabled:
            return False
        self.receipt_entry_id = self.history_store.add(rework)
        return True

    def _undo_rework(self, rework):
        self.undo_calls += 1
        self.calls.append("undo_rework")

    def seed_history(self, count: int):
        samples = [
            (
                "Concise",
                "The cat sat on the mat today and looked outside.",
                "The cat rested on the mat and watched the garden.",
            ),
            (
                "Proofread",
                "their going to the store tomorow",
                "they are going to the store tomorrow",
            ),
            (
                "Rewrite",
                "We need to make a decision about the plan soon.",
                "We should decide on the plan soon.",
            ),
        ]
        ids = []
        for option, original, revised in samples[:count]:
            ids.append(self.history_store.add(Rework.create(option, original, revised)))
        return ids

    def process_option(self, option, custom_instruction=None):
        self.processed.append((option, custom_instruction or ""))
        self.calls.append(f"process_option:{option}")
        revised = "The cat rested on the mat and watched the garden."
        rework = Rework.create(option, self.selected_text, revised)
        self.workflow.begin(option, self.selected_text)
        run = self.workflow.last
        self.workflow.set_original(run.serial, self.selected_text)
        self.workflow.finish(run.serial, revised)
        self.rework_controller.present(option, self.selected_text, revised)
        return rework

    def process_followup_question(self, window, message):
        self.followups.append(message)
        self.calls.append("followup")

    def open_receipt_history(self):
        if self.shell is not None and self.receipt_entry_id is not None:
            self.shell.open_entry(self.receipt_entry_id)

    def save_config(self, config=None):
        if config is not None and config is not self.config:
            self.config.clear()
            self.config.update(copy.deepcopy(config))
        self.saved_configs.append(copy.deepcopy(self.config))
        self.calls.append("save_config")

    def validate_shortcut(self, value):
        text = (value or "").strip()
        if not text:
            return "Enter a shortcut, for example ctrl+space."
        try:
            from pynput import keyboard as pykeyboard

            pykeyboard.HotKey.parse(self._to_pynput_hotkey(text))
        except Exception:
            return f"'{text}' is not a valid shortcut."
        return None

    @staticmethod
    def _to_pynput_hotkey(value):
        return "+".join(
            f"{token}" if len(token) <= 1 else f"<{token}>"
            for token in value.split("+")
        )

    def register_hotkey(self):
        self.calls.append("register_hotkey")

    def create_tray_icon(self):
        self.calls.append("create_tray_icon")

    def set_history_enabled(self, enabled):
        self.history_enabled = bool(enabled)
        self.config["history_enabled"] = bool(enabled)
        self.calls.append(f"set_history_enabled:{bool(enabled)}")
        self.save_config(self.config)

    def actions_changed(self):
        self.calls.append("actions_changed")

    def history_changed(self):
        self.calls.append("history_changed")

    def toggle_paused(self):
        self.paused = not self.paused
        self.calls.append(f"paused:{self.paused}")

    def _cancel_active_request(self):
        self.workflow.cancel()
        self.calls.append("cancel_request")

    def exit_app(self):
        self.calls.append("exit_app")

    def load_options(self):
        from ui import ActionStore

        self.options = ActionStore.load()
        self.calls.append("load_options")

    def show_dashboard(self, view="home"):
        from ui.AppShell import AppShell

        if self.shell is None:
            self.shell = AppShell(self, self.history_store)
        self.shell.navigate(view)
        self.shell.show_window()
        return self.shell

    def show_history(self):
        return self.show_dashboard("rewrites")

    def show_settings(self, providers_only=False):
        shell = self.show_dashboard("settings")
        if providers_only:
            shell.settings.provider_form.setFocus()
        return shell

    def show_about(self):
        return self.show_dashboard("about")

    def show_onboarding(self):
        return self.show_dashboard("home")

    def count(self) -> int:
        return self.history_store.count()


def build_shell(host: FakeHost):
    from ui.AppShell import AppShell

    if host.shell is None:
        host.shell = AppShell(host, host.history_store)
    host.shell.show_window()
    from PySide6 import QtWidgets

    QtWidgets.QApplication.processEvents()
    return host.shell


def click(widget) -> None:
    from PySide6 import QtCore, QtTest, QtWidgets

    widget.setFocus()
    QtTest.QTest.mouseClick(widget, QtCore.Qt.MouseButton.LeftButton)
    QtWidgets.QApplication.processEvents()


def click_named(parent, name: str):
    from PySide6 import QtWidgets

    for button in parent.findChildren(QtWidgets.QPushButton):
        if button.accessibleName() == name or button.text() == name:
            click(button)
            return button
    raise AssertionError(f"No button named {name!r}")


def click_action(popup, name: str):
    for button in getattr(popup, "button_widgets", []):
        if getattr(button, "key", None) == name:
            click(button)
            return button
    raise AssertionError(f"No popup action named {name!r}")


def line_edit(parent, accessible_name: str):
    from PySide6 import QtWidgets

    for field in parent.findChildren(QtWidgets.QLineEdit):
        if field.accessibleName() == accessible_name:
            return field
    raise AssertionError(f"No line edit named {accessible_name!r}")


def combo_box(parent, accessible_name: str):
    from PySide6 import QtWidgets

    for field in parent.findChildren(QtWidgets.QComboBox):
        if field.accessibleName() == accessible_name:
            return field
    raise AssertionError(f"No combo box named {accessible_name!r}")


def flush_deletes() -> None:
    from PySide6 import QtCore, QtWidgets

    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    QtWidgets.QApplication.processEvents()


def wait_until(predicate, timeout: int = 5000) -> bool:
    from PySide6 import QtTest

    elapsed = 0
    while elapsed < timeout:
        if predicate():
            return True
        QtTest.QTest.qWait(25)
        elapsed += 25
    return predicate()


class TempAppFiles:
    """Context manager that isolates options.json and restores sys.argv[0]."""

    def __init__(self):
        self._temp = tempfile.TemporaryDirectory(prefix="writingtools-shell-")
        self._old_argv0 = None

    def __enter__(self) -> Path:
        self._old_argv0 = sys.argv[0]
        return isolate_app_files(self._temp.name)

    def __exit__(self, exc_type, exc, tb):
        if self._old_argv0 is not None:
            sys.argv[0] = self._old_argv0
        self._temp.cleanup()


class ShellTestCase(unittest.TestCase):
    """Base case with a QApplication, temp app files, and a fake host."""

    @classmethod
    def setUpClass(cls):
        from PySide6 import QtWidgets

        from ui.design import apply_app_style

        cls.qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        apply_app_style(cls.qapp)

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory(prefix="writingtools-test-")
        self.addCleanup(self._temp.cleanup)
        self._old_argv0 = sys.argv[0]
        isolate_app_files(self._temp.name)
        self.addCleanup(self._restore_argv0)
        self.host = FakeHost(self._temp.name)
        self.addCleanup(self._close_widgets)

    def _restore_argv0(self):
        sys.argv[0] = self._old_argv0

    def _close_widgets(self):
        from PySide6 import QtWidgets

        for widget in QtWidgets.QApplication.topLevelWidgets():
            if widget is not self.qapp:
                widget.close()
                widget.deleteLater()
        flush_deletes()

    def make_shell(self, host=None):
        self.shell = build_shell(host or self.host)
        self.addCleanup(self.shell.deleteLater)
        return self.shell

