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
        self.tray_menu = QtWidgets.QMenu()
        self.toggle_action = None
        self._ = lambda text: text
        self.apply_dark_mode_styles = WritingToolApp.__dict__[
            "apply_dark_mode_styles"
        ].__get__(self)

    def show_history(self):
        pass

    def show_dashboard(self):
        pass

    def show_settings(self):
        pass

    def toggle_paused(self):
        pass

    def show_about(self):
        pass

    def exit_app(self):
        pass


class TrayMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_update_tray_menu_applies_palette_and_actions(self):
        app = FakeApp()
        WritingToolApp.update_tray_menu(app)
        labels = [action.text() for action in app.tray_menu.actions() if not action.isSeparator()]
        self.assertIn("Rewrite History", labels)
        self.assertIn("Open Writing Tools", labels)
        self.assertIn("Settings", labels)
        self.assertIn("Pause", labels)
        self.assertIn("About", labels)
        self.assertIn("Exit", labels)


if __name__ == "__main__":
    unittest.main()
