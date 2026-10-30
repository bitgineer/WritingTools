# Popup and rework receipt

The popup is the action palette that appears after the Writing Tools hotkey. After an in-place rework, a compact receipt shows the option, the changed-word count, the first edits, and Review and Undo actions. The expanded review shows a word-level diff for small edits or the full original and revised text for a substantial rewrite. Status: verified through the demo and preview harnesses. The global hotkey and foreground-app capture are not synthesized.

## Sub-features

- `popup-open` shows the paper card with the title, the custom instruction field, the action grid, and the Enter and Esc footer.
- `popup-custom` sends a typed instruction through the Apply this change button.
- `popup-edit` rearranges buttons in place with the pencil control and shows the add, edit, and delete affordances.
- `receipt-compact` appears after a change and names the option, the headline, the first edits, and the saved state.
- `receipt-review` expands to the inline diff for a small edit and to the full-text view for a substantial rewrite.
- `receipt-copy` copies the revised text and changes the button label to Copied.
- `receipt-undo` dismisses the receipt and restores the demo document to the original text.
- `receipt-theme` renders the receipt in light and dark palettes.

## How to get to it (user POV)

- Press the global Writing Tools shortcut in any app. The popup opens with the selected text captured in the background.
- Choose an action button, or type an instruction in Describe your change and press Enter or Apply this change.
- Choose the pencil to enter edit mode, then drag buttons or use the add, edit, and delete controls.
- After a rework lands, use Review changes on the receipt to expand it, Copy revised to copy the result, or Undo to return the source app to the original.
- Run `python -m rework.demo` from `Windows_and_Linux` to use the same receipt outside the tray app. The Small edits, Larger rewrite, History, and Dark buttons are the demo entry points.
- Run `python -m ui.design_preview --surface popup` or `--surface popup-edit` to render the popup surfaces alone.

## Driving it with verify.py

Preconditions:

- Run from the repository root.
- `.venv\Scripts\python.exe` has PySide6 installed.
- No real API key is needed. The demo uses fixed sample text.
- The helper uses the native Qt platform when a display is available: `windows` on Windows, `xcb` on Linux with `DISPLAY`. It falls back to `offscreen` for headless logic runs. Set `VERIFY_QT_PLATFORM` to force a platform.

- **Render the popup and editor.** Run `.\.venv\Scripts\python.exe -B .opencode\skills\verify-writingtools\scripts\verify.py run --feature surfaces --run-id <id>`. The surfaces folder gets `popup-light.png`, `popup-dark.png`, `popup-edit-light.png`, and `popup-edit-dark.png`. Each is a valid PNG at 592 by 360 pixels or larger. The popup screenshot shows Writing Tools, the Describe your change field, the two-column action grid, and `Enter to send · Esc to close`. The edit screenshot shows `Edit buttons`, `Drag to rearrange`, and the add control.
- **Open the demo receipt.** Run `.\.venv\Scripts\python.exe -B .opencode\skills\verify-writingtools\scripts\verify.py run --feature receipt --run-id <id>`. The run calls `DemoWindow.run_example("small")`. The transcript reads `receipt appears: compact card visible`, `compact title: Concise rewrite`, `compact headline: 15 words changed`, and `compact sample: First changes: yesterday to ; went through to reviewed`.
- **Check the saved state.** The compact card shows `Saved to History.` because the demo save handler writes to its temporary store. Run the same command and read `history saved flag: Saved to History.`
- **Expand the review.** The run clicks the real `Review changes` button. The transcript reads `review expands: expanded=True`, `small edit uses inline diff: DiffView`, and `review shows both versions`. The review screenshot is `receipt-review-light.png`.
- **Copy the result.** The run clicks `Copy revised text`. The transcript reads `copy revised: clipboard=290 chars, button=Copied`. The clipboard contains the revised sample, not the original.
- **Undo.** The run clicks `Undo rework`. The transcript reads `undo restores the demo document` and `receipt closes after undo`. The demo editor returns to the original 330-character sample.
- **Check the substantial path.** The run switches to `Larger rewrite`. The transcript reads `large rewrite is substantial: substantial=True` and `substantial rewrite uses full text: FullTextView`. The screenshot is `receipt-review-large-light.png`.
- **Check the dark theme.** The run clicks `Dark`, runs the small sample again, and expands the card. The transcript reads `dark theme applies: palette=dark`. The screenshots are `receipt-compact-dark.png` and `receipt-review-dark.png`.
- **Proof.** Keep `evidence/receipt-compact-light.png`, `evidence/context-compact-light.png`, `evidence/receipt-review-light.png`, `evidence/receipt-review-large-light.png`, `evidence/receipt-compact-dark.png`, and `evidence/receipt-review-dark.png` with `evidence/summary.json`. The summary records the git HEAD and the working-tree status.

## Gotchas

- The demo editor stands in for the source application. It proves the receipt and the undo wiring, not a real Word or browser undo. The real source-app undo is best effort and is not covered here.
- The real popup hotkey path needs a global keyboard hook and a foreground app with a selection. The harness does not synthesize that path. Use the preview for the popup and the demo for the receipt. Do not report the real hotkey path as verified.
- The demo receipt sample text is fixed. A run that expects `very good` and `strong` is reading the unit-test sample, not the demo sample. The demo sample contains `yesterday` and `reviewed`.
- The receipt auto-closes after 20 seconds when the pointer is not over it. Drive it promptly or keep the pointer inside. The helper finishes well inside that window.
- `design_preview` creates a new `QApplication` for each surface. Run one surface per process. The helper does this for you.
- A preview subprocess can exit abnormally after saving a valid PNG on this Qt build. The helper retries once and checks the PNG header and dimensions. Record the exit code if it appears.
- Do not edit `design/qt`. The preview output is redirected to the run evidence directory.
