# WritingTools fork: a paper redesign

This fork starts from the upstream snapshot recorded in `UPSTREAM.md`. It answers one question first.

> When the AI rewrites your selection, what changed?

The answer is a receipt after every in-place rework, a local rewrite history, and one paper design system across the Windows/Linux app.

## What changed

- **A receipt after every in-place rework.** The text still lands instantly. A small card then shows the option, the number of changed words, the first edits, and two actions, Review and Undo. It appears without taking focus.
- **An expanded review.** Small edits render as a word-level inline diff with struck removals and underlined additions. Substantial rewrites switch to the full original and reworked text, because word marks become noise when most of the paragraph changed.
- **Local rewrite history.** Every applied rework is saved to a local SQLite database. Open **Rewrite History** from the tray to search, compare, copy, delete one entry, or clear all. History is on by default and you can turn it off in the window. History stays on this device and is never uploaded. When you run an action, the selected text is sent to the AI provider you chose. The upstream maintainer declined persistent logging on privacy grounds in issue #136. This fork makes the opposite call explicitly.
- **Provider errors are surfaced, not pasted.** When output starts with `An error occurred`, the app shows a message box and leaves the document unchanged.
- **Provider switching works in Settings.** The provider form rebuilds when you choose a different provider. Save validates the settings before it writes them. If the provider cannot start, a warning keeps setup open and nothing changes. If the saved provider fails at launch, the app opens provider setup instead of crashing. See [Provider setup](#provider-setup).
- **One paper design system across the app.** Popup, Settings, Response, Onboarding, About, History, the button editor, and the receipt share `ui/design.py`. The old gradient and plain themes and the four background PNGs are gone. Appearance follows the system light or dark setting.
- **Popup as a command palette.** The popup is a flat paper card with a clear header, one instruction field, a two-column action grid, and a footer that names Enter and Esc. Edit mode rearranges actions in place, and the action editor uses the same fields and segmented control.
- **No dead air, no dead end.** Choosing an action puts a small non-activating pill on screen in about 20 ms. It names the action, spins, counts elapsed seconds, and offers Cancel. Cancel drops the response instead of pasting it late. The frameless popup and receipt move when you drag their header. Rewrite History is one click from the popup header, one click from the receipt header, or `Ctrl+H`. A left click on the tray icon opens the dashboard.
- **Manage the popup actions in Settings.** The **Actions** card lists every action with its mode and shortcut. Edit, delete, add, or reset there, or keep using the popup pencil. Edits save in place and re-register action shortcuts; no restart.
- **Copy that matches the app.** "Rewrite" is the saved result, "actions" are the popup choices, "shortcuts" are keys, and "App controls" are Settings, Pause, About, and Exit. History says that it stays on the device and that the selected text goes to your AI provider.
- **The receipt waits for the reader.** It no longer closes on a 20 second timer while the pointer is over it.
- **A real app window.** A manual launch, a left click on the tray icon, or **Open Writing Tools** shows a native dashboard. First-run setup ends on it. It lists the five most recent rewrites, opens History at the one you click, names the provider and shortcut, and hosts Settings, Pause, About, and Exit. Autostart passes `--background`, so a boot login stays in the tray. A second launch asks the running copy to show its window instead of dying silently.
- **Setup no longer punishes a misclick.** Closing onboarding or provider setup keeps the tray app running instead of quitting. A bad shortcut is rejected with a message instead of being saved silently. Provider and shortcut changes apply on save; action edits apply right away.
- **Action edits apply in place.** Adding, editing, deleting, or resetting an action no longer shows a quit dialog and requires a relaunch. The grid refreshes and the action shortcuts re-register.
- **One instance.** A second launch raises the running window instead of adding a second tray icon and a competing hotkey listener.

## Run the demo

From the repository root, create the environment once.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r Windows_and_Linux\requirements.txt
```

Then run the demo.

```powershell
cd Windows_and_Linux
..\.venv\Scripts\python.exe -m rework.demo
```

The demo uses a mock draft. Click **Small edits** for an inline diff, **Larger rewrite** for the full-text fallback, **History** for the rewrite list, and **Dark** to switch themes. The demo writes to a temporary database, not your real history.

## Build the Windows app

The build script reads `main.py`, `icons`, `locales`, `pot_files`, and `options.json` from the current directory, so run it from `Windows_and_Linux`.

```powershell
cd Windows_and_Linux
..\.venv\Scripts\python.exe pyinstaller-build-script.py
```

The script deletes `dist` and `build`, then runs PyInstaller with `--onefile` and `--windowed`. It writes `dist\Writing Tools.exe` and copies `icons`, `locales`, `pot_files`, `options.json`, and `Latest_Version_for_Update_Check.txt` beside it. Keep those files together when you move the app. The script does not create a zip archive.

## Run the checks

```powershell
cd Windows_and_Linux
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The suite has 119 tests. All 119 pass.

## Regenerate the screenshots

The gallery in `design/qt` is rendered from the real Qt widgets. Both commands write there by default.

```powershell
cd Windows_and_Linux
..\.venv\Scripts\python.exe -m ui.design_preview --surface settings --theme light
..\.venv\Scripts\python.exe -m rework.screenshot --theme light --example small
```

Surfaces for `ui.design_preview`: `popup`, `popup-edit`, `dialog`, `settings`, `onboarding`, `about`, `response`. Run each with `--theme light` and `--theme dark`.

`rework.screenshot` takes `--theme light` or `--theme dark` and `--example small` or `--example large`. Run all four combinations to refresh the receipt, its expanded review, the composed context images, and the history window.

`rework.screenshot` defaults to the offscreen Qt platform. On some Windows systems the offscreen platform renders text as empty boxes. If that happens, set `$env:QT_QPA_PLATFORM="windows"` before the command. Each command prints the files it writes under `design/qt`.

## Where things live

- `Windows_and_Linux/rework/diff.py` owns tokenization and the word-level diff. It has no Qt imports.
- `Windows_and_Linux/rework/model.py` owns `Rework` and the receipt counts.
- `Windows_and_Linux/rework/controller.py` owns the single active receipt and clears it on dismissal.
- `Windows_and_Linux/rework/review_card.py` owns the compact card and the expanded review.
- `Windows_and_Linux/ui/WorkingPill.py` owns the in-flight progress pill.
- `Windows_and_Linux/ui/drag.py` owns drag-to-move for frameless surfaces.
- `Windows_and_Linux/rework/theme.py` owns the light and dark tokens.
- `Windows_and_Linux/rework/undo.py` owns the best-effort return-focus-and-send-Ctrl+Z boundary.
- `Windows_and_Linux/rework/history.py` owns the local SQLite store, search, retention, delete, and clear.
- `Windows_and_Linux/ui/HistoryWindow.py` owns the searchable history window.
- `Windows_and_Linux/ui/DashboardWindow.py` owns the main window.
- `Windows_and_Linux/ui/design.py` owns the app-wide tokens, stylesheet, and shared controls.
- `Windows_and_Linux/ui/ActionStore.py` owns the popup action entries and shortcut rules.
- `Windows_and_Linux/ui/SettingsWindow.py` owns the provider form, the action list, and the switch between providers.
- `Windows_and_Linux/ui/design_preview.py` renders each surface to `design/qt` for verification.
- `Windows_and_Linux/rework/demo.py` is the runnable receipt and history demo.
- `design/system.md` is the internal design system. `design/` also holds the brief, the arena candidates, the synthesis note, and the decisions. It stays local and is not part of the published snapshot.

## Provider setup

Settings offers three providers. **Gemini (Recommended)** uses a Gemini API key and model. **OpenAI Compatible (For Experts)** uses an API key, base URL, and model, with optional organisation and project fields. **Ollama (For Experts)** uses a base URL, model, and keep-alive time. The form under **AI Provider** shows only the selected provider's fields.

Save and **Finish AI Setup** validate a copy of the selected provider before the app writes anything. If the provider cannot start, the app shows **AI provider not ready**, keeps the window open, and leaves the config, the current provider, and the hotkey unchanged. A missing Gemini API key is one cause. Fix the field and save again.

On launch, the app loads the provider named in the config. If that provider cannot start, the app shows the same warning, opens the providers-only setup window, and leaves the provider unset. A rework or chat request with no provider shows **AI provider not set up** and makes no request.

`tests/test_provider_switch.py` covers field rendering for all three providers and saving each one. `tests/test_provider_save_validation.py` covers the empty Gemini key case. `tests/test_startup_provider_guard.py` covers a bad saved key at launch and a request with no provider. The tests build the real settings window and app methods with test objects and mock dialogs. They make no network request, so a valid key against a live provider remains unverified.

## Where history is stored

History goes to the Qt app-data directory, usually:

```text
%APPDATA%\Writing Tools\Writing Tools\history.db
```

The store keeps the newest 500 rewrites by default and prunes older rows. Change the limit with the `history_limit` config key. Delete one entry from the window, or clear every entry with **Clear all**.

## Known limits

- **Undo is best-effort.** The source application owns its undo stack. The receipt can return focus and send Ctrl+Z, but it cannot confirm that the source app undid the paste. This is tested for wiring, not across Word, browsers, and native edit controls.
- **Focus was checked on Windows only.** The receipt stays non-activating on Windows with `WA_ShowWithoutActivating`. Linux window managers still need a manual check.
- **No per-hunk accept or reject.** You can review the whole rework and undo it. Accepting individual edits is deliberately out of scope for this pass.
- **History records the applied rework, even if you undo it afterward.** The entry is a record of what was applied, not the current state of the document. Delete the entry if you want it gone.
- **History is local and not synced.** There is no cloud account, no network upload, and no merge between machines.
- **History is not encrypted at rest.** It is a local SQLite file. Protect it with your OS account or full-disk encryption.
- **Search is a simple `LIKE` match.** It searches the option and both texts. Case-insensitive matching works for ASCII only, so search accented or non-Latin text with the exact case.
- **The About version follows `UpdateChecker.CURRENT_VERSION`.** That value is 8 in this snapshot. The release process must update it before a release. Do not add a second hardcoded version.
- **No appearance override.** The app follows the system light/dark setting. A manual System/Light/Dark picker is a later feature.
- **Button edits still use the upstream relaunch contract.** Saving, adding, deleting, or resetting a button exits the app so the new hotkeys and options load cleanly. A live reload is the next behavior pass.
- **The provider switch is tested without a live provider.** The form rebuild, the validate-before-write save path, the startup guard, and the no-provider message have automated tests. Real Gemini, OpenAI-compatible, and Ollama connections are not exercised by the suite.
- **macOS is unchanged.** The Windows/Linux app is fully reskinned. The Swift port remains upstream and needs its own pass.
