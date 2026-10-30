import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shell_fixtures import ShellTestCase, click_named, read_options, write_options

from PySide6 import QtWidgets

from ui.ActionsView import ActionsView

BASE_ACTIONS = {
    "Custom": {
        "prefix": "Make this change to the following text:\n\n",
        "instruction": "Make the requested change.",
        "icon": "icons/summary",
        "open_in_window": False,
    },
    "Proofread": {
        "prefix": "Proofread this:\n\n",
        "instruction": "Correct the grammar.",
        "icon": "icons/magnifying-glass",
        "open_in_window": False,
    },
    "Rewrite": {
        "prefix": "Rewrite this:\n\n",
        "instruction": "Improve the phrasing.",
        "icon": "icons/rewrite",
        "open_in_window": False,
    },
    "Concise": {
        "prefix": "Make this more concise:\n\n",
        "instruction": "Shorten the text.",
        "icon": "icons/concise",
        "open_in_window": False,
    },
}


class ActionsViewTests(ShellTestCase):
    def make_view(self, data=None):
        write_options(data or BASE_ACTIONS)
        view = ActionsView(self.host)
        view.show()
        QtWidgets.QApplication.processEvents()
        self.addCleanup(view.deleteLater)
        self.addCleanup(view.close)
        return view

    def test_add_an_action_inline_and_save(self):
        view = self.make_view()
        changed = []
        view.changed.connect(lambda: changed.append(True))
        before = len(read_options())

        view._add()
        self.assertFalse(view.editor.isHidden())
        view.editor.name.setText("Tighten")
        view.editor.instruction.setPlainText("Tighten the prose without losing meaning.")
        click_named(view, "Save action")
        QtWidgets.QApplication.processEvents()

        data = read_options()
        self.assertIn("Tighten", data)
        self.assertEqual(data["Tighten"]["instruction"], "Tighten the prose without losing meaning.")
        self.assertFalse(data["Tighten"]["open_in_window"])
        self.assertEqual(len(data), before + 1)
        self.assertTrue(view.editor.isHidden())
        self.assertEqual(changed, [True])
        self.assertEqual(self.host.calls.count("actions_changed"), 1)

    def test_edit_and_rename_keeps_the_action_position(self):
        view = self.make_view()
        order_before = list(read_options())
        view._edit("Proofread")
        self.assertEqual(view.editor.title.text(), "Edit Proofread")
        view.editor.name.setText("Tighten")
        view.editor.instruction.setPlainText("Tighten the grammar.")
        click_named(view, "Save action")
        QtWidgets.QApplication.processEvents()

        data = read_options()
        self.assertNotIn("Proofread", data)
        self.assertIn("Tighten", data)
        self.assertEqual(data["Tighten"]["instruction"], "Tighten the grammar.")
        self.assertEqual(
            list(data).index("Tighten"),
            order_before.index("Proofread"),
            "a rename keeps the action in its original slot",
        )
        self.assertEqual(len(data), len(order_before))
        self.assertEqual(self.host.calls.count("actions_changed"), 1)

    def test_reorder_moves_an_action_and_saves_the_file_order(self):
        view = self.make_view()
        view._move("Concise", -1)
        QtWidgets.QApplication.processEvents()
        data = read_options()
        self.assertEqual(
            [name for name in data if name != "Custom"],
            ["Proofread", "Concise", "Rewrite"],
        )
        self.assertIn("actions_changed", self.host.calls)

    def test_delete_removes_the_action_after_confirmation(self):
        view = self.make_view()
        with mock.patch(
            "ui.ActionsView.QtWidgets.QMessageBox.question",
            return_value=QtWidgets.QMessageBox.StandardButton.Yes,
        ) as question:
            view._delete("Rewrite")

        question.assert_called_once()
        data = read_options()
        self.assertNotIn("Rewrite", data)
        self.assertIn("Proofread", data)
        self.assertIn("actions_changed", self.host.calls)

    def test_reset_restores_the_defaults(self):
        custom = dict(BASE_ACTIONS)
        custom["Mine"] = {
            "prefix": "Do it:\n\n",
            "instruction": "Mine.",
            "icon": "icons/custom",
            "open_in_window": False,
        }
        view = self.make_view(custom)
        with mock.patch(
            "ui.ActionsView.QtWidgets.QMessageBox.question",
            return_value=QtWidgets.QMessageBox.StandardButton.Yes,
        ) as question:
            view._reset()

        question.assert_called_once()
        data = read_options()
        self.assertNotIn("Mine", data)
        self.assertIn("Proofread", data)
        self.assertIn("Summary", data)
        self.assertIn("actions_changed", self.host.calls)

    def test_hotkey_conflict_stays_inline_and_does_not_save(self):
        data = dict(BASE_ACTIONS)
        data["Proofread"]["hotkey"] = "ctrl+j"
        view = self.make_view(data)

        view._add()
        view.editor.name.setText("Second")
        view.editor.instruction.setPlainText("Second instruction.")
        view.editor.hotkey.setText("ctrl+j")
        click_named(view, "Save action")
        QtWidgets.QApplication.processEvents()

        self.assertFalse(view.editor.isHidden(), "the editor stays open on a conflict")
        self.assertFalse(view.editor.banner.isHidden())
        self.assertEqual(view.editor.banner.title_label.text(), "Shortcut not valid")
        self.assertIn("Proofread", view.editor.banner.body_label.text())
        self.assertNotIn("Second", read_options())
        self.assertNotIn("actions_changed", self.host.calls)

    def test_global_shortcut_conflict_stays_inline(self):
        view = self.make_view()
        view._add()
        view.editor.name.setText("Second")
        view.editor.hotkey.setText("ctrl+space")
        click_named(view, "Save action")
        QtWidgets.QApplication.processEvents()

        self.assertEqual(view.editor.banner.title_label.text(), "Shortcut not valid")
        self.assertIn("main Writing Tools hotkey", view.editor.banner.body_label.text())
        self.assertNotIn("Second", read_options())

    def test_an_empty_name_is_rejected_inline(self):
        view = self.make_view()
        view._add()
        view.editor.name.setText("   ")
        click_named(view, "Save action")
        QtWidgets.QApplication.processEvents()
        self.assertEqual(view.editor.banner.title_label.text(), "Action not saved")
        self.assertIn("name", view.editor.banner.body_label.text())
        self.assertFalse(view.editor.isHidden())


if __name__ == "__main__":
    unittest.main()
