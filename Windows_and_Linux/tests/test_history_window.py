import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6 import QtWidgets

from rework.history import HistoryStore
from rework.model import Rework
from ui.HistoryWindow import HistoryWindow


class HistoryWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = HistoryStore(Path(self.temp.name) / "history.db")
        self.config = {"history_enabled": True}
        self.saved = []

    def make_window(self):
        window = HistoryWindow(
            self.store,
            self.config,
            on_config_change=self.saved.append,
        )

        def destroy():
            window.close()
            window.deleteLater()
            QtWidgets.QApplication.processEvents()

        self.addCleanup(destroy)
        return window

    def add(self, option, original, revised):
        self.store.add(Rework.create(option, original, revised))

    def test_lists_entries_newest_first(self):
        self.add("Concise", "the budget draft", "the budget")
        self.add("Friendly", "Hello there", "Hi there")
        window = self.make_window()
        self.assertEqual(window.list.count(), 2)
        self.assertIn("2 rewrites", window.count_label.text())

    def test_selecting_an_entry_shows_both_texts(self):
        self.add("Concise", "the budget draft", "the budget")
        window = self.make_window()
        window.list.setCurrentRow(0)
        self.assertEqual(window.original_view.toPlainText(), "the budget draft")
        self.assertEqual(window.reworked_view.toPlainText(), "the budget")

    def test_search_filters_the_list(self):
        self.add("Concise", "the budget draft", "the budget")
        self.add("Friendly", "Hello there", "Hi there")
        window = self.make_window()
        window.search.setText("budget")
        window.refresh()
        self.assertEqual(window.list.count(), 1)
        self.assertIn("1 of 2", window.count_label.text())

    def test_empty_store_shows_an_empty_state(self):
        window = self.make_window()
        self.assertEqual(window.list.count(), 0)
        self.assertIn("No rewrites yet", window.meta.text())

    def test_toggle_updates_config(self):
        window = self.make_window()
        window.toggle.setChecked(False)
        self.assertFalse(self.config["history_enabled"])
        self.assertEqual(self.saved, [self.config])
        self.assertIn("History is off", window.toggle_note.text())

    def test_delete_removes_the_selected_entry(self):
        self.add("Concise", "the budget draft", "the budget")
        window = self.make_window()
        window.list.setCurrentRow(0)
        with patch(
            "ui.HistoryWindow.QtWidgets.QMessageBox.question",
            return_value=QtWidgets.QMessageBox.StandardButton.Yes,
        ):
            window._delete_current()
        self.assertEqual(self.store.count(), 0)
        self.assertIn("No rewrites yet", window.meta.text())

    def test_clear_all_removes_every_entry(self):
        self.add("Concise", "the budget draft", "the budget")
        self.add("Friendly", "Hello there", "Hi there")
        window = self.make_window()
        with patch(
            "ui.HistoryWindow.QtWidgets.QMessageBox.question",
            return_value=QtWidgets.QMessageBox.StandardButton.Yes,
        ):
            window._clear_all()
        self.assertEqual(self.store.count(), 0)
        self.assertIn("No rewrites yet", window.meta.text())

    def test_copy_puts_the_selected_text_on_the_clipboard(self):
        window = self.make_window()
        window._copy(window.copy_original, "the budget draft")
        self.assertEqual(
            QtWidgets.QApplication.clipboard().text(), "the budget draft"
        )


if __name__ == "__main__":
    unittest.main()
