"""Shared shell components.

Small, native Qt widgets that carry the paper language. Views compose these
instead of restyling labels and frames themselves.
"""

from __future__ import annotations

from typing import Callable

from PySide6 import QtCore, QtGui, QtWidgets

from rework.theme import Palette, current_palette
from ui.design import GAP, ghost_button, primary_button


class StatusChip(QtWidgets.QPushButton):
    """A clickable run state. The text carries the state, not only the color."""

    def __init__(self, palette: Palette | None = None, parent=None):
        super().__init__(parent)
        self._palette = palette or current_palette()
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(30)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.set_state(paused=False)

    def set_state(self, paused: bool, detail: str = "") -> None:
        if paused:
            self.set_status("Paused", "warning", "Resume Writing Tools", "Resume Writing Tools", detail)
        else:
            self.set_status("Running", "accent", "Pause Writing Tools", "Pause Writing Tools", detail)

    def set_status(
        self,
        text: str,
        tone: str = "accent",
        tooltip: str = "",
        accessible: str = "",
        detail: str = "",
    ) -> None:
        p = self._palette
        if tone == "warning":
            background, color = p.warning_bg, p.warning_fg
        else:
            background, color = p.accent_soft, p.accent
        label = f"{text}  {detail}" if detail else text
        self.setText(label)
        self.setToolTip(tooltip or text)
        self.setAccessibleName(accessible or text)
        self.setStyleSheet(
            f"QPushButton {{ background: {background}; color: {color};"
            f" border: 1px solid {color}; border-radius: 14px;"
            " padding: 4px 12px; font-size: 11px; font-weight: 700; }"
            f"QPushButton:hover {{ border-color: {p.ink}; }}"
            f"QPushButton:focus {{ border: 2px solid {p.ink}; }}"
        )


class EmptyState(QtWidgets.QWidget):
    def __init__(
        self,
        title: str,
        body: str,
        action_text: str | None = None,
        on_action: Callable[[], None] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(24, 32, 24, 32)
        layout.setSpacing(8)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        title_label = QtWidgets.QLabel(title)
        title_label.setObjectName("EmptyTitle")
        title_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title_label.setWordWrap(True)
        layout.addWidget(title_label)
        self.title_label = title_label

        body_label = QtWidgets.QLabel(body)
        body_label.setObjectName("EmptyBody")
        body_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        body_label.setWordWrap(True)
        body_label.setMaximumWidth(420)
        layout.addWidget(body_label, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)
        self.body_label = body_label

        self.button = None
        self._layout = layout
        if action_text and on_action is not None:
            button = primary_button(action_text)
            button.clicked.connect(on_action)
            layout.addSpacing(4)
            layout.addWidget(button, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)
            self.button = button

    def set_content(self, title: str, body: str) -> None:
        self.title_label.setText(title)
        self.body_label.setText(body)

    def set_action(self, text: str | None, on_action: Callable[[], None] | None) -> None:
        if self.button is not None:
            self.button.setParent(None)
            self.button.deleteLater()
            self.button = None
        if not text or on_action is None:
            return
        button = primary_button(text)
        button.clicked.connect(on_action)
        self._layout.addSpacing(4)
        self._layout.addWidget(button, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)
        self.button = button


class Banner(QtWidgets.QFrame):
    """Inline cause and next step. Errors stay until the problem is fixed."""

    def __init__(
        self,
        title: str,
        body: str = "",
        action_text: str | None = None,
        on_action: Callable[[], None] | None = None,
        tone: str = "warning",
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("Banner" if tone == "warning" else "BannerInfo")
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        text_column = QtWidgets.QVBoxLayout()
        text_column.setSpacing(2)
        title_label = QtWidgets.QLabel(title)
        title_label.setObjectName("BannerTitle")
        title_label.setWordWrap(True)
        text_column.addWidget(title_label)
        self.title_label = title_label
        body_label = QtWidgets.QLabel(body)
        body_label.setObjectName("BannerBody")
        body_label.setWordWrap(True)
        body_label.setVisible(bool(body))
        text_column.addWidget(body_label)
        self.body_label = body_label
        layout.addLayout(text_column, 1)

        if action_text and on_action is not None:
            button = ghost_button(action_text)
            button.setMinimumHeight(28)
            button.clicked.connect(on_action)
            layout.addWidget(button, 0, QtCore.Qt.AlignmentFlag.AlignTop)

    def set_content(self, title: str, body: str = "") -> None:
        self.title_label.setText(title)
        self.body_label.setText(body)
        self.body_label.setVisible(bool(body))

    def set_action(self, text: str, on_action: Callable[[], None]) -> None:
        button = ghost_button(text)
        button.setMinimumHeight(28)
        button.clicked.connect(on_action)
        self.layout().addWidget(button, 0, QtCore.Qt.AlignmentFlag.AlignTop)


class ElidedLabel(QtWidgets.QLabel):
    """One line that elides instead of forcing the card wider."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._full = text
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Ignored,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        self.setText(text)

    def set_full_text(self, text: str) -> None:
        self._full = text
        self._apply()

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt signature)
        super().resizeEvent(event)
        self._apply()

    def _apply(self) -> None:
        metrics = self.fontMetrics()
        self.setText(
            metrics.elidedText(self._full, QtCore.Qt.TextElideMode.ElideRight, max(0, self.width()))
        )


class Metric(QtWidgets.QWidget):
    def __init__(self, label: str, value: str = "", parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        self.label = QtWidgets.QLabel(label)
        self.label.setObjectName("MetricLabel")
        layout.addWidget(self.label)
        self.value = QtWidgets.QLabel(value)
        self.value.setObjectName("MetricValue")
        self.value.setWordWrap(True)
        layout.addWidget(self.value)

    def set_value(self, value: str) -> None:
        self.value.setText(value)


class Toast(QtWidgets.QFrame):
    """A short confirmation. It never steals focus and never blocks."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        self.label = QtWidgets.QLabel("")
        self.label.setObjectName("ToastText")
        layout.addWidget(self.label)
        self.hide()
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text: str, milliseconds: int = 2600) -> None:
        self.label.setText(text)
        self.setAccessibleName(text)
        self.adjustSize()
        self.reposition()
        self.show()
        self.raise_()
        self._timer.start(milliseconds)

    def reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        margin = 20
        x = max(margin, (parent.width() - self.width()) // 2)
        y = parent.height() - self.height() - margin
        self.move(x, y)


class CommandPalette(QtWidgets.QFrame):
    """In-window command palette. It is an accelerator, not a second app."""

    def __init__(self, host: QtWidgets.QWidget, palette: Palette | None = None):
        super().__init__(host)
        self._palette = palette or current_palette()
        self._host = host
        self._commands: list[tuple[str, str, Callable[[], None]]] = []
        self._filtered: list[int] = []
        self.setObjectName("Scrim")
        self.hide()
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        self.card = QtWidgets.QFrame(self)
        self.card.setObjectName("Palette")
        self.card.setFixedWidth(520)
        card_layout = QtWidgets.QVBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 8)
        card_layout.setSpacing(0)

        self.input = QtWidgets.QLineEdit()
        self.input.setObjectName("PaletteInput")
        self.input.setPlaceholderText("Search views and commands")
        self.input.setAccessibleName("Search views and commands")
        self.input.textChanged.connect(self._filter)
        self.input.returnPressed.connect(self._run_current)
        self.input.installEventFilter(self)
        card_layout.addWidget(self.input)

        self.list = QtWidgets.QListWidget()
        self.list.setObjectName("PaletteList")
        self.list.setAccessibleName("Commands")
        self.list.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.list.itemClicked.connect(lambda _item: self._run_current())
        card_layout.addWidget(self.list, 1)

        hint = QtWidgets.QLabel("Enter to run  \u00b7  Esc to close")
        hint.setObjectName("PaletteHint")
        hint.setContentsMargins(12, 4, 12, 4)
        card_layout.addWidget(hint)

        self._previous_focus: QtWidgets.QWidget | None = None

    def open(self, commands: list[tuple[str, str, Callable[[], None]]]) -> None:
        self._commands = commands
        self._previous_focus = QtWidgets.QApplication.focusWidget()
        self.setGeometry(self._host.rect())
        self.input.clear()
        self._filter("")
        self.show()
        self.raise_()
        self.input.setFocus()
        self._place_card()

    def close_palette(self) -> None:
        self.hide()
        if self._previous_focus is not None:
            self._previous_focus.setFocus()
        self._previous_focus = None
        self._host.setFocus()

    def _place_card(self) -> None:
        rows = max(1, len(self._commands))
        desired = 56 + rows * 34 + 34
        available = max(180, self.height() - 80)
        height = min(max(180, desired), available)
        self.card.resize(self.card.width(), height)
        x = (self.width() - self.card.width()) // 2
        y = max(30, (self.height() - height) // 3)
        self.card.move(x, y)

    def _filter(self, text: str) -> None:
        needle = text.strip().lower()
        self.list.clear()
        self._filtered = []
        for index, (label, keywords, _callback) in enumerate(self._commands):
            if needle and needle not in label.lower() and needle not in keywords.lower():
                continue
            item = QtWidgets.QListWidgetItem(label)
            item.setSizeHint(QtCore.QSize(0, 34))
            self.list.addItem(item)
            self._filtered.append(index)
        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            self.list.addItem("No matching command")
            self.list.setEnabled(False)
            return
        self.list.setEnabled(True)

    def _run_current(self) -> None:
        row = self.list.currentRow()
        if row < 0 or row >= len(self._filtered):
            return
        _label, _keywords, callback = self._commands[self._filtered[row]]
        self.close_palette()
        callback()

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt signature)
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self.close_palette()
            return
        if event.key() in (QtCore.Qt.Key.Key_Down, QtCore.Qt.Key.Key_Up):
            self._move_selection(-1 if event.key() == QtCore.Qt.Key.Key_Up else 1)
            return
        super().keyPressEvent(event)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt signature)
        if obj is self.input and event.type() == QtCore.QEvent.Type.KeyPress:
            if event.key() == QtCore.Qt.Key.Key_Escape:
                self.close_palette()
                return True
            if event.key() in (QtCore.Qt.Key.Key_Down, QtCore.Qt.Key.Key_Up):
                self._move_selection(-1 if event.key() == QtCore.Qt.Key.Key_Up else 1)
                return True
            if event.key() in (QtCore.Qt.Key.Key_Tab, QtCore.Qt.Key.Key_Backtab):
                self._move_selection(-1 if event.key() == QtCore.Qt.Key.Key_Backtab else 1)
                return True
        return super().eventFilter(obj, event)

    def focusNextPrevChild(self, next: bool) -> bool:  # noqa: N802 (Qt signature)
        """Keep Tab inside the palette while it is open."""
        if self.isVisible():
            self._move_selection(1 if next else -1)
            return True
        return super().focusNextPrevChild(next)

    def _move_selection(self, delta: int) -> None:
        if not self.list.count() or not self._filtered:
            return
        row = self.list.currentRow()
        row = max(0, min(self.list.count() - 1, row + delta))
        self.list.setCurrentRow(row)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt signature)
        if not self.card.geometry().contains(event.position().toPoint()):
            self.close_palette()
            return
        super().mousePressEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt signature)
        super().resizeEvent(event)
        self._place_card()


def make_button(text: str, on_click: Callable[[], None], danger: bool = False) -> QtWidgets.QPushButton:
    button = QtWidgets.QPushButton(text)
    button.setObjectName("danger" if danger else "ghost")
    button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(30)
    button.setAccessibleName(text)
    button.clicked.connect(on_click)
    return button


def card_frame(parent=None) -> tuple[QtWidgets.QFrame, QtWidgets.QVBoxLayout]:
    frame = QtWidgets.QFrame(parent)
    frame.setObjectName("RowCard")
    layout = QtWidgets.QVBoxLayout(frame)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(6)
    return frame, layout


def set_selected(widget: QtWidgets.QWidget, selected: bool) -> None:
    widget.setProperty("selected", bool(selected))
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def scroll_page() -> tuple[QtWidgets.QScrollArea, QtWidgets.QVBoxLayout]:
    area = QtWidgets.QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    content = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(content)
    layout.setContentsMargins(28, 24, 28, 28)
    layout.setSpacing(16)
    area.setWidget(content)
    return area, layout
