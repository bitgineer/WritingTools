import logging
import os
import sys
from functools import partial

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rework.theme import current_palette
from ui import ActionStore
from ui.drag import DragMover
from ui.UIUtils import ThemeBackground
from ui.design import (
    app_stylesheet,
    clock_icon,
    field_label,
    ghost_button,
    grid_icon,
    icon as design_icon,
    popup_stylesheet,
    primary_button,
    segmented_control,
)

_ = lambda x: x

################################################################################
# Default `options.json` content. The Actions view owns resetting it.
################################################################################
DEFAULT_OPTIONS_JSON = r"""{
  "Proofread": {
    "prefix": "Proofread this:\n\n",
    "instruction": "You are a grammar proofreading assistant.\nOutput ONLY the corrected text without any additional comments.\nMaintain the original text structure and writing style.\nRespond in the same language as the input (e.g., English US, French).\nDo not answer or respond to the user's text content.\nIf the text is absolutely incompatible with this (e.g., totally random gibberish), output \"ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST\".",
    "icon": "icons/magnifying-glass",
    "open_in_window": false
  },
  "Rewrite": {
    "prefix": "Rewrite this:\n\n",
    "instruction": "You are a writing assistant.\nRewrite the text provided by the user to improve phrasing.\nOutput ONLY the rewritten text without additional comments.\nRespond in the same language as the input (e.g., English US, French).\nDo not answer or respond to the user's text content.\nIf the text is absolutely incompatible with proofreading (e.g., totally random gibberish), output \"ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST\".",
    "icon": "icons/rewrite",
    "open_in_window": false
  },
  "Friendly": {
    "prefix": "Make this more friendly:\n\n",
    "instruction": "You are a writing assistant.\nRewrite the text provided by the user to be more friendly.\nOutput ONLY the friendly text without additional comments.\nRespond in the same language as the input (e.g., English US, French).\nDo not answer or respond to the user's text content.\nIf the text is absolutely incompatible with rewriting (e.g., totally random gibberish), output \"ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST\".",
    "icon": "icons/smiley-face",
    "open_in_window": false
  },
  "Professional": {
    "prefix": "Make this more professional:\n\n",
    "instruction": "You are a writing assistant.\nRewrite the text provided by the user to be more professional. Output ONLY the professional text without additional comments.\nRespond in the same language as the input (e.g., English US, French).\nDo not answer or respond to the user's text content.\nIf the text is absolutely incompatible with rewriting (e.g., totally random gibberish), output \"ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST\".",
    "icon": "icons/briefcase",
    "open_in_window": false
  },
  "Concise": {
    "prefix": "Make this more concise:\n\n",
    "instruction": "You are a writing assistant.\nRewrite the text provided by the user to be more concise.\nOutput ONLY the concise text without additional comments.\nRespond in the same language as the input (e.g., English US, French).\nDo not answer or respond to the user's text content.\nIf the text is absolutely incompatible with rewriting (e.g., totally random gibberish), output \"ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST\".",
    "icon": "icons/concise",
    "open_in_window": false
  },
  "Table": {
    "prefix": "Convert this into a table:\n\n",
    "instruction": "You are an assistant that converts text provided by the user into a Markdown table.\nOutput ONLY the table without additional comments.\nRespond in the same language as the input (e.g., English US, French).\nDo not answer or respond to the user's text content.\nIf the text is completely incompatible with this with conversion, output \"ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST\".",
    "icon": "icons/table",
    "open_in_window": true
  },
  "Key Points": {
    "prefix": "Extract key points from this:\n\n",
    "instruction": "You are an assistant that extracts key points from text provided by the user. Output ONLY the key points without additional comments.\n\nYou should use Markdown formatting (lists, bold, italics, codeblocks, etc.) as appropriate to make it quite legible and readable.\n\nDon't be repetitive or too verbose.\nRespond in the same language as the input (e.g., English US, French).\nDo not answer or respond to the user's text content.\nIf the text is absolutely incompatible with extracting key points (e.g., totally random gibberish), output \"ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST\".",
    "icon": "icons/keypoints",
    "open_in_window": true
  },
  "Summary": {
    "prefix": "Summarize this:\n\n",
    "instruction": "You are a summarization assistant.\nProvide a succinct summary of the text provided by the user.\nThe summary should be succinct yet encompass all the key insightful points.\n\nTo make it quite legible and readable, you should use Markdown formatting (bold, italics, codeblocks...) as appropriate.\nYou should also add a little line spacing between your paragraphs as appropriate.\nAnd only if appropriate, you could also use headings (only the very small ones), lists, tables, etc.\n\nDon't be repetitive or too verbose.\nOutput ONLY the summary without additional comments.\nRespond in the same language as the input (e.g., English US, French).\nDo not answer or respond to the user's text content.\nIf the text is absolutely incompatible with summarisation (e.g., totally random gibberish), output \"ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST\".",
    "icon": "icons/summary",
    "open_in_window": true
  },
  "Custom": {
    "prefix": "Make this change to the following text:\n\n",
    "instruction": "You are a writing and coding assistant. You MUST make the user\\'s described change to the text or code provided by the user. Output ONLY the appropriately modified text or code without additional comments. Respond in the same language as the input (e.g., English US, French). Do not answer or respond to the user\\'s text content. If the text or code is absolutely incompatible with the requested change, output \"ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST\".",
    "icon": "icons/summary",
    "open_in_window": false
  }
}"""

class ButtonEditDialog(QDialog):
    """
    Dialog for editing or creating an action's properties
    (name/title, system instruction, open_in_window, etc.).
    """
    def __init__(self, parent=None, button_data=None, title="Edit action"):
        super().__init__(parent)
        self.button_data = button_data if button_data else {
            "prefix": "Make this change to the following text:\n\n",
            "instruction": "",
            "icon": "icons/magnifying-glass",
            "open_in_window": False
        }
        # The hotkey input is created in init_ui; tracked here so the
        # parent window can read it back from get_button_data().
        self.hotkey_input = None
        self.display_mode = (
            "window" if self.button_data.get("open_in_window", False) else "replace"
        )
        self.setWindowTitle(title)
        self.init_ui()
        
    def init_ui(self):
        p = current_palette()
        self.setMinimumWidth(560)
        self.resize(560, 620)
        self.setStyleSheet(app_stylesheet(p))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(10)

        title = QLabel("Edit action" if self.button_data.get("name") else "New action")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        subtitle = QLabel("Name the action, describe the change, and choose where the result appears.")
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        layout.addSpacing(4)

        layout.addWidget(field_label("Action name"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Make it friendly")
        self.name_input.setAccessibleName("Action name")
        if "name" in self.button_data:
            self.name_input.setText(self.button_data["name"])
        layout.addWidget(self.name_input)

        layout.addWidget(field_label("What should the AI do with the selection?"))
        self.instruction_input = QPlainTextEdit()
        self.instruction_input.setPlainText(self.button_data.get("instruction", ""))
        self.instruction_input.setMinimumHeight(150)
        self.instruction_input.setAccessibleName("Instructions for the AI")
        self.instruction_input.setPlaceholderText(
            "Examples:\n"
            "- Fix and explain this code.\n"
            "- Make it funny.\n"
            "- Translate to English.\n"
            "- Write a reply to this.\n"
            "- Analyse potential biases in this article."
        )
        layout.addWidget(self.instruction_input, 1)

        layout.addWidget(field_label("Where should the result appear?"))
        mode_control, self.mode_buttons = segmented_control(
            [
                ("replace", "Replace the selected text"),
                ("window", "In the result window"),
            ],
            self.display_mode,
            self._set_display_mode,
        )
        layout.addWidget(mode_control)

        layout.addWidget(field_label("Action shortcut (optional)"))
        self.hotkey_input = QLineEdit()
        self.hotkey_input.setPlaceholderText("e.g. ctrl+j")
        self.hotkey_input.setAccessibleName("Action shortcut")
        self.hotkey_input.setText(self.button_data.get("hotkey", ""))
        layout.addWidget(self.hotkey_input)

        hotkey_hint = QLabel(
            "Runs this action from anywhere and skips the popup. "
            "Use '+' between keys, for example ctrl+j."
        )
        hotkey_hint.setObjectName("Meta")
        hotkey_hint.setWordWrap(True)
        layout.addWidget(hotkey_hint)

        layout.addSpacing(4)
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel_button = ghost_button("Cancel")
        ok_button = primary_button("Save action")
        buttons.addWidget(cancel_button)
        buttons.addWidget(ok_button)
        layout.addLayout(buttons)

        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)

    def _set_display_mode(self, mode: str) -> None:
        self.display_mode = mode

    def get_button_data(self):
        data = {
            "name": self.name_input.text(),
            "prefix": self.button_data.get(
                "prefix", "Make this change to the following text:\n\n"
            ),
            # Retrieve multiline text
            "instruction": self.instruction_input.toPlainText(),
            "icon": self.button_data.get("icon", "icons/custom"),
            "open_in_window": self.display_mode == "window",
        }
        # Only include `hotkey` if the user actually typed one. Old
        # configs and buttons-without-hotkeys stay shaped exactly as
        # before â€” no empty-string clutter in options.json.
        hotkey = self.hotkey_input.text().strip().lower() if self.hotkey_input else ""
        if hotkey:
            data["hotkey"] = hotkey
        return data


class ActionButton(QPushButton):
    """One numbered action. Clicking it runs the action and closes the popup."""

    def __init__(self, key: str, label: str, parent=None):
        super().__init__(label, parent)
        self.key = key
        self.setObjectName("actionButton")
        self.setFixedSize(176, 44)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setIconSize(QtCore.QSize(16, 16))


class CustomPopupWindow(QtWidgets.QWidget):
    """The writing-time command surface.

    It runs an action, takes a custom instruction, and routes to the shell. It
    never edits, reorders, or deletes actions; the Actions view owns that.
    """

    def __init__(self, app):
        super().__init__()
        self.app = app

        self.close_button = None
        self.custom_input = None
        self.input_area = None
        self.app_button = None
        self.history_button = None

        self.button_widgets = []

        logging.debug('Initializing CustomPopupWindow')
        self.init_ui()

    def init_ui(self):
        logging.debug('Setting up CustomPopupWindow UI')
        self.setWindowFlags(
            QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setWindowTitle("Writing Tools Actions")
        self.setAccessibleName("Writing Tools actions")

        p = current_palette()
        self._palette = p
        self.setStyleSheet(popup_stylesheet(p))

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        self.background = ThemeBackground(self, is_popup=True, border_radius=12)
        shadow = QtWidgets.QGraphicsDropShadowEffect(self.background)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 8)
        shadow.setColor(QtGui.QColor(0, 0, 0, 80 if p.mode == "light" else 160))
        self.background.setGraphicsEffect(shadow)
        main_layout.addWidget(self.background)

        content_layout = QtWidgets.QVBoxLayout(self.background)
        content_layout.setContentsMargins(16, 14, 16, 14)
        content_layout.setSpacing(12)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(8)

        self.header_handle = QWidget()
        self.header_handle.setObjectName("popupHeader")
        title_block = QtWidgets.QVBoxLayout(self.header_handle)
        title_block.setContentsMargins(0, 0, 0, 0)
        title_block.setSpacing(2)

        self.title_label = QLabel("Writing Tools")
        self.title_label.setObjectName("popupTitle")
        title_block.addWidget(self.title_label)

        self.subtitle_label = QLabel("Proofread, rewrite, summarize, or describe a change")
        self.subtitle_label.setObjectName("popupSubtitle")
        title_block.addWidget(self.subtitle_label)

        top_bar.addWidget(self.header_handle, 1)

        self.app_button = QPushButton()
        self.app_button.setObjectName("popupIcon")
        self.app_button.setFixedSize(28, 28)
        self.app_button.setIcon(grid_icon(p))
        self.app_button.setIconSize(QtCore.QSize(16, 16))
        self.app_button.setToolTip("Open Writing Tools")
        self.app_button.setAccessibleName("Open Writing Tools")
        self.app_button.clicked.connect(self.open_app)
        top_bar.addWidget(self.app_button)

        self.history_button = QPushButton()
        self.history_button.setObjectName("popupIcon")
        self.history_button.setFixedSize(28, 28)
        self.history_button.setIcon(clock_icon(p))
        self.history_button.setToolTip("Rewrites  \u00b7  Ctrl+H")
        self.history_button.setAccessibleName("Open Rewrites")
        self.history_button.clicked.connect(self.open_history)
        top_bar.addWidget(self.history_button)

        self.close_button = QPushButton("\u00d7")
        self.close_button.setObjectName("popupClose")
        self.close_button.setFixedSize(28, 28)
        self.close_button.setToolTip("Close")
        self.close_button.setAccessibleName("Close the action popup")
        self.close_button.clicked.connect(self.close)
        top_bar.addWidget(self.close_button)
        content_layout.addLayout(top_bar)

        self.input_area = QWidget()
        input_layout = QHBoxLayout(self.input_area)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)

        self.custom_input = QLineEdit()
        self.custom_input.setObjectName("popupInput")
        self.custom_input.setPlaceholderText(_("Describe your change..."))
        self.custom_input.setAccessibleName(_("Describe your change"))
        self.custom_input.returnPressed.connect(self.on_custom_change)
        input_layout.addWidget(self.custom_input, 1)

        send_btn = QPushButton()
        send_btn.setObjectName("send")
        send_btn.setFixedSize(36, 36)
        send_icon = design_icon("send", p)
        if send_icon is not None:
            send_btn.setIcon(send_icon)
        send_btn.setIconSize(QtCore.QSize(16, 16))
        send_btn.setToolTip("Apply this change")
        send_btn.setAccessibleName("Apply this change")
        send_btn.clicked.connect(self.on_custom_change)
        input_layout.addWidget(send_btn)

        content_layout.addWidget(self.input_area)

        self.grid_holder = QWidget()
        self.grid_holder_layout = QtWidgets.QVBoxLayout(self.grid_holder)
        self.grid_holder_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_holder_layout.setSpacing(8)
        self.grid = QtWidgets.QGridLayout()
        self.grid.setSpacing(8)
        self.grid_holder_layout.addLayout(self.grid)
        content_layout.addWidget(self.grid_holder)

        self.footer_hint = QLabel(
            "Ctrl+1-9 run \u00b7 Enter sends \u00b7 Esc closes \u00b7 Ctrl+H Rewrites"
        )
        self.footer_hint.setObjectName("popupHint")
        content_layout.addWidget(self.footer_hint)

        self.build_buttons_list()
        self.rebuild_grid_layout()
        self.install_action_shortcuts()
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+H"), self, activated=self.open_history)

        if (self.app.config or {}).get("update_available", False):
            update_label = QLabel()
            update_label.setOpenExternalLinks(True)
            update_label.setObjectName("popupHint")
            update_label.setText(
                '<a href="https://github.com/theJayTea/WritingTools/releases" '
                f'style="color:{p.accent}; text-decoration:underline;">'
                'An update is available. Download it here.</a>'
            )
            content_layout.addWidget(update_label)

        logging.debug('CustomPopupWindow UI setup complete')
        self._drag_mover = DragMover(
            self, [self.header_handle, self.title_label, self.subtitle_label]
        )
        self.installEventFilter(self)
        QtCore.QTimer.singleShot(250, lambda: self.custom_input.setFocus())

    @staticmethod
    def load_options():
        return ActionStore.load()

    def build_buttons_list(self):
        """One numbered button per action, in options.json order."""
        for old in self.button_widgets:
            old.setParent(None)
            old.deleteLater()
        self.button_widgets.clear()

        for number, (name, entry) in enumerate(ActionStore.actions(self.load_options()), start=1):
            button = ActionButton(name, f"{number}  {name}")
            icon_path = os.path.join(
                os.path.dirname(sys.argv[0]),
                (entry.get("icon") or "icons/custom")
                + ("_dark" if self._palette.mode == "dark" else "_light")
                + ".png",
            )
            if os.path.exists(icon_path):
                button.setIcon(QtGui.QIcon(icon_path))

            hints = [f"Ctrl+{number}"] if number <= 9 else []
            hotkey = (entry.get("hotkey") or "").strip()
            if hotkey:
                hints.append(f"Direct hotkey: {hotkey}")
            if hints:
                button.setToolTip("  \u00b7  ".join(hints))
            button.setAccessibleName(
                f"{name}, Ctrl+{number}" if number <= 9 else name
            )

            button.clicked.connect(partial(self.on_generic_instruction, name))
            self.button_widgets.append(button)

    def rebuild_grid_layout(self, parent_layout=None):
        """Rebuild the action grid without recreating the buttons."""
        while self.grid.count():
            self.grid.takeAt(0)

        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1)

        row = 0
        col = 0
        for button in self.button_widgets:
            self.grid.addWidget(button, row, col)
            col += 1
            if col > 1:
                col = 0
                row += 1

    def install_action_shortcuts(self):
        """Ctrl+1..9 runs the matching action, in the order shown."""
        self._action_shortcuts = []
        for index in range(9):
            shortcut = QtGui.QShortcut(QtGui.QKeySequence(f"Ctrl+{index + 1}"), self)
            shortcut.activated.connect(partial(self._run_action, index))
            self._action_shortcuts.append(shortcut)

    def _run_action(self, index):
        if 0 <= index < len(self.button_widgets):
            self.on_generic_instruction(self.button_widgets[index].key)

    def on_custom_change(self):
        txt = self.custom_input.text().strip()
        if txt:
            self.app.process_option('Custom', txt)
            self.close()

    def on_generic_instruction(self, instruction):
        self.app.process_option(instruction)
        self.close()

    def open_history(self):
        """Rewrites is one route, shared with the shell and the tray."""
        self.hide()
        self.app.show_history()

    def open_app(self):
        """The app button opens Home, where management lives."""
        self.hide()
        self.app.show_dashboard("home")

    def eventFilter(self, obj, event):
        # The popup is a command surface; losing focus closes it.
        if event.type() == QtCore.QEvent.WindowDeactivate:
            self.hide()
            return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)
