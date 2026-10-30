# Rewrite history

Rewrite History is a local list of applied reworks. It opens from the tray, shows the newest entry first, searches option and both texts, copies either side, turns new saves off and on, deletes one entry, and clears everything. History is local SQLite and nothing is uploaded. Status: verified through the demo harness. The tray menu path shares the same window but is not clicked by the drive.

## Sub-features

- `history-open` opens the window from the tray or from the demo History button and fills the list.
- `history-list` shows the count and the newest entry with its option, changed-word headline, timestamp, original, and reworked text.
- `history-search` filters the list and reports `1 of 2` while the query is active.
- `history-copy` copies the original or reworked text and changes the button label to Copied.
- `history-toggle` stops or resumes saving new rewrites and updates the note under the toggle.
- `history-delete` asks for confirmation and removes the selected entry.
- `history-clear` asks for confirmation and removes every entry.
- `history-empty` shows the empty state after the last entry is removed.

## How to get to it (user POV)

- Right-click the Writing Tools tray icon and choose Rewrite History.
- In the demo, choose History in the top bar after running one or more examples.
- In code, `WritingToolApp.show_history` opens the same `ui.HistoryWindow.HistoryWindow` with the app's `HistoryStore`.

## Driving it with verify.py

Preconditions:

- Run from the repository root.
- Use a fresh run ID so the demo database starts empty.
- The demo uses a temporary database under the run scratch directory. It never touches the real history database.
- The helper uses the native Qt platform when a display is available: `windows` on Windows, `xcb` on Linux with `DISPLAY`. It falls back to `offscreen` for headless logic runs. Set `VERIFY_QT_PLATFORM` to force a platform.

- **Create two rewrites.** Run `.\.venv\Scripts\python.exe -B .opencode\skills\verify-writingtools\scripts\verify.py run --feature history --run-id <id>`. The run calls `run_example("small")` and `run_example("large")`, which save through the demo's history handler.
- **Open the window.** The run clicks the real `History` button. The transcript reads `history opens: window visible`, `two saved rewrites: list=2 label=2 rewrites`, and `newest entry is selected: Professional · 33 words changed · ...`. The selected row is the large example because the list is newest first.
- **Search.** The run types `yesterday` into `Search rewrites`. The transcript reads `search filters the list: list=1 label=1 of 2`. The search screenshot is `history-search-light.png`.
- **Copy.** The run selects row 0 and clicks `Copy revised`. The transcript reads `Copy revised text: clipboard=270 chars, button=Copied`.
- **Toggle history off and on.** The run clicks `Save rewrites to history`. The transcript reads `history toggle persists off` with the note `History is off. Existing entries stay until you clear them.` Clicking again reads `history toggle persists on`.
- **Delete one.** The run selects row 0 and clicks `Delete`. A real `QMessageBox` opens. The helper clicks its Yes button and records the title. The transcript reads `delete asks for confirmation: title=Delete rewrite` and `delete removes one entry: store=1 list=1`. The screenshot is `history-deleted-light.png`.
- **Clear all.** The run clicks `Clear all`. The helper answers the real confirmation dialog. The transcript reads `clear all asks for confirmation: title=Clear rewrite history` and `clear all removes every entry: store=0 ... No rewrites yet`. The screenshot is `history-empty-light.png`.
- **Proof.** Keep `history-list-light.png`, `history-search-light.png`, `history-off-light.png`, `history-deleted-light.png`, `history-empty-light.png`, `transcript.txt`, and `summary.json`. The summary records the check results and the artifact list.

## Gotchas

- Both demo samples contain the word `budget`. A search for `budget` returns both rows and looks like a broken filter. Use `yesterday`, which appears only in the small sample's original.
- The demo's History button is a harness entry point. It calls the same `HistoryWindow` as the tray, but it does not prove the tray action itself. Do not report the tray menu click as verified.
- Delete and Clear all open modal confirmation dialogs. The helper schedules a real Yes click inside the dialog's event loop. If the dialog is replaced with a non-modal prompt, the drive hangs. Update the helper before changing the window.
- The toggle writes `history_enabled` into the demo config, not the user's real config. In the tray app it calls `WritingToolApp._history_config_changed` and saves `config.json`.
- Timestamps are rendered in the local time zone. Assert the option, headline, and text, not a fixed clock value.
- The store keeps the newest 500 rows by default. The drive only creates two. A retention test needs its own seeded store and is out of scope for this feature.
- History records the applied rework even if the user undoes it. Do not expect Undo to remove the row.
