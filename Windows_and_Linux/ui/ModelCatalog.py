"""Fetch the model list for an OpenAI-compatible provider.

The app does not ship a fixed model list per vendor. It asks the provider
that the user configured for `GET <base>/models` and fills a picker. The
model field stays editable, so a provider with no list endpoint still works.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request


class ModelFetchError(Exception):
    """A readable failure to show in the form."""


class _SameHostRedirects(urllib.request.HTTPRedirectHandler):
    """Keep an API key from following a redirect to another host or plain HTTP."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old = urllib.parse.urlsplit(req.full_url)
        new = urllib.parse.urlsplit(newurl)
        if new.hostname != old.hostname:
            raise ModelFetchError(
                "The provider redirected to another host. Loading models was stopped."
            )
        if new.scheme == "http" and old.scheme == "https":
            raise ModelFetchError(
                "Refusing to send the API key over plain HTTP."
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def models_url(base_url: str) -> str:
    base = (base_url or "").strip().rstrip("/")
    if not base:
        raise ModelFetchError("Enter an API base URL first.")
    if not (base.startswith("https://") or base.startswith("http://")):
        raise ModelFetchError("The API base URL must start with http:// or https://.")
    return f"{base}/models"


def parse_models(payload) -> list[str]:
    """Read ids from the shapes OpenAI-compatible servers return."""
    if isinstance(payload, dict):
        items = payload.get("data")
        if items is None:
            items = payload.get("models")
    elif isinstance(payload, list):
        items = payload
    else:
        items = None

    ids = []
    for item in items or []:
        if isinstance(item, dict):
            value = item.get("id") or item.get("name") or item.get("model")
        elif isinstance(item, str):
            value = item
        else:
            value = None
        if isinstance(value, str) and value.strip():
            ids.append(value.strip())
    return sorted(set(ids), key=str.lower)


def fetch_models(base_url: str, api_key: str = "", timeout: float = 12.0) -> list[str]:
    url = models_url(base_url)
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    key = (api_key or "").strip()
    if key:
        request.add_header("Authorization", f"Bearer {key}")

    try:
        opener = urllib.request.build_opener(_SameHostRedirects)
        with opener.open(request, timeout=timeout) as response:
            body = response.read(4_000_000)
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            raise ModelFetchError(
                "The provider rejected the key. Check the API key and try again."
            ) from error
        raise ModelFetchError(f"The provider returned HTTP {error.code}.") from error
    except urllib.error.URLError as error:
        raise ModelFetchError(f"Could not reach {url}. {error.reason}") from error
    except OSError as error:
        raise ModelFetchError(f"Could not reach {url}. {error}") from error

    try:
        payload = json.loads(body.decode("utf-8", "replace"))
    except ValueError as error:
        raise ModelFetchError("The provider did not return JSON.") from error

    models = parse_models(payload)
    if not models:
        raise ModelFetchError("The provider returned no models. Type the model name instead.")
    return models
