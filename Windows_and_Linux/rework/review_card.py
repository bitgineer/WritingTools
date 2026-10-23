"""The compact receipt and its expanded review."""

from __future__ import annotations

import html
from typing import Callable

from PySide6 import QtCore, QtGui, QtWidgets

from rework.diff_view import DiffView
from rework.full_text_view import FullTextView
from rework.model import Rework
from rework.theme import Palette, card_stylesheet, current_palette
from ui.drag import DragMover
from ui.design import clock_icon

COMPACT_WIDTH = 372
REVIEW_WIDTH = 480
SHADOW_MARGIN = 12
AUTO_CLOSE_MS = 20000


class ReworkCard(QtWidgets.QWidget):
    def __init__(
        self,
        rework: Rework,
        on_undo: Callable[[], None],
        on_close: Callable[[], None],
        saved_to_history: bool = False,
        palette: Palette | None = None,
        on_history: Callable[[], None] | None = None,
    ):
        super().__init__(None)
        self.rework = rework
        self._on_undo = on_undo
        self._on_close = on_close
        self._saved_to_history = saved_to_history
        self._on_history = on_history
        self._palette = palette or current_palette()
        self._expanded = False
        self._closing = False
        self._anchor = QtCore.QPoint()
        self._drag_movers: list[DragMover] = []

        self._setup_window()
        self._build()
        self._install_shortcuts()

        self._auto_close = QtCore.QTimer(self)
        self._auto_close.setSingleShot(True)
        self._auto_close.timeout.connect(self.close)

    def _setup_window(self) -> None:
        self.setWindowFlags(
            QtCore.Qt.WindowType.Tool
            | QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowTitle("Rewrite review")
        self.setAccessibleName("Rewrite receipt")
        self.setStyleSheet(card_stylesheet(self._palette))
        self.setFixedWidth(COMPACT_WIDTH + SHADOW_MARGIN * 2)

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(SHADOW_MARGIN, SHADOW_MARGIN, SHADOW_MARGIN, SHADOW_MARGIN)
        self.card = QtWidgets.QFrame()
        self.card.setObjectName("card")
        root.addWidget(self.card)

        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 6)
        shadow.setColor(QtGui.QColor(0, 0, 0, 70 if self._palette.mode == "light" else 140))
        self.card.setGraphicsEffect(shadow)

        card_layout = QtWidgets.QVBoxLayout(self.card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(10)

        self.page_host = QtWidgets.QWidget()
        self.page_layout = QtWidgets.QVBoxLayout(self.page_host)
        self.page_layout.setContentsMargins(0, 0, 0, 0)
        self.compact_page = self._build_compact_page()
        self.review_page = None
        self.page_layout.addWidget(self.compact_page)
        card_layout.addWidget(self.page_host)

        self.adjustSize()

    def _build_compact_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(self._check_badge())
        title = QtWidgets.QLabel(f"{self.rework.option} rewrite")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._history_button())
        header.addWidget(self._close_button())
        layout.addLayout(header)

        headline = QtWidgets.QLabel(self.rework.headline())
        headline.setObjectName("headline")
        layout.addWidget(headline)
        self._make_draggable(title, headline)

        sample = self._sample_label()
        if sample is not None:
            layout.addWidget(sample)

        meta_row = QtWidgets.QHBoxLayout()
        meta = QtWidgets.QLabel(self.rework.detail())
        meta.setObjectName("meta")
        meta_row.addWidget(meta)
        meta_row.addStretch()
        privacy = QtWidgets.QLabel(
            "Saved to history." if self._saved_to_history else "Not saved to history."
        )
        privacy.setObjectName("privacy")
        meta_row.addWidget(privacy)
        layout.addLayout(meta_row)

        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(8)
        review = QtWidgets.QPushButton("Review changes")
        review.setObjectName("primary")
        review.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        review.setAccessibleName("Review changes")
        review.clicked.connect(self.expand)
        actions.addWidget(review)

        undo = QtWidgets.QPushButton("Undo")
        undo.setObjectName("ghost")
        undo.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        undo.setAccessibleName("Undo rework")
        undo.clicked.connect(self._undo)
        actions.addWidget(undo)
        actions.addStretch()
        layout.addLayout(actions)

        return page

    def _sample_label(self) -> QtWidgets.QLabel | None:
        samples = self.rework.sample_changes(limit=2)
        if not samples:
            return None

        parts = []
        for sample in samples:
            old = html.escape(sample.old)
            new = html.escape(sample.new)
            if old and new:
                parts.append(
                    f'<span style="color:{self._palette.delete_fg}; text-decoration:line-through;">{old}</span>'
                    f' <span style="color:{self._palette.muted};">\u2192</span> '
                    f'<span style="color:{self._palette.insert_fg}; text-decoration:underline;">{new}</span>'
                )
            elif old:
                parts.append(
                    f'<span style="color:{self._palette.delete_fg};">\u2212</span> '
                    f'<span style="color:{self._palette.delete_fg}; text-decoration:line-through;">{old}</span>'
                )
            else:
                parts.append(
                    f'<span style="color:{self._palette.insert_fg};">+</span> '
                    f'<span style="color:{self._palette.insert_fg}; text-decoration:underline;">{new}</span>'
                )

        label = QtWidgets.QLabel(" &nbsp;\u00b7&nbsp; ".join(parts))
        label.setObjectName("sample")
        label.setTextFormat(QtCore.Qt.TextFormat.RichText)
        label.setWordWrap(True)
        label.setAccessibleName("First changes: " + "; ".join(f"{s.old} to {s.new}" for s in samples))
        return label

    def _build_review_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(self._check_badge())
        title = QtWidgets.QLabel(f"{self.rework.option} rewrite")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._history_button())
        header.addWidget(self._close_button())
        layout.addLayout(header)

        meta = QtWidgets.QLabel(f"{self.rework.headline()} \u00b7 {self.rework.detail()}")
        meta.setObjectName("meta")
        layout.addWidget(meta)
        self._make_draggable(title, meta)

        divider = QtWidgets.QFrame()
        divider.setObjectName("divider")
        layout.addWidget(divider)

        if self.rework.is_substantial:
            note = QtWidgets.QLabel(
                "Most of the text changed, so the full version is easier to compare than word-by-word changes."
            )
            note.setObjectName("meta")
            note.setWordWrap(True)
            layout.addWidget(note)
            self.content_view = FullTextView(self.rework, self._palette)
            layout.addWidget(self.content_view)
        else:
            self.content_view = DiffView(self.rework.diff, self._palette)
            layout.addWidget(self.content_view)

        legend = QtWidgets.QHBoxLayout()
        legend.setSpacing(8)
        if not self.rework.is_substantial:
            legend.addWidget(self._legend_swatch("removed", self._palette.delete_fg, self._palette.delete_bg, strike=True))
            legend.addWidget(self._legend_swatch("added", self._palette.insert_fg, self._palette.insert_bg, strike=False))
        legend.addStretch()
        privacy = QtWidgets.QLabel(
            "Saved to history on this device."
            if self._saved_to_history
            else "This comparison is not saved to history."
        )
        privacy.setObjectName("privacy")
        legend.addWidget(privacy)
        layout.addLayout(legend)

        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(8)
        copy = QtWidgets.QPushButton("Copy revised")
        copy.setObjectName("ghost")
        copy.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        copy.setAccessibleName("Copy revised text")
        copy.clicked.connect(lambda: self._copy_revised(copy))
        actions.addWidget(copy)

        undo = QtWidgets.QPushButton("Undo rework")
        undo.setObjectName("ghost")
        undo.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        undo.setAccessibleName("Undo rework")
        undo.clicked.connect(self._undo)
        actions.addWidget(undo)
        actions.addStretch()

        done = QtWidgets.QPushButton("Done")
        done.setObjectName("primary")
        done.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        done.setAccessibleName("Keep rework and close")
        done.clicked.connect(self.close)
        actions.addWidget(done)
        layout.addLayout(actions)

        return page

    def _check_badge(self) -> QtWidgets.QLabel:
        badge = QtWidgets.QLabel("\u2713")
        badge.setFixedSize(20, 20)
        badge.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background-color: {self._palette.accent_soft};"
            f"color: {self._palette.accent};"
            "border-radius: 10px; font-size: 12px; font-weight: 700;"
        )
        return badge

    def _close_button(self) -> QtWidgets.QToolButton:
        button = QtWidgets.QToolButton()
        button.setObjectName("close")
        button.setText("\u00d7")
        button.setFixedSize(32, 32)
        button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        button.setToolTip("Dismiss")
        button.setAccessibleName("Dismiss rework receipt")
        button.clicked.connect(self.close)
        return button

    def _history_button(self) -> QtWidgets.QPushButton:
        button = QtWidgets.QPushButton()
        button.setObjectName("icon")
        button.setFixedSize(32, 32)
        button.setIcon(clock_icon(self._palette, 15))
        button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        button.setToolTip("Open Rewrite History")
        button.setAccessibleName("Open Rewrite History")
        button.clicked.connect(self._open_history)
        return button

    def _open_history(self) -> None:
        if self._on_history is None:
            return
        self.close()
        self._on_history()

    def _make_draggable(self, *handles: QtWidgets.QWidget) -> None:
        self._drag_movers.append(DragMover(self, list(handles)))

    def _legend_swatch(self, text: str, color: str, background: str, strike: bool) -> QtWidgets.QLabel:
        decoration = "text-decoration: line-through;" if strike else "text-decoration: underline;"
        label = QtWidgets.QLabel(text)
        label.setStyleSheet(
            f"color: {color}; background-color: {background};"
            f"border-radius: 4px; padding: 1px 6px; font-size: 11px; {decoration}"
        )
        return label

    def _install_shortcuts(self) -> None:
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Escape), self, activated=self.close)
        QtGui.QShortcut(QtGui.QKeySequence.StandardKey.Undo, self, activated=self._undo)
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Return), self, activated=self._enter)

    def _enter(self) -> None:
        if not self._expanded:
            self.expand()

    @property
    def expanded(self) -> bool:
        return self._expanded

    def expand(self) -> None:
        if self._expanded:
            return
        self._expanded = True
        self._auto_close.stop()
        self.setFixedWidth(REVIEW_WIDTH + SHADOW_MARGIN * 2)
        compact = self.compact_page
        self.compact_page = None
        self.page_layout.removeWidget(compact)
        # Hide before the deferred delete so the two pages never overlap.
        compact.hide()
        compact.deleteLater()
        self.review_page = self._build_review_page()
        self.page_layout.addWidget(self.review_page)
        self.page_layout.activate()
        self.review_page.layout().activate()
        self.adjustSize()
        self.content_view.fit_to_content()
        destiny = QtCore.QTimer(self)
        destiny.setSingleShot(True)
        destiny.timeout.connect(self._relayout_review)
        destiny.start(0)

    def _relayout_review(self) -> None:
        self.content_view.fit_to_content()
        self.adjustSize()
        self._place_near_anchor()

    def _copy_revised(self, button: QtWidgets.QPushButton) -> None:
        QtWidgets.QApplication.clipboard().setText(self.rework.revised)
        button.setText("Copied")
        timer = QtCore.QTimer(button)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: button.setText("Copy revised"))
        timer.start(1400)

    def _undo(self) -> None:
        self._on_undo()

    def enterEvent(self, event) -> None:  # noqa: N802 (Qt signature)
        """Keep the receipt while the user is reading or reaching for Undo."""
        self._auto_close.stop()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 (Qt signature)
        if not self._expanded:
            self._auto_close.start(AUTO_CLOSE_MS)
        super().leaveEvent(event)

    def show_near(self, position: QtCore.QPoint) -> None:
        self._anchor = QtCore.QPoint(position)
        self.adjustSize()
        self._place_near_anchor()
        self.show()
        self.raise_()
        self._auto_close.start(AUTO_CLOSE_MS)

    def _place_near_anchor(self) -> None:
        screen = QtGui.QGuiApplication.screenAt(self._anchor) or QtGui.QGuiApplication.primaryScreen()
        bounds = screen.availableGeometry()
        width = self.width()
        height = self.height()
        x = self._anchor.x() + 18
        y = self._anchor.y() + 18
        if x + width > bounds.right() - 8:
            x = self._anchor.x() - width - 18
        if y + height > bounds.bottom() - 8:
            y = self._anchor.y() - height - 18
        x = max(bounds.left() + 8, min(x, bounds.right() - width - 8))
        y = max(bounds.top() + 8, min(y, bounds.bottom() - height - 8))
        self.move(x, y)

    def enterEvent(self, event: QtGui.QEnterEvent) -> None:
        self._auto_close.stop()
        super().enterEvent(event)

    def leaveEvent(self, event: QtCore.QEvent) -> None:
        if not self._expanded:
            self._auto_close.start(AUTO_CLOSE_MS)
        super().leaveEvent(event)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self._auto_close.stop()
        if not self._closing:
            self._closing = True
            self._on_close()
        super().closeEvent(event)
