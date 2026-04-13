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
