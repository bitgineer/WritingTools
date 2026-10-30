# Response window

The response window is the reading workspace for options that open in a window instead of replacing the selection. It renders markdown, copies the first response, zooms the messages, accepts a follow-up question, and shows a provider failure in place of a spinner. Status: verified through the real window.

## Sub-features

- `response-initial` shows the option title, the thinking state, and then the first assistant message.
- `response-markdown` renders headings, bold text, lists, tables, and links from markdown.
- `response-copy` copies the first response as markdown.
- `response-zoom` changes the message text size with Zoom in, Zoom out, and Reset zoom.
- `response-followup` sends a typed question, disables the input while waiting, and appends the assistant reply.
- `response-failure` replaces the thinking state with a titled error and the provider message.

## How to get to it (user POV)

- Choose a window option such as Summary, Key Points, or Table from the popup. The response window opens instead of pasting into the source app.
- In the window, use Copy response, the Zoom controls, and the Ask a follow-up question field.
- Run `python -m ui.design_preview --surface response` to render the window alone.

## Driving it with verify.py

Preconditions:

- Run from the repository root.
- The helper uses the native Qt platform when a display is available: `windows` on Windows, `xcb` on Linux with `DISPLAY`. It falls back to `offscreen` for headless logic runs. Set `VERIFY_QT_PLATFORM` to force a platform.
- The drive uses a signal shell for the app. It does not call a provider and does not need an API key.

- **Render the markdown response.** Run `.\.venv\Scripts\python.exe -B .opencode\skills\verify-writingtools\scripts\verify.py run --feature response --run-id <id>`. The run creates a real `ResponseWindow`, sets the selected text, and calls `set_text` with a markdown sample. The transcript reads `markdown response renders: Budget review ... Q3 forecast ... Read the full report`. The screenshot is `response-light.png`.
- **Copy the first response.** The run clicks `Copy response`. The transcript reads `Copy response: clipboard=284 chars`. The clipboard starts with `# Budget review` and contains `Q3 forecast`.
- **Zoom.** The run reads the message view's `zoom_factor`, clicks `Zoom in`, and reads it again. The transcript reads `zoom control changes the message: 1.2 -> 1.32`.
- **Send a follow-up.** The run types `Make it shorter` into `Follow-up question` and clicks `Send follow-up`. The transcript reads `follow-up is sent: [('Rewrite', 'Make it shorter')]` and `input is busy while waiting: enabled=False`. The window option is `Rewrite` because the title is `Rewrite Result` and the window strips the suffix.
- **Receive the reply.** The run emits the follow-up signal with `Shorter version.`. The transcript reads `follow-up response appears: {'role': 'assistant', 'content': 'Shorter version.'}` and the input is enabled again. The screenshot is `response-followup-light.png`.
- **Show a provider failure.** The run opens a second window and emits the app error signal before any text arrives. The transcript reads `provider error shows in the window: Couldn't get a response: The provider returned an error.` The screenshot is `response-failure-light.png`.
- **Proof.** Keep `response-light.png`, `response-followup-light.png`, `response-failure-light.png`, `transcript.txt`, and `summary.json`.

## Gotchas

- The window's `option` is derived by stripping ` Result` from the title. A title of `Rewrite Result` produces `Rewrite`. Assert the stripped value.
- `ResponseWindow` never sets `current_text_display` on itself because `ChatContentScrollArea.add_message` only assigns it when the attribute already exists. Read the `MarkdownTextBrowser` returned by `add_message` or found under `chat_area` when checking zoom. Do not rely on `window.current_text_display`.
- The drive's shell records `process_followup_question` and emits a canned reply. It proves the send path and the response rendering, not a live model call.
- The failure path uses `show_message_signal` with a title that starts with `Error`. A different title leaves the thinking state running.
- Markdown is rendered to HTML. Assert visible text from `toPlainText()`, not raw markdown markers.
- The window resizes itself 100 milliseconds after the first response. Wait before taking the screenshot.
- `Copy response` copies the first assistant message, not the whole conversation. The whole-conversation copy method exists but is not wired to a visible button.
- Closing the window tries to save `response_window_zoom` only when `current_text_display` exists. With the current attribute gap, that save is skipped. Do not use the close path as proof of zoom persistence.
