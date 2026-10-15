# CHANGELOG

Append-only record of AI agent changes for this workspace.

## 2026-10-14 20:48 +08:00

- Summary: Expanded the teacher-facing analysis method guide with end-to-end and statistical flowcharts, exact calculation formulas, a worked example, and explicit trustworthiness limits; linked it from the README.
- Files: `ANALYSIS_METHOD.md`, `README.md`, `CHANGELOG.md`
- Verification: Cross-checked documented behavior against the Python analysis, plotting, statistics, configuration, exclusion code, and existing tests; `rtk git diff --check` (pass); no tests run because this was a documentation-only change.

## 2026-05-14 17:59 +08:00

- Summary: Added macOS Tauri packaging support with `.app`/`.dmg` build scripts, host-native bundle defaults, macOS icon assets, and packaging documentation.
- Files: `desktop-tauri/package.json`, `desktop-tauri/scripts/build-macos.mjs`, `desktop-tauri/src-tauri/tauri.conf.json`, `desktop-tauri/src-tauri/icons/*`, `desktop-tauri/README.md`, `README.md`, `CHANGELOG.md`
- Verification: `cd "desktop-tauri" && npm run build` (pass; existing Svelte label accessibility warnings remain); `cd "desktop-tauri/src-tauri" && cargo test` (pass; 23 unit tests + 1 parity integration test); `cd "desktop-tauri" && npm run tauri:build:exe:cached` (pass; Tauri config/icons accepted, release exe built); `cd "desktop-tauri" && node scripts/build-macos.mjs` on Windows returned the expected macOS-host guard. Real `.app`/`.dmg` output still requires running `npm run tauri:build:mac` on macOS.

## 2026-05-12 16:44 +08:00

- Summary: 打包 Tauri edition — 產生 Windows NSIS 安裝程式 `Skin Analysis Desktop_0.1.0_x64-setup.exe`（3.7 MB）。
- Files: `desktop-tauri/src-tauri/target/release/bundle/nsis/Skin Analysis Desktop_0.1.0_x64-setup.exe`（產物，未納入 git）
- Verification: `npm run tauri:build` exit 0；Vite build 2.06s；Rust release compile 46.28s；NSIS packager 完成。

## 2026-05-12 +08:00

- Summary: 清理打包臃腫問題——刪除 Codex 產生的 vendor/ 離線快取、還原 Cargo registry 設定、清除 debug 編譯產物，釋出約 8 GB 磁碟空間。
- Files: `desktop-tauri/.gitignore`, `desktop-tauri/src-tauri/.cargo/config.toml`（刪除）, `desktop-tauri/src-tauri/vendor/`（刪除）, `desktop-tauri/src-tauri/target/debug/`（刪除）
- Verification: `npm run tauri:build` — release 快取（2.78 GB）保留，下次打包為增量編譯。

## 2026-05-08 15:34 +08:00

- Summary: Ignored the local `.claudeskill/` folder so it is excluded from Git commits.
- Files: `.gitignore`, `CHANGELOG.md`
- Verification: `git status --short` (confirmed `.claudeskill/` is no longer listed as an untracked folder); `git diff --check` (pass; Windows line-ending warnings only).

## 2026-05-08 15:25 +08:00

- Summary: Made the Tauri n<5 Sample Exclusion warning more prominent with red bold text and added hover-only warnings on Exclude Selected, Restore Selected, and Run Dixon Q Review explaining that fewer than 5 samples cannot use Dixon Q or data exclusion.
- Files: `desktop-tauri/src/App.svelte`, `CHANGELOG.md`
- Verification: `cd "desktop-tauri" && npm run build` (pass; existing Svelte label accessibility warnings and Rollup chunk-size warning remain).

## 2026-05-08 14:46 +08:00

- Summary: Updated the Tauri Sample Exclusion panel so experiment folders with fewer than 5 `.xlsx` samples clearly warn that the data count is too low for exclusion. Exclude Selected and Dixon Q Review are disabled for n<5, and direct exclusion attempts report the same rule.
- Files: `desktop-tauri/src/App.svelte`, `CHANGELOG.md`
- Verification: `cd "desktop-tauri" && npm run build` (pass; existing Svelte label accessibility warnings and Rollup chunk-size warning remain).

## 2026-05-08 10:22 +08:00

- Summary: Added a Python-style selected Excel sample exclusion control to the Tauri frontend. The Sample Exclusion panel now shows a selectable `.xlsx` list with `[IN]` / `[OUT]` status and dedicated `Exclude Selected` / `Restore Selected` buttons while preserving the existing metadata-backed exclusion behavior.
- Files: `desktop-tauri/src/App.svelte`, `CHANGELOG.md`
- Verification: `cd "desktop-tauri" && npm run build` (pass; existing Svelte label accessibility warnings and Rollup chunk-size warning remain).

## 2026-05-08 10:18 +08:00

- Summary: Added a first-launch Tauri theme picker with Light, Dark, and Follow OS choices, persisted the selection locally, and updated Plotly colors to follow the active theme.
- Files: `desktop-tauri/src/App.svelte`, `desktop-tauri/src/lib/plot.ts`, `desktop-tauri/src-tauri/capabilities/default.json`, `desktop-tauri/src-tauri/gen/schemas/capabilities.json`, `CHANGELOG.md`
- Verification: `cd "desktop-tauri" && npm run build` (pass; existing Svelte accessibility/CSS warnings and Rollup chunk-size warning remain); `cd "desktop-tauri/src-tauri" && cargo test` (pass; 23 unit tests + 1 parity integration test).

## 2026-05-07 Asia/Taipei (update 2)

- Summary: Added light/dark theme toggle to Tauri/Svelte frontend. Sun icon (switch to light) / Moon icon (switch to dark) button in sidebar header. Plotly chart re-renders with theme-matched colors on toggle. Light theme uses slate-blue surfaces (#F1F5F9 bg, #FFFFFF cards) with dark green accent (#16A34A) and dark text (#0F172A). No application logic changes.
- Files: `desktop-tauri/src/App.svelte`, `desktop-tauri/src/lib/plot.ts`
- Verification: Visual-only changes; all TypeScript bindings and Svelte reactive variables untouched.

## 2026-05-07 Asia/Taipei

- Summary: Complete dark-mode UI redesign for Tauri/Svelte frontend using ui-ux-pro-max skill. Applied Developer Tool / IDE dark color palette (#0B1120 background, #22C55E green accent). Redesigned sidebar as a proper panel system with pinned action footer, chevron collapsibles, styled radio/checkbox groups with active highlighting, sample dot indicators (green=included, red=excluded), glow-effect primary CTA button, spinner for busy state, and slim status bar with semantic dot indicator. Updated Plotly chart theme to dark (navy background, slate grid lines, muted labels). All application logic preserved without changes.
- Files: `desktop-tauri/src/App.svelte`, `desktop-tauri/src/app.css`, `desktop-tauri/src/lib/plot.ts`
- Verification: No logic changes — all TypeScript bindings and Svelte reactive variables untouched; visual-only.

## 2026-05-06 Asia/Taipei

- Summary: Ported all Python-version features to the Tauri version: configurable timing parameters, apply-window drop detection, baseline accuracy warnings, drop-aligned time axis (t=0 at drop), metadata persistence (.skin_analysis_metadata.json), sample exclusion system with Dixon Q exception, group statistics + one-way ANOVA + Brown-Forsythe variance check + Dixon Q10 review + robust outlier (MAD) review + CSV export, overlay group legend with medicine summary, medicine metadata UI, timing parameters UI, statistics panel. Also added Tauri version usage section to README.md.
- Files: `desktop-tauri/src-tauri/Cargo.toml`, `desktop-tauri/src-tauri/src/config.rs`, `desktop-tauri/src-tauri/src/models.rs`, `desktop-tauri/src-tauri/src/analysis.rs`, `desktop-tauri/src-tauri/src/metadata.rs` (new), `desktop-tauri/src-tauri/src/exclusions.rs` (new), `desktop-tauri/src-tauri/src/statistics.rs` (new), `desktop-tauri/src-tauri/src/plotting.rs`, `desktop-tauri/src-tauri/src/commands.rs`, `desktop-tauri/src-tauri/src/lib.rs`, `desktop-tauri/src/lib/types.ts`, `desktop-tauri/src/lib/api.ts`, `desktop-tauri/src/lib/plot.ts`, `desktop-tauri/src/App.svelte`, `README.md`
- Verification: `cd desktop-tauri/src-tauri && cargo test` → 25 tests pass (23 unit + 1 parity integration + 0 doc); 0 failures.
- Follow-up fixes: created `desktop-tauri/src-tauri/icons/icon.ico` (required by tauri-build on Windows), fixed `tests/parity_cases.rs` to pass `&AnalysisParams::default()` to `process_single_file`, removed unused `fmt_float` helper in `statistics.rs`, removed stale `INITIAL_BASELINE_POINTS` import in `plotting.rs`.

## 2026-05-05 16:16 +08:00

- Summary: Simplified grouped overlay legends to one enlarged color swatch per concentration group instead of per-sample line-style entries.
- Files: `Python version/skin_analysis/plotting.py`, `Python version/skin_analysis/gui.py`, `Python version/tests/test_plotting.py`, `README.md`, `CHANGELOG.md`
- Verification: `cd "Python version" && ./.venv-gui/bin/python -m unittest tests.test_plotting` (pass); `cd "Python version" && ./.venv-gui/bin/python -m unittest discover` (pass; SciPy emitted an expected Shapiro warning for identical test data); `cd "Python version" && ./.venv-gui/bin/python -m py_compile main.py skin_analysis/*.py` (pass)

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

## 2026-05-04 19:36 +08:00

- Summary: Made the Python launcher recover from dependency mismatches when possible, block the macOS 15 + Python 3.11 Tk crash path before AppKit aborts, and document the required Python 3.12+ GUI runtime.
- Files: `Python version/main.py`, `Python version/skin_analysis/launcher.py`, `Python version/setup_macos_gui_env.sh`, `README.md`, `MACOS_GUI_FIXES.md`, `CHANGELOG.md`
- Verification: `cd "Python version" && python3 main.py` (blocked safely with Python 3.12+ instructions instead of crashing); `cd "Python version" && ./setup_macos_gui_env.sh` (blocked safely because only Python 3.11 is installed on macOS 15.7.4); `cd "Python version" && python3 -m py_compile main.py skin_analysis/*.py` (pass); `cd "Python version" && .venv-gui/bin/python -m unittest discover` (pass; existing `.pth` and Matplotlib cache warnings)

## 2026-05-04 19:59 +08:00

- Summary: Added missing Tkinter detection for Homebrew Python 3.13, updated setup guidance to require the matching `python-tk@3.13` package, and pointed Matplotlib cache writes at a writable temp directory.
- Files: `Python version/skin_analysis/__init__.py`, `Python version/skin_analysis/launcher.py`, `Python version/setup_macos_gui_env.sh`, `README.md`, `MACOS_GUI_FIXES.md`, `CHANGELOG.md`
- Verification: `brew install python-tk@3.13` (installed `python-tk@3.13`, `tcl-tk`, and `libtommath`); `cd "Python version" && rm -rf .venv-gui && ./setup_macos_gui_env.sh` (rebuilt Python 3.13 GUI environment); `cd "Python version" && ./.venv-gui/bin/python -c 'import tkinter; print(tkinter.TkVersion)'` (Tk 9.0); `cd "Python version" && ./.venv-gui/bin/python -m py_compile main.py skin_analysis/*.py` (pass); `cd "Python version" && ./.venv-gui/bin/python -m unittest discover` (pass); `cd "Python version" && ./.venv-gui/bin/python -c 'import tkinter; from skin_analysis.gui import RawDataViewerApp; print("gui import ok")'` (pass); `git diff --check` (pass)

## 2026-05-04 21:10 +08:00

- Summary: Added manual sample exclusion with a 20% floor cap, saved exclusion reasons in metadata, and made plotting/statistics skip excluded `.xlsx` files while reporting exclusions.
- Files: `Python version/skin_analysis/models.py`, `Python version/skin_analysis/exclusions.py`, `Python version/skin_analysis/metadata.py`, `Python version/skin_analysis/plotting.py`, `Python version/skin_analysis/statistics.py`, `Python version/skin_analysis/gui.py`, `Python version/tests/test_exclusions.py`, `Python version/tests/test_metadata.py`, `Python version/tests/test_plotting.py`, `Python version/tests/test_statistics.py`, `README.md`, `ANALYSIS_METHOD.md`, `CHANGELOG.md`
- Verification: `cd "Python version" && python3 -m unittest discover` (fails in global Python because the existing NumPy 2.4.4 environment is ABI-incompatible with installed pandas/Matplotlib); `cd "Python version" && ./.venv-gui/bin/python -m unittest discover` (pass; SciPy emitted an expected Shapiro warning for identical test data); `cd "Python version" && python3 -m py_compile main.py skin_analysis/*.py` (pass); `cd "Python version" && ./.venv-gui/bin/python -m py_compile main.py skin_analysis/*.py` (pass); `git diff --check` (pass)

## 2026-05-04 23:22 +08:00

- Summary: Added robust Delta % outlier review that flags candidate samples with leave-one-out median/MAD modified z-scores without automatically excluding them.
- Files: `Python version/skin_analysis/config.py`, `Python version/skin_analysis/models.py`, `Python version/skin_analysis/statistics.py`, `Python version/skin_analysis/gui.py`, `Python version/tests/test_statistics.py`, `README.md`, `ANALYSIS_METHOD.md`, `CHANGELOG.md`
- Verification: `cd "Python version" && ./.venv-gui/bin/python -m unittest tests.test_statistics` (pass; SciPy emitted an expected Shapiro warning for identical test data); `cd "Python version" && ./.venv-gui/bin/python -m unittest discover` (pass; SciPy emitted an expected Shapiro warning for identical test data); `cd "Python version" && ./.venv-gui/bin/python -m py_compile main.py skin_analysis/*.py` (pass); `git diff --check` (pass)

## 2026-05-04 23:54 +08:00

- Summary: Added Dixon Q10 recommended exclusions, Dixon-backed small-n exclusion metadata, ANOVA sensitivity reporting, and a Sample Exclusion button for running Dixon Q on the selected experiment folder.
- Files: `Python version/skin_analysis/config.py`, `Python version/skin_analysis/models.py`, `Python version/skin_analysis/metadata.py`, `Python version/skin_analysis/exclusions.py`, `Python version/skin_analysis/statistics.py`, `Python version/skin_analysis/gui.py`, `Python version/tests/test_exclusions.py`, `Python version/tests/test_metadata.py`, `Python version/tests/test_statistics.py`, `README.md`, `ANALYSIS_METHOD.md`, `CHANGELOG.md`
- Verification: `cd "Python version" && ./.venv-gui/bin/python -m unittest tests.test_statistics tests.test_metadata tests.test_exclusions` (pass; SciPy emitted an expected Shapiro warning for identical test data); `cd "Python version" && ./.venv-gui/bin/python -m unittest discover` (pass; SciPy emitted an expected Shapiro warning for identical test data); `cd "Python version" && ./.venv-gui/bin/python -m py_compile main.py skin_analysis/*.py` (pass); `git diff --check` (pass)

## 2026-05-07 09:28 +08:00

- Summary: Fixed the Tauri Svelte sample exclusion button disabled expression so Vite can parse the app and restore buttons remain available at the exclusion cap.
- Files: `desktop-tauri/src/App.svelte`, `CHANGELOG.md`
- Verification: `cd "desktop-tauri" && npm run build` (pass; existing Svelte accessibility/CSS warnings and Rollup chunk-size warning remain).

## 2026-05-07 09:38 +08:00

- Summary: Updated the Tauri edition to match the Python edition's current experiment-folder layout: the root path now lists direct experiment folders, plotting/sample metadata read `root/experiment`, and statistics scan every direct child folder under the selected root.
- Files: `desktop-tauri/src/App.svelte`, `desktop-tauri/src/lib/api.ts`, `desktop-tauri/src/lib/types.ts`, `desktop-tauri/src-tauri/src/commands.rs`, `desktop-tauri/src-tauri/src/lib.rs`, `desktop-tauri/src-tauri/src/models.rs`, `desktop-tauri/src-tauri/src/plotting.rs`, `README.md`, `CHANGELOG.md`
- Verification: `cd "desktop-tauri" && npm run build` (pass; existing Svelte accessibility/CSS warnings and Rollup chunk-size warning remain); `cd "desktop-tauri/src-tauri" && cargo test` (pass; 23 unit tests + 1 parity integration test).

## 2026-05-08 17:16 +08:00

- Summary: Optimized the Tauri edition startup path by moving Plotly out of the initial Vite/Rollup bundle and loading the local vendor asset only when a plot is first rendered or exported.
- Files: `.gitignore`, `desktop-tauri/package.json`, `desktop-tauri/scripts/sync-plotly-vendor.mjs`, `desktop-tauri/src/App.svelte`, `desktop-tauri/src/lib/plotly.ts`, `desktop-tauri/src/vite-env.d.ts`, `desktop-tauri/README.md`, `CHANGELOG.md`
- Verification: `cd "desktop-tauri" && npm run build` (pass in 10.75s; existing Svelte accessibility warnings remain); `cd "desktop-tauri/src-tauri" && cargo test` (pass in 63.19s); `npm run dev -- --host 127.0.0.1` reached Vite ready in 4.29s; `git diff --check` (pass; line-ending warnings only).

## 2026-05-08 18:21 +08:00

- Summary: Added Tauri packaging dependency preparation scripts for local npm/Cargo cache warmup and optional project-local Cargo vendoring, plus faster Windows release build commands.
- Files: `.gitignore`, `desktop-tauri/package.json`, `desktop-tauri/scripts/prepare-build-deps.mjs`, `desktop-tauri/scripts/vendor-cargo-deps.mjs`, `desktop-tauri/src-tauri/Cargo.toml`, `desktop-tauri/src-tauri/tauri.conf.json`, `desktop-tauri/README.md`, `CHANGELOG.md`
- Verification: `cd "desktop-tauri" && npm run deps:prepare` (pass; npm packages, Plotly vendor asset, and Cargo crates available locally); `cd "desktop-tauri" && npm run deps:vendor -- --refresh` (pass; generated local `src-tauri/vendor/` mirror); `cd "desktop-tauri/src-tauri" && cargo fetch --locked --offline` (pass); `cd "desktop-tauri" && npm run tauri:build:exe` (pass in 584.51s after release profile/cache change); `cd "desktop-tauri" && npm run tauri:build:exe` second run (pass in 122.97s); `cd "desktop-tauri" && npm run tauri:build:exe:cached` (pass in 64.74s).

## 2026-05-08 17:28 +08:00

- Summary: Added plot grid visibility toggles to both the Python Tkinter app and the Tauri Plotly edition.
- Files: `Python version/skin_analysis/gui.py`, `desktop-tauri/src/App.svelte`, `desktop-tauri/src/lib/plot.ts`, `README.md`, `CHANGELOG.md`
- Verification: `cd "Python version" && python -m unittest discover` (pass); `cd "Python version" && python -m py_compile main.py skin_analysis/*.py` (initial PowerShell wildcard form failed with invalid argument); `cd "Python version" && python -m py_compile main.py skin_analysis/*.py` equivalent using PowerShell-expanded file list (pass); `cd "desktop-tauri" && npm run build` (pass; existing Svelte accessibility warnings remain); `git diff --check` (pass; line-ending warnings only).


## 2026-10-15 15:04 +08:00 (Asia/Taipei)

- Summary: Produced distributable Tauri desktop installers for macOS Universal 2 and Windows x64 with offline WebView2; added platform packaging, release instructions, SHA-256 manifests, and separate temporary build caches. Fixed PNG/CSV export permissions and moved blocking save dialogs off the UI thread after packaged-app smoke testing exposed a freeze. Kept raw macOS app staging outside File Provider folders so generated FinderInfo metadata cannot contaminate delivered app archives.
- Files: `.gitignore`, `README.md`, `desktop-tauri/README.md`, `desktop-tauri/WINDOWS_DISTRIBUTION.md`, `desktop-tauri/package.json`, `desktop-tauri/scripts/build-macos.mjs`, `desktop-tauri/scripts/build-windows.mjs`, `desktop-tauri/src-tauri/tauri.macos.conf.json`, `desktop-tauri/src-tauri/tauri.windows.conf.json`, `desktop-tauri/src-tauri/Cargo.toml`, `desktop-tauri/src-tauri/capabilities/default.json`, `desktop-tauri/src-tauri/gen/schemas/capabilities.json`, `desktop-tauri/src-tauri/src/commands.rs`, `CHANGELOG.md`; generated delivery artifacts and manifests under ignored `releases/0.1.0/`.
- Verification: `npm ci --prefer-offline --no-audit --fund=false` and `npm run build` (pass; existing Svelte label accessibility warnings); `cargo test --locked --offline` (25 unit tests + 1 Excel parity integration test pass); `node --check scripts/build-macos.mjs` and `node --check scripts/build-windows.mjs` (pass); `npm run tauri:build:mac:universal -- --cached` (pass); `npm run tauri:build:win:cached` (pass after task-local LLVM/NSIS path setup; missing CRT PDB warnings concern debug information only); macOS `lipo`, `vtool`, `otool`, strict `codesign`, DMG mount/layout, ZIP extraction, and SHA-256 verification (pass); native packaged macOS app loaded 3 Excel traces, rendered bundled Plotly, exported a 3600x2000 PNG and a statistics CSV (pass); `7zz t`/extraction of Windows NSIS installer (pass, 8 files), x64 PE and embedded runtime hash verification (pass); `git diff --check` (pass).
- Limits: Windows setup has not been installed or executed on Windows; Intel/older macOS runtime behavior was not exercised. macOS is ad-hoc signed and not notarized; Windows is unsigned. The installers may show OS security/publisher prompts on recipient machines.

## 2026-10-15 16:06 +08:00 (Asia/Taipei)

- Summary: Corrected the product mix-up: recovered the saved lightweight error-band application and separated it into `cap-s-studio/` with the `cap_s` package, CAP-S Studio branding, a dedicated launcher, and SEM selected by default. Removed legacy GUI/statistical entrypoints from the new product while preserving the saved signal and error-band calculations. Produced native Apple Silicon DMG/ZIP plus a source ZIP. The user explicitly chose Python/Tk and deferred Windows packaging until a native Windows environment is available.
- Files: new `cap-s-studio/main.py`, `cap-s-studio/cap_s/*.py`, `cap-s-studio/tests/*.py`, `cap-s-studio/cap_s.spec`, `cap-s-studio/build_portable.py`, `cap-s-studio/build_windows.bat`, `cap-s-studio/run_macos.command`, `cap-s-studio/run_windows.bat`, `cap-s-studio/create_demo_data.py`, `cap-s-studio/requirements-error-band.txt`, `cap-s-studio/README_PORTABLE.md`, `cap-s-studio/ANALYSIS_METHOD.md`; additive product notices in root `README.md`, `ANALYSIS_METHOD.md`, `MIGRATION_RULES.md`; `CHANGELOG.md`. Generated artifacts, checksums, manifest and validation report under ignored `releases/cap-s/1.0.0/`; marked old `releases/0.1.0/` as Skin Analysis, not CAP-S.
- Verification: GUI virtualenv Python `-m unittest discover -q` in `cap-s-studio` (58 passed); `build_portable.py` (pass); saved branch analysis byte comparison and six plotting helper AST comparisons (pass); source ZIP module equality and 20 synthetic Excel samples (pass); PyInstaller archive product/dependency checks (pass); four synthetic groups with n=5, SEM formula, PNG/PDF/SVG export and 16,988-row CSV bounds (pass); DMG read-only mount, Applications link, arm64 executable, strict deep `codesign --verify` and delivery SHA-256 checks (pass).
- Limits: Packaged app opened the dedicated CAP-S interface with SEM selected; full GUI click-through/save dialogs remain unverified because UI automation returned window lookup/coordinate errors. Helper-level exports passed independently. Mac package is arm64 only, ad-hoc signed and not notarized; Intel/other macOS versions were not exercised. No CAP-S Windows EXE is claimed or delivered.

## 2026-10-15 16:14 +08:00 (Asia/Taipei)

- Summary: Extended CAP-S folder discovery from direct child folders to the selected root and up to three child-directory levels. Each directory containing Excel files remains a separate experiment, identified by its relative path; selecting a folder that directly contains Excel now also works. Directory symlinks are not followed. Scan permission failures display a warning before replacing the current group list. Rebuilt the native Mac distribution as 1.0.1.
- Files: `cap-s-studio/cap_s/filesystem.py`, `cap-s-studio/cap_s/gui.py`, `cap-s-studio/build_portable.py`, `cap-s-studio/cap_s.spec`, `cap-s-studio/build_windows.bat`, `cap-s-studio/README_PORTABLE.md`, `cap-s-studio/ANALYSIS_METHOD.md`, `README.md`, `CHANGELOG.md`; generated DMG, ZIP, source ZIP, SHA-256 manifest and delivery notes under ignored `releases/cap-s/1.0.1/`.
- Verification: `rtk proxy env XDG_CACHE_HOME=/private/tmp/cap-s-python-build/font-cache "../Python version/.venv-gui/bin/python" build_portable.py` from `cap-s-studio` (pass; produced arm64 DMG/ZIP and source ZIP, including the builder's strict deep ad-hoc signature checks). Reviewed discovery depth and relative-path flow through existing plotting/metadata readers. No automated tests or GUI click-through were run for this change.
- Limits / suggested manual check: The user's OneDrive `Dropping/20260606/pbs` directory returned macOS `Operation not permitted`, including outside the shell sandbox, so its actual layout/data could not be inspected. In 1.0.1, select `Dropping` and confirm `20260606/pbs` or its Excel-containing third-level child groups appear separately; select `pbs` directly to load any Excel files in that folder. Fourth-level folders require selecting a closer root. Mac remains Apple Silicon only and not notarized; Windows packaging remains deferred.

## 2026-10-15 16:25 +08:00 (Asia/Taipei)

- Summary: Renamed the window, page heading and Mac display name to `Cap-s data analysis`. Replaced the all-at-once sidebar with a three-step flow: select a folder, select groups, then plot/export. Only the current step is displayed. Empty folders cannot advance; at least one selected group is required for step three. Added back navigation and current-step highlighting. Export controls, plot toolbar and analysis details appear after analysis; data/selection/analysis changes hide stale previews and exports until replotting.
- Files: `cap-s-studio/cap_s/gui.py`, `cap-s-studio/cap_s.spec`, `cap-s-studio/build_portable.py`, `cap-s-studio/build_windows.bat`, `cap-s-studio/README_PORTABLE.md`, `README.md`, `CHANGELOG.md`; generated native Mac and source distributions under ignored `releases/cap-s/1.0.2/`.
- Verification: Rebuilt with `rtk proxy env XDG_CACHE_HOME=/private/tmp/cap-s-python-build/font-cache "../Python version/.venv-gui/bin/python" build_portable.py` from `cap-s-studio`; the build includes strict deep ad-hoc signature checks. Reviewed step transitions, empty/all-unselected guards, busy navigation, and stale-export handling. No automated tests or manual GUI click-through were run for this change.
- Risks / suggested manual checks: Confirm initial view contains only folder selection; cancel/invalid/empty folder stays at step one; valid folders advance to group selection; all-unselected disables Next; Back preserves the workflow; step three shows graph settings, and exports appear only for a completed plot. Changing groups then returning to step three must require replotting. Native distribution remains Apple Silicon only and not notarized; Windows remains deferred.

## 2026-10-15 16:41 +08:00 (Asia/Taipei)

- Summary: Added queued per-file analysis progress, elapsed time, waiting hints, safe cooperative cancellation, and per-file read/signal-processing timing details. Added a bounded 64 MiB memory cache keyed by file identity metadata to avoid rereading unchanged Excel values; failed/unstable reads are not cached. Read actual worksheet XML rows rather than trusting an inflated saved range. Replaced automatic legend-position searching with a fixed, configurable position. Added a post-plot color/legend editor, 16 default colors, position/column/font controls and draggable legends; visual changes redraw the current result without reading Excel.
- Files: `cap-s-studio/cap_s/analysis.py`, `cap-s-studio/cap_s/plotting.py`, `cap-s-studio/cap_s/models.py`, `cap-s-studio/cap_s/gui.py`, `cap-s-studio/cap_s.spec`, `cap-s-studio/build_portable.py`, `cap-s-studio/build_windows.bat`, `cap-s-studio/README_PORTABLE.md`, `cap-s-studio/ANALYSIS_METHOD.md`, `README.md`, `CHANGELOG.md`; generated delivery artifacts under ignored `releases/cap-s/1.0.3/`.
- Verification: Inspected installed Matplotlib legend implementation/defaults to confirm the prior `best` position searches curve geometry; reviewed installed openpyxl read-only iteration for missing-row preservation. `rtk proxy env XDG_CACHE_HOME=/private/tmp/cap-s-python-build/font-cache "../Python version/.venv-gui/bin/python" build_portable.py` from `cap-s-studio` (pass; native arm64 DMG/ZIP and source ZIP, including strict deep ad-hoc signature checks). No automated tests, performance benchmarks or GUI click-through were run for this change.
- Risks / suggested manual checks: Cloud synchronization is a possible contributor, not an established root cause; compare the same data locally and in the cloud using the new timing details. Cancellation cannot interrupt an operating-system call that is blocked opening/reading a file; it takes effect after that call returns. Verify progress/Cancel responsiveness, unchanged-file reuse and changed-file invalidation, independent group colors, legend positions and exported images. Dragged legend placement is preserved in direct image exports but resets to configured placement on the next redraw. Scientific formulas, common-time intersections, exclusion handling and n remain unchanged. Mac distribution remains Apple Silicon only and not notarized; Windows remains deferred.

## 2026-10-15 16:52 +08:00 (Asia/Taipei)

- Summary: Prepared 1.0.4 with optional Mean ± SEM/SD annotation and same-parent coloring, both off by default. Added separate individual/shared color selections and reset behavior. The user interrupted delivery to discuss grouping rules; this intermediate version is superseded by 1.0.5 below.
- Files: `cap-s-studio/cap_s/models.py`, `cap-s-studio/cap_s/plotting.py`, `cap-s-studio/cap_s/gui.py`, `cap-s-studio/build_portable.py`, `cap-s-studio/cap_s.spec`, `cap-s-studio/build_windows.bat`, `cap-s-studio/README_PORTABLE.md`, `cap-s-studio/ANALYSIS_METHOD.md`, `README.md`, `CHANGELOG.md`; intermediate generated files in ignored `releases/cap-s/1.0.4/`.
- Verification: `build_portable.py` completed successfully with the existing GUI virtualenv Python and strict deep ad-hoc signature checks. No automated tests or GUI click-through were run.

## 2026-10-15 17:00 +08:00 (Asia/Taipei)

- Summary: Implemented the user's confirmed grouping rules in 1.0.5: optional same-color groups use either the Excel-containing folder name or its parent folder name. The appearance dialog previews each curve's color group and enables the grouping choice only when shared coloring is on. Matching names across paths share colors, with no unit parsing or conversion. Individual, folder-name and parent-name custom palettes are retained separately. Mean ± SEM/SD annotation and shared coloring both default off; underlying curves, error bands and scientific groups remain independent.
- Files: `cap-s-studio/cap_s/models.py`, `cap-s-studio/cap_s/plotting.py`, `cap-s-studio/cap_s/gui.py`, `cap-s-studio/build_portable.py`, `cap-s-studio/cap_s.spec`, `cap-s-studio/build_windows.bat`, `cap-s-studio/README_PORTABLE.md`, `cap-s-studio/ANALYSIS_METHOD.md`, `README.md`, `CHANGELOG.md`; generated native Mac and source packages under ignored `releases/cap-s/1.0.5/`.
- Verification: `rtk proxy env XDG_CACHE_HOME=/private/tmp/cap-s-python-build/font-cache "../Python version/.venv-gui/bin/python" build_portable.py` from `cap-s-studio` (pass; arm64 DMG/ZIP and source ZIP, including strict deep ad-hoc signature checks). Reviewed all color resolver callers, root-folder handling, preview/update paths, independent palette retention and reset defaults. No automated tests or GUI click-through were run for this change.
- Risks / suggested manual checks: For `1%/2 micro L`, `1%/3 micro L` and `5%/2 micro L`, confirm folder-name mode pairs the two `2 micro L` curves while parent-name mode pairs the two `1%` curves. Repeat with ppm or arbitrary names, switch modes after custom coloring, reset defaults, and export an image. Same names under different dates intentionally share colors; scientific data retain their full relative-path identities. Mac remains Apple Silicon only and not notarized; Windows remains deferred.

## 2026-10-15 17:19 +08:00 (Asia/Taipei)

- Summary: Added a Cap-s data analysis 1.0.5 operating SOP using the prior instrument SOP's cover, section banners, numbered procedure cards, and footer layout.
- Files: `releases/cap-s/1.0.5/SOP0006_Cap-s-Analysis操作SOP.docx`, `CHANGELOG.md`
- Verification: `hdiutil verify releases/cap-s/1.0.5/CapSStudio-macOS-arm64.dmg` (valid); DMG SHA-256 matches `manifest.json`; `section_audit.py` (one US Letter portrait section); `fields_report.py` (PAGE field retained); `render_and_diff.py` completed with 5 pages and all pages visually reviewed in Microsoft Word at 100%; reference SOP SHA-256 unchanged. Final package audit confirmed 20 unchanged parts and only `document.xml`, `styles.xml`, and `footer1.xml` updated as planned.

## 2026-10-15 17:58 +08:00 (Asia/Taipei)

- Summary: Revised the Cap-s data analysis SOP into a screenshot-based, step-by-step draft. Added the two available real interface screenshots and a clearly labeled ExampleData chart illustration; placed the calculation method and limitations in a supplementary section at the end, based on `cap-s-studio/ANALYSIS_METHOD.md`.
- Files: `releases/cap-s/1.0.5/SOP0006_Cap-s-Analysis操作SOP.docx`, `CHANGELOG.md`
- Verification: Rendered the document to eight pages and visually reviewed all rendered pages; checked the latest calculation pages in Microsoft Word at 100%; confirmed the screenshot placeholder count is zero, the prior SOP reference file checksum is unchanged, and the package audit retained the reference template parts outside the planned document/style/footer updates and added embedded images.
- Limits: Only two genuine CapSStudio interface screenshots were available; remaining workflow steps are described in text and no unobserved interface screenshots were fabricated.
