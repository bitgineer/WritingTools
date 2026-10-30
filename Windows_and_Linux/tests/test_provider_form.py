import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shell_fixtures import (
    ShellTestCase,
    flush_deletes,
    line_edit,
    wait_until,
)

from PySide6 import QtCore, QtWidgets

from ui.ProviderForm import ProviderForm


class ProviderFormTests(ShellTestCase):
    def make_form(self, provider=None):
        if provider is not None:
            self.host.config["provider"] = provider
            self.host.current_provider = next(
                p for p in self.host.providers if p.provider_name == provider
            )
        form = ProviderForm(self.host)
        form.show()
        QtWidgets.QApplication.processEvents()
        self.addCleanup(form.deleteLater)
        self.addCleanup(form.close)
        return form

    def rendered_names(self, form):
        flush_deletes()
        fields = form.findChildren(QtWidgets.QLineEdit) + form.findChildren(QtWidgets.QComboBox)
        return {field.accessibleName() for field in fields}

    def test_switching_provider_rebuilds_the_fields(self):
        form = self.make_form()
        gemini = self.rendered_names(form)
        self.assertIn("API Key", gemini)
        self.assertIn("Model", gemini)

        form.provider_combo.setCurrentIndex(1)
        openai = self.rendered_names(form)
        self.assertIn("API Key", openai)
        self.assertIn("API Base URL", openai)
        self.assertIn("API Model", openai)
        self.assertNotIn("Model", openai)

        form.provider_combo.setCurrentIndex(2)
        ollama = self.rendered_names(form)
        self.assertNotIn("API Key", ollama)
        self.assertIn("API Base URL", ollama)
        self.assertIn("API Model", ollama)
        self.assertIn("Keep Alive", ollama)

        form.provider_combo.setCurrentIndex(0)
        self.assertIn("Model", self.rendered_names(form))

    def test_openai_preset_fills_the_base_and_model(self):
        form = self.make_form("OpenAI Compatible (For Experts)")
        preset = form.preset_combo
        index = preset.findData("openrouter")
        self.assertGreater(index, 0)
        preset.setCurrentIndex(index)
        QtWidgets.QApplication.processEvents()

        self.assertEqual(line_edit(form, "API Base URL").text(), "https://openrouter.ai/api/v1")
        self.assertEqual(line_edit(form, "API Model").text(), "moonshotai/kimi-k3.1-pro")
        self.assertIn("Get an API key", form.preset_note.text())

    def test_model_load_failure_is_inline(self):
        form = self.make_form("OpenAI Compatible (For Experts)")
        line_edit(form, "API Base URL").setText("https://openrouter.ai/api/v1")
        with mock.patch(
            "ui.ProviderForm.ModelCatalog.fetch_models",
            side_effect=RuntimeError("the model endpoint is down"),
        ):
            form._load_models()
            self.assertTrue(wait_until(lambda: not form._loading_models))

        self.assertEqual(form.model_status.text(), "the model endpoint is down")
        self.assertTrue(form.load_button.isEnabled())
        self.assertFalse(form.banner.isVisible())

    def test_model_load_success_fills_the_picker(self):
        form = self.make_form("OpenAI Compatible (For Experts)")
        line_edit(form, "API Base URL").setText("https://openrouter.ai/api/v1")
        with mock.patch(
            "ui.ProviderForm.ModelCatalog.fetch_models",
            return_value=["model-one", "model-two"],
        ):
            form._load_models()
            self.assertTrue(wait_until(lambda: not form._loading_models))

        self.assertTrue(form.model_combo.isEnabled())
        self.assertEqual(form.model_combo.count(), 2)
        self.assertIn("2 models", form.model_status.text())
        form.model_combo.setCurrentIndex(1)
        self.assertEqual(line_edit(form, "API Model").text(), "model-two")

    def test_save_validates_before_writing(self):
        form = self.make_form("OpenAI Compatible (For Experts)")
        line_edit(form, "API Key").setText("")
        line_edit(form, "API Model").setText("")
        before = len(self.host.saved_configs)

        self.assertFalse(form.save())
        self.assertTrue(form.banner.isVisible())
        self.assertEqual(form.banner.title_label.text(), "Provider not ready")
        self.assertIn("API key", form.banner.body_label.text())
        self.assertEqual(len(self.host.saved_configs), before)
        self.assertIs(self.host.current_provider, self.host.providers[1])

    def test_save_writes_the_provider_after_validation(self):
        form = self.make_form("OpenAI Compatible (For Experts)")
        line_edit(form, "API Key").setText("sk-test")
        line_edit(form, "API Model").setText("moonshotai/kimi-k3.1-pro")

        self.assertTrue(form.save())
        self.assertEqual(self.host.config["provider"], "OpenAI Compatible (For Experts)")
        self.assertIn("OpenAI Compatible (For Experts)", self.host.config["providers"])
        self.assertEqual(
            self.host.config["providers"]["OpenAI Compatible (For Experts)"]["api_model"],
            "moonshotai/kimi-k3.1-pro",
        )
        self.assertIs(self.host.current_provider, self.host.providers[1])
        self.assertFalse(form.banner.isVisible())

    def test_switching_away_and_back_keeps_the_draft(self):
        form = self.make_form()
        form.provider_combo.setCurrentIndex(1)
        flush_deletes()
        line_edit(form, "API Base URL").setText("https://example.test/v1")
        form.provider_combo.setCurrentIndex(0)
        flush_deletes()
        form.provider_combo.setCurrentIndex(1)
        flush_deletes()
        self.assertEqual(line_edit(form, "API Base URL").text(), "https://example.test/v1")


if __name__ == "__main__":
    unittest.main()
