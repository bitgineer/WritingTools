import logging

import markdown2
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QScrollArea

from rework.theme import current_palette
from ui.UIUtils import UIUtils
from ui.design import FONT_STACK, GAP, PAGE_MARGIN, SERIF_STACK, icon as design_icon, page_header

_ = lambda x: x


def _families(stack):
    return [name.strip().strip('"') for name in stack.split(',')]


def _icon(name):
    return design_icon(name, current_palette()) or QtGui.QIcon()


class MarkdownTextBrowser(QtWidgets.QTextBrowser):
    """Markdown text that sits transparently on its message surface."""

    def __init__(self, parent=None, is_user_message=False):
        super().__init__(parent)
        self.setObjectName("prose")
        self.setReadOnly(True)
        self.setOpenExternalLinks(True)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.viewport().setAutoFillBackground(False)
        self.zoom_factor = 1.2
        self.base_font_size = 14
        self.is_user_message = is_user_message

        p = current_palette()
        self.document().setDefaultStyleSheet(
            "table { border-collapse: collapse; }"
            f" th, td {{ border: 1px solid {p.hairline}; padding: 4px 6px; }}"
            f" code {{ background-color: {p.surface_alt}; }}"
        )

        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum
        )
        self.setAccessibleName(_("Your message") if is_user_message else _("Assistant response"))

        self._apply_zoom()

    def _apply_zoom(self):
        font = QtGui.QFont()
        font.setFamilies(_families(FONT_STACK if self.is_user_message else SERIF_STACK))
        font.setPixelSize(int(self.base_font_size * self.zoom_factor))
        self.document().setDefaultFont(font)

    def changeEvent(self, event):
        super().changeEvent(event)
        # The app stylesheet sets the widget font when it polishes, which resets the document font.
        if event.type() == QtCore.QEvent.Type.FontChange:
            self._apply_zoom()
            self._update_size()

    def _update_size(self):
        available_width = self.viewport().width() - 16
        self.document().setTextWidth(available_width)

        content_height = self.document().size().height()
        new_height = int(content_height + 16)

        if self.minimumHeight() != new_height:
            self.setMinimumHeight(new_height)
            self.setMaximumHeight(new_height)

            scroll_area = self.get_scroll_area()
            if scroll_area:
                scroll_area.update_content_height()

    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            parent = self.parent()
            while parent and not isinstance(parent, ResponseWindow):
                parent = parent.parent()

            if parent:
                if delta > 0:
                    parent.zoom_all_messages('in')
                else:
                    parent.zoom_all_messages('out')
                event.accept()
        else:
            if self.parent():
                self.parent().wheelEvent(event)

    def zoom_in(self):
        old_factor = self.zoom_factor
        self.zoom_factor = min(3.0, self.zoom_factor * 1.1)
        if old_factor != self.zoom_factor:
            self._apply_zoom()
            self._update_size()

    def zoom_out(self):
        old_factor = self.zoom_factor
        self.zoom_factor = max(0.5, self.zoom_factor / 1.1)
        if old_factor != self.zoom_factor:
            self._apply_zoom()
            self._update_size()

    def reset_zoom(self):
        old_factor = self.zoom_factor
        self.zoom_factor = 1.2
        if old_factor != self.zoom_factor:
            self._apply_zoom()
            self._update_size()

    def get_scroll_area(self):
        """Find the parent ChatContentScrollArea"""
        parent = self.parent()
        while parent:
            if isinstance(parent, ChatContentScrollArea):
                return parent
            parent = parent.parent()
        return None

    def sizeHint(self):
        # The default scroll-area hint (192px) would reserve space under short messages.
        hint = super().sizeHint()
        return QtCore.QSize(hint.width(), int(self.document().size().height()) + 16)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_size()


def _message_container(is_user):
    container = QtWidgets.QFrame()
    container.setSizePolicy(
        QtWidgets.QSizePolicy.Policy.Expanding,
        QtWidgets.QSizePolicy.Policy.Minimum
    )
    container.setObjectName("UserMessage" if is_user else "Card")
    return container


class ChatContentScrollArea(QScrollArea):
    """Scrollable chat column. Scrollbar and background styling come from the app stylesheet."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.content_widget = None
        self.layout = None
        self.setup_ui()

    def setup_ui(self):
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.content_widget = QtWidgets.QWidget()
        self.content_widget.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.MinimumExpanding
        )
        self.setWidget(self.content_widget)

        self.layout = QtWidgets.QVBoxLayout(self.content_widget)
        self.layout.setSpacing(GAP)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.addStretch()

    def add_message(self, text, is_user=False):
        self.layout.takeAt(self.layout.count() - 1)

        msg_container = _message_container(is_user)
        msg_layout = QtWidgets.QVBoxLayout(msg_container)
        msg_layout.setContentsMargins(16, 12, 16, 12)
        msg_layout.setSpacing(0)

        text_display = MarkdownTextBrowser(is_user_message=is_user)

        html = markdown2.markdown(text, extras=['tables', 'strike'])
        text_display.setHtml(html)

        text_display.document().setTextWidth(self.width() - 20)
        doc_size = text_display.document().size()
        text_display.setMinimumHeight(int(doc_size.height() + 16))

        msg_layout.addWidget(text_display)

        self.layout.addWidget(msg_container)
        self.layout.addStretch()

        if hasattr(self.parent(), 'current_text_display'):
            self.parent().current_text_display = text_display

        QtCore.QTimer.singleShot(50, self.post_message_updates)

        return text_display

    def post_message_updates(self):
        """Handle updates after adding a message with proper timing"""
        self.scroll_to_bottom()
        if isinstance(self.parent(), ResponseWindow):
            self.parent()._adjust_window_height()

    def update_content_height(self):
        """Recalculate total content height with improved spacing calculation"""
        total_height = 0

        for i in range(self.layout.count() - 1):
            item = self.layout.itemAt(i)
            if item and item.widget():
                widget_height = item.widget().sizeHint().height()
                total_height += widget_height

        total_height += (self.layout.spacing() * (self.layout.count() - 2))
        total_height += self.layout.contentsMargins().top() + self.layout.contentsMargins().bottom()

        self.content_widget.setMinimumHeight(total_height + 10)

        if isinstance(self.parent(), ResponseWindow):
            self.parent()._adjust_window_height()

    def scroll_to_bottom(self):
        vsb = self.verticalScrollBar()
        vsb.setValue(vsb.maximum())

    def resizeEvent(self, event):
        super().resizeEvent(event)

        for i in range(self.layout.count() - 1):
            item = self.layout.itemAt(i)
            if item and item.widget():
                container = item.widget()
                text_display = container.layout().itemAt(0).widget()
                if isinstance(text_display, MarkdownTextBrowser):
                    text_display._update_size()


class ResponseWindow(QtWidgets.QWidget):
    """Reading workspace for a model response, with zoom and follow-up questions."""

    def __init__(self, app, title=_("Response"), parent=None):
        super().__init__(parent)
        self.app = app
        self.original_title = title
        self.setWindowTitle(title)
        self.option = title.replace(" Result", "")
        self.selected_text = None
        self.input_field = None
        self.loading_label = None
        self.loading_container = None
        self.status_container = None
        self.status_title = None
        self.status_body = None
        self.chat_area = None
        self.chat_history = []
        self.awaiting_initial_response = True
        self.history_id = None

        self.thinking_timer = QtCore.QTimer(self)
        self.thinking_timer.timeout.connect(self.update_thinking_dots)
        self.thinking_dots_state = 0
        self.thinking_dots = ["", ".", "..", "..."]
        self.thinking_timer.setInterval(300)

        self.init_ui()
        logging.debug('Connecting response signals')
        self.app.followup_response_signal.connect(self.handle_followup_response)
        self.app.show_message_signal.connect(self.handle_app_message)
        logging.debug('Response signals connected')

        initial_width = 500
        initial_height = 250
        self.resize(initial_width, initial_height)

    def init_ui(self):
        self.setWindowFlags(QtCore.Qt.WindowType.Window |
                            QtCore.Qt.WindowType.WindowCloseButtonHint |
                            QtCore.Qt.WindowType.WindowMinimizeButtonHint |
                            QtCore.Qt.WindowType.WindowMaximizeButtonHint)
        self.setMinimumSize(600, 400)

        UIUtils.setup_window_and_layout(self)
        content_layout = QtWidgets.QVBoxLayout(self.background)
        content_layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        content_layout.setSpacing(GAP)

        content_layout.addLayout(self._build_header())

        self.loading_label = QtWidgets.QLabel(_("Thinking"))
        self.loading_label.setObjectName("SectionTitle")
        self.loading_label.setMinimumWidth(140)
        loading_container = QtWidgets.QWidget()
        loading_layout = QtWidgets.QHBoxLayout(loading_container)
        loading_layout.setContentsMargins(0, 0, 0, 0)
        loading_layout.addWidget(self.loading_label)
        loading_layout.addStretch()
        content_layout.addWidget(loading_container)
        self.loading_container = loading_container

        self.status_title = QtWidgets.QLabel()
        self.status_title.setObjectName("SectionTitle")
        self.status_body = QtWidgets.QLabel()
        self.status_body.setObjectName("Meta")
        self.status_body.setWordWrap(True)
        self.status_container = QtWidgets.QWidget()
        status_layout = QtWidgets.QVBoxLayout(self.status_container)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(4)
        status_layout.addWidget(self.status_title)
        status_layout.addWidget(self.status_body)
        self.status_container.hide()
        content_layout.addWidget(self.status_container)

        self.start_thinking_animation(initial=True)

        self.chat_area = ChatContentScrollArea()
        content_layout.addWidget(self.chat_area)

        content_layout.addLayout(self._build_input_row())

        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+H"), self, activated=self.open_rewrites)

    def _build_header(self):
        header = QtWidgets.QHBoxLayout()
        header.setSpacing(GAP)

        subtitle = _("Ask a follow-up below.")
        header.addWidget(page_header(self.option, subtitle), 1)

        rewrites_btn = QtWidgets.QPushButton(_("Rewrites"))
        rewrites_btn.setObjectName("ghost")
        rewrites_btn.setToolTip(_("Open Rewrites (Ctrl+H)"))
        rewrites_btn.setAccessibleName(_("Open Rewrites"))
        rewrites_btn.clicked.connect(self.open_rewrites)
        header.addWidget(rewrites_btn, 0, QtCore.Qt.AlignmentFlag.AlignTop)

        copy_md_btn = QtWidgets.QPushButton(_("Copy response"))
        copy_md_btn.setObjectName("ghost")
        copy_md_btn.setToolTip(_("Copy the first response as Markdown"))
        copy_md_btn.clicked.connect(self.copy_first_response)
        header.addWidget(copy_md_btn, 0, QtCore.Qt.AlignmentFlag.AlignTop)

        header.addLayout(self._build_zoom_controls(), 0)
        return header

    def open_rewrites(self):
        """The reader links back to Rewrites with its own entry selected."""
        opener = getattr(self.app, "show_history", None)
        if opener is None:
            return
        entry_id = getattr(self, "history_id", None)
        if entry_id is None:
            opener()
        else:
            opener(entry_id)

    def _build_zoom_controls(self):
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(2)

        zoom_label = QtWidgets.QLabel(_("Zoom"))
        zoom_label.setObjectName("Meta")
        row.addWidget(zoom_label)
        row.addSpacing(4)

        zoom_controls = [
            ('plus', _("Zoom in"), 'in'),
            ('minus', _("Zoom out"), 'out'),
            ('reset', _("Reset zoom"), 'reset'),
        ]
        for icon_name, label, action in zoom_controls:
            btn = QtWidgets.QPushButton()
            btn.setObjectName("ghost")
            btn.setIcon(_icon(icon_name))
            btn.setFixedSize(28, 28)
            btn.setToolTip(label)
            btn.setAccessibleName(label)
            btn.clicked.connect(lambda checked=False, a=action: self.zoom_all_messages(a))
            row.addWidget(btn)
        return row

    def _build_input_row(self):
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(8)

        self.input_field = QtWidgets.QLineEdit()
        self.input_field.setPlaceholderText(_("Ask a follow-up question") + '...')
        self.input_field.setAccessibleName(_("Follow-up question"))
        self.input_field.returnPressed.connect(self.send_message)
        row.addWidget(self.input_field, 1)

        send_button = QtWidgets.QPushButton()
        send_button.setObjectName("primary")
        send_button.setIcon(_icon('send'))
        send_button.setFixedSize(36, 36)
        send_button.setToolTip(_("Send follow-up"))
        send_button.setAccessibleName(_("Send follow-up"))
        send_button.clicked.connect(self.send_message)
        row.addWidget(send_button)
        return row

    def get_first_response_text(self):
        """Get the first model response text from chat history"""
        try:
            if not self.chat_history:
                return None

            for msg in self.chat_history:
                if msg["role"] == "assistant":
                    return msg["content"]

            return None
        except Exception as e:
            logging.error(f"Error getting first response: {e}")
            return None

    def copy_first_response(self):
        """Copy only the first model response as Markdown"""
        response_text = self.get_first_response_text()
        if response_text:
            QtWidgets.QApplication.clipboard().setText(response_text)

    def update_thinking_dots(self):
        """Update the thinking animation dots with proper cycling"""
        self.thinking_dots_state = (self.thinking_dots_state + 1) % len(self.thinking_dots)
        dots = self.thinking_dots[self.thinking_dots_state]

        if self.loading_label.isVisible():
            self.loading_label.setText(_("Thinking") + f"{dots}")
        else:
            self.input_field.setPlaceholderText(_("Thinking") + f"{dots}")

    def start_thinking_animation(self, initial=False):
        """Start the thinking animation for either initial load or follow-up questions"""
        self.thinking_dots_state = 0
        self.status_container.hide()

        if initial:
            self.loading_label.setText(_("Thinking"))
            self.loading_label.setVisible(True)
            self.loading_container.setVisible(True)
        else:
            self.input_field.setPlaceholderText(_("Thinking"))
            self.loading_container.setVisible(False)

        self.thinking_timer.start()

    def stop_thinking_animation(self):
        """Stop the thinking animation"""
        self.thinking_timer.stop()
        self.loading_container.hide()
        self.loading_label.hide()
        self.input_field.setPlaceholderText(_("Ask a follow-up question"))
        self.input_field.setEnabled(True)

        if self.layout():
            self.layout().invalidate()
            self.layout().activate()

    def show_failure(self, title, body):
        """Stop the thinking state and show an empty or error message in its place."""
        self.awaiting_initial_response = False
        self.thinking_timer.stop()
        self.loading_label.hide()
        self.loading_container.hide()
        self.status_title.setText(title)
        self.status_body.setText(body)
        self.status_container.show()
        self.input_field.setPlaceholderText(_("Ask a follow-up question"))
        self.input_field.setEnabled(True)

    def zoom_all_messages(self, action='in'):
        """Apply zoom action to all messages in the chat"""
        for i in range(self.chat_area.layout.count() - 1):
            item = self.chat_area.layout.itemAt(i)
            if item and item.widget():
                text_display = item.widget().layout().itemAt(0).widget()
                if isinstance(text_display, MarkdownTextBrowser):
                    if action == 'in':
                        text_display.zoom_in()
                    elif action == 'out':
                        text_display.zoom_out()
                    else:
                        text_display.reset_zoom()

        self.chat_area.update_content_height()

    def _adjust_window_height(self):
        """Calculate and set the ideal window height"""
        if hasattr(self, '_size_initialized'):
            return

        try:
            content_height = self.chat_area.content_widget.sizeHint().height()

            ui_elements_height = (
                self.layout().contentsMargins().top() +
                self.layout().contentsMargins().bottom() +
                self.input_field.height() +
                self.layout().spacing() * 5 +
                200
            )

            screen = QtWidgets.QApplication.screenAt(self.pos())
            if not screen:
                screen = QtWidgets.QApplication.primaryScreen()

            max_height = int(screen.geometry().height() * 0.85)

            desired_content_height = int(content_height * 0.85)
            desired_total_height = min(
                desired_content_height + ui_elements_height,
                max_height
            )

            final_height = max(460, desired_total_height)
            final_width = 600

            self.resize(final_width, final_height)

            frame_geometry = self.frameGeometry()
            screen_center = screen.geometry().center()
            frame_geometry.moveCenter(screen_center)
            self.move(frame_geometry.topLeft())

            self._size_initialized = True

        except Exception as e:
            logging.error(f"Error adjusting window height: {e}")
            self.resize(600, 600)
            self._size_initialized = True

    @Slot(str, str)
    def handle_app_message(self, title, message):
        """Show a provider failure in the window, since the worker never delivers text to it."""
        if self.awaiting_initial_response and title.startswith('Error'):
            self.show_failure(_("Couldn't get a response"), message)

    @Slot(str)
    def set_text(self, text):
        """Set initial response text, or show the empty state when the model returned nothing."""
        self.awaiting_initial_response = False
        if not text or not text.strip():
            self.show_failure(
                _("No response came back"),
                _("The model returned an empty reply. Close this window and try again."),
            )
            return

        self.chat_history = [
            {"role": "user", "content": f"{self.option}: {self.selected_text}"},
            {"role": "assistant", "content": text}
        ]

        self.stop_thinking_animation()
        text_display = self.chat_area.add_message(text)

        if hasattr(self.app.config, 'response_window_zoom'):
            text_display.zoom_factor = self.app.config['response_window_zoom']
            text_display._apply_zoom()

        QtCore.QTimer.singleShot(100, self._adjust_window_height)

    @Slot(str)
    def handle_followup_response(self, response_text):
        """Handle the follow-up response from the AI with improved layout handling"""
        if response_text:
            self.loading_label.setVisible(False)
            text_display = self.chat_area.add_message(response_text)

            if hasattr(self, 'current_text_display'):
                text_display.zoom_factor = self.current_text_display.zoom_factor
                text_display._apply_zoom()

            if len(self.chat_history) > 0 and self.chat_history[-1]["role"] != "assistant":
                self.chat_history.append({
                    "role": "assistant",
                    "content": response_text
                })

        self.stop_thinking_animation()
        self.input_field.setEnabled(True)

        QtCore.QTimer.singleShot(100, self._adjust_window_height)

    def send_message(self):
        """Send a new message/question"""
        message = self.input_field.text().strip()
        if not message:
            return

        self.input_field.setEnabled(False)
        self.input_field.clear()

        text_display = self.chat_area.add_message(message, is_user=True)
        if hasattr(self, 'current_text_display'):
            text_display.zoom_factor = self.current_text_display.zoom_factor
            text_display._apply_zoom()

        self.chat_history.append({"role": "user", "content": message})
        self.start_thinking_animation()
        self.app.process_followup_question(self, message)

    def copy_as_markdown(self):
        """Copy conversation as Markdown"""
        markdown = ""
        for msg in self.chat_history:
            if msg["role"] == "user":
                markdown += f"**User**: {msg['content']}\n\n"
            else:
                markdown += f"**Assistant**: {msg['content']}\n\n"

        QtWidgets.QApplication.clipboard().setText(markdown)

    def closeEvent(self, event):
        """Handle window close event"""
        if hasattr(self, 'current_text_display'):
            self.app.config['response_window_zoom'] = self.current_text_display.zoom_factor
            self.app.save_config(self.app.config)

        self.chat_history = []

        if hasattr(self.app, 'current_response_window'):
            delattr(self.app, 'current_response_window')

        super().closeEvent(event)
