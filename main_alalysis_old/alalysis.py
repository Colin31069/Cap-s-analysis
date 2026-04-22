# raw_data_viewer_v3_4.py
# -*- coding: utf-8 -*-
"""
Raw Data Viewer for Dropping Experiment (v3.4 - Custom Legend)
- v3.4 Update: Added customizable Legend options (Simple vs Detailed).
- v3.4 Update: Users can toggle Group Name, Baseline, and Delta in the legend.
- v3.3 Feature: Real Raw Baseline plotting (20s).
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import re
import threading
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from itertools import cycle

# =============================== 1. 設定區 =======================================
ROOT = r"/Users/k/Downloads/20260303"  # 請修改為您的實際路徑

DATA_COL = "pF - Plot 0"
DT_SEC = 0.1
INITIAL_BASELINE_POINTS = 200 # 20 seconds
DROP_SIGMA_THRESHOLD = 3.0   
COLOR_PALETTE = plt.cm.tab10.colors 

# ============================ 2. 輔助工具函式 ==========================

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]

def get_subfolders(path):
    if not os.path.exists(path):
        return []
    return [f for f in os.listdir(path) if os.path.isdir(os.path.join(path, f))]

# ============================ 3. 核心處理函式 ==========================

def read_xlsx_single(path: str) -> pd.DataFrame | None:
    try:
        df = pd.read_excel(path, engine="openpyxl")
        if DATA_COL not in df.columns:
            return None
        return df[[DATA_COL]].copy()
    except Exception:
        return None

def process_single_file(file_path: str) -> dict | None:
    df = read_xlsx_single(file_path)
    if df is None or df.empty:
        return None

    data = df[DATA_COL].to_numpy()
    
    if len(data) < INITIAL_BASELINE_POINTS:
        baseline_len = len(data)
    else:
        baseline_len = INITIAL_BASELINE_POINTS

    baseline_segment = data[:baseline_len]
    mu = np.mean(baseline_segment)
    sd = np.std(baseline_segment, ddof=1)
    
    threshold = mu + DROP_SIGMA_THRESHOLD * max(sd, 1e-4)
    search_end = min(len(data), baseline_len + 500)
    search_range = data[baseline_len : search_end]
    
    over_idx = np.where(search_range > threshold)[0]
    idx_drop = baseline_len + (over_idx[0] if over_idx.size > 0 else 0)

    initial_avg = mu
    final_avg = np.nanmean(data[-100:]) if len(data) >= 100 else np.nan
    delta_raw = final_avg - initial_avg

    return {
        'time_sec': np.arange(len(data)) * DT_SEC,
        'capacitance': data,
        'drop_time': idx_drop * DT_SEC,
        'delta_capacitance': delta_raw,
        'initial_avg': initial_avg
    }

# ============================ 4. GUI 應用程式類別 ==========================================
class RawDataViewerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Raw Data Viewer - v3.4 (Custom Legend)")
        self.geometry("1400x900") #稍微加大高度以容納新選項

        # --- 變數區 ---
        self.show_drop_lines_var = tk.BooleanVar(value=True)
        self.overlay_mode_var = tk.BooleanVar(value=False)
        self.display_mode_var = tk.StringVar(value="Norm")
        self.group_color_var = tk.BooleanVar(value=True)
        
        # v3.4 Legend Options Variables
        self.legend_style_var = tk.StringVar(value="Detailed") # Simple or Detailed
        self.leg_show_group = tk.BooleanVar(value=True)
        self.leg_show_base = tk.BooleanVar(value=True)
        self.leg_show_delta = tk.BooleanVar(value=False) # 預設只顯示 Base (符合您的圖片)
        self.l1_var = tk.StringVar(value="")
        self.l2_var = tk.StringVar(value="")
        self.l3_var = tk.StringVar(value="")

        self.color_cycler = cycle(COLOR_PALETTE)
        self.is_plotting = False
        self._control_widgets = []

        self.create_widgets()
        self.refresh_folder_structure() 

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- 左側控制面板 ---
        control_panel = ttk.LabelFrame(main_frame, text="Dynamic Selection", padding="8")
        control_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        self.control_canvas = tk.Canvas(control_panel, width=260, highlightthickness=0, borderwidth=0)
        control_scrollbar = ttk.Scrollbar(control_panel, orient=tk.VERTICAL, command=self.control_canvas.yview)
        controls_frame = ttk.Frame(self.control_canvas)

        controls_frame.bind(
            "<Configure>",
            lambda _event: self.control_canvas.configure(scrollregion=self.control_canvas.bbox("all"))
        )
        self.control_canvas.create_window((0, 0), window=controls_frame, anchor="nw")
        self.control_canvas.configure(yscrollcommand=control_scrollbar.set)
        self.control_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        control_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        controls_frame.bind("<Enter>", lambda _event: self.control_canvas.bind_all("<MouseWheel>", self._on_control_mousewheel))
        controls_frame.bind("<Leave>", lambda _event: self.control_canvas.unbind_all("<MouseWheel>"))

        # 1. Folder Selection
        ttk.Label(controls_frame, text="Step 1: Folder").pack(anchor=tk.W)
        self.l1_list = self._create_selection_list(controls_frame, self._on_l1_selected)
        self.l1_list.pack(fill=tk.X, pady=(0, 5))
        self._control_widgets.append(self.l1_list)

        ttk.Label(controls_frame, text="Step 2: Volume").pack(anchor=tk.W)
        self.l2_list = self._create_selection_list(controls_frame, self._on_l2_selected)
        self.l2_list.pack(fill=tk.X, pady=(0, 5))
        self._control_widgets.append(self.l2_list)

        ttk.Label(controls_frame, text="Step 3: Solution").pack(anchor=tk.W)
        self.l3_list = self._create_selection_list(controls_frame, self._on_l3_selected)
        self.l3_list.pack(fill=tk.X, pady=(0, 5))
        self._control_widgets.append(self.l3_list)

        self.refresh_btn = ttk.Button(controls_frame, text="↻ Refresh List", command=self.refresh_folder_structure)
        self.refresh_btn.pack(fill=tk.X, pady=5)
        self._control_widgets.append(self.refresh_btn)
        ttk.Separator(controls_frame, orient='horizontal').pack(fill='x', pady=10)

        # 2. Display Unit
        ttk.Label(controls_frame, text="Display Unit:").pack(anchor=tk.W)
        self.display_norm_rb = ttk.Radiobutton(controls_frame, text="Normalized (%)", variable=self.display_mode_var, value="Norm")
        self.display_norm_rb.pack(anchor=tk.W)
        self._control_widgets.append(self.display_norm_rb)
        self.display_raw_rb = ttk.Radiobutton(controls_frame, text="Raw Data (pF)", variable=self.display_mode_var, value="Raw")
        self.display_raw_rb.pack(anchor=tk.W)
        self._control_widgets.append(self.display_raw_rb)
        self.display_base_rb = ttk.Radiobutton(controls_frame, text="Baseline Only (Raw 20s)", variable=self.display_mode_var, value="Base")
        self.display_base_rb.pack(anchor=tk.W)
        self._control_widgets.append(self.display_base_rb)
        ttk.Separator(controls_frame, orient='horizontal').pack(fill='x', pady=10)

        # 3. Legend Options (v3.4 New Feature)
        leg_frame = ttk.LabelFrame(controls_frame, text="Legend Customization", padding=5)
        leg_frame.pack(fill=tk.X, pady=5)

        # Style Toggle
        self.legend_simple_rb = ttk.Radiobutton(leg_frame, text="Simple (e.g., N 1)", variable=self.legend_style_var, value="Simple")
        self.legend_simple_rb.pack(anchor=tk.W)
        self._control_widgets.append(self.legend_simple_rb)
        self.legend_detailed_rb = ttk.Radiobutton(leg_frame, text="Detailed", variable=self.legend_style_var, value="Detailed")
        self.legend_detailed_rb.pack(anchor=tk.W)
        self._control_widgets.append(self.legend_detailed_rb)

        # Details Checkboxes (Indented)
        detail_frame = ttk.Frame(leg_frame, padding=(15, 0, 0, 0))
        detail_frame.pack(fill=tk.X)
        self.leg_group_cb = ttk.Checkbutton(detail_frame, text="Group Name", variable=self.leg_show_group)
        self.leg_group_cb.pack(anchor=tk.W)
        self._control_widgets.append(self.leg_group_cb)
        self.leg_base_cb = ttk.Checkbutton(detail_frame, text="Baseline (Avg)", variable=self.leg_show_base)
        self.leg_base_cb.pack(anchor=tk.W)
        self._control_widgets.append(self.leg_base_cb)
        self.leg_delta_cb = ttk.Checkbutton(detail_frame, text="Delta (Δ)", variable=self.leg_show_delta)
        self.leg_delta_cb.pack(anchor=tk.W)
        self._control_widgets.append(self.leg_delta_cb)

        # 4. Visual Options
        ttk.Label(controls_frame, text="Visual Options:", font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(10,0))
        self.overlay_cb = ttk.Checkbutton(controls_frame, text="Overlay Mode", variable=self.overlay_mode_var)
        self.overlay_cb.pack(anchor=tk.W)
        self._control_widgets.append(self.overlay_cb)
        self.group_color_cb = ttk.Checkbutton(controls_frame, text="Group Color", variable=self.group_color_var)
        self.group_color_cb.pack(anchor=tk.W)
        self._control_widgets.append(self.group_color_cb)
        self.drop_lines_cb = ttk.Checkbutton(controls_frame, text="Show Drop Lines", variable=self.show_drop_lines_var)
        self.drop_lines_cb.pack(anchor=tk.W)
        self._control_widgets.append(self.drop_lines_cb)

        # 5. Buttons
        ttk.Separator(controls_frame, orient='horizontal').pack(fill='x', pady=(10, 10))
        self.plot_btn = ttk.Button(controls_frame, text="LOAD & PLOT", command=self.plot_data)
        self.plot_btn.pack(fill=tk.X, pady=(0, 5))
        self._control_widgets.append(self.plot_btn)
        self.clear_btn = ttk.Button(controls_frame, text="Clear Plot", command=self.clear_plot)
        self.clear_btn.pack(fill=tk.X, pady=5)
        self._control_widgets.append(self.clear_btn)
        self.export_btn = ttk.Button(controls_frame, text="Export Plot", command=self.export_plot)
        self.export_btn.pack(fill=tk.X, pady=5)
        self._control_widgets.append(self.export_btn)
        self.change_root_btn = ttk.Button(controls_frame, text="Change Root Path", command=self.select_root)
        self.change_root_btn.pack(fill=tk.X, pady=5)
        self._control_widgets.append(self.change_root_btn)

        self.path_label = ttk.Label(controls_frame, text=f"Root: {ROOT}", wraplength=220, font=("Arial", 8), foreground="gray")
        self.path_label.pack(fill=tk.X, pady=(10, 0))

        # --- 右側繪圖區 ---
        plot_frame = ttk.Frame(main_frame)
        plot_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.toolbar_frame = ttk.Frame(plot_frame)
        self.toolbar_frame.pack(side=tk.TOP, fill=tk.X)

        self.canvas_frame = ttk.Frame(plot_frame)
        self.canvas_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.fig = Figure(figsize=(10, 7), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.canvas_frame)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.toolbar_frame, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.pack(side=tk.LEFT, fill=tk.X)
        self.clear_plot()

    def set_controls_enabled(self, enabled: bool):
        selection_widgets = [
            self.l1_list,
            self.l2_list,
            self.l3_list,
        ]

        for widget in selection_widgets:
            widget.configure(state="normal" if enabled else "disabled")

        for widget in self._control_widgets:
            if widget in selection_widgets:
                continue
            try:
                if enabled:
                    widget.state(["!disabled"])
                else:
                    widget.state(["disabled"])
            except tk.TclError:
                pass

        self.update_idletasks()

    def _create_selection_list(self, parent, callback):
        listbox = tk.Listbox(parent, height=2, exportselection=False)
        listbox.bind("<<ListboxSelect>>", callback if callback is not None else lambda _event: None)
        return listbox

    def _on_control_mousewheel(self, event):
        delta = 0
        if event.delta:
            delta = -1 * int(event.delta / 120)
        if delta:
            self.control_canvas.yview_scroll(delta, "units")

    def _set_list_values(self, listbox, variable, values):
        listbox.delete(0, tk.END)
        for value in values:
            listbox.insert(tk.END, value)

        if not values:
            variable.set("")
            return

        current = variable.get()
        if current not in values:
            current = values[0]
        index = values.index(current)
        variable.set(current)
        listbox.selection_clear(0, tk.END)
        listbox.selection_set(index)
        listbox.activate(index)
        listbox.see(index)

    def _selected_list_value(self, listbox):
        selection = listbox.curselection()
        if not selection:
            return ""
        return listbox.get(selection[0])

    def _on_l1_selected(self, _event=None):
        self.l1_var.set(self._selected_list_value(self.l1_list))
        self.update_l2()

    def _on_l2_selected(self, _event=None):
        self.l2_var.set(self._selected_list_value(self.l2_list))
        self.update_l3()

    def _on_l3_selected(self, _event=None):
        self.l3_var.set(self._selected_list_value(self.l3_list))

    def _set_plotting_state(self, plotting: bool):
        self.is_plotting = plotting
        self.set_controls_enabled(not plotting)
        self.config(cursor="watch" if plotting else "")
        self.update_idletasks()

    # ============================ 5. 資料夾動態掃描邏輯 ==========================
    def select_root(self):
        global ROOT
        folder = filedialog.askdirectory()
        if folder:
            ROOT = folder
            self.path_label.config(text=f"Root: {ROOT}")
            self.refresh_folder_structure()

    def refresh_folder_structure(self):
        folders = get_subfolders(ROOT)
        self._set_list_values(self.l1_list, self.l1_var, folders)
        if folders:
            self.update_l2()
        else:
            self._set_list_values(self.l2_list, self.l2_var, [])
            self._set_list_values(self.l3_list, self.l3_var, [])

    def update_l2(self):
        p1 = os.path.join(ROOT, self.l1_var.get())
        folders = get_subfolders(p1)
        self._set_list_values(self.l2_list, self.l2_var, folders)
        if folders:
            self.update_l3()
        else:
            self._set_list_values(self.l3_list, self.l3_var, [])

    def update_l3(self):
        p2 = os.path.join(ROOT, self.l1_var.get(), self.l2_var.get())
        folders = get_subfolders(p2)
        self._set_list_values(self.l3_list, self.l3_var, folders)

    # ============================ 6. 繪圖邏輯 ==========================

    def clear_plot(self):
        self.ax.clear()
        self.ax.set_title("Ready", fontsize=14)
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Value")
        self.ax.grid(True, linestyle=':', alpha=0.6)
        self.color_cycler = cycle(COLOR_PALETTE)
        self.ax.set_prop_cycle(None)
        self.canvas.draw_idle()

    def plot_data(self):
        if self.is_plotting:
            return

        l1, l2, l3 = self.l1_var.get(), self.l2_var.get(), self.l3_var.get()
        if not all([l1, l2, l3]):
            messagebox.showwarning("Missing Path", "Please select all folder levels.")
            self.l3_list.focus_set()
            return

        target_dir = os.path.join(ROOT, l1, l2, l3)
        if not os.path.exists(target_dir):
            messagebox.showerror("Error", "Folder not found.")
            self.l3_list.focus_set()
            return

        all_files = [f for f in os.listdir(target_dir) if f.lower().endswith(".xlsx")]
        all_files.sort(key=natural_sort_key)

        if not all_files:
            messagebox.showinfo("Empty", "No .xlsx files found in this folder.")
            self.l3_list.focus_set()
            return

        settings = {
            'l1': l1,
            'l2': l2,
            'l3': l3,
            'target_dir': target_dir,
            'all_files': all_files,
            'is_overlay': self.overlay_mode_var.get(),
            'display_mode': self.display_mode_var.get(),
            'use_group_color': self.group_color_var.get(),
            'show_drop_lines': self.show_drop_lines_var.get(),
            'leg_style': self.legend_style_var.get(),
            'show_group': self.leg_show_group.get(),
            'show_base': self.leg_show_base.get(),
            'show_delta': self.leg_show_delta.get(),
        }

        self._set_plotting_state(True)
        threading.Thread(target=self._plot_data_worker, args=(settings,), daemon=True).start()

    def _plot_data_worker(self, settings: dict):
        try:
            if settings['display_mode'] == "Norm":
                y_unit = "Normalized (%)"
            elif settings['display_mode'] == "Base":
                y_unit = "Baseline Capacitance (pF)"
            else:
                y_unit = "Raw Capacitance (pF)"

            group_color = next(self.color_cycler)
            style_cycler = cycle(['-', '--', '-.', ':'])
            plot_items = []

            for fname in settings['all_files']:
                file_path = os.path.join(settings['target_dir'], fname)
                res = process_single_file(file_path)
                if not res:
                    continue

                y_raw = res['capacitance']
                base = res['initial_avg']
                d_val_raw = res['delta_capacitance']
                n_label = os.path.splitext(fname)[0]

                x_plot = res['time_sec']
                y_plot = y_raw
                delta_str = ""

                if settings['display_mode'] == "Norm":
                    y_plot = (y_raw / base) * 100
                    d_pct = (((base + d_val_raw) / base) * 100) - 100
                    delta_str = f"Δ:{d_pct:.2f}%"
                elif settings['display_mode'] == "Base":
                    limit = min(INITIAL_BASELINE_POINTS, len(y_raw))
                    y_plot = y_raw[:limit]
                    x_plot = res['time_sec'][:limit]
                    delta_str = f"Δ:{d_val_raw:.2f}pF"
                else:
                    delta_str = f"Δ:{d_val_raw:.2f}pF"

                if settings['leg_style'] == "Simple":
                    label_txt = f"N {n_label}"
                else:
                    parts = []
                    if settings['show_group']:
                        parts.append(f"[{settings['l1']}]")
                    parts.append(f"N {n_label}")

                    info_parts = []
                    if settings['show_base']:
                        info_parts.append(f"Base:{base:.2f} pF")
                    if settings['show_delta']:
                        info_parts.append(delta_str)

                    if info_parts:
                        label_txt = " ".join(parts) + " (" + ", ".join(info_parts) + ")"
                    else:
                        label_txt = " ".join(parts)

                ls = next(style_cycler) if settings['use_group_color'] else '-'
                c = group_color if settings['use_group_color'] else None

                plot_items.append({
                    'x_plot': x_plot,
                    'y_plot': y_plot,
                    'label_txt': label_txt,
                    'drop_time': res['drop_time'],
                    'line_style': ls,
                    'line_color': c,
                })

            payload = {
                'settings': settings,
                'y_unit': y_unit,
                'plot_items': plot_items,
            }
            self.after(0, lambda: self._plot_data_apply(payload))
        except Exception as exc:
            self.after(0, lambda: self._plot_data_failed(exc))

    def _plot_data_apply(self, payload: dict):
        settings = payload['settings']

        if not settings['is_overlay']:
            self.clear_plot()
            self.ax.set_title(f"{settings['l1']} | {settings['l2']} | {settings['l3']}", fontsize=12)

        self.ax.set_ylabel(payload['y_unit'])

        count = 0
        for item in payload['plot_items']:
            count += 1
            line, = self.ax.plot(
                item['x_plot'],
                item['y_plot'],
                label=item['label_txt'],
                color=item['line_color'],
                linestyle=item['line_style'],
                alpha=0.8,
                lw=1.5,
            )

            if settings['display_mode'] != "Base" and settings['show_drop_lines']:
                self.ax.axvline(x=item['drop_time'], color=line.get_color(), ls='--', alpha=0.3)

        if count > 0:
            self.ax.legend(fontsize='x-small', loc='upper left', bbox_to_anchor=(1.0, 1.0))
            self.fig.tight_layout()
            self.canvas.draw_idle()

        self._set_plotting_state(False)

    def _plot_data_failed(self, exc: Exception):
        self._set_plotting_state(False)
        self.l3_list.focus_set()
        messagebox.showerror("Plot Error", f"Failed to load or plot data.\n\n{exc}")

    def export_plot(self):
        path = filedialog.asksaveasfilename(defaultextension=".png")
        if path:
            self.fig.savefig(path, dpi=300, bbox_inches="tight")
            messagebox.showinfo("Exported", "Saved successfully.")

if __name__ == "__main__":
    app = RawDataViewerApp()
    app.mainloop()
