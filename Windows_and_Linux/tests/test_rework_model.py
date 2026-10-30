import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rework.model import Rework


class ReworkModelTests(unittest.TestCase):
    def test_headline_counts_changed_words(self):
        rework = Rework.create("Concise", "very good report", "strong report")
        self.assertEqual(rework.headline(), "2 words changed")
        self.assertEqual(rework.detail(), "2 removed \u00b7 1 added")

    def test_punctuation_only_headline(self):
        rework = Rework.create("Proofread", "Wait...", "Wait.")
        self.assertEqual(rework.headline(), "Punctuation and spacing updated")

    def test_no_change_is_flagged(self):
        rework = Rework.create("Proofread", "Same text.", "Same text.")
        self.assertFalse(rework.has_changes)
        self.assertEqual(rework.headline(), "No visible changes")

    def test_samples_pair_removed_and_added_words(self):
        rework = Rework.create("Concise", "very good report", "strong report")
        samples = rework.sample_changes()
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0].old, "very good")
        self.assertEqual(samples[0].new, "strong")

    def test_samples_separate_edits_at_unchanged_words(self):
        rework = Rework.create("Proofread", "one two three", "one four five")
        samples = rework.sample_changes()
        self.assertEqual([(s.old, s.new) for s in samples], [("two", "four"), ("three", "five")])

    def test_samples_truncate_long_hunks(self):
        rework = Rework.create(
            "Rewrite",
            "a" * 80,
            "b" * 80,
        )
        sample = rework.sample_changes(width=20)[0]
        self.assertEqual(len(sample.old), 20)
        self.assertTrue(sample.old.endswith("\u2026"))

    def test_samples_cap_the_number_of_edits(self):
        rework = Rework.create("Proofread", "a b c d", "w x y z")
        self.assertEqual(len(rework.sample_changes(limit=2)), 2)

    def test_small_edit_is_not_substantial(self):
        rework = Rework.create(
            "Proofread",
            "The report is very good and it covers the main points.",
            "The report is strong and it covers the main points.",
        )
        self.assertFalse(rework.is_substantial)

    def test_most_of_the_text_changed_is_substantial(self):
        rework = Rework.create(
            "Professional",
            "I wanted to follow up on the budget draft you sent over yesterday.",
            "Following up on the budget draft. Two areas need another pass.",
        )
        self.assertTrue(rework.is_substantial)


if __name__ == "__main__":
    unittest.main()
