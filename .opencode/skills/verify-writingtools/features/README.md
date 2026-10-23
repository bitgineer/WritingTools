# Writing Tools verification map

This directory is the maintained source for verifying the user-facing behavior of the Windows and Linux app. Read this index before driving, then use the matching feature file as the recipe. The harness is `.opencode/skills/verify-writingtools/scripts/verify.py`.

## Baseline preconditions

- Run from the repository root on Windows or Linux with `.venv\Scripts\python.exe` and `Windows_and_Linux/requirements.txt` installed. The current environment is Windows, Python 3.13.1, PySide6 6.12.0.
- Use a fresh run ID for each session: `--run-id <date>-<topic>`. Evidence goes to `artifacts/verify/<run-id>/evidence/`.
- Set no real API key. The settings drive uses dummy values and writes its config to the run evidence directory.
- Never read or write `Windows_and_Linux/config.json`, the real `%APPDATA%\Writing Tools` history database, or `design/qt`. The demo uses a temporary database. The preview renderer is pointed at the run evidence directory.
- The real tray app is probed in an isolated copy of `Windows_and_Linux`. The probe constructs the app, builds the tray menu, and exits. It does not click the tray actions.
- Never drive an instance that another run started. Use one process per feature because `QApplication` is a singleton.

## Driving conventions

- Read the feature file before running its command.
- Start every recipe from the baseline state unless its preconditions say otherwise.
- Use `verify.py run --feature <id>` exactly as written. The helper drives real widgets with `QTest`.
- Prefer accessible names and visible labels over widget position. The stable handles are listed in `SKILL.md`.
- Treat every command as literal. Keep paths and flags unchanged.
- One feature per process. `surfaces` is a supervisor that starts one subprocess per surface and theme.
- Record the feature ID and entry point with every artifact. The helper writes them into `summary.json` and `transcript.txt`.
- Do not edit the app, tests, `options.json`, `README.md`, `FORK.md`, or the design documents to make a run pass.

## Proof and skip reporting

- Capture the user action and the resulting state, not only the final screen.
- A UI proof pairs a screenshot with a read of visible text, a config file, a clipboard value, or a database count.
- A mutation proof includes a read-only second view of the stored value, such as `store.count()` after Delete or the saved provider in `settings-config.json`.
- The settings drive must run `tests/test_provider_switch.py` first. If that file is missing, the run is `BLOCKED`. Do not substitute another test and do not call `save_settings` directly.
- The real app probe is separate from the surface drives. A passing settings window journey does not prove the tray app can finish setup. Name the blocker when the probe fails.
- Report an unreachable path with the attempted command and the unmet precondition. Do not report a skipped entry point as verified through another path.
- Mock only a production boundary. The About link drive patches `webbrowser.open` and records the URL. The settings drive uses an app shell and records the tray and hotkey calls. The real app probe is the evidence for the shell behavior.

## Feature entry contract

Each feature file starts with an H1 title and one paragraph describing the user-visible behavior. It then uses exactly four H2 sections in this order.

1. `Sub-features` lists short IDs with one line for each behavior.
2. `How to get to it (user POV)` lists every user entry point.
3. `Driving it with verify.py` starts with `Preconditions:` and uses labeled bullets that pair each user action with an exact command and an observable result.
4. `Gotchas` lists traps that can waste or invalidate a run.

Keep implementation details out of the map. Name only user paths, stable handles, required state, commands, and observable proof. Add a status line under the H1 when a feature is not fully verified.

## Features

- [Popup and rework receipt](./popup-and-receipt.md) covers the action popup, the button editor, the receipt, the expanded review, copy, undo, and both themes. Status: verified through the demo and preview harnesses. The global hotkey path is not synthesized.
- [Rewrite history](./rewrite-history.md) covers the local history list, search, copy, the history toggle, delete one entry, and clear all. Status: verified through the demo harness.
- [Settings and provider setup](./settings-and-provider-setup.md) covers the settings window, switching Gemini to OpenAI Compatible and Ollama, Save, and Finish AI Setup. Status: verified. The provider-switch test passes, the window journey passes, and the real-app construction probe passes.
- [Response window](./response-window.md) covers the initial response, markdown rendering, copy, zoom, follow-up, and provider failure. Status: verified through the real window.
- [Onboarding and About](./onboarding-and-about.md) covers the welcome screen, shortcut entry, the providers-only handoff, the About version, and the About links. Status: verified, with the final provider setup owned by the settings feature.
- [Friction journeys](./friction-journeys.md) covers moving the frameless popup and receipt, opening History from either, the in-flight progress pill, cancel, and the stale-response guard. Status: verified through the real widgets.
- [End-to-end gate](./end-to-end-gate.md) runs every feature and the unit suite, then reports pass, pass with blocked dependency, or fail. Status: runnable. It returns `0` when every feature passes.
