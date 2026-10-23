"""Owns the one receipt that may be on screen.

The controller holds no history. Presenting a second rework closes the first;
dismissing clears the only reference to the text.
"""

from __future__ import annotations

import logging
from typing import Callable, Protocol

from PySide6 import QtCore
from PySide6.QtGui import QCursor

from rework.model import Rework


class Receipt(Protocol):
    def show_near(self, position) -> None: ...
    def close(self) -> None: ...


CardFactory = Callable[[Rework, Callable[[], None], Callable[[], None], bool], Receipt]
UndoHandler = Callable[[Rework], None]
SaveHandler = Callable[[Rework], bool]


class ReworkController:
    def __init__(
        self,
        card_factory: CardFactory,
        undo: UndoHandler | None = None,
        save: SaveHandler | None = None,
    ):
        self._card_factory = card_factory
        self._undo = undo
        self._save = save
        self._card: Receipt | None = None
        self.current: Rework | None = None

    def present(
        self,
        option: str,
        original: str,
        revised: str,
        anchor: QtCore.QPoint | None = None,
    ) -> Rework | None:
        """Show a receipt for this rework. No visible change means no receipt."""
        rework = Rework.create(option, original, revised)
        if not rework.has_changes:
            logging.debug("Rework had no visible changes; clearing receipt")
            self.dismiss()
            return None

        saved = False
        if self._save is not None:
            try:
                saved = bool(self._save(rework))
            except Exception:
                logging.exception("Could not save the rework to history")

        self.dismiss()
        self.current = rework
        card = self._card_factory(
            rework, self._on_undo, lambda: self._on_close(card), saved
        )
        self._card = card
        card.show_near(anchor if anchor is not None else QCursor.pos())
        logging.debug(
            "Rework receipt shown: option=%s changed_words=%d edits=%d",
            option,
            rework.diff.stats.changed_words,
            rework.diff.stats.edits,
        )
        return rework

    def dismiss(self) -> None:
        card, self._card = self._card, None
        self.current = None
        if card is not None:
            logging.debug("Rework receipt dismissed")
            card.close()

    def _on_close(self, card: Receipt) -> None:
        if self._card is not card:
            return
        self._card = None
        self.current = None

    def _on_undo(self) -> None:
        rework = self.current
        self.dismiss()
        if rework is not None and self._undo is not None:
            self._undo(rework)
