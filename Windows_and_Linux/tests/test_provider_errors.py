import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.ProviderErrors import describe


class FakeError(Exception):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class ProviderErrorTests(unittest.TestCase):
    def test_a_gated_free_model_names_the_restriction(self):
        error = FakeError(
            "Error code: 403 - {'error': {'message': 'thinkingmachines/inkling:free "
            "is only available on agentic harnesses.'}}",
            status_code=403,
        )
        title, message = describe(error, model="thinkingmachines/inkling:free")
        self.assertEqual(title, "Model not available")
        self.assertIn("thinkingmachines/inkling:free", message)
        self.assertIn("partner apps", message)
        self.assertIn("standard model", message)
        self.assertNotIn("agentic harnesses", message)

    def test_a_bad_key_is_named(self):
        title, message = describe(FakeError("Incorrect API key provided", 401))
        self.assertEqual(title, "API key rejected")
        self.assertIn("Settings", message)

    def test_a_rate_limit_is_named(self):
        title, message = describe(FakeError("rate limit exceeded", 429))
        self.assertEqual(title, "Rate limit hit")

    def test_a_missing_model_is_named(self):
        title, message = describe(FakeError("model not found", 404))
        self.assertEqual(title, "Model not found")
        self.assertIn("Load the model list", message)

    def test_a_long_context_error_is_named(self):
        title, message = describe(FakeError("maximum context length exceeded", 400))
        self.assertEqual(title, "Selection too long")

    def test_an_unknown_error_is_shortened(self):
        title, message = describe(FakeError("x" * 900))
        self.assertEqual(title, "Provider error")
        self.assertLessEqual(len(message), 300)
        self.assertTrue(message.endswith("\u2026"))


if __name__ == "__main__":
    unittest.main()
