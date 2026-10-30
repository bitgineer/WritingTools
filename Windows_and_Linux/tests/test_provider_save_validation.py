import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6 import QtWidgets

from aiprovider import GeminiProvider, deobfuscate_api_key
from ui.SettingsWindow import SettingsWindow


class FakeApp:
    def __init__(self):
        self.config = {"provider": "Gemini (Recommended)"}
        self.saved_configs = []
        self.hotkeys_registered = 0
        self.providers = [GeminiProvider(self)]
        self.current_provider = self.providers[0]

    def save_config(self, config):
        self.saved_configs.append(config)

    def create_tray_icon(self):
        pass

    def show_dashboard(self):
        pass

    def register_hotkey(self):
        self.hotkeys_registered += 1


class ProviderSaveValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def make_window(self):
        app = FakeApp()
        window = SettingsWindow(app, providers_only=True)
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)
        return window, app

    def test_finish_setup_with_empty_gemini_key_shows_message_and_stays_open(self):
        window, app = self.make_window()
        self.assertEqual(window.provider_dropdown.currentText(), "Gemini (Recommended)")

        with mock.patch("ui.SettingsWindow.QtWidgets.QMessageBox.warning") as warning:
            window.save_settings()

        warning.assert_called_once()
        self.assertTrue(window.providers_only, "window must stay in setup mode after a failed save")
        self.assertEqual(app.hotkeys_registered, 0)
        self.assertEqual(app.saved_configs, [], "an invalid provider must not be written to config")
        self.assertIs(app.current_provider, app.providers[0])

    def test_finish_setup_with_valid_gemini_key_writes_config_and_activates(self):
        window, app = self.make_window()
        for field in window.findChildren(QtWidgets.QLineEdit):
            if field.accessibleName() == "API Key":
                field.setText("test-key")

        with mock.patch("ui.SettingsWindow.QtWidgets.QMessageBox.warning") as warning:
            window.save_settings()

        warning.assert_not_called()
        self.assertEqual(len(app.saved_configs), 1)
        stored_key = app.saved_configs[0]["providers"]["Gemini (Recommended)"]["api_key"]
        self.assertEqual(deobfuscate_api_key(stored_key), "test-key")
        self.assertIs(app.current_provider, app.providers[0])
        self.assertEqual(app.hotkeys_registered, 1)
        self.assertFalse(window.providers_only)


if __name__ == "__main__":
    unittest.main()
