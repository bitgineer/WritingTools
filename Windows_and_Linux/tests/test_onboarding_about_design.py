import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6 import QtWidgets

from update_checker import CURRENT_VERSION
from ui.AboutWindow import AboutWindow, RELEASES_URL
from ui.OnboardingWindow import OnboardingWindow


class FakeApp:
    def __init__(self):
        self.config = {}
        self.settings_calls = []

    def show_settings(self, providers_only=False):
        self.settings_calls.append(providers_only)

    def validate_shortcut(self, shortcut):
        return None if shortcut.strip() else "Enter a shortcut, for example ctrl+space."


def _destroy(widget):
    widget.close()
    widget.deleteLater()
    QtWidgets.QApplication.processEvents()


class OnboardingDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def make_window(self):
        fake = FakeApp()
        window = OnboardingWindow(fake)
        self.addCleanup(_destroy, window)
        closed = []
        window.close_signal.connect(lambda: closed.append(True))
        return window, fake, closed

    def test_window_width_is_in_the_design_range(self):
        window, _, _ = self.make_window()
        self.assertGreaterEqual(window.width(), 640)
        self.assertLessEqual(window.width(), 720)

    def test_no_theme_radio_buttons_remain(self):
        window, _, _ = self.make_window()
        self.assertEqual(window.findChildren(QtWidgets.QRadioButton), [])

    def test_continue_saves_shortcut_only_and_hands_off_to_providers_settings(self):
        window, fake, closed = self.make_window()
        window.shortcut_input.setText("ctrl+alt+j")
        continue_button = next(
            b for b in window.findChildren(QtWidgets.QPushButton) if b.text() == "Continue"
        )
        continue_button.click()
        self.assertEqual(fake.config, {"shortcut": "ctrl+alt+j"})
        self.assertEqual(fake.settings_calls, [True])
        self.assertEqual(closed, [])

    def test_blank_shortcut_falls_back_to_default(self):
        window, fake, _ = self.make_window()
        window.shortcut_input.setText("   ")
        window.on_next_clicked()
        self.assertEqual(fake.config, {"shortcut": "ctrl+space"})

    def test_shortcut_field_has_accessible_name_and_example(self):
        window, _, _ = self.make_window()
        self.assertEqual(window.shortcut_input.accessibleName(), "Shortcut")
        self.assertIn("ctrl+space", window.shortcut_input.accessibleDescription())

    def test_closing_without_continue_emits_close_signal(self):
        window, _, closed = self.make_window()
        window.close()
        self.assertEqual(closed, [True])


class AboutDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def make_window(self):
        window = AboutWindow()
        self.addCleanup(_destroy, window)
        return window

    def test_window_width_is_in_the_design_range(self):
        window = self.make_window()
        self.assertGreaterEqual(window.width(), 640)
        self.assertLessEqual(window.width(), 720)

    def test_version_line_comes_from_update_checker(self):
        window = self.make_window()
        texts = [label.text() for label in window.findChildren(QtWidgets.QLabel)]
        self.assertIn(f"Version {CURRENT_VERSION}", texts)
        self.assertFalse(any("7.0" in text for text in texts))

    def test_latest_release_button_opens_the_releases_page(self):
        window = self.make_window()
        button = next(
            b for b in window.findChildren(QtWidgets.QPushButton)
            if b.text() == "See the latest release"
        )
        with mock.patch("ui.AboutWindow.webbrowser.open") as opened:
            button.click()
        opened.assert_called_once_with(RELEASES_URL)

    def test_view_source_button_is_present_and_secondary(self):
        window = self.make_window()
        names = [b.text() for b in window.findChildren(QtWidgets.QPushButton)]
        self.assertIn("View source", names)
        source = next(b for b in window.findChildren(QtWidgets.QPushButton) if b.text() == "View source")
        self.assertNotEqual(source.objectName(), "primary")

    def test_contributor_link_opens_their_profile(self):
        window = self.make_window()
        button = next(
            b for b in window.findChildren(QtWidgets.QPushButton)
            if b.accessibleName() == "ErrorCatDev on GitHub"
        )
        with mock.patch("ui.AboutWindow.webbrowser.open") as opened:
            button.click()
        opened.assert_called_once_with("https://github.com/ErrorCatDev")

    def test_details_are_in_a_named_scroll_area(self):
        window = self.make_window()
        scroll_areas = window.findChildren(QtWidgets.QScrollArea)
        self.assertEqual(len(scroll_areas), 1)
        self.assertEqual(scroll_areas[0].accessibleName(), "About details")


if __name__ == "__main__":
    unittest.main()
