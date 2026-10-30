import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from WritingToolApp import WritingToolApp
from rework.history import HistoryStore
from rework.model import Rework


class FakeHistoryApp:
    def __init__(self, store, enabled=True):
        self.history_store = store
        self.history_enabled = enabled
        self.history_window = None
        self.dashboard_window = None

    def _refresh_dashboard(self):
        pass


class FailingStore:
    def add(self, rework):
        raise RuntimeError("disk full")


class HistoryIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = HistoryStore(Path(self.temp.name) / "history.db")
        self.rework = Rework.create("Concise", "very good report", "strong report")

    def save(self, app):
        return WritingToolApp._save_rework_to_history(app, self.rework)

    def test_enabled_history_writes_a_row(self):
        app = FakeHistoryApp(self.store)
        self.assertTrue(self.save(app))
        self.assertEqual(self.store.count(), 1)

    def test_disabled_history_writes_nothing(self):
        app = FakeHistoryApp(self.store, enabled=False)
        self.assertFalse(self.save(app))
        self.assertEqual(self.store.count(), 0)

    def test_missing_store_writes_nothing(self):
        app = FakeHistoryApp(None)
        self.assertFalse(self.save(app))

    def test_store_failure_is_swallowed(self):
        app = FakeHistoryApp(FailingStore())
        self.assertFalse(self.save(app))


if __name__ == "__main__":
    unittest.main()
