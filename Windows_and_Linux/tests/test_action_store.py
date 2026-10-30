import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui import ActionStore


def to_pynput(value):
    return "+".join(f"<{part}>" if len(part) > 1 else part for part in value.split("+"))


class ActionStoreTests(unittest.TestCase):
    def test_build_entry_keeps_the_prefix_and_icon_when_editing(self):
        existing = {
            "prefix": "Proofread this:\n\n",
            "icon": "icons/magnifying-glass",
            "instruction": "old",
        }
        result = ActionStore.build_entry(
            {
                "name": "Proofread",
                "prefix": "Make this change to the following text:\n\n",
                "instruction": "new",
                "icon": "icons/custom",
                "open_in_window": False,
            },
            existing=existing,
        )
        self.assertEqual(result["prefix"], "Proofread this:\n\n")
        self.assertEqual(result["icon"], "icons/magnifying-glass")
        self.assertEqual(result["instruction"], "new")

    def test_rename_keeps_the_popup_order(self):
        data = {
            "Proofread": {"instruction": "a"},
            "Rewrite": {"instruction": "b"},
            "Custom": {"instruction": "c"},
        }
        result = ActionStore.replace_entry(
            data, "Proofread", "Check", {"instruction": "a"}
        )
        self.assertEqual(list(result), ["Check", "Rewrite", "Custom"])

    def test_hotkey_cannot_reuse_the_global_shortcut(self):
        error = ActionStore.validate_hotkey(
            "ctrl+space", {}, "ctrl+space", to_pynput
        )
        self.assertIn("main Writing Tools hotkey", error)

    def test_hotkey_cannot_reuse_another_action(self):
        data = {"Proofread": {"hotkey": "ctrl+j"}}
        error = ActionStore.validate_hotkey("ctrl+j", data, "ctrl+space", to_pynput)
        self.assertIn("already used by the 'Proofread' action", error)

    def test_a_malformed_hotkey_is_rejected(self):
        error = ActionStore.validate_hotkey(
            "ctrl+not-a-key-name", {}, "ctrl+space", to_pynput
        )
        self.assertIsNotNone(error)

    def test_empty_hotkey_is_allowed(self):
        self.assertIsNone(
            ActionStore.validate_hotkey("", {}, "ctrl+space", to_pynput)
        )

    def test_missing_options_fall_back_to_the_defaults(self):
        data = ActionStore.load(os.path.join(os.path.dirname(__file__), "no-such.json"))
        self.assertIn("Proofread", data)
        self.assertIn("Custom", data)


if __name__ == "__main__":
    unittest.main()
