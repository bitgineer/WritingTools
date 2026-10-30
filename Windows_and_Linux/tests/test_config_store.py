import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import ConfigStore


class ConfigStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp(prefix="wt-config-")
        self.path = Path(self.directory) / "config.json"

    def tearDown(self):
        import shutil

        shutil.rmtree(self.directory, ignore_errors=True)

    def test_a_missing_file_starts_empty(self):
        store = ConfigStore(self.path)
        self.assertEqual(store.data, {})
        self.assertIsNone(store.recovered_from)

    def test_a_saved_config_round_trips(self):
        store = ConfigStore(self.path)
        store.set("shortcut", "ctrl+j")
        store.set("provider", "Gemini (Recommended)")
        store.update({"history_enabled": False}, save=True)

        again = ConfigStore(self.path)
        self.assertEqual(again.get("shortcut"), "ctrl+j")
        self.assertFalse(again.get("history_enabled"))

    def test_a_corrupt_file_is_quarantined_and_replaced(self):
        self.path.write_text("{ this is not json", encoding="utf-8")

        store = ConfigStore(self.path)
        self.assertEqual(store.data, {})
        self.assertTrue(store.recovered_from)
        self.assertTrue(Path(store.recovered_from).exists())
        self.assertFalse(self.path.exists())

        store.save()
        self.assertTrue(self.path.exists())
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), {})

    def test_save_leaves_no_temporary_file(self):
        store = ConfigStore(self.path)
        store.update({"shortcut": "ctrl+space"}, save=True)
        leftovers = list(Path(self.directory).glob("*.tmp"))
        self.assertEqual(leftovers, [])

    def test_replacing_the_dict_keeps_one_live_object(self):
        store = ConfigStore(self.path)
        live = store.data
        store.save({"shortcut": "ctrl+alt+j"})
        self.assertIs(store.data, live)
        self.assertEqual(live["shortcut"], "ctrl+alt+j")

    def test_provider_values_are_scoped(self):
        store = ConfigStore(self.path)
        store.set_provider("Gemini (Recommended)", {"model_name": "gemini-flash-latest"})
        store.set_provider("Ollama (For Experts)", {"api_base": "http://localhost:11434"})
        self.assertEqual(
            store.provider("Gemini (Recommended)")["model_name"],
            "gemini-flash-latest",
        )
        self.assertEqual(store.provider("missing"), {})


if __name__ == "__main__":
    unittest.main()
