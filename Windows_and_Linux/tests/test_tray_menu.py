import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6 import QtWidgets

from rework.theme import LIGHT
from WritingToolApp import WritingToolApp


class FakeApp:
    def __init__(self):
        self.design_palette = LIGHT
        self.paused = False
        self.tray_icon = None
        self.tray_menu = QtWidgets.QMenu()
        self.toggle_action = None
        self.history_enabled = False
        self.history_store = None
        self._ = lambda text: text
        self.apply_dark_mode_styles = WritingToolApp.__dict__[
            "apply_dark_mode_styles"
        ].__get__(self)
        self._refresh_tray_tooltip = lambda: None

    def show_history(self, entry_id=None):
        pass

    def show_dashboard(self, view=None):
        pass

    def show_settings(self):
        pass

    def toggle_paused(self):
        pass

    def exit_app(self):
        pass


class TrayMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_update_tray_menu_is_small_and_names_the_new_views(self):
        app = FakeApp()
        WritingToolApp.update_tray_menu(app)
        labels = [
            action.text()
            for action in app.tray_menu.actions()
            if not action.isSeparator()
        ]
        self.assertEqual(
            labels,
            ["Open Writing Tools", "Recent rewrites", "Rewrites", "Settings", "Pause", "Quit"],
        )
        self.assertNotIn("About", labels)
        self.assertNotIn("Exit", labels)

    def test_recent_rewrites_submenu_lists_a_saved_entry(self):
        app = FakeApp()
        app.history_enabled = True
        app.history_store = type(
            "Store",
            (),
            {"entries": lambda self, limit=5: [type("Entry", (), {
                "id": 7,
                "option": "Proofread",
                "original": "their going home",
            })()]},
        )()
        WritingToolApp.update_tray_menu(app)
        recent = next(
            action.menu()
            for action in app.tray_menu.actions()
            if action.text() == "Recent rewrites"
        )
        self.assertEqual([action.text() for action in recent.actions()], [
            "Proofread  \u00b7  their going home"
        ])


if __name__ == "__main__":
    unittest.main()
