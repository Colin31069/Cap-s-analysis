# Skin Analysis Agent Guide

## Purpose

This project is a desktop Tkinter application for browsing experiment folders, loading `.xlsx` raw capacitance files, analyzing drop timing, and plotting the results with Matplotlib.

## Package Map

Python version source lives under `Python version/`:

- `Python version/main.py`: official launch entrypoint
- `Python version/skin_analysis/config.py`: constants and app defaults
- `Python version/skin_analysis/filesystem.py`: folder and file discovery helpers
- `Python version/skin_analysis/analysis.py`: Excel loading and signal analysis
- `Python version/skin_analysis/models.py`: typed dataclasses passed between modules
- `Python version/skin_analysis/plotting.py`: display-mode transforms and plot payload assembly
- `Python version/skin_analysis/gui.py`: Tk widgets, dialogs, threading handoff, and Matplotlib rendering
- `Python version/tests/`: unit tests for non-GUI logic

## Run And Test

```bash
cd "Python version"
python3 main.py
python3 -m unittest discover
python3 -m py_compile main.py skin_analysis/*.py
```

For macOS GUI setup and troubleshooting, see [MACOS_GUI_FIXES.md](./MACOS_GUI_FIXES.md).

## Expected Data Shape

The app expects a three-level folder structure under the selected root:

```text
ROOT/
  Group/
    Volume/
      Solution/
        1.xlsx
        2.xlsx
```

Each Excel file must contain a column named `pF - Plot 0`.

## Threading Rule

Background work may read files and build `PlotPayload`, but all Tk widget updates must stay on the main thread. Keep using `self.after(...)` for any UI updates after a worker thread finishes.

## Safe Extension Points

- Add new display modes in `skin_analysis/plotting.py`.
- Adjust signal detection behavior in `skin_analysis/analysis.py`.
- Add new GUI controls in `skin_analysis/gui.py`, then mirror them in `PlotSettings`.
- Add tests for any non-GUI logic under `tests/` before changing behavior.

## Guardrails For Agents

- Do not put new business logic back into `main.py`.
- Prefer pure helper functions in `analysis.py` and `plotting.py` so behavior stays testable.
- Preserve the current `ProcessedSignal` and `PlotPayload` contracts unless you update all callers and tests together.
- If you touch Tk or Matplotlib rendering code, verify that worker threads never call widget methods directly.

## Change Log Rule

- Any AI agent change that modifies repo files must append a new entry to `CHANGELOG.md` before finishing.
- Keep `CHANGELOG.md` append-only unless the user explicitly asks to rewrite prior history.
- Each entry must include an Asia/Taipei timestamp, a short summary, the affected files, and the verification commands or outcomes.
