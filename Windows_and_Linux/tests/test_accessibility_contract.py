import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shell_fixtures import ShellTestCase, build_shell

from PySide6 import QtCore, QtGui, QtTest, QtWidgets

from ui.ActionsView import ActionRow
from ui.RewritesView import RewritesView
from rework.theme import current_palette


class AccessibilityContractTests(ShellTestCase):
    def test_action_rows_are_buttons_to_assistive_tech(self):
        host = self.host
        shell = build_shell(host)
        row = shell.actions.findChildren(ActionRow)[0]
        interface = QtGui.QAccessible.queryAccessibleInterface(row)
        self.assertIsNotNone(interface)
        self.assertEqual(interface.role(), QtGui.QAccessible.Role.Button)
        self.assertIn("Press", interface.actionNames())

    def test_palette_traps_tab_and_closes_on_escape(self):
        shell = build_shell(self.host)
        shell.open_palette()
        QtWidgets.QApplication.processEvents()
        self.assertTrue(shell.command_palette.isVisible())
        QtTest.QTest.keyClick(shell.command_palette.input, QtCore.Qt.Key.Key_Tab)
        QtWidgets.QApplication.processEvents()
        self.assertIs(QtWidgets.QApplication.focusWidget(), shell.command_palette.input)
        QtTest.QTest.keyClick(shell.command_palette.input, QtCore.Qt.Key.Key_Escape)
        QtWidgets.QApplication.processEvents()
        self.assertFalse(shell.command_palette.isVisible())

    def test_palette_fits_the_last_command(self):
        shell = build_shell(self.host)
        shell.open_palette()
        QtWidgets.QApplication.processEvents()
        last = shell.command_palette.list.item(shell.command_palette.list.count() - 1)
        rect = shell.command_palette.list.visualItemRect(last)
        self.assertLessEqual(rect.bottom(), shell.command_palette.list.viewport().height())

    def test_placeholder_text_uses_the_muted_role(self):
        from ui.design import app_stylesheet

        color = self.qapp.palette().color(QtGui.QPalette.ColorRole.PlaceholderText)
        self.assertEqual(color.name(), current_palette().muted.lower())
        self.assertIn(
            f"placeholder-text-color: {current_palette().muted}",
            app_stylesheet(current_palette()),
        )

    def test_history_error_offers_a_retry(self):
        self.host.history_store = None
        view = RewritesView(self.host, store=None)
        view.show()
        buttons = [
            button
            for button in view.findChildren(QtWidgets.QPushButton)
            if button.text() == "Try again"
        ]
        self.assertEqual(len(buttons), 1)
        self.assertTrue(buttons[0].isVisible())


if __name__ == "__main__":
    unittest.main()
