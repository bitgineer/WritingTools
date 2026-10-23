"""Best-effort undo in the application that owns the text.

The receipt never owns the source application's undo stack. It can only
return focus and send the same Ctrl+Z the writer would send. On Windows the
foreground window handle is captured before the popup opens. On Linux the
window manager usually restores focus when the receipt closes, so the
keystroke is sent without a handle.
"""

from __future__ import annotations

import ctypes
import logging
import sys
import time

from pynput import keyboard


def capture_foreground_window() -> int | None:
    if sys.platform != "win32":
        return None
    try:
        return int(ctypes.windll.user32.GetForegroundWindow())
    except Exception as error:
        logging.debug(f"Could not capture foreground window: {error}")
        return None


def focus_window(handle: int | None) -> bool:
    if sys.platform != "win32" or not handle:
        return False
    try:
        if ctypes.windll.user32.IsIconic(handle):
            ctypes.windll.user32.ShowWindow(handle, 9)
        return bool(ctypes.windll.user32.SetForegroundWindow(handle))
    except Exception as error:
        logging.debug(f"Could not restore focus: {error}")
        return False


def is_foreground(handle: int | None) -> bool:
    """True when the captured window still owns focus, so paste needs no wait."""
    if sys.platform != "win32" or not handle:
        return False
    try:
        return int(ctypes.windll.user32.GetForegroundWindow()) == handle
    except Exception:
        return False


def send_undo() -> bool:
    try:
        controller = keyboard.Controller()
        with controller.pressed(keyboard.Key.ctrl):
            controller.press("z")
            controller.release("z")
        return True
    except Exception as error:
        logging.warning(f"Could not send Ctrl+Z: {error}")
        return False


def undo_last_paste(handle: int | None = None) -> bool:
    if handle is not None:
        focus_window(handle)
        time.sleep(0.08)
    sent = send_undo()
    if sent:
        logging.debug("Sent Ctrl+Z to the source window")
    return sent
