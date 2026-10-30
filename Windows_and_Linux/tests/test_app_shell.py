import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shell_fixtures import ShellTestCase, click, flush_deletes

from PySide6 import QtCore, QtGui, QtTest, QtWidgets

from ui.AppShell import VIEW_TITLES


class AppShellTests(ShellTestCase):
    def setUp(self):
        super().setUp()
        self.host.seed_history(2)

    def test_ctrl_1_to_5_switches_views(self):
        shell = self.make_shell()
        shell.show()
        shell.activateWindow()
        QtTest.QTest.qWait(50)
        for index, key in enumerate(("home", "rewrites", "actions", "settings", "about"), start=1):
            shell.navigate("home")
            shell.activateWindow()
            QtTest.QTest.qWait(20)
            QtTest.QTest.keySequence(shell, QtGui.QKeySequence(f"Ctrl+{index}"))
            QtWidgets.QApplication.processEvents()
            self.assertEqual(shell._current, key, f"Ctrl+{index} must open {key}")
            self.assertIs(shell.stack.currentWidget(), shell._views[key])
            self.assertEqual(shell.title_label.text(), VIEW_TITLES[key][0])
            self.assertEqual(shell.nav.currentRow(), index - 1)

    def test_palette_filters_and_enter_runs_the_command(self):
        shell = self.make_shell()
        shell.open_palette()
        palette = shell.command_palette
        self.assertTrue(palette.isVisible())
        self.assertGreater(palette.list.count(), 5)

        palette.input.setText("sett")
        QtWidgets.QApplication.processEvents()
        labels = [palette.list.item(i).text() for i in range(palette.list.count())]
        self.assertIn("Go to Settings", labels)
        self.assertIn("Open provider settings", labels)
        self.assertEqual(palette.list.currentItem().text(), "Go to Settings")

        QtTest.QTest.keyClick(palette.input, QtCore.Qt.Key.Key_Return)
        QtWidgets.QApplication.processEvents()
        self.assertFalse(palette.isVisible())
        self.assertEqual(shell._current, "settings")

    def test_palette_reports_no_match(self):
        shell = self.make_shell()
        shell.open_palette()
        shell.command_palette.input.setText("zzzz-no-command")
        QtWidgets.QApplication.processEvents()
        self.assertEqual(shell.command_palette.list.count(), 1)
        self.assertEqual(shell.command_palette.list.item(0).text(), "No matching command")
        self.assertFalse(shell.command_palette.list.isEnabled())

    def test_banner_shows_and_clears(self):
        shell = self.make_shell()
        shell.show_banner(
            "Provider not ready",
            "The saved key was rejected.",
            "Open provider settings",
            lambda: shell.navigate("settings"),
        )
        QtWidgets.QApplication.processEvents()
        self.assertFalse(shell.banner_host.isHidden())
        banner = shell.banner_layout.itemAt(0).widget()
        self.assertEqual(banner.title_label.text(), "Provider not ready")
        self.assertIn("rejected", banner.body_label.text())

        shell.clear_banner()
        QtWidgets.QApplication.processEvents()
        self.assertTrue(shell.banner_host.isHidden())
        self.assertEqual(shell.banner_layout.count(), 0)

    def test_status_chip_names_setup_and_opens_settings(self):
        self.host.current_provider = None
        shell = self.make_shell()
        shell.refresh_chrome()
        self.assertEqual(shell.status_chip.text(), "Setup needed")
        self.assertIn("Open provider settings", shell.status_chip.accessibleName())

        click(shell.status_chip)
        self.assertEqual(shell._current, "settings")

    def test_status_chip_toggles_pause(self):
        shell = self.make_shell()
        shell.refresh_chrome()
        self.assertEqual(shell.status_chip.text(), "Running")

        click(shell.status_chip)
        self.assertTrue(self.host.paused)
        self.assertEqual(shell.status_chip.text(), "Paused")
        self.assertEqual(shell.status_chip.accessibleName(), "Resume Writing Tools")

        click(shell.status_chip)
        self.assertFalse(self.host.paused)
        self.assertEqual(shell.status_chip.text(), "Running")

    def test_open_entry_selects_the_exact_rewrite(self):
        entries = self.host.history_store.entries()
        target = entries[0]
        shell = self.make_shell()
        shell.open_entry(target.id)
        QtWidgets.QApplication.processEvents()

        self.assertEqual(shell._current, "rewrites")
        self.assertEqual(shell.rewrites._selected_id, target.id)
        current = shell.rewrites.list.currentItem()
        self.assertIsNotNone(current)
        self.assertEqual(current.data(QtCore.Qt.ItemDataRole.UserRole), target.id)
        self.assertTrue(shell.rewrites.meta.text().startswith(target.option))

    def test_close_hides_instead_of_quitting(self):
        shell = self.make_shell()
        self.assertTrue(shell.isVisible())
        closed = shell.close()
        QtWidgets.QApplication.processEvents()
        self.assertFalse(closed)
        self.assertFalse(shell.isVisible())
        self.assertEqual(self.host.calls.count("exit_app"), 0)
        self.assertIsNotNone(QtWidgets.QApplication.instance())

    def test_nav_count_reads_the_store(self):
        shell = self.make_shell()
        shell.refresh_chrome()
        self.assertEqual(shell.nav.item(1).text(), "Rewrites   2")

    def test_ctrl_f_focuses_rewrite_search(self):
        shell = self.make_shell()
        sequences = [shortcut.key().toString() for shortcut in shell._shortcuts]
        self.assertIn("Ctrl+F", sequences)
        shell.navigate("home")
        shell._focus_search()
        self.assertEqual(shell._current, "rewrites")
        self.assertIs(shell.focusWidget(), shell.rewrites.search)


if __name__ == "__main__":
    unittest.main()
