import logging

from PySide6 import QtCore, QtWidgets

from ui.UIUtils import UIUtils
from ui.design import GAP, divider, field_label, primary_button

_ = lambda x: x

DEFAULT_SHORTCUT = 'ctrl+space'
MARGIN = 32


class OnboardingWindow(QtWidgets.QWidget):
    # Closing signal
    close_signal = QtCore.Signal()

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.shortcut = DEFAULT_SHORTCUT
        self.content_layout = None
        self.shortcut_input = None
        self.self_close = False
        self.init_ui()

    def init_ui(self):
        logging.debug('Initializing onboarding UI')
        self.setWindowTitle(_('Welcome to Writing Tools'))
        self.setAccessibleName(_('Welcome to Writing Tools'))
        self.setMinimumWidth(640)
        self.setMaximumWidth(720)
        self.resize(680, 600)

        UIUtils.setup_window_and_layout(self)

        self.content_layout = QtWidgets.QVBoxLayout(self.background)
        self.content_layout.setContentsMargins(MARGIN, MARGIN, MARGIN, MARGIN)
        self.content_layout.setSpacing(GAP)

        self.show_welcome_screen()

    def show_welcome_screen(self):
        layout = self.content_layout

        step_label = QtWidgets.QLabel(_("Step 1 of 2"))
        step_label.setObjectName("Meta")
        layout.addWidget(step_label)

        title_label = QtWidgets.QLabel(_("Welcome to Writing Tools"))
        title_label.setObjectName("hero")
        layout.addWidget(title_label)

        intro_label = QtWidgets.QLabel(_(
            "Writing Tools brings AI to any app you write in. Use Google Gemini, "
            "any OpenAI-compatible API, or a local model. You will add a provider next."
        ))
        intro_label.setObjectName("lead")
        intro_label.setWordWrap(True)
        layout.addWidget(intro_label)

        layout.addSpacing(GAP)

        features = [
            (
                _("Rework selected text"),
                _("Select text in any app, press your shortcut, then choose Proofread, Rewrite, or another action."),
            ),
            (
                _("Summarize articles and videos"),
                _("Select a full article or YouTube transcript, press your shortcut, and choose Summary."),
            ),
            (
                _("Ask for a custom change"),
                _("Describe the change you want in the popup, then press Enter."),
            ),
        ]
        for number, (feature_title, feature_body) in enumerate(features, start=1):
            layout.addLayout(self._feature_row(number, feature_title, feature_body))

        layout.addSpacing(GAP)
        layout.addWidget(divider())
        layout.addSpacing(GAP)

        shortcut_label = field_label(_("Shortcut"))
        layout.addWidget(shortcut_label)

        self.shortcut_input = QtWidgets.QLineEdit(self.shortcut)
        self.shortcut_input.setAccessibleName(_("Shortcut"))
        self.shortcut_input.setAccessibleDescription(_("Example: ctrl+space"))
        self.shortcut_input.returnPressed.connect(lambda: self.on_next_clicked())
        shortcut_label.setBuddy(self.shortcut_input)
        layout.addWidget(self.shortcut_input)

        shortcut_hint = QtWidgets.QLabel(_("Example: ctrl+space or ctrl+alt+j. Use + between keys."))
        shortcut_hint.setObjectName("Hint")
        shortcut_hint.setWordWrap(True)
        layout.addWidget(shortcut_hint)

        layout.addStretch(1)

        actions = QtWidgets.QHBoxLayout()
        actions.addStretch(1)
        continue_button = primary_button(_("Continue"))
        continue_button.clicked.connect(lambda: self.on_next_clicked())
        actions.addWidget(continue_button)
        layout.addLayout(actions)

        self.shortcut_input.setFocus()

    def _feature_row(self, number, feature_title, feature_body):
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(GAP)

        badge = QtWidgets.QLabel(str(number))
        badge.setObjectName("badge")
        badge.setFixedSize(28, 28)
        badge.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        row.addWidget(badge, 0, QtCore.Qt.AlignmentFlag.AlignTop)

        text_column = QtWidgets.QVBoxLayout()
        text_column.setSpacing(2)

        title_label = QtWidgets.QLabel(feature_title)
        title_label.setObjectName("SectionTitle")
        text_column.addWidget(title_label)

        body_label = QtWidgets.QLabel(feature_body)
        body_label.setWordWrap(True)
        text_column.addWidget(body_label)

        row.addLayout(text_column, 1)
        return row

    def on_next_clicked(self):
        self.shortcut = self.shortcut_input.text().strip() or DEFAULT_SHORTCUT
        error = self.app.validate_shortcut(self.shortcut)
        if error:
            QtWidgets.QMessageBox.warning(self, _("Shortcut not valid"), error)
            self.shortcut_input.setFocus()
            return
        logging.debug(f'User selected shortcut: {self.shortcut}')
        config = dict(self.app.config or {})
        config.pop('theme', None)
        config['shortcut'] = self.shortcut
        self.app.config = config
        self.show_api_key_input()

    def show_api_key_input(self):
        self.app.show_settings(providers_only=True)
        self.self_close = True
        self.close()

    def closeEvent(self, event):
        # Emit the close signal
        if not self.self_close:
            self.close_signal.emit()
        super().closeEvent(event)
