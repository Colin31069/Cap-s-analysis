# CHANGELOG

Append-only record of AI agent changes for this workspace.

## 2026-04-13 14:39 +08:00

- Summary: Added pasted root path support, a collapsible medicine metadata section, and AI agent changelog rules.
- Files: `AGENTS.md`, `README.md`, `skin_analysis/filesystem.py`, `skin_analysis/gui.py`, `tests/test_filesystem.py`
- Verification: `python3 -m unittest discover`; `python3 -m py_compile main.py skin_analysis/*.py`

## 2026-04-13 14:42 +08:00

- Summary: Finalized the root path workflow, stabilized filesystem path tests across macOS path aliases, and re-ran verification.
- Files: `CHANGELOG.md`, `tests/test_filesystem.py`
- Verification: `python3 -m unittest discover`; `python3 -m py_compile main.py skin_analysis/*.py`

## 2026-04-13 14:48 +08:00

- Summary: Moved the Python implementation into `Python version/` and updated docs/tests to run from that folder.
- Files: `README.md`, `AGENTS.md`, `MIGRATION_RULES.md`, `desktop-tauri/README.md`, `Python version/tests/test_parity_cases.py`
- Verification: `cd "Python version" && python3 -m py_compile main.py skin_analysis/*.py`; `cd "Python version" && python3 -m unittest discover` (pass)

## 2026-04-13 15:46 +08:00

- Summary: Reworked the agent instructions to match the current Tkinter project structure, metadata flow, validation expectations, and optional Git branch workflow.
- Files: `AGENTS.md`, `CHANGELOG.md`
- Verification: Documentation-only change; no code tests run

## 2026-04-13 16:40 +08:00

- Summary: Shifted plotted time axes to use the detected drop as `0`, updated the GUI label/drop marker behavior, and documented the new overlay semantics.
- Files: `Python version/skin_analysis/plotting.py`, `Python version/skin_analysis/gui.py`, `Python version/tests/test_plotting.py`, `README.md`, `CHANGELOG.md`
- Verification: `cd "Python version" && python3 -m unittest tests.test_plotting tests.test_analysis`; `cd "Python version" && python3 -m unittest discover`; `cd "Python version" && python3 -m py_compile main.py skin_analysis/*.py`

## 2026-04-14 00:50 +08:00

- Summary: Added first-20s baseline accuracy warnings with configurable thresholds, surfaced warning states in legends and GUI dialogs, and documented the new user guidance.
- Files: `Python version/skin_analysis/config.py`, `Python version/skin_analysis/analysis.py`, `Python version/skin_analysis/models.py`, `Python version/skin_analysis/plotting.py`, `Python version/skin_analysis/gui.py`, `Python version/tests/test_analysis.py`, `Python version/tests/test_plotting.py`, `README.md`, `CHANGELOG.md`
- Verification: `cd "Python version" && python3 -m unittest tests.test_analysis tests.test_plotting`; `cd "Python version" && python3 -m unittest discover`; `cd "Python version" && python3 -m py_compile main.py skin_analysis/*.py`; manual spot-check with `exprimental_data/J_fin`

## 2026-04-14 01:18 +08:00

- Summary: Added session-only timing controls for baseline duration and drug-apply search windows, auto-shortened overlapping baselines, and surfaced fallback timing warnings in the plot workflow.
- Files: `Python version/skin_analysis/config.py`, `Python version/skin_analysis/analysis.py`, `Python version/skin_analysis/models.py`, `Python version/skin_analysis/plotting.py`, `Python version/skin_analysis/gui.py`, `Python version/tests/test_analysis.py`, `Python version/tests/test_plotting.py`, `README.md`, `CHANGELOG.md`
- Verification: `cd "Python version" && python3 -m unittest tests.test_analysis tests.test_plotting`; `cd "Python version" && python3 -m unittest discover`; `cd "Python version" && python3 -m py_compile main.py skin_analysis/*.py`; manual spot-check with `exprimental_data/J_fin`

## 2026-04-22 13:30 +08:00

- Summary: Restructured repository layout — renamed folders to remove spaces and standardise naming, moved archived prototype and standalone scripts to dedicated directories, added Tauri edition section to README, updated all cross-references, and rewrote CLAUDE.md from AGENTS.md for Claude Code conventions.
- Files: `python-app/` (was `Python version/`), `tauri-app/` (was `desktop-tauri/`), `archive/` (was `main_alalysis_old/`), `scripts/` (new), `CLAUDE.md`, `README.md`, `MIGRATION_RULES.md`, `tauri-app/README.md`, `CHANGELOG.md`
- Verification: `cd python-app && python3 -m py_compile main.py skin_analysis/*.py`; `cd python-app && python3 -m unittest discover`
