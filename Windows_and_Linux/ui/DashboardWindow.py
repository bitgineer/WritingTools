"""The main window. Recent rewrites, status, and every control in one place.

The tray app can stay in the tray. This window exists so the writer can see
what the AI has been doing, reach Settings, pause, About, or exit without
hunting for a tray menu.
"""

from __future__ import annotations

from datetime import datetime, timezone

from PySide6 import QtCore, QtGui, QtWidgets

from rework.history import HistoryEntry, HistoryStore
from rework.theme import Palette, current_palette
from ui.design import (
    GAP,
    PAGE_MARGIN,
    ghost_button,
    page_header,
    primary_button,
    section_card,
)

RECENT_LIMIT = 5


class RecentRow(QtWidgets.QFrame):
    """One rewrite, clickable, with the option, the age, and the changed text."""

    clicked = QtCore.Signal(int)

    def __init__(self, entry: HistoryEntry, palette: Palette, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.setObjectName("RecentRow")
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_Hover, True)
        self.setAccessibleName(
            f"{entry.option}, {self._change_text(entry)}, {self._age(entry.created_at)}"
        )
        self.setToolTip("Open this rewrite in History")
        self.setStyleSheet(
            f"""
            QFrame#RecentRow {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 8px;
            }}
            QFrame#RecentRow:hover {{
                background: {palette.surface_alt};
                border-color: {palette.hairline};
            }}
            QFrame#RecentRow:focus {{
                border-color: {palette.accent};
            }}
            QLabel#rowTitle {{
                color: {palette.ink};
                font-size: 13px;
                font-weight: 600;
            }}
            QLabel#rowMeta {{
                color: {palette.muted};
                font-size: 12px;
            }}
            """
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        top = QtWidgets.QHBoxLayout()
        top.setSpacing(8)
        title = QtWidgets.QLabel(entry.option)
        title.setObjectName("rowTitle")
        top.addWidget(title)
        top.addStretch(1)
        age = QtWidgets.QLabel(self._age(entry.created_at))
        age.setObjectName("rowMeta")
        top.addWidget(age)
        layout.addLayout(top)

        snippet = QtWidgets.QLabel(
            f"{self._change_text(entry)}  \u00b7  {self._snippet(entry.original)}"
        )
        snippet.setObjectName("rowMeta")
        snippet.setWordWrap(False)
        layout.addWidget(snippet)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt signature)
        if (
            event.button() == QtCore.Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self.clicked.emit(self.entry.id)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt signature)
        if event.key() in (
            QtCore.Qt.Key.Key_Return,
            QtCore.Qt.Key.Key_Enter,
            QtCore.Qt.Key.Key_Space,
        ):
            self.clicked.emit(self.entry.id)
            return
        super().keyPressEvent(event)

    @staticmethod
    def _change_text(entry: HistoryEntry) -> str:
        if entry.changed_words:
            plural = "" if entry.changed_words == 1 else "s"
            return f"{entry.changed_words} word{plural} changed"
        return "Punctuation and spacing updated"

    @staticmethod
    def _snippet(text: str, width: int = 74) -> str:
        text = " ".join(text.split())
        return text if len(text) <= width else text[: width - 1].rstrip() + "\u2026"

    @staticmethod
    def _age(value: str) -> str:
        try:
            moment = datetime.fromisoformat(value)
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=timezone.utc)
            seconds = (datetime.now(timezone.utc) - moment).total_seconds()
        except ValueError:
            return value
        if seconds < 60:
            return "Just now"
        if seconds < 3600:
            return f"{int(seconds // 60)} min ago"
        if seconds < 86400:
            return f"{int(seconds // 3600)} hr ago"
        if seconds < 172800:
            return "Yesterday"
        if seconds < 604800:
            return f"{int(seconds // 86400)} days ago"
        return moment.astimezone().strftime("%b %d, %Y")


class DashboardWindow(QtWidgets.QWidget):
    """A native window that hosts the history, status, and app controls."""

    def __init__(
        self,
        app,
        store: HistoryStore | None,
        palette: Palette | None = None,
        parent: QtWidgets.QWidget | None = None,
    ):
        super().__init__(parent)
        self.app = app
        self.store = store
        self._palette = palette or current_palette()
        self._placed = False

        self.setWindowTitle("Writing Tools")
        self.setAccessibleName("Writing Tools dashboard")
        self.setMinimumSize(760, 500)
        self.resize(920, 630)
        self._build()

    def _build(self) -> None:
        page = QtWidgets.QWidget()
        page.setObjectName("AppPage")
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        layout.setSpacing(GAP)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(GAP)
        header.addWidget(
            page_header(
                "Writing Tools",
                "Select text in any app, press your shortcut, then choose an action.",
            ),
            1,
        )
        self.state_chip = QtWidgets.QLabel("Running")
        self.state_chip.setObjectName("StateChip")
        self.state_chip.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self.state_chip, 0, QtCore.Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        body = QtWidgets.QHBoxLayout()
        body.setSpacing(GAP)

        recent_column = QtWidgets.QVBoxLayout()
        recent_column.setSpacing(GAP)
        recent_card, recent_layout = section_card(
            "Recent rewrites",
            "The last five changes. Click one to open it in Rewrite History.",
        )
        self.recent_host = QtWidgets.QWidget()
        self.recent_layout = QtWidgets.QVBoxLayout(self.recent_host)
        self.recent_layout.setContentsMargins(0, 0, 0, 0)
        self.recent_layout.setSpacing(2)
        recent_layout.addWidget(self.recent_host)

        recent_footer = QtWidgets.QHBoxLayout()
        recent_footer.setSpacing(GAP)
        self.count_label = QtWidgets.QLabel("")
        self.count_label.setObjectName("Meta")
        recent_footer.addWidget(self.count_label, 1)
        self.edit_actions_button = ghost_button("Edit actions")
        self.edit_actions_button.clicked.connect(lambda: self.app.show_settings())
        recent_footer.addWidget(self.edit_actions_button)
        self.history_button = primary_button("Open Rewrite History")
        self.history_button.clicked.connect(self._open_history)
        recent_footer.addWidget(self.history_button)
        recent_layout.addLayout(recent_footer)
        recent_column.addWidget(recent_card, 1)
        body.addLayout(recent_column, 3)

        side_column = QtWidgets.QVBoxLayout()
        side_column.setSpacing(GAP)

        status_card, status_layout = section_card("Status")
        self.status_values: dict[str, QtWidgets.QLabel] = {}
        for name in ("Provider", "Shortcut", "History", "Version"):
            group = QtWidgets.QVBoxLayout()
            group.setSpacing(1)
            label = QtWidgets.QLabel(name)
            label.setObjectName("Meta")
            group.addWidget(label)
            value = QtWidgets.QLabel("")
            value.setObjectName("body")
            value.setWordWrap(True)
            value.setAlignment(
                QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
            )
            group.addWidget(value)
            self.status_values[name] = value
            status_layout.addLayout(group)
        side_column.addWidget(status_card)

        actions_card, actions_layout = section_card("App controls")
        self.settings_button = self._action_button("Settings")
        self.settings_button.clicked.connect(lambda: self.app.show_settings())
        actions_layout.addWidget(self.settings_button)

        self.pause_button = self._action_button("Pause")
        self.pause_button.clicked.connect(self._toggle_pause)
        actions_layout.addWidget(self.pause_button)

        self.about_button = self._action_button("About")
        self.about_button.clicked.connect(lambda: self.app.show_about())
        actions_layout.addWidget(self.about_button)

        self.exit_button = self._action_button("Exit Writing Tools", danger=True)
        self.exit_button.clicked.connect(lambda: self.app.exit_app())
        actions_layout.addWidget(self.exit_button)
        side_column.addWidget(actions_card)
        side_column.addStretch(1)
        body.addLayout(side_column, 2)
        layout.addLayout(body, 1)

        self.hint_label = QtWidgets.QLabel("")
        self.hint_label.setObjectName("Hint")
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)

        self.refresh()

    def refresh(self) -> None:
        config = self.app.config or {}
        paused = bool(getattr(self.app, "paused", False))
        self.state_chip.setText("Paused" if paused else "Running")
        self.state_chip.setStyleSheet(self._chip_style(paused))
        self.pause_button.setText("Resume" if paused else "Pause")
        self.pause_button.setAccessibleName("Resume" if paused else "Pause")

        shortcut = (config.get("shortcut") or "ctrl+space").strip()
        self.hint_label.setText(
            "Close this window to keep Writing Tools running in the tray."
        )

        provider = getattr(self.app, "current_provider", None)
        provider_name = (
            getattr(provider, "provider_name", None)
            or config.get("provider")
            or "Not set up"
        )
        self.status_values["Provider"].setText(provider_name)
        self.status_values["Shortcut"].setText(shortcut)
        self.status_values["Version"].setText(
            f"Version {self._version()}"
        )

        if self.store is None:
            self.status_values["History"].setText("Unavailable")
        else:
            self.status_values["History"].setText(
                "On, stored locally"
                if getattr(self.app, "history_enabled", True)
                else "Off"
            )

        self._refresh_recent()

    def _refresh_recent(self) -> None:
        while self.recent_layout.count():
            item = self.recent_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        if self.store is None:
            self.count_label.setText("History is unavailable.")
            self.history_button.setEnabled(False)
            self.recent_layout.addWidget(self._empty_label("History could not be opened."))
            return

        self.history_button.setEnabled(True)
        try:
            entries = self.store.entries(limit=RECENT_LIMIT)
            total = self.store.count()
        except Exception:
            self.count_label.setText("History is unavailable.")
            self.history_button.setEnabled(False)
            self.recent_layout.addWidget(self._empty_label("History could not be opened."))
            return

        if not entries:
            if not getattr(self.app, "history_enabled", True):
                self.count_label.setText("History is off")
                message = (
                    "History is off, so new rewrites are not saved. "
                    "Turn on Save rewrites to history."
                )
            else:
                self.count_label.setText("No rewrites yet")
                message = (
                    "Your next rewrite will appear here. Select text in any app "
                    "and press the shortcut."
                )
            self.recent_layout.addWidget(self._empty_label(message))
            return

        plural = "" if total == 1 else "s"
        self.count_label.setText(f"{total} saved rewrite{plural}")
        for entry in entries:
            row = RecentRow(entry, self._palette)
            row.clicked.connect(self._open_entry)
            self.recent_layout.addWidget(row)
        self.recent_layout.addStretch(1)

    def _action_button(self, text: str, danger: bool = False) -> QtWidgets.QPushButton:
        palette = self._palette
        button = QtWidgets.QPushButton(text)
        button.setObjectName("actionRow")
        button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        button.setMinimumHeight(34)
        color = palette.delete_fg if danger else palette.ink
        hover = palette.delete_bg if danger else palette.surface_alt
        button.setStyleSheet(
            f"""
            QPushButton#actionRow {{
                text-align: left;
                padding: 8px 10px;
                border: 1px solid {palette.hairline};
                border-radius: 8px;
                background: transparent;
                color: {color};
                font-size: 13px;
            }}
            QPushButton#actionRow:hover {{ background: {hover}; }}
            QPushButton#actionRow:focus {{ border: 2px solid {palette.accent}; }}
            """
        )
        button.setAccessibleName(text)
        return button

    def _empty_label(self, text: str) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(text)
        label.setObjectName("Meta")
        label.setWordWrap(True)
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        return label

    def _chip_style(self, paused: bool) -> str:
        p = self._palette
        if paused:
            return (
                f"background: {p.surface_alt}; color: {p.muted};"
                "border-radius: 10px; padding: 3px 10px;"
                "font-size: 11px; font-weight: 600;"
            )
        return (
            f"background: {p.accent_soft}; color: {p.accent};"
            "border-radius: 10px; padding: 3px 10px;"
            "font-size: 11px; font-weight: 600;"
        )

    @staticmethod
    def _version() -> str:
        try:
            from update_checker import CURRENT_VERSION

            return str(CURRENT_VERSION)
        except Exception:
            return "unknown"

    def _toggle_pause(self) -> None:
        self.app.toggle_paused()
        self.refresh()

    def _open_history(self) -> None:
        if self.store is None:
            return
        self.app.show_history()

    def _open_entry(self, entry_id: int) -> None:
        if self.store is None:
            return
        self.app.show_history()
        window = getattr(self.app, "history_window", None)
        if window is not None and hasattr(window, "show_entry"):
            window.show_entry(entry_id)

    def show_window(self) -> None:
        if not self._placed:
            screen = QtGui.QGuiApplication.primaryScreen()
            if screen is not None:
                frame = self.frameGeometry()
                frame.moveCenter(screen.availableGeometry().center())
                self.move(frame.topLeft())
            self._placed = True
        self.refresh()
        self.show()
        self.raise_()
        self.activateWindow()
