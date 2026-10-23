import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rework.history import HistoryStore
from rework.model import Rework


class HistoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "history.db"
        self.store = HistoryStore(self.path)

    def add(self, option, original, revised):
        return self.store.add(Rework.create(option, original, revised))

    def test_add_and_list_newest_first(self):
        first = self.add("Concise", "very good", "strong")
        second = self.add("Proofread", "Wait...", "Wait.")
        entries = self.store.entries()
        self.assertEqual([entry.id for entry in entries], [second, first])
        self.assertEqual(entries[0].option, "Proofread")
        self.assertEqual(entries[0].original, "Wait...")
        self.assertEqual(entries[0].revised, "Wait.")

    def test_stats_are_stored(self):
        self.add("Concise", "very good report", "strong report")
        entry = self.store.entries()[0]
        self.assertEqual(entry.changed_words, 2)
        self.assertEqual(entry.removed_words, 2)
        self.assertEqual(entry.added_words, 1)

    def test_search_matches_any_text(self):
        self.add("Concise", "the budget draft", "the budget")
        self.add("Friendly", "Hello there", "Hi there")
        self.assertEqual(len(self.store.entries("budget")), 1)
        self.assertEqual(len(self.store.entries("Friendly")), 1)
        self.assertEqual(len(self.store.entries("nothing")), 0)

    def test_delete_one_and_clear_all(self):
        entry_id = self.add("Concise", "very good", "strong")
        self.assertTrue(self.store.delete(entry_id))
        self.assertFalse(self.store.delete(entry_id))
        self.add("Concise", "very good", "strong")
        self.store.clear()
        self.assertEqual(self.store.count(), 0)

    def test_retention_keeps_newest(self):
        store = HistoryStore(self.path, limit=2)
        for index in range(4):
            store.add(Rework.create("Concise", f"old {index}", f"new {index}"))
        entries = store.entries()
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].original, "old 3")
        self.assertEqual(entries[1].original, "old 2")

    def test_parent_directory_is_created(self):
        nested = Path(self.temp.name) / "a" / "b" / "history.db"
        HistoryStore(nested)
        self.assertTrue(nested.exists())


if __name__ == "__main__":
    unittest.main()
