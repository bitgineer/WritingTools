import json
import logging
import os
import sys
from functools import partial

from pynput import keyboard as pykeyboard
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt
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
    icon as design_icon,
    popup_stylesheet,
    primary_button,
    segmented_control,
)

_ = lambda x: x

################################################################################
# Default `options.json` content to restore when the user presses "Reset"
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
        # before — no empty-string clutter in options.json.
        hotkey = self.hotkey_input.text().strip().lower() if self.hotkey_input else ""
        if hotkey:
            data["hotkey"] = hotkey
        return data

class DraggableButton(QtWidgets.QPushButton):
    def __init__(self, parent_popup, key, text):
        super().__init__(text, parent_popup)
        self.popup = parent_popup
        self.key = key
        self.drag_start_position = None
        self.setAcceptDrops(True)
        self.icon_container = None

        # Enable mouse tracking and hover events, and styled background
        self.setMouseTracking(True)
        self.setAttribute(QtCore.Qt.WA_Hover, True)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)

        self.setObjectName("actionButton")
        self.setFixedSize(176, 44)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setIconSize(QtCore.QSize(16, 16))
        self.setProperty("dragging", False)
        logging.debug("DraggableButton initialized")

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            if self.popup.edit_mode:
                self.drag_start_position = event.pos()
                event.accept()
                return
        super().mousePressEvent(event)
            
    def mouseMoveEvent(self, event):
        if not (event.buttons() & QtCore.Qt.LeftButton) or not self.drag_start_position:
            return

        distance = (event.pos() - self.drag_start_position).manhattanLength()
        if distance < QtWidgets.QApplication.startDragDistance():
            return

        if self.popup.edit_mode:
            drag = QtGui.QDrag(self)
            mime_data = QtCore.QMimeData()
            idx = self.popup.button_widgets.index(self)
            mime_data.setData("application/x-button-index", str(idx).encode())
            drag.setMimeData(mime_data)

            pixmap = self.grab()
            drag.setPixmap(pixmap)
            drag.setHotSpot(event.pos())

            self.drag_start_position = None
            drop_action = drag.exec_(QtCore.Qt.MoveAction)
            logging.debug(f"Drag completed with action: {drop_action}")

    def _set_dragging(self, dragging: bool) -> None:
        self.setProperty("dragging", dragging)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event):
        if self.popup.edit_mode and event.mimeData().hasFormat("application/x-button-index"):
            self._set_dragging(True)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._set_dragging(False)
        event.accept()

    def dropEvent(self, event):
        if not self.popup.edit_mode or not event.mimeData().hasFormat("application/x-button-index"):
            event.ignore()
            return

        source_idx = int(event.mimeData().data("application/x-button-index").data().decode())
        target_idx = self.popup.button_widgets.index(self)

        if source_idx != target_idx:
            bw = self.popup.button_widgets
            bw[source_idx], bw[target_idx] = bw[target_idx], bw[source_idx]
            self.popup.rebuild_grid_layout()
            self.popup.update_json_from_grid()

        self._set_dragging(False)
        event.setDropAction(QtCore.Qt.MoveAction)
        event.acceptProposedAction()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.icon_container:
            self.icon_container.setGeometry(0, 0, self.width(), self.height())

class CustomPopupWindow(QtWidgets.QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.edit_mode = False

        self.drag_label = None
        self.edit_button = None
        self.reset_button = None
        self.close_button = None
        self.custom_input = None
        self.input_area = None
        
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
        self.setWindowTitle("Writing Tools")
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

        self.drag_label = QLabel("Drag actions to rearrange")
        self.drag_label.setObjectName("popupSubtitle")
        self.drag_label.hide()
        title_block.addWidget(self.drag_label)

        top_bar.addWidget(self.header_handle, 1)

        self.history_button = QPushButton()
        self.history_button.setObjectName("popupIcon")
        self.history_button.setFixedSize(28, 28)
        self.history_button.setIcon(clock_icon(p))
        self.history_button.setToolTip("Rewrite History  ·  Ctrl+H")
        self.history_button.setAccessibleName("Open Rewrite History")
        self.history_button.clicked.connect(self.open_history)
        top_bar.addWidget(self.history_button)

        self.edit_button = QPushButton()
        self.edit_button.setObjectName("popupIcon")
        self.edit_button.setFixedSize(28, 28)
        self.edit_button.setIcon(design_icon("pencil", p))
        self.edit_button.setToolTip("Edit actions")
        self.edit_button.setAccessibleName("Edit actions")
        self.edit_button.clicked.connect(self.toggle_edit_mode)
        top_bar.addWidget(self.edit_button)

        self.reset_button = QPushButton()
        self.reset_button.setObjectName("popupIcon")
        self.reset_button.setFixedSize(28, 28)
        self.reset_button.setIcon(design_icon("restore", p))
        self.reset_button.setToolTip("Reset actions to defaults")
        self.reset_button.setAccessibleName("Reset actions to defaults")
        self.reset_button.clicked.connect(self.on_reset_clicked)
        self.reset_button.hide()
        top_bar.addWidget(self.reset_button)

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
        send_btn.setIcon(design_icon("send", p))
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

        self.footer_hint = QLabel("Enter to send  \u00b7  Esc to close  \u00b7  Ctrl+H history")
        self.footer_hint.setObjectName("popupHint")
        content_layout.addWidget(self.footer_hint)

        self.build_buttons_list()
        self.rebuild_grid_layout()

        if self.app.config.get("update_available", False):
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
            self,
            [self.header_handle, self.title_label, self.subtitle_label, self.drag_label],
        )
        self.installEventFilter(self)
        QtCore.QTimer.singleShot(250, lambda: self.custom_input.setFocus())

    @staticmethod
    def load_options():
        return ActionStore.load()

    @staticmethod
    def save_options(options):
        ActionStore.save(options)

    def build_buttons_list(self):
        """
        Reads options.json, creates DraggableButton for each (except "Custom"),
        storing them in self.button_widgets in the same order as the JSON file.
        """
        for old in self.button_widgets:
            old.setParent(None)
            old.deleteLater()
        self.button_widgets.clear()
        data = self.load_options()

        for k,v in data.items():
            if k=="Custom":
                continue
            b = DraggableButton(self, k, k)
            icon_path = os.path.join(
                os.path.dirname(sys.argv[0]),
                v["icon"] + ("_dark" if self._palette.mode == "dark" else "_light") + ".png",
            )
            if os.path.exists(icon_path):
                b.setIcon(QtGui.QIcon(icon_path))

            # Tooltip surfaces the direct hotkey (if any) for discoverability.
            # Buttons without a hotkey get no tooltip — keeps things uncluttered.
            hotkey = (v.get("hotkey") or "").strip()
            if hotkey:
                b.setToolTip(f"Direct hotkey: {hotkey}")

            if not self.edit_mode:
                b.clicked.connect(partial(self.on_generic_instruction, k))
            self.button_widgets.append(b)

    def rebuild_grid_layout(self, parent_layout=None):
        """Rebuild the action grid without recreating the buttons."""
        while self.grid.count():
            self.grid.takeAt(0)

        if getattr(self, "add_button", None) is not None:
            self.add_button.deleteLater()
            self.add_button = None

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

        if self.edit_mode:
            self.add_button = QPushButton("+ Add action")
            self.add_button.setObjectName("addButton")
            self.add_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            self.add_button.clicked.connect(self.add_new_button_clicked)
            self.grid.addWidget(self.add_button, row, 0, 1, 2)

    def add_edit_delete_icons(self, btn):
        """Add edit/delete icons as overlays with proper spacing."""
        if hasattr(btn, 'icon_container') and btn.icon_container:
            btn.icon_container.deleteLater()
        
        btn.icon_container = QtWidgets.QWidget(btn)
        btn.icon_container.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)
        
        btn.icon_container.setGeometry(0, 0, btn.width(), btn.height())
        
        # Create edit icon (top-left)
        edit_btn = QPushButton(btn.icon_container)
        edit_btn.setObjectName("overlay")
        edit_btn.setGeometry(3, 3, 24, 24)
        edit_btn.setIcon(design_icon("pencil", self._palette))
        edit_btn.setIconSize(QtCore.QSize(12, 12))
        edit_btn.setAccessibleName(f"Edit {btn.key}")
        edit_btn.clicked.connect(partial(self.edit_button_clicked, btn))
        edit_btn.show()

        # Create delete icon (top-right)
        delete_btn = QPushButton(btn.icon_container)
        delete_btn.setObjectName("overlay")
        delete_btn.setGeometry(btn.width() - 27, 3, 24, 24)
        delete_btn.setIcon(design_icon("cross", self._palette))
        delete_btn.setIconSize(QtCore.QSize(12, 12))
        delete_btn.setAccessibleName(f"Delete {btn.key}")
        delete_btn.clicked.connect(partial(self.delete_button_clicked, btn))
        delete_btn.show()
        
        btn.icon_container.raise_()
        btn.icon_container.show()

    def toggle_edit_mode(self):
        """Toggle edit mode with improved button labels and state handling."""
        self.edit_mode = not self.edit_mode
        logging.debug(f'Edit mode toggled: {self.edit_mode}')

        if self.edit_mode:
            self.edit_button.setIcon(design_icon("check", self._palette))
            self.edit_button.setFixedSize(28, 28)
            self.edit_button.setToolTip("Done editing actions")
            self.edit_button.setAccessibleName("Done editing actions")
            self.title_label.setText("Edit actions")
            self.subtitle_label.hide()
            self.drag_label.show()
            self.footer_hint.setText("Drag to rearrange  \u00b7  Done when finished")
            self.close_button.hide()
            self.reset_button.show()
        else:
            self.edit_button.setIcon(design_icon("pencil", self._palette))
            self.edit_button.setFixedSize(28, 28)
            self.edit_button.setToolTip("Edit actions")
            self.edit_button.setAccessibleName("Edit actions")
            self.title_label.setText("Writing Tools")
            self.subtitle_label.show()
            self.drag_label.hide()
            self.footer_hint.setText(
                "Enter to send  \u00b7  Esc to close  \u00b7  Ctrl+H history"
            )
            self.close_button.show()
            self.reset_button.hide()

            # Changes apply in place. The old flow quit the app and asked the
            # writer to relaunch, which cost more than the edit itself.
            self.app.load_options()
            self.app.register_hotkey()

        self.input_area.setVisible(not self.edit_mode)

        for btn in self.button_widgets:
            try:
                btn.clicked.disconnect()
            except Exception:
                pass

            if not self.edit_mode:
                btn.clicked.connect(partial(self.on_generic_instruction, btn.key))
                if hasattr(btn, 'icon_container') and btn.icon_container:
                    btn.icon_container.deleteLater()
                    btn.icon_container = None
            else:
                self.add_edit_delete_icons(btn)

            btn._set_dragging(False)

        self.rebuild_grid_layout()


    def on_reset_clicked(self):
        """
        Reset `options.json` to the DEFAULT_OPTIONS_JSON, then show message & restart.
        """
        confirm_box = QtWidgets.QMessageBox()
        confirm_box.setWindowTitle("Reset actions to defaults?")
        confirm_box.setText("This restores the default actions and removes your custom ones.\nAre you sure you want to continue?")
        confirm_box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        confirm_box.setDefaultButton(QtWidgets.QMessageBox.No)
        
        if confirm_box.exec_() == QtWidgets.QMessageBox.Yes:
            try:
                logging.debug('Resetting to default options.json')
                default_data = json.loads(DEFAULT_OPTIONS_JSON)
                if not self.save_options(default_data):
                    raise RuntimeError("options.json could not be written")

                # Save and refresh in place
                self.app.load_options()
                self.app.register_hotkey()
                self.build_buttons_list()
                self.rebuild_grid_layout()
            
            except Exception as e:
                logging.error(f"Error resetting options.json: {e}")
                error_msg = QtWidgets.QMessageBox()
                error_msg.setWindowTitle("Error")
                error_msg.setText(f"An error occurred while resetting: {str(e)}")
                error_msg.exec_()

    def _validate_hotkey(self, hotkey, exclude_button=None):
        """
        Check a button hotkey string for validity and conflicts.

        Returns (ok, error_message). Empty hotkey is always ok — the dialog
        omits the field on save, which means "no direct hotkey for this
        button". This is also how every legacy/old options.json entry
        looks, so absence is always safe.
        """
        error = ActionStore.validate_hotkey(
            (hotkey or "").strip().lower(),
            self.load_options(),
            self.app.config.get('shortcut') or 'ctrl+space',
            self.app._to_pynput_hotkey,
            exclude=exclude_button,
        )
        return (error is None, error)

    @staticmethod
    def _build_button_entry(bd, existing=None):
        """
        Assemble the options.json entry for a button from dialog output.
        Preserves any non-dialog fields already on the existing entry, and
        only writes `hotkey` when the user provided one (legacy-clean).
        """
        return ActionStore.build_entry(bd, existing=existing)

    def add_new_button_clicked(self):
        dialog = ButtonEditDialog(self, title="Add action")
        while dialog.exec_():
            bd = dialog.get_button_data()
            name = (bd.get("name") or "").strip()
            if not name:
                QtWidgets.QMessageBox.warning(self, "Action not saved", "Give the action a name.")
                continue
            data = self.load_options()
            if name in data:
                QtWidgets.QMessageBox.warning(
                    self, "Action not saved", f"An action named '{name}' already exists."
                )
                continue
            ok, err = self._validate_hotkey(bd.get("hotkey", ""))
            if not ok:
                QtWidgets.QMessageBox.warning(self, "Invalid hotkey", err)
                # Re-open the dialog with the user's entries preserved so
                # they can fix the hotkey instead of starting over.
                continue
            bd["name"] = name
            data[name] = self._build_button_entry(bd)
            if not self.save_options(data):
                QtWidgets.QMessageBox.warning(
                    self, "Could not save", "Writing Tools could not write options.json."
                )
                return

            self.app.load_options()
            self.app.register_hotkey()
            self.build_buttons_list()
            self.rebuild_grid_layout()
            return


    def edit_button_clicked(self, btn):
        """User clicked the small pencil icon over a button."""
        key = btn.key
        data = self.load_options()
        bd = data[key]
        bd["name"] = key

        dialog = ButtonEditDialog(self, bd)
        while dialog.exec_():
            new_data = dialog.get_button_data()
            new_name = (new_data.get("name") or "").strip()
            if not new_name:
                QtWidgets.QMessageBox.warning(self, "Action not saved", "Give the action a name.")
                continue
            if new_name != key and new_name in self.load_options():
                QtWidgets.QMessageBox.warning(
                    self, "Action not saved", f"An action named '{new_name}' already exists."
                )
                continue
            # Pass `exclude_button=key` so we don't flag the button's own
            # current hotkey as a conflict with itself.
            ok, err = self._validate_hotkey(new_data.get("hotkey", ""), exclude_button=key)
            if not ok:
                QtWidgets.QMessageBox.warning(self, "Invalid hotkey", err)
                continue
            data = self.load_options()
            existing = data.get(key)
            new_data["name"] = new_name
            data = ActionStore.replace_entry(
                data, key, new_name, self._build_button_entry(new_data, existing=existing)
            )
            if not self.save_options(data):
                QtWidgets.QMessageBox.warning(
                    self, "Could not save", "Writing Tools could not write options.json."
                )
                return

            self.app.load_options()
            self.app.register_hotkey()
            self.build_buttons_list()
            self.rebuild_grid_layout()
            return

    def delete_button_clicked(self, btn):
        """Handle deletion of a button."""
        key = btn.key
        confirm = QtWidgets.QMessageBox()
        confirm.setWindowTitle("Delete action?")
        confirm.setText(f"Delete the '{key}' action?\nYou can add it again later.")
        confirm.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        confirm.setDefaultButton(QtWidgets.QMessageBox.No)
        
        if confirm.exec_() == QtWidgets.QMessageBox.Yes:
            try:
                data = self.load_options()
                del data[key]
                if not self.save_options(data):
                    raise RuntimeError("options.json could not be written")

                # Clean up UI elements
                for btn_ in self.button_widgets[:]:
                    if btn_.key == key:
                        if hasattr(btn_, 'icon_container') and btn_.icon_container:
                            btn_.icon_container.deleteLater()
                        btn_.deleteLater()
                        self.button_widgets.remove(btn_)
                
                self.app.load_options()
                self.app.register_hotkey()
                self.build_buttons_list()
                self.rebuild_grid_layout()

            except Exception as e:
                logging.error(f"Error deleting button: {e}")
                error_msg = QtWidgets.QMessageBox()
                error_msg.setWindowTitle("Error")
                error_msg.setText(f"An error occurred while deleting the action: {str(e)}")
                error_msg.exec_()

    def update_json_from_grid(self):
        """
        Called after a drop reorder. Reflect the new order in options.json,
        so that user's custom arrangement persists.
        """
        data = self.load_options()
        new_data = {"Custom": data["Custom"]} if "Custom" in data else {}
        for b in self.button_widgets:
            new_data[b.key] = data[b.key]
        if not self.save_options(new_data):
            logging.error("Could not save the new action order")

    def on_custom_change(self):
        txt = self.custom_input.text().strip()
        if txt:
            self.app.process_option('Custom', txt)
            self.close()

    def open_history(self):
        """Open Rewrite History without a detour through the tray menu."""
        self.hide()
        self.app.show_history()

    def on_generic_instruction(self, instruction):
        if not self.edit_mode:
            self.app.process_option(instruction)
            self.close()

    def eventFilter(self, obj, event):
        # Hide on deactivate only if NOT in edit mode
        if event.type()==QtCore.QEvent.WindowDeactivate:
            if not self.edit_mode:
                self.hide()
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.key()==QtCore.Qt.Key_Escape:
            self.close()
        elif (
            event.key() == QtCore.Qt.Key_H
            and event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier
        ):
            self.open_history()
        else:
            super().keyPressEvent(event)
