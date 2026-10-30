import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rework.controller import ReworkController
from rework.model import Rework


class FakeCard:
    def __init__(self, rework, on_undo, on_close, saved=False):
        self.rework = rework
        self.on_undo = on_undo
        self.on_close = on_close
        self.saved = saved
        self.shown_at = None
        self.closed = False

    def show_near(self, position):
        self.shown_at = position

    def close(self):
        self.closed = True


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.cards = []
        self.undone = []

        def factory(rework, on_undo, on_close, saved):
            card = FakeCard(rework, on_undo, on_close, saved)
            self.cards.append(card)
            return card

        self.controller = ReworkController(factory, undo=self.undone.append)

    def test_no_change_shows_no_receipt(self):
        result = self.controller.present("Proofread", "Same.", "Same.")
        self.assertIsNone(result)
        self.assertEqual(self.cards, [])

    def test_no_change_dismisses_the_previous_receipt(self):
        self.controller.present("Concise", "very good", "strong")
        result = self.controller.present("Proofread", "Same.", "Same.")
        self.assertIsNone(result)
        self.assertTrue(self.cards[0].closed)
        self.assertIsNone(self.controller.current)

    def test_receipt_holds_the_rework(self):
        result = self.controller.present("Concise", "very good", "strong")
        self.assertIsNotNone(result)
        self.assertIs(self.controller.current, result)
        self.assertEqual(len(self.cards), 1)
        self.assertEqual(self.cards[0].rework.option, "Concise")

    def test_second_rework_replaces_the_first(self):
        self.controller.present("Concise", "very good", "strong")
        self.controller.present("Friendly", "Hello.", "Hi there!")
        self.assertEqual(len(self.cards), 2)
        self.assertTrue(self.cards[0].closed)
        self.assertFalse(self.cards[1].closed)

    def test_close_clears_the_reference(self):
        self.controller.present("Concise", "very good", "strong")
        self.cards[0].on_close()
        self.assertIsNone(self.controller.current)
        self.assertIsNone(self.controller._card)

    def test_late_close_from_old_card_does_not_clear_new_card(self):
        self.controller.present("Concise", "very good", "strong")
        self.controller.present("Friendly", "Hello.", "Hi there!")
        self.cards[0].on_close()
        self.assertIs(self.controller._card, self.cards[1])
        self.assertEqual(self.controller.current.option, "Friendly")

    def test_undo_dismisses_then_calls_handler(self):
        rework = self.controller.present("Concise", "very good", "strong")
        self.cards[0].on_undo()
        self.assertEqual(self.undone, [rework])
        self.assertTrue(self.cards[0].closed)
        self.assertIsNone(self.controller.current)

    def test_undo_without_handler_still_dismisses(self):
        controller = ReworkController(lambda *args: FakeCard(*args))
        controller.present("Concise", "very good", "strong")
        controller._card.on_undo()
        self.assertIsNone(controller.current)

    def test_save_callback_marks_the_card_saved(self):
        saved = []
        controller = ReworkController(
            lambda *args: FakeCard(*args),
            save=lambda rework: saved.append(rework) or True,
        )
        controller.present("Concise", "very good", "strong")
        self.assertEqual(len(saved), 1)
        self.assertTrue(controller._card.saved)

    def test_save_is_not_called_when_there_are_no_changes(self):
        saved = []
        controller = ReworkController(
            lambda *args: FakeCard(*args),
            save=lambda rework: saved.append(rework) or True,
        )
        controller.present("Proofread", "Same.", "Same.")
        self.assertEqual(saved, [])

    def test_save_failure_still_shows_an_unsaved_receipt(self):
        def fail(rework):
            raise RuntimeError("disk full")

        controller = ReworkController(lambda *args: FakeCard(*args), save=fail)
        controller.present("Concise", "very good", "strong")
        self.assertFalse(controller._card.saved)


if __name__ == "__main__":
    unittest.main()
