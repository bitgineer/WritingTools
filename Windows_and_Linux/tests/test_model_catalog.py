import json
import os
import sys
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PySide6 import QtTest, QtWidgets

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiprovider import GeminiProvider, OllamaProvider, OpenAICompatibleProvider
from ui import ModelCatalog
from ui.SettingsWindow import SettingsWindow

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ModelHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/v1/models":
            self.send_error(404)
            return
        if self.headers.get("Authorization") != "Bearer test-key":
            self.send_error(401)
            return
        body = json.dumps(
            {"data": [{"id": "model-b"}, {"id": "model-a"}, {"id": "model-a"}]}
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class Shell:
    def __init__(self):
        self.config = {
            "provider": "OpenAI Compatible (For Experts)",
            "providers": {},
        }
        self.providers = [
            GeminiProvider(self),
            OpenAICompatibleProvider(self),
            OllamaProvider(self),
        ]
        self.current_provider = self.providers[1]
        self.dashboard_window = None

    def save_config(self, config):
        pass

    def register_hotkey(self):
        pass

    def create_tray_icon(self):
        pass

    def show_dashboard(self):
        pass

    def validate_shortcut(self, value):
        return None

    @staticmethod
    def _to_pynput_hotkey(value):
        return value


class ModelCatalogTests(unittest.TestCase):
    def test_models_url_appends_models(self):
        self.assertEqual(
            ModelCatalog.models_url("https://api.openai.com/v1/"),
            "https://api.openai.com/v1/models",
        )

    def test_models_url_rejects_missing_or_bad_base(self):
        with self.assertRaises(ModelCatalog.ModelFetchError):
            ModelCatalog.models_url("")
        with self.assertRaises(ModelCatalog.ModelFetchError):
            ModelCatalog.models_url("api.openai.com")

    def test_parse_models_handles_common_shapes(self):
        self.assertEqual(
            ModelCatalog.parse_models(
                {"data": [{"id": "b"}, {"id": "a"}, {"id": "a"}]}
            ),
            ["a", "b"],
        )
        self.assertEqual(ModelCatalog.parse_models({"models": ["x"]}), ["x"])
        self.assertEqual(ModelCatalog.parse_models(["y", "x"]), ["x", "y"])
        self.assertEqual(ModelCatalog.parse_models({"data": [{"nope": 1}]}), [])

    def test_redirects_cannot_carry_the_key_to_another_host(self):
        handler = ModelCatalog._SameHostRedirects()
        request = urllib.request.Request(
            "https://api.example.com/v1/models",
            headers={"Authorization": "Bearer secret"},
        )
        with self.assertRaises(ModelCatalog.ModelFetchError):
            handler.redirect_request(
                request, None, 302, "Found", {}, "https://evil.example/models"
            )
        with self.assertRaises(ModelCatalog.ModelFetchError):
            handler.redirect_request(
                request, None, 302, "Found", {}, "http://api.example.com/models"
            )


class ModelPickerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ModelHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_address[1]}/v1"
        cls.qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self._argv = sys.argv[0]
        sys.argv[0] = os.path.join(APP, "main.py")
        self.addCleanup(self._restore_argv)

    def _restore_argv(self):
        sys.argv[0] = self._argv

    def _window(self):
        window = SettingsWindow(Shell())
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)
        return window

    def _wait_for(self, predicate, timeout_ms=4000):
        waited = 0
        while not predicate() and waited < timeout_ms:
            QtTest.QTest.qWait(100)
            waited += 100
        return predicate()

    def test_apply_models_fills_the_picker_and_a_choice_fills_the_field(self):
        window = self._window()
        window._apply_models(["model-b", "model-a"])
        self.assertTrue(window.model_combo.isEnabled())
        self.assertEqual(window.model_combo.count(), 2)
        self.assertIn("2 models", window.model_status.text())

        window.model_combo.setCurrentIndex(window.model_combo.findText("model-a"))
        fields = {
            field.accessibleName(): field
            for field in window.findChildren(QtWidgets.QLineEdit)
        }
        self.assertEqual(fields["API Model"].text(), "model-a")

    def test_load_models_fetches_from_the_configured_endpoint(self):
        window = self._window()
        fields = {
            field.accessibleName(): field
            for field in window.findChildren(QtWidgets.QLineEdit)
        }
        fields["API Base URL"].setText(self.base_url)
        fields["API Key"].setText("test-key")

        window._load_models()
        self.assertTrue(self._wait_for(lambda: window.model_combo.isEnabled()))
        self.assertEqual(
            [window.model_combo.itemText(i) for i in range(window.model_combo.count())],
            ["model-a", "model-b"],
        )

    def test_a_rejected_key_shows_a_readable_error(self):
        window = self._window()
        fields = {
            field.accessibleName(): field
            for field in window.findChildren(QtWidgets.QLineEdit)
        }
        fields["API Base URL"].setText(self.base_url)
        fields["API Key"].setText("wrong-key")

        window._load_models()
        self.assertTrue(
            self._wait_for(lambda: "rejected the key" in window.model_status.text())
        )

    def test_load_without_a_base_url_does_not_call_the_provider(self):
        window = self._window()
        fields = {
            field.accessibleName(): field
            for field in window.findChildren(QtWidgets.QLineEdit)
        }
        fields["API Base URL"].setText("")

        window._load_models()
        self.assertIn("base URL", window.model_status.text())


if __name__ == "__main__":
    unittest.main()
