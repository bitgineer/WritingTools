"""Settings: general, provider, privacy, and updates in one scrollable view."""

from __future__ import annotations

import webbrowser

from PySide6 import QtCore, QtWidgets

from ui.AutostartManager import AutostartManager
from ui.Components import scroll_page
from ui.ProviderForm import ProviderForm
from ui.design import GAP, field_label, ghost_button, section_card
from update_checker import CURRENT_VERSION

RELEASES_URL = "https://github.com/bitgineer/WritingTools/releases"
SOURCE_URL = "https://github.com/bitgineer/WritingTools"


class SettingsView(QtWidgets.QWidget):
    changed = QtCore.Signal()

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self._build()
        self.refresh()

    def _build(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        scroll, self.content = scroll_page()
        self.scroll = scroll
        layout.addWidget(scroll)

        general, general_layout = section_card(
            "General", "The shortcut and startup behavior."
        )
        general_layout.addWidget(field_label("Shortcut"))
        self.shortcut = QtWidgets.QLineEdit()
        self.shortcut.setAccessibleName("Shortcut")
        self.shortcut.setPlaceholderText("ctrl+space")
        self.shortcut.editingFinished.connect(self._save_shortcut)
        self.shortcut.returnPressed.connect(self._save_shortcut)
        general_layout.addWidget(self.shortcut)
        self.shortcut_error = QtWidgets.QLabel("")
        self.shortcut_error.setObjectName("FieldError")
        self.shortcut_error.setWordWrap(True)
        self.shortcut_error.hide()
        general_layout.addWidget(self.shortcut_error)
        hint = QtWidgets.QLabel(
            "Saves as soon as you press Enter or leave the field. Use + between keys."
        )
        hint.setObjectName("FieldHint")
        hint.setWordWrap(True)
        general_layout.addWidget(hint)

        self.autostart = QtWidgets.QCheckBox("Start Writing Tools when I sign in")
        self.autostart.setAccessibleName("Start Writing Tools when I sign in")
        self.autostart.stateChanged.connect(self._toggle_autostart)
        general_layout.addWidget(self.autostart)
        appearance = QtWidgets.QLabel(
            "Appearance follows Windows light and dark mode. There is no separate theme."
        )
        appearance.setObjectName("FieldHint")
        appearance.setWordWrap(True)
        general_layout.addWidget(appearance)

        provider_card, provider_layout = section_card(
            "AI provider", "The service that answers your rewrites."
        )
        self.provider_form = ProviderForm(self.app, save_label="Save provider")
        self.provider_form.saved.connect(self._provider_saved)
        provider_layout.addWidget(self.provider_form)
        self.content.addWidget(provider_card)
        self.content.addWidget(general)

        privacy, privacy_layout = section_card(
            "Privacy", "History is local and never uploaded."
        )
        self.history_toggle = QtWidgets.QCheckBox("Save rewrites to history")
        self.history_toggle.setAccessibleName("Save rewrites to history")
        self.history_toggle.toggled.connect(self._toggle_history)
        privacy_layout.addWidget(self.history_toggle)
        self.history_note = QtWidgets.QLabel("")
        self.history_note.setObjectName("FieldHint")
        self.history_note.setWordWrap(True)
        privacy_layout.addWidget(self.history_note)
        privacy_actions = QtWidgets.QHBoxLayout()
        privacy_actions.addStretch(1)
        clear = ghost_button("Clear rewrite history")
        clear.setObjectName("danger")
        clear.clicked.connect(self._clear_history)
        privacy_actions.addWidget(clear)
        privacy_layout.addLayout(privacy_actions)
        self.content.addWidget(privacy)

        updates, updates_layout = section_card("Updates", "Version and links.")
        version = QtWidgets.QLabel(f"Version {CURRENT_VERSION}")
        version.setObjectName("MetricValue")
        updates_layout.addWidget(version)
        links = QtWidgets.QHBoxLayout()
        check = ghost_button("See the latest release")
        check.clicked.connect(lambda: webbrowser.open(RELEASES_URL))
        links.addWidget(check)
        source = ghost_button("View source")
        source.clicked.connect(lambda: webbrowser.open(SOURCE_URL))
        links.addWidget(source)
        links.addStretch(1)
        updates_layout.addLayout(links)
        self.content.addWidget(updates)
        self.content.addStretch(1)

    def refresh(self) -> None:
        config = self.app.config or {}
        self.shortcut.setText((config.get("shortcut") or "ctrl+space").strip())
        self.history_toggle.blockSignals(True)
        self.history_toggle.setChecked(bool(getattr(self.app, "history_enabled", True)))
        self.history_toggle.blockSignals(False)
        self._refresh_history_note()
        if AutostartManager.get_startup_path():
            self.autostart.show()
            self.autostart.blockSignals(True)
            self.autostart.setChecked(bool(AutostartManager.check_autostart()))
            self.autostart.blockSignals(False)
        else:
            self.autostart.hide()

    def _save_shortcut(self) -> None:
        value = self.shortcut.text().strip()
        if value == ((self.app.config or {}).get("shortcut") or "").strip():
            return
        error = self.app.validate_shortcut(value)
        if error:
            self.shortcut_error.setText(error)
            self.shortcut_error.show()
            return
        self.shortcut_error.hide()
        config = self.app.config
        config["shortcut"] = value
        self.app.save_config(config)
        self.app.register_hotkey()
        self._toast("Shortcut saved.")
        self.changed.emit()

    def _toggle_autostart(self, state) -> None:
        wanted = state == 2
        if AutostartManager.set_autostart(wanted):
            return
        self.autostart.blockSignals(True)
        self.autostart.setChecked(not wanted)
        self.autostart.blockSignals(False)
        shell = self.window()
        if hasattr(shell, "show_banner"):
            shell.show_banner(
                "Start on Boot",
                "Windows did not accept the startup change. Try again, or add Writing Tools to your startup apps.",
            )
        else:
            QtWidgets.QMessageBox.warning(
                self,
                "Start on Boot",
                "Windows did not accept the startup change. Try again, or add Writing Tools to your startup apps.",
            )

    def _toggle_history(self, enabled: bool) -> None:
        setter = getattr(self.app, "set_history_enabled", None)
        if setter is not None:
            setter(enabled)
        else:
            self.app.history_enabled = enabled
            self.app.config["history_enabled"] = enabled
            self.app.save_config(self.app.config)
        self._refresh_history_note()
        self.changed.emit()

    def _refresh_history_note(self) -> None:
        store = getattr(self.app, "history_store", None)
        limit = getattr(store, "limit", 500) if store is not None else 500
        if getattr(self.app, "history_enabled", True):
            self.history_note.setText(
                f"New rewrites are saved on this device. The newest {limit} are kept."
            )
        else:
            self.history_note.setText(
                "History is off. Existing rewrites stay until you clear them."
            )

    def _clear_history(self) -> None:
        store = getattr(self.app, "history_store", None)
        if store is None or store.count() == 0:
            self._toast("History is already empty.")
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
        store.clear()
        callback = getattr(self.app, "history_changed", None)
        if callback is not None:
            callback()
        self._toast("History cleared.")
        self.changed.emit()

    def _provider_saved(self) -> None:
        self.refresh()
        shell = self.window()
        if hasattr(shell, "clear_banner"):
            shell.clear_banner()
        self._toast("Provider saved.")
        self.changed.emit()

    def focus_provider(self) -> None:
        self.scroll.ensureWidgetVisible(self.provider_form)
        self.provider_form.focus_provider()

    def _toast(self, message: str) -> None:
        shell = self.window()
        if hasattr(shell, "toast"):
            shell.toast.show_message(message)
