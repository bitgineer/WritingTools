---
name: verify-writingtools
description: Verify user-facing Writing Tools behavior on Windows and Linux by driving the real Qt widgets through the receipt demo, history window, settings, response window, onboarding, About, friction journeys, and the design-preview renderer, with screenshots and state transcripts under artifacts/verify. Use when asked to verify, smoke-test, or prove a change in Windows_and_Linux.
---

# Verify Writing Tools

Writing Tools is a tray application built with PySide6. This skill drives its real Qt widgets with `QTest` on the native platform when a display is available, uses the repo's own receipt demo and `ui.design_preview` renderer, and writes evidence under `artifacts/verify/`. It never opens the user's real history database, writes `Windows_and_Linux/config.json`, or edits `design/qt`.

The feature map is `.opencode/skills/verify-writingtools/features/README.md`. Read it before driving. Use the feature file that matches the change.

## Launch

Prerequisites. Run from the repository root with the project virtualenv. The venv already contains PySide6 and the provider SDKs.

```powershell
Test-Path .venv\Scripts\python.exe
.\.venv\Scripts\python.exe -c "import PySide6; print(PySide6.__version__)"
```

The harness is short-lived. There is no server to keep alive. Launch means start one feature process. The helper uses the native Qt platform when a display is available, so screenshots render real text. It falls back to `offscreen` for headless logic runs. Set `VERIFY_QT_PLATFORM` to force a platform.

```powershell
.\.venv\Scripts\python.exe -B .opencode\skills\verify-writingtools\scripts\verify.py doctor --run-id <run-id>
.\.venv\Scripts\python.exe -B .opencode\skills\verify-writingtools\scripts\verify.py run --feature receipt --run-id <run-id>
```

Ready means the run prints `[run] ... started` and then `RESULT <feature> PASS <evidence-path>`. A run that prints `RESULT ... BLOCKED` is a dependency block. A run that prints `RESULT ... PASS_WITH_BLOCKER` drove the window journey but a named external path is broken. Read `evidence/summary.json` before reporting.

Isolation. The receipt demo creates its own temporary SQLite history database. The settings drive writes its config to `artifacts/verify/<run-id>/evidence/settings-config.json`. The design-preview subprocesses get `preview.OUT` pointed at the run evidence directory, so `design/qt` is not touched. Do not drive an instance that another run started. Run one feature per process. `QApplication` is a singleton, so a second `ui.design_preview` surface in the same process fails.

The doctor probes the real app in an isolated copy and reports `real app launch`. A blocked probe means the tray app cannot construct. The surface harness can still run, but do not claim the tray app is usable until the probe passes. Record the detail verbatim. Do not work around it by stubbing `create_tray_icon` in the app.

Teardown. Evidence survives. Remove scratch state with the cleanup command in the Cleanup section.

## Doctor

Run this first whenever a launch, artifact, or dependency looks wrong. It is read-only with respect to the checkout. It writes its own transcript and summary.

```powershell
.\.venv\Scripts\python.exe -B .opencode\skills\verify-writingtools\scripts\verify.py doctor --run-id <run-id>
```

It checks the Python executable, the app tree, `options.json`, the app icon, PySide6, the provider-switch dependency, and a real `WritingToolApp` construction in a copied app tree. It prints one line per check.

- `[PASS] provider-switch dependency` means `Windows_and_Linux/tests/test_provider_switch.py` exists and passes. If it is `[BLOCKED]`, the settings feature must stay unverified.
- `[BLOCKED] real app launch` means the tray app cannot be constructed. The receipt, history, response, and design-preview harnesses can still run. Record the detail verbatim.
- `DOCTOR PASS_WITH_BLOCKER` is not a clean instance. It means the surface harness is usable and one or more named checks are blocked. Read the blocked line.

## Drive

Use the helper. Do not call internal test-only setters when a visible widget action exists. The helper uses `QTest.mouseClick` and `QTest.keyClicks` against buttons, fields, and combo boxes, and reads the resulting labels, table rows, config files, clipboard, and database counts.

| Feature | Command | What it drives |
| --- | --- | --- |
| Surfaces | `run --feature surfaces` | `ui.design_preview` for popup, popup edit, button dialog, settings, onboarding, About, and response in light and dark |
| Popup and receipt | `run --feature receipt` | `rework.demo`: Small edits, Review changes, Copy revised, Undo rework, Larger rewrite, Dark |
| Rewrite history | `run --feature history` | `rework.demo`: History, search, copy, history toggle, delete, clear all |
| Settings and provider setup | `run --feature settings` | Real `SettingsWindow` with real providers: Gemini, OpenAI Compatible, Ollama, Save, Finish AI Setup |
| Response window | `run --feature response` | Markdown response, Copy response, Zoom in, follow-up, provider error |
| Onboarding and About | `run --feature onboarding-about` | Welcome, shortcut, Continue handoff, About version, update and source links |
| Friction journeys | `run --feature friction` | Popup drag, History from popup, progress pill, cancel, receipt drag, dashboard, stale-response guard |
| End-to-end gate | `gate` | All of the above plus the unit tests |

Selectors are accessible names and visible labels. The helper already knows them. When you add a drive, use these stable handles. `Review changes`, `Undo rework`, `Copy revised text`, `Dismiss rework receipt`, `History`, `Search rewrites`, `Save rewrites to history`, `Delete`, `Clear all`, `AI Provider`, `API Key`, `API Base URL`, `API Model`, `Finish AI Setup`, `Follow-up question`, `Send follow-up`, `Zoom in`, `See the latest release`, `View source`, `Continue`.

The settings drive is the only feature with a dependency gate. It runs `tests/test_provider_switch.py` before it opens the window. If the file is missing, it writes `RESULT settings BLOCKED` and leaves the feature unverified. Do not replace that check with a direct call to `save_settings`.

## Evidence

Every run writes to `artifacts/verify/<run-id>/evidence/`. `summary.json` records the feature, status, start and finish times, Python path, git HEAD, `git status --short`, every check, every artifact, and any error. `transcript.txt` is the console log.

Required proof per feature:

- Surfaces. Fourteen PNGs under `evidence/surfaces/`, one for each surface and theme. Each must be a valid PNG at least 300 by 200 pixels. The helper records dimensions and a retry if the preview process exits abnormally after saving.
- Receipt. `receipt-compact-light.png`, `context-compact-light.png`, `receipt-review-light.png`, `receipt-review-large-light.png`, `receipt-compact-dark.png`, and `receipt-review-dark.png`. The transcript names the compact title, headline, first edits, saved-to-history label, inline diff, full-text fallback, clipboard length, and restored demo text.
- History. `history-list-light.png`, `history-search-light.png`, `history-off-light.png`, `history-deleted-light.png`, and `history-empty-light.png`. The transcript names the row count, search count, copied text length, toggle note, confirmation titles, and store count after each mutation.
- Settings. `settings-full-light.png`, `settings-openai-light.png`, `settings-ollama-light.png`, `settings-finish-openai-light.png`, `settings-config.json`, `provider-switch-test.txt`, and `app-launch.txt`. The transcript names the provider list, field values, saved provider, saved Ollama values, live provider, hotkey call, tray-icon call, and the real-app probe result.
- Response. `response-light.png`, `response-followup-light.png`, and `response-failure-light.png`. The transcript names the rendered markdown, clipboard prefix, zoom factor before and after, follow-up tuple, busy state, response message, and failure title.
- Onboarding and About. `onboarding-light.png` and `about-light.png`. The transcript names the saved shortcut, the providers-only handoff, the version line, the scroll area, and the release and source URLs.
- Friction journeys. `popup-drag-light.png`, `progress-pill-light.png`, `dashboard-light.png`, `receipt-review-light.png`, and `friction-journeys.txt`. The transcript names the measured drag delta, the click that opens History, the milliseconds from pill construction to visible, the elapsed-time readout, the cancel result, the dashboard's recent rows, the exact entry a row opens, and the stale-response guard. The pill must be visible in 100 ms or less and must carry `WindowDoesNotAcceptFocus` plus `WA_ShowWithoutActivating`.

Proof standards. Exercise the user path, not a private setter. Capture the action and the resulting state. A screenshot alone is weak. Pair it with a read of the widget text, the clipboard, the config file, or the SQLite count. Mocks are allowed only at a production boundary. The About link check patches `webbrowser.open` so the run does not open a browser, and the transcript records the URL it would have opened. The settings drive uses a shell for the app object because it drives the window without starting the tray loop. The separate real-app probe records whether the tray app constructs. Do not present the settings window journey alone as proof that the tray app finishes setup.

Never claim the settings feature verified from unit tests alone. The drive must open the real `SettingsWindow`, switch providers with the combo box, fill the visible fields, press Save or Finish AI Setup, and read the resulting config. The provider-switch unit test is a gate, not the proof.

## Cleanup

```powershell
.\.venv\Scripts\python.exe -B .opencode\skills\verify-writingtools\scripts\verify.py cleanup --run-id <run-id>
.\.venv\Scripts\python.exe -B .opencode\skills\verify-writingtools\scripts\verify.py cleanup --all-runs
```

Cleanup removes `artifacts/verify/<run-id>/scratch/`, which holds the copied app tree and probe files. It keeps `evidence/`, `summary.json`, and `transcript.txt`. It never kills processes by name. The helper waits for every subprocess it starts and kills only its own child on timeout. No background process should survive a run. After cleanup, list the evidence directory and confirm the artifacts are still there.

## Helpers

`scripts/verify.py` is the only helper. It is runnable with the project virtualenv. Its subcommands are `doctor`, `run`, `gate`, and `cleanup`.

```powershell
.\.venv\Scripts\python.exe -B .opencode\skills\verify-writingtools\scripts\verify.py --help
.\.venv\Scripts\python.exe -B .opencode\skills\verify-writingtools\scripts\verify.py run --feature receipt --run-id local-receipt
.\.venv\Scripts\python.exe -B .opencode\skills\verify-writingtools\scripts\verify.py gate --run-id local-gate
```

`gate` returns `0` when every feature passes, `2` when a feature is blocked or has a named external blocker, and `1` when a check fails. It runs the full unit suite as a corroborating check, not as the proof. It writes the per-feature runs under `artifacts/verify/<gate-id>-<feature>/` and its own summary under `artifacts/verify/<gate-id>/evidence/summary.json`.

## Reporting

Report the feature ID, the run directory, the command, and the status. Quote the failing check and the artifact that proves it. For a blocked feature, name the missing file or the broken app path. Do not report a skipped entry point as verified through another path. Do not edit application code, tests, or documentation to make a drive pass.
