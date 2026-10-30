# Settings and provider setup

Settings owns the shortcut, the startup control, and the AI provider section. The same window opens in a providers-only mode during first-run setup, where the footer button reads Finish AI Setup. A user can switch from Gemini to OpenAI Compatible or Ollama, enter that provider's fields, save, and finish setup. Status: verified. `tests/test_provider_switch.py` exists and passes. The window journey below and the real-app construction probe both pass at this revision.

## Sub-features

- `settings-open` opens the full Settings window from the tray with the General, Actions, and AI Provider sections.
- `settings-actions` lists every popup action with its mode and Edit and Delete controls, plus Add action and Reset actions. Edits save in place.
- `provider-list` lists the real providers in this order: Gemini (Recommended), OpenAI Compatible (For Experts), Ollama (For Experts).
- `provider-switch-openai` replaces the Gemini fields with API Key, API Base URL, API Organisation, API Project, and API Model.
- `provider-presets` fills the base URL and model from a service preset and links to that service's key page.
- `model-list` asks the configured endpoint for its model list and fills a picker. The model field stays editable.
- `provider-switch-ollama` replaces them with API Base URL, API Model, and the keep-alive field, with the local defaults.
- `settings-save` saves the selected provider, stores its values, makes it the live provider, and re-registers the hotkey.
- `finish-setup` opens providers-only mode from onboarding, hides the General section, saves the provider, creates the tray icon, and closes.
- `provider-switch-gate` runs `tests/test_provider_switch.py` before the drive and refuses to claim the feature if it is missing or failing.

## How to get to it (user POV)

- Right-click the Writing Tools tray icon and choose Settings.
- On first run, choose Continue on the welcome screen. The providers-only settings window opens. Choose a provider, fill its fields, and choose Finish AI Setup.
- To switch later, open Settings, choose a provider in the AI Provider dropdown, edit its fields, and choose Save.

## Driving it with verify.py

Preconditions:

- Run from the repository root.
- `Windows_and_Linux/tests/test_provider_switch.py` exists and passes. The drive checks this first. If the file is missing, the run is `BLOCKED` and the feature stays unverified.
- Use dummy values only. The drive writes its config to `artifacts/verify/<run-id>/evidence/settings-config.json`. It never writes `Windows_and_Linux/config.json`.
- The real provider constructors run. They do not make network calls during the drive. A dummy OpenAI key and an unreachable local base URL are fine because no request is sent.
- The helper uses the native Qt platform when a display is available: `windows` on Windows, `xcb` on Linux with `DISPLAY`. It falls back to `offscreen` for headless logic runs. Set `VERIFY_QT_PLATFORM` to force a platform.

- **Gate on the provider-switch test.** Run `.\.venv\Scripts\python.exe -B .opencode\skills\verify-writingtools\scripts\verify.py run --feature settings --run-id <id>`. The first check reads `provider-switch dependency: tests/test_provider_switch.py passed`. If the file is absent, the transcript reads `provider-switch dependency: ... is missing; settings/provider setup is unverified` and the result is `BLOCKED`.
- **Check the real provider list.** The transcript reads `real providers are listed: Gemini (Recommended), OpenAI Compatible (For Experts), Ollama (For Experts)` and `full settings starts on Gemini: Gemini (Recommended)`. The full window screenshot is `settings-full-light.png` and shows the General card, the Actions card, the AI Provider card, and the live-apply notice.
- **Check the Actions card.** The transcript reads `settings lists the popup actions: rows=8` or more and `settings offers add and reset: add=True, reset=True`. The rows are the same actions the popup shows.
- **Switch to OpenAI Compatible.** The drive sets the AI Provider combo to OpenAI Compatible. It flushes deferred deletes, then reads the visible fields. The transcript reads `OpenAI Compatible fields render: API Key, API Base URL, API Organisation, API Project, API Model`. It chooses OpenRouter in the Service preset combo and reads `preset fills the endpoint: https://openrouter.ai/api/v1`, `preset fills the model: moonshotai/kimi-k3.1-pro`, `preset links the key page: ...`, and `model picker can load the provider list: picker=True`. The live model fetch is covered by `tests/test_model_catalog.py` against a local server, not by this drive. It then types `verify-openai-key`, `https://example.invalid/v1`, and `verify-openai-model` into the visible fields. The screenshot is `settings-openai-light.png`.
- **Switch to Ollama.** The drive sets the combo to Ollama and flushes deferred deletes. The transcript reads `Ollama fields render with defaults: base=http://localhost:11434 model=llama3.1:8b`. It types `http://127.0.0.1:11434`, `verify-ollama-model`, and `7` into the visible fields. The screenshot is `settings-ollama-light.png`.
- **Save Ollama.** The drive clicks the real `Save` button. The transcript reads `saving Ollama switches the provider: Ollama (For Experts)`, `Ollama values are saved: {...}`, `Ollama becomes the live provider: Ollama (For Experts)`, `hotkey is re-registered: save_config, register_hotkey`, and `full settings closes`. The saved config is `settings-config.json`.
- **Finish setup from providers-only mode.** The drive opens a new `SettingsWindow` with `providers_only=True`. The transcript reads `finish setup hides general settings`. It switches to OpenAI Compatible, fills the fields, and clicks `Finish AI Setup`. The transcript reads `Finish AI Setup switches to OpenAI Compatible`, `Finish AI Setup creates the tray icon`, and `Finish AI Setup closes`. The screenshot is `settings-finish-openai-light.png`.
- **Probe the real app.** The drive runs the isolated `WritingToolApp` probe. At this revision the transcript reads `real app launch: real WritingToolApp constructed and exited` and the result is `PASS`. The probe log is `app-launch.txt`. If the probe fails, the result is `PASS_WITH_BLOCKER`, and the tray app is not usable.
- **Proof.** Keep `settings-full-light.png`, `settings-openai-light.png`, `settings-ollama-light.png`, `settings-finish-openai-light.png`, `settings-config.json`, `provider-switch-test.txt`, `app-launch.txt`, `transcript.txt`, and `summary.json`.

## Gotchas

- The settings window journey proves the window, the provider switching, the save contract, and the Finish AI Setup contract. The separate real-app probe proves the tray app constructs and builds its menu. The drive does not click the tray Settings action itself. Do not report that tray click as covered.
- Do not replace the `test_provider_switch.py` gate with a direct `save_settings` call. The test is the named dependency for this feature. If it is missing, report the dependency and leave the feature unverified.
- The provider panels use `deleteLater`. Right after a combo change, `findChildren` can still see the old provider's fields. The helper calls `sendPostedEvents` for deferred deletes before it reads or types. A new drive must do the same.
- The drive uses an app shell for `create_tray_icon`, `register_hotkey`, and `save_config`. The shell records the calls and writes the config to evidence. The separate real-app probe is what catches a tray-menu or construction failure. Do not report the shell as the real app.
- Do not use a real API key in this drive. The config file is evidence and may be read later.
- The OpenAI Compatible base URL is intentionally unreachable. The client is constructed but no request is sent. A drive that sends a request is out of scope.
- The full Settings window shows the live-apply notice ("Provider and shortcut apply when you save. Actions apply right away."). The providers-only window does not. Assert both states separately.
- Action add, edit, delete, and reset save immediately and re-register action shortcuts. They do not wait for the Save button, which owns the provider and shortcut only.
- An invalid shortcut is rejected with a message before the provider or config is written. Drive it by typing a malformed value and clicking Save; the config must keep its previous shortcut.
- The current provider-switch fix may be uncommitted in the working tree. `summary.json` records `git_head` and `git_status`. Quote that state when you report the result.
