"""Standalone demo for the rework receipt.

Run from Windows_and_Linux:
    python -m rework.demo

The demo uses the same diff engine and card as the app. The editor stands in
for the source application: it swaps to the revised text, then the receipt
appears next to it.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from rework.controller import ReworkController
from rework.history import HistoryStore
from rework.review_card import ReworkCard
from rework.theme import DARK, LIGHT, Palette
from ui.HistoryWindow import HistoryWindow

EXAMPLES = {
    "small": {
        "option": "Concise",
        "original": (
            "Hi Dana,\n\n"
            "Thanks for sending the revised budget draft yesterday. I went through it this "
            "morning and I think the forecast for Q3 is a little optimistic, especially the "
            "hiring line, which assumes everyone starts on the first of the month. Could we "
            "talk about it before Friday? I'm free after 2pm on tuesday or wednesday.\n\n"
            "Best,\nJack"
        ),
        "revised": (
            "Hi Dana,\n\n"
            "Thanks for sending the revised budget draft. I reviewed it this morning, and the "
            "Q3 forecast looks optimistic, especially the hiring line, which assumes everyone "
            "starts on the first of the month. Could we talk before Friday? I'm free after 2pm "
            "on Tuesday or Wednesday.\n\n"
            "Best,\nJack"
        ),
    },
    "large": {
        "option": "Professional",
        "original": (
            "Hi Dana,\n\n"
            "I wanted to follow up on the budget draft you sent over. There are a few areas that "
            "I think need another look before we send it to the finance team. The hiring "
            "assumptions seem too aggressive, and the travel line does not match what we spent "
            "last quarter. I would like to get your thoughts on both before we lock the numbers.\n\n"
            "Thanks,\nJack"
        ),
        "revised": (
            "Hi Dana,\n\n"
            "Following up on the budget draft. Two areas need another pass before it goes to "
            "finance: the hiring assumptions look too aggressive, and the travel line does not "
            "match last quarter's actuals. I'd like your read on both before we lock the numbers.\n\n"
            "Thanks,\nJack"
        ),
    },
}


class DemoWindow(QtWidgets.QWidget):
    def __init__(self, palette: Palette | None = None):
        super().__init__()
        self._palette = palette or LIGHT
        self._example = "small"
        self._original = ""
        self._temp_dir = tempfile.TemporaryDirectory(prefix="writingtools-demo-")
        self.store = HistoryStore(Path(self._temp_dir.name) / "history.db")
        self.config = {"history_enabled": True}
        self.history_window = None
        self.controller = ReworkController(
            self._make_card,
            undo=self._undo,
            save=self._save,
        )

        self.setWindowTitle("Writing Tools - rework receipt demo")
        self.resize(1080, 760)
        self._build()
        self._apply_theme()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.top_bar = QtWidgets.QFrame()
        self.top_bar.setObjectName("topBar")
        top_layout = QtWidgets.QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(28, 14, 28, 14)
        top_layout.setSpacing(10)

        title = QtWidgets.QLabel("Writing Tools")
        title.setObjectName("demoTitle")
        top_layout.addWidget(title)

        subtitle = QtWidgets.QLabel("Rework receipt")
        subtitle.setObjectName("demoSubtitle")
        top_layout.addWidget(subtitle)
        top_layout.addStretch()

        for label, key in (("Small edits", "small"), ("Larger rewrite", "large")):
            button = QtWidgets.QPushButton(label)
            button.setObjectName("demoButton")
            button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _=False, k=key: self.run_example(k))
            top_layout.addWidget(button)

        history_button = QtWidgets.QPushButton("History")
        history_button.setObjectName("demoButton")
        history_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        history_button.clicked.connect(self.show_history)
        top_layout.addWidget(history_button)

        self.theme_button = QtWidgets.QPushButton("Dark")
        self.theme_button.setObjectName("demoButton")
        self.theme_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.theme_button.clicked.connect(self.toggle_theme)
        top_layout.addWidget(self.theme_button)

        root.addWidget(self.top_bar)

        self.canvas = QtWidgets.QWidget()
        self.canvas.setObjectName("canvas")
        canvas_layout = QtWidgets.QVBoxLayout(self.canvas)
        canvas_layout.setContentsMargins(40, 36, 40, 36)
        canvas_layout.addStretch()

        row = QtWidgets.QHBoxLayout()
        row.addStretch()
        self.document = QtWidgets.QFrame()
        self.document.setObjectName("document")
        self.document.setMaximumWidth(760)
        doc_layout = QtWidgets.QVBoxLayout(self.document)
        doc_layout.setContentsMargins(44, 34, 44, 34)
        doc_layout.setSpacing(14)

        draft = QtWidgets.QLabel("DRAFT")
        draft.setObjectName("draftLabel")
        doc_layout.addWidget(draft)

        self.editor = QtWidgets.QTextEdit()
        self.editor.setObjectName("editor")
        self.editor.setReadOnly(True)
        self.editor.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.editor.setMinimumHeight(360)
        doc_layout.addWidget(self.editor)

        row.addWidget(self.document, 1)
        row.addStretch()
        canvas_layout.addLayout(row)
        canvas_layout.addStretch()
        root.addWidget(self.canvas, 1)

    def _apply_theme(self) -> None:
        p = self._palette
        self.setStyleSheet(
            f"""
            QWidget#canvas {{ background-color: {p.surface_alt}; }}
            QFrame#topBar {{ background-color: {p.surface}; border-bottom: 1px solid {p.hairline}; }}
            QLabel#demoTitle {{ color: {p.ink}; font-size: 15px; font-weight: 700; }}
            QLabel#demoSubtitle {{ color: {p.muted}; font-size: 13px; }}
            QPushButton#demoButton {{
                background-color: transparent; color: {p.muted};
                border: 1px solid {p.hairline}; border-radius: 8px;
                padding: 6px 12px; font-size: 12px;
            }}
            QPushButton#demoButton:hover {{ background-color: {p.surface_alt}; color: {p.ink}; }}
            QFrame#document {{ background-color: {p.surface}; border: 1px solid {p.hairline}; border-radius: 16px; }}
            QLabel#draftLabel {{ color: {p.muted}; font-size: 10px; font-weight: 700; }}
            QTextEdit#editor {{
                background-color: transparent; color: {p.ink};
                font-family: Georgia, "Times New Roman", serif; font-size: 16px;
                selection-background-color: {p.accent_soft};
            }}
            """
        )
        self.theme_button.setText("Light" if self._palette.mode == "dark" else "Dark")

    def toggle_theme(self) -> None:
        self._palette = DARK if self._palette.mode == "light" else LIGHT
        self._apply_theme()
        self.run_example(self._example)

    def _make_card(self, rework, on_undo, on_close, saved):
        return ReworkCard(
            rework,
            on_undo,
            on_close,
            saved_to_history=saved,
            palette=self._palette,
        )

    def _save(self, rework):
        self.store.add(rework)
        return True

    def show_history(self):
        if self.history_window is None:
            self.history_window = HistoryWindow(
                self.store,
                self.config,
                on_config_change=self._config_changed,
                palette=self._palette,
            )
        self.history_window.show_window()

    def _config_changed(self, config):
        self.config = config

    def _anchor(self) -> QtCore.QPoint:
        corner = self.editor.mapToGlobal(
            QtCore.QPoint(self.editor.width() - 64, min(self.editor.height() - 42, 320))
        )
        return corner

    def run_example(self, key: str) -> None:
        example = EXAMPLES[key]
        self._example = key
        self._original = example["original"]
        self.controller.dismiss()
        self.editor.setPlainText(example["original"])
        QtWidgets.QApplication.processEvents()
        self.editor.setPlainText(example["revised"])
        self.controller.present(
            example["option"],
            example["original"],
            example["revised"],
            anchor=self._anchor(),
        )

    def _undo(self, rework) -> None:
        self.editor.setPlainText(rework.original)


def main() -> int:
    app = QtWidgets.QApplication([sys.argv[0]])
    window = DemoWindow()
    window.show()
    window.run_example("small")
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
