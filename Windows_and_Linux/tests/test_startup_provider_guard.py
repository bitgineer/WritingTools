import os
import sys
import threading
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiprovider import GeminiProvider
from WritingToolApp import WritingToolApp


class Signal:
    def __init__(self):
        self.emitted = []

    def emit(self, *args):
        self.emitted.append(args)


class FakeApp:
    def __init__(self, api_key):
        self.config = {
            "provider": "Gemini (Recommended)",
            "providers": {"Gemini (Recommended)": {"api_key": api_key, "model_name": "gemini-flash-latest"}},
        }
        self.providers = [GeminiProvider(self)]
        self.current_provider = None
        self.settings_calls = []
        self.show_message_signal = Signal()
        self.followup_response_signal = Signal()
        self._ = lambda text: text

    def show_settings(self, providers_only=False):
        self.settings_calls.append(providers_only)

    def _provider_ready(self):
        return WritingToolApp._provider_ready(self)

    def _finish_working(self):
        pass


class StartupProviderGuardTests(unittest.TestCase):
    def test_bad_saved_key_does_not_crash_and_opens_setup(self):
        app = FakeApp(api_key="")
        with self.assertLogs(level="ERROR"):
            ready = WritingToolApp._activate_saved_provider(app)

        self.assertFalse(ready)
        self.assertIsNone(app.current_provider)
        self.assertEqual(app.settings_calls, [True], "providers-only setup must open")
        self.assertEqual(len(app.show_message_signal.emitted), 1)
        title, message = app.show_message_signal.emitted[0]
        self.assertEqual(title, "AI provider not ready")
        self.assertIn("Gemini (Recommended) could not start", message)

    def test_valid_saved_key_activates_provider_without_setup(self):
        app = FakeApp(api_key="test-key")
        ready = WritingToolApp._activate_saved_provider(app)

        self.assertTrue(ready)
        self.assertIs(app.current_provider, app.providers[0])
        self.assertEqual(app.settings_calls, [])
        self.assertEqual(app.show_message_signal.emitted, [])

    def test_request_without_provider_shows_message_and_skips_the_call(self):
        app = FakeApp(api_key="")
        app.options = {"Proofread": {"open_in_window": False, "prefix": "", "instruction": ""}}
        app.current_text_holder = None
        holder = SimpleNamespace(ready=threading.Event(), text="Some text.")
        holder.ready.set()
        app.output_queue = ""

        WritingToolApp.process_option_thread(app, "Proofread", None, holder)

        self.assertEqual(len(app.show_message_signal.emitted), 1)
        title, message = app.show_message_signal.emitted[0]
        self.assertEqual(title, "AI provider not set up")
        self.assertIn("Settings", message)


if __name__ == "__main__":
    unittest.main()
