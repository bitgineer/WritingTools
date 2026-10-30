"""Atomic configuration storage.

The app has one config dict. This store is the only writer. It keeps the same
dict object alive so existing surfaces can read it, and replaces the file in
one step so a crash cannot leave a half-written config.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


class ConfigStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.data: dict[str, Any] = {}
        self.recovered_from: str | None = None
        self.load()

    def load(self) -> dict[str, Any]:
        self.recovered_from = None
        if not self.path.exists():
            self.data = {}
            return self.data

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("config root is not an object")
        except (OSError, ValueError):
            self.data = {}
            self.recovered_from = self._quarantine()
            logging.exception(
                "Config file could not be read; moved it to %s", self.recovered_from
            )
            return self.data

        self.data = raw
        return self.data

    def _quarantine(self) -> str:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = self.path.with_name(f"{self.path.name}.broken-{stamp}")
        try:
            shutil.move(str(self.path), str(target))
        except OSError:
            logging.exception("Could not move the unreadable config aside")
            return ""
        return str(target)

    def save(self, data: dict[str, Any] | None = None) -> None:
        if data is not None:
            if not isinstance(data, dict):
                raise TypeError("config must be a dict")
            if data is not self.data:
                self.data.clear()
                self.data.update(data)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f"{self.path.name}.tmp")
        try:
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump(self.data, handle, indent=4)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary.exists():
                try:
                    temporary.unlink()
                except OSError:
                    logging.exception("Could not remove the temporary config file")

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any, save: bool = False) -> None:
        self.data[key] = value
        if save:
            self.save()

    def update(self, values: dict[str, Any], save: bool = False) -> None:
        self.data.update(values)
        if save:
            self.save()

    def snapshot(self) -> dict[str, Any]:
        return json.loads(json.dumps(self.data))

    def provider(self, name: str) -> dict[str, Any]:
        providers = self.data.get("providers")
        if not isinstance(providers, dict):
            return {}
        values = providers.get(name)
        return values if isinstance(values, dict) else {}

    def set_provider(self, name: str, values: dict[str, Any], save: bool = False) -> None:
        providers = self.data.setdefault("providers", {})
        if not isinstance(providers, dict):
            providers = {}
            self.data["providers"] = providers
        providers[name] = dict(values)
        if save:
            self.save()
