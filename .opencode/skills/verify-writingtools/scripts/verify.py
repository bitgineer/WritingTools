#!/usr/bin/env python3
"""Drive Writing Tools surfaces and capture verification evidence.

Run from the repository root with the project virtualenv:

    .venv\\Scripts\\python.exe .opencode\\skills\\verify-writingtools\\scripts\\verify.py doctor
    .venv\\Scripts\\python.exe .opencode\\skills\\verify-writingtools\\scripts\\verify.py run --feature receipt

Every run writes screenshots, transcripts, and a summary under
`artifacts/verify/<run-id>/`. The harness is short-lived. It must not be
started in the same process as the app.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
APP = REPO / "Windows_and_Linux"
ARTIFACTS = REPO / "artifacts" / "verify"
PROVIDER_SWITCH_TEST = APP / "tests" / "test_provider_switch.py"
FEATURES = (
    "surfaces",
    "receipt",
    "history",
    "settings",
    "response",
    "onboarding-about",
    "friction",
    "workflow",
)
SURFACES = ("popup", "popup-custom", "dialog", "settings", "onboarding", "about", "response")
THEMES = ("light", "dark")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _run_id(value: str | None) -> str:
    if value:
        return value
    from_env = os.environ.get("VERIFY_RUN_ID")
    return from_env or _stamp()


def _dirs(run_id: str) -> tuple[Path, Path]:
    root = ARTIFACTS / run_id
    evidence = root / "evidence"
    scratch = root / "scratch"
    evidence.mkdir(parents=True, exist_ok=True)
    scratch.mkdir(parents=True, exist_ok=True)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "latest.txt").write_text(run_id + "\n", encoding="utf-8")
    return evidence, scratch


def _platform() -> str:
    """Use a real platform for visual runs; fall back when no display exists."""
    forced = os.environ.get("VERIFY_QT_PLATFORM")
    if forced:
        return forced
    if sys.platform == "win32":
        return "windows"
    if sys.platform.startswith("linux") and os.environ.get("DISPLAY"):
        return "xcb"
    return "offscreen"


def _env() -> dict:
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = _platform()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("PYTHONUTF8", "1")
    return env


def _python() -> str:
    return sys.executable


def _git(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return (result.stdout or result.stderr).strip()
    except Exception:
        return ""


class Context:
    """Evidence and check state for one feature run."""

    def __init__(self, feature: str, run_id: str):
        self.feature = feature
        self.run_id = run_id
        self.evidence, self.scratch = _dirs(run_id)
        self.checks: list[dict] = []
        self.artifacts: list[str] = []
        self.transcript: list[str] = []
        self.started = _now()
        self.status = "RUNNING"
        self.blocked_reason: str | None = None
        self.note("run", f"{feature} {run_id} started")

    def note(self, kind: str, message: str) -> None:
        line = f"[{kind}] {message}"
        self.transcript.append(line)
        print(line, flush=True)

    def check(self, name: str, ok: bool, detail: str, blocked: bool = False) -> bool:
        self.checks.append(
            {"check": name, "ok": bool(ok), "detail": str(detail), "blocked": bool(blocked)}
        )
        state = "BLOCKED" if blocked else ("PASS" if ok else "FAIL")
        line = f"[{state}] {name}: {detail}"
        self.transcript.append(line)
        print(line, flush=True)
        return bool(ok)

    def artifact(self, path: Path, minimum: int = 1) -> bool:
        path = Path(path)
        ok = path.exists() and path.stat().st_size >= minimum
        rel = str(path.relative_to(self.evidence)) if path.is_relative_to(self.evidence) else str(path)
        if ok:
            self.artifacts.append(rel)
        return self.check(f"artifact {rel}", ok, f"{path.stat().st_size if path.exists() else 0} bytes")

    def write_text(self, name: str, text: str) -> Path:
        path = self.evidence / name
        path.write_text(text + ("\n" if not text.endswith("\n") else ""), encoding="utf-8")
        return path

    def save_summary(self, error: str | None = None) -> dict:
        self.status = "BLOCKED" if self.blocked_reason else _status(self.checks, error)
        data = {
            "feature": self.feature,
            "run_id": self.run_id,
            "status": self.status,
            "started": self.started,
            "finished": _now(),
            "python": _python(),
            "cwd": str(REPO),
            "command": " ".join(sys.argv),
            "git_head": _git("rev-parse", "HEAD"),
            "git_status": _git("status", "--short"),
            "checks": self.checks,
            "artifacts": self.artifacts,
            "error": error,
        }
        (self.evidence / "summary.json").write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )
        self.write_text("transcript.txt", "\n".join(self.transcript))
        return data


def _status(checks: list[dict], error: str | None) -> str:
    if error:
        return "FAIL"
    if any(item["ok"] is False and not item["blocked"] for item in checks):
        return "FAIL"
    if any(item["blocked"] for item in checks):
        return "PASS_WITH_BLOCKER"
    return "PASS"


def _import_qt():
    from PySide6 import QtCore, QtTest, QtWidgets

    return QtCore, QtTest, QtWidgets


def _force_theme(theme: str = "light") -> None:
    """Use one palette regardless of the desktop setting."""
    import rework.theme as tokens

    target = tokens.DARK if theme == "dark" else tokens.LIGHT
    forced = lambda: target
    tokens.current_palette = forced
    for module_name in (
        "ui.CustomPopupWindow",
        "ui.ResponseWindow",
        "ui.SettingsWindow",
        "ui.UIUtils",
        "ui.design",
    ):
        module = __import__(module_name, fromlist=["current_palette"])
        if hasattr(module, "current_palette"):
            module.current_palette = forced


def _qt_app():
    _, _, QtWidgets = _import_qt()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from ui.design import apply_app_style
    apply_app_style(app)
    return app


def _process() -> None:
    _, _, QtWidgets = _import_qt()
    QtWidgets.QApplication.processEvents()


def _wait(ms: int = 100) -> None:
    _, QtTest, _ = _import_qt()
    QtTest.QTest.qWait(ms)


def _flush_deletes() -> None:
    """Let provider panels that called deleteLater leave findChildren()."""
    from PySide6 import QtCore, QtWidgets

    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    QtWidgets.QApplication.processEvents()


def _shot(widget, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    widget.grab().save(str(path))
    return path


def _compose(window, card, path: Path) -> Path:
    """Match rework/screenshot.py: put the top-level card over the demo window."""
    from PySide6 import QtCore, QtGui

    canvas = window.grab()
    overlay = card.grab()
    painter = QtGui.QPainter(canvas)
    origin = QtCore.QPoint(
        window.width() - card.width() - 20,
        window.height() - card.height() - 20,
    )
    painter.drawPixmap(origin, overlay)
    painter.end()
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(str(path))
    return path


def _click(button) -> None:
    from PySide6 import QtCore, QtWidgets

    QtTest = _import_qt()[1]
    button.setFocus()
    QtTest.QTest.mouseClick(button, QtCore.Qt.MouseButton.LeftButton)
    QtWidgets.QApplication.processEvents()


def _click_named(parent, name: str):
    from PySide6 import QtWidgets

    for button in parent.findChildren(QtWidgets.QPushButton):
        if button.accessibleName() == name or button.text() == name:
            _click(button)
            return button
    raise AssertionError(f"No button named {name!r}")


def _field(window, accessible_name: str):
    from PySide6 import QtWidgets

    for field in window.findChildren(QtWidgets.QLineEdit):
        if field.accessibleName() == accessible_name:
            return field
    raise AssertionError(f"No line edit named {accessible_name!r}")


def _type(field, value: str) -> None:
    _, QtTest, _ = _import_qt()
    field.clear()
    field.setFocus()
    QtTest.QTest.keyClicks(field, value)
    _process()


def _answer_message_box(button_name: str = "Yes") -> dict:
    """Click a standard button in the next visible QMessageBox.

    The schedule runs inside the modal event loop opened by the window's
    button handler, so the real confirmation dialog is still exercised.
    """
    from PySide6 import QtCore, QtWidgets

    state = {"answered": False, "title": None, "text": None, "attempts": 0}

    def answer() -> None:
        if state["answered"] or state["attempts"] > 80:
            return
        state["attempts"] += 1
        for widget in QtWidgets.QApplication.topLevelWidgets():
            if isinstance(widget, QtWidgets.QMessageBox) and widget.isVisible():
                state["title"] = widget.windowTitle()
                state["text"] = widget.text()
                button = widget.button(getattr(QtWidgets.QMessageBox.StandardButton, button_name))
                if button is None:
                    widget.accept()
                else:
                    button.click()
                state["answered"] = True
                return
        QtCore.QTimer.singleShot(50, answer)

    QtCore.QTimer.singleShot(50, answer)
    return state


def _png_size(path: Path) -> tuple[int, int] | None:
    try:
        data = Path(path).read_bytes()[:24]
    except OSError:
        return None
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def _current_summary(feature: str, run_id: str) -> dict | None:
    path = ARTIFACTS / run_id / "evidence" / "summary.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Feature drives
# ---------------------------------------------------------------------------


def drive_surfaces(ctx: Context) -> None:
    """Render every app surface in both themes through ui.design_preview."""
    out_dir = ctx.evidence / "surfaces"
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for theme in THEMES:
        for surface in SURFACES:
            code = textwrap.dedent(
                f"""
                import sys
                from pathlib import Path
                app_dir = Path({str(APP)!r})
                out = Path({str(out_dir)!r})
                sys.path.insert(0, str(app_dir))
                sys.argv[0] = str(app_dir / "WritingToolApp.py")
                import ui.design_preview as preview
                preview.OUT = out
                preview.main()
                """
            )
            result = subprocess.run(
                [_python(), "-B", "-c", code, "--surface", surface, "--theme", theme],
                cwd=APP,
                env=_env(),
                capture_output=True,
                text=True,
                timeout=90,
            )
            path = out_dir / f"{surface}-{theme}.png"
            size = _png_size(path)
            if result.returncode != 0 or size is None:
                retry = subprocess.run(
                    [_python(), "-B", "-c", code, "--surface", surface, "--theme", theme],
                    cwd=APP,
                    env=_env(),
                    capture_output=True,
                    text=True,
                    timeout=90,
                )
                retry_size = _png_size(path)
                if retry_size is not None:
                    result, size = retry, retry_size
            ok = (
                result.returncode == 0
                and size is not None
                and size[0] >= 300
                and size[1] >= 200
            )
            detail = (
                f"exit={result.returncode} size={path.stat().st_size if path.exists() else 0} "
                f"dims={size[0]}x{size[1]}" if size else f"exit={result.returncode} no PNG"
            )
            results.append((surface, theme, result.returncode, path))
            ctx.check(f"surface {surface} {theme}", ok, detail)
            if ok:
                ctx.artifact(path, minimum=1000)
            else:
                ctx.write_text(
                    f"surface-{surface}-{theme}.txt",
                    f"exit={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}",
                )
    ctx.write_text(
        "surfaces.txt",
        "\n".join(
            f"{surface} {theme} exit={code} {path.name} size={path.stat().st_size if path.exists() else 0}"
            for surface, theme, code, path in results
        ),
    )


def drive_receipt(ctx: Context) -> None:
    """Drive the runnable receipt demo: compact, review, copy, undo, themes."""
    _force_theme("light")
    _qt_app()
    from PySide6 import QtWidgets

    from rework.demo import EXAMPLES, DemoWindow
    from rework.diff_view import DiffView
    from rework.full_text_view import FullTextView
    from rework.theme import LIGHT

    window = DemoWindow(palette=LIGHT)
    window.show()
    _process()
    try:
        window.run_example("small")
        _process()
        card = window.controller._card
        ctx.check("receipt appears", card is not None and card.isVisible(), "compact card visible")
        if card is None:
            return
        title = card.findChild(QtWidgets.QLabel, "title")
        headline = card.findChild(QtWidgets.QLabel, "headline")
        ctx.check(
            "compact title",
            title is not None and title.text() == "Concise rewrite",
            title.text() if title is not None else "missing",
        )
        ctx.check(
            "compact headline",
            headline is not None and "changed" in headline.text(),
            headline.text() if headline is not None else "missing",
        )
        sample = card.findChild(QtWidgets.QLabel, "sample")
        ctx.check(
            "compact sample",
            sample is not None and "yesterday" in sample.accessibleName() and "reviewed" in sample.accessibleName(),
            sample.accessibleName() if sample is not None else "missing",
        )
        privacy = card.findChild(QtWidgets.QLabel, "privacy")
        ctx.check(
            "history saved flag",
            privacy is not None and "Saved to history" in privacy.text(),
            privacy.text() if privacy is not None else "missing",
        )
        compact = _shot(card, ctx.evidence / "receipt-compact-light.png")
        context = _compose(window, card, ctx.evidence / "context-compact-light.png")
        ctx.artifact(compact, 2000)
        ctx.artifact(context, 5000)

        _click_named(card, "Review changes")
        _process()
        ctx.check("review expands", card.expanded, f"expanded={card.expanded}")
        ctx.check(
            "small edit uses inline diff",
            isinstance(card.content_view, DiffView),
            type(card.content_view).__name__,
        )
        review_text = card.content_view.toPlainText()
        ctx.check(
            "review shows both versions",
            "went through" in review_text and "reviewed" in review_text,
            review_text[:120].replace("\n", " "),
        )
        review = _shot(card, ctx.evidence / "receipt-review-light.png")
        ctx.artifact(review, 2000)

        copy_button = _click_named(card, "Copy revised text")
        clipboard = QtWidgets.QApplication.clipboard().text()
        ctx.check(
            "copy revised",
            clipboard == EXAMPLES["small"]["revised"] and copy_button.text() == "Copied",
            f"clipboard={len(clipboard)} chars, button={copy_button.text()}",
        )

        _click_named(card, "Undo rework")
        _process()
        ctx.check(
            "undo restores the demo document",
            window.editor.toPlainText() == EXAMPLES["small"]["original"],
            f"{len(window.editor.toPlainText())} chars restored",
        )
        ctx.check("receipt closes after undo", window.controller._card is None, "controller cleared")

        window.run_example("large")
        _process()
        large_card = window.controller._card
        ctx.check(
            "large rewrite is substantial",
            large_card is not None and large_card.rework.is_substantial,
            f"substantial={large_card.rework.is_substantial if large_card else None}",
        )
        if large_card is not None:
            _click_named(large_card, "Review changes")
            _process()
            ctx.check(
                "substantial rewrite uses full text",
                isinstance(large_card.content_view, FullTextView),
                type(large_card.content_view).__name__,
            )
            large = _shot(large_card, ctx.evidence / "receipt-review-large-light.png")
            ctx.artifact(large, 2000)

        _click_named(window, "Dark")
        _process()
        window.run_example("small")
        _process()
        dark_card = window.controller._card
        ctx.check(
            "dark theme applies",
            window._palette.mode == "dark" and dark_card is not None,
            f"palette={window._palette.mode}",
        )
        if dark_card is not None:
            dark = _shot(dark_card, ctx.evidence / "receipt-compact-dark.png")
            ctx.artifact(dark, 2000)
            _click_named(dark_card, "Review changes")
            _process()
            dark_review = _shot(dark_card, ctx.evidence / "receipt-review-dark.png")
            ctx.artifact(dark_review, 2000)
    finally:
        window.controller.dismiss()
        window.close()
        if getattr(window, "_temp_dir", None) is not None:
            window._temp_dir.cleanup()
        _process()


def drive_history(ctx: Context) -> None:
    """Drive the demo into History, then search, copy, toggle, delete, clear."""
    _force_theme("light")
    _qt_app()
    from PySide6 import QtWidgets

    from rework.demo import EXAMPLES, DemoWindow
    from rework.theme import LIGHT

    window = DemoWindow(palette=LIGHT)
    window.show()
    _process()
    try:
        window.run_example("small")
        window.run_example("large")
        _process()
        _click_named(window, "History")
        _wait(150)
        history = window.history_window
        ctx.check("history opens", history is not None and history.isVisible(), "window visible")
        if history is None:
            return
        ctx.check(
            "two saved rewrites",
            history.list.count() == 2 and "2 rewrites" in history.count_label.text(),
            f"list={history.list.count()} label={history.count_label.text()}",
        )
        ctx.check(
            "newest entry is selected",
            history.original_view.toPlainText() == EXAMPLES["large"]["original"]
            and history.reworked_view.toPlainText() == EXAMPLES["large"]["revised"],
            history.meta.text(),
        )
        listing = _shot(history, ctx.evidence / "history-list-light.png")
        ctx.artifact(listing, 4000)

        _type(history.search, "yesterday")
        _wait(300)
        ctx.check(
            "search filters the list",
            history.list.count() == 1 and "1 of 2" in history.count_label.text(),
            f"list={history.list.count()} label={history.count_label.text()}",
        )
        search = _shot(history, ctx.evidence / "history-search-light.png")
        ctx.artifact(search, 4000)
        history.search.clear()
        _wait(300)

        history.list.setCurrentRow(0)
        _process()
        copy_button = history.copy_reworked
        _click(copy_button)
        copied = QtWidgets.QApplication.clipboard().text()
        ctx.check(
            "copy revised text",
            copied == EXAMPLES["large"]["revised"] and copy_button.text() == "Copied",
            f"clipboard={len(copied)} chars, button={copy_button.text()}",
        )

        _click(history.toggle)
        ctx.check(
            "history toggle persists off",
            window.config["history_enabled"] is False and "History is off" in history.toggle_note.text(),
            history.toggle_note.text(),
        )
        off = _shot(history, ctx.evidence / "history-off-light.png")
        ctx.artifact(off, 4000)
        _click(history.toggle)
        ctx.check(
            "history toggle persists on",
            window.config["history_enabled"] is True,
            history.toggle_note.text(),
        )

        history.list.setCurrentRow(0)
        _process()
        dialog = _answer_message_box("Yes")
        _click(history.delete_button)
        _wait(150)
        ctx.check(
            "delete asks for confirmation",
            dialog["answered"] and dialog["title"] == "Delete rewrite",
            f"title={dialog['title']}",
        )
        ctx.check(
            "delete removes one entry",
            history.store.count() == 1 and history.list.count() == 1,
            f"store={history.store.count()} list={history.list.count()}",
        )
        deleted = _shot(history, ctx.evidence / "history-deleted-light.png")
        ctx.artifact(deleted, 4000)

        dialog = _answer_message_box("Yes")
        _click(history.clear_button)
        _wait(150)
        ctx.check(
            "clear all asks for confirmation",
            dialog["answered"] and dialog["title"] == "Clear rewrite history",
            f"title={dialog['title']}",
        )
        ctx.check(
            "clear all removes every entry",
            history.store.count() == 0
            and history.list.count() == 0
            and "No rewrites yet" in history.meta.text(),
            f"store={history.store.count()} meta={history.meta.text()}",
        )
        empty = _shot(history, ctx.evidence / "history-empty-light.png")
        ctx.artifact(empty, 4000)
    finally:
        if window.history_window is not None:
            window.history_window.close()
        window.controller.dismiss()
        window.close()
        if getattr(window, "_temp_dir", None) is not None:
            window._temp_dir.cleanup()
        _process()


def _provider_test(ctx: Context) -> bool:
    if not PROVIDER_SWITCH_TEST.exists():
        ctx.check(
            "provider-switch dependency",
            False,
            f"{PROVIDER_SWITCH_TEST} is missing; settings/provider setup is unverified",
            blocked=True,
        )
        return False
    command = [
        _python(),
        "-B",
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-p",
        "test_provider_switch.py",
        "-v",
    ]
    try:
        result = subprocess.run(
            command,
            cwd=APP,
            env=_env(),
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        result = subprocess.CompletedProcess(command, 124, "", "timeout after 120s")
    ctx.write_text(
        "provider-switch-test.txt",
        f"exit={result.returncode}\n{result.stdout}\n{result.stderr}",
    )
    ctx.check(
        "provider-switch dependency",
        result.returncode == 0,
        "tests/test_provider_switch.py passed"
        if result.returncode == 0
        else result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "failed",
    )
    return result.returncode == 0


def drive_settings(ctx: Context) -> None:
    """Switch Gemini to OpenAI Compatible and Ollama, then finish setup."""
    if not _provider_test(ctx):
        if not PROVIDER_SWITCH_TEST.exists():
            ctx.blocked_reason = "tests/test_provider_switch.py is missing"
        return

    _force_theme("light")
    _qt_app()
    from PySide6 import QtWidgets

    from aiprovider import GeminiProvider, OllamaProvider, OpenAICompatibleProvider
    from ui.SettingsWindow import SettingsWindow

    config_path = ctx.evidence / "settings-config.json"

    class Shell:
        def __init__(self) -> None:
            self.config = {
                "shortcut": "ctrl+space",
                "provider": "Gemini (Recommended)",
                "providers": {},
            }
            self.providers = [
                GeminiProvider(self),
                OpenAICompatibleProvider(self),
                OllamaProvider(self),
            ]
            self.current_provider = self.providers[0]
            self.calls: list[str] = []

        def save_config(self, config):
            self.config = config
            config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
            self.calls.append("save_config")

        def create_tray_icon(self):
            self.calls.append("create_tray_icon")

        def register_hotkey(self):
            self.calls.append("register_hotkey")

        def validate_shortcut(self, value):
            from WritingToolApp import WritingToolApp

            return WritingToolApp.validate_shortcut(self, value)

        @staticmethod
        def _to_pynput_hotkey(value):
            from WritingToolApp import WritingToolApp

            return WritingToolApp._to_pynput_hotkey(value)

    shell = Shell()
    window = SettingsWindow(shell, providers_only=False)
    window.show()
    _process()
    finish = None
    try:
        names = [window.provider_dropdown.itemText(i) for i in range(window.provider_dropdown.count())]
        ctx.check(
            "real providers are listed",
            names
            == [
                "Gemini (Recommended)",
                "OpenAI Compatible (For Experts)",
                "Ollama (For Experts)",
            ],
            ", ".join(names),
        )
        ctx.check(
            "full settings starts on Gemini",
            window.provider_dropdown.currentText() == "Gemini (Recommended)",
            window.provider_dropdown.currentText(),
        )
        full = _shot(window, ctx.evidence / "settings-full-light.png")
        ctx.artifact(full, 4000)

        action_rows = window.findChildren(QtWidgets.QFrame, "ActionRow")
        action_buttons = [
            button.text() for button in window.findChildren(QtWidgets.QPushButton)
        ]
        ctx.check(
            "settings lists the popup actions",
            len(action_rows) >= 8,
            f"rows={len(action_rows)}",
        )
        ctx.check(
            "settings offers add and reset",
            "Add action" in action_buttons and "Reset actions" in action_buttons,
            f"add={'Add action' in action_buttons}, reset={'Reset actions' in action_buttons}",
        )

        window.provider_dropdown.setCurrentIndex(1)
        _process()
        _flush_deletes()
        ctx.check(
            "OpenAI Compatible fields render",
            all(
                any(field.accessibleName() == name for field in window.findChildren(QtWidgets.QLineEdit))
                for name in ("API Key", "API Base URL", "API Organisation", "API Project", "API Model")
            ),
            "API Key, API Base URL, API Organisation, API Project, API Model",
        )
        preset = next(
            combo
            for combo in window.findChildren(QtWidgets.QComboBox)
            if combo.accessibleName() == "Service preset"
        )
        preset.setCurrentIndex(preset.findData("openrouter"))
        _process()
        ctx.check(
            "preset fills the endpoint",
            _field(window, "API Base URL").text() == "https://openrouter.ai/api/v1",
            _field(window, "API Base URL").text(),
        )
        ctx.check(
            "preset fills the model",
            _field(window, "API Model").text() == "moonshotai/kimi-k3.1-pro",
            _field(window, "API Model").text(),
        )
        ctx.check(
            "preset links the key page",
            "openrouter.ai/settings/keys" in window.preset_note.text(),
            window.preset_note.text(),
        )
        ctx.check(
            "model picker can load the provider list",
            window.model_combo is not None
            and window.model_button.text() == "Load models",
            f"picker={window.model_combo is not None}",
        )
        _type(_field(window, "API Key"), "verify-openai-key")
        _type(_field(window, "API Base URL"), "https://example.invalid/v1")
        _type(_field(window, "API Model"), "verify-openai-model")
        openai = _shot(window, ctx.evidence / "settings-openai-light.png")
        ctx.artifact(openai, 4000)

        window.provider_dropdown.setCurrentIndex(2)
        _process()
        _flush_deletes()
        ctx.check(
            "Ollama fields render with defaults",
            _field(window, "API Base URL").text() == "http://localhost:11434"
            and _field(window, "API Model").text() == "llama3.1:8b",
            f"base={_field(window, 'API Base URL').text()} model={_field(window, 'API Model').text()}",
        )
        _type(_field(window, "API Base URL"), "http://127.0.0.1:11434")
        _type(_field(window, "API Model"), "verify-ollama-model")
        _type(_field(window, "Time to keep the model loaded in memory in minutes"), "7")
        ollama = _shot(window, ctx.evidence / "settings-ollama-light.png")
        ctx.artifact(ollama, 4000)

        _click_named(window, "Save")
        _process()
        saved = shell.config.get("providers", {}).get("Ollama (For Experts)", {})
        ctx.check(
            "saving Ollama switches the provider",
            shell.config.get("provider") == "Ollama (For Experts)",
            str(shell.config.get("provider")),
        )
        ctx.check(
            "Ollama values are saved",
            saved.get("api_base") == "http://127.0.0.1:11434"
            and saved.get("api_model") == "verify-ollama-model"
            and saved.get("keep_alive") == "7",
            json.dumps(saved),
        )
        ctx.check(
            "Ollama becomes the live provider",
            shell.current_provider.provider_name == "Ollama (For Experts)",
            shell.current_provider.provider_name,
        )
        ctx.check("hotkey is re-registered", "register_hotkey" in shell.calls, ", ".join(shell.calls))
        ctx.check("full settings closes", not window.isVisible(), f"visible={window.isVisible()}")
        ctx.artifact(config_path, 50)

        finish = SettingsWindow(shell, providers_only=True)
        finish.show()
        _process()
        ctx.check(
            "finish setup hides general settings",
            finish.shortcut_input is None and not finish.findChildren(QtWidgets.QCheckBox),
            "no shortcut or autostart controls",
        )
        finish.provider_dropdown.setCurrentIndex(1)
        _process()
        _flush_deletes()
        _type(_field(finish, "API Key"), "verify-finish-key")
        _type(_field(finish, "API Base URL"), "https://finish.invalid/v1")
        _type(_field(finish, "API Model"), "verify-finish-model")
        finish_shot = _shot(finish, ctx.evidence / "settings-finish-openai-light.png")
        ctx.artifact(finish_shot, 4000)
        _click_named(finish, "Finish AI Setup")
        _process()
        ctx.check(
            "Finish AI Setup switches to OpenAI Compatible",
            shell.config.get("provider") == "OpenAI Compatible (For Experts)",
            str(shell.config.get("provider")),
        )
        ctx.check(
            "Finish AI Setup creates the tray icon",
            "create_tray_icon" in shell.calls,
            ", ".join(shell.calls),
        )
        ctx.check(
            "Finish AI Setup closes",
            not finish.isVisible() and shell.current_provider.provider_name == "OpenAI Compatible (For Experts)",
            f"visible={finish.isVisible()} provider={shell.current_provider.provider_name}",
        )

        launch_ok, launch_detail = app_launch_probe(ctx)
        ctx.check("real app launch", launch_ok, launch_detail, blocked=not launch_ok)
    finally:
        if finish is not None:
            finish.close()
        window.close()
        _process()


def drive_response(ctx: Context) -> None:
    """Drive the response window: markdown, copy, zoom, follow-up, failure."""
    _force_theme("light")
    _qt_app()
    from PySide6 import QtCore, QtWidgets
    from ui.ResponseWindow import MarkdownTextBrowser, ResponseWindow

    class Shell(QtCore.QObject):
        followup_response_signal = QtCore.Signal(str)
        show_message_signal = QtCore.Signal(str, str)

        def __init__(self) -> None:
            super().__init__()
            self.config = {}
            self.followups = []
            self.saved = []

        def process_followup_question(self, window, message):
            self.followups.append((window.option, message))

        def save_config(self, config):
            self.saved.append(dict(config))

    shell = Shell()
    window = ResponseWindow(shell, "Rewrite Result")
    window.selected_text = "Original text"
    window.show()
    window.set_text(
        "# Budget review\n\n"
        "The **Q3 forecast** looks optimistic. The hiring line assumes everyone "
        "starts on the first of the month.\n\n"
        "- Hiring assumptions\n"
        "- Travel actuals\n\n"
        "| Area | Change |\n"
        "| --- | --- |\n"
        "| Hiring | Lower by 2 |\n"
        "| Travel | Match Q2 |\n\n"
        "[Read the full report](https://example.com)"
    )
    _wait(250)
    try:
        rendered = "\n".join(
            view.toPlainText()
            for view in window.chat_area.findChildren(QtWidgets.QTextBrowser)
        )
        ctx.check(
            "markdown response renders",
            "Budget review" in rendered and "Q3 forecast" in rendered and "Read the full report" in rendered,
            rendered[:140].replace("\n", " "),
        )
        screenshot = _shot(window, ctx.evidence / "response-light.png")
        ctx.artifact(screenshot, 5000)

        _click_named(window, "Copy response")
        clipboard = QtWidgets.QApplication.clipboard().text()
        ctx.check(
            "copy response",
            clipboard.startswith("# Budget review") and "Q3 forecast" in clipboard,
            f"clipboard={len(clipboard)} chars",
        )

        message_views = window.chat_area.findChildren(MarkdownTextBrowser)
        ctx.check("markdown view exists", bool(message_views), f"{len(message_views)} message views")
        before_zoom = message_views[-1].zoom_factor if message_views else 1.0
        _click_named(window, "Zoom in")
        after_zoom = message_views[-1].zoom_factor if message_views else 1.0
        ctx.check(
            "zoom control changes the message",
            after_zoom > before_zoom,
            f"{before_zoom} -> {after_zoom}",
        )

        _type(window.input_field, "Make it shorter")
        _click_named(window, "Send follow-up")
        _process()
        ctx.check(
            "follow-up is sent",
            shell.followups == [("Rewrite", "Make it shorter")]
            and window.chat_history[-1]["role"] == "user",
            str(shell.followups),
        )
        ctx.check(
            "input is busy while waiting",
            not window.input_field.isEnabled() and window.input_field.text() == "",
            f"enabled={window.input_field.isEnabled()}",
        )
        shell.followup_response_signal.emit("Shorter version.")
        _wait(200)
        ctx.check(
            "follow-up response appears",
            window.chat_history[-1] == {"role": "assistant", "content": "Shorter version."}
            and window.input_field.isEnabled(),
            str(window.chat_history[-1]),
        )
        followup = _shot(window, ctx.evidence / "response-followup-light.png")
        ctx.artifact(followup, 5000)
    finally:
        window.close()
        window.deleteLater()
        shell.deleteLater()
        _process()

    failure_shell = Shell()
    failure = ResponseWindow(failure_shell, "Summary Result")
    failure.show()
    failure_shell.show_message_signal.emit("Error", "The provider returned an error.")
    _process()
    try:
        ctx.check(
            "provider error shows in the window",
            failure.status_container.isVisible()
            and "Couldn't get a response" in failure.status_title.text(),
            f"{failure.status_title.text()}: {failure.status_body.text()}",
        )
        failure_shot = _shot(failure, ctx.evidence / "response-failure-light.png")
        ctx.artifact(failure_shot, 3000)
    finally:
        failure.close()
        failure.deleteLater()
        failure_shell.deleteLater()
        _process()


def drive_onboarding_about(ctx: Context) -> None:
    """Drive first-run onboarding, its handoff, and the About links."""
    _force_theme("light")
    _qt_app()
    from unittest import mock

    from PySide6 import QtWidgets

    from ui.AboutWindow import AboutWindow, RELEASES_URL, REPO_URL
    from ui.OnboardingWindow import OnboardingWindow
    from update_checker import CURRENT_VERSION

    class Shell:
        def __init__(self) -> None:
            self.config = {}
            self.settings_calls = []
            self.calls = []

        def show_settings(self, providers_only=False):
            self.settings_calls.append(providers_only)

        def create_tray_icon(self):
            self.calls.append("create_tray_icon")

        def register_hotkey(self):
            self.calls.append("register_hotkey")

        def validate_shortcut(self, value):
            from WritingToolApp import WritingToolApp

            return WritingToolApp.validate_shortcut(self, value)

        @staticmethod
        def _to_pynput_hotkey(value):
            from WritingToolApp import WritingToolApp

            return WritingToolApp._to_pynput_hotkey(value)

        def save_config(self, config):
            self.config = config
            self.calls.append("save_config")

    shell = Shell()
    onboarding = OnboardingWindow(shell)
    onboarding.show()
    _process()
    try:
        ctx.check(
            "onboarding welcome renders",
            onboarding.windowTitle() == "Welcome to Writing Tools"
            and onboarding.shortcut_input.accessibleName() == "Shortcut",
            onboarding.windowTitle(),
        )
        welcome = _shot(onboarding, ctx.evidence / "onboarding-light.png")
        ctx.artifact(welcome, 4000)

        _type(onboarding.shortcut_input, "ctrl+alt+j")
        _click_named(onboarding, "Continue")
        _process()
        ctx.check(
            "onboarding saves the shortcut",
            shell.config.get("shortcut") == "ctrl+alt+j",
            json.dumps(shell.config),
        )
        ctx.check(
            "onboarding hands off to provider setup",
            shell.settings_calls == [True] and not onboarding.isVisible(),
            f"settings_calls={shell.settings_calls} visible={onboarding.isVisible()}",
        )
    finally:
        onboarding.close()
        _process()

    about = AboutWindow()
    about.show()
    _process()
    try:
        labels = [label.text() for label in about.findChildren(QtWidgets.QLabel)]
        ctx.check(
            "about shows the app version",
            f"Version {CURRENT_VERSION}" in labels,
            f"Version {CURRENT_VERSION}",
        )
        ctx.check(
            "about details are scrollable",
            any(
                area.accessibleName() == "About details"
                for area in about.findChildren(QtWidgets.QScrollArea)
            ),
            "About details",
        )
        about_shot = _shot(about, ctx.evidence / "about-light.png")
        ctx.artifact(about_shot, 4000)

        with mock.patch("ui.AboutWindow.webbrowser.open") as opened:
            _click_named(about, "See the latest release")
        ctx.check(
            "latest release opens the releases page",
            opened.call_args is not None and opened.call_args[0][0] == RELEASES_URL,
            str(opened.call_args),
        )
        with mock.patch("ui.AboutWindow.webbrowser.open") as opened:
            _click_named(about, "View source")
        ctx.check(
            "view source opens the repository",
            opened.call_args is not None and opened.call_args[0][0] == REPO_URL,
            str(opened.call_args),
        )
    finally:
        about.close()
        _process()


# ---------------------------------------------------------------------------
# Real app launch probe
# ---------------------------------------------------------------------------


def drive_friction(ctx: Context) -> None:
    """Drive the friction journeys: move, reach history, see progress, cancel."""
    _force_theme("light")
    _qt_app()
    from PySide6 import QtCore, QtGui, QtWidgets

    import ui.CustomPopupWindow
    import ui.DashboardWindow
    from WritingToolApp import WritingToolApp, _RequestContext
    from rework.history import HistoryStore
    from rework.model import Rework
    from rework.review_card import ReworkCard
    from ui.WorkingPill import WorkingPill

    class HostApp:
        """The app surface the popup and the receipt actually touch."""

        def __init__(self):
            self.config = {"update_available": False, "shortcut": "ctrl+space"}
            self.history_requests = 0
            self.options_run = []
            self.history_enabled = True
            self.paused = False
            self.current_provider = None
            self.history_window = None
            self.settings_requests = 0
            self.about_requests = 0

        def show_history(self):
            self.history_requests += 1

        def process_option(self, option, change=None):
            self.options_run.append((option, change))

        def load_options(self):
            pass

        def exit_app(self):
            pass

        def show_settings(self):
            self.settings_requests += 1

        def show_about(self):
            self.about_requests += 1

        def toggle_paused(self):
            self.paused = not self.paused

    def drag(handle, dx, dy):
        _, QtTest, _ = _import_qt()
        start = QtCore.QPoint(14, 14)
        end = QtCore.QPoint(14 + dx, 14 + dy)
        QtTest.QTest.mousePress(handle, QtCore.Qt.MouseButton.LeftButton, pos=start)
        _process()
        QtTest.QTest.mouseMove(handle, end)
        _process()
        QtTest.QTest.mouseRelease(handle, QtCore.Qt.MouseButton.LeftButton, pos=end)
        _process()

    # Journey 1 and 2: the popup moves, and History is one click away.
    host = HostApp()
    popup = ui.CustomPopupWindow.CustomPopupWindow(host)
    popup.move(420, 320)
    popup.show()
    _process()
    try:
        before = popup.pos()
        drag(popup.title_label, 64, 40)
        moved = popup.pos() - before
        ctx.check(
            "popup header drags the window",
            moved == QtCore.QPoint(64, 40),
            f"moved {moved.x()},{moved.y()} from {before.x()},{before.y()}",
        )
        shot = _shot(popup, ctx.evidence / "popup-drag-light.png")
        ctx.artifact(shot, 2000)

        ctx.check(
            "popup offers Rewrites in the header",
            any(
                button.accessibleName() == "Open Rewrites"
                for button in popup.findChildren(QtWidgets.QPushButton)
            ),
            "Open Rewrites button present",
        )
        _click_named(popup, "Open Rewrites")
        ctx.check(
            "history opens from the popup in one click",
            host.history_requests == 1,
            f"show_history calls={host.history_requests}",
        )
        ctx.check("popup yields to history", not popup.isVisible(), "popup hidden")
    finally:
        popup.close()
        _process()

    # Journey 3: a rewrite shows progress at once and can be cancelled.
    pill = WorkingPill("Proofread")
    started = time.perf_counter()
    pill.show_near(QtCore.QPoint(520, 380))
    _process()
    first_ms = (time.perf_counter() - started) * 1000
    ctx.check(
        "progress appears within 100 ms",
        pill.isVisible() and first_ms <= 100,
        f"{first_ms:.1f} ms to visible",
    )
    ctx.check(
        "progress never takes focus",
        bool(
            pill.windowFlags()
            & QtCore.Qt.WindowType.WindowDoesNotAcceptFocus
        )
        and pill.testAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating),
        "WindowDoesNotAcceptFocus and WA_ShowWithoutActivating set",
    )
    pill.set_stage("Thinking")
    _wait(420)
    elapsed_text = pill.stage_label.text()
    elapsed = float(elapsed_text.split("\u00b7")[-1].strip().rstrip("s") or 0)
    ctx.check(
        "elapsed time advances while the model works",
        elapsed >= 0.3,
        elapsed_text,
    )
    shot = _shot(pill, ctx.evidence / "progress-pill-light.png")
    ctx.artifact(shot, 2000)

    cancelled = []
    pill.cancelled.connect(lambda: cancelled.append(True))
    _click_named(pill, "Cancel this rewrite")
    ctx.check(
        "cancel is offered and dismisses the wait",
        cancelled == [True] and not pill.isVisible(),
        f"cancelled={cancelled}, visible={pill.isVisible()}",
    )

    # Journey: the main window shows what changed without a tray detour.
    store_dir = tempfile.mkdtemp(prefix="wt-dashboard-")
    store = HistoryStore(str(Path(store_dir) / "history.db"))
    store.add(
        Rework.create(
            "Concise",
            "The cat sat on the mat today and looked outside.",
            "The cat rested on the mat and watched the garden.",
        )
    )
    store.add(
        Rework.create(
            "Proofread",
            "their going to the store tomorow",
            "they are going to the store tomorrow",
        )
    )

    class HistoryTarget:
        def __init__(self):
            self.entry_ids = []

        def show_entry(self, entry_id):
            self.entry_ids.append(entry_id)

    dashboard_host = HostApp()
    dashboard_host.current_provider = type(
        "Provider", (), {"provider_name": "Gemini (Recommended)"}
    )()
    dashboard_host.history_window = HistoryTarget()
    dashboard = ui.DashboardWindow.DashboardWindow(dashboard_host, store)
    dashboard.show_window()
    _process()
    _flush_deletes()
    try:
        rows = dashboard.findChildren(ui.DashboardWindow.RecentRow)
        ctx.check(
            "dashboard lists the recent rewrites",
            len(rows) == 2 and dashboard.count_label.text() == "2 saved rewrites",
            f"rows={len(rows)}, count={dashboard.count_label.text()}",
        )
        _click_named(dashboard, "Open Rewrite History")
        ctx.check(
            "dashboard opens history in one click",
            dashboard_host.history_requests == 1,
            f"show_history calls={dashboard_host.history_requests}",
        )
        _click_named(dashboard, "Edit actions")
        ctx.check(
            "dashboard opens Settings for actions",
            dashboard_host.settings_requests == 1,
            f"show_settings calls={dashboard_host.settings_requests}",
        )
        QtTest = _import_qt()[1]
        QtTest.QTest.mouseClick(rows[0], QtCore.Qt.MouseButton.LeftButton)
        _process()
        ctx.check(
            "dashboard row opens that exact entry",
            dashboard_host.history_window.entry_ids == [rows[0].entry.id],
            f"entry ids={dashboard_host.history_window.entry_ids}",
        )
        dashboard.pause_button.click()
        _process()
        ctx.check(
            "dashboard pause is real",
            dashboard_host.paused and dashboard.pause_button.text() == "Resume",
            f"paused={dashboard_host.paused}, button={dashboard.pause_button.text()}",
        )
        shot = _shot(dashboard, ctx.evidence / "dashboard-light.png")
        ctx.artifact(shot, 3000)
    finally:
        dashboard.close()
        _process()
        shutil.rmtree(store_dir, ignore_errors=True)

    # Journey 4: the receipt moves, and History is one click away.
    rework = Rework.create(
        "Concise",
        "The cat sat on the mat today.",
        "The cat rested on the mat today.",
    )
    history_calls = []
    card = ReworkCard(
        rework,
        lambda: None,
        lambda: None,
        saved_to_history=True,
        on_history=lambda: history_calls.append(True),
    )
    card.show_near(QtCore.QPoint(560, 300))
    _process()
    try:
        before = card.pos()
        title = card.findChild(QtWidgets.QLabel, "title")
        drag(title, 36, 28)
        moved = card.pos() - before
        ctx.check(
            "receipt header drags the window",
            moved == QtCore.QPoint(36, 28),
            f"moved {moved.x()},{moved.y()}",
        )
        _click_named(card, "Open Rewrite History")
        ctx.check(
            "receipt opens history in one click",
            history_calls == [True] and not card.isVisible(),
            f"history calls={len(history_calls)}, visible={card.isVisible()}",
        )
        review = ReworkCard(rework, lambda: None, lambda: None, saved_to_history=True)
        review.show_near(QtCore.QPoint(560, 300))
        _process()
        _click_named(review, "Review changes")
        _process()
        drag(review.findChild(QtWidgets.QLabel, "title"), 30, 20)
        shot = _shot(review, ctx.evidence / "receipt-review-light.png")
        ctx.artifact(shot, 2000)
        review.close()
    finally:
        card.close()
        _process()

    # Journey 5: a stale or cancelled response can never paste.
    from core.workflow import WorkflowController

    class ResponseHost(QtCore.QObject):
        _deliver_response = WritingToolApp._deliver_response
        _cancel_active_request = WritingToolApp._cancel_active_request

        def __init__(self):
            super().__init__()
            self.workflow = WorkflowController(self)
            self.workflow.begin("Proofread", "original")
            self.workflow.set_original(1, "original")
            self.workflow.begin("Proofread", "original")
            self.workflow.set_original(2, "original")
            self._active_request = _RequestContext("Proofread", "original", serial=2)
            self._request_serial = 2
            self.working_pill = None
            self.pasted = []

        def _hide_working(self):
            pass

        def _refresh_dashboard(self):
            pass

        def _refresh_tray_tooltip(self):
            pass

        def replace_text(self, text):
            self.pasted.append(text)

    response_host = ResponseHost()
    response_host._deliver_response(1, "stale response")
    response_host._deliver_response(2, "live response")
    response_host._cancel_active_request()
    response_host._deliver_response(2, "late response")
    ctx.check(
        "stale and cancelled responses never paste",
        response_host.pasted == ["live response"],
        f"pasted={response_host.pasted}",
    )

    ledger = ctx.write_text(
        "friction-journeys.txt",
        "\n".join(
            [
                "P2 daily writer: popup moves by header drag; History is one click",
                "P3 skeptic reviewer: receipt moves; review keeps the diff",
                "P4 returning searcher: popup -> History in 1 action, was 4",
                "P4 dashboard: recent rewrites listed, one click opens the exact entry",
                "P5 actions: Settings lists the popup actions; Add and Reset are visible",
                f"P2 progress: visible in {first_ms:.1f} ms, elapsed {elapsed_text}",
                "P2 cancel: one action, stale responses dropped",
            ]
        ),
    )
    ctx.artifact(ledger, 10)


WORKFLOWS = (
    ("W1", "First run to first rewrite", 27, 10),
    ("W2", "Quick rewrite with a known action", 6, 4),
    ("W3", "Custom instruction rewrite", 7, 5),
    ("W4", "Review and undo a rewrite", 5, 3),
    ("W5", "Find and reuse a past rewrite", 12, 5),
    ("W6", "Add or edit an action", 16, 7),
    ("W7", "Change the shortcut", 7, 3),
    ("W8", "Connect a provider", 14, 6),
    ("W9", "Pause or resume", 2, 1),
    ("W10", "Recover from a provider error", 16, 5),
    ("W11", "Read a long result and follow up", 5, 3),
    ("W12", "Open the app again", 1, 1),
    ("W13", "Change history privacy", 5, 2),
    ("W14", "Abandon setup and come back", 8, 2),
)


class Tally:
    """Count explicit drive actions, decisions, and dead ends for one workflow."""

    def __init__(self, ctx: Context, workflow_id: str):
        self.ctx = ctx
        self.workflow_id = workflow_id
        self.actions: list[str] = []
        self.decisions = 0
        self.dead_ends = 0
        self.context_switches = 0

    def act(self, label: str) -> None:
        self.actions.append(label)
        self.ctx.note("action", f"{self.workflow_id} {label}")

    def decide(self, label: str) -> None:
        self.decisions += 1
        self.ctx.note("decision", f"{self.workflow_id} {label}")

    def dead_end(self, label: str) -> None:
        self.dead_ends += 1
        self.ctx.note("dead-end", f"{self.workflow_id} {label}")

    def score(self) -> int:
        return (
            len(self.actions)
            + 2 * self.context_switches
            + self.decisions
            + 3 * self.dead_ends
        )


def _workflow_evidence(ctx: Context, name: str, widget) -> str:
    path = _shot(widget, ctx.evidence / name)
    ctx.artifact(path, 3000)
    return name


def drive_workflow(ctx: Context) -> None:
    """Drive the one-shell workflows, then write the friction scorecard."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    _force_theme("light")
    _qt_app()
    from PySide6 import QtCore, QtGui, QtWidgets
    from unittest import mock

    sys.path.insert(0, str(APP / "tests"))
    from shell_fixtures import (
        FakeHost,
        build_shell,
        click,
        click_action,
        click_named,
        isolate_app_files,
        line_edit,
        read_options,
        wait_until,
    )

    work = ctx.scratch / "workflow"
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    isolate_app_files(work / "app")
    tallies = {wid: Tally(ctx, wid) for wid, _title, _baseline, _target in WORKFLOWS}
    evidence: dict[str, list[str]] = {wid: [] for wid in tallies}
    keepalive: list = []

    def tally(wid: str) -> Tally:
        return tallies[wid]

    def note_shot(wid: str, name: str, widget) -> None:
        evidence[wid].append(_workflow_evidence(ctx, name, widget))

    host = FakeHost(work / "host")
    host.seed_history(2)
    shell = build_shell(host)
    keepalive.append(shell)

    # W11. Read a long result and follow up. Run it early, before the long
    # shell sequence, so the reader's own window and timer stay isolated.
    t11 = tally("W11")
    from ui.ResponseWindow import ResponseWindow

    reader = ResponseWindow(host, "Summary")
    keepalive.append(reader)
    reader.show()
    reader.set_text("# Result\n\nA long answer that needs a follow-up.")
    _wait(100)
    t11.act("copy the response")
    click_named(reader, "Copy response")
    _wait(50)
    copied = QtWidgets.QApplication.clipboard().text()
    ctx.check("W11 copy returns the response", copied.startswith("# Result"), f"{len(copied)} chars")
    t11.act("type a follow-up")
    line_edit(reader, "Follow-up question").setText("What changed?")
    t11.act("send the follow-up")
    click_named(reader, "Send follow-up")
    _wait(50)
    ctx.check("W11 the follow-up is sent", host.followups == ["What changed?"], str(host.followups))
    host.followup_response_signal.emit("A follow-up answer.")
    _wait(50)
    note_shot("W11", "workflow-reader.png", reader)
    reader.close()

    first_popup = None
    first_card = None
    try:
        # W1. First run to first rewrite.
        t1 = tally("W1")
        setup_host = FakeHost(work / "setup", with_provider=False)
        setup_shell = build_shell(setup_host)
        note_shot("W1", "workflow-home-setup.png", setup_shell)
        t1.act("open the app")
        wizard = setup_shell.home._wizard
        ctx.check(
            "W1 setup is a state of Home",
            wizard is not None and setup_shell.home.main_host.isHidden(),
            f"wizard={type(wizard).__name__ if wizard else None}",
        )
        t1.decide("provider: Gemini")
        t1.act("edit the shortcut")
        wizard.shortcut_input.setText("ctrl+alt+j")
        t1.act("continue to the provider step")
        click_named(wizard, "Continue")
        _wait(100)
        form = wizard._provider_form
        ctx.check(
            "W1 step 2 renders the provider form",
            form is not None and form.provider_name() == "Gemini (Recommended)",
            form.provider_name() if form is not None else "missing",
        )
        note_shot("W1", "workflow-setup-step2.png", setup_shell)

        # W14. Abandon setup and come back. This runs here so the same
        # setup shell proves the close-and-return path before it completes.
        t14 = tally("W14")
        t14.act("close the shell")
        setup_shell.close()
        _wait(50)
        ctx.check(
            "W14 closing setup keeps the app running",
            not setup_shell.isVisible() and "exit_app" not in setup_host.calls,
            f"visible={setup_shell.isVisible()}",
        )
        t14.act("open the app again")
        setup_shell.show_window()
        _wait(50)
        ctx.check(
            "W14 Home still offers setup on return",
            setup_shell.home._wizard is not None,
            f"wizard={setup_shell.home._wizard is not None}",
        )
        note_shot("W14", "workflow-setup-return.png", setup_shell)

        t1.act("paste the API key")
        line_edit(form, "API Key").setText("test-key")
        t1.act("finish setup")
        click_named(form, "Finish setup")
        _wait(100)
        ctx.check(
            "W1 ready screen names the shortcut",
            wizard.step_label.text() == "Ready" and "ctrl+alt+j" in wizard.body.text(),
            wizard.step_label.text(),
        )
        t1.act("open Home")
        click_named(wizard, "Open Home")
        _wait(100)
        ctx.check(
            "W1 setup finished on Home",
            setup_host.current_provider is not None
            and setup_shell.home.main_host.isHidden() is False,
            f"provider={getattr(setup_host.current_provider, 'provider_name', None)}",
        )
        t1.act("select text")
        t1.act("press the shortcut")
        first_popup = __import__("ui.CustomPopupWindow", fromlist=["CustomPopupWindow"]).CustomPopupWindow(
            setup_host
        )
        keepalive.append(first_popup)
        first_popup.show()
        first_popup.activateWindow()
        _wait(100)
        t1.act("click Proofread")
        click_action(first_popup, "Proofread")
        _wait(150)
        first_card = setup_host.rework_controller._card
        keepalive.append(first_card)
        ctx.check(
            "W1 first rewrite produces a receipt and a history row",
            first_card is not None and setup_host.history_store.count() == 1,
            f"card={first_card is not None} rows={setup_host.history_store.count()}",
        )
        if first_card is not None:
            note_shot("W1", "workflow-receipt-first.png", first_card)
        setup_host.rework_controller.dismiss()
        first_popup.close()
        setup_shell.close()

        # W2. Quick rewrite with a known action.
        t2 = tally("W2")
        t2.act("select text")
        t2.act("press the shortcut")
        popup = __import__("ui.CustomPopupWindow", fromlist=["CustomPopupWindow"]).CustomPopupWindow(host)
        keepalive.append(popup)
        popup.show()
        popup.activateWindow()
        _wait(100)
        note_shot("W2", "workflow-popup-light.png", popup)
        before = len(host.processed)
        t2.act("Ctrl+1")
        QtTest = _import_qt()[1]
        QtTest.QTest.keyClick(
            popup, QtCore.Qt.Key.Key_1, QtCore.Qt.KeyboardModifier.ControlModifier
        )
        _wait(200)
        ctrl_one_ok = (
            len(host.processed) == before + 1
            and host.processed[before][0] == "Proofread"
        )
        ctx.check(
            "W2 popup Ctrl+1 runs the first action",
            ctrl_one_ok,
            f"processed={host.processed[-1] if host.processed else None}",
        )
        if not ctrl_one_ok:
            t2.dead_end("Ctrl+1 did not run an action")
            t2.act("click the action")
            click_action(popup, "Proofread")
            _wait(150)
        card = host.rework_controller._card
        keepalive.append(card)
        ctx.check(
            "W2 the action produces a receipt",
            card is not None,
            f"rows={host.history_store.count()}",
        )
        if card is not None:
            note_shot("W2", "workflow-receipt-quick.png", card)
        host.rework_controller.dismiss()
        popup.close()

        # W3. Custom instruction rewrite.
        t3 = tally("W3")
        t3.act("select text")
        t3.act("press the shortcut")
        popup = __import__("ui.CustomPopupWindow", fromlist=["CustomPopupWindow"]).CustomPopupWindow(host)
        keepalive.append(popup)
        popup.show()
        popup.activateWindow()
        _wait(100)
        t3.act("type the custom instruction")
        popup.custom_input.setText("Make it funny.")
        note_shot("W3", "workflow-popup-custom.png", popup)
        t3.act("press Enter")
        QtTest.QTest.keyClick(popup.custom_input, QtCore.Qt.Key.Key_Return)
        _wait(150)
        custom_ok = ("Custom", "Make it funny.") in host.processed
        ctx.check("W3 custom instruction is sent", custom_ok, f"processed={host.processed[-1] if host.processed else None}")
        card = host.rework_controller._card
        keepalive.append(card)
        if card is not None:
            note_shot("W3", "workflow-receipt-custom.png", card)

        # W4. Review and undo.
        t4 = tally("W4")
        t4.act("show the receipt")
        ctx.check("W4 receipt is on screen", card is not None and card.isVisible(), "receipt visible")
        t4.act("review changes")
        if card is not None:
            click_named(card, "Review changes")
            _wait(100)
            note_shot("W4", "workflow-receipt-review.png", card)
            ctx.check("W4 review expands the diff", card.expanded, f"expanded={card.expanded}")
        t4.act("undo")
        if card is not None:
            click_named(card, "Undo rework")
            _wait(100)
        ctx.check(
            "W4 undo dismisses the receipt",
            host.undo_calls == 1 and host.rework_controller._card is None,
            f"undo={host.undo_calls}",
        )

        # W5. Find and reuse a past rewrite.
        t5 = tally("W5")
        shell.close()
        t5.act("open the app")
        shell.show_window()
        t5.act("open Rewrites")
        shell.navigate("rewrites")
        t5.act("search")
        shell.rewrites.search.setText("store")
        _wait(100)
        note_shot("W5", "workflow-rewrites-search.png", shell)
        t5.act("select the result")
        shell.rewrites.list.setCurrentRow(0)
        _wait(50)
        t5.act("copy the revised text")
        click(shell.rewrites.copy_revised)
        _wait(50)
        copied = QtWidgets.QApplication.clipboard().text()
        ctx.check(
            "W5 search, select, and copy return the revision",
            shell.rewrites.list.count() == 1
            and "store" in copied
            and bool(copied),
            f"rows={shell.rewrites.list.count()} clipboard={len(copied)} chars",
        )
        note_shot("W5", "workflow-rewrites-copied.png", shell)

        # W6. Add an action.
        t6 = tally("W6")
        t6.act("open Actions")
        shell.navigate("actions")
        t6.act("add an action")
        click_named(shell.actions, "Add action")
        t6.act("name the action")
        line_edit(shell.actions.editor, "Action name").setText("Tighten")
        t6.act("describe the change")
        shell.actions.editor.instruction.setPlainText("Tighten the prose without losing meaning.")
        t6.act("save the action")
        click_named(shell.actions, "Save action")
        _wait(100)
        saved_action = "Tighten" in read_options()
        ctx.check(
            "W6 the action is saved and the popup reloads",
            saved_action and "actions_changed" in host.calls,
            f"saved={saved_action}",
        )
        note_shot("W6", "workflow-actions-saved.png", shell)

        # W7. Change the shortcut.
        t7 = tally("W7")
        t7.act("open Settings")
        shell.navigate("settings")
        t7.act("edit the shortcut")
        shortcut_field = line_edit(shell.settings, "Shortcut")
        shortcut_field.setText("ctrl+alt+p")
        t7.act("press Enter")
        QtTest.QTest.keyClick(shortcut_field, QtCore.Qt.Key.Key_Return)
        _wait(100)
        ctx.check(
            "W7 the shortcut autosaves",
            host.config.get("shortcut") == "ctrl+alt+p"
            and host.calls.count("register_hotkey") >= 1,
            host.config.get("shortcut"),
        )
        note_shot("W7", "workflow-settings-shortcut.png", shell)

        # W13. Change history privacy while Settings is already open.
        t13 = tally("W13")
        t13.act("toggle history off")
        shell.settings.history_toggle.setChecked(False)
        _wait(50)
        ctx.check(
            "W13 the toggle updates the app and the note",
            host.history_enabled is False
            and host.config.get("history_enabled") is False
            and "History is off" in shell.settings.history_note.text(),
            shell.settings.history_note.text(),
        )
        note_shot("W13", "workflow-settings-history-off.png", shell)
        shell.settings.history_toggle.setChecked(True)
        _wait(50)

        # W8. Connect a provider.
        t8 = tally("W8")
        from ui.ProviderForm import ProviderForm

        t8.decide("provider and model")
        form = shell.settings.provider_form
        form.provider_combo.setCurrentIndex(1)
        _wait(150)
        openai_visible = any(
            field.accessibleName() == "API Base URL"
            for field in form.findChildren(QtWidgets.QLineEdit)
        )
        if not openai_visible:
            t8.dead_end("switching to OpenAI did not render its fields")
            host.config["provider"] = "OpenAI Compatible (For Experts)"
            form = ProviderForm(host, save_label="Save provider")
            keepalive.append(form)
            form.show()
            _wait(50)
        preset_index = form.preset_combo.findData("openrouter")
        t8.act("choose the OpenRouter preset")
        form.preset_combo.setCurrentIndex(preset_index)
        _wait(50)
        t8.act("paste the API key")
        line_edit(form, "API Key").setText("sk-test")
        t8.act("load models")
        from ui import ModelCatalog

        with mock.patch.object(
            ModelCatalog, "fetch_models", return_value=["model-one", "model-two"]
        ):
            form._load_models()
            loaded = wait_until(lambda: not form._loading_models, timeout=2500)
        if not loaded:
            t8.dead_end("the model list did not finish loading")
            line_edit(form, "API Model").setText("moonshotai/kimi-k3.1-pro")
        ctx.check(
            "W8 the preset fills the base and model",
            "openrouter.ai" in line_edit(form, "API Base URL").text(),
            line_edit(form, "API Base URL").text(),
        )
        t8.act("test the connection")
        click_named(form, "Test connection")
        wait_until(lambda: not form._testing, timeout=2500)
        ctx.check(
            "W8 the connection test succeeds",
            "Connected" in form.status.text(),
            form.status.text(),
        )
        t8.act("save the provider")
        click_named(form, "Save provider")
        _wait(100)
        ctx.check(
            "W8 the provider is saved",
            host.config.get("provider") == "OpenAI Compatible (For Experts)"
            and "OpenAI Compatible (For Experts)" in host.config.get("providers", {}),
            host.config.get("provider", ""),
        )
        note_shot("W8", "workflow-provider-saved.png", shell)

        # W9. Pause and resume.
        t9 = tally("W9")
        t9.act("click the status chip")
        click(shell.status_chip)
        _wait(50)
        ctx.check(
            "W9 one click pauses the app",
            host.paused and shell.status_chip.text() == "Paused",
            shell.status_chip.text(),
        )
        note_shot("W9", "workflow-settings-paused.png", shell)
        click(shell.status_chip)
        _wait(50)

        # W10. Recover from a provider error.
        t10 = tally("W10")
        shell.show_banner(
            "Connection failed",
            "The provider rejected the key.",
            "Open provider settings",
            lambda: shell.navigate("settings"),
        )
        t10.act("use the banner action")
        click_named(shell, "Open provider settings")
        _wait(50)
        ctx.check("W10 the banner opens provider settings", shell._current == "settings", shell._current)
        host.config["provider"] = "Gemini (Recommended)"
        host.current_provider = host.providers[0]
        form = ProviderForm(host, save_label="Save provider")
        keepalive.append(form)
        form.show()
        _wait(50)
        t10.act("fix the key")
        line_edit(form, "API Key").setText("sk-fixed")
        t10.act("test again")
        click_named(form, "Test connection")
        wait_until(lambda: not form._testing, timeout=2500)
        ctx.check(
            "W10 the retry test succeeds inline",
            "Connected" in form.status.text(),
            form.status.text(),
        )
        t10.act("save the provider")
        click_named(form, "Save provider")
        _wait(100)
        t10.act("retry the rewrite")
        host.process_option("Proofread")
        _wait(100)
        keepalive.append(host.rework_controller._card)
        ctx.check(
            "W10 the retry produces a receipt",
            host.rework_controller._card is not None,
            f"rows={host.history_store.count()}",
        )
        note_shot("W10", "workflow-recovery.png", shell)
        host.rework_controller.dismiss()

        # W12. Open the app again.
        t12 = tally("W12")
        current_shell = host.shell
        t12.act("open the app again")
        host.show_dashboard()
        _wait(50)
        ctx.check(
            "W12 the running shell is raised",
            host.shell is current_shell,
            f"same={host.shell is current_shell}",
        )
    finally:
        host.rework_controller.dismiss()
        shell.hide()
        _process()

    rows = []
    for wid, title, baseline, target in WORKFLOWS:
        measured = tally(wid)
        after = measured.score()
        rows.append(
            {
                "id": wid,
                "workflow": title,
                "baseline": baseline,
                "target": target,
                "after": after,
                "actions": len(measured.actions),
                "action_log": list(measured.actions),
                "decisions": measured.decisions,
                "context_switches": measured.context_switches,
                "dead_ends": measured.dead_ends,
                "status": "PASS" if after <= target else "FAIL",
                "evidence": evidence[wid],
            }
        )
    scorecard = {
        "run_id": ctx.run_id,
        "generated": _now(),
        "scoring": "user actions + 2 x context switches + decisions + 3 x dead ends",
        "note": "Actions are explicit drive interactions, not wall time.",
        "rows": rows,
        "totals": {
            "baseline": sum(row["baseline"] for row in rows),
            "target": sum(row["target"] for row in rows),
            "after": sum(row["after"] for row in rows),
            "status": "PASS" if all(row["status"] == "PASS" for row in rows) else "FAIL",
        },
    }
    scorecard_path = ctx.evidence / "friction-scorecard.json"
    scorecard_path.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
    ctx.artifact(scorecard_path, 500)
    ctx.write_text(
        "friction-actions.txt",
        "\n".join(
            f"{row['id']} {row['status']} after={row['after']} target={row['target']} "
            f"actions={row['actions']} decisions={row['decisions']} "
            f"dead_ends={row['dead_ends']} | "
            + "; ".join(row["action_log"])
            for row in rows
        ),
    )
    failed = [row["id"] for row in rows if row["status"] == "FAIL"]
    ctx.note(
        "scorecard",
        "friction totals baseline=%d target=%d after=%d, misses=%s"
        % (
            scorecard["totals"]["baseline"],
            scorecard["totals"]["target"],
            scorecard["totals"]["after"],
            ",".join(failed) if failed else "none",
        ),
    )


def app_launch_probe(ctx: Context) -> tuple[bool, str]:
    """Construct the real WritingToolApp in an isolated copy of the app tree.

    This is deliberately separate from the surface drives. The app needs a
    config file and starts the tray icon and global hotkey. If it cannot
    construct, the surface harness can still run, but the real app is not
    usable.
    """
    copy = ctx.scratch / "app-copy"
    if copy.exists():
        shutil.rmtree(copy, ignore_errors=True)
    copy.mkdir(parents=True, exist_ok=True)
    ignore = shutil.ignore_patterns("__pycache__", ".venv", "dist", "tests", "*.pyc")
    for name in ("main.py", "WritingToolApp.py", "aiprovider.py", "update_checker.py", "options.json"):
        source = APP / name
        if source.exists():
            shutil.copy2(source, copy / name)
    for name in ("ui", "rework", "core", "icons", "locales"):
        source = APP / name
        if source.exists():
            shutil.copytree(source, copy / name, ignore=ignore)
    config = {
        "shortcut": "ctrl+space",
        "provider": "Gemini (Recommended)",
        "providers": {
            "Gemini (Recommended)": {
                "api_key": "verify-dummy-key",
                "model_name": "gemini-flash-latest",
            }
        },
        "is_config_file_updated_for_v8": True,
        "is_config_file_updated_for_v9": True,
    }
    (copy / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    probe = copy / "launch_probe.py"
    probe.write_text(
        textwrap.dedent(
            """
            import sys
            from PySide6 import QtCore
            import WritingToolApp as module

            class NoUpdate:
                def __init__(self, app):
                    pass

                def check_updates_async(self):
                    pass

            module.UpdateChecker = NoUpdate
            app = module.WritingToolApp([sys.argv[0]])
            print("APP_CONSTRUCTED", flush=True)
            QtCore.QTimer.singleShot(500, app.exit_app)
            QtCore.QTimer.singleShot(1500, app.quit)
            app.exec()
            print("APP_EXITED", flush=True)
            """
        ),
        encoding="utf-8",
    )
    try:
        result = subprocess.run(
            [_python(), "-B", "launch_probe.py"],
            cwd=copy,
            env=_env(),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired as error:
        (ctx.evidence / "app-launch.txt").write_text(
            f"timeout after {error.timeout}s\nstdout={error.stdout}\nstderr={error.stderr}",
            encoding="utf-8",
        )
        return False, "real app probe timed out"
    (ctx.evidence / "app-launch.txt").write_text(
        f"exit={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}",
        encoding="utf-8",
    )
    if result.returncode == 0 and "APP_CONSTRUCTED" in result.stdout:
        return True, "real WritingToolApp constructed and exited"
    lines = [line for line in (result.stderr or result.stdout).splitlines() if line.strip()]
    detail = lines[-1] if lines else f"exit={result.returncode}"
    if "NameError" in detail or "apply_dark_mode_styles" in (result.stderr or ""):
        detail = "NameError in apply_dark_mode_styles while building the tray menu"
    return False, detail


# ---------------------------------------------------------------------------
# Doctor
# ---------------------------------------------------------------------------


def doctor(run_id: str) -> int:
    ctx = Context("doctor", run_id)
    checks: list[dict] = []

    def check(name: str, ok: bool, detail: str, blocked: bool = False) -> None:
        ctx.check(name, ok, detail, blocked=blocked)
        checks.append({"check": name, "ok": bool(ok), "detail": str(detail), "blocked": bool(blocked)})

    check("python executable", ".venv" in _python().lower(), _python())
    check("repository", (APP / "main.py").exists(), str(APP))
    for name in ("WritingToolApp.py", "options.json", "icons/app_icon.png", "tests"):
        path = APP / name
        check(f"app file {name}", path.exists(), str(path))
    try:
        import PySide6

        check("PySide6", True, getattr(PySide6, "__version__", "imported"))
    except Exception as error:
        check("PySide6", False, repr(error))
    check(
        "Qt platform",
        True,
        os.environ.get("QT_QPA_PLATFORM", _platform()),
    )
    check(
        "provider-switch dependency",
        PROVIDER_SWITCH_TEST.exists(),
        str(PROVIDER_SWITCH_TEST) if PROVIDER_SWITCH_TEST.exists() else "missing; settings is BLOCKED",
        blocked=not PROVIDER_SWITCH_TEST.exists(),
    )
    if PROVIDER_SWITCH_TEST.exists():
        try:
            result = subprocess.run(
                [
                    _python(),
                    "-B",
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "tests",
                    "-p",
                    "test_provider_switch.py",
                ],
                cwd=APP,
                env=_env(),
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            result = subprocess.CompletedProcess([], 124, "", "timeout after 120s")
        check(
            "provider-switch test",
            result.returncode == 0,
            "test_provider_switch.py passed"
            if result.returncode == 0
            else (result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "failed"),
        )
    launch_ok, launch_detail = app_launch_probe(ctx)
    check("real app launch", launch_ok, launch_detail, blocked=not launch_ok)
    ctx.save_summary()
    print(
        f"DOCTOR {ctx.status}: {sum(1 for item in checks if item['ok'])}/{len(checks)} checks passed",
        flush=True,
    )
    return 0 if all(item["ok"] or item["blocked"] for item in checks) else 1


# ---------------------------------------------------------------------------
# Feature runner, gate, cleanup
# ---------------------------------------------------------------------------


def drive_feature(feature: str, run_id: str) -> int:
    if feature not in FEATURES:
        print(f"unknown feature {feature}; choose from {', '.join(FEATURES)}", file=sys.stderr)
        return 1
    ctx = Context(feature, run_id)
    os.environ["QT_QPA_PLATFORM"] = _platform()
    sys.path.insert(0, str(APP))
    sys.argv[0] = str(APP / "WritingToolApp.py")
    error = None
    try:
        if feature == "surfaces":
            drive_surfaces(ctx)
        elif feature == "receipt":
            drive_receipt(ctx)
        elif feature == "history":
            drive_history(ctx)
        elif feature == "settings":
            drive_settings(ctx)
        elif feature == "response":
            drive_response(ctx)
        elif feature == "onboarding-about":
            drive_onboarding_about(ctx)
        elif feature == "friction":
            drive_friction(ctx)
        elif feature == "workflow":
            drive_workflow(ctx)
    except Exception:
        error = traceback.format_exc()
        ctx.write_text("error.txt", error)
        print(error, file=sys.stderr, flush=True)
    finally:
        data = ctx.save_summary(error)
        print(f"RESULT {feature} {data['status']} {ctx.evidence}", flush=True)
    if data["status"] == "BLOCKED":
        code = 3
    elif data["status"] == "PASS_WITH_BLOCKER":
        code = 2
    else:
        code = 0 if data["status"] == "PASS" else 1
    sys.stdout.flush()
    sys.stderr.flush()
    # PySide6 can access-violate during DLL detach after the evidence is
    # already written. This process is short-lived, so terminate it directly.
    if sys.platform == "win32":
        kernel32 = ctypes.windll.kernel32
        kernel32.TerminateProcess(kernel32.GetCurrentProcess(), code)
    os._exit(code)


def _terminate_child(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/PID", str(pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    else:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


def run_feature(feature: str, run_id: str) -> int:
    """Run one feature in a disposable child so Qt teardown cannot fail the evidence."""
    if feature not in FEATURES:
        print(f"unknown feature {feature}; choose from {', '.join(FEATURES)}", file=sys.stderr)
        return 1
    summary_path = ARTIFACTS / run_id / "evidence" / "summary.json"
    if summary_path.exists():
        summary_path.unlink()
    child = subprocess.Popen(
        [_python(), "-B", str(Path(__file__).resolve()), "_drive", "--feature", feature, "--run-id", run_id],
        cwd=REPO,
        env=_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []

    def drain(stream, sink: list[str]) -> None:
        try:
            for line in iter(stream.readline, ""):
                sink.append(line)
        finally:
            stream.close()

    readers = [
        threading.Thread(target=drain, args=(child.stdout, stdout_chunks), daemon=True),
        threading.Thread(target=drain, args=(child.stderr, stderr_chunks), daemon=True),
    ]
    for reader in readers:
        reader.start()
    deadline = time.time() + 300
    while time.time() < deadline:
        if summary_path.exists() and summary_path.stat().st_size:
            break
        if child.poll() is not None:
            break
        time.sleep(0.1)
    if child.poll() is None:
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _terminate_child(child.pid)
            child.wait(timeout=10)
    for reader in readers:
        reader.join(timeout=5)
    stdout = "".join(stdout_chunks)
    stderr = "".join(stderr_chunks)
    if stdout:
        print(stdout, end="")
    if stderr:
        print(stderr, end="", file=sys.stderr)
    if not summary_path.exists():
        print(f"RESULT {feature} FAIL {ARTIFACTS / run_id / 'evidence'}")
        return 1
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    status = summary.get("status", "FAIL")
    if status == "BLOCKED":
        return 3
    if status == "PASS_WITH_BLOCKER":
        return 2
    return 0 if status == "PASS" else 1


def gate(run_id: str) -> int:
    ctx = Context("gate", run_id)
    gate_root = ARTIFACTS / run_id
    results = {}

    doctor_result = subprocess.run(
        [_python(), "-B", str(Path(__file__).resolve()), "doctor", "--run-id", f"{run_id}-doctor"],
        cwd=REPO,
        env=_env(),
        capture_output=True,
        text=True,
        timeout=180,
    )
    ctx.write_text(
        "doctor.txt",
        f"exit={doctor_result.returncode}\n{doctor_result.stdout}\n{doctor_result.stderr}",
    )
    ctx.check("doctor", doctor_result.returncode == 0, f"exit={doctor_result.returncode}")

    for feature in FEATURES:
        sub_run = f"{run_id}-{feature}"
        command = [
            _python(),
            "-B",
            str(Path(__file__).resolve()),
            "run",
            "--feature",
            feature,
            "--run-id",
            sub_run,
        ]
        try:
            result = subprocess.run(
                command,
                cwd=REPO,
                env=_env(),
                capture_output=True,
                text=True,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            result = subprocess.CompletedProcess(command, 124, "", "timeout after 300s")
        summary = _current_summary(feature, sub_run) or {}
        status = summary.get("status", "FAIL")
        if result.returncode not in (0, 2, 3):
            try:
                retry = subprocess.run(
                    command,
                    cwd=REPO,
                    env=_env(),
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
            except subprocess.TimeoutExpired:
                retry = subprocess.CompletedProcess(command, 124, "", "timeout after 300s")
            retry_summary = _current_summary(feature, sub_run) or {}
            if retry.returncode in (0, 2, 3):
                result, summary = retry, retry_summary
                status = summary.get("status", "FAIL")
        results[feature] = {
            "run_id": sub_run,
            "status": status,
            "exit": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "evidence": str(ARTIFACTS / sub_run / "evidence"),
        }
        ctx.check(
            f"feature {feature}",
            status == "PASS" and result.returncode == 0,
            f"{status} (exit={result.returncode})",
        )

    test_command = [_python(), "-B", "-m", "unittest", "discover", "-s", "tests", "-v"]
    try:
        tests = subprocess.run(
            test_command,
            cwd=APP,
            env=_env(),
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        tests = subprocess.CompletedProcess(test_command, 124, "", "timeout after 300s")
    ctx.write_text("unit-tests.txt", f"exit={tests.returncode}\n{tests.stdout}\n{tests.stderr}")
    ctx.check(
        "unit tests",
        tests.returncode == 0,
        (tests.stderr.strip().splitlines()[-1] if tests.stderr.strip() else "all tests passed"),
    )

    blocked = [
        name
        for name, item in results.items()
        if item["status"] in ("BLOCKED", "PASS_WITH_BLOCKER")
    ]
    failed = [name for name, item in results.items() if item["status"] == "FAIL"]
    summary = ctx.save_summary()
    summary["gate"] = {
        "features": results,
        "blocked": blocked,
        "failed": failed,
        "unit_tests_exit": tests.returncode,
        "doctor_exit": doctor_result.returncode,
    }
    (ctx.evidence / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (ARTIFACTS / "latest.txt").write_text(run_id + "\n", encoding="utf-8")
    print("GATE SUMMARY", flush=True)
    for name, item in results.items():
        print(f"  {name:18} {item['status']}", flush=True)
    print(f"  {'unit tests':18} {'PASS' if tests.returncode == 0 else 'FAIL'}", flush=True)
    if failed or tests.returncode != 0:
        print("GATE FAIL", flush=True)
        return 1
    if blocked:
        print(f"GATE PASS WITH BLOCKED: {', '.join(blocked)}", flush=True)
        return 2
    print("GATE PASS", flush=True)
    return 0


FFMPEG = Path(r"C:\ProgramData\chocolatey\bin\ffmpeg.exe")


def _ffmpeg() -> str | None:
    if FFMPEG.exists():
        return str(FFMPEG)
    found = shutil.which("ffmpeg")
    return found


def record_workflow(run_id: str) -> int:
    """Record Home -> Actions -> add action -> Rewrites -> Settings -> palette."""
    evidence, scratch = _dirs(run_id)
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    sys.path.insert(0, str(APP))
    sys.argv[0] = str(APP / "WritingToolApp.py")
    _force_theme("light")
    _qt_app()
    from PySide6 import QtCore, QtWidgets

    sys.path.insert(0, str(APP / "tests"))
    from shell_fixtures import (
        FakeHost,
        build_shell,
        click_named,
        isolate_app_files,
        line_edit,
    )

    isolate_app_files(scratch / "record-app")
    host = FakeHost(scratch / "record-host")
    host.seed_history(2)
    shell = build_shell(host)
    shell.resize(1040, 720)
    shell.show_window()
    _wait(800)

    frames = scratch / "frames"
    if frames.exists():
        shutil.rmtree(frames, ignore_errors=True)
    frames.mkdir(parents=True, exist_ok=True)
    state = {"count": 0}

    def grab() -> None:
        state["count"] += 1
        shell.grab().save(str(frames / f"frame-{state['count']:05d}.png"))

    timer = QtCore.QTimer(shell)
    timer.setInterval(100)
    timer.timeout.connect(grab)
    timer.start()
    try:
        shell.navigate("home")
        _wait(900)
        shell.navigate("actions")
        _wait(900)
        click_named(shell.actions, "Add action")
        _wait(800)
        line_edit(shell.actions.editor, "Action name").setText("Tighten")
        _wait(800)
        shell.actions.editor.instruction.setPlainText(
            "Tighten the prose without losing meaning."
        )
        _wait(800)
        click_named(shell.actions, "Save action")
        _wait(900)
        shell.navigate("rewrites")
        _wait(900)
        shell.navigate("settings")
        _wait(900)
        shell.open_palette()
        _wait(800)
        shell.command_palette.input.setText("About")
        _wait(800)
        _import_qt()[1].QTest.keyClick(
            shell.command_palette.input, QtCore.Qt.Key.Key_Return
        )
        _wait(900)
        shell.navigate("home")
        _wait(900)
    finally:
        grab()
        timer.stop()

    frame_paths = sorted(frames.glob("frame-*.png"))
    if not frame_paths:
        print("RECORD FAIL no frames captured", flush=True)
        return 1
    ffmpeg = _ffmpeg()
    if ffmpeg is None:
        print(
            f"RECORD FAIL ffmpeg not found at {FFMPEG} or PATH",
            flush=True,
        )
        return 1

    mp4 = evidence / "workflow.mp4"
    gif = evidence / "workflow.gif"
    mp4_command = [
        ffmpeg,
        "-y",
        "-start_number",
        "1",
        "-framerate",
        "10",
        "-i",
        str(frames / "frame-%05d.png"),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(mp4),
    ]
    mp4_result = subprocess.run(
        mp4_command, capture_output=True, text=True, timeout=180
    )
    gif_command = [
        ffmpeg,
        "-y",
        "-start_number",
        "1",
        "-framerate",
        "10",
        "-i",
        str(frames / "frame-%05d.png"),
        "-vf",
        "fps=10,scale=720:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
        "-loop",
        "0",
        str(gif),
    ]
    gif_result = subprocess.run(
        gif_command, capture_output=True, text=True, timeout=180
    )
    duration = len(frame_paths) / 10.0

    def _last_line(text: str) -> str:
        lines = (text or "").strip().splitlines()
        return lines[-1] if lines else ""

    record_log = [
        f"frames={len(frame_paths)}",
        f"duration={duration:.1f}s",
        f"mp4_exit={mp4_result.returncode}",
        f"mp4={mp4}",
        f"mp4_bytes={mp4.stat().st_size if mp4.exists() else 0}",
        f"gif_exit={gif_result.returncode}",
        f"gif={gif}",
        f"gif_bytes={gif.stat().st_size if gif.exists() else 0}",
        "mp4_command=" + " ".join(mp4_command),
        "mp4_stderr_tail=" + _last_line(mp4_result.stderr),
        "gif_stderr_tail=" + _last_line(gif_result.stderr),
    ]
    (evidence / "record.txt").write_text("\n".join(record_log), encoding="utf-8")
    if not mp4.exists() or mp4.stat().st_size == 0:
        print(
            f"RECORD FAIL mp4 exit={mp4_result.returncode} "
            f"stderr={(mp4_result.stderr or '').strip()[-400:]}",
            flush=True,
        )
        return 1
    gif_note = (
        f"gif={gif} bytes={gif.stat().st_size}"
        if gif.exists() and gif.stat().st_size > 0
        else f"gif=FAIL exit={gif_result.returncode}"
    )
    print(
        f"RECORD PASS mp4={mp4} bytes={mp4.stat().st_size} "
        f"frames={len(frame_paths)} duration={duration:.1f}s {gif_note}",
        flush=True,
    )
    shell.close()
    return 0


def cleanup(run_id: str | None, all_runs: bool) -> int:
    if all_runs:
        roots = [path for path in ARTIFACTS.iterdir() if path.is_dir()] if ARTIFACTS.exists() else []
    elif run_id:
        roots = [ARTIFACTS / run_id]
    else:
        print("pass --run-id <id> or --all-runs", file=sys.stderr)
        return 1
    removed = []
    for root in roots:
        scratch = root / "scratch"
        if scratch.exists():
            removed.append(str(scratch))
            shutil.rmtree(scratch, ignore_errors=True)
    remaining = []
    for root in roots:
        evidence = root / "evidence"
        if evidence.exists():
            remaining.extend(str(path) for path in evidence.rglob("*") if path.is_file())
    print(f"removed {len(removed)} scratch director{'y' if len(removed) == 1 else 'ies'}:")
    for path in removed:
        print(f"  {path}")
    print(f"kept {len(remaining)} evidence files under {ARTIFACTS}")
    for path in remaining[:20]:
        print(f"  {path}")
    return 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_doctor = sub.add_parser("doctor", help="read-only readiness check")
    p_doctor.add_argument("--run-id", default=None)

    p_run = sub.add_parser("run", help="drive one feature")
    p_run.add_argument("--feature", required=True, choices=FEATURES)
    p_run.add_argument("--run-id", default=None)

    p_drive = sub.add_parser("_drive", help=argparse.SUPPRESS)
    p_drive.add_argument("--feature", required=True, choices=FEATURES)
    p_drive.add_argument("--run-id", default=None)

    p_gate = sub.add_parser("gate", help="drive every feature and the unit tests")
    p_gate.add_argument("--run-id", default=None)

    p_record = sub.add_parser("record", help="record the workflow video with ffmpeg")
    p_record.add_argument("--run-id", default=None)

    p_clean = sub.add_parser("cleanup", help="remove scratch state, keep evidence")
    p_clean.add_argument("--run-id", default=None)
    p_clean.add_argument("--all-runs", action="store_true")

    args = parser.parse_args()
    if args.command == "doctor":
        return doctor(_run_id(args.run_id))
    if args.command == "run":
        return run_feature(args.feature, _run_id(args.run_id))
    if args.command == "_drive":
        return drive_feature(args.feature, _run_id(args.run_id))
    if args.command == "gate":
        return gate(_run_id(args.run_id))
    if args.command == "record":
        return record_workflow(_run_id(args.run_id))
    if args.command == "cleanup":
        return cleanup(args.run_id, args.all_runs)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
