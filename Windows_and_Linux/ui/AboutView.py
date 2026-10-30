"""About: the same credits, as an in-app view."""

from __future__ import annotations

import webbrowser

from PySide6 import QtWidgets

from ui.Components import scroll_page
from ui.design import GAP, ghost_button, section_card
from update_checker import CURRENT_VERSION

REPO_URL = "https://github.com/bitgineer/WritingTools"
RELEASES_URL = "https://github.com/bitgineer/WritingTools/releases"
MACOS_PORT_URL = "https://github.com/theJayTea/WritingTools#-macos"


class AboutView(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        scroll, self.content = scroll_page()
        layout.addWidget(scroll)

        intro, intro_layout = section_card()
        title = QtWidgets.QLabel("Writing Tools")
        title.setObjectName("PageTitle")
        intro_layout.addWidget(title)
        version = QtWidgets.QLabel(f"Version {CURRENT_VERSION}")
        version.setObjectName("MetricLabel")
        intro_layout.addWidget(version)
        body = QtWidgets.QLabel(
            "A free, system-wide writing assistant. Select text in any app, "
            "choose an action, and the revision lands in place."
        )
        body.setObjectName("PageSubtitle")
        body.setWordWrap(True)
        intro_layout.addWidget(body)
        self.content.addWidget(intro)

        author, author_layout = section_card("Author")
        author_layout.addWidget(
            QtWidgets.QLabel("Created with care by Jesai, a high school student.")
        )
        author_layout.addWidget(QtWidgets.QLabel("Contact: jesaitarun@gmail.com"))
        self.content.addWidget(author)

        contributors, contributors_layout = section_card("Contributors")
        people = [
            ("momokrono", "Linux support, pynput, Ollama, customizable actions, localization."),
            ("Cameron Redmore", "Refactor, OpenAI-compatible support, streamed responses."),
            ("Soszust40", "Dark mode, tray fixes, UI improvements."),
            ("Alok Saboo", "Selection reliability."),
            ("raghavdhingra24", "Rounded corners and visual polish."),
            ("ErrorCatDev", "About window, .gitignore, requirements."),
            ("Vadim Karpenko", "Start on boot."),
        ]
        for name, detail in people:
            row = QtWidgets.QVBoxLayout()
            row.setSpacing(1)
            label = QtWidgets.QLabel(name)
            label.setObjectName("SectionTitle")
            row.addWidget(label)
            text = QtWidgets.QLabel(detail)
            text.setObjectName("Meta")
            text.setWordWrap(True)
            row.addWidget(text)
            contributors_layout.addLayout(row)
        self.content.addWidget(contributors)

        links, links_layout = section_card("Links")
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(GAP)
        source = ghost_button("View source")
        source.clicked.connect(lambda: webbrowser.open(REPO_URL))
        row.addWidget(source)
        release = ghost_button("See the latest release")
        release.clicked.connect(lambda: webbrowser.open(RELEASES_URL))
        row.addWidget(release)
        mac = ghost_button("Writing Tools for macOS")
        mac.clicked.connect(lambda: webbrowser.open(MACOS_PORT_URL))
        row.addWidget(mac)
        row.addStretch(1)
        links_layout.addLayout(row)
        self.content.addWidget(links)
        self.content.addStretch(1)
