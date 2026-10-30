import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiprovider import AIProvider
from WritingToolApp import WritingToolApp


class Signal:
    def __init__(self):
        self.emitted = []

    def emit(self, *args):
        self.emitted.append(args)


class EventSignal(Signal):
    def __init__(self):
        super().__init__()
        self.event = threading.Event()

    def emit(self, *args):
        super().emit(*args)
        self.event.set()


class RecordingProvider(AIProvider):
    def __init__(self, app):
        super().__init__(app, "Recording", [])
        self.calls = []

    def get_response(self, system_instruction, prompt, return_response=False):
        self.calls.append((system_instruction, prompt, return_response))
        return "recorded answer"

    def after_load(self):
        pass

    def before_load(self):
        pass

    def cancel(self):
        pass


class ChatInterfaceTests(unittest.TestCase):
    def test_chat_uses_the_full_conversation(self):
        provider = RecordingProvider(None)
        messages = [
            {"role": "user", "content": "Summarize this"},
            {"role": "assistant", "content": "A summary"},
            {"role": "user", "content": "Make it shorter"},
        ]
        answer = provider.chat("Be direct", messages)
        self.assertEqual(answer, "recorded answer")
        self.assertEqual(provider.calls, [("Be direct", messages, True)])

    def test_follow_up_does_not_branch_on_provider_class(self):
        provider = RecordingProvider(None)

        class ResponseWindow:
            def __init__(self):
                self.chat_history = [
                    {"role": "user", "content": "Original text to summarize"},
                    {"role": "assistant", "content": "First answer"},
                ]

        class FakeApp:
            def __init__(self):
                self.current_provider = provider
                self.followup_response_signal = EventSignal()
                self.show_message_signal = Signal()

            def _provider_ready(self):
                return True

        app = FakeApp()
        window = ResponseWindow()
        WritingToolApp.process_followup_question(app, window, "Make it shorter")

        self.assertTrue(app.followup_response_signal.event.wait(2.0))
        self.assertEqual(app.followup_response_signal.emitted, [("recorded answer",)])
        self.assertEqual(len(provider.calls), 1)
        self.assertTrue(provider.calls[0][0].startswith("You are a helpful AI assistant"))
        self.assertEqual(window.chat_history[-1]["content"], "recorded answer")


if __name__ == "__main__":
    unittest.main()
