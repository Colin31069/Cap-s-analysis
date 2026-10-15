# Parallel Migration Rules

## CAP-S product boundary

The dedicated CAP-S mean-curve and SD/SEM error-band product lives in `cap-s-studio/`, with its own `cap_s` Python package, launcher, Tk interface, build spec, and `releases/cap-s/` delivery directory. Its default band is SEM. Keep its interface focused on data groups, curve settings, and image/CSV export. It is not the Skin Analysis Tauri migration described below; do not package `desktop-tauri/` as the CAP-S product. Windows CAP-S packaging is deferred until a native Windows build environment is available, as requested by the user.

This repository now contains two maintained desktop implementations:

- Python reference app in `Python version/`
- Rust/Tauri app in `desktop-tauri/`

## Maintenance Policy

- Keep the Python version runnable from `Python version/main.py`.
- Keep the Tauri version isolated inside `desktop-tauri/`.
- Do not move or delete the current Python package while the migration is in progress.
- Treat both versions as active products until the team explicitly retires one of them.

## Sync Rules

- If a change affects user-visible behavior, update both versions in the same branch.
- If a bug exists in both implementations, fix both implementations together.
- If a change is specific to Tauri packaging, frontend rendering, or Rust tooling, limit it to `desktop-tauri/`.
- If a change is specific to Tkinter, Matplotlib, or Python environment issues, limit it to the existing Python app.

## Shared Behavior Contract

Both versions must continue to honor the same core behavior unless a deliberate migration decision says otherwise:

- Three-level folder selection under the chosen root path
- `.xlsx` input files only
- Required Excel column: `pF - Plot 0`
- Display modes: `Norm`, `Raw`, and `Base`
- Overlay plotting, group-color plotting, drop lines, legend customization, and PNG export

## Testing Expectations

- Keep non-GUI logic covered by automated tests in both implementations.
- Use the shared parity cases in `shared/parity_cases.json` when validating equivalent analysis behavior.
- Run version-specific smoke tests before switching primary usage from Python to Tauri.
