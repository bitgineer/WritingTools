"""Home: status, recent rewrites, quick actions, and first-run setup."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from rework.history import HistoryEntry
from rework.theme import current_palette
from ui.Components import ElidedLabel, EmptyState, Metric, scroll_page
from ui.SetupWizard import SetupWizard
from ui.design import GAP, ghost_button, section_card
from ui.formatting import format_age, headline, snippet

RECENT_LIMIT = 5


class RecentRow(QtWidgets.QPushButton):
    def __init__(self, entry: HistoryEntry, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.setObjectName("RowCard")
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(
            f"{entry.option}, {headline(entry.changed_words)}, {format_age(entry.created_at)}"
        )
        self.setToolTip("Open this rewrite in Rewrites")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(3)

        top = QtWidgets.QHBoxLayout()
        top.setSpacing(8)
        title = QtWidgets.QLabel(entry.option)
        title.setObjectName("SectionTitle")
        title.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        top.addWidget(title)
        top.addStretch(1)
        age = QtWidgets.QLabel(format_age(entry.created_at))
        age.setObjectName("MetricLabel")
        age.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        top.addWidget(age)
        layout.addLayout(top)

        detail = ElidedLabel(f"{headline(entry.changed_words)}  \u00b7  {snippet(entry.original, 80)}")
        detail.setObjectName("Meta")
        detail.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(detail)

    def sizeHint(self) -> QtCore.QSize:
        hint = super().sizeHint()
        return QtCore.QSize(hint.width(), max(52, hint.height()))


class HomeView(QtWidgets.QWidget):
    open_entry = QtCore.Signal(int)
    open_actions = QtCore.Signal()
    open_settings = QtCore.Signal()
    setup_ready = QtCore.Signal()
    setup_finished = QtCore.Signal()

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self._palette = current_palette()
        self._show_setup = not self._has_provider()
        self._build()
        self.refresh()

    def _has_provider(self) -> bool:
        return getattr(self.app, "current_provider", None) is not None

    def _build(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.scroll, self.content = scroll_page()
        layout.addWidget(self.scroll)

        self.setup_host = QtWidgets.QWidget()
        self.setup_layout = QtWidgets.QVBoxLayout(self.setup_host)
        self.setup_layout.setContentsMargins(0, 0, 0, 0)
        self.content.addWidget(self.setup_host)

        self.main_host = QtWidgets.QWidget()
        main = QtWidgets.QVBoxLayout(self.main_host)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(GAP)
        self.content.addWidget(self.main_host)

        hero = QtWidgets.QFrame()
        hero.setObjectName("BannerInfo")
        hero_layout = QtWidgets.QHBoxLayout(hero)
        hero_layout.setContentsMargins(20, 16, 20, 16)
        hero_layout.setSpacing(GAP)
        hero_text = QtWidgets.QVBoxLayout()
        hero_text.setSpacing(3)
        self.hero_title = QtWidgets.QLabel("Ready when you are")
        self.hero_title.setObjectName("SectionTitle")
        hero_text.addWidget(self.hero_title)
        self.hero_body = QtWidgets.QLabel("")
        self.hero_body.setObjectName("Meta")
        self.hero_body.setWordWrap(True)
        hero_text.addWidget(self.hero_body)
        hero_layout.addLayout(hero_text, 1)
        self.hero_action = QtWidgets.QPushButton("Open Rewrites")
        self.hero_action.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.hero_action.setMinimumHeight(30)
        self.hero_action.setAccessibleName("Open Rewrites")
        self.hero_action.clicked.connect(self._open_rewrites)
        hero_layout.addWidget(self.hero_action)
        main.addWidget(hero)

        status_card, status_layout = section_card("Status")
        metrics = QtWidgets.QHBoxLayout()
        metrics.setSpacing(24)
        self.metrics = {
            "Provider": Metric("Provider"),
            "Shortcut": Metric("Shortcut"),
            "History": Metric("History"),
            "Startup": Metric("Startup"),
        }
        for metric in self.metrics.values():
            metrics.addWidget(metric, 1)
        status_layout.addLayout(metrics)
        main.addWidget(status_card)

        columns = QtWidgets.QHBoxLayout()
        columns.setSpacing(GAP)

        recent_card, recent_layout = section_card(
            "Recent rewrites", "The last five changes. Open one to read the diff."
        )
        recent_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.recent_host = QtWidgets.QWidget()
        self.recent_layout = QtWidgets.QVBoxLayout(self.recent_host)
        self.recent_layout.setContentsMargins(0, 0, 0, 0)
        self.recent_layout.setSpacing(6)
        recent_layout.addWidget(self.recent_host)
        self.recent_footer = QtWidgets.QLabel("")
        self.recent_footer.setObjectName("MetricLabel")
        recent_layout.addWidget(self.recent_footer)
        columns.addWidget(recent_card, 3)

        side = QtWidgets.QVBoxLayout()
        side.setSpacing(GAP)
        actions_card, actions_layout = section_card("Actions")
        self.actions_host = QtWidgets.QWidget()
        self.actions_layout = QtWidgets.QVBoxLayout(self.actions_host)
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(2)
        actions_layout.addWidget(self.actions_host)
        edit = ghost_button("Edit actions")
        edit.clicked.connect(self.open_actions.emit)
        actions_layout.addWidget(edit, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        side.addWidget(actions_card)

        tip_card, tip_layout = section_card("Keyboard")
        for text in (
            "Ctrl+Space opens the popup.",
            "In the popup, Ctrl+1 to 9 run an action.",
            "Here, Ctrl+1 to 5 switch views.",
            "Ctrl+K runs a command.",
            "Ctrl+H opens Rewrites.",
        ):
            label = QtWidgets.QLabel(text)
            label.setObjectName("Meta")
            label.setWordWrap(True)
            tip_layout.addWidget(label)
        side.addWidget(tip_card)
        side.addStretch(1)
        columns.addLayout(side, 2)
        main.addLayout(columns)
        main.addStretch(1)

    def _clear_setup(self) -> None:
        while self.setup_layout.count():
            item = self.setup_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def refresh(self) -> None:
        if not self._has_provider():
            self._show_setup_mode()
            return
        self._show_main_mode()
        self._refresh_chrome()
        self._refresh_recent()
        self._refresh_actions()

    def _show_setup_mode(self) -> None:
        self.main_host.hide()
        self.setup_host.show()
        if getattr(self, "_wizard", None) is not None:
            return
        self._clear_setup()
        self._wizard = SetupWizard(self.app)
        self._wizard.finished.connect(self._finish_setup)
        self._wizard.ready.connect(self._setup_ready)
        self.setup_layout.addWidget(self._wizard)

    def _setup_ready(self) -> None:
        self.setup_ready.emit()

    def _finish_setup(self) -> None:
        self._wizard = None
        self._clear_setup()
        self.refresh()
        self.setup_finished.emit()

    def _show_main_mode(self) -> None:
        self.setup_host.hide()
        self.main_host.show()
        if getattr(self, "_wizard", None) is not None:
            self._wizard = None
            self._clear_setup()

    def _refresh_chrome(self) -> None:
        config = self.app.config or {}
        shortcut = (config.get("shortcut") or "ctrl+space").strip()
        provider = getattr(self.app, "current_provider", None)
        provider_name = getattr(provider, "provider_name", None) or "Not set up"
        history_on = bool(getattr(self.app, "history_enabled", True))
        startup = "On" if _autostart_enabled() else "Off"
        self.metrics["Provider"].set_value(provider_name)
        self.metrics["Shortcut"].set_value(shortcut)
        self.metrics["History"].set_value("On, local" if history_on else "Off")
        self.metrics["Startup"].set_value(startup)
        self.hero_body.setText(
            f"Select text in any app and press {shortcut}. "
            "The rewrite lands in place, and the receipt shows what changed."
        )

    def _refresh_recent(self) -> None:
        while self.recent_layout.count():
            item = self.recent_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        store = getattr(self.app, "history_store", None)
        if store is None:
            self.recent_footer.setText("History is unavailable.")
            self.recent_layout.addWidget(
                EmptyState(
                    "History is unavailable",
                    "The local database could not be opened. Try again, or open Settings.",
                    "Try again",
                    self.refresh,
                )
            )
            return
        if not getattr(self.app, "history_enabled", True):
            self.recent_footer.setText("History is off.")
            self.recent_layout.addWidget(
                EmptyState(
                    "History is off",
                    "New rewrites are not saved. Turn on Save rewrites to history in Settings.",
                    "Open Settings",
                    lambda: self.open_settings.emit(),
                )
            )
            return
        try:
            entries = store.entries(limit=RECENT_LIMIT)
            total = store.count()
        except Exception:
            self.recent_footer.setText("History is unavailable.")
            self.recent_layout.addWidget(
                EmptyState(
                    "History is unavailable",
                    "The local database could not be read. Try again, or open Settings.",
                    "Try again",
                    self.refresh,
                )
            )
            return
        if not entries:
            self.recent_footer.setText("No rewrites yet.")
            self.recent_layout.addWidget(
                EmptyState(
                    "No rewrites yet",
                    "Your next rewrite will appear here. Select text in any app and press the shortcut.",
                )
            )
            return
        self.recent_footer.setText(
            f"{total} saved rewrite{'s' if total != 1 else ''}."
        )
        for entry in entries:
            row = RecentRow(entry)
            row.clicked.connect(lambda _=False, entry_id=entry.id: self.open_entry.emit(entry_id))
            self.recent_layout.addWidget(row)

    def _refresh_actions(self) -> None:
        while self.actions_layout.count():
            item = self.actions_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        try:
            from ui.ActionStore import load, actions
            entries = actions(load())
        except Exception:
            entries = []
        if not entries:
            label = QtWidgets.QLabel("No actions yet. Add one in Actions.")
            label.setObjectName("Meta")
            self.actions_layout.addWidget(label)
            return
        for name, entry in entries:
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(8)
            label = QtWidgets.QLabel(name)
            label.setObjectName("Meta")
            row.addWidget(label)
            row.addStretch(1)
            hotkey = (entry.get("hotkey") or "").strip()
            if hotkey:
                hint = QtWidgets.QLabel(hotkey)
                hint.setObjectName("FieldHint")
                row.addWidget(hint)
            self.actions_layout.addLayout(row)

    def _open_rewrites(self) -> None:
        self.open_entry.emit(-1)

    def focus_first(self) -> None:
        wizard = getattr(self, "_wizard", None)
        if wizard is not None:
            wizard.focus_first()
            return
        self.hero_action.setFocus()


def _autostart_enabled() -> bool:
    try:
        from ui.AutostartManager import AutostartManager

        return bool(AutostartManager.check_autostart())
    except Exception:
        return False
