import ctypes
import logging
import os
import sys
import traceback

# Set up logging to console
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

from PySide6 import QtCore


def crash_log_path():
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "crash.log")


def write_crash_log():
    """A windowed app has no console, so put the startup traceback on disk."""
    try:
        with open(crash_log_path(), "a", encoding="utf-8") as handle:
            handle.write(traceback.format_exc() + "\n")
    except Exception:
        pass


def raise_running_window() -> bool:
    """Bring an existing Writing Tools window forward, if one is open.

    Uses the Win32 window title instead of a socket server. That keeps the
    packaged app free of an extra Qt module and works whether the window is
    visible or hidden to the tray.
    """
    if sys.platform != "win32":
        return False
    try:
        user32 = ctypes.windll.user32
        handle = user32.FindWindowW(None, "Writing Tools")
        if handle:
            user32.ShowWindow(handle, 9)  # SW_RESTORE
            user32.SetForegroundWindow(handle)
            return True
    except Exception:
        logging.exception("Could not raise the running window")
    return False


def acquire_single_instance_lock():
    """Keep a second launch from adding a second tray icon and hotkey listener."""
    QtCore.QCoreApplication.setApplicationName("Writing Tools")
    QtCore.QCoreApplication.setOrganizationName("Writing Tools")
    folder = QtCore.QStandardPaths.writableLocation(
        QtCore.QStandardPaths.StandardLocation.AppDataLocation
    ) or os.path.expanduser("~")
    os.makedirs(folder, exist_ok=True)

    lock = QtCore.QLockFile(os.path.join(folder, "writing-tools.lock"))
    lock.setStaleLockTime(30000)
    return lock if lock.tryLock(100) else None


def main():
    """
    The main entry point of the application.
    """
    from WritingToolApp import WritingToolApp

    if "--background" not in sys.argv and raise_running_window():
        logging.info("Writing Tools is already running. Raised its window.")
        return

    lock = acquire_single_instance_lock()
    if lock is None:
        logging.info("Writing Tools is already running. Exiting this launch.")
        return

    app = WritingToolApp(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    sys.exit(app.exec())


if __name__ == '__main__':
    try:
        main()
    except Exception:
        write_crash_log()
        raise
