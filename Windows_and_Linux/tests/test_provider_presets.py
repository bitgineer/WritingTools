import os
import sys
import unittest

from PySide6 import QtWidgets

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiprovider import GeminiProvider, OllamaProvider, OpenAICompatibleProvider
from ui import ProviderPresets
from ui.SettingsWindow import SettingsWindow

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Shell:
    def __init__(self):
        self.config = {
            "provider": "OpenAI Compatible (For Experts)",
            "providers": {},
        }
        self.providers = [
            GeminiProvider(self),
            OpenAICompatibleProvider(self),
            OllamaProvider(self),
        ]
        self.current_provider = self.providers[1]
        self.dashboard_window = None
        self.saved = []

    def save_config(self, config):
        self.saved.append(config)

    def register_hotkey(self):
        pass

    def create_tray_icon(self):
        pass

    def show_dashboard(self):
        pass

    def validate_shortcut(self, value):
        return None

    @staticmethod
    def _to_pynput_hotkey(value):
        return value


class ProviderPresetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        self._argv = sys.argv[0]
        sys.argv[0] = os.path.join(APP, "main.py")
        self.addCleanup(self._restore_argv)

    def _restore_argv(self):
        sys.argv[0] = self._argv

    def test_catalog_is_valid_and_has_coverage(self):
        presets = ProviderPresets.load()
        self.assertGreaterEqual(len(presets), 10)
        self.assertEqual(ProviderPresets.validate(presets), [])
        self.assertEqual(len({preset.id for preset in presets}), len(presets))
        for preset in presets:
            self.assertTrue(preset.base_url.startswith("https://"), preset.id)
            self.assertTrue(preset.key_url.startswith("https://"), preset.id)
            self.assertTrue(preset.model, preset.id)

    def test_selecting_a_preset_fills_the_endpoint_and_model(self):
        window = SettingsWindow(Shell())
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)

        combo = next(
            item
            for item in window.findChildren(QtWidgets.QComboBox)
            if item.accessibleName() == "Service preset"
        )
        combo.setCurrentIndex(combo.findData("openrouter"))
        QtWidgets.QApplication.processEvents()

        fields = {
            field.accessibleName(): field
            for field in window.findChildren(QtWidgets.QLineEdit)
        }
        self.assertEqual(fields["API Base URL"].text(), "https://openrouter.ai/api/v1")
        self.assertEqual(fields["API Model"].text(), "moonshotai/kimi-k3.1-pro")
        self.assertIn("openrouter.ai/settings/keys", window.preset_note.text())

    def test_saving_a_preset_writes_the_endpoint_model_and_preset_id(self):
        shell = Shell()
        window = SettingsWindow(shell)
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)

        combo = next(
            item
            for item in window.findChildren(QtWidgets.QComboBox)
            if item.accessibleName() == "Service preset"
        )
        combo.setCurrentIndex(combo.findData("groq"))
        QtWidgets.QApplication.processEvents()

        fields = {
            field.accessibleName(): field
            for field in window.findChildren(QtWidgets.QLineEdit)
        }
        fields["API Key"].setText("test-key")

        window.save_settings()
        QtWidgets.QApplication.processEvents()

        provider_config = shell.config["providers"]["OpenAI Compatible (For Experts)"]
        self.assertEqual(shell.config["provider_preset"], "groq")
        self.assertEqual(provider_config["api_base"], "https://api.groq.com/openai/v1")
        self.assertEqual(provider_config["api_model"], "qwen/qwen3.8-27b")

    def test_choose_a_service_clears_the_preset(self):
        window = SettingsWindow(Shell())
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)

        combo = next(
            item
            for item in window.findChildren(QtWidgets.QComboBox)
            if item.accessibleName() == "Service preset"
        )
        combo.setCurrentIndex(combo.findData("deepseek"))
        QtWidgets.QApplication.processEvents()
        combo.setCurrentIndex(0)
        QtWidgets.QApplication.processEvents()
        self.assertEqual(window._active_preset, "")
        self.assertEqual(window.preset_note.text(), "")


if __name__ == "__main__":
    unittest.main()
