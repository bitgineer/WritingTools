import webbrowser

from PySide6 import QtCore, QtWidgets

from ui.UIUtils import UIUtils
from ui.design import GAP, PAGE_MARGIN, ghost_button, primary_button, section_card
from update_checker import CURRENT_VERSION

_ = lambda x: x

REPO_URL = "https://github.com/theJayTea/WritingTools"
RELEASES_URL = "https://github.com/theJayTea/WritingTools/releases"
BLISS_AI_URL = "https://play.google.com/store/apps/details?id=com.jesai.blissai"
MACOS_PORT_URL = "https://github.com/theJayTea/WritingTools#-macos"
MACOS_AUTHOR_URL = "https://github.com/Aryamirsepasi"


def _contributors():
    return [
        (
            "momokrono",
            "https://github.com/momokrono",
            _("Added Linux support, switched to the pynput API to improve Windows stability. "
              "Added Ollama API support, core logic for customizable buttons, and localization. "
              "Fixed misc. bugs and added graceful termination support by handling SIGINT signal."),
        ),
        (
            "Cameron Redmore (CameronRedmore)",
            "https://github.com/CameronRedmore",
            _("Extensively refactored Writing Tools and added OpenAI Compatible API support, "
              "streamed responses, and the text generation mode when no text is selected."),
        ),
        (
            "Soszust40 (Soszust40)",
            "https://github.com/Soszust40",
            _("Helped add dark mode, tray menu fixes, and UI improvements."),
        ),
        (
            "Alok Saboo (arsaboo)",
            "https://github.com/arsaboo",
            _("Helped improve the reliability of text selection."),
        ),
        (
            "raghavdhingra24",
            "https://github.com/raghavdhingra24",
            _("Made the rounded corners anti-aliased and prettier."),
        ),
        (
            "ErrorCatDev",
            "https://github.com/ErrorCatDev",
            _("Significantly improved the About window, making it scrollable and cleaning things up. "
              "Also improved our .gitignore and requirements.txt."),
        ),
        (
            "Vadim Karpenko",
            "https://github.com/Vadim-Karpenko",
            _("Helped add the start-on-boot setting."),
        ),
    ]


def _link_button(text, url, accessible_name=None):
    button = QtWidgets.QPushButton(text)
    button.setObjectName("link")
    button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
    button.setAccessibleName(accessible_name or text)
    button.clicked.connect(lambda: webbrowser.open(url))
    return button


def _inline_row(parts):
    """Lay out plain text and (text, url) link pairs on one line."""
    row = QtWidgets.QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(2)
    for part in parts:
        if isinstance(part, tuple):
            row.addWidget(_link_button(*part), 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        else:
            row.addWidget(QtWidgets.QLabel(part))
    row.addStretch(1)
    return row


class AboutWindow(QtWidgets.QWidget):
    """
    The about window for the application.
    """
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        """
        Initialize the user interface for the about window.
        """
        self.setWindowTitle(_("About Writing Tools"))
        self.setAccessibleName(_("About Writing Tools"))
        self.setMinimumWidth(640)
        self.setMaximumWidth(720)
        self.setGeometry(300, 300, 680, 640)

        screen = QtWidgets.QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

        UIUtils.setup_window_and_layout(self)

        # Disable minimize button while keeping the normal close affordance.
        self.setWindowFlags(
            self.windowFlags()
            & ~QtCore.Qt.WindowMinimizeButtonHint
            & ~QtCore.Qt.WindowSystemMenuHint
            | QtCore.Qt.WindowCloseButtonHint
            | QtCore.Qt.WindowTitleHint
        )

        content_layout = QtWidgets.QVBoxLayout(self.background)
        content_layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        content_layout.setSpacing(GAP)

        title_label = QtWidgets.QLabel(_("About Writing Tools"))
        title_label.setObjectName("PageTitle")
        content_layout.addWidget(title_label)

        version_label = QtWidgets.QLabel(_("Version {version}").format(version=CURRENT_VERSION))
        version_label.setObjectName("Meta")
        content_layout.addWidget(version_label)

        description_label = QtWidgets.QLabel(_(
            "Writing Tools is a free, lightweight tool that helps you improve your writing with AI, "
            "similar to Apple Intelligence. It works with many AI models, both online and running locally."
        ))
        description_label.setObjectName("PageSubtitle")
        description_label.setWordWrap(True)
        content_layout.addWidget(description_label)

        content_layout.addSpacing(GAP)

        body = QtWidgets.QWidget()
        body_layout = QtWidgets.QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(GAP)

        body_layout.addWidget(self._author_card())
        body_layout.addWidget(self._contributors_card())
        body_layout.addWidget(self._links_card())
        body_layout.addStretch(1)

        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll_area.setAccessibleName(_("About details"))
        scroll_area.setWidget(body)
        content_layout.addWidget(scroll_area, 1)

        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(GAP)
        actions.addStretch(1)

        source_button = QtWidgets.QPushButton(_("View source"))
        source_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        source_button.setMinimumHeight(32)
        source_button.clicked.connect(lambda: self.original_app())
        actions.addWidget(source_button)

        update_button = primary_button(_("See the latest release"))
        update_button.clicked.connect(lambda: self.check_for_updates())
        actions.addWidget(update_button)

        content_layout.addLayout(actions)

    def _author_card(self):
        frame, layout = section_card(_("Author"))
        layout.addWidget(QtWidgets.QLabel(_("Created with care by Jesai, a high school student.")))
        layout.addWidget(QtWidgets.QLabel(_("Contact") + ": jesaitarun@gmail.com"))
        layout.addLayout(_inline_row([
            _("Also try") + " ",
            ("Bliss AI", BLISS_AI_URL),
            ", " + _("a free AI tutor on Google Play."),
        ]))
        return frame

    def _contributors_card(self):
        frame, layout = section_card(_("Contributors"))
        intro = QtWidgets.QLabel(_("Writing Tools would not be where it is today without its amazing contributors."))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        for name, url, description in _contributors():
            header = QtWidgets.QHBoxLayout()
            header.setSpacing(GAP)
            name_label = QtWidgets.QLabel(name)
            name_label.setObjectName("SectionTitle")
            header.addWidget(name_label)
            header.addStretch(1)
            header.addWidget(_link_button("GitHub", url, accessible_name=f"{name} on GitHub"))
            layout.addLayout(header)

            description_label = QtWidgets.QLabel(description)
            description_label.setWordWrap(True)
            layout.addWidget(description_label)
        return frame

    def _links_card(self):
        frame, layout = section_card(_("Links"))
        layout.addLayout(_inline_row([
            _("Mac version") + ": ",
            (_("Writing Tools for macOS"), MACOS_PORT_URL),
            " " + _("by") + " ",
            ("Arya Mirsepasi", MACOS_AUTHOR_URL),
        ]))
        layout.addLayout(_inline_row([
            (_("Source on GitHub"), REPO_URL),
        ]))
        return frame

    def check_for_updates(self):
        """
        Open the GitHub releases page to check for updates.
        """
        webbrowser.open(RELEASES_URL)

    def original_app(self):
        """
        Open the source repository on GitHub.
        """
        webbrowser.open(REPO_URL)
