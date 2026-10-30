"""Small display helpers shared by Rewrites and Home."""

from __future__ import annotations

from datetime import datetime, timezone


def format_time(value: str) -> str:
    try:
        moment = datetime.fromisoformat(value)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return moment.astimezone().strftime("%b %d, %Y at %I:%M %p")
    except ValueError:
        return value


def format_age(value: str) -> str:
    try:
        moment = datetime.fromisoformat(value)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        seconds = (datetime.now(timezone.utc) - moment).total_seconds()
    except ValueError:
        return value
    if seconds < 60:
        return "Just now"
    if seconds < 3600:
        return f"{int(seconds // 60)} min ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)} hr ago"
    if seconds < 172800:
        return "Yesterday"
    if seconds < 604800:
        return f"{int(seconds // 86400)} days ago"
    return moment.astimezone().strftime("%b %d, %Y")


def snippet(text: str, width: int = 96) -> str:
    text = " ".join(text.split())
    if len(text) <= width:
        return text
    return text[: width - 1].rstrip() + "\u2026"


def headline(changed_words: int) -> str:
    if changed_words:
        plural = "" if changed_words == 1 else "s"
        return f"{changed_words} word{plural} changed"
    return "Punctuation and spacing updated"
