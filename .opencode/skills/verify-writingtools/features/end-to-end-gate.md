# End-to-end gate

The gate drives every mapped feature in its own process, renders every design surface in light and dark, runs the repository unit suite, and writes one summary. It is the check to run before calling a Windows or Linux change verified. Status: runnable. It returns `0` when every feature passes, `2` when a feature is blocked, and `1` when a check fails.

## Sub-features

- `gate-doctor` runs the readiness check and records the real-app probe.
- `gate-surfaces` renders popup, popup edit, button dialog, settings, onboarding, About, and response in both themes.
- `gate-receipt` drives the compact receipt, review, copy, undo, substantial rewrite, and dark theme.
- `gate-history` drives list, search, copy, toggle, delete, and clear all against a temporary database.
- `gate-settings` gates on `tests/test_provider_switch.py` and drives Gemini to OpenAI Compatible to Ollama to Save and Finish AI Setup.
- `gate-response` drives markdown rendering, copy, zoom, follow-up, and provider failure.
- `gate-onboarding-about` drives the welcome shortcut and handoff plus the About version, scroll area, and links.
- `gate-tests` runs `python -m unittest discover -s tests -v` as a corroborating check.

## How to get to it (user POV)

- Run the command before reporting a change to the Windows and Linux app.
- Read the gate summary after every failure. It names the feature, the status, the evidence directory, and the unit-test exit.
- Open the per-feature `evidence/summary.json` and screenshots for the failing surface.

## Driving it with verify.py

Preconditions:

- Run from the repository root with the project virtualenv.
- Use a fresh gate ID. Each feature runs under `<gate-id>-<feature>`.
- Do not run another verification run at the same time. The gate starts many Qt subprocesses and they share the machine, not a data directory.
- The settings feature returns `PASS` when the provider-switch test passes, the window journey passes, and the real-app construction probe passes. If the probe fails, the feature is `PASS_WITH_BLOCKER`, which is not a pass.

```powershell
.\.venv\Scripts\python.exe -B .opencode\skills\verify-writingtools\scripts\verify.py gate --run-id <gate-id>
```

- **Doctor.** The gate runs `doctor` under `<gate-id>-doctor`. Its output is in `artifacts/verify/<gate-id>/evidence/doctor.txt`. The check reads `doctor: exit=0`.
- **Surfaces.** The gate runs `run --feature surfaces` under `<gate-id>-surfaces`. Fourteen PNGs land in `artifacts/verify/<gate-id>-surfaces/evidence/surfaces/`.
- **Receipt.** The gate runs `run --feature receipt` under `<gate-id>-receipt`. The summary status is `PASS` and the screenshots are in its evidence directory.
- **History.** The gate runs `run --feature history` under `<gate-id>-history`. The summary status is `PASS` and the temporary database is removed with the scratch directory.
- **Settings.** The gate runs `run --feature settings` under `<gate-id>-settings`. The summary status is `PASS` when the provider-switch test and the real-app probe pass. It is `PASS_WITH_BLOCKER` when the real app cannot construct, and `BLOCKED` when `tests/test_provider_switch.py` is missing.
- **Response and onboarding.** The gate runs `run --feature response` and `run --feature onboarding-about`. Both summaries are `PASS` when their checks pass.
- **Unit tests.** The gate runs the full suite in `Windows_and_Linux` and writes `unit-tests.txt`. The check reads `unit tests: OK`.
- **Result.** A clean run prints `GATE PASS` and exits `0`. A blocked feature prints `GATE PASS WITH BLOCKED: settings` and exits `2`. A failed check prints `GATE FAIL` and exits `1`.
- **Proof.** Keep `artifacts/verify/<gate-id>/evidence/summary.json`, `doctor.txt`, `unit-tests.txt`, and every `<gate-id>-<feature>/evidence/` directory.

## Gotchas

- A `PASS_WITH_BLOCKER` feature is not a pass. Read the blocked check and name the external path. The settings feature uses that status when the real-app construction probe fails.
- The unit suite is corroboration. It does not replace the surface screenshots and the state reads. A green suite with a missing screenshot is not a gate pass.
- The gate does not launch the real tray app. It probes construction in an isolated copy and records the result in `doctor.txt` and `app-launch.txt`.
- The gate can take one to two minutes because it starts a Qt process per surface and per feature. Use a generous timeout.
- The preview subprocesses can exit abnormally after saving a valid PNG on this Qt build. The surface check retries once and validates the PNG header and dimensions. Record the exit code if it appears.
- The gate writes only under `artifacts/verify/`. It does not modify the app, tests, `design/qt`, or the user's real config or history.
- Do not run `cleanup --all-runs` before you have read the gate summary. It removes scratch directories, not evidence, but it can remove the copied app tree you may want for a failure investigation. Re-run doctor to recreate it.
