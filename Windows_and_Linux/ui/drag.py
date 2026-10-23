"""Drag-to-move support for frameless windows.

Every floating surface in the app is frameless so it can sit quietly over the
document. Frameless windows have no title bar, so without a drag handle the
user can only move them by closing and reopening. This module gives the
floating surfaces a small, reuseable move behavior without adding chrome.

Attach it to the widgets that already look like the window's header. The
handle list is explicit so clicks on buttons and fields keep their normal
behavior.
"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class DragMover(QtCore.QObject):
    """Move a top-level window while the user drags one of its handles."""

    def __init__(
        self,
        window: QtWidgets.QWidget,
        handles: list[QtWidgets.QWidget],
        cursor: QtCore.Qt.CursorShape = QtCore.Qt.CursorShape.OpenHandCursor,
    ) -> None:
        super().__init__(window)
        self._window = window
        self._offset = QtCore.QPoint()
        self._dragging = False
        for handle in handles:
            handle.installEventFilter(self)
            handle.setCursor(cursor)
            handle.setToolTip(handle.toolTip() or "Drag to move")

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt signature)
        etype = event.type()
        if etype == QtCore.QEvent.Type.MouseButtonPress:
            if event.button() == QtCore.Qt.MouseButton.LeftButton:
                self._offset = (
                    event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
                )
                self._dragging = True
                self._window.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
                return True
        elif etype == QtCore.QEvent.Type.MouseMove:
            if self._dragging:
                self._window.move(event.globalPosition().toPoint() - self._offset)
                return True
        elif etype == QtCore.QEvent.Type.MouseButtonRelease:
            if self._dragging:
                self._dragging = False
                self._window.unsetCursor()
                return True
        return False
