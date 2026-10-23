import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6 import QtCore, QtGui, QtWidgets

from rework.diff_view import DiffView
from rework.full_text_view import FullTextView
from rework.model import Rework
from rework.review_card import ReworkCard
from rework.theme import LIGHT


def _destroy(widget):
    widget.close()
    widget.deleteLater()
    QtWidgets.QApplication.processEvents()


class ReworkUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def make_card(self):
        rework = Rework.create("Concise", "very good report", "strong report")
        closed = []
        card = ReworkCard(rework, lambda: None, lambda: closed.append(True), palette=LIGHT)
        self.addCleanup(_destroy, card)
        return card, closed

    def test_card_starts_compact_and_expands(self):
        card, _ = self.make_card()
        card.show_near(QtCore.QPoint(200, 200))
        self.assertFalse(card.expanded)
        self.assertTrue(card.isVisible())
        compact_width = card.width()
        compact_height = card.height()
        card.expand()
        QtWidgets.QApplication.processEvents()
        self.assertTrue(card.expanded)
        self.assertGreater(card.width(), compact_width)
        self.assertGreater(card.height(), compact_height)

    def test_compact_receipt_shows_the_first_edits(self):
        card, _ = self.make_card()
        sample = card.findChild(QtWidgets.QLabel, "sample")
        self.assertIsNotNone(sample)
        self.assertIn("very good", sample.text())
        self.assertIn("strong", sample.text())

    def test_card_declares_a_non_activating_window(self):
        card, _ = self.make_card()
        self.assertTrue(
            card.testAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating)
        )
        self.assertTrue(card.windowFlags() & QtCore.Qt.WindowType.Tool)

    def test_diff_view_marks_removed_and_added_words(self):
        rework = Rework.create("Concise", "very good report", "strong report")
        view = DiffView(rework.diff, LIGHT)
        text = view.document().toPlainText()
        cursor = QtGui.QTextCursor(view.document())

        cursor.setPosition(text.index("good") + 1)
        self.assertTrue(cursor.charFormat().fontStrikeOut())

        cursor.setPosition(text.index("strong") + 1)
        self.assertTrue(cursor.charFormat().fontUnderline())

    def test_close_reports_once(self):
        card, closed = self.make_card()
        card.show_near(QtCore.QPoint(200, 200))
        card.close()
        card.close()
        self.assertEqual(closed, [True])

    def test_diff_view_fits_without_error(self):
        rework = Rework.create("Concise", "very good report", "strong report")
        view = DiffView(rework.diff, LIGHT)
        self.addCleanup(_destroy, view)
        view.resize(320, 200)
        view.show()
        view.fit_to_content()
        self.assertGreater(view.height(), 0)

    def test_small_edit_uses_inline_diff(self):
        rework = Rework.create(
            "Proofread",
            "The report is very good and it covers the main points.",
            "The report is strong and it covers the main points.",
        )
        card = ReworkCard(rework, lambda: None, lambda: None, palette=LIGHT)
        self.addCleanup(_destroy, card)
        card.expand()
        self.assertIsInstance(card.content_view, DiffView)

    def test_substantial_rewrite_uses_full_text(self):
        rework = Rework.create(
            "Professional",
            "I wanted to follow up on the budget draft you sent over yesterday.",
            "Following up on the budget draft. Two areas need another pass.",
        )
        card = ReworkCard(rework, lambda: None, lambda: None, palette=LIGHT)
        self.addCleanup(_destroy, card)
        card.expand()
        self.assertIsInstance(card.content_view, FullTextView)


if __name__ == "__main__":
    unittest.main()
