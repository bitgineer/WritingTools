"""Read-only Qt view that renders one word-level diff."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from rework.diff import DELETE, INSERT, WordDiff
from rework.theme import Palette


class DiffView(QtWidgets.QTextEdit):
    def __init__(self, diff: WordDiff, palette: Palette, parent=None):
        super().__init__(parent)
        self._diff = diff
        self._palette = palette

        self.setObjectName("diff")
        self.setReadOnly(True)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setWordWrapMode(QtGui.QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
            | QtCore.Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.document().setDocumentMargin(10)

        font = QtGui.QFont()
        font.setFamilies(["Segoe UI", "Inter", "Ubuntu", "sans-serif"])
        font.setPixelSize(13)
        self.setFont(font)

        self._build()

    def _build(self) -> None:
        cursor = self.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.Start)
        cursor.beginEditBlock()

        previous = None
        for span in self._diff.spans:
            fmt = QtGui.QTextCharFormat()
            fmt.setForeground(QtGui.QColor(self._palette.ink))
            if span.kind == DELETE:
                fmt.setForeground(QtGui.QColor(self._palette.delete_fg))
                fmt.setBackground(QtGui.QColor(self._palette.delete_bg))
                fmt.setFontStrikeOut(True)
            elif span.kind == INSERT:
                fmt.setForeground(QtGui.QColor(self._palette.insert_fg))
                fmt.setBackground(QtGui.QColor(self._palette.insert_bg))
                fmt.setFontUnderline(True)

            if {previous, span.kind} == {DELETE, INSERT}:
                cursor.insertText("\u2009", QtGui.QTextCharFormat())
            cursor.insertText(span.text, fmt)
            previous = span.kind

        cursor.endEditBlock()

        block = QtGui.QTextBlockFormat()
        block.setLineHeight(145, QtGui.QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        cursor.select(QtGui.QTextCursor.SelectionType.Document)
        cursor.mergeBlockFormat(block)

    def fit_to_content(self, max_height: int = 320) -> None:
        """Size the viewport to short diffs; long diffs scroll."""
        width = self.viewport().width()
        if width <= 0:
            return
        self.document().setTextWidth(width)
        height = int(self.document().size().height()) + 2 * int(self.document().documentMargin())
        self.setFixedHeight(max(72, min(max_height, height + 2)))
