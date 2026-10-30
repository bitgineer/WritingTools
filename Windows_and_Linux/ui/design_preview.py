"""Render app surfaces to PNG for visual verification.

Run from Windows_and_Linux:
    python -m ui.design_preview --surface popup --theme light
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PySide6 import QtCore, QtWidgets

BASE = Path(__file__).resolve().parents[1]
OUT = BASE.parent / "design" / "qt"


class FakeApp:
    def __init__(self):
        self.config = {"update_available": False}
        self.providers = []

    def load_options(self):
        return json.loads((BASE / "options.json").read_text(encoding="utf-8"))

    def process_option(self, *args, **kwargs):
        pass

    def exit_app(self):
        pass

    def save_config(self, config):
        self.config = config

    def _to_pynput_hotkey(self, value):
        return value


def _set_theme(theme: str) -> None:
    import rework.theme as tokens
    import ui.CustomPopupWindow
    import ui.ResponseWindow
    import ui.SettingsWindow
    import ui.UIUtils
    import ui.design

    target = tokens.DARK if theme == "dark" else tokens.LIGHT
    forced = lambda: target
    tokens.current_palette = forced
    ui.CustomPopupWindow.current_palette = forced
    ui.ResponseWindow.current_palette = forced
    ui.SettingsWindow.current_palette = forced
    ui.UIUtils.current_palette = forced
    ui.design.current_palette = forced


class FakeProvider:
    def __init__(self):
        from aiprovider import DropdownSetting, TextSetting

        self.provider_name = "Gemini"
        self.description = (
            "Connect a cloud model or a local endpoint. Keys stay on this device."
        )
        self.logo = "gemini"
        self.button_text = "Get an API key"
        self.button_action = lambda: None
        self.settings = [
            TextSetting("api_key", "API key", "", "Paste your Gemini API key"),
            DropdownSetting(
                "model_name",
                "Model",
                "gemini-flash-latest",
                options=[
                    ("Gemini Flash", "gemini-flash-latest"),
                    ("Gemini Pro", "gemini-pro"),
                ],
                allow_custom=True,
            ),
        ]

    def save_config(self):
        pass

    def load_config(self, config):
        pass


class FakeSettingsApp(FakeApp):
    def __init__(self):
        super().__init__()
        self.config = {
            "shortcut": "ctrl+space",
            "provider": "Gemini",
            "providers": {},
        }
        self.providers = [FakeProvider()]

    def create_tray_icon(self):
        pass

    def register_hotkey(self):
        pass


class FakeOnboardingApp(FakeApp):
    def __init__(self):
        super().__init__()
        self.config = {}
        self.calls = []

    def show_settings(self, providers_only=False):
        self.calls.append(providers_only)


class FakeResponseApp(QtCore.QObject):
    followup_response_signal = QtCore.Signal(str)
    show_message_signal = QtCore.Signal(str, str)

    def __init__(self):
        super().__init__()
        self.config = {}


def _popup(edit=False):
    import ui.CustomPopupWindow as popup_module
    from ui.design import apply_app_style

    app = QtWidgets.QApplication([sys.argv[0]])
    apply_app_style(app)

    popup_module.CustomPopupWindow.load_options = staticmethod(
        lambda: json.loads((BASE / "options.json").read_text(encoding="utf-8"))
    )
    window = popup_module.CustomPopupWindow(FakeApp())
    window.show()
    app.processEvents()
    if edit:
        window.custom_input.setText("Make it funnier")
        window.custom_input.setFocus()
        app.processEvents()
    return app, window


def _dialog():
    import ui.CustomPopupWindow as popup_module
    from ui.design import apply_app_style

    app = QtWidgets.QApplication([sys.argv[0]])
    apply_app_style(app)
    window = popup_module.ButtonEditDialog(
        None,
        {
            "name": "Make it friendly",
            "instruction": "Make the selected text warmer and more conversational.",
            "open_in_window": False,
            "hotkey": "ctrl+j",
        },
    )
    window.show()
    app.processEvents()
    return app, window


def _settings():
    import ui.SettingsWindow as settings_module
    from ui.design import apply_app_style

    app = QtWidgets.QApplication([sys.argv[0]])
    apply_app_style(app)
    window = settings_module.SettingsWindow(FakeSettingsApp())
    window.show()
    app.processEvents()
    return app, window


def _onboarding():
    import ui.OnboardingWindow as onboarding_module
    from ui.design import apply_app_style

    app = QtWidgets.QApplication([sys.argv[0]])
    apply_app_style(app)
    window = onboarding_module.OnboardingWindow(FakeOnboardingApp())
    window.show()
    app.processEvents()
    return app, window


def _about():
    import ui.AboutWindow as about_module
    from ui.design import apply_app_style

    app = QtWidgets.QApplication([sys.argv[0]])
    apply_app_style(app)
    window = about_module.AboutWindow()
    window.show()
    app.processEvents()
    return app, window


def _response():
    import ui.ResponseWindow as response_module
    from ui.design import apply_app_style

    app = QtWidgets.QApplication([sys.argv[0]])
    apply_app_style(app)
    fake_app = FakeResponseApp()
    window = response_module.ResponseWindow(fake_app, "Rewrite Result")
    window.selected_text = "Original text"
    window.show()

    window.chat_area.add_message("Make it shorter, please.", is_user=True)
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
    window.resize(600, 720)
    app.processEvents()
    return app, window


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--surface",
        choices=("popup", "popup-custom", "dialog", "settings", "onboarding", "about", "response"),
        default="popup",
    )
    parser.add_argument("--theme", choices=("light", "dark"), default="light")
    args = parser.parse_args()

    sys.argv[0] = str(BASE / "WritingToolApp.py")
    _set_theme(args.theme)

    if args.surface == "popup":
        app, window = _popup()
    elif args.surface == "popup-custom":
        app, window = _popup(edit=True)
    elif args.surface == "dialog":
        app, window = _dialog()
    elif args.surface == "settings":
        app, window = _settings()
    elif args.surface == "onboarding":
        app, window = _onboarding()
    elif args.surface == "about":
        app, window = _about()
    else:
        app, window = _response()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{args.surface}-{args.theme}.png"
    window.grab().save(str(path))
    print(path)
    window.close()
    window.deleteLater()
    app.processEvents()
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
