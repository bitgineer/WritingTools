"""Reading, validating, and writing the rework actions in options.json.

The popup and Settings both manage the same list. This module owns the entry
shape and the hotkey rules so the two surfaces cannot drift apart.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Callable

from pynput import keyboard as pykeyboard

CUSTOM = "Custom"


def options_path() -> str:
    return os.path.join(os.path.dirname(sys.argv[0]), "options.json")


def load(path: str | None = None) -> dict:
    target = path or options_path()
    try:
        with open(target, "r") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        logging.warning("Options file missing or unreadable; using the defaults")
        return defaults()


def save(data: dict, path: str | None = None) -> bool:
    target = path or options_path()
    temporary = target + ".tmp"
    try:
        with open(temporary, "w") as handle:
            json.dump(data, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        return True
    except OSError:
        logging.exception("Could not save the actions to %s", target)
        try:
            if os.path.exists(temporary):
                os.unlink(temporary)
        except OSError:
            pass
        return False


def defaults() -> dict:
    from ui.CustomPopupWindow import DEFAULT_OPTIONS_JSON

    return json.loads(DEFAULT_OPTIONS_JSON)


def actions(data: dict) -> list[tuple[str, dict]]:
    """The editable actions, in file order. Custom is the free-text field."""
    return [(name, entry) for name, entry in data.items() if name != CUSTOM]


def validate_hotkey(
    hotkey: str,
    data: dict,
    global_shortcut: str,
    to_pynput: Callable[[str], str],
    exclude: str | None = None,
) -> str | None:
    """Return an error message, or None when the hotkey can be registered.

    An empty hotkey is always valid. It means the action only appears in the
    popup, which is how every legacy entry looks.
    """
    if not hotkey:
        return None
    try:
        pykeyboard.HotKey.parse(to_pynput(hotkey))
    except Exception as error:
        return (
            f"'{hotkey}' isn't a valid hotkey.\n\n"
            f"Use '+' between keys, e.g. ctrl+j or ctrl+shift+p.\n"
            f"({error})"
        )

    if hotkey == (global_shortcut or "ctrl+space").strip().lower():
        return (
            f"'{hotkey}' is already used as the main Writing Tools "
            f"hotkey. Pick a different combination."
        )

    for name, entry in data.items():
        if name == exclude:
            continue
        other = (entry.get("hotkey") or "").strip().lower()
        if other and other == hotkey:
            return (
                f"'{hotkey}' is already used by the '{name}' action. "
                f"Pick a different combination."
            )
    return None


def build_entry(dialog_data: dict, existing: dict | None = None) -> dict:
    """Assemble the options.json entry from the editor's output.

    Preserves fields the dialog does not expose and only writes `hotkey` when
    the user provided one.
    """
    entry = dict(existing) if existing else {}
    entry["prefix"] = entry.get("prefix") or dialog_data["prefix"]
    entry["icon"] = entry.get("icon") or dialog_data["icon"]
    entry["instruction"] = dialog_data["instruction"]
    entry["open_in_window"] = dialog_data["open_in_window"]
    hotkey = (dialog_data.get("hotkey") or "").strip().lower()
    if hotkey:
        entry["hotkey"] = hotkey
    else:
        entry.pop("hotkey", None)
    return entry


def summary(entry: dict) -> str:
    """One readable line for a list row."""
    if entry.get("open_in_window"):
        return "Opens in the reader"
    return "Replaces the selected text"


def replace_entry(data: dict, old_name: str, new_name: str, entry: dict) -> dict:
    """Swap an entry in place, keeping the popup order when it is renamed."""
    result = {}
    for key, value in data.items():
        if key == old_name:
            result[new_name] = entry
        elif key == new_name:
            continue
        else:
            result[key] = value
    return result
