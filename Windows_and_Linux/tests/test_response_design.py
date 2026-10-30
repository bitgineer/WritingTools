import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6 import QtCore, QtWidgets

from rework.theme import current_palette
from ui.design import app_stylesheet
from ui.ResponseWindow import MarkdownTextBrowser, ResponseWindow


class FakeApp(QtCore.QObject):
    followup_response_signal = QtCore.Signal(str)
    show_message_signal = QtCore.Signal(str, str)

    def __init__(self):
        super().__init__()
        self.config = {}

    def save_config(self, config):
        pass

    def process_followup_question(self, window, message):
        pass


class ResponseWindowDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def make_window(self, title="Concise Result"):
        app = FakeApp()
        window = ResponseWindow(app, title)
        window.setStyleSheet(app_stylesheet(current_palette()))
        window.selected_text = "original text"
        window.show()
        self.addCleanup(self._destroy, window)
        self.app.processEvents()
        return window, app

    @staticmethod
    def _destroy(window):
        window.close()
        window.deleteLater()
        QtWidgets.QApplication.processEvents()

    def message_browsers(self, window):
        browsers = []
        for i in range(window.chat_area.layout.count() - 1):
            container = window.chat_area.layout.itemAt(i).widget()
            browsers.append(container.layout().itemAt(0).widget())
        return browsers

    def test_empty_response_stops_thinking_and_shows_message(self):
        window, _ = self.make_window()
        self.assertTrue(window.thinking_timer.isActive())

        window.set_text("   ")
        self.app.processEvents()

        self.assertFalse(window.thinking_timer.isActive())
        self.assertFalse(window.loading_container.isVisible())
        self.assertTrue(window.status_container.isVisible())
        self.assertTrue(window.status_title.text())
        self.assertTrue(window.status_body.text())

    def test_provider_error_before_first_response_stops_thinking(self):
        window, app = self.make_window()

        app.show_message_signal.emit("Error", "An error occurred: boom")
        self.app.processEvents()

        self.assertFalse(window.thinking_timer.isActive())
        self.assertTrue(window.status_container.isVisible())
        self.assertEqual(window.status_body.text(), "An error occurred: boom")

    def test_unrelated_message_does_not_end_thinking(self):
        window, app = self.make_window()

        app.show_message_signal.emit("Information", "Settings saved.")
        self.app.processEvents()

        self.assertTrue(window.thinking_timer.isActive())
        self.assertFalse(window.status_container.isVisible())

    def test_successful_response_replaces_thinking_with_message(self):
        window, _ = self.make_window()

        window.set_text("A tight rewrite.")
        self.app.processEvents()

        self.assertFalse(window.thinking_timer.isActive())
        self.assertFalse(window.loading_container.isVisible())
        self.assertFalse(window.status_container.isVisible())
        self.assertEqual(len(self.message_browsers(window)), 1)

    def test_zoom_all_messages_changes_prose_size(self):
        window, _ = self.make_window()
        window.set_text("Some prose to zoom.")
        browser = self.message_browsers(window)[0]
        before = browser.document().defaultFont().pixelSize()

        window.zoom_all_messages("in")
        self.app.processEvents()
        grown = browser.document().defaultFont().pixelSize()

        window.zoom_all_messages("reset")
        self.app.processEvents()
        reset = browser.document().defaultFont().pixelSize()

        self.assertGreater(grown, before)
        self.assertEqual(reset, before)

    def test_assistant_prose_is_serif_and_user_text_is_sans(self):
        window, _ = self.make_window()
        window.set_text("Assistant reply.")
        window.chat_area.add_message("User question.", is_user=True)
        self.app.processEvents()

        assistant, user = self.message_browsers(window)
        self.assertIn("Georgia", assistant.document().defaultFont().families())
        self.assertIn("Segoe UI", user.document().defaultFont().families())

    def test_icon_only_buttons_have_accessible_names_and_tooltips(self):
        window, _ = self.make_window()

        icon_only = [
            button
            for button in window.findChildren(QtWidgets.QPushButton)
            if not button.text()
        ]
        self.assertGreaterEqual(len(icon_only), 4)
        for button in icon_only:
            self.assertTrue(button.accessibleName(), "icon-only button needs an accessible name")
            self.assertTrue(button.toolTip(), "icon-only button needs a tooltip")

    def test_message_browser_is_a_read_only_transparent_prose_surface(self):
        window, _ = self.make_window()
        window.set_text("Read only.")

        browser = self.message_browsers(window)[0]
        self.assertIsInstance(browser, MarkdownTextBrowser)
        self.assertTrue(browser.isReadOnly())
        self.assertFalse(browser.viewport().autoFillBackground())


if __name__ == "__main__":
    unittest.main()
