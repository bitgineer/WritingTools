import os
import sys
import tempfile
import unittest

from PySide6 import QtCore, QtTest, QtWidgets

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rework.history import HistoryStore
from rework.model import Rework
from ui.DashboardWindow import DashboardWindow, RecentRow


class FakeProvider:
    provider_name = "Gemini (Recommended)"


class FakeHistoryWindow:
    def __init__(self):
        self.entry_ids = []

    def show_entry(self, entry_id):
        self.entry_ids.append(entry_id)


class FakeApp:
    def __init__(self):
        self.config = {"shortcut": "ctrl+space", "provider": "Gemini (Recommended)"}
        self.current_provider = FakeProvider()
        self.history_enabled = True
        self.paused = False
        self.history_window = FakeHistoryWindow()
        self.history_calls = 0
        self.settings_calls = 0
        self.about_calls = 0
        self.exit_calls = 0

    def show_history(self):
        self.history_calls += 1

    def show_settings(self):
        self.settings_calls += 1

    def show_about(self):
        self.about_calls += 1

    def exit_app(self):
        self.exit_calls += 1

    def toggle_paused(self):
        self.paused = not self.paused


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def make_window(self, entries=2):
        folder = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(folder, ignore_errors=True))
        store = HistoryStore(os.path.join(folder, "history.db"))
        if entries:
            store.add(
                Rework.create(
                    "Concise",
                    "The cat sat on the mat today and looked outside.",
                    "The cat rested on the mat and watched the garden.",
                )
            )
        if entries > 1:
            store.add(
                Rework.create(
                    "Proofread",
                    "their going to the store tomorow",
                    "they are going to the store tomorrow",
                )
            )
        app = FakeApp()
        window = DashboardWindow(app, store)
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)
        return window, app, store

    def test_recent_rewrites_render_newest_first(self):
        window, _, _ = self.make_window()
        rows = window.findChildren(RecentRow)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].entry.option, "Proofread")
        self.assertEqual(window.count_label.text(), "2 saved rewrites")

    def test_clicking_a_row_opens_history_at_that_entry(self):
        window, app, _ = self.make_window()
        row = window.findChildren(RecentRow)[0]
        QtTest.QTest.mouseClick(row, QtCore.Qt.MouseButton.LeftButton)
        QtWidgets.QApplication.processEvents()
        self.assertEqual(app.history_calls, 1)
        self.assertEqual(app.history_window.entry_ids, [row.entry.id])

    def test_empty_history_explains_the_next_step(self):
        window, _, _ = self.make_window(entries=0)
        self.assertEqual(window.findChildren(RecentRow), [])
        self.assertEqual(window.count_label.text(), "No rewrites yet")
        texts = [label.text() for label in window.findChildren(QtWidgets.QLabel)]
        self.assertTrue(any("next rewrite will appear here" in text for text in texts))

    def test_pause_updates_the_state_and_the_button(self):
        window, app, _ = self.make_window()
        window.pause_button.click()
        QtWidgets.QApplication.processEvents()
        self.assertTrue(app.paused)
        self.assertEqual(window.pause_button.text(), "Resume")
        self.assertEqual(window.pause_button.accessibleName(), "Resume")
        self.assertEqual(window.state_chip.text(), "Paused")

    def test_row_opens_with_the_keyboard(self):
        window, app, _ = self.make_window()
        row = window.findChildren(RecentRow)[0]
        row.setFocus()
        QtTest.QTest.keyClick(row, QtCore.Qt.Key.Key_Return)
        QtWidgets.QApplication.processEvents()
        self.assertEqual(app.history_window.entry_ids, [row.entry.id])

    def test_history_off_explains_that_nothing_is_saved(self):
        window, app, _ = self.make_window(entries=0)
        app.history_enabled = False
        window.refresh()
        self.assertEqual(window.count_label.text(), "History is off")
        texts = [label.text() for label in window.findChildren(QtWidgets.QLabel)]
        self.assertTrue(any("History is off" in text for text in texts))
        self.assertFalse(any("next rewrite will appear" in text for text in texts))

    def test_history_opens_the_requested_entry_even_after_a_search(self):
        from ui.HistoryWindow import HistoryWindow

        window, app, store = self.make_window()
        history = HistoryWindow(store, {})
        self.addCleanup(history.deleteLater)
        self.addCleanup(history.close)
        history.search.setText("zzz-no-match")
        history.refresh()
        target = store.entries()[0].id
        history.show_entry(target)
        self.assertEqual(history.search.text(), "")
        self.assertEqual(history._selected_id, target)
        self.assertEqual(
            history.list.currentItem().data(QtCore.Qt.ItemDataRole.UserRole),
            target,
        )

    def test_status_names_the_provider_shortcut_and_retention(self):
        window, _, store = self.make_window()
        self.assertEqual(window.status_values["Provider"].text(), "Gemini (Recommended)")
        self.assertEqual(window.status_values["Shortcut"].text(), "ctrl+space")
        self.assertEqual(window.status_values["History"].text(), "On, stored locally")

    def test_history_button_opens_the_history_window(self):
        window, app, _ = self.make_window()
        window.history_button.click()
        QtWidgets.QApplication.processEvents()
        self.assertEqual(app.history_calls, 1)

    def test_history_off_is_named_in_status(self):
        window, app, _ = self.make_window()
        app.history_enabled = False
        window.refresh()
        self.assertEqual(window.status_values["History"].text(), "Off")


if __name__ == "__main__":
    unittest.main()
