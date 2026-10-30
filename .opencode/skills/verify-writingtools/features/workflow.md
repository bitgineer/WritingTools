# One-window workflow

The shell is the whole management app. Home, Rewrites, Actions, Settings, and
About are views in one window, the first run is a state of Home, and every
writing-time surface routes back to the matching view. This drive walks the
fourteen workflows in `design/friction-baseline.md`, counts the explicit
actions it takes, and writes the scorecard beside the screenshots.

Status: runnable. The workflow drive passes and the scorecard matches every
target, including W14 at 2.

## Sub-features

- `WF-1` Shell navigation. Ctrl+1..5 and the rail switch Home, Rewrites, Actions, Settings, and About.
- `WF-2` Command palette. Ctrl+K opens it; typing filters; Enter runs the selected command.
- `WF-3` First run. Home shows the two-step setup; step 1 saves the shortcut, step 2 renders the provider form, ready shows the next action.
- `WF-4` Popup. Ctrl+1..9 runs the matching action; Enter sends the custom instruction.
- `WF-5` Rewrites. Search, select, copy original or revised, delete one, clear all, history toggle.
- `WF-6` Actions. Add, edit, rename, reorder, delete, and reset inline; saving reloads the popup and hotkeys.
- `WF-7` Settings. Shortcut autosaves on Enter or blur; invalid values stay inline; provider saves through the one form.
- `WF-8` Receipt route. A finished rewrite saves to history, and the receipt opens that exact entry in Rewrites.
- `WF-9` Status chip. One click pauses or resumes; with no provider it opens Settings.
- `WF-10` Friction scorecard. One row per workflow with baseline, target, measured actions, and PASS or FAIL.

## How to get to it (user POV)

- Start the app. With no config, Home shows the setup card. After setup, Home shows status, recent rewrites, and actions.
- Click a rail item or press Ctrl+1..5 to move between the five views.
- Press Ctrl+K, type a view or command name, and press Enter.
- Select text in another app and press the shortcut. The popup appears; press Ctrl+1..9 or type a custom instruction and press Enter.
- In Rewrites, type in the search field, choose an action filter, click a row, then copy, delete, or clear.
- In Actions, click Add action. The inline editor is the only action editor. Save applies without a restart.
- In Settings, edit the shortcut and press Enter or leave the field. Toggle history, start on boot, or save the provider.
- In the receipt, click Open Rewrites to land on the saved entry.

## Driving it with verify.py

Preconditions: run from the repository root with `.venv\Scripts\python.exe`.
The drive writes its own temp `options.json`, `provider_presets.json`, and
SQLite history under `artifacts/verify/<run-id>/scratch/workflow/`. It never
reads or writes the real config or history database. It uses fake providers
only at the provider boundary and makes no network calls. It forces the
offscreen Qt platform because the long widget sequence was unstable on the
native platform in this environment.

- Shell navigation: `Ctrl+1..5` must set `_current` and the visible stack page. Proof: transcript line `Ctrl+2 must open rewrites` plus the screenshot `workflow-home-setup.png`.
- Palette: `Ctrl+K`, type `sett`, press Enter. Proof: the list contains `Go to Settings`, Enter lands on Settings, and `workflow-provider-saved.png` shows the shell.
- First run: click Continue, enter the shortcut and key, click Finish setup, then Open Home. Proof: the transcript names the saved shortcut and the ready step.
- Popup: press Ctrl+1 and type a custom instruction. Proof: the fake host records `(Proofread, "")` and `(Custom, "Make it funny.")`.
- Rewrites: search `store`, select the row, click Copy revised. Proof: one row and the clipboard contains `store`. The delete and clear confirmation paths are unit-tested.
- Actions: click Add action, fill the name and instruction, click Save action. Proof: `options.json` in the run scratch contains `Tighten`.
- Settings: set the shortcut and press Enter. Proof: the config snapshot records `ctrl+alt+p` and `register_hotkey` was called.
- Provider: choose the OpenRouter preset, paste a key, Load models, Test connection, Save provider. Proof: the saved config names the OpenAI-compatible provider and the test status reads `Connected. 3 models available.`
- Receipt route: the first rewrite saves a row; the receipt's history button calls `open_entry` with that row. Proof: the selected id matches `last_entry_id`.
- Scorecard: the drive writes `evidence/friction-scorecard.json`, `evidence/friction-actions.txt`, and a `[scorecard]` transcript line.

Command:

```powershell
.\.venv\Scripts\python.exe -B .opencode\skills\verify-writingtools\scripts\verify.py run --feature workflow --run-id agent-workflow
```

Video:

```powershell
.\.venv\Scripts\python.exe -B .opencode\skills\verify-writingtools\scripts\verify.py record --run-id agent-workflow
```

Evidence: `workflow-home-setup.png`, `workflow-setup-step2.png`, `workflow-setup-return.png`, `workflow-receipt-first.png`, `workflow-popup-light.png`, `workflow-popup-custom.png`, `workflow-receipt-quick.png`, `workflow-receipt-custom.png`, `workflow-receipt-review.png`, `workflow-rewrites-search.png`, `workflow-rewrites-copied.png`, `workflow-actions-saved.png`, `workflow-settings-shortcut.png`, `workflow-settings-history-off.png`, `workflow-provider-saved.png`, `workflow-settings-paused.png`, `workflow-recovery.png`, `workflow-reader.png`, `friction-scorecard.json`, `friction-actions.txt`, `workflow.mp4`, and `workflow.gif`.

## Gotchas

- Run one feature per process. The shell creates a QApplication singleton.
- The drive forces `QT_QPA_PLATFORM=offscreen`. The native platform access-violated partway through the long sequence; the offscreen screenshots still render the real widgets.
- The provider form is stateful. Switching providers collects drafts before rendering the new one; a failure there leaves the old fields on screen.
- Model loading runs on a thread. A queued list result that never arrives leaves `Loading models...` in place; the scorecard records the dead end.
- The first-run drive uses a second fake host with no provider. Do not point it at the real config.
- The scorecard counts explicit drive actions, not wall time. A dead end costs three.
- W14 measures 2 (close, reopen) against a target of 2. The return to the app is the second action and is counted.
- The video recorder needs `C:\ProgramData\chocolatey\bin\ffmpeg.exe` or `ffmpeg` on PATH. Frames stay in `scratch/frames/`; only the MP4 and GIF are evidence.
