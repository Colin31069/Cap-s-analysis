# Skin Analysis — Improvement Backlog

> **Audience:** Coding agents implementing improvements to `python-app/`.
> **Priority levels:** P0 (critical UX blockers) → P3 (polish / nice-to-have).
> **File-scoped tags** mark which module each item touches.

---

## 1. GUI / UX — High Impact

### P0 — Blockers

#### 1.1 Hardcoded macOS default path breaks Windows startup  
**Files:** `python-app/skin_analysis/config.py`  
`DEFAULT_ROOT_PATH = "/Users/k/Documents/skin_data/20260407"` is a macOS absolute path.  
On Windows or Linux the left panel starts with an invalid path, and Refresh immediately errors.  
**Fix:** Derive the default from `pathlib.Path.home()`, e.g. `Path.home() / "Documents"`.  
Persist the last-used path to a small JSON settings file (see §4.1) and restore it on startup.

#### 1.2 No progress feedback during file loading  
**Files:** `python-app/skin_analysis/gui.py`  
The cursor switches to "watch" but the UI gives no per-file progress. For experiments with
10+ large .xlsx files the window appears frozen.  
**Fix:** Add a `ttk.Progressbar` (indeterminate mode) in the control panel that starts when
the worker thread begins and stops when `_plot_data_apply` is called. Alternatively, emit
`self.after(0, ...)` status-line updates from the worker to a `tk.StringVar` status label.

#### 1.3 Warning dialog is non-modal — allows state divergence  
**Files:** `python-app/skin_analysis/gui.py` → `_show_warning_dialog`  
The dialog is a `Toplevel` without `grab_set()`. The user can click LOAD & PLOT again while
the dialog is open, launching a second worker thread. The first dialog then refers to stale data.  
**Fix:** Call `dialog.grab_set()` after creation. Track `_warning_dialog` reference and
destroy it before creating a new one (already partially implemented, just add `grab_set()`).

---

### P1 — Significant UX improvements

#### 1.4 No status bar / last-action feedback  
**Files:** `python-app/skin_analysis/gui.py`  
After a successful plot, nothing confirms completion. After a failed file, nothing lists which
file failed. The user must re-open the warning dialog or guess.  
**Fix:** Add a single-line `tk.Label` status bar at the bottom of the window. Update it with:
- "Loaded N files, plotted M traces." on success
- "Warning: K files failed — click for details." (clickable) if any file returned `None`
- Timestamp or elapsed time for reassurance on slow loads

#### 1.5 Spinbox floating-point display artifacts  
**Files:** `python-app/skin_analysis/gui.py`  
`ttk.Spinbox` with `increment=0.1` produces strings like `"20.100000000002"` due to IEEE 754
accumulation.  
**Fix:** Bind `<FocusOut>` to a formatter: `var.set(f"{float(var.get()):.1f}")`. Or use
`increment="0.1"` as a string and override the Spinbox's internal `_validate` command with
one that formats to 1 decimal place on every key-up.

#### 1.6 Legend always anchored upper-left, overlaps data  
**Files:** `python-app/skin_analysis/plotting.py` (or `gui.py` where `ax.legend()` is called)  
`ax.legend(loc="upper left", bbox_to_anchor=(1, 1))` is hardcoded. For normalized data
the upper-left region often overlaps the capacitance drop curve.  
**Fix:** Expose a "Legend position" dropdown in the control panel (values: Auto, Upper Left,
Upper Right, Lower Left, Lower Right, Outside Right). Pass as a `PlotSettings` field.
Default to `"best"` (Matplotlib auto-placement) for non-overlay mode.

#### 1.7 No ability to remove a single trace without clearing all  
**Files:** `python-app/skin_analysis/gui.py`  
`clear_plot()` wipes all traces. If the user added 4 overlay groups and wants to remove one,
they must re-plot from scratch.  
**Fix:** In the file list area (or a separate "Loaded traces" panel), add checkboxes next to
each loaded experiment. A "Remove selected" or per-checkbox toggle that calls `ax.lines[i].remove()`
and `canvas.draw_idle()`.

#### 1.8 Export limited to PNG — no SVG/PDF for publications  
**Files:** `python-app/skin_analysis/gui.py` → `export_plot`  
Currently hard-coded to `figure.savefig(path, dpi=300)` with a `.png` extension filter.  
**Fix:** Use `filedialog.asksaveasfilename` with a compound filetypes list:  
`[("PNG", "*.png"), ("SVG", "*.svg"), ("PDF", "*.pdf"), ("TIFF", "*.tiff")]`.  
Let Matplotlib infer the format from the extension.

#### 1.9 No tooltip / inline help on controls  
**Files:** `python-app/skin_analysis/gui.py`  
Parameters like "Baseline Duration", "Apply Tolerance" are opaque to new users.  
**Fix:** Implement a lightweight `create_tooltip(widget, text)` helper using `Toplevel` + `bind("<Enter>", ...)` / `bind("<Leave>", ...)`. Add short tooltip strings to every control.  
Example: `"Baseline Duration: seconds of pre-drug signal used to compute the reference mean."`

#### 1.10 Warning text mixes languages (Chinese in English UI)  
**Files:** `python-app/skin_analysis/plotting.py`  
Legend suffixes `" [注意]"` and `" [不準確]"` are Chinese inside an otherwise English/mixed UI.  
**Fix:** Consolidate all user-visible strings into a single `STRINGS` dict in `config.py` (or a
dedicated `i18n.py`). Default to English: `"[!]"` / `"[!!]"`. If CJK support is desired, add a
`LOCALE` config that switches the dict.

#### 1.11 No keyboard shortcuts for common actions  
**Files:** `python-app/skin_analysis/gui.py`  
Power users must always reach for the mouse.  
**Fix:** Bind:
- `<Return>` on the folder listbox → trigger "LOAD & PLOT"
- `<F5>` → Refresh folder structure  
- `<Ctrl+E>` → Export plot  
- `<Ctrl+L>` → focus root path entry  
- `<Escape>` → close warning dialog

---

### P2 — Quality-of-life improvements

#### 1.12 No search / filter for experiment folder list  
**Files:** `python-app/skin_analysis/gui.py`  
When a root contains 30+ experiment folders, the `Listbox` (height=8) requires extensive scrolling.  
**Fix:** Add a `ttk.Entry` filter box above the Listbox. Bind `<KeyRelease>` to filter
`_all_folders` (store unfiltered list separately) and repopulate the Listbox to only matching entries.

#### 1.13 Metadata editor has no undo / reset button  
**Files:** `python-app/skin_analysis/gui.py`  
Autosave writes to disk on every blur. If the user accidentally clears a field, there is no way
to revert without knowing the original value.  
**Fix:** When loading metadata from disk, snapshot the loaded `ExperimentMetadata` into
`_metadata_snapshot`. Add a "Reset" button that restores from that snapshot and re-saves.

#### 1.14 Fixed left panel width (310 px) cannot be resized  
**Files:** `python-app/skin_analysis/gui.py`  
**Fix:** Replace the fixed-width `Canvas`-based scroll panel with a `PanedWindow` (horizontal sash)
between the control column and the Matplotlib canvas. Min width ~260 px, default 320 px.

#### 1.15 App window title is too technical  
**Files:** `python-app/skin_analysis/gui.py`  
`"Raw Data Viewer - v3.5"` is not meaningful to a lab user.  
**Fix:** Change to `"Skin Analysis — v3.5"`. Update experiment-level title dynamically to
`"Skin Analysis — {experiment_name}"` when an experiment is loaded.

#### 1.16 No recent paths history  
**Files:** `python-app/skin_analysis/gui.py`, `python-app/skin_analysis/config.py`  
Users return to the same 2–3 root paths daily, but must type the full path each time.  
**Fix:** Maintain a `recent_paths` list (max 5) in the user settings JSON (§4.1). Replace the
root-path `Entry` with a `ttk.Combobox` populated from `recent_paths`. Append on successful Refresh.

#### 1.17 No visual indicator for baseline quality before loading  
**Files:** `python-app/skin_analysis/gui.py`  
Baseline quality warnings only appear *after* clicking LOAD & PLOT. The user has no way to
see per-file quality without reading warning text.  
**Fix:** In the "Loaded traces" list (if implemented per §1.7), add color-coded icons:
green circle = ok, yellow triangle = warning, red X = inaccurate. Derive from
`PlotItem.baseline_warning_status` after `build_plot_payload` returns.

#### 1.18 Metadata section collapse does not persist across sessions  
**Files:** `python-app/skin_analysis/gui.py`  
`_metadata_expanded` resets to `True` on every launch.  
**Fix:** Save/restore `metadata_panel_expanded` in user settings JSON (§4.1).

---

## 2. Signal Analysis Algorithm

### P1 — Analytical rigor improvements

#### 2.1 Single-point threshold crossing is noise-susceptible  
**Files:** `python-app/skin_analysis/analysis.py` → `_find_first_threshold_crossing`  
A single transient noise spike above `mean + 3σ` will be mistaken for the drug-application drop.  
**Fix:** Require `N` **consecutive** points above the threshold before declaring a crossing.
Add `config.DROP_CONSECUTIVE_POINTS = 3` (configurable). This is a standard practice in
electrophysiology event detection.  
**Test:** Add unit tests with synthetic spike (1 point above threshold) that should NOT trigger,
and sustained crossing (≥3 points) that should trigger.

#### 2.2 `DROP_SIGMA_THRESHOLD = 3.0` is hardcoded and not user-adjustable  
**Files:** `python-app/skin_analysis/config.py`, `python-app/skin_analysis/gui.py`  
For noisy signals, 2σ may be more appropriate; for very stable baselines, 4σ avoids false triggers.  
**Fix:** Add a "Drop threshold (σ)" `ttk.Spinbox` to the control panel. Pass as a field
in `PlotSettings` and `analyze_signal()`. Keep `3.0` as default.

#### 2.3 Delta capacitance uses hardcoded last-100-points window  
**Files:** `python-app/skin_analysis/analysis.py` (line ~205)  
`final_avg = float(np.nanmean(samples[-100:]))` — 100 points = 10 seconds at 100 Hz.  
The signal may not have stabilized in 10 seconds for slow-response samples.  
**Fix:** Add `config.FINAL_AVG_POINTS = 100` so it is at least named. Better: add a
"Final average window (s)" spinbox in the Advanced section of the GUI, pass as `PlotSettings`
field, and convert to points in `analyze_signal`.

#### 2.4 `DT_SEC = 0.1` assumes 100 Hz sampling — not validated against actual data  
**Files:** `python-app/skin_analysis/analysis.py`, `python-app/skin_analysis/config.py`  
If the instrument records at a different rate, all timing calculations are wrong silently.  
**Fix:** After `read_xlsx_single()`, attempt to read a time column or derive `dt` from row count
and a known experiment duration. If no time column exists, emit a one-time warning that
"DT_SEC assumed to be 0.1 s (100 Hz); verify with instrument settings."

#### 2.5 Fallback search window (`LEGACY_DROP_SEARCH_POINTS = 500`) is arbitrary  
**Files:** `python-app/skin_analysis/analysis.py`, `python-app/skin_analysis/config.py`  
500 points = 50 seconds. This was a "legacy" constant but is never explained or justified.  
**Fix:** Replace with `config.FALLBACK_SEARCH_SEC = 60.0` and compute points dynamically from
`DT_SEC`. Document in config.py why this bound was chosen.

#### 2.6 No outlier rejection in baseline  
**Files:** `python-app/skin_analysis/analysis.py`  
A single artifact spike in the baseline skews `initial_avg` and `sample_std`, inflating/deflating
the threshold. The 3σ mean+std is not robust to outliers.  
**Fix:** Use a trimmed mean (e.g. `scipy.stats.trim_mean` with 5% trim) or median ± MAD for
baseline statistics. Guard with a try/except for the scipy import; fallback to current behavior.

#### 2.7 No logging infrastructure — silent failures are invisible  
**Files:** all modules  
`read_xlsx_single` swallows all exceptions and returns `None`. There is no way to see what failed
without a debugger.  
**Fix:** Add `import logging` at the top of `analysis.py` and `gui.py`. Use `logging.getLogger(__name__)`.
Emit `logger.warning(...)` in all exception handlers.  
In `main.py`, configure `logging.basicConfig(level=logging.INFO, filename="skin_analysis.log")`.

---

## 3. Architecture

### P2 — Maintainability improvements

#### 3.1 `gui.py` (784 lines) conflates view, controller, and state  
**Files:** `python-app/skin_analysis/gui.py`  
The class `RawDataViewerApp` manages widget creation, event handlers, metadata I/O, threading,
plot rendering, and warning dialogs. Any change risks cascading side effects.  
**Recommended refactor:**
- Extract `MetadataController` (owns autosave logic, load/save calls, field ↔ model translation)
- Extract `PlotController` (owns worker thread lifecycle, settings construction)
- Keep `RawDataViewerApp` as a thin orchestrator that wires widgets to controllers
- Do this incrementally — start with `MetadataController` as it is self-contained

#### 3.2 Analysis parameters stored as `StringVar` — type safety lost  
**Files:** `python-app/skin_analysis/gui.py`  
`baseline_duration_var`, `drug_apply_time_var`, etc. are `StringVar`. Parsing happens in
`_get_analysis_timing_settings()` with manual `float()` conversion and error handling.  
**Fix:** Create a typed `GUISettings` dataclass (not frozen) with float fields. Sync with
StringVars via a single `_sync_settings()` method that validates and converts. Avoids
scattered `float(var.get())` calls.

#### 3.3 No caching — same `.xlsx` re-analyzed on every LOAD & PLOT  
**Files:** `python-app/skin_analysis/plotting.py`, `python-app/skin_analysis/analysis.py`  
Re-reading disk and re-running the full analysis on every plot click wastes time for large
experiments.  
**Fix:** Cache `ProcessedSignal` keyed by `(file_path, mtime, analysis_params_hash)`.
Use a module-level `dict` or `functools.lru_cache`. Invalidate when file changes or params change.
This is a significant speedup for overlay mode with multiple experiments.

#### 3.4 User settings not persisted between sessions  
**Files:** `python-app/skin_analysis/config.py`, `python-app/skin_analysis/gui.py`  
Every launch resets: display_mode, overlay_mode, legend_style, show_drop_lines, baseline_duration,
apply_time, apply_tolerance, threshold, metadata panel state.  
**Fix:** Add a `UserSettings` dataclass. On app close (`protocol("WM_DELETE_WINDOW", ...)`),
serialize to `~/.skin_analysis_settings.json`. Load and apply on startup.  
Fields to persist: `root_path`, `recent_paths`, `display_mode`, `overlay_mode`, `legend_style`,
`show_drop_lines`, `baseline_duration_sec`, `drug_apply_time_sec`, `drug_apply_tolerance_sec`,
`baseline_warning_threshold_pct`, `sigma_threshold`, `metadata_panel_expanded`.

#### 3.5 Color cycler state is fragile across overlay plots  
**Files:** `python-app/skin_analysis/gui.py` → `clear_plot` and `_plot_data_apply`  
The `group_color` index is incremented per overlay group but never validated against the number
of palette entries. Multiple sequential overlays on one axis can repeat colors without visual
distinction.  
**Fix:** Move the color assignment into `PlotController`. Track `_overlay_group_count` explicitly.
After `clear_plot()`, reset the counter to 0.

---

## 4. Data / Configuration

#### 4.1 User settings file (prerequisite for §1.1, §1.16, §3.4)  
**Files:** `python-app/skin_analysis/config.py` (new: `python-app/skin_analysis/settings_store.py`)  
Create `settings_store.py` with:
```python
SETTINGS_PATH = Path.home() / ".skin_analysis_settings.json"

def load_user_settings() -> dict: ...
def save_user_settings(data: dict) -> None: ...
```
Use in `gui.py` `__init__` (load) and `_on_close` (save).

#### 4.2 `DATA_COL = "pF - Plot 0"` not validated with a helpful message  
**Files:** `python-app/skin_analysis/analysis.py` → `read_xlsx_single`  
Currently returns `None` silently if the column is missing. The user sees "0 files loaded".  
**Fix:** Log and surface the column name mismatch:  
`"File {name}.xlsx: column 'pF - Plot 0' not found. Available columns: {cols}"`  
Show this in the status bar or warning dialog.

---

## 5. Test Coverage Gaps

#### 5.1 No tests for `gui.py` workflows  
The GUI has no automated tests — all verification is manual.  
**Fix:** Add `tests/test_gui_smoke.py` using `unittest.mock` to patch `tk.Tk` and validate
that `RawDataViewerApp.__init__` completes without error, that `plot_data()` with a mock
`build_plot_payload` completes the thread cycle, and that `export_plot()` calls `savefig`.

#### 5.2 No regression test for silent `None` return from failed file loads  
**Fix:** In `test_analysis.py`, add a test for `process_single_file` with a non-existent path
and a file missing the `DATA_COL` column. Assert result is `None` and (after §2.7) that a
warning was logged.

#### 5.3 `test_parity_cases.py` only covers 1 aggregate test  
**Fix:** Expand `shared/parity_cases.json` to include edge cases:
- Signal with no threshold crossing (fallback should activate)
- Baseline shorter than `baseline_duration_sec` (auto-shorten path)
- All-constant signal (std = 0, should not divide by zero)
- File with extra/irrelevant columns (should still load correctly)

---

## Summary Priority Table

| # | Item | Priority | Files | Effort |
|---|------|----------|-------|--------|
| 1.1 | Fix hardcoded macOS path | P0 | config.py | Small |
| 1.2 | Progress bar during loading | P0 | gui.py | Small |
| 1.3 | Modal warning dialog | P0 | gui.py | Tiny |
| 2.7 | Add logging infrastructure | P1 | all | Small |
| 1.4 | Status bar | P1 | gui.py | Small |
| 1.5 | Spinbox float formatting | P1 | gui.py | Tiny |
| 1.6 | Legend position control | P1 | gui.py, plotting.py, models.py | Small |
| 1.8 | SVG/PDF export | P1 | gui.py | Tiny |
| 1.9 | Tooltips on controls | P1 | gui.py | Small |
| 2.1 | Consecutive-point crossing | P1 | analysis.py, config.py | Small |
| 2.2 | Adjustable sigma threshold | P1 | gui.py, config.py, models.py, analysis.py | Small |
| 3.4 | Persist user settings | P2 | config.py, gui.py, new settings_store.py | Medium |
| 1.12 | Folder search/filter | P2 | gui.py | Small |
| 1.16 | Recent paths history | P2 | gui.py, config.py | Small |
| 1.7 | Remove individual traces | P2 | gui.py | Medium |
| 3.3 | Cache processed signals | P2 | plotting.py, analysis.py | Medium |
| 3.1 | Refactor gui.py → MVC | P2 | gui.py | Large |
| 1.10 | Language consistency (i18n) | P2 | config.py, plotting.py | Small |
| 2.4 | Validate DT_SEC assumption | P2 | analysis.py | Small |
| 5.1 | GUI smoke tests | P3 | tests/ | Medium |
| 5.3 | Expand parity test cases | P3 | shared/, tests/ | Small |
