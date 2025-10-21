# raw_data_viewer_gui.py
# -*- coding: utf-8 -*-
"""
Raw Data Viewer for Lanolin Experiment (v1.0)
- A GUI tool to load and visualize raw experimental data directly from .xlsx files.
- Allows selection of a single experimental condition (Lanolin + Profenofos).
- Plots all replicates for the selected condition on a single graph.
- Marks the algorithmically detected reagent drop point (t=0) for each replicate.
- This tool is designed for data quality control and algorithm verification.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from itertools import cycle

# =============================== 1. 設定區 (請確保與您的數據結構相符) =======================================
# --- 資料夾與檔案結構 ---
ROOT = r"E:\Onedrive\桌面\新增資料夾\1019_lanolin\concetration" # 你的資料根目錄
LANOLIN_CONCS = ["1%", "2.5%", "5%"]
PROFENOFOS_DILUTIONS = ["DI water", "100x", "1000x", "2000x", "10000x"]
REPLICATES = ["1", "2", "3", "4"] # 搜尋的重複次數範圍

# --- 數據欄位與時間參數 ---
DATA_COL = "pF - Plot 0"
DT_SEC = 0.1

# --- 滴藥點偵測演算法參數 ---
DROP_SEARCH_WINDOW = 100
DROP_SIGMA_THRESHOLD = 3.0
BASELINE_TAIL_FOR_DROP = 100

# --- 繪圖設定 ---
COLOR_CYCLE = plt.cm.tab10.colors 

# ============================ 2. 核心函式 (從預處理腳本修改而來) ==========================
def read_xlsx(path: str) -> pd.DataFrame | None:
    """安全地讀取 Excel，只保留數據欄位"""
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_excel(path, engine="openpyxl")
        if DATA_COL not in df.columns:
            return None
        return df[[DATA_COL]].copy()
    except Exception:
        return None

def load_and_process_replicate(xi_path: str, xf_path: str) -> dict | None:
    """
    讀取單一重複實驗的原始數據，並偵測滴藥點。
    返回包含時間、原始電容和滴藥點索引的字典。
    """
    df_i = read_xlsx(xi_path)
    df_f = read_xlsx(xf_path)

    if df_i is None or df_f is None or df_i.empty or df_f.empty:
        return None

    len_i = len(df_i)
    f_data = df_f[DATA_COL].to_numpy()

    # --- 偵測滴藥點 ---
    s = max(0, len_i - BASELINE_TAIL_FOR_DROP)
    base = df_i[DATA_COL].iloc[s:].to_numpy()
    base = base[np.isfinite(base)]
    if base.size < 10: 
        return None # 基線太短，無法偵測
        
    mu, sd = np.mean(base), np.std(base, ddof=1)
    thr = mu + DROP_SIGMA_THRESHOLD * (sd if sd > 1e-9 else 1e-9)
    search_end = min(len_i + DROP_SEARCH_WINDOW, len(f_data))
    over_threshold_indices = np.where(f_data[len_i:search_end] > thr)[0]
    
    idx_drop = len_i + over_threshold_indices[0] if over_threshold_indices.size > 0 else len_i
    
    # --- 準備回傳資料 ---
    time_sec = np.arange(len(f_data)) * DT_SEC
    
    return {
        'time_sec': time_sec,
        'capacitance': f_data,
        'drop_index': idx_drop
    }

# ============================ 3. GUI 應用程式類別 ==========================================
class RawDataViewerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Raw Data Viewer")
        self.geometry("1200x800")
        
        self.create_widgets()

    def create_widgets(self):
        """建立 GUI 的所有元件"""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- 控制面板 ---
        control_panel = ttk.LabelFrame(main_frame, text="Select Condition", padding="10")
        control_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        ttk.Label(control_panel, text="Lanolin Concentration:").pack(anchor=tk.W, pady=(0, 5))
        self.lanolin_combo = ttk.Combobox(control_panel, values=LANOLIN_CONCS, state="readonly")
        self.lanolin_combo.pack(fill=tk.X, pady=(0, 10))
        self.lanolin_combo.set(LANOLIN_CONCS[0])
        
        ttk.Label(control_panel, text="Profenofos Dilution:").pack(anchor=tk.W, pady=(0, 5))
        self.profenofos_combo = ttk.Combobox(control_panel, values=PROFENOFOS_DILUTIONS, state="readonly")
        self.profenofos_combo.pack(fill=tk.X, pady=(0, 20))
        self.profenofos_combo.set(PROFENOFOS_DILUTIONS[0])
        
        button_frame = ttk.Frame(control_panel)
        button_frame.pack(fill=tk.X)
        
        ttk.Button(button_frame, text="Load & Plot Data", command=self.plot_selected_condition).pack(fill=tk.X, pady=5)
        ttk.Button(button_frame, text="Clear Plot", command=self.initialize_plot).pack(fill=tk.X, pady=5)
        ttk.Button(button_frame, text="Export Plot...", command=self.export_plot).pack(fill=tk.X, pady=5)

        # --- 圖表顯示區 ---
        plot_frame = ttk.Frame(main_frame)
        plot_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.fig = Figure(figsize=(10, 7), dpi=100)
        self.ax = self.fig.add_subplot(111)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        self.toolbar = NavigationToolbar2Tk(self.canvas, plot_frame)
        self.toolbar.update()
        
        self.initialize_plot()

    def initialize_plot(self, title="Select a condition and click 'Load & Plot Data'"):
        """初始化或清空圖表"""
        self.ax.clear()
        self.ax.set_title(title, fontsize=14)
        self.ax.set_xlabel("Time (seconds)", fontsize=12)
        self.ax.set_ylabel(f"Raw Capacitance ({DATA_COL})", fontsize=12)
        self.ax.grid(True, linestyle='--', alpha=0.6)
        self.fig.tight_layout()
        self.canvas.draw()

    def plot_selected_condition(self):
        """根據使用者選擇的條件，載入並繪製所有重複實驗的原始數據"""
        lanolin = self.lanolin_combo.get()
        profenofos = self.profenofos_combo.get()

        if not lanolin or not profenofos:
            messagebox.showwarning("Selection Missing", "Please select both a Lanolin concentration and a Profenofos dilution.")
            return
        
        plot_title = f"Raw Data for: {lanolin} Lanolin / {profenofos} Profenofos"
        self.initialize_plot(title=plot_title)
        
        color_cycler = cycle(COLOR_CYCLE)
        found_data = False

        for rep in REPLICATES:
            xi_path = os.path.join(ROOT, profenofos, lanolin, f"{rep}i.xlsx")
            xf_path = os.path.join(ROOT, profenofos, lanolin, f"{rep}f.xlsx")

            result_data = load_and_process_replicate(xi_path, xf_path)
            
            if result_data:
                found_data = True
                time = result_data['time_sec']
                capacitance = result_data['capacitance']
                drop_idx = result_data['drop_index']
                drop_time = time[drop_idx]
                
                color = next(color_cycler)
                
                # 繪製原始數據曲線
                self.ax.plot(time, capacitance, color=color, alpha=0.8, label=f"Replicate {rep}")
                
                # 標示偵測到的滴藥點
                self.ax.axvline(x=drop_time, color=color, linestyle='--', linewidth=1.5, 
                                label=f"Drop (Rep {rep}) at {drop_time:.1f}s")
        
        if found_data:
            self.ax.legend()
        else:
            self.ax.text(0.5, 0.5, "No valid data found for this condition.", 
                         horizontalalignment='center', verticalalignment='center', 
                         transform=self.ax.transAxes, fontsize=14, color='red')

        self.canvas.draw()

    def export_plot(self):
        """匯出當前圖表為圖片檔案"""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG file", "*.png"), ("SVG file", "*.svg"), ("All files", "*.*")],
            title="Save the plot as..."
        )
        if not file_path:
            return
        try:
            self.fig.savefig(file_path, dpi=300, bbox_inches="tight")
            messagebox.showinfo("Success", f"Plot successfully saved to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save plot:\n{e}")

# ============================ 4. 應用程式啟動 ==========================================
if __name__ == "__main__":
    app = RawDataViewerApp()
    app.mainloop()