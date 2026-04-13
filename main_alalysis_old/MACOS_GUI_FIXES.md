# macOS Tkinter GUI recovery

This project uses `tkinter` + `ttk` + embedded `matplotlib` (`TkAgg`). On macOS, older Tk builds can cause:

- `ttk.Combobox` not opening or not accepting a selection
- `Checkbutton` / `Radiobutton` not toggling
- focus staying on the canvas instead of the control panel

## Recommended setup

1. Install a newer Python on macOS, preferably Python 3.12 or newer.
2. Create a dedicated GUI environment:

```bash
chmod +x ./setup_macos_gui_env.sh
./setup_macos_gui_env.sh
```

3. Activate the environment and run the smoke test:

```bash
source ./.venv-gui/bin/activate
python ./tk_macos_smoke_test.py
```

If the smoke test still cannot open the dropdown or toggle options, the problem is your local Tk/macOS runtime, not the app logic.

## App-side mitigations already added

- Separate frame for `NavigationToolbar2Tk`
- Initial focus pushed to the first combobox
- Explicit combobox compatibility mode on macOS
- UI state recovery after plotting success/failure

## Main app run

```bash
source ./.venv-gui/bin/activate
python ./alalysis拷貝.py
```
