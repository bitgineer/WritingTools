---
name: writingtools-design
description: Design and review Writing Tools UI changes against the one-shell paper system, the shared workflow state, and the friction scorecard. Use when adding or changing a Writing Tools surface, popup, receipt, reader, shell view, settings form, or copy.
---

# Writing Tools design

Use this skill before changing a Writing Tools surface. The app is one system,
not a set of windows.

## The shape

One `AppShell` owns Home, Rewrites, Actions, Settings, and About. A left rail
switches views. In-context surfaces (popup, progress pill, receipt, reader)
stay near the writing and route back to the matching view. The shell is the
only place a writer manages the app.

Read `design/unified-flow.md` for the full flow and decisions D20 to D29.
Read `design/system.md` for the tokens and component rules.

## Non-negotiable rules

1. **One workflow state.** Popup, pill, receipt, shell, and tray read
   `WritingToolApp.workflow` (`core/workflow.py`). A response is applied only
   when its serial is current. Do not add a second request tracker.
2. **One action editor.** `ui/ActionsView.py` owns adding, editing, renaming,
   reordering, and deleting actions. The popup only runs actions. Never add
   edit mode, drag reorder, or an add button to the popup.
3. **One first run.** Setup is a state of Home (`ui/SetupWizard.py`). Do not
   add an onboarding window or a providers-only window.
4. **One provider form.** `ui/ProviderForm.py` is used by first run and
   Settings. It validates before writing, shows errors inline, and saves
   through `ProviderForm.save`.
5. **One history surface.** `ui/RewritesView.py` is the only history. Do not
   add a History window or a dashboard-to-history detour.
6. **One design layer.** `ui/design.py` owns tokens, type, spacing, control
   styles, and shell object names. `rework/theme.py` owns the palette values.
   A view may style one unique element, not a second palette.
7. **One primary action per surface.** Everything else is secondary or ghost.
8. **Cause and next step.** An error names what failed and offers one action.
   Never paste raw provider JSON into a dialog. Prefer an inline banner.
9. **Keyboard first.** Every action is reachable by Tab. Icon-only controls
   need `setAccessibleName` and a tooltip. Focus is always visible.
10. **No new window for a management task.** If the task changes config,
    actions, history, or provider state, it belongs in a shell view.

## Where work goes

| Change | File |
| --- | --- |
| Shell, rail, top bar, palette, toast, banners | `ui/AppShell.py`, `ui/Components.py` |
| Home, status, recent rewrites, first run | `ui/HomeView.py`, `ui/SetupWizard.py` |
| History, diff, copy, privacy | `ui/RewritesView.py` |
| Action list and inline editor | `ui/ActionsView.py` |
| General, provider, privacy, updates | `ui/SettingsView.py`, `ui/ProviderForm.py` |
| About | `ui/AboutView.py` |
| Popup | `ui/CustomPopupWindow.py` |
| Receipt | `rework/review_card.py` |
| Progress | `ui/WorkingPill.py` |
| Reader | `ui/ResponseWindow.py` |
| Workflow state | `core/workflow.py` |
| Config | `core/config.py` |
| Action data | `ui/ActionStore.py` |
| History data | `rework/history.py` |

If you need a new shell method, add it to `AppShell` and call it from the view.
Do not reach across views with private attributes.

## Copy

- The result is a **rewrite**.
- The action is a **rewrite**, **proofread**, or **custom instruction**.
- The history view is **Rewrites**.
- The long-result surface is the **reader**.
- The setting is **AI provider**.
- The key is **shortcut**, not hotkey, in user-facing copy.
- Use sentence case. Verb-first buttons. No em dashes. No "seamless",
  "effortless", "AI-powered", or "oops".

## Friction check

Score a workflow as:

`actions + 2 x context switches + decisions + 3 x dead ends`

Targets are in `design/friction-baseline.md`. A change that adds a window, a
modal, or a restart raises the score. A change that removes one lowers it.
Do not add a step to explain a step.

## Verify

Run from the repo root:

```powershell
.\.venv\Scripts\python.exe -B .opencode\skills\verify-writingtools\scripts\verify.py gate --run-id design-gate
```

Render the shell for a visual check:

```powershell
.\.venv\Scripts\python.exe -B .scratch\shell_preview.py --light
.\.venv\Scripts\python.exe -B .scratch\shell_preview.py --light --setup
```

Screenshots land in `.scratch/shell/`. Check light and dark, empty and filled,
and the setup path. A screenshot alone is not proof: read the widget text, the
config value, the history count, or the clipboard after the action.

## Review before ship

- [ ] Every management task is in a shell view, not a new window.
- [ ] The popup has no editor controls.
- [ ] First run reaches a provider inside Home.
- [ ] Errors are inline and name a next step.
- [ ] Every control has an accessible name and a focus ring.
- [ ] The primary action is obvious and singular.
- [ ] The copy uses the terms above.
- [ ] The verify gate passes, including the workflow drive.
- [ ] The screenshot and video evidence exist under `artifacts/verify/`.
