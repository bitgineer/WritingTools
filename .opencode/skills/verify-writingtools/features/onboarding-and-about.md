# Onboarding and About

Onboarding is the two-step first-run welcome. It explains the three main workflows, lets the user set the global shortcut, and hands off to the providers-only settings window. About shows the app version, the author, the contributors, and links to the source and releases. Status: verified. The final provider setup is owned by the settings feature.

## Sub-features

- `onboarding-welcome` shows Step 1 of 2, the welcome title, the three feature rows, and the shortcut field.
- `onboarding-shortcut` saves a typed shortcut, trims it, and falls back to `ctrl+space` when it is blank.
- `onboarding-handoff` opens the providers-only settings window and closes the welcome window.
- `about-version` reads the version from `UpdateChecker.CURRENT_VERSION`.
- `about-scroll` puts the author, contributors, and links in a named scroll area.
- `about-links` opens the releases page, the source repository, and contributor profiles.

## How to get to it (user POV)

- Launch Writing Tools with no `config.json`. The welcome window opens.
- Type a shortcut such as `ctrl+alt+j` and choose Continue. The providers-only setup window opens.
- Right-click the tray icon and choose About. The About window opens with the version, author, contributors, and links.
- Run `python -m ui.design_preview --surface onboarding` or `--surface about` to render either surface alone.

## Driving it with verify.py

Preconditions:

- Run from the repository root.
- The helper uses the native Qt platform when a display is available: `windows` on Windows, `xcb` on Linux with `DISPLAY`. It falls back to `offscreen` for headless logic runs. Set `VERIFY_QT_PLATFORM` to force a platform.
- The drive uses a shell for the app. It records the shortcut config, the providers-only handoff, and the tray and hotkey calls.
- The About link drive patches `webbrowser.open` so no browser opens.

- **Render the welcome screen.** Run `.\.venv\Scripts\python.exe -B .opencode\skills\verify-writingtools\scripts\verify.py run --feature onboarding-about --run-id <id>`. The transcript reads `onboarding welcome renders: Welcome to Writing Tools`. The screenshot is `onboarding-light.png` and shows Step 1 of 2, the three numbered feature rows, the Shortcut field, and Continue.
- **Save the shortcut.** The run types `ctrl+alt+j` into the Shortcut field and clicks `Continue`. The transcript reads `onboarding saves the shortcut: {"shortcut": "ctrl+alt+j"}`.
- **Check the handoff.** The transcript reads `onboarding hands off to provider setup: settings_calls=[True] visible=False`. The welcome window closed and the app was asked for providers-only settings.
- **Check the About version.** The run opens `AboutWindow`. The transcript reads `about shows the app version: Version 8`. The version comes from `update_checker.CURRENT_VERSION`, not a hardcoded label.
- **Check the scroll area.** The transcript reads `about details are scrollable: About details`. The screenshot is `about-light.png`.
- **Check the links.** The run clicks `See the latest release` and `View source` with `webbrowser.open` patched. The transcript reads `See the latest release opens releases: call('https://github.com/theJayTea/WritingTools/releases')` and `view source opens the repository: call('https://github.com/theJayTea/WritingTools')`.
- **Proof.** Keep `onboarding-light.png`, `about-light.png`, `transcript.txt`, and `summary.json`.

## Gotchas

- Onboarding does not finish provider setup. It saves the shortcut and opens the providers-only settings window. The Finish AI Setup step is in the settings feature.
- The shortcut is trimmed. A blank or whitespace-only value becomes `ctrl+space`. A malformed value is rejected with a message and setup stays open. Assert the saved value, not the raw field text.
- The drive's shell records `show_settings(True)`. The real app creates a `SettingsWindow` with `providers_only=True` and connects its close signal to exit. Do not report the shell as the real window.
- The About version is `8` in this snapshot. It is not the release tag. Read `CURRENT_VERSION` and assert that value.
- The About link check patches `webbrowser.open`. Without the patch, the verification run opens the user's browser. Keep the patch and record the URL.
- The About window disables minimize and the system menu. It keeps the close button. Do not expect a minimize control.
- The onboarding window is 680 by 600 and the About window is 680 by 640. A screenshot at a much smaller size means the layout was not shown before the grab.
