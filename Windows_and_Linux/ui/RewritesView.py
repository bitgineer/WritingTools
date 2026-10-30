"""Rewrites: search, read, compare, copy, and remove local rewrites."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from rework.diff_view import DiffView
from rework.full_text_view import FullTextView
from rework.model import Rework
from rework.theme import current_palette
from ui.Components import EmptyState, scroll_page
from ui.design import GAP, field_label, ghost_button, primary_button, section_card
from ui.formatting import format_time, headline, snippet

PAGE_SIZE = 200


class RewritesView(QtWidgets.QWidget):
    def __init__(self, app, store=None, parent=None):
        super().__init__(parent)
        self.app = app
        self.store = store if store is not None else getattr(app, "history_store", None)
        self._palette = current_palette()
        self._selected_id: int | None = None
        self._entries = []
        self._build()
        self.refresh()

    def _build(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.scroll, self.content = scroll_page()
        layout.addWidget(self.scroll)

        toolbar_card, toolbar = section_card()
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(field_label("Search"), 0)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search actions, originals, and revisions")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Search rewrites")
        self.search.setMinimumWidth(260)
        self.search.textChanged.connect(self.refresh)
        row.addWidget(self.search, 1)

        row.addWidget(field_label("Action"), 0)
        self.filter = QtWidgets.QComboBox()
        self.filter.setAccessibleName("Filter by action")
        self.filter.setMinimumWidth(160)
        self.filter.currentIndexChanged.connect(self.refresh)
        row.addWidget(self.filter)

        self.count = QtWidgets.QLabel("")
        self.count.setObjectName("MetricLabel")
        row.addWidget(self.count)
        toolbar.addLayout(row)
        self.content.addWidget(toolbar_card)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(1)
        self.splitter = splitter

        list_panel = QtWidgets.QFrame()
        list_panel.setObjectName("ListPanel")
        list_layout = QtWidgets.QVBoxLayout(list_panel)
        list_layout.setContentsMargins(8, 8, 8, 8)
        list_layout.setSpacing(8)
        self.list = QtWidgets.QListWidget()
        self.list.setObjectName("RewritesList")
        self.list.setWordWrap(False)
        self.list.setSpacing(2)
        self.list.setAccessibleName("Saved rewrites")
        self.list.currentItemChanged.connect(self._show_current)
        list_layout.addWidget(self.list, 1)

        privacy = QtWidgets.QHBoxLayout()
        privacy.setSpacing(6)
        self.history_toggle = QtWidgets.QCheckBox("Save rewrites to history")
        self.history_toggle.setAccessibleName("Save rewrites to history")
        self.history_toggle.setChecked(bool(getattr(self.app, "history_enabled", True)))
        self.history_toggle.toggled.connect(self._toggle_history)
        privacy.addWidget(self.history_toggle)
        privacy.addStretch(1)
        self.clear_button = ghost_button("Clear all")
        self.clear_button.setObjectName("danger")
        self.clear_button.clicked.connect(self._clear_all)
        privacy.addWidget(self.clear_button)
        list_layout.addLayout(privacy)
        splitter.addWidget(list_panel)

        detail_panel = QtWidgets.QFrame()
        detail_panel.setObjectName("ListPanel")
        detail_layout = QtWidgets.QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(16, 14, 16, 14)
        detail_layout.setSpacing(10)

        self.meta = QtWidgets.QLabel("")
        self.meta.setObjectName("MetricLabel")
        self.meta.setWordWrap(True)
        detail_layout.addWidget(self.meta)

        self.mode_row = QtWidgets.QHBoxLayout()
        self.mode_row.setSpacing(6)
        self.changes_button = QtWidgets.QPushButton("Changes")
        self.changes_button.setObjectName("segment")
        self.changes_button.setCheckable(True)
        self.changes_button.setChecked(True)
        self.changes_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.side_button = QtWidgets.QPushButton("Side by side")
        self.side_button.setObjectName("segment")
        self.side_button.setCheckable(True)
        self.side_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        group = QtWidgets.QButtonGroup(self)
        group.setExclusive(True)
        group.addButton(self.changes_button)
        group.addButton(self.side_button)
        self.changes_button.clicked.connect(lambda: self._set_mode("changes"))
        self.side_button.clicked.connect(lambda: self._set_mode("side"))
        self.mode_row.addWidget(self.changes_button)
        self.mode_row.addWidget(self.side_button)
        self.mode_row.addStretch(1)
        detail_layout.addLayout(self.mode_row)

        self.stack = QtWidgets.QStackedWidget()
        self.diff_host = QtWidgets.QWidget()
        self.diff_layout = QtWidgets.QVBoxLayout(self.diff_host)
        self.diff_layout.setContentsMargins(0, 0, 0, 0)
        self.stack.addWidget(self.diff_host)

        self.side_host = QtWidgets.QWidget()
        side_layout = QtWidgets.QHBoxLayout(self.side_host)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(8)
        original_panel = QtWidgets.QVBoxLayout()
        original_panel.setSpacing(3)
        original_label = QtWidgets.QLabel("Original")
        original_label.setObjectName("MetricLabel")
        original_panel.addWidget(original_label)
        self.original_view = QtWidgets.QTextBrowser()
        self.original_view.setObjectName("PlainText")
        self.original_view.setAccessibleName("Original text")
        original_panel.addWidget(self.original_view, 1)
        revised_panel = QtWidgets.QVBoxLayout()
        revised_panel.setSpacing(3)
        revised_label = QtWidgets.QLabel("Revised")
        revised_label.setObjectName("MetricLabel")
        revised_panel.addWidget(revised_label)
        self.revised_view = QtWidgets.QTextBrowser()
        self.revised_view.setObjectName("PlainText")
        self.revised_view.setAccessibleName("Revised text")
        revised_panel.addWidget(self.revised_view, 1)
        side_layout.addLayout(original_panel, 1)
        side_layout.addLayout(revised_panel, 1)
        self.stack.addWidget(self.side_host)
        detail_layout.addWidget(self.stack, 1)

        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(8)
        self.copy_revised = primary_button("Copy revised")
        self.copy_revised.clicked.connect(lambda: self._copy("revised", self.copy_revised))
        actions.addWidget(self.copy_revised)
        self.copy_original = ghost_button("Copy original")
        self.copy_original.clicked.connect(lambda: self._copy("original", self.copy_original))
        actions.addWidget(self.copy_original)
        actions.addStretch(1)
        self.delete_button = ghost_button("Delete")
        self.delete_button.setObjectName("danger")
        self.delete_button.clicked.connect(self._delete_current)
        actions.addWidget(self.delete_button)
        detail_layout.addLayout(actions)

        splitter.addWidget(detail_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 620])
        self.content.addWidget(splitter, 1)

        self.empty = EmptyState(
            "No rewrites yet",
            "Select text in any app and press your shortcut. Every applied rewrite lands here.",
        )
        self.content.addWidget(self.empty, 1)

    def _set_mode(self, mode: str) -> None:
        self.stack.setCurrentIndex(0 if mode == "changes" else 1)

    def _clear_filters(self) -> None:
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.filter.blockSignals(True)
        self.filter.setCurrentIndex(0)
        self.filter.blockSignals(False)
        self.refresh()

    def refresh(self) -> None:
        if self.store is None:
            self._show_empty(
                "History is unavailable",
                "The local history database could not be opened.",
                "Try again",
                self.refresh,
            )
            return
        query = self.search.text().strip()
        option = self.filter.currentData() or None
        self._refresh_filter_options()
        try:
            entries = self.store.entries(query, limit=PAGE_SIZE, option=option)
            total = self.store.count()
        except Exception:
            self._show_empty(
                "History is unavailable",
                "The local history database could not be read.",
                "Try again",
                self.refresh,
            )
            return

        current = self._selected_id
        self.list.blockSignals(True)
        self.list.clear()
        self._entries = entries
        for entry in entries:
            item = QtWidgets.QListWidgetItem(
                f"{entry.option}  \u00b7  {format_time(entry.created_at)}\n{snippet(entry.original, 110)}"
            )
            item.setData(QtCore.Qt.ItemDataRole.UserRole, entry.id)
            item.setSizeHint(QtCore.QSize(0, 56))
            self.list.addItem(item)
        self.list.blockSignals(False)

        self.count.setText(
            f"{len(entries)} of {total} rewrites" if query else f"{total} rewrites"
        )
        self.clear_button.setEnabled(total > 0)
        self.history_toggle.blockSignals(True)
        self.history_toggle.setChecked(bool(getattr(self.app, "history_enabled", True)))
        self.history_toggle.blockSignals(False)

        if not entries:
            if query or option:
                self._show_empty(
                    "No matches",
                    "Try a different search or action.",
                    "Clear filters",
                    self._clear_filters,
                )
            elif not getattr(self.app, "history_enabled", True):
                self._show_empty(
                    "History is off",
                    "New rewrites are not saved. Turn on Save rewrites to history in Settings.",
                    "Open Settings",
                    self._open_settings,
                )
            else:
                self._show_empty(
                    "No rewrites yet",
                    "Select text in any app and press your shortcut. Every applied rewrite lands here.",
                )
            return
        self.empty.hide()
        self.splitter.show()
        self.list.show()
        target = None
        for index in range(self.list.count()):
            item = self.list.item(index)
            if item.data(QtCore.Qt.ItemDataRole.UserRole) == current:
                target = item
                break
        if target is None:
            target = self.list.item(0)
        self.list.setCurrentItem(target)
        self._show_current(target)

    def _refresh_filter_options(self) -> None:
        if self.store is None:
            return
        try:
            options = self.store.options()
        except Exception:
            options = []
        current = self.filter.currentData() or ""
        self.filter.blockSignals(True)
        self.filter.clear()
        self.filter.addItem("All actions", "")
        for option in options:
            self.filter.addItem(option, option)
        index = self.filter.findData(current)
        self.filter.setCurrentIndex(max(0, index))
        self.filter.blockSignals(False)

    def _show_empty(
        self,
        title: str,
        body: str,
        action_text: str | None = None,
        on_action=None,
    ) -> None:
        self.empty.set_content(title, body)
        self.empty.set_action(action_text, on_action)
        self.empty.show()
        self.splitter.hide()
        self.copy_revised.setEnabled(False)
        self.copy_original.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.meta.setText("")
        self.stack.hide()

    def _show_current(self, current, previous=None) -> None:
        if current is None or self.store is None:
            return
        entry_id = current.data(QtCore.Qt.ItemDataRole.UserRole)
        entry = self.store.get(int(entry_id))
        if entry is None:
            self._selected_id = None
            return
        self._selected_id = entry.id
        self.empty.hide()
        self.stack.show()
        self.meta.setText(
            f"{entry.option}  \u00b7  {headline(entry.changed_words)}  \u00b7  {format_time(entry.created_at)}"
        )
        while self.diff_layout.count():
            item = self.diff_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        rework = Rework.create(entry.option, entry.original, entry.revised)
        if rework.is_substantial:
            view = FullTextView(rework, self._palette)
        else:
            view = DiffView(rework.diff, self._palette)
        view.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self.diff_layout.addWidget(view)
        self.original_view.setPlainText(entry.original)
        self.revised_view.setPlainText(entry.revised)
        self.copy_revised.setEnabled(True)
        self.copy_original.setEnabled(True)
        self.delete_button.setEnabled(True)

    def _copy(self, field: str, button: QtWidgets.QPushButton) -> None:
        if self._selected_id is None or self.store is None:
            return
        entry = self.store.get(self._selected_id)
        if entry is None:
            return
        QtWidgets.QApplication.clipboard().setText(getattr(entry, field))
        original = button.text()
        button.setText("Copied")
        timer = QtCore.QTimer(button)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: button.setText(original))
        timer.start(1200)

    def _toggle_history(self, enabled: bool) -> None:
        setter = getattr(self.app, "set_history_enabled", None)
        if setter is not None:
            setter(enabled)
        else:
            self.app.history_enabled = enabled
            self.app.config["history_enabled"] = enabled
            self.app.save_config(self.app.config)

    def _delete_current(self) -> None:
        if self._selected_id is None or self.store is None:
            return
        answer = QtWidgets.QMessageBox.question(
            self,
            "Delete rewrite",
            "Delete this rewrite from history? This cannot be undone.",
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self.store.delete(self._selected_id)
        self._selected_id = None
        self.refresh()
        self._entries_changed()

    def _clear_all(self) -> None:
        if self.store is None or self.store.count() == 0:
            return
        answer = QtWidgets.QMessageBox.question(
            self,
            "Clear rewrite history",
            "Delete every saved rewrite? This cannot be undone.",
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

    def _entries_changed(self) -> None:
        callback = getattr(self.app, "history_changed", None)
        if callback is not None:
            callback()

    def _open_settings(self) -> None:
        opener = getattr(self.app, "show_dashboard", None)
        if opener is not None:
            opener("settings")

    def show_entry(self, entry_id: int) -> None:
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.filter.blockSignals(True)
        self.filter.setCurrentIndex(0)
        self.filter.blockSignals(False)
        self._selected_id = int(entry_id)
        self.refresh()
