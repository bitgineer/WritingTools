import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6 import QtWidgets
from PySide6.QtWidgets import QCheckBox, QComboBox, QLabel, QLineEdit, QPushButton, QRadioButton

from aiprovider import DropdownSetting, TextSetting
from ui.SettingsWindow import SettingsWindow


class FakeProvider:
    def __init__(self, name, settings=None):
        self.provider_name = name
        self.settings = settings or []
        self.logo = None
        self.description = "Test provider description."
        self.button_text = ""
        self.button_action = None
        self.saved = False
        self.loaded_config = None

    def save_config(self):
        self.saved = True

    def load_config(self, config):
        self.loaded_config = config


def _fake_app(config):
    app = mock.MagicMock()
    app.config = config
    app.providers = [
        FakeProvider(
            "Gemini (Recommended)",
            [
                TextSetting(name="api_key", display_name="API Key", description="Paste your key"),
                DropdownSetting(
                    name="model_name",
                    display_name="Model",
                    default_value="model-a",
                    options=[("Model A", "model-a"), ("Model B", "model-b")],
                    allow_custom=True,
                ),
            ],
        ),
        FakeProvider("OpenAI Compatible (For Experts)"),
    ]
    from WritingToolApp import WritingToolApp

    app._to_pynput_hotkey = WritingToolApp._to_pynput_hotkey
    app.validate_shortcut = lambda shortcut: WritingToolApp.validate_shortcut(app, shortcut)
    return app


class SettingsDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def make_window(self, config=None, providers_only=False):
        app = _fake_app(config if config is not None else {"provider": "Gemini (Recommended)"})
        window = SettingsWindow(app, providers_only=providers_only)
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)
        return window

    def test_width_is_in_range_and_height_fits_the_screen(self):
        window = self.make_window()
        self.assertGreaterEqual(window.width(), 640)
        self.assertLessEqual(window.width(), 720)
        screen_height = QtWidgets.QApplication.primaryScreen().geometry().height()
        self.assertLessEqual(window.height(), int(screen_height * 0.85))

    def test_no_theme_radio_buttons_remain(self):
        window = self.make_window()
        self.assertEqual(window.findChildren(QRadioButton), [])

    def test_provider_and_general_fields_carry_no_inline_style(self):
        window = self.make_window()
        fields = window.findChildren(QLineEdit) + window.findChildren(QComboBox)
        self.assertTrue(fields)
        for field in fields:
            self.assertEqual(field.styleSheet(), "", field.accessibleName())

    def test_save_does_not_write_a_theme_key(self):
        config = {"provider": "Gemini (Recommended)", "shortcut": "ctrl+space"}
        window = self.make_window(config)
        window.shortcut_input.setText("ctrl+j")
        window.save_settings()
        self.assertNotIn("theme", config)
        self.assertEqual(config["shortcut"], "ctrl+j")
        self.assertTrue(window.app.providers[0].saved)

    def test_invalid_shortcut_is_rejected_before_anything_is_saved(self):
        config = {"provider": "Gemini (Recommended)", "shortcut": "ctrl+space"}
        window = self.make_window(config)
        window.shortcut_input.setText("ctrl+space+junk")
        with mock.patch.object(QtWidgets.QMessageBox, "warning") as warning:
            window.save_settings()
        self.assertTrue(warning.called)
        self.assertEqual(window.app.config["shortcut"], "ctrl+space")

    def test_providers_only_mode_shows_only_the_provider_section(self):
        window = self.make_window(providers_only=True)
        self.assertIsNone(window.shortcut_input)
        self.assertEqual(window.findChildren(QCheckBox), [])
        restart_texts = [label.text() for label in window.findChildren(QLabel) if "Restart" in label.text()]
        self.assertEqual(restart_texts, [])
        save_texts = [button.text() for button in window.findChildren(QPushButton)]
        self.assertIn("Finish AI Setup", save_texts)

    def test_actions_card_lists_the_popup_actions(self):
        window = self.make_window()
        rows = window.findChildren(QtWidgets.QFrame, "ActionRow")
        self.assertGreaterEqual(len(rows), 8)
        texts = [label.text() for label in window.findChildren(QtWidgets.QLabel)]
        self.assertIn("Proofread", texts)
        buttons = [button.text() for button in window.findChildren(QPushButton)]
        self.assertIn("Add action", buttons)
        self.assertIn("Reset actions", buttons)
        self.assertIn("Edit", buttons)

    def test_full_mode_shows_live_apply_notice_and_named_fields(self):
        window = self.make_window()
        restart_texts = [label.text() for label in window.findChildren(QLabel) if "Restart" in label.text()]
        self.assertEqual(restart_texts, [])
        apply_texts = [
            label.text()
            for label in window.findChildren(QLabel)
            if "Provider and shortcut apply when you save" in label.text()
        ]
        self.assertEqual(len(apply_texts), 1)
        self.assertEqual(window.shortcut_input.accessibleName(), "Shortcut Key")
        self.assertEqual(window.provider_dropdown.accessibleName(), "AI Provider")


if __name__ == "__main__":
    unittest.main()
