# WritingTools fork: one window, one flow

This fork starts from the upstream snapshot in `UPSTREAM.md`. It keeps the
instant in-place rewrite and reworks the app around one question.

> When the AI rewrites your selection, what changed, and what can I do next?

The answer is a receipt after every rewrite, a local rewrite history, and one
window that owns Home, Rewrites, Actions, Settings, and About. The short version
is in the [README](README.md). This file records what changed and where it lives.

## What changed

- **One app window.** `ui/AppShell.py` owns a left rail, a content stack, a
  command palette, and inline banners. Settings, history, About, and onboarding
  are views, not windows. `Ctrl+1` to `Ctrl+5` switch views, and `Ctrl+K` opens
  the command palette.
- **One workflow state.** `core/workflow.py` tracks the active run with a serial,
  option, original text, revised text, and state. The popup, progress pill,
  receipt, shell, and tray read the same state. A late or cancelled response is
  dropped by serial and cannot paste.
- **One action editor.** `ui/ActionsView.py` adds, edits, renames, reorders,
  deletes, and resets actions in place. Saving applies immediately. The popup no
  longer has an edit mode or a second action dialog.
- **First run inside Home.** `ui/SetupWizard.py` asks for the shortcut, then a
  provider. `ui/ProviderForm.py` is the same form Settings uses. The tray keeps
  the app alive from the first launch, and the shortcut is registered after the
  provider is saved. Closing the window before setup finishes keeps the app in
  the tray and resumes setup later.
- **Rewrites as master-detail.** `ui/RewritesView.py` searches and filters the
  local database, shows a word-level diff or a side-by-side comparison, and
  offers copy, delete, clear, and a save toggle. A receipt or tray entry opens
  the exact rewrite, not a second window.
- **Provider setup that tests before it writes.** The form has a provider
  choice, 13 OpenAI-compatible presets, a key field, a live model list, and
  **Test connection**. Save validates a copy before writing. Failures stay inline
  with a cause and a next step.
- **Receipt and reader.** The receipt shows the first edits, a word-level diff,
  and Undo. It appears after the paste, never gates it, and does not take focus.
  Long results open in a separate reader with follow-up chat and a link to the
  matching rewrite.
- **A small tray.** Open, recent rewrites, Rewrites, Settings, Pause, Quit. A
  left click opens the shell. A second launch raises the running shell with the
  Win32 window title, not a second tray icon.
- **Atomic local state.** `core/config.py` writes the config in one replace and
  moves an unreadable file aside. `ui/ActionStore.py` writes options atomically.
  History stays in a local SQLite database with the newest 500 rows by default.
- **One paper design system.** `ui/design.py` owns the palette roles, type,
  spacing, controls, and shell object names. Light and dark follow the system.
  The receipt uses the same tokens. There is no gradient, texture, or theme
  picker.
- **Actionable provider errors.** A gated model, a bad key, a missing model, a
  rate limit, and a context limit each get a short cause and one next step. The
  app does not spoof a user agent to get around a provider gate.

## Run from source

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r Windows_and_Linux\requirements.txt
cd Windows_and_Linux
..\.venv\Scripts\python.exe main.py
```

The receipt and history demo runs without a provider:

```powershell
..\.venv\Scripts\python.exe -m rework.demo
```

## Build the Windows app

Run from `Windows_and_Linux`. The script reads `main.py`, `icons`, `locales`,
`pot_files`, `options.json`, `provider_presets.json`, and
`Latest_Version_for_Update_Check.txt` from the current directory.

```powershell
cd Windows_and_Linux
..\.venv\Scripts\python.exe pyinstaller-build-script.py
```

The script deletes `dist` and `build`, runs PyInstaller with `--onefile` and
`--windowed`, writes `dist\Writing Tools.exe`, and copies the data files beside
it. Keep the folder together. The script does not create a zip.

## Run the checks

```powershell
cd Windows_and_Linux
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The repository ships a verification harness that drives the real Qt widgets,
takes screenshots, writes a friction scorecard, and records a workflow video
under `artifacts/verify`:

```powershell
.\.venv\Scripts\python.exe -B .opencode\skills\verify-writingtools\scripts\verify.py gate --run-id local
```

The design skill is `.opencode/skills/writingtools-design/SKILL.md`. It records
the one-shell rules, the copy terms, the friction score, and the pre-ship
checklist.

## Where things live

- `Windows_and_Linux/core/config.py` owns atomic config storage and recovery.
- `Windows_and_Linux/core/workflow.py` owns the run state and serial guard.
- `Windows_and_Linux/ui/AppShell.py` owns the shell, rail, top bar, palette,
  banners, and toast.
- `Windows_and_Linux/ui/HomeView.py` owns status, recent rewrites, actions,
  keyboard help, and the first-run card.
- `Windows_and_Linux/ui/SetupWizard.py` owns the two setup steps and ready state.
- `Windows_and_Linux/ui/RewritesView.py` owns search, filter, diff, side-by-side,
  copy, delete, clear, and the history toggle.
- `Windows_and_Linux/ui/ActionsView.py` owns the only action editor.
- `Windows_and_Linux/ui/SettingsView.py` owns general, provider, privacy, and
  updates.
- `Windows_and_Linux/ui/ProviderForm.py` owns provider choice, presets, keys,
  model lists, test, and save.
- `Windows_and_Linux/ui/AboutView.py` owns the in-app About page.
- `Windows_and_Linux/ui/CustomPopupWindow.py` owns the in-context action popup.
- `Windows_and_Linux/ui/WorkingPill.py` owns the non-activating progress pill.
- `Windows_and_Linux/rework/review_card.py` owns the receipt and review.
- `Windows_and_Linux/ui/ResponseWindow.py` owns the reader.
- `Windows_and_Linux/rework/diff.py` owns tokenization and the word-level diff.
- `Windows_and_Linux/rework/history.py` owns the local SQLite store.
- `Windows_and_Linux/ui/ActionStore.py` owns action entries and shortcut rules.
- `Windows_and_Linux/ui/ProviderPresets.py` loads the preset catalog.
- `Windows_and_Linux/provider_presets.json` is the preset data.

The internal design notes live in `design/` and are not part of the published
snapshot. `design/system.md` has the tokens, `design/unified-flow.md` has the
flow and decisions, and `design/friction-baseline.md` has the scorecard.

## Known limits

- **Undo is best effort.** The source app owns its undo stack. The receipt
  returns focus and sends `Ctrl+Z`, but it cannot confirm the source app undid
  the paste.
- **No per-hunk accept or reject.** The whole rewrite can be reviewed and
  undone. Accepting individual edits is out of scope.
- **History records what was applied.** Undo does not delete the row. Use Delete
  or Clear all.
- **History is local and not encrypted.** It is a SQLite file in the app-data
  folder. No account and no sync.
- **Some free models are gated.** The provider decides. The app names the gate
  and points to a standard model. It does not spoof a client identity.
- **A reader has no Cancel once it opens.** Close it to stop reading. The
  follow-up request is separate.
- **No manual appearance override.** The app follows the system light or dark
  setting until restart.
- **macOS is upstream and unchanged.** The Swift port is a separate codebase.

## Upstream and license

Writing Tools was created by [Jesai Tarun](https://github.com/theJayTea) with
contributors, including the macOS port by Arya Mirsepasi. This fork keeps the
GPLv3 license and the upstream attribution. See [LICENSE](LICENSE),
[UPSTREAM.md](UPSTREAM.md), and the [README](README.md).
