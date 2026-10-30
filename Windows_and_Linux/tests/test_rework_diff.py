import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rework.diff import DELETE, EQUAL, INSERT, diff_words, tokenize


class TokenizeTests(unittest.TestCase):
    def test_round_trip_preserves_whitespace_and_punctuation(self):
        text = "  Hello,   world!\nSecond line.  "
        self.assertEqual("".join(tokenize(text)), text)

    def test_contractions_stay_together(self):
        self.assertIn("don't", tokenize("I don't know."))

    def test_cjk_is_split_per_character(self):
        self.assertEqual(tokenize("你好世界"), ["你", "好", "世", "界"])

    def test_accented_words_stay_together(self):
        self.assertEqual(tokenize("café résumé"), ["café", " ", "résumé"])

    def test_cyrillic_words_stay_together(self):
        self.assertEqual(tokenize("привет мир"), ["привет", " ", "мир"])


class DiffTests(unittest.TestCase):
    def test_reconstructs_both_sides(self):
        original = "The report was very good, but it was long."
        revised = "The report was strong, but it was long."
        diff = diff_words(original, revised)
        self.assertEqual(diff.original_text(), original)
        self.assertEqual(diff.revised_text(), revised)

    def test_marks_small_word_swap(self):
        diff = diff_words("very good", "strong")
        kinds = [span.kind for span in diff.spans]
        self.assertIn(DELETE, kinds)
        self.assertIn(INSERT, kinds)
        self.assertEqual(diff.stats.removed_words, 2)
        self.assertEqual(diff.stats.added_words, 1)
        self.assertEqual(diff.stats.changed_words, 2)

    def test_unchanged_text_has_no_edits(self):
        diff = diff_words("Same text.", "Same text.")
        self.assertFalse(diff.stats.has_changes)
        self.assertEqual([span.kind for span in diff.spans], [EQUAL])

    def test_punctuation_only_change_counts_as_an_edit(self):
        diff = diff_words("Wait...", "Wait.")
        self.assertTrue(diff.stats.has_changes)
        self.assertEqual(diff.stats.changed_words, 0)
        self.assertEqual(diff.stats.edits, 1)

    def test_insertion_into_empty_original(self):
        diff = diff_words("", "New sentence.")
        self.assertEqual(diff.original_text(), "")
        self.assertEqual(diff.revised_text(), "New sentence.")
        self.assertEqual(diff.stats.added_words, 2)

    def test_each_replaced_word_is_marked(self):
        diff = diff_words("one two three", "one four five")
        kinds = [span.kind for span in diff.spans]
        self.assertEqual(kinds.count(DELETE), 2)
        self.assertEqual(kinds.count(INSERT), 2)


if __name__ == "__main__":
    unittest.main()
