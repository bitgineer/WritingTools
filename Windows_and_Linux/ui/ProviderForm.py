"""One provider form for Settings and first-run setup.

The form owns provider choice, presets, key entry, model discovery, connection
testing, and save. It never opens a window and never writes a bad config.
"""

from __future__ import annotations

import copy
import logging
import threading

from PySide6 import QtCore, QtWidgets

from aiprovider import AIProvider
from rework.theme import current_palette
from ui import ModelCatalog, ProviderPresets
from ui.Components import Banner
from ui.UIUtils import UIUtils
from ui.design import GAP, field_label, ghost_button, primary_button

PROVIDER_HINT = {
    "Gemini (Recommended)": "Google Gemini. Fast, with a free tier.",
    "OpenAI Compatible (For Experts)": "Any service that speaks the OpenAI chat API.",
    "Ollama (For Experts)": "A local model served by Ollama on this machine.",
}


class ProviderForm(QtWidgets.QWidget):
    saved = QtCore.Signal()
    tested = QtCore.Signal(bool, str)
    models_loaded = QtCore.Signal(object)
    models_failed = QtCore.Signal(str)

    def __init__(
        self,
        app,
        save_label: str = "Save provider",
        compact: bool = False,
        on_back=None,
        parent=None,
    ):
        super().__init__(parent)
        self.app = app
        self._save_label = save_label
        self._compact = compact
        self._on_back = on_back
        self._palette = current_palette()
        self._current_name = ""
        self._drafts: dict[str, dict[str, str]] = {}
        self._loading_models = False
        self._testing = False
        self._model_widgets: list[QtWidgets.QWidget] = []
        self._preset_widgets: list[QtWidgets.QWidget] = []

        self.tested.connect(self._on_tested)
        self.models_loaded.connect(self._models_loaded)
        self.models_failed.connect(self._models_failed)
        self._build()
        initial = self._initial_provider()
        index = self.provider_combo.findText(initial)
        if index >= 0:
            self.provider_combo.blockSignals(True)
            self.provider_combo.setCurrentIndex(index)
            self.provider_combo.blockSignals(False)
        self._current_name = self.provider_name()
        self._render_provider(self._current_name)

    def _build(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(GAP)

        self.banner = Banner("", tone="warning")
        self.banner.hide()
        layout.addWidget(self.banner)

        layout.addWidget(field_label("Provider"))
        self.provider_combo = QtWidgets.QComboBox()
        self.provider_combo.setAccessibleName("AI Provider")
        for provider in self.app.providers:
            self.provider_combo.addItem(provider.provider_name)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        layout.addWidget(self.provider_combo)

        self.provider_note = QtWidgets.QLabel("")
        self.provider_note.setObjectName("FieldHint")
        self.provider_note.setWordWrap(True)
        layout.addWidget(self.provider_note)

        self.preset_host = QtWidgets.QWidget()
        preset_layout = QtWidgets.QVBoxLayout(self.preset_host)
        preset_layout.setContentsMargins(0, 0, 0, 0)
        preset_layout.setSpacing(6)
        preset_layout.addWidget(field_label("Quick setup"))
        self.preset_combo = QtWidgets.QComboBox()
        self.preset_combo.setAccessibleName("Service preset")
        self.preset_combo.addItem("Choose a service...", "")
        for preset in ProviderPresets.load():
            self.preset_combo.addItem(preset.name, preset.id)
        self.preset_combo.currentIndexChanged.connect(self._apply_preset)
        preset_layout.addWidget(self.preset_combo)
        self.preset_note = QtWidgets.QLabel("")
        self.preset_note.setObjectName("FieldHint")
        self.preset_note.setWordWrap(True)
        self.preset_note.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.preset_note.setOpenExternalLinks(True)
        preset_layout.addWidget(self.preset_note)
        layout.addWidget(self.preset_host)
        self._preset_widgets.append(self.preset_host)

        self.fields_host = QtWidgets.QWidget()
        self.fields_layout = QtWidgets.QVBoxLayout(self.fields_host)
        self.fields_layout.setContentsMargins(0, 0, 0, 0)
        self.fields_layout.setSpacing(10)
        layout.addWidget(self.fields_host)

        self.model_host = QtWidgets.QWidget()
        model_layout = QtWidgets.QHBoxLayout(self.model_host)
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_layout.setSpacing(8)
        self.model_combo = QtWidgets.QComboBox()
        self.model_combo.setAccessibleName("Available models")
        self.model_combo.setEnabled(False)
        self.model_combo.currentTextChanged.connect(self._pick_model)
        model_layout.addWidget(self.model_combo, 1)
        self.load_button = QtWidgets.QPushButton("Load models")
        self.load_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.load_button.setAccessibleName("Load models")
        self.load_button.clicked.connect(self._load_models)
        model_layout.addWidget(self.load_button)
        layout.addWidget(self.model_host)
        self._model_widgets.append(self.model_host)

        self.model_status = QtWidgets.QLabel("")
        self.model_status.setObjectName("FieldHint")
        self.model_status.setWordWrap(True)
        layout.addWidget(self.model_status)

        hint = QtWidgets.QLabel(
            "The model list comes from the provider. If it is empty, type the model id."
        )
        hint.setObjectName("FieldHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.model_hint = hint

        footer = QtWidgets.QHBoxLayout()
        footer.setSpacing(8)
        if self._on_back is not None:
            back = ghost_button("Back")
            back.clicked.connect(self._on_back)
            footer.addWidget(back)
        self.test_button = ghost_button("Test connection")
        self.test_button.clicked.connect(self._test)
        footer.addWidget(self.test_button)
        footer.addStretch(1)
        self.save_button = primary_button(self._save_label)
        self.save_button.clicked.connect(self.save)
        footer.addWidget(self.save_button)
        layout.addLayout(footer)

        self.status = QtWidgets.QLabel("")
        self.status.setObjectName("FieldHint")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

    def _initial_provider(self) -> str:
        saved = (self.app.config or {}).get("provider", "")
        names = [provider.provider_name for provider in self.app.providers]
        return saved if saved in names else names[0]

    def set_provider(self, name: str) -> None:
        index = self.provider_combo.findText(name)
        if index < 0:
            return
        if self.provider_combo.currentIndex() == index:
            self._current_name = name
            self._render_provider(name)
        else:
            self.provider_combo.setCurrentIndex(index)

    def provider_name(self) -> str:
        return self.provider_combo.currentText()

    def focus_provider(self) -> None:
        self.provider_combo.setFocus()

    def provider(self) -> AIProvider:
        return self.app.providers[self.provider_combo.currentIndex()]

    def _on_provider_changed(self, _index: int) -> None:
        if self._current_name:
            previous = self._provider_by_name(self._current_name)
            if previous is not None:
                self._drafts[self._current_name] = self._collect_provider_values(previous)
        name = self.provider_name()
        self._current_name = name
        self._render_provider(name)

    def _provider_by_name(self, name: str):
        for provider in self.app.providers:
            if provider.provider_name == name:
                return provider
        return None

    def _render_provider(self, name: str) -> None:
        provider = self.provider()
        self.provider_note.setText(PROVIDER_HINT.get(name, provider.description))
        self.banner.hide()
        self.status.setText("")

        UIUtils.clear_layout(self.fields_layout)
        self.show_key = None
        saved = dict(self._drafts.get(name) or {})
        if not saved:
            saved = dict((self.app.config or {}).get("providers", {}).get(name, {}))

        for setting in provider.settings:
            value = saved.get(setting.name, setting.default_value)
            setting.set_value(value)
            setting.render_to_layout(self.fields_layout)
            if getattr(setting, "secret", False) and setting.input is not None:
                self.show_key = QtWidgets.QCheckBox("Show API key")
                self.show_key.setAccessibleName("Show API key")
                self.show_key.toggled.connect(self._toggle_key_visibility)
                self.fields_layout.addWidget(self.show_key)

        is_openai = name == "OpenAI Compatible (For Experts)"
        self.preset_host.setVisible(is_openai)
        self.model_host.setVisible(is_openai)
        self.model_status.setVisible(is_openai)
        self.model_hint.setVisible(is_openai)
        if is_openai:
            self._restore_preset(saved)
            self._reset_model_picker()
        else:
            self.preset_combo.blockSignals(True)
            self.preset_combo.setCurrentIndex(0)
            self.preset_combo.blockSignals(False)
            self.preset_note.setText("")

    def _setting(self, name: str):
        for setting in self.provider().settings:
            if setting.name == name:
                return setting
        return None

    def _input(self, name: str):
        setting = self._setting(name)
        return getattr(setting, "input", None) if setting is not None else None

    def _collect_values(self) -> dict[str, str]:
        return self._collect_provider_values(self.provider())

    def _collect_provider_values(self, provider) -> dict[str, str]:
        values = {}
        for setting in provider.settings:
            input_widget = getattr(setting, "input", None)
            if input_widget is not None:
                values[setting.name] = input_widget.text()
            elif getattr(setting, "dropdown", None) is not None:
                values[setting.name] = setting.get_value()
            else:
                values[setting.name] = str(getattr(setting, "internal_value", "") or "")
        return values

    def values(self) -> dict[str, str]:
        return self._collect_values()

    def _restore_preset(self, saved: dict[str, str]) -> None:
        preset_id = (self.app.config or {}).get("provider_preset", "")
        index = self.preset_combo.findData(preset_id)
        self.preset_combo.blockSignals(True)
        self.preset_combo.setCurrentIndex(index if index > 0 else 0)
        self.preset_combo.blockSignals(False)
        if index > 0:
            self._show_preset_note(preset_id)

    def _apply_preset(self, _index: int) -> None:
        preset_id = self.preset_combo.currentData() or ""
        if not preset_id:
            self.preset_note.setText("")
            return
        preset = ProviderPresets.get(preset_id)
        if preset is None:
            self.preset_note.setText("")
            return
        base = self._input("api_base")
        model = self._input("api_model")
        if base is not None:
            base.setText(preset.base_url)
        if model is not None:
            model.setText(preset.model)
        self._reset_model_picker()
        self.model_status.setText("Pick a service, then load its models.")
        self._show_preset_note(preset_id)

    def _show_preset_note(self, preset_id: str) -> None:
        preset = ProviderPresets.get(preset_id)
        if preset is None:
            return
        parts = []
        if preset.note:
            parts.append(preset.note)
        if preset.key_url:
            parts.append(f'<a href="{preset.key_url}">Get an API key</a>')
        if preset.docs_url:
            parts.append(f'<a href="{preset.docs_url}">Docs</a>')
        self.preset_note.setText(" \u00b7 ".join(parts))

    def _toggle_key_visibility(self, visible: bool) -> None:
        for setting in self.provider().settings:
            if getattr(setting, "secret", False) and setting.input is not None:
                setting.input.setEchoMode(
                    QtWidgets.QLineEdit.EchoMode.Normal
                    if visible
                    else QtWidgets.QLineEdit.EchoMode.Password
                )

    def _reset_model_picker(self) -> None:
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.setEnabled(False)
        self.model_combo.blockSignals(False)
        self.model_status.setText(
            "Enter your API key, then load the list. The model field stays editable."
        )

    def _pick_model(self, model: str) -> None:
        if not model.strip():
            return
        field = self._input("api_model")
        if field is not None:
            field.setText(model)

    def _load_models(self) -> None:
        if self._loading_models:
            return
        base = self._input("api_base")
        key = self._input("api_key")
        base_url = base.text() if base is not None else ""
        try:
            ModelCatalog.models_url(base_url)
        except ModelCatalog.ModelFetchError as error:
            self.model_status.setText(str(error))
            return
        self._loading_models = True
        self.load_button.setEnabled(False)
        self.model_status.setText("Loading models...")
        api_key = key.text() if key is not None else ""

        def work():
            try:
                models = ModelCatalog.fetch_models(base_url, api_key)
            except Exception as error:
                self.models_failed.emit(str(error))
            else:
                self.models_loaded.emit(models)

        threading.Thread(target=work, daemon=True).start()

    @QtCore.Slot(list)
    def _models_loaded(self, models: list) -> None:
        self._loading_models = False
        self.load_button.setEnabled(True)
        current = self._input("api_model")
        current_text = current.text() if current is not None else ""
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItems(models)
        self.model_combo.setEnabled(bool(models))
        self.model_combo.setCurrentIndex(self.model_combo.findText(current_text))
        self.model_combo.blockSignals(False)
        if models:
            free = sum(1 for model in models if model.endswith(":free"))
            note = f"{len(models)} models."
            if free:
                note += " Models marked :free may be limited to specific apps."
            self.model_status.setText(note + " Pick one to fill the model field.")

    @QtCore.Slot(str)
    def _models_failed(self, message: str) -> None:
        self._loading_models = False
        self.load_button.setEnabled(True)
        self.model_status.setText(message)

    def _test(self) -> None:
        if self._testing:
            return
        values = self._collect_values()
        name = self.provider_name()
        try:
            probe = copy.copy(self.app.providers[self.provider_combo.currentIndex()])
            probe.load_config(values)
        except Exception as error:
            self._show_error("Provider not ready", str(error))
            return
        self._testing = True
        self.test_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.status.setText("Testing connection...")

        def work():
            try:
                detail = probe.test_connection()
            except Exception as error:
                self.tested.emit(False, str(error))
            else:
                self.tested.emit(True, detail)

        threading.Thread(target=work, daemon=True).start()

    @QtCore.Slot(bool, str)
    def _on_tested(self, ok: bool, message: str) -> None:
        self._testing = False
        self.test_button.setEnabled(True)
        self.save_button.setEnabled(True)
        if ok:
            self.banner.hide()
            self.status.setText(message)
        else:
            self._show_error("Connection failed", message)

    def _show_error(self, title: str, body: str) -> None:
        self.banner.set_content(title, body)
        self.banner.show()
        self.banner.raise_()
        self.status.setText("")

    def validate(self) -> tuple[bool, str]:
        values = self._collect_values()
        for field, label in (
            ("api_key", "API key"),
            ("api_base", "API base URL"),
            ("api_model", "model"),
        ):
            if field in values and not str(values[field]).strip():
                return False, f"Enter the {label}."
        try:
            copy.copy(self.app.providers[self.provider_combo.currentIndex()]).load_config(values)
        except Exception as error:
            return False, str(error)
        return True, ""

    def save(self) -> bool:
        ok, error = self.validate()
        if not ok:
            self._show_error("Provider not ready", error)
            return False

        provider = self.provider()
        values = self._collect_values()
        self.app.config.setdefault("providers", {})
        try:
            provider.load_config(values)
            provider.save_config()
            config = self.app.config
            config["provider"] = provider.provider_name
            config["streaming"] = False
            if provider.provider_name == "OpenAI Compatible (For Experts)":
                config["provider_preset"] = self.preset_combo.currentData() or ""
            self.app.save_config(config)
        except Exception as error:
            logging.exception("Could not save the provider")
            self._show_error("Could not save", str(error))
            return False

        self.app.current_provider = provider
        if hasattr(self.app, "create_tray_icon"):
            self.app.create_tray_icon()
        if hasattr(self.app, "register_hotkey"):
            self.app.register_hotkey()
        self._drafts.pop(provider.provider_name, None)
        self.banner.hide()
        self.status.setText("Saved. The provider is ready.")
        self.saved.emit()
        return True
