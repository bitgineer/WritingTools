"""The one app window.

Left rail, content stack, command palette, and a status strip. Every management
surface is a view here. The writing surfaces stay in context and route back
here.
"""

from __future__ import annotations

import webbrowser

from PySide6 import QtCore, QtGui, QtWidgets

from core.workflow import WorkflowState
from rework.theme import current_palette
from ui.AboutView import AboutView
from ui.ActionsView import ActionsView
from ui.Components import CommandPalette, StatusChip, Toast
from ui.HomeView import HomeView
from ui.RewritesView import RewritesView
from ui.SettingsView import SettingsView
from ui.design import GAP, PAGE_MARGIN, ghost_button

VIEWS = ("home", "rewrites", "actions", "settings", "about")
VIEW_TITLES = {
    "home": ("Home", "What happened, what is ready, and what to do next."),
    "rewrites": ("Rewrites", "Every applied rewrite, searchable and local."),
    "actions": ("Actions", "The choices in the popup. Edit one or add your own."),
    "settings": ("Settings", "Shortcut, provider, privacy, and updates."),
    "about": ("About", "Version, credits, and links."),
}


class _NavDelegate(QtWidgets.QStyledItemDelegate):
    """Keep the selected style but drop the native focus rectangle."""

    def paint(self, painter, option, index) -> None:  # noqa: N802 (Qt signature)
        option.state &= ~QtWidgets.QStyle.StateFlag.State_HasFocus
        super().paint(painter, option, index)


class AppShell(QtWidgets.QWidget):
    def __init__(self, app, store=None, palette=None, parent=None):
        super().__init__(parent)
        self.app = app
        self.store = store if store is not None else getattr(app, "history_store", None)
        self._palette = palette or current_palette()
        self._placed = False
        self._current = "home"

        self.setWindowTitle("Writing Tools")
        self.setAccessibleName("Writing Tools")
        self.setMinimumSize(900, 620)
        self.resize(1040, 720)
        icon_path = _icon_path()
        if icon_path:
            self.setWindowIcon(QtGui.QIcon(icon_path))

        self._build()
        self._install_shortcuts()
        self.refresh_chrome()
        self.navigate("home")

        self._run_timer = QtCore.QTimer(self)
        self._run_timer.setInterval(250)
        self._run_timer.timeout.connect(self._refresh_run_chip)
        self._run_timer.start()

    def _build(self) -> None:
        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QtWidgets.QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(224)
        side = QtWidgets.QVBoxLayout(sidebar)
        side.setContentsMargins(0, 20, 0, 16)
        side.setSpacing(10)

        brand = QtWidgets.QWidget()
        brand_layout = QtWidgets.QVBoxLayout(brand)
        brand_layout.setContentsMargins(20, 0, 20, 6)
        brand_layout.setSpacing(1)
        name = QtWidgets.QLabel("Writing Tools")
        name.setObjectName("Brand")
        brand_layout.addWidget(name)
        tagline = QtWidgets.QLabel("Your writing desk")
        tagline.setObjectName("BrandSub")
        brand_layout.addWidget(tagline)
        side.addWidget(brand)

        self.nav = QtWidgets.QListWidget()
        self.nav.setObjectName("NavList")
        self.nav.setAccessibleName("Sections")
        self.nav.setFocusPolicy(QtCore.Qt.FocusPolicy.ClickFocus)
        self.nav.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setItemDelegate(_NavDelegate(self.nav))
        for key, (title, _subtitle) in VIEW_TITLES.items():
            item = QtWidgets.QListWidgetItem(title)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, key)
            item.setSizeHint(QtCore.QSize(0, 38))
            self.nav.addItem(item)
        self.nav.currentRowChanged.connect(self._nav_changed)
        side.addWidget(self.nav, 1)

        footer = QtWidgets.QWidget()
        footer_layout = QtWidgets.QVBoxLayout(footer)
        footer_layout.setContentsMargins(16, 0, 16, 0)
        footer_layout.setSpacing(6)

        self.status_chip = StatusChip(self._palette)
        self.status_chip.clicked.connect(self._toggle_pause)
        footer_layout.addWidget(self.status_chip)

        self.run_label = QtWidgets.QLabel("")
        self.run_label.setObjectName("FieldHint")
        self.run_label.setWordWrap(True)
        footer_layout.addWidget(self.run_label)

        self.provider_label = QtWidgets.QLabel("")
        self.provider_label.setObjectName("FieldHint")
        self.provider_label.setWordWrap(True)
        footer_layout.addWidget(self.provider_label)

        self.shortcut_label = QtWidgets.QLabel("")
        self.shortcut_label.setObjectName("FieldHint")
        footer_layout.addWidget(self.shortcut_label)
        side.addWidget(footer)

        root.addWidget(sidebar)

        content = QtWidgets.QFrame()
        content_layout = QtWidgets.QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        topbar = QtWidgets.QFrame()
        topbar.setObjectName("TopBar")
        topbar_layout = QtWidgets.QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(PAGE_MARGIN, 16, PAGE_MARGIN, 14)
        topbar_layout.setSpacing(GAP)
        title_block = QtWidgets.QVBoxLayout()
        title_block.setSpacing(1)
        self.title_label = QtWidgets.QLabel("")
        self.title_label.setObjectName("PageTitle")
        title_block.addWidget(self.title_label)
        self.subtitle_label = QtWidgets.QLabel("")
        self.subtitle_label.setObjectName("PageSubtitle")
        self.subtitle_label.setWordWrap(True)
        title_block.addWidget(self.subtitle_label)
        topbar_layout.addLayout(title_block, 1)

        self.run_chip = QtWidgets.QFrame()
        self.run_chip.setObjectName("BannerInfo")
        run_layout = QtWidgets.QHBoxLayout(self.run_chip)
        run_layout.setContentsMargins(10, 3, 8, 3)
        run_layout.setSpacing(6)
        self.run_chip_label = QtWidgets.QLabel("")
        self.run_chip_label.setObjectName("MetricLabel")
        run_layout.addWidget(self.run_chip_label)
        cancel = ghost_button("Cancel")
        cancel.setMinimumHeight(24)
        cancel.setAccessibleName("Cancel the current rewrite")
        cancel.clicked.connect(self._cancel_run)
        run_layout.addWidget(cancel)
        self.run_chip.hide()
        topbar_layout.addWidget(self.run_chip, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)

        self.command_button = ghost_button("Search or run a command   Ctrl+K")
        self.command_button.setObjectName("Command")
        self.command_button.setAccessibleName("Search or run a command")
        self.command_button.clicked.connect(self.open_palette)
        topbar_layout.addWidget(self.command_button, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        content_layout.addWidget(topbar)

        self.banner_host = QtWidgets.QWidget()
        self.banner_layout = QtWidgets.QVBoxLayout(self.banner_host)
        self.banner_layout.setContentsMargins(PAGE_MARGIN, 12, PAGE_MARGIN, 0)
        self.banner_layout.setSpacing(0)
        self.banner_host.hide()
        content_layout.addWidget(self.banner_host)

        self.stack = QtWidgets.QStackedWidget()
        content_layout.addWidget(self.stack, 1)
        root.addWidget(content, 1)

        self.home = HomeView(self.app)
        self.home.open_entry.connect(self.open_entry)
        self.home.open_actions.connect(lambda: self.navigate("actions"))
        self.home.open_settings.connect(lambda: self.navigate("settings"))
        self.home.setup_ready.connect(self.refresh_chrome)
        self.home.setup_finished.connect(self._setup_finished)
        self.rewrites = RewritesView(self.app, self.store)
        self.actions = ActionsView(self.app)
        self.actions.changed.connect(self._content_changed)
        self.settings = SettingsView(self.app)
        self.settings.changed.connect(self._content_changed)
        self.about = AboutView()
        self._views = {
            "home": self.home,
            "rewrites": self.rewrites,
            "actions": self.actions,
            "settings": self.settings,
            "about": self.about,
        }
        for view in self._views.values():
            self.stack.addWidget(view)

        self.toast = Toast(self)
        self.command_palette = CommandPalette(self, self._palette)

    def _install_shortcuts(self) -> None:
        self._shortcuts = []
        for index, key in enumerate(VIEWS, start=1):
            shortcut = QtGui.QShortcut(
                QtGui.QKeySequence(f"Ctrl+{index}"), self
            )
            shortcut.activated.connect(lambda name=key: self.navigate(name))
            self._shortcuts.append(shortcut)
        for sequence, callback in (
            ("Ctrl+K", self.open_palette),
            ("Ctrl+H", lambda: self.navigate("rewrites")),
            ("Ctrl+F", self._focus_search),
        ):
            shortcut = QtGui.QShortcut(QtGui.QKeySequence(sequence), self)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)

    def _nav_changed(self, row: int) -> None:
        if row < 0:
            return
        item = self.nav.item(row)
        if item is not None:
            self.navigate(item.data(QtCore.Qt.ItemDataRole.UserRole))

    def navigate(self, name: str) -> None:
        if name not in self._views:
            return
        self._current = name
        self.stack.setCurrentWidget(self._views[name])
        row = VIEWS.index(name)
        if self.nav.currentRow() != row:
            self.nav.blockSignals(True)
            self.nav.setCurrentRow(row)
            self.nav.blockSignals(False)
        title, subtitle = VIEW_TITLES[name]
        self.title_label.setText(title)
        self.subtitle_label.setText(subtitle)
        view = self._views[name]
        if hasattr(view, "refresh"):
            view.refresh()
        self.refresh_chrome()

    def open_entry(self, entry_id: int) -> None:
        self.navigate("rewrites")
        if entry_id is not None and int(entry_id) >= 0:
            self.rewrites.show_entry(int(entry_id))

    def _focus_search(self) -> None:
        self.navigate("rewrites")
        self.rewrites.search.setFocus()
        self.rewrites.search.selectAll()

    def _content_changed(self) -> None:
        self.home.refresh()
        self.rewrites.refresh()
        self.refresh_chrome()

    def _setup_finished(self) -> None:
        self.home.refresh()
        self.refresh_chrome()
        self.navigate("home")

    def refresh(self) -> None:
        view = self._views.get(self._current)
        if view is not None and hasattr(view, "refresh"):
            view.refresh()
        self.refresh_chrome()

    def refresh_chrome(self) -> None:
        config = getattr(self.app, "config", None) or {}
        paused = bool(getattr(self.app, "paused", False))
        active = getattr(self.app, "workflow", None)
        working = active is not None and active.state in (
            WorkflowState.CAPTURING,
            WorkflowState.RUNNING,
        )
        detail = ""
        if working and active.last is not None:
            detail = active.last.option
        provider = getattr(self.app, "current_provider", None)
        if provider is None:
            self.status_chip.set_status(
                "Setup needed",
                "warning",
                "Open provider settings",
                "Setup needed. Open provider settings.",
                detail,
            )
        else:
            self.status_chip.set_state(paused, detail)
        self.provider_label.setText(
            "Provider: " + (getattr(provider, "provider_name", None) or "not set up")
        )
        self.shortcut_label.setText(
            "Shortcut: " + (config.get("shortcut") or "ctrl+space")
        )
        self._refresh_run_chip()
        self._refresh_nav_count()

    def _refresh_nav_count(self) -> None:
        item = self.nav.item(1)
        if item is None:
            return
        try:
            total = self.store.count() if self.store is not None else 0
        except Exception:
            total = 0
        item.setText(f"Rewrites   {total}" if total else "Rewrites")

    def _refresh_run_chip(self) -> None:
        workflow = getattr(self.app, "workflow", None)
        if workflow is None or workflow.state not in (
            WorkflowState.CAPTURING,
            WorkflowState.RUNNING,
        ):
            self.run_chip.hide()
            self.run_label.setText("")
            return
        run = workflow.last
        if run is None:
            self.run_chip.hide()
            return
        self.run_chip.show()
        self.run_chip_label.setText(f"{run.option}  {run.elapsed:.1f}s")
        self.run_label.setText(f"Working on {run.option}")
        self.status_chip.set_state(False, run.option)

    def _toggle_pause(self) -> None:
        if getattr(self.app, "current_provider", None) is None:
            self.navigate("settings")
            return
        callback = getattr(self.app, "toggle_paused", None)
        if callback is not None:
            callback()
        self.refresh_chrome()

    def _cancel_run(self) -> None:
        callback = getattr(self.app, "_cancel_active_request", None)
        if callback is not None:
            callback()
        self.refresh_chrome()

    def open_palette(self) -> None:
        provider_ready = getattr(self.app, "current_provider", None) is not None
        pause_command = (
            (
                "Resume Writing Tools"
                if getattr(self.app, "paused", False)
                else "Pause Writing Tools",
                "pause resume",
                self._toggle_pause,
            )
            if provider_ready
            else ("Finish provider setup", "provider api key", self._palette_provider)
        )
        commands = [
            ("Go to Home", "home start", lambda: self.navigate("home")),
            ("Go to Rewrites", "history rewrites", lambda: self.navigate("rewrites")),
            ("Go to Actions", "actions popup edit", lambda: self.navigate("actions")),
            ("Go to Settings", "provider shortcut privacy", lambda: self.navigate("settings")),
            ("Go to About", "version credits links", lambda: self.navigate("about")),
            pause_command,
            ("Add an action", "new action", self._palette_add_action),
            ("Focus rewrite search", "find history", self._focus_search),
            ("Open provider settings", "api key model", self._palette_provider),
            ("Clear rewrite history", "delete all privacy", self._palette_clear_history),
            ("Check for updates", "release version", lambda: webbrowser.open(
                "https://github.com/bitgineer/WritingTools/releases"
            )),
            ("View source", "github code", lambda: webbrowser.open(
                "https://github.com/bitgineer/WritingTools"
            )),
            ("Quit Writing Tools", "exit close", self.app.exit_app),
        ]
        self.command_palette.open(commands)

    def _palette_add_action(self) -> None:
        self.navigate("actions")
        self.actions._add()

    def _palette_provider(self) -> None:
        self.navigate("settings")
        self.settings.focus_provider()

    def _palette_clear_history(self) -> None:
        self.navigate("settings")
        self.settings._clear_history()

    def show_banner(
        self,
        title: str,
        body: str = "",
        action_text: str | None = None,
        action=None,
        tone: str = "warning",
    ) -> None:
        from ui.Components import Banner

        while self.banner_layout.count():
            item = self.banner_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        banner = Banner(title, body, action_text, action, tone=tone)
        self.banner_layout.addWidget(banner)
        self.banner_host.show()

    def clear_banner(self) -> None:
        while self.banner_layout.count():
            item = self.banner_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.banner_host.hide()

    def show_window(self) -> None:
        if not self._placed:
            screen = QtGui.QGuiApplication.primaryScreen()
            if screen is not None:
                frame = self.frameGeometry()
                frame.moveCenter(screen.availableGeometry().center())
                self.move(frame.topLeft())
            self._placed = True
        self.refresh()
        self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()
        if self._current == "home":
            QtCore.QTimer.singleShot(50, self.home.focus_first)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt signature)
        super().resizeEvent(event)
        if hasattr(self, "toast"):
            self.toast.reposition()
        if hasattr(self, "command_palette") and self.command_palette.isVisible():
            self.command_palette.setGeometry(self.rect())

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt signature)
        if event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
            key = event.key()
            if key == QtCore.Qt.Key.Key_K:
                self.open_palette()
                return
            if key == QtCore.Qt.Key.Key_F:
                self._focus_search()
                return
            if key == QtCore.Qt.Key.Key_H:
                self.navigate("rewrites")
                return
            if QtCore.Qt.Key.Key_1 <= key <= QtCore.Qt.Key.Key_5:
                self.navigate(VIEWS[int(key) - int(QtCore.Qt.Key.Key_1)])
                return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt signature)
        """Closing the window leaves the tray app running."""
        self.hide()
        event.ignore()


def _icon_path() -> str:
    import os
    import sys

    return os.path.join(os.path.dirname(sys.argv[0]), "icons", "app_icon.png")
