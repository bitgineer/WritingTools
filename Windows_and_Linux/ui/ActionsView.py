"""Actions: the only editor for popup actions.

Add, edit, reorder, and remove actions in place. Saving applies immediately;
there is no restart and no second editor.
"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ui import ActionStore
from ui.Components import Banner, scroll_page
from ui.design import field_label, ghost_button, primary_button, section_card, segmented_control

CUSTOM = "Custom"


class ActionRow(QtWidgets.QPushButton):
    def __init__(self, name: str, entry: dict, index: int, total: int, parent=None):
        super().__init__(parent)
        self.name = name
        self.setObjectName("RowCard")
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(f"Edit {name}")
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(8)

        text = QtWidgets.QVBoxLayout()
        text.setSpacing(1)
        title = QtWidgets.QLabel(name)
        title.setObjectName("SectionTitle")
        title.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        text.addWidget(title)
        detail = QtWidgets.QLabel(
            f"{ActionStore.summary(entry)}"
            + (f"  \u00b7  {entry.get('hotkey')}" if entry.get("hotkey") else "")
        )
        detail.setObjectName("Meta")
        detail.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        text.addWidget(detail)
        layout.addLayout(text, 1)

        tag = QtWidgets.QLabel("Window" if entry.get("open_in_window") else "Replace")
        tag.setObjectName("TagMuted")
        tag.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(tag)

        edit = QtWidgets.QLabel("Edit")
        edit.setObjectName("FieldHint")
        edit.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(edit)

    def sizeHint(self) -> QtCore.QSize:
        hint = super().sizeHint()
        return QtCore.QSize(hint.width(), max(52, hint.height()))


class InlineEditor(QtWidgets.QFrame):
    saved = QtCore.Signal()
    cancelled = QtCore.Signal()
    delete_requested = QtCore.Signal(str)
    move_requested = QtCore.Signal(str, int)

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.editing_name: str | None = None
        self.setObjectName("SetupCard")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        self.title = QtWidgets.QLabel("New action")
        self.title.setObjectName("SectionTitle")
        layout.addWidget(self.title)

        self.banner = Banner("", tone="warning")
        self.banner.hide()
        layout.addWidget(self.banner)

        layout.addWidget(field_label("Action name"))
        self.name = QtWidgets.QLineEdit()
        self.name.setPlaceholderText("e.g. Make it friendly")
        self.name.setAccessibleName("Action name")
        layout.addWidget(self.name)

        layout.addWidget(field_label("What should the AI do with the selection?"))
        self.instruction = QtWidgets.QPlainTextEdit()
        self.instruction.setPlaceholderText(
            "Examples:\n- Fix and explain this code.\n- Make it funny.\n- Translate to English."
        )
        self.instruction.setAccessibleName("Instructions for the AI")
        self.instruction.setMinimumHeight(120)
        layout.addWidget(self.instruction)

        layout.addWidget(field_label("Where should the result appear?"))
        self.mode_control, self.mode_buttons = segmented_control(
            [("replace", "Replace the selection"), ("window", "Open in the reader")],
            "replace",
            self._set_mode,
        )
        self.mode = "replace"
        layout.addWidget(self.mode_control)

        layout.addWidget(field_label("Action shortcut (optional)"))
        self.hotkey = QtWidgets.QLineEdit()
        self.hotkey.setPlaceholderText("e.g. ctrl+j")
        self.hotkey.setAccessibleName("Action shortcut")
        layout.addWidget(self.hotkey)
        hint = QtWidgets.QLabel("Runs this action from anywhere and skips the popup.")
        hint.setObjectName("FieldHint")
        layout.addWidget(hint)

        footer = QtWidgets.QHBoxLayout()
        self.delete_button = ghost_button("Delete")
        self.delete_button.setObjectName("danger")
        self.delete_button.setAccessibleName("Delete action")
        self.delete_button.clicked.connect(
            lambda: self.delete_requested.emit(self.editing_name or "")
        )
        footer.addWidget(self.delete_button)
        self.up_button = ghost_button("Move up")
        self.up_button.setAccessibleName("Move action up")
        self.up_button.clicked.connect(
            lambda: self.move_requested.emit(self.editing_name or "", -1)
        )
        footer.addWidget(self.up_button)
        self.down_button = ghost_button("Move down")
        self.down_button.setAccessibleName("Move action down")
        self.down_button.clicked.connect(
            lambda: self.move_requested.emit(self.editing_name or "", 1)
        )
        footer.addWidget(self.down_button)
        footer.addStretch(1)
        cancel = ghost_button("Cancel")
        cancel.clicked.connect(self.cancelled.emit)
        footer.addWidget(cancel)
        save = primary_button("Save action")
        save.clicked.connect(self.save)
        footer.addWidget(save)
        layout.addLayout(footer)

    def _set_mode(self, mode: str) -> None:
        self.mode = mode

    def start(self, name: str | None = None) -> None:
        self.editing_name = name
        self.banner.hide()
        if name:
            data = ActionStore.load()
            entry = data.get(name, {})
            self.title.setText(f"Edit {name}")
            self.name.setText(name)
            self.instruction.setPlainText(entry.get("instruction", ""))
            self.hotkey.setText(entry.get("hotkey", ""))
            window_mode = bool(entry.get("open_in_window"))
            self.mode = "window" if window_mode else "replace"
            for key, button in self.mode_buttons.items():
                button.setChecked(key == self.mode)
            names = [key for key, _value in ActionStore.actions(data)]
            index = names.index(name) if name in names else 0
            self.delete_button.show()
            self.up_button.show()
            self.down_button.show()
            self.up_button.setEnabled(index > 0)
            self.down_button.setEnabled(index < len(names) - 1)
        else:
            self.title.setText("New action")
            self.name.clear()
            self.instruction.clear()
            self.hotkey.clear()
            self.mode = "replace"
            for key, button in self.mode_buttons.items():
                button.setChecked(key == "replace")
            self.delete_button.hide()
            self.up_button.hide()
            self.down_button.hide()
        self.name.setFocus()

    def save(self) -> None:
        data = ActionStore.load()
        name = self.name.text().strip()
        if not name:
            self._error("Action not saved", "Give the action a name.")
            return
        if name == CUSTOM:
            self._error("Action not saved", "Custom is reserved for the free-text field.")
            return
        if name != self.editing_name and name in data:
            self._error("Action not saved", f"An action named '{name}' already exists.")
            return
        hotkey = self.hotkey.text().strip().lower()
        error = ActionStore.validate_hotkey(
            hotkey,
            data,
            (self.app.config or {}).get("shortcut") or "ctrl+space",
            self.app._to_pynput_hotkey,
            exclude=self.editing_name,
        )
        if error:
            self._error("Shortcut not valid", error)
            return
        result = {
            "name": name,
            "prefix": "Make this change to the following text:\n\n",
            "instruction": self.instruction.toPlainText(),
            "icon": "icons/custom",
            "open_in_window": self.mode == "window",
            "hotkey": hotkey,
        }
        existing = data.get(self.editing_name) if self.editing_name else None
        entry = ActionStore.build_entry(result, existing=existing)
        if self.editing_name and self.editing_name != name:
            data = ActionStore.replace_entry(data, self.editing_name, name, entry)
        elif self.editing_name:
            data[self.editing_name] = entry
        else:
            data[name] = entry
        if not ActionStore.save(data):
            self._error("Could not save", "Writing Tools could not write options.json.")
            return
        self.editing_name = None
        self.saved.emit()

    def _error(self, title: str, body: str) -> None:
        self.banner.set_content(title, body)
        self.banner.show()
        self.banner.raise_()


class ActionsView(QtWidgets.QWidget):
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
        layout.addWidget(scroll)

        card, card_layout = section_card()
        header = QtWidgets.QHBoxLayout()
        self.count = QtWidgets.QLabel("")
        self.count.setObjectName("MetricLabel")
        header.addWidget(self.count)
        header.addStretch(1)
        reset = ghost_button("Reset actions")
        reset.clicked.connect(self._reset)
        header.addWidget(reset)
        add = primary_button("Add action")
        add.clicked.connect(self._add)
        header.addWidget(add)
        card_layout.addLayout(header)
        self.content.addWidget(card)

        self.editor = InlineEditor(self.app)
        self.editor.saved.connect(self._saved)
        self.editor.cancelled.connect(self._cancel)
        self.editor.delete_requested.connect(self._delete)
        self.editor.move_requested.connect(self._move)
        self.editor.hide()
        self.content.addWidget(self.editor)

        self.list_host = QtWidgets.QWidget()
        self.list_layout = QtWidgets.QVBoxLayout(self.list_host)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(6)
        self.content.addWidget(self.list_host)
        self.content.addStretch(1)

    def refresh(self) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        data = ActionStore.load()
        entries = ActionStore.actions(data)
        self.count.setText(f"{len(entries)} action{'s' if len(entries) != 1 else ''}")
        for index, (name, entry) in enumerate(entries):
            row = ActionRow(name, entry, index, len(entries))
            row.clicked.connect(lambda _=False, target=name: self._edit(target))
            self.list_layout.addWidget(row)
        if not entries:
            label = QtWidgets.QLabel("No actions yet. Add one to fill the popup.")
            label.setObjectName("Meta")
            self.list_layout.addWidget(label)

    def _add(self) -> None:
        self.editor.start(None)
        self.editor.show()
        self.editor.raise_()

    def _edit(self, name: str) -> None:
        self.editor.start(name)
        self.editor.show()
        self.editor.raise_()

    def _cancel(self) -> None:
        self.editor.hide()
        self.editor.banner.hide()

    def _saved(self) -> None:
        self.editor.hide()
        self.refresh()
        self._apply()
        self._toast("Action saved.")

    def _delete(self, name: str) -> None:
        answer = QtWidgets.QMessageBox.question(
            self,
            "Delete action",
            f"Remove the '{name}' action from the popup?",
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        data = ActionStore.load()
        data.pop(name, None)
        if ActionStore.save(data):
            self.editor.hide()
            self.refresh()
            self._apply()
            self._toast(f"Deleted {name}.")

    def _move(self, name: str, delta: int) -> None:
        data = ActionStore.load()
        names = [key for key, _value in ActionStore.actions(data)]
        if name not in names:
            return
        index = names.index(name)
        target = index + delta
        if target < 0 or target >= len(names):
            return
        names[index], names[target] = names[target], names[index]
        reordered = {CUSTOM: data[CUSTOM]} if CUSTOM in data else {}
        for key in names:
            reordered[key] = data[key]
        if ActionStore.save(reordered):
            self.refresh()
            self.editor.start(name)
            self._apply()

    def _reset(self) -> None:
        answer = QtWidgets.QMessageBox.question(
            self,
            "Reset actions",
            "Restore the default actions and remove your custom ones?",
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        if ActionStore.save(ActionStore.defaults()):
            self.refresh()
            self._apply()
            self._toast("Actions reset to defaults.")

    def _apply(self) -> None:
        callback = getattr(self.app, "actions_changed", None)
        if callback is not None:
            callback()
        else:
            self.app.load_options()
            self.app.register_hotkey()
        self.changed.emit()

    def _toast(self, message: str) -> None:
        shell = self.window()
        if hasattr(shell, "toast"):
            shell.toast.show_message(message)
