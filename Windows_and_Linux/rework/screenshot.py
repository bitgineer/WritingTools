"""Render the receipt states to PNG without a visible desktop.

    python -m rework.screenshot --theme light
    python -m rework.screenshot --theme dark
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtGui, QtWidgets

from rework.demo import DemoWindow
from rework.theme import DARK, LIGHT


def _compose(window: DemoWindow, card, path: Path) -> None:
    canvas = window.grab()
    overlay = card.grab()
    painter = QtGui.QPainter(canvas)
    origin = QtCore.QPoint(
        window.width() - card.width() - 20,
        window.height() - card.height() - 20,
    )
    painter.drawPixmap(origin, overlay)
    painter.end()
    canvas.save(str(path))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--theme", choices=("light", "dark"), default="light")
    parser.add_argument("--example", choices=("small", "large"), default="small")
    parser.add_argument(
        "--out-dir",
        default=str(Path(__file__).resolve().parents[2] / "design" / "qt"),
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    app = QtWidgets.QApplication([sys.argv[0]])
    window = DemoWindow(palette=DARK if args.theme == "dark" else LIGHT)
    window.show()
    window.run_example(args.example)
    QtWidgets.QApplication.processEvents()
    suffix = f"{args.example}-{args.theme}"

    def capture_compact() -> None:
        card = window.controller._card
        if card is None:
            app.quit()
            return
        card.grab().save(str(out_dir / f"receipt-compact-{suffix}.png"))
        _compose(window, card, out_dir / f"context-compact-{suffix}.png")
        card.expand()
        QtCore.QTimer.singleShot(450, capture_review)

    def capture_review() -> None:
        card = window.controller._card
        if card is None:
            app.quit()
            return
        card.grab().save(str(out_dir / f"receipt-review-{suffix}.png"))
        _compose(window, card, out_dir / f"context-review-{suffix}.png")
        window.controller.dismiss()
        window.run_example("large" if args.example == "small" else "small")
        QtCore.QTimer.singleShot(450, capture_history)

    def capture_history() -> None:
        window.controller.dismiss()
        window.show_history()
        if window.history_window is None:
            app.quit()
            return
        QtCore.QTimer.singleShot(450, save_history)

    def save_history() -> None:
        window.history_window.grab().save(
            str(out_dir / f"history-{args.theme}.png")
        )
        app.quit()

    QtCore.QTimer.singleShot(450, capture_compact)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
