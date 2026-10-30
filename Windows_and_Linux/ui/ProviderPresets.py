"""Provider presets for the OpenAI-compatible form.

The catalog is data (`provider_presets.json`), not a class per vendor. This
module loads and validates it. Settings uses it to prefill the base URL and
model and to link to the provider's key page.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Preset:
    id: str
    name: str
    base_url: str
    model: str
    key_url: str = ""
    docs_url: str = ""
    note: str = ""


def catalog_path() -> str:
    return os.path.join(os.path.dirname(sys.argv[0]), "provider_presets.json")


def load(path: str | None = None) -> list[Preset]:
    target = path or catalog_path()
    try:
        with open(target, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        logging.exception("Could not read the provider presets at %s", target)
        return []

    presets = []
    for item in data.get("presets", []):
        if not isinstance(item, dict):
            continue
        preset = Preset(
            id=str(item.get("id", "")).strip(),
            name=str(item.get("name", "")).strip(),
            base_url=str(item.get("base_url", "")).strip(),
            model=str(item.get("model", "")).strip(),
            key_url=str(item.get("key_url", "")).strip(),
            docs_url=str(item.get("docs_url", "")).strip(),
            note=str(item.get("note", "")).strip(),
        )
        if validate([preset]):
            logging.warning("Skipping an invalid provider preset: %s", preset.id)
            continue
        presets.append(preset)
    return presets


def get(preset_id: str, presets: list[Preset] | None = None) -> Preset | None:
    for preset in presets if presets is not None else load():
        if preset.id == preset_id:
            return preset
    return None


def validate(presets: list[Preset]) -> list[str]:
    """Return a list of problems. An empty list means the catalog is usable."""
    problems = []
    seen = set()
    for preset in presets:
        if not preset.id:
            problems.append("a preset has no id")
        if preset.id in seen:
            problems.append(f"duplicate preset id {preset.id}")
        seen.add(preset.id)
        if not preset.name:
            problems.append(f"{preset.id} has no name")
        if not preset.base_url.startswith("https://"):
            problems.append(f"{preset.id} base URL is not https")
        if not preset.model:
            problems.append(f"{preset.id} has no default model")
        if preset.key_url and not preset.key_url.startswith("https://"):
            problems.append(f"{preset.id} key URL is not https")
        if preset.docs_url and not preset.docs_url.startswith("https://"):
            problems.append(f"{preset.id} docs URL is not https")
    return problems
