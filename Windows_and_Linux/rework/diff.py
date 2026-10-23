"""Word-level diff for a single AI rework.

The diff is computed from the two strings the app already has: the captured
selection and the model output. Nothing here reads the source application or
touches disk.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re

EQUAL = "equal"
DELETE = "delete"
INSERT = "insert"

_TOKEN_RE = re.compile(
    r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]"
    r"|[\w\u0300-\u036f]+(?:['\u2019\-][\w\u0300-\u036f]+)*"
    r"|[^\s\w]|\s+"
)


@dataclass(frozen=True)
class DiffSpan:
    """A run of text that is unchanged, removed, or added."""

    kind: str
    text: str


@dataclass(frozen=True)
class ChangeStats:
    """Receipt-sized numbers derived from the diff."""

    edits: int
    changed_words: int
    removed_words: int
    added_words: int

    @property
    def has_changes(self) -> bool:
        return self.edits > 0


@dataclass(frozen=True)
class WordDiff:
    original: str
    revised: str
    spans: tuple[DiffSpan, ...]
    stats: ChangeStats

    def original_text(self) -> str:
        """Reconstruct the original text from unchanged and deleted spans."""
        return "".join(s.text for s in self.spans if s.kind in (EQUAL, DELETE))

    def revised_text(self) -> str:
        """Reconstruct the revised text from unchanged and inserted spans."""
        return "".join(s.text for s in self.spans if s.kind in (EQUAL, INSERT))


def tokenize(text: str) -> list[str]:
    """Split text into words, punctuation, and whitespace runs.

    Whitespace is kept so that concatenating the tokens reproduces the input
    byte for byte. CJK characters and emoji fall through as single-character
    tokens, which still gives a readable diff.
    """
    return _TOKEN_RE.findall(text)


def _word_count(tokens: list[str]) -> int:
    """Count tokens that carry a letter or digit, ignoring punctuation."""
    return sum(1 for token in tokens if any(ch.isalnum() for ch in token))


def diff_words(original: str, revised: str) -> WordDiff:
    """Return an inline, word-level diff between two strings."""
    original_tokens = tokenize(original)
    revised_tokens = tokenize(revised)
    matcher = SequenceMatcher(None, original_tokens, revised_tokens, autojunk=False)

    spans: list[DiffSpan] = []
    edits = changed = removed = added = 0

    def push(kind: str, tokens: list[str]) -> None:
        if not tokens:
            return
        text = "".join(tokens)
        if spans and spans[-1].kind == kind:
            spans[-1] = DiffSpan(kind, spans[-1].text + text)
        else:
            spans.append(DiffSpan(kind, text))

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        old = original_tokens[i1:i2]
        new = revised_tokens[j1:j2]

        if tag == "equal":
            push(EQUAL, old)
        elif tag == "delete":
            push(DELETE, old)
            edits += 1
            removed += _word_count(old)
            changed += _word_count(old)
        elif tag == "insert":
            push(INSERT, new)
            edits += 1
            added += _word_count(new)
            changed += _word_count(new)
        elif tag == "replace":
            push(DELETE, old)
            push(INSERT, new)
            edits += 1
            old_words = _word_count(old)
            new_words = _word_count(new)
            removed += old_words
            added += new_words
            changed += max(old_words, new_words)

    return WordDiff(
        original=original,
        revised=revised,
        spans=tuple(spans),
        stats=ChangeStats(
            edits=edits,
            changed_words=changed,
            removed_words=removed,
            added_words=added,
        ),
    )
