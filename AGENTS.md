# Skin Analysis Agent Guide

## Purpose

This repository contains a desktop `Tkinter` + `Matplotlib` application for browsing experiment folders, loading `.xlsx` capacitance files, analyzing drop timing, storing experiment medicine metadata, and plotting the results.

Agents working here should optimize for safety, clarity, and small reversible changes.

## Core Working Style

1. Work in small, focused tasks: one feature, one bug fix, or one documentation update at a time.
2. Keep scope narrow and avoid unrelated refactors.
3. Preserve the existing architecture and naming patterns.
4. Prefer incremental improvements over broad rewrites.
5. Prefer safe and readable solutions over clever ones.
6. If requirements are unclear and the choice is risky, pause and clarify instead of guessing.

## Active Code Area

Treat `Python version/` as the active implementation unless the user explicitly asks for another area.

- `Python version/main.py`: launch entrypoint only
- `Python version/skin_analysis/config.py`: constants and defaults
- `Python version/skin_analysis/filesystem.py`: experiment folder and file discovery
- `Python version/skin_analysis/analysis.py`: Excel loading and signal/drop analysis
- `Python version/skin_analysis/metadata.py`: `.skin_analysis_metadata.json` loading, validation, and saving
- `Python version/skin_analysis/models.py`: shared dataclasses and typed payloads
- `Python version/skin_analysis/plotting.py`: display transforms and plot payload assembly
- `Python version/skin_analysis/gui.py`: Tk widgets, dialogs, threading handoff, and Matplotlib rendering
- `Python version/tests/`: unit tests for non-GUI logic

## Expected Data Shape

The current app treats each direct child under the selected root as one experiment folder:

```text
ROOT/
  Experiment A/
    1.xlsx
    2.xlsx
    .skin_analysis_metadata.json
  Experiment B/
    1.xlsx
    2.xlsx
```

Rules:

- Each Excel file must contain a column named `pF - Plot 0`.
- Each experiment folder may contain `.skin_analysis_metadata.json`.
- If metadata behavior changes, keep backward compatibility or update all readers, writers, tests, and docs together.

## Mandatory Agent Workflow

### 1. Planning

Before starting any non-trivial change, explicitly identify:

1. Affected files
2. Change plan
3. Potential risks

Do not jump into broad edits before the scope is clear.

### 2. Implementation

- Modify only the files needed for the task.
- Do not move business logic back into `main.py`.
- Prefer pure helpers in `analysis.py`, `plotting.py`, `filesystem.py`, and `metadata.py`.
- Keep GUI changes localized to `gui.py` and mirror related state in the appropriate models/settings.
- Do not change data contracts (`ProcessedSignal`, `PlotPayload`, metadata schema) unless all callers and tests are updated together.
- Do not introduce new dependencies unless they are necessary and justified.
- Do not delete large sections of code without explaining why.

### 3. Validation

After implementation, report:

1. What changed
2. Why it changed
3. Possible side effects or regression risks
4. Suggested tests or manual checks

For non-trivial tasks, prefer the response structure:

1. `PLAN`
2. `IMPLEMENTATION`
3. `CHANGES`
4. `RISKS`
5. `TESTS`

## Project-Specific Guardrails

### Threading

Background work may read files and build `PlotPayload`, but all Tk widget updates must stay on the main thread. Keep using `self.after(...)` for UI updates after worker completion.

### Safe Extension Points

- Add new display modes in `Python version/skin_analysis/plotting.py`.
- Adjust signal detection behavior in `Python version/skin_analysis/analysis.py`.
- Extend metadata handling in `Python version/skin_analysis/metadata.py`.
- Add new GUI controls in `Python version/skin_analysis/gui.py`, then update the corresponding settings/models together.
- Add or update non-GUI tests in `Python version/tests/` before changing behavior.

### Do Not Break These Assumptions

- `main.py` stays a thin launcher.
- Tk or Matplotlib widget methods must not be called from worker threads.
- User-visible workflow changes should also update `README.md`.
- Folder discovery changes must stay aligned with the current experiment-folder layout.
- Metadata schema changes must consider existing `.skin_analysis_metadata.json` files already on disk.

## Git Workflow (Only When The User Wants Git Operations)

This workspace may not always be attached to Git. Do not invent branches or commits unless the user explicitly asks for Git work. When Git workflow is requested, use the following model:

- `main`: stable / production
- `beta`: integration / testing
- `feature/*`: new feature work
- `fix/*`: bug fixes
- `hotfix/*`: urgent production fixes

Rules:

- Never commit directly to `main`.
- Create the appropriate branch before coding.
- Feature work goes on `feature/*`.
- Bug fixes go on `fix/*` or `hotfix/*`.
- If a hotfix is made from `main`, it should also be merged back into `beta`.

If the folder is not under Git yet, keep changes isolated and recommend that the user initialize Git before relying on branch rules.

## Commit Message Convention

Only if the user explicitly asks for commits:

- `[feat] short description`
- `[fix] short description`
- `[refactor] short description`
- `[docs] short description`
- `[test] short description`

Commit after meaningful checkpoints, not after every tiny edit.

## Run And Test

```bash
cd "Python version"
python3 main.py
python3 -m unittest discover
python3 -m py_compile main.py skin_analysis/*.py
```

Manual GUI verification for UI-related changes:

1. Launch the app
2. Paste or browse a root path
3. Refresh and select an experiment folder
4. Edit medicine metadata if relevant
5. Load and plot data
6. Confirm legends, drop lines, and export still work

For macOS GUI setup and troubleshooting, see [MACOS_GUI_FIXES.md](./MACOS_GUI_FIXES.md).

## Change Log Rule

- Any AI agent change that modifies repo files must append a new entry to `CHANGELOG.md` before finishing.
- Keep `CHANGELOG.md` append-only unless the user explicitly asks to rewrite prior history.
- Each entry must include an Asia/Taipei timestamp, a short summary, the affected files, and the verification commands or outcomes.
