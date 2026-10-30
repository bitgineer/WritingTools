"""Turn provider exceptions into short, actionable messages.

The raw SDK error often carries a wall of JSON. The writer needs the cause
and the next step, not the payload.
"""

from __future__ import annotations


def _status(error) -> int | None:
    value = getattr(error, "status_code", None)
    if isinstance(value, int):
        return value
    response = getattr(error, "response", None)
    value = getattr(response, "status_code", None)
    if isinstance(value, int):
        return value
    return None


def describe(error, model: str = "") -> tuple[str, str]:
    """Return (title, message) for a provider failure."""
    text = str(error)
    lower = text.lower()
    status = _status(error)

    if "agentic harness" in lower or "only available on" in lower:
        target = f"'{model}'" if model else "this model"
        return (
            "Model not available",
            f"The provider limits {target} to specific partner apps. "
            "Choose a standard model in Settings, or use a paid variant. "
            "The model field accepts any id your account can use.",
        )
    if status == 401 or "invalid api key" in lower or "incorrect api key" in lower or "unauthorized" in lower:
        return (
            "API key rejected",
            "The provider did not accept the API key. Check it in Settings and try again.",
        )
    if status == 403:
        return (
            "Access denied",
            "The provider refused this request. Check the model name and your plan, "
            "or choose a different model.",
        )
    if status == 404 or "model not found" in lower or "does not exist" in lower:
        return (
            "Model not found",
            "The provider does not recognize this model id. Load the model list and "
            "pick one, or check the id.",
        )
    if status == 400 and ("context" in lower or "too long" in lower):
        return (
            "Selection too long",
            "The selected text is longer than this model accepts. Select less text or "
            "choose a model with a larger context.",
        )
    if status == 429 or "rate limit" in lower or ("exceeded" in lower and status not in (400,)):
        return (
            "Rate limit hit",
            "The provider is rate limiting this key. Wait a moment, or switch models "
            "in Settings.",
        )

    snippet = " ".join(text.split())
    if len(snippet) > 300:
        snippet = snippet[:299].rstrip() + "\u2026"
    return ("Provider error", snippet or "The provider returned an error.")
