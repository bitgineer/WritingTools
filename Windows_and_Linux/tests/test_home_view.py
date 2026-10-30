import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shell_fixtures import ShellTestCase, click_named, line_edit

from PySide6 import QtWidgets

from ui.HomeView import HomeView
from ui.ProviderForm import ProviderForm
from ui.SetupWizard import SetupWizard


class HomeViewTests(ShellTestCase):
    def make_home(self, with_provider=False):
        self.host.current_provider = self.host.providers[0] if with_provider else None
        self.host.config["provider"] = self.host.current_provider.provider_name if with_provider else ""
        view = HomeView(self.host)
        view.show()
        QtWidgets.QApplication.processEvents()
        self.addCleanup(view.deleteLater)
        self.addCleanup(view.close)
        return view

    def test_first_run_shows_the_setup_wizard(self):
        view = self.make_home(with_provider=False)
        wizard = view._wizard
        self.assertIsInstance(wizard, SetupWizard)
        self.assertFalse(view.setup_host.isHidden())
        self.assertTrue(view.main_host.isHidden())
        self.assertEqual(wizard.step_label.text(), "Step 1 of 2")
        self.assertEqual(wizard.shortcut_input.text(), "ctrl+space")
        self.assertEqual(wizard.title.text(), "A writing desk in every app")

    def test_step_one_rejects_an_invalid_shortcut_and_saves_a_valid_one(self):
        view = self.make_home(with_provider=False)
        wizard = view._wizard
        wizard.shortcut_input.setText("ctrl+notakey")
        click_named(view, "Continue")
        QtWidgets.QApplication.processEvents()

        self.assertEqual(wizard.step_label.text(), "Step 1 of 2")
        self.assertFalse(wizard.error.isHidden())
        self.assertIn("Shortcut not valid", wizard.error.title_label.text())
        self.assertIn("not a valid shortcut", wizard.error.body_label.text())
        self.assertEqual(self.host.config["shortcut"], "ctrl+space")
        self.assertEqual(self.host.saved_configs, [])

        wizard.shortcut_input.setText("ctrl+alt+j")
        click_named(view, "Continue")
        QtWidgets.QApplication.processEvents()

        self.assertEqual(self.host.config["shortcut"], "ctrl+alt+j")
        self.assertTrue(self.host.saved_configs)
        self.assertEqual(wizard.step_label.text(), "Step 2 of 2")
        self.assertIsInstance(wizard._provider_form, ProviderForm)
        self.assertTrue(wizard._provider_form.isVisibleTo(wizard))
        self.assertEqual(wizard._provider_form.provider_name(), "Gemini (Recommended)")

    def test_step_two_finishes_setup_and_the_ready_screen_emits_finished(self):
        view = self.make_home(with_provider=False)
        wizard = view._wizard
        wizard.shortcut_input.setText("ctrl+alt+j")
        click_named(view, "Continue")
        QtWidgets.QApplication.processEvents()

        form = wizard._provider_form
        line_edit(form, "API Key").setText("test-key")

        ready = []
        finished = []
        wizard.ready.connect(lambda: ready.append(True))
        view.setup_finished.connect(lambda: finished.append(True))

        click_named(wizard, "Finish setup")
        QtWidgets.QApplication.processEvents()

        self.assertEqual(ready, [True])
        self.assertEqual(wizard.step_label.text(), "Ready")
        self.assertEqual(wizard.title.text(), "You are set up")
        self.assertIn("ctrl+alt+j", wizard.body.text())
        self.assertIsNotNone(self.host.current_provider)
        self.assertEqual(self.host.config["provider"], "Gemini (Recommended)")
        self.assertIn("Gemini (Recommended)", self.host.config["providers"])
        self.assertIn("create_tray_icon", self.host.calls)
        self.assertIn("register_hotkey", self.host.calls)

        click_named(wizard, "Open Home")
        QtWidgets.QApplication.processEvents()

        self.assertEqual(finished, [True])
        self.assertIsNone(view._wizard)
        self.assertTrue(view.setup_host.isHidden())
        self.assertFalse(view.main_host.isHidden())

    def test_home_lists_recent_rewrites_and_opens_one(self):
        self.host.seed_history(2)
        view = self.make_home(with_provider=True)
        self.assertEqual(view.recent_layout.count(), 2)
        self.assertIn("2 saved rewrites", view.recent_footer.text())

        opened = []
        view.open_entry.connect(opened.append)
        from ui.HomeView import RecentRow

        row = view.findChildren(RecentRow)[0]
        row.click()
        QtWidgets.QApplication.processEvents()
        self.assertEqual(opened, [row.entry.id])

    def test_history_off_is_named_on_home(self):
        self.host.history_enabled = False
        view = self.make_home(with_provider=True)
        self.assertEqual(view.metrics["History"].value.text(), "Off")
        self.assertIn("History is off", view.recent_footer.text())


if __name__ == "__main__":
    unittest.main()
