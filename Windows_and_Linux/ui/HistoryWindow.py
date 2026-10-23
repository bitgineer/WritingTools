"""Rewrite history window.

A searchable list of past reworks with a side-by-side comparison. The
window owns no storage policy. It reads and writes the HistoryStore passed
by the app and only changes the `history_enabled` key in the config dict.
"""

from __future__ import annotations

import gettext
import logging
import os
import sys
from datetime import datetime, timezone

from PySide6 import QtCore, QtGui, QtWidgets

from rework.history import HistoryEntry, HistoryStore
from rework.theme import Palette, current_palette, history_stylesheet

_ = gettext.gettext


class HistoryWindow(QtWidgets.QWidget):
    def __init__(
        self,
        store: HistoryStore,
        config: dict,
        on_config_change=None,
        palette: Palette | None = None,
        on_entries_change=None,
    ):
        super().__init__(None)
        self.store = store
        self.config = config
        self._on_config_change = on_config_change
        self._on_entries_change = on_entries_change
        self._palette = palette or current_palette()
        self._selected_id: int | None = None
        self._placed = False

        self.setWindowTitle(_("Rewrite History"))
        self.setMinimumSize(780, 520)
        self.resize(940, 620)
        self.setStyleSheet(history_stylesheet(self._palette))

        qt_palette = self.palette()
        qt_palette.setColor(
            QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(self._palette.accent)
        )
        qt_palette.setColor(
            QtGui.QPalette.ColorRole.HighlightedText,
            QtGui.QColor(self._palette.accent_text),
        )
        self.setPalette(qt_palette)

        icon_path = os.path.join(os.path.dirname(sys.argv[0]), "icons", "app_icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QtGui.QIcon(icon_path))

        self._build()
        self.refresh()

    def _build(self) -> None:
        root = QtWidgets.QWidget()
        root.setObjectName("historyRoot")
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(root)

        layout = QtWidgets.QVBoxLayout(root)
        layout.setContentsMargins(24, 22, 24, 18)
        layout.setSpacing(12)

        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel(_("Rewrite History"))
        title.setObjectName("historyTitle")
        header.addWidget(title)
        header.addSpacing(10)

        self.count_label = QtWidgets.QLabel("")
        self.count_label.setObjectName("historyCount")
        header.addWidget(self.count_label)
        header.addStretch()
        layout.addLayout(header)

        controls = QtWidgets.QHBoxLayout()
        self.search = QtWidgets.QLineEdit()
        self.search.setObjectName("historySearch")
        self.search.setPlaceholderText(_("Search rewrites"))
        self.search.setClearButtonEnabled(True)
        self.search.setMaximumWidth(360)
        self.search.textChanged.connect(self._start_search_timer)
        controls.addWidget(self.search)
        controls.addStretch()

        self.toggle = QtWidgets.QPushButton(_("Save rewrites to history"))
        self.toggle.setObjectName("historyToggle")
        self.toggle.setCheckable(True)
        self.toggle.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.toggle.setAccessibleName(_("Save rewrites to history"))
        self.toggle.setChecked(bool(self.config.get("history_enabled", True)))
        self.toggle.toggled.connect(self._toggle_history)
        controls.addWidget(self.toggle)
        layout.addLayout(controls)

        self.toggle_note = QtWidgets.QLabel("")
        self.toggle_note.setObjectName("historyMeta")
        self.toggle_note.setWordWrap(True)
        layout.addWidget(self.toggle_note)
        self._update_toggle_note()

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(1)

        list_panel = QtWidgets.QFrame()
        list_panel.setObjectName("historyPanel")
        list_layout = QtWidgets.QVBoxLayout(list_panel)
        list_layout.setContentsMargins(8, 8, 8, 8)
        self.list = QtWidgets.QListWidget()
        self.list.setObjectName("historyList")
        self.list.setWordWrap(True)
        self.list.setSpacing(2)
        self.list.currentItemChanged.connect(self._show_entry)
        self.list.setAccessibleName(_("Saved rewrites"))
        list_layout.addWidget(self.list)
        splitter.addWidget(list_panel)

        detail_panel = QtWidgets.QFrame()
        detail_panel.setObjectName("historyPanel")
        detail_layout = QtWidgets.QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(16, 14, 16, 14)
        detail_layout.setSpacing(10)

        self.meta = QtWidgets.QLabel("")
        self.meta.setObjectName("historyMeta")
        self.meta.setWordWrap(True)
        detail_layout.addWidget(self.meta)

        detail_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        detail_splitter.setChildrenCollapsible(False)
        detail_splitter.setHandleWidth(1)
        original_panel, self.original_view = self._text_panel(_("Original"))
        reworked_panel, self.reworked_view = self._text_panel(_("Revised"))
        detail_splitter.addWidget(original_panel)
        detail_splitter.addWidget(reworked_panel)
        detail_splitter.setSizes([300, 300])
        detail_layout.addWidget(detail_splitter, 1)

        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(8)
        self.copy_original = QtWidgets.QPushButton(_("Copy original"))
        self.copy_original.setObjectName("ghost")
        self.copy_original.clicked.connect(
            lambda: self._copy(self.copy_original, self._current_text("original"))
        )
        actions.addWidget(self.copy_original)

        self.copy_reworked = QtWidgets.QPushButton(_("Copy revised"))
        self.copy_reworked.setObjectName("ghost")
        self.copy_reworked.clicked.connect(
            lambda: self._copy(self.copy_reworked, self._current_text("revised"))
        )
        actions.addWidget(self.copy_reworked)
        actions.addStretch()

        self.delete_button = QtWidgets.QPushButton(_("Delete"))
        self.delete_button.setObjectName("danger")
        self.delete_button.clicked.connect(self._delete_current)
        actions.addWidget(self.delete_button)
        detail_layout.addLayout(actions)

        splitter.addWidget(detail_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 600])
        layout.addWidget(splitter, 1)

        footer = QtWidgets.QHBoxLayout()
        limit = getattr(self.store, "limit", 0)
        privacy_text = _(
            "History stays on this device. When you run an action, the selected text is sent to your AI provider."
        )
        if limit:
            privacy_text = _(
                "Stored locally on this device. Nothing is uploaded. Keeps the newest {limit} rewrites."
            ).format(limit=limit)
        privacy = QtWidgets.QLabel(privacy_text)
        privacy.setObjectName("historyPrivacy")
        footer.addWidget(privacy)
        footer.addStretch()

        self.clear_button = QtWidgets.QPushButton(_("Clear all"))
        self.clear_button.setObjectName("danger")
        self.clear_button.clicked.connect(self._clear_all)
        footer.addWidget(self.clear_button)
        layout.addLayout(footer)

        self._search_timer = QtCore.QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(150)
        self._search_timer.timeout.connect(self.refresh)

    def _text_panel(self, title: str):
        panel = QtWidgets.QFrame()
        panel.setObjectName("historyTextPanel")
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        label = QtWidgets.QLabel(title.upper())
        label.setObjectName("historySection")
        layout.addWidget(label)

        view = QtWidgets.QTextBrowser()
        view.setObjectName("historyText")
        view.setReadOnly(True)
        view.setOpenExternalLinks(False)
        view.setAccessibleName(title)
        layout.addWidget(view, 1)
        return panel, view

    def _start_search_timer(self) -> None:
        self._search_timer.start()

    def refresh(self) -> None:
        query = self.search.text().strip()
        entries = self.store.entries(query, limit=self.store.limit or 1000)
        total = self.store.count()

        if query:
            self.count_label.setText(f"{len(entries)} of {total} rewrites")
        else:
            self.count_label.setText(f"{total} rewrite{'s' if total != 1 else ''}")

        selected = self._selected_id
        self.list.blockSignals(True)
        self.list.clear()
        for entry in entries:
            item = QtWidgets.QListWidgetItem(self._item_text(entry))
            item.setData(QtCore.Qt.ItemDataRole.UserRole, entry.id)
            item.setToolTip(self._snippet(entry.original, 220))
            item.setSizeHint(QtCore.QSize(0, 54))
            self.list.addItem(item)
        self.list.blockSignals(False)

        target = None
        for index in range(self.list.count()):
            item = self.list.item(index)
            if item.data(QtCore.Qt.ItemDataRole.UserRole) == selected:
                target = item
                break
        if target is None and self.list.count():
            target = self.list.item(0)

        if target is not None:
            self.list.setCurrentItem(target)
            self._show_entry(target)
        else:
            self._selected_id = None
            message = (
                _("No rewrites match that search.")
                if query
                else _("No rewrites yet. Your next rework will appear here.")
            )
            self._clear_detail(message)

        self.clear_button.setEnabled(total > 0)

    def _item_text(self, entry: HistoryEntry) -> str:
        return f"{entry.option}  ·  {self._format_time(entry.created_at)}\n{self._snippet(entry.original)}"

    @staticmethod
    def _snippet(text: str, width: int = 96) -> str:
        text = " ".join(text.split())
        if len(text) <= width:
            return text
        return text[: width - 1].rstrip() + "\u2026"

    @staticmethod
    def _format_time(value: str) -> str:
        try:
            moment = datetime.fromisoformat(value)
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=timezone.utc)
            return moment.astimezone().strftime("%b %d, %Y at %I:%M %p")
        except ValueError:
            return value

    @staticmethod
    def _headline(entry: HistoryEntry) -> str:
        if entry.changed_words:
            return f"{entry.changed_words} word{'s' if entry.changed_words != 1 else ''} changed"
        return _("Punctuation and spacing updated")

    def _show_entry(self, current, previous=None) -> None:
        if current is None:
            self._clear_detail(
                _("No rewrites yet. Your next rework will appear here.")
            )
            return

        entry_id = current.data(QtCore.Qt.ItemDataRole.UserRole)
        entry = self.store.get(int(entry_id))
        if entry is None:
            self._clear_detail(_("That rewrite is no longer saved."))
            return

        self._selected_id = entry.id
        self.meta.setText(
            f"{entry.option}  ·  {self._headline(entry)}  ·  {self._format_time(entry.created_at)}"
        )
        self.original_view.setPlainText(entry.original)
        self.reworked_view.setPlainText(entry.revised)
        self.copy_original.setEnabled(True)
        self.copy_reworked.setEnabled(True)
        self.delete_button.setEnabled(True)

    def _clear_detail(self, message: str) -> None:
        self.meta.setText(message)
        self.original_view.clear()
        self.reworked_view.clear()
        self.copy_original.setEnabled(False)
        self.copy_reworked.setEnabled(False)
        self.delete_button.setEnabled(False)

    def _current_text(self, field: str) -> str:
        item = self.list.currentItem()
        if item is None:
            return ""
        entry = self.store.get(int(item.data(QtCore.Qt.ItemDataRole.UserRole)))
        return getattr(entry, field) if entry else ""

    def _copy(self, button: QtWidgets.QPushButton, text: str) -> None:
        if not text:
            return
        QtWidgets.QApplication.clipboard().setText(text)
        original = button.text()
        button.setText(_("Copied"))
        timer = QtCore.QTimer(button)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: button.setText(original))
        timer.start(1200)

    def _delete_current(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        entry_id = int(item.data(QtCore.Qt.ItemDataRole.UserRole))
        answer = QtWidgets.QMessageBox.question(
            self,
            _("Delete rewrite"),
            _("Delete this rewrite from history? This cannot be undone."),
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self.store.delete(entry_id)
        self._selected_id = None
        self.refresh()
        self._entries_changed()

    def _clear_all(self) -> None:
        if self.store.count() == 0:
            return
        answer = QtWidgets.QMessageBox.question(
            self,
            _("Clear rewrite history"),
            _("Delete every saved rewrite? This cannot be undone."),
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self.store.clear()
        self._selected_id = None
        self.refresh()
        self._entries_changed()

    def _toggle_history(self, enabled: bool) -> None:
        self.config["history_enabled"] = enabled
        if self._on_config_change is not None:
            try:
                self._on_config_change(self.config)
            except Exception:
                logging.exception("Could not save the history setting")
        self._update_toggle_note()

    def _update_toggle_note(self) -> None:
        enabled = self.config.get("history_enabled", True)
        label = _("Save rewrites to history")
        self.toggle.setText(("\u2713  " + label) if enabled else label)
        limit = getattr(self.store, "limit", 0)
        if enabled:
            text = _(
                "New rewrites are saved on this device. The newest {limit} are kept."
            ).format(limit=limit or 500)
        else:
            text = _(
                "History is off. Existing rewrites stay until you clear them."
            )
        self.toggle_note.setText(text)

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

    def show_entry(self, entry_id: int) -> None:
        """Open the window with one rewrite already selected.

        A search saved from an earlier visit could hide that rewrite. The
        dashboard asked for this exact entry, so clear the filter first.
        """
        self._search_timer.stop()
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self._selected_id = int(entry_id)
        self.show_window()

    def _entries_changed(self) -> None:
        if self._on_entries_change is not None:
            try:
                self._on_entries_change()
            except Exception:
                logging.exception("Could not refresh the dashboard after a history change")
