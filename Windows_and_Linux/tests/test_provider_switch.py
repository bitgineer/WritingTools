import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6 import QtCore, QtWidgets
from PySide6.QtWidgets import QComboBox, QLineEdit

from aiprovider import GeminiProvider, OllamaProvider, OpenAICompatibleProvider
from ui.SettingsWindow import SettingsWindow


class FakeApp:
    def __init__(self):
        self.config = {"provider": "Gemini (Recommended)"}
        self.saved_configs = []
        self.hotkeys_registered = 0
        self.tray_icons_created = 0
        self.providers = [
            GeminiProvider(self),
            OpenAICompatibleProvider(self),
            OllamaProvider(self),
        ]
        self.current_provider = self.providers[0]

    def save_config(self, config):
        self.saved_configs.append(config)

    def create_tray_icon(self):
        self.tray_icons_created += 1

    def show_dashboard(self):
        pass

    def register_hotkey(self):
        self.hotkeys_registered += 1


class ProviderSwitchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def make_window(self):
        app = FakeApp()
        window = SettingsWindow(app, providers_only=True)
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)
        return window, app

    def rendered_field_names(self, window):
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
        fields = window.findChildren(QLineEdit) + window.findChildren(QComboBox)
        return {field.accessibleName() for field in fields}

    def test_switching_to_each_provider_renders_its_own_fields(self):
        window, app = self.make_window()
        for index, provider in enumerate(app.providers):
            with self.subTest(provider=provider.provider_name):
                window.provider_dropdown.setCurrentIndex(index)
                names = self.rendered_field_names(window)
                for setting in provider.settings:
                    self.assertIn(setting.display_name, names)

    def test_switching_away_from_gemini_removes_gemini_fields(self):
        window, app = self.make_window()
        window.provider_dropdown.setCurrentIndex(1)
        names = self.rendered_field_names(window)
        self.assertNotIn("Model", names)
        self.assertIn("API Base URL", names)

    def test_save_completes_for_each_provider_after_switching(self):
        for index in range(3):
            window, app = self.make_window()
            provider = app.providers[index]
            with self.subTest(provider=provider.provider_name):
                window.provider_dropdown.setCurrentIndex(index)
                for field in window.findChildren(QLineEdit):
                    if field.accessibleName() == "API Key":
                        field.setText("test-key")
                window.save_settings()
                self.assertEqual(app.config["provider"], provider.provider_name)
                self.assertIn(provider.provider_name, app.config["providers"])
                self.assertIs(app.current_provider, provider)


if __name__ == "__main__":
    unittest.main()
