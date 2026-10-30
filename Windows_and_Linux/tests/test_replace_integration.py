import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from WritingToolApp import WritingToolApp, _RequestContext


class Holder:
    def __init__(self, text):
        self.text = text


class RecordingController:
    def __init__(self):
        self.calls = []

    def present(self, *args):
        self.calls.append(args)


class FakeClipboard:
    def __init__(self):
        self.copied = []

    def paste(self):
        return "clipboard backup"

    def copy(self, text):
        self.copied.append(text)


class FakeKeyboard:
    class Key:
        class ctrl:
            value = "ctrl"

    class Controller:
        def press(self, key):
            pass

        def release(self, key):
            pass


class FakeMessageSignal:
    def __init__(self):
        self.messages = []

    def emit(self, *args):
        self.messages.append(args)


class FakeApp:
    def __init__(self, original="Original text."):
        self.output_queue = ""
        self.current_text_holder = Holder(original)
        self.current_option = "Concise"
        self._active_request = _RequestContext("Concise", original)
        self.rework_controller = RecordingController()
        self.show_message_signal = FakeMessageSignal()
        self._rework_target = None

    def _hide_working(self):
        pass


class ReplaceIntegrationTests(unittest.TestCase):
    def run_replace(self, app, text):
        clipboard = FakeClipboard()
        with (
            patch("WritingToolApp.pyperclip", clipboard),
            patch("WritingToolApp.pykeyboard", FakeKeyboard()),
            patch("WritingToolApp.time.sleep", lambda _: None),
        ):
            WritingToolApp.replace_text(app, text)
        return clipboard

    def test_direct_replace_presents_receipt(self):
        app = FakeApp("Original text.")
        self.run_replace(app, "Revised text.")
        self.assertEqual(
            app.rework_controller.calls,
            [("Concise", "Original text.", "Revised text.")],
        )

    def test_window_mode_does_not_present_receipt(self):
        app = FakeApp("Original text.")
        app.current_response_window = type(
            "Window",
            (),
            {"chat_history": [{"role": "user"}], "append_text": lambda self, text: None},
        )()
        self.run_replace(app, "Summary text.")
        self.assertEqual(app.rework_controller.calls, [])

    def test_window_mode_error_uses_the_window_failure_state(self):
        app = FakeApp("Original text.")
        failures = []

        class Window:
            chat_history = [{"role": "user"}]

            def show_failure(self, title, body):
                failures.append((title, body))

        app.current_response_window = Window()
        self.run_replace(app, "An error occurred while processing the response.")
        self.assertEqual(
            failures,
            [("Couldn't get a response", "An error occurred while processing the response.")],
        )
        self.assertEqual(app.rework_controller.calls, [])

    def test_provider_error_does_not_paste_or_present_receipt(self):
        app = FakeApp("Original text.")
        clipboard = self.run_replace(app, "An error occurred while processing the response.")
        self.assertEqual(app.rework_controller.calls, [])
        self.assertEqual(clipboard.copied, [])
        self.assertEqual(
            app.show_message_signal.messages,
            [("Error", "An error occurred while processing the response.")],
        )

    def test_no_captured_text_does_not_present_receipt(self):
        app = FakeApp("")
        self.run_replace(app, "Revised text.")
        self.assertEqual(app.rework_controller.calls, [])

    def test_receipt_uses_the_text_pinned_to_the_request(self):
        app = FakeApp("Original text.")
        app.current_text_holder.text = "A newer selection"
        self.run_replace(app, "Revised text.")
        self.assertEqual(
            app.rework_controller.calls,
            [("Concise", "Original text.", "Revised text.")],
        )


if __name__ == "__main__":
    unittest.main()
