"""The in-memory record of one rework.

There is deliberately no persistence layer here. A Rework lives only as long
as its receipt is on screen.
"""

from __future__ import annotations

from dataclasses import dataclass

from rework.diff import DELETE, EQUAL, INSERT, WordDiff, diff_words, tokenize


@dataclass(frozen=True)
class ChangeSample:
    old: str
    new: str


@dataclass(frozen=True)
class Rework:
    option: str
    original: str
    revised: str
    diff: WordDiff

    @classmethod
    def create(cls, option: str, original: str, revised: str) -> "Rework":
        return cls(
            option=option,
            original=original,
            revised=revised,
            diff=diff_words(original, revised),
        )

    @property
    def has_changes(self) -> bool:
        return self.diff.stats.has_changes

    @property
    def is_substantial(self) -> bool:
        """True when word marks would be noisier than reading both texts."""
        words = sum(1 for token in tokenize(self.original) if any(ch.isalnum() for ch in token))
        if words == 0:
            return bool(self.revised.strip())
        return self.diff.stats.changed_words >= 6 and self.diff.stats.changed_words / words >= 0.4

    def headline(self) -> str:
        """The compact receipt's count, e.g. '8 words changed'."""
        words = self.diff.stats.changed_words
        if words:
            return f"{words} word{'s' if words != 1 else ''} changed"
        if self.diff.stats.edits:
            return "Punctuation and spacing updated"
        return "No visible changes"

    def detail(self) -> str:
        """The expanded review's secondary count."""
        stats = self.diff.stats
        parts = []
        if stats.removed_words:
            parts.append(f"{stats.removed_words} removed")
        if stats.added_words:
            parts.append(f"{stats.added_words} added")
        if not parts:
            parts.append(f"{stats.edits} edit{'s' if stats.edits != 1 else ''}")
        return " \u00b7 ".join(parts)

    def sample_changes(self, limit: int = 2, width: int = 34) -> tuple[ChangeSample, ...]:
        """The first few edits, short enough for the compact receipt."""
        samples: list[ChangeSample] = []
        old_parts: list[str] = []
        new_parts: list[str] = []

        def flush() -> None:
            old = _short("".join(old_parts), width)
            new = _short("".join(new_parts), width)
            old_parts.clear()
            new_parts.clear()
            if old or new:
                samples.append(ChangeSample(old=old, new=new))

        for span in self.diff.spans:
            if span.kind == EQUAL:
                flush()
            elif span.kind == DELETE:
                old_parts.append(span.text)
            elif span.kind == INSERT:
                new_parts.append(span.text)
        flush()
        return tuple(samples[:limit])


def _short(text: str, width: int) -> str:
    text = " ".join(text.split())
    if len(text) <= width:
        return text
    return text[: width - 1].rstrip() + "\u2026"
