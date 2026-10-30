import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shell_fixtures import ShellTestCase, click

from PySide6 import QtCore, QtTest, QtWidgets

from ui.RewritesView import RewritesView


class RewritesViewTests(ShellTestCase):
    def make_view(self, entries=2):
        if entries:
            self.host.seed_history(entries)
        view = RewritesView(self.host, self.host.history_store)
        view.show()
        QtWidgets.QApplication.processEvents()
        self.addCleanup(view.deleteLater)
        self.addCleanup(view.close)
        return view

    def test_empty_history_shows_the_next_step(self):
        view = self.make_view(entries=0)
        self.assertFalse(view.empty.isHidden())
        self.assertEqual(view.empty.title_label.text(), "No rewrites yet")
        self.assertIn("press your shortcut", view.empty.body_label.text())
        self.assertTrue(view.splitter.isHidden())
        self.assertFalse(view.copy_revised.isEnabled())
        self.assertEqual(view.count.text(), "0 rewrites")

    def test_no_match_search_is_named(self):
        view = self.make_view()
        view.search.setText("zzz-no-match")
        QtWidgets.QApplication.processEvents()
        self.assertEqual(view.list.count(), 0)
        self.assertEqual(view.count.text(), "0 of 2 rewrites")
        self.assertEqual(view.empty.title_label.text(), "No matches")
        self.assertIn("different search", view.empty.body_label.text())

    def test_search_filters_by_original_and_revision(self):
        view = self.make_view()
        view.search.setText("tomorow")
        QtWidgets.QApplication.processEvents()
        self.assertEqual(view.list.count(), 1)
        self.assertEqual(view.count.text(), "1 of 2 rewrites")
        self.assertIn("Proofread", view.meta.text())

        view.search.setText("garden")
        QtWidgets.QApplication.processEvents()
        self.assertEqual(view.list.count(), 1)
        self.assertIn("Concise", view.meta.text())

    def test_action_filter_limits_the_list(self):
        view = self.make_view()
        index = view.filter.findData("Proofread")
        self.assertGreaterEqual(index, 1)
        view.filter.setCurrentIndex(index)
        QtWidgets.QApplication.processEvents()
        self.assertEqual(view.list.count(), 1)
        self.assertIn("Proofread", view.meta.text())
        self.assertEqual(view.filter.currentData(), "Proofread")

    def test_selecting_a_row_shows_its_detail(self):
        view = self.make_view()
        entry = self.host.history_store.entries()[0]
        view.list.setCurrentRow(0)
        QtWidgets.QApplication.processEvents()
        self.assertEqual(view._selected_id, entry.id)
        self.assertTrue(view.meta.text().startswith(entry.option))
        self.assertEqual(view.original_view.toPlainText(), entry.original)
        self.assertEqual(view.revised_view.toPlainText(), entry.revised)
        self.assertTrue(view.copy_revised.isEnabled())
        self.assertTrue(view.copy_original.isEnabled())

        view.side_button.click()
        QtWidgets.QApplication.processEvents()
        self.assertEqual(view.stack.currentWidget(), view.side_host)
        view.changes_button.click()
        self.assertEqual(view.stack.currentWidget(), view.diff_host)

    def test_copy_original_and_revised_write_the_clipboard(self):
        view = self.make_view()
        view.list.setCurrentRow(0)
        QtWidgets.QApplication.processEvents()
        entry = self.host.history_store.get(view._selected_id)

        click(view.copy_revised)
        QtTest.QTest.qWait(50)
        self.assertEqual(QtWidgets.QApplication.clipboard().text(), entry.revised)
        self.assertEqual(view.copy_revised.text(), "Copied")

        click(view.copy_original)
        QtTest.QTest.qWait(50)
        self.assertEqual(QtWidgets.QApplication.clipboard().text(), entry.original)
        self.assertEqual(view.copy_original.text(), "Copied")

    def test_delete_removes_one_entry_after_confirmation(self):
        view = self.make_view()
        view.list.setCurrentRow(0)
        QtWidgets.QApplication.processEvents()
        selected = view._selected_id

        with mock.patch(
            "ui.RewritesView.QtWidgets.QMessageBox.question",
            return_value=QtWidgets.QMessageBox.StandardButton.Yes,
        ) as question:
            click(view.delete_button)

        question.assert_called_once()
        self.assertEqual(self.host.history_store.count(), 1)
        self.assertIsNone(self.host.history_store.get(selected))
        self.assertEqual(view.count.text(), "1 rewrites")
        self.assertIn("history_changed", self.host.calls)

    def test_clear_all_removes_every_entry(self):
        view = self.make_view()
        with mock.patch(
            "ui.RewritesView.QtWidgets.QMessageBox.question",
            return_value=QtWidgets.QMessageBox.StandardButton.Yes,
        ) as question:
            click(view.clear_button)

        question.assert_called_once()
        self.assertEqual(self.host.history_store.count(), 0)
        self.assertEqual(view.list.count(), 0)
        self.assertEqual(view.empty.title_label.text(), "No rewrites yet")
        self.assertFalse(view.clear_button.isEnabled())

    def test_history_toggle_updates_the_app_and_the_store(self):
        view = self.make_view()
        view.history_toggle.setChecked(False)
        QtWidgets.QApplication.processEvents()
        self.assertFalse(self.host.history_enabled)
        self.assertFalse(self.host.config["history_enabled"])
        self.assertIn("set_history_enabled:False", self.host.calls)

        view.history_toggle.setChecked(True)
        QtWidgets.QApplication.processEvents()
        self.assertTrue(self.host.history_enabled)
        self.assertTrue(self.host.config["history_enabled"])

    def test_show_entry_clears_the_search_and_selects_the_exact_row(self):
        view = self.make_view(entries=3)
        target = self.host.history_store.entries()[-1]
        view.search.setText("zzz-no-match")
        QtWidgets.QApplication.processEvents()

        view.show_entry(target.id)
        QtWidgets.QApplication.processEvents()

        self.assertEqual(view.search.text(), "")
        self.assertEqual(view._selected_id, target.id)
        current = view.list.currentItem()
        self.assertIsNotNone(current)
        self.assertEqual(current.data(QtCore.Qt.ItemDataRole.UserRole), target.id)


if __name__ == "__main__":
    unittest.main()
