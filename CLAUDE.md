# Skin Analysis — Claude Code Guide

## Project Overview

Desktop application (Tkinter + Matplotlib) for browsing experiment folders, loading `.xlsx` capacitance files, analyzing drop timing, storing experiment medicine metadata, and plotting results.

A parallel Rust/Tauri rewrite (`tauri-app/`) is in progress but significantly lags behind the Python edition. Python is the primary active development target.

## Repository Layout

```
python-app/      ← active Python edition (Tkinter + Matplotlib)
tauri-app/       ← in-progress Tauri/Rust rewrite
shared/          ← parity cases shared between both editions
scripts/         ← standalone one-off analysis scripts
archive/         ← retired single-file prototype
```

## Active Code — Python Edition

`python-app/` is the active implementation. All work defaults here unless the user says otherwise.

| File | Purpose |
|------|---------|
| `python-app/main.py` | Thin launch entrypoint only |
| `python-app/skin_analysis/config.py` | Constants and defaults |
| `python-app/skin_analysis/filesystem.py` | Experiment folder and file discovery |
| `python-app/skin_analysis/analysis.py` | Excel loading and signal/drop analysis |
| `python-app/skin_analysis/metadata.py` | `.skin_analysis_metadata.json` load/validate/save |
| `python-app/skin_analysis/models.py` | Shared dataclasses and typed payloads |
| `python-app/skin_analysis/plotting.py` | Display transforms and plot payload assembly |
| `python-app/skin_analysis/gui.py` | Tk widgets, dialogs, threading handoff, Matplotlib rendering |
| `python-app/tests/` | Unit tests for non-GUI logic |

## Running and Testing

```bash
cd python-app
python3 main.py
python3 -m unittest discover
python3 -m py_compile main.py skin_analysis/*.py
```

Manual GUI verification for UI changes:
1. Launch the app
2. Paste or browse a root path
3. Refresh and select an experiment folder
4. Edit medicine metadata if relevant
5. Load and plot data
6. Confirm legends, drop lines, and export still work

For macOS GUI setup, see [MACOS_GUI_FIXES.md](./MACOS_GUI_FIXES.md).

## Tauri Edition

`tauri-app/` is a parallel rewrite (Rust + Tauri + Svelte + Plotly.js). It lags behind the Python edition and is not yet production-ready. See [tauri-app/README.md](./tauri-app/README.md) and [MIGRATION_RULES.md](./MIGRATION_RULES.md) for sync rules between the two editions.

```bash
cd tauri-app
npm install
npm run tauri dev
```

## Expected Data Shape

```
ROOT/
  Experiment A/
    1.xlsx
    2.xlsx
    .skin_analysis_metadata.json
  Experiment B/
    1.xlsx
    2.xlsx
```

- Each Excel file must contain a column named `pF - Plot 0`.
- Each experiment folder may contain `.skin_analysis_metadata.json`.

## Architecture Rules

- `main.py` must stay a thin launcher — no business logic.
- Pure helpers belong in `analysis.py`, `plotting.py`, `filesystem.py`, and `metadata.py`.
- GUI changes go in `gui.py`; mirror any new state in the appropriate models/settings.
- Do not change data contracts (`ProcessedSignal`, `PlotPayload`, metadata schema) without updating all callers and tests together.
- Do not introduce new dependencies unless necessary and justified.

## Threading

Background workers may read files and build `PlotPayload`. All Tk widget updates must stay on the main thread — use `self.after(...)` for UI updates after worker completion. Never call Tk or Matplotlib widget methods from worker threads.

## Safe Extension Points

- New display modes → `plotting.py`
- Signal detection behavior → `analysis.py`
- Metadata handling → `metadata.py`
- New GUI controls → `gui.py` + update corresponding settings/models
- New or updated tests → `tests/` (write tests before changing behavior)

## Invariants — Do Not Break

- Folder discovery must stay aligned with the experiment-folder layout above.
- Metadata schema changes must remain backward-compatible with existing `.skin_analysis_metadata.json` files on disk, or update all readers, writers, tests, and docs together.
- User-visible workflow changes must also update `README.md`.

## Git Workflow

Only perform Git operations when the user explicitly requests them.

Branch model:
- `main` — stable/production
- `beta` — integration/testing
- `feature/*` — new features
- `fix/*` — bug fixes
- `hotfix/*` — urgent production fixes

Rules:
- Never commit directly to `main`.
- Hotfixes from `main` must also be merged back into `beta`.

Commit message format (only when user asks for commits):
```
[feat] short description
[fix] short description
[refactor] short description
[docs] short description
[test] short description
```

## Changelog

Every change to repo files must append an entry to `CHANGELOG.md` before finishing. Keep it append-only. Each entry must include an Asia/Taipei timestamp, short summary, affected files, and verification commands or outcomes.
