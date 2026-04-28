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

## 2026-04-28 11:06 +08:00

- Summary: Added export file type choices and guarded plot saving against unsupported filename extensions by falling back to PNG.
- Files: `Python version/skin_analysis/gui.py`, `CHANGELOG.md`
- Verification: `cd "Python version" && python3 -m py_compile main.py skin_analysis/*.py`; `cd "Python version" && python3 -m unittest discover` (pass; Matplotlib warned about using a temporary cache directory)

## 2026-04-28 11:49 +08:00

- Summary: Added a Chinese analysis-method document explaining data loading, baseline construction, drop detection, delta calculation, display modes, warnings, and interpretation limits.
- Files: `ANALYSIS_METHOD.md`, `CHANGELOG.md`
- Verification: Documentation-only change; no code tests run

## 2026-04-28 11:56 +08:00

- Summary: Added an optional editable plot title field while preserving the existing folder-and-metadata default title when the field is blank.
- Files: `Python version/skin_analysis/models.py`, `Python version/skin_analysis/plotting.py`, `Python version/skin_analysis/gui.py`, `Python version/tests/test_plotting.py`, `README.md`, `CHANGELOG.md`
- Verification: `cd "Python version" && python3 -m unittest tests.test_plotting` (pass; Matplotlib warned about using a temporary cache directory); `cd "Python version" && python3 -m py_compile main.py skin_analysis/*.py` (pass); `cd "Python version" && python3 -m unittest discover` (pass; Matplotlib warned about using a temporary cache directory)

## 2026-04-28 12:15 +08:00

- Summary: Made plot title edits update the currently displayed Matplotlib figure immediately so exported PNG files use the edited title without reloading the data.
- Files: `Python version/skin_analysis/gui.py`, `README.md`, `CHANGELOG.md`
- Verification: `cd "Python version" && python3 -m unittest discover` (pass; Matplotlib warned about using a temporary cache directory); `cd "Python version" && python3 -m py_compile main.py skin_analysis/*.py` (pass)

## 2026-04-28 12:34 +08:00

- Summary: Added medicine and dose summaries to grouped overlay plot legends so overlaid concentrations are identifiable.
- Files: `Python version/skin_analysis/plotting.py`, `Python version/tests/test_plotting.py`, `README.md`, `CHANGELOG.md`
- Verification: `cd "Python version" && python3 -m unittest tests.test_plotting` (pass; Matplotlib warned about using a temporary cache directory); `cd "Python version" && python3 -m py_compile main.py skin_analysis/*.py` (pass); `cd "Python version" && python3 -m unittest discover` (pass; Matplotlib warned about using a temporary cache directory)

## 2026-04-28 12:38 +08:00

- Summary: Made grouped overlay legends fall back to the experiment folder name when medicine metadata is blank.
- Files: `Python version/skin_analysis/plotting.py`, `Python version/tests/test_plotting.py`, `README.md`, `CHANGELOG.md`
- Verification: `cd "Python version" && python3 -m unittest tests.test_plotting` (pass; Matplotlib warned about using a temporary cache directory); `cd "Python version" && python3 -m py_compile main.py skin_analysis/*.py` (pass); `cd "Python version" && python3 -m unittest discover` (pass; Matplotlib warned about using a temporary cache directory)

## 2026-04-28 13:00 +08:00

- Summary: Added Delta % statistical analysis by concentration folder, including descriptive statistics, Welch t-tests, Holm-adjusted pairwise comparisons, ANOVA summaries, GUI result viewing, and CSV export.
- Files: `Python version/skin_analysis/models.py`, `Python version/skin_analysis/statistics.py`, `Python version/skin_analysis/gui.py`, `Python version/requirements-gui.txt`, `Python version/tests/test_statistics.py`, `README.md`, `ANALYSIS_METHOD.md`, `CHANGELOG.md`
- Verification: `cd "Python version" && python3 -m unittest tests.test_statistics` (pass; Matplotlib warned about using a temporary cache directory); `cd "Python version" && python3 -m unittest discover` (pass; Matplotlib warned about using a temporary cache directory); `cd "Python version" && python3 -m py_compile main.py skin_analysis/*.py` (pass); `git diff --check` (pass)

## 2026-04-28 13:13 +08:00

- Summary: Added GUI dependency version ranges to avoid NumPy ABI mismatches with older pandas and Matplotlib installs.
- Files: `.gitignore`, `Python version/requirements-gui.txt`, `CHANGELOG.md`
- Verification: `cd "Python version" && python3 -m py_compile main.py skin_analysis/*.py` (pass in global Python); `cd "Python version" && python3 -m unittest discover` (fails in global Python because NumPy 2.4.4 is paired with older pandas 2.0.3 and Matplotlib 3.6.2); `cd "Python version" && .venv-gui/bin/python -m py_compile main.py skin_analysis/*.py` (pass); `cd "Python version" && .venv-gui/bin/python -m unittest discover` (pass; Matplotlib warned about using a temporary cache directory; SciPy emitted one expected runtime warning in stats tests); `cd "Python version" && .venv-gui/bin/python -c "from skin_analysis.gui import RawDataViewerApp; print('gui import ok')"` (pass; Matplotlib warned about using a temporary cache directory)

## 2026-04-28 16:06 +08:00

- Summary: Simplified the statistics workflow to one-way ANOVA only by removing control-group selection, pairwise comparisons, Welch t-test outputs, Holm adjustment, and related report sections.
- Files: `Python version/skin_analysis/models.py`, `Python version/skin_analysis/statistics.py`, `Python version/skin_analysis/gui.py`, `Python version/tests/test_statistics.py`, `README.md`, `ANALYSIS_METHOD.md`, `CHANGELOG.md`
- Verification: `cd "Python version" && python3 -m py_compile main.py skin_analysis/*.py` (pass in global Python); `cd "Python version" && python3 -m unittest tests.test_statistics` (fails in global Python because NumPy 2.4.4 is paired with older pandas 2.0.3); `cd "Python version" && .venv-gui/bin/python -m py_compile main.py skin_analysis/*.py` (pass; venv emitted existing distutils `.pth` warnings); `cd "Python version" && .venv-gui/bin/python -m unittest tests.test_statistics` (pass; Matplotlib warned about using a temporary cache directory); `cd "Python version" && .venv-gui/bin/python -m unittest discover` (pass; Matplotlib warned about using a temporary cache directory); `git diff --check` (pass)
