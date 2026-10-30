"""First-run setup inside Home.

Two steps in one window. Step 1 saves the shortcut. Step 2 saves a working
provider. The ready screen names the exact next action.
"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ui.Components import Banner
from ui.ProviderForm import ProviderForm
from ui.UIUtils import UIUtils
from ui.design import GAP, field_label, primary_button

DEFAULT_SHORTCUT = "ctrl+space"


class SetupWizard(QtWidgets.QFrame):
    finished = QtCore.Signal()
    ready = QtCore.Signal()

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.setObjectName("SetupCard")
        self._step = 1
        self._provider_form: ProviderForm | None = None
        self._build()
        self._show_step(1 if not self._has_provider() else 2)

    def _has_provider(self) -> bool:
        return getattr(self.app, "current_provider", None) is not None

    def _build(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        self.step_label = QtWidgets.QLabel("")
        self.step_label.setObjectName("MetricLabel")
        layout.addWidget(self.step_label)

        self.title = QtWidgets.QLabel("")
        self.title.setObjectName("hero")
        self.title.setWordWrap(True)
        layout.addWidget(self.title)

        self.body = QtWidgets.QLabel("")
        self.body.setObjectName("lead")
        self.body.setWordWrap(True)
        layout.addWidget(self.body)

        self.host = QtWidgets.QWidget()
        self.host_layout = QtWidgets.QVBoxLayout(self.host)
        self.host_layout.setContentsMargins(0, 0, 0, 0)
        self.host_layout.setSpacing(10)
        layout.addWidget(self.host, 1)

        self.error = Banner("", tone="warning")
        self.error.hide()
        layout.addWidget(self.error)

        self.footer = QtWidgets.QHBoxLayout()
        self.footer.setSpacing(8)
        self.footer.addStretch(1)
        layout.addLayout(self.footer)

    def _clear_host(self) -> None:
        UIUtils.clear_layout(self.host_layout)

    def _show_step(self, step: int) -> None:
        self._step = step
        self._clear_host()
        while self.footer.count():
            item = self.footer.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.footer.addStretch(1)
        self.error.hide()

        if step == 1:
            self._build_welcome()
        elif step == 2:
            self._build_provider()
        else:
            self._build_ready()
        QtCore.QTimer.singleShot(0, self.focus_first)

    def _build_welcome(self) -> None:
        self.step_label.setText("Step 1 of 2")
        self.title.setText("A writing desk in every app")
        self.body.setText(
            "Select text anywhere, press your shortcut, and choose what to do. "
            "The revised text lands in place. Nothing else changes."
        )
        features = [
            ("1", "Rewrite in place", "Proofread, rewrite, change tone, or apply your own instruction."),
            ("2", "Review what changed", "A receipt shows the edits. Undo is one action."),
            ("3", "Keep a local history", "Search past rewrites. Nothing leaves this device."),
        ]
        for number, title, body in features:
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(GAP)
            badge = QtWidgets.QLabel(number)
            badge.setObjectName("badge")
            badge.setFixedSize(28, 28)
            badge.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            row.addWidget(badge, 0, QtCore.Qt.AlignmentFlag.AlignTop)
            text = QtWidgets.QVBoxLayout()
            text.setSpacing(1)
            name = QtWidgets.QLabel(title)
            name.setObjectName("SectionTitle")
            text.addWidget(name)
            detail = QtWidgets.QLabel(body)
            detail.setObjectName("Meta")
            detail.setWordWrap(True)
            text.addWidget(detail)
            row.addLayout(text, 1)
            self.host_layout.addLayout(row)

        self.host_layout.addSpacing(6)
        self.host_layout.addWidget(field_label("Shortcut"))
        self.shortcut_input = QtWidgets.QLineEdit(
            (self.app.config or {}).get("shortcut", DEFAULT_SHORTCUT)
        )
        self.shortcut_input.setAccessibleName("Shortcut")
        self.shortcut_input.setPlaceholderText("ctrl+space")
        self.shortcut_input.returnPressed.connect(self._next)
        self.host_layout.addWidget(self.shortcut_input)
        hint = QtWidgets.QLabel("Use + between keys, for example ctrl+space or ctrl+alt+j.")
        hint.setObjectName("FieldHint")
        hint.setWordWrap(True)
        self.host_layout.addWidget(hint)
        self.shortcut_input.setFocus()
        QtCore.QTimer.singleShot(0, self.shortcut_input.setFocus)

        continue_button = primary_button("Continue")
        continue_button.setAccessibleName("Continue")
        continue_button.clicked.connect(self._next)
        self.footer.addWidget(continue_button)

    def _next(self) -> None:
        shortcut = self.shortcut_input.text().strip() or DEFAULT_SHORTCUT
        error = self.app.validate_shortcut(shortcut)
        if error:
            self.error.set_content("Shortcut not valid", error)
            self.error.show()
            self.shortcut_input.setFocus()
            return
        config = self.app.config
        config["shortcut"] = shortcut
        self.app.save_config(config)
        if self._has_provider():
            self._finish()
            return
        self._show_step(2)

    def _build_provider(self) -> None:
        self.step_label.setText("Step 2 of 2")
        self.title.setText("Connect an AI provider")
        self.body.setText(
            "Pick a service and paste its key. The model list loads from the "
            "provider, and the model field stays editable."
        )
        self._provider_form = ProviderForm(
            self.app,
            save_label="Finish setup",
            compact=True,
            on_back=lambda: self._show_step(1),
        )
        self._provider_form.saved.connect(self._finish)
        self.host_layout.addWidget(self._provider_form)

    def _build_ready(self) -> None:
        self.step_label.setText("Ready")
        self.title.setText("You are set up")
        self.body.setText(
            "Select text in any app, then press "
            f"{(self.app.config or {}).get('shortcut', DEFAULT_SHORTCUT)}. "
            "Choose an action in the popup, or type a custom instruction."
        )
        card = QtWidgets.QFrame()
        card.setObjectName("BannerInfo")
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(4)
        next_title = QtWidgets.QLabel("Your first rewrite")
        next_title.setObjectName("SectionTitle")
        card_layout.addWidget(next_title)
        next_body = QtWidgets.QLabel(
            "Open a document or email, select a sentence, and press the shortcut. "
            "The popup appears at the cursor."
        )
        next_body.setObjectName("Meta")
        next_body.setWordWrap(True)
        card_layout.addWidget(next_body)
        self.host_layout.addWidget(card)
        self.host_layout.addStretch(1)
        done = primary_button("Open Home")
        done.clicked.connect(lambda: self.finished.emit())
        self.footer.addWidget(done)

    def _finish(self) -> None:
        self._show_step(3)
        self.ready.emit()

    def focus_first(self) -> None:
        if self._step == 1 and getattr(self, "shortcut_input", None) is not None:
            self.shortcut_input.setFocus()
        elif self._step == 2 and self._provider_form is not None:
            self._provider_form.focus_provider()
