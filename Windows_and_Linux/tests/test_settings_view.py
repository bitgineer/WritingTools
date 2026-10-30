import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shell_fixtures import ShellTestCase, line_edit

from PySide6 import QtWidgets

from ui.SettingsView import SettingsView


class SettingsViewTests(ShellTestCase):
    def make_view(self):
        view = SettingsView(self.host)
        view.show()
        QtWidgets.QApplication.processEvents()
        self.addCleanup(view.deleteLater)
        self.addCleanup(view.close)
        return view

    def test_shortcut_autosaves_on_enter(self):
        view = self.make_view()
        view.shortcut.setText("ctrl+alt+j")
        view.shortcut.returnPressed.emit()
        QtWidgets.QApplication.processEvents()

        self.assertEqual(self.host.config["shortcut"], "ctrl+alt+j")
        self.assertEqual(self.host.saved_configs[-1]["shortcut"], "ctrl+alt+j")
        self.assertIn("register_hotkey", self.host.calls)
        self.assertTrue(view.shortcut_error.isHidden())

    def test_shortcut_autosaves_on_editing_finished(self):
        view = self.make_view()
        view.shortcut.setText("ctrl+alt+p")
        view.shortcut.editingFinished.emit()
        QtWidgets.QApplication.processEvents()

        self.assertEqual(self.host.config["shortcut"], "ctrl+alt+p")
        self.assertEqual(self.host.saved_configs[-1]["shortcut"], "ctrl+alt+p")

    def test_invalid_shortcut_shows_an_inline_error_and_does_not_save(self):
        view = self.make_view()
        before = len(self.host.saved_configs)
        view.shortcut.setText("ctrl+notakey")
        view.shortcut.returnPressed.emit()
        QtWidgets.QApplication.processEvents()

        self.assertFalse(view.shortcut_error.isHidden())
        self.assertIn("not a valid shortcut", view.shortcut_error.text())
        self.assertEqual(self.host.config["shortcut"], "ctrl+space")
        self.assertEqual(len(self.host.saved_configs), before)
        self.assertNotIn("register_hotkey", self.host.calls)

        view.shortcut.setText("ctrl+alt+j")
        view.shortcut.returnPressed.emit()
        QtWidgets.QApplication.processEvents()
        self.assertTrue(view.shortcut_error.isHidden())
        self.assertEqual(self.host.config["shortcut"], "ctrl+alt+j")

    def test_history_toggle_updates_the_note_and_the_app(self):
        view = self.make_view()
        view.history_toggle.setChecked(False)
        QtWidgets.QApplication.processEvents()

        self.assertFalse(self.host.history_enabled)
        self.assertFalse(self.host.config["history_enabled"])
        self.assertIn("History is off", view.history_note.text())

        view.history_toggle.setChecked(True)
        QtWidgets.QApplication.processEvents()
        self.assertTrue(self.host.history_enabled)
        self.assertIn("saved on this device", view.history_note.text())

    def test_autostart_failure_reverts_the_checkbox_and_explains(self):
        with (
            mock.patch(
                "ui.SettingsView.AutostartManager.get_startup_path",
                return_value="C:/fake/WritingTools.exe",
            ),
            mock.patch("ui.SettingsView.AutostartManager.check_autostart", return_value=False),
            mock.patch("ui.SettingsView.AutostartManager.set_autostart", return_value=False) as setter,
            mock.patch("ui.SettingsView.QtWidgets.QMessageBox.warning") as warning,
        ):
            view = self.make_view()
            self.assertFalse(view.autostart.isHidden())
            self.assertFalse(view.autostart.isChecked())

            view.autostart.setChecked(True)
            QtWidgets.QApplication.processEvents()

            setter.assert_called_once_with(True)
            warning.assert_called_once()
            self.assertEqual(warning.call_args.args[1], "Start on Boot")
            self.assertFalse(view.autostart.isChecked())

    def test_autostart_success_keeps_the_checkbox_on(self):
        with (
            mock.patch(
                "ui.SettingsView.AutostartManager.get_startup_path",
                return_value="C:/fake/WritingTools.exe",
            ),
            mock.patch("ui.SettingsView.AutostartManager.check_autostart", return_value=False),
            mock.patch("ui.SettingsView.AutostartManager.set_autostart", return_value=True) as setter,
            mock.patch("ui.SettingsView.QtWidgets.QMessageBox.warning") as warning,
        ):
            view = self.make_view()
            view.autostart.setChecked(True)
            QtWidgets.QApplication.processEvents()

            setter.assert_called_once_with(True)
            warning.assert_not_called()
            self.assertTrue(view.autostart.isChecked())

    def test_provider_save_uses_the_fake_provider_and_emits_changed(self):
        view = self.make_view()
        changed = []
        view.changed.connect(lambda: changed.append(True))
        form = view.provider_form
        line_edit(form, "API Key").setText("test-key")

        saved = form.save()
        QtWidgets.QApplication.processEvents()

        self.assertTrue(saved)
        self.assertEqual(self.host.config["provider"], "Gemini (Recommended)")
        self.assertIn("Gemini (Recommended)", self.host.config["providers"])
        self.assertIs(self.host.current_provider, self.host.providers[0])
        self.assertIn("create_tray_icon", self.host.calls)
        self.assertIn("register_hotkey", self.host.calls)
        self.assertEqual(changed, [True])
        self.assertIn("Saved", view.provider_form.status.text())


if __name__ == "__main__":
    unittest.main()
