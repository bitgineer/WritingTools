# Friction journeys

The writer can move any floating surface, reach Rewrite History in one action from the popup or the receipt, see that a rewrite is running within 100 ms, cancel a slow one, and trust that a cancelled response never pastes.

## Sub-features

- `move`: the popup and the receipt move when the user drags their header.
- `history-entry`: the popup header and the receipt header both open Rewrite History in one click. The popup footer names `Ctrl+H`.
- `progress`: a non-activating pill appears immediately with the option name, a spinner, elapsed seconds, and Cancel.
- `cancel`: Cancel dismisses the wait and marks the request superseded.
- `stale-guard`: a response that belongs to an older or cancelled request never reaches the document.
- `dashboard`: a native window lists the recent rewrites, names the provider and shortcut, and hosts Settings, Pause, About, and Exit.
- `dashboard-actions`: an **Edit actions** button opens Settings, where the popup actions can be changed.
- `dashboard-entry`: clicking a recent rewrite opens History at that exact entry.
- `tray-menu`: a left click on the tray icon opens the dashboard. A right click opens the menu.

## How to get to it (user POV)

- Move: drag the title area of the popup or the receipt.
- History from popup: click the clock button in the popup header, or press `Ctrl+H`.
- History from receipt: click the clock button in the receipt header.
- Progress: choose any action in the popup. The pill appears where the popup was.
- Cancel: click Cancel on the pill.

## Driving it with verify.py

Preconditions: run from the repository root with the project virtualenv. The harness uses the native Qt platform when a display is available and falls back to `offscreen`.

- Drag the popup. `run --feature friction` presses the popup title, moves it 64 by 40, and releases. The transcript must read `popup header drags the window: moved 64,40`.
- Open History from the popup. The drive clicks `Open Rewrite History`. The transcript must read `history opens from the popup in one click: show_history calls=1` and `popup yields to history`.
- Watch progress. The drive constructs the real `WorkingPill`, shows it, and measures. The transcript must read `progress appears within 100 ms` with a value of 100 or less, and `progress never takes focus`.
- Confirm the clock runs. After 420 ms the transcript must read `elapsed time advances while the model works` with a value of at least 0.3 seconds.
- Cancel. The drive clicks `Cancel this rewrite`. The transcript must read `cancel is offered and dismisses the wait` with `cancelled=[True]`.
- Drag the receipt and open History from it. The transcript must read `receipt header drags the window` and `receipt opens history in one click`.
- Check the stale guard. The drive calls the real delivery method with an old serial, the live serial, then a cancelled serial. Only the live text may paste.
- Check the dashboard. The drive builds the real `DashboardWindow` over a temporary history database. The transcript must read `dashboard lists the recent rewrites: rows=2`, `dashboard opens history in one click`, `dashboard opens Settings for actions`, `dashboard row opens that exact entry`, and `dashboard pause is real`. The screenshot is `dashboard-light.png`.

## Gotchas

- The drag assertions compare exact pixel deltas. A window manager that snaps or clamps the window will fail them. Move the window away from screen edges in the drive.
- `QTest.mouseMove` must follow a press on the same handle. A move without a press does not move the window.
- The progress pill is intentionally allowed to appear over other windows. Do not assert focus; assert `WindowDoesNotAcceptFocus` and `WA_ShowWithoutActivating` instead.
- The stale guard drive uses the real `WritingToolApp._deliver_response` bound to a Qt host object. It does not construct the tray app, so do not report it as proof that the tray app launched. The doctor owns that probe.
