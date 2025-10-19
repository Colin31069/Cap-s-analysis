# interactive_analyzer_gui.py
# -*- coding: utf-8 -*-
"""
Interactive Time-Response Curve Analysis Tool (v1.0)
- Loads preprocessed time-series data from 'preprocessed_data.pkl'.
- Provides a GUI to select and overlay multiple experimental conditions.
- Displays mean curves with their corresponding SEM error bands.
- Allows exporting the generated plot to a file.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pickle
import os
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from itertools import cycle

# =============================== 1. 設定區 (可調參數) =======================================
DATA_FILE = os.path.join(r"E:\Onedrive\桌面\新增資料夾\1019_lanolin\concetration", 
                         "analysis_outputs_interactive", 
                         "preprocessed_data.pkl")

# --- 繪圖設定 ---
# 使用 Matplotlib 的 'tab10' 色彩循環，提供10種高對比度的顏色
COLOR_CYCLE = plt.cm.tab10.colors 
PLOT_TITLE = "Comparative Time Response Analysis"
X_AXIS_LABEL = "Time after Reagent Drop (min)"
# 👇 *** 在這裡進行修改 *** 👇
Y_AXIS_LABEL = "Capacitance Change (%)" 

# ============================ 2. GUI 應用程式類別 ==========================================
class CurveAnalyzerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Interactive Time-Response Curve Analyzer")
        self.geometry("1200x800")

        self.data = self.load_data()
        if not self.data:
            self.destroy()
            return
            
        self.lanolin_options, self.profenofos_options = self.get_options()
        self.color_cycler = cycle(COLOR_CYCLE)
        
        self.create_widgets()

    def load_data(self):
        """載入預處理的 pickle 檔案"""
        try:
            with open(DATA_FILE, 'rb') as f:
                return pickle.load(f)
        except FileNotFoundError:
            messagebox.showerror(
                "Error", 
                f"Data file not found:\n{DATA_FILE}\n\nPlease run the preprocess_data.py script first."
            )
            return None
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while loading data:\n{e}")
            return None

    def get_options(self):
        """從資料中提取獨特的實驗條件選項"""
        lanolin = sorted(list(set(key[0] for key in self.data.keys())))
        profenofos = sorted(list(set(key[1] for key in self.data.keys())))
        return lanolin, profenofos

    def create_widgets(self):
        """建立 GUI 的所有元件"""
        # --- 主框架 ---
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- 控制面板 ---
        control_panel = ttk.LabelFrame(main_frame, text="Controls", padding="10")
        control_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        # Lanolin 選擇區
        ttk.Label(control_panel, text="Lanolin Concentration:").pack(anchor=tk.W, pady=(0, 5))
        self.lanolin_listbox = tk.Listbox(control_panel, selectmode=tk.MULTIPLE, exportselection=False, height=5)
        for option in self.lanolin_options:
            self.lanolin_listbox.insert(tk.END, option)
        self.lanolin_listbox.pack(fill=tk.X, expand=True, pady=(0, 10))
        
        # Profenofos 選擇區
        ttk.Label(control_panel, text="Profenofos Dilution:").pack(anchor=tk.W, pady=(0, 5))
        self.profenofos_listbox = tk.Listbox(control_panel, selectmode=tk.MULTIPLE, exportselection=False, height=6)
        for option in self.profenofos_options:
            self.profenofos_listbox.insert(tk.END, option)
        self.profenofos_listbox.pack(fill=tk.X, expand=True, pady=(0, 20))
        
        # 功能按鈕區
        button_frame = ttk.Frame(control_panel)
        button_frame.pack(fill=tk.X)
        
        ttk.Button(button_frame, text="Generate/Update Plot", command=self.plot_selected_curves).pack(fill=tk.X, pady=5)
        ttk.Button(button_frame, text="Clear Selections & Plot", command=self.clear_all).pack(fill=tk.X, pady=5)
        ttk.Button(button_frame, text="Export Plot...", command=self.export_plot).pack(fill=tk.X, pady=5)

        # --- 圖表顯示區 ---
        plot_frame = ttk.Frame(main_frame)
        plot_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.fig = Figure(figsize=(10, 7), dpi=100)
        self.ax = self.fig.add_subplot(111)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        toolbar = NavigationToolbar2Tk(self.canvas, plot_frame)
        toolbar.update()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        self.initialize_plot()

    def initialize_plot(self):
        """初始化空的圖表外觀"""
        self.ax.clear()
        self.ax.set_title(PLOT_TITLE)
        self.ax.set_xlabel(X_AXIS_LABEL)
        self.ax.set_ylabel(Y_AXIS_LABEL)
        self.ax.grid(True, linestyle='--', alpha=0.6)
        self.ax.axvline(0, color='blue', linestyle='--', linewidth=1.5, label='Reagent Drop (t=0)')
        self.fig.tight_layout()
        self.canvas.draw()

    def plot_selected_curves(self):
        """根據使用者選擇繪製曲線"""
        selected_lanolin_indices = self.lanolin_listbox.curselection()
        selected_profenofos_indices = self.profenofos_listbox.curselection()

        if not selected_lanolin_indices or not selected_profenofos_indices:
            messagebox.showinfo("Information", "Please select at least one option from each list.")
            return

        selected_lanolin = [self.lanolin_options[i] for i in selected_lanolin_indices]
        selected_profenofos = [self.profenofos_options[i] for i in selected_profenofos_indices]

        self.initialize_plot()
        self.color_cycler = cycle(COLOR_CYCLE) # 重置顏色循環

        for l_conc in selected_lanolin:
            for p_dil in selected_profenofos:
                key = (l_conc, p_dil)
                if key in self.data:
                    curve_data = self.data[key]
                    time = curve_data['time']
                    mean = curve_data['mean']
                    sem = curve_data['sem']
                    
                    color = next(self.color_cycler)
                    label = f"{l_conc} - {p_dil}"
                    
                    self.ax.plot(time, mean, color=color, label=label, linewidth=2)
                    self.ax.fill_between(time, mean - sem, mean + sem, color=color, alpha=0.2)
        
        # 更新圖例和佈局
        handles, labels = self.ax.get_legend_handles_labels()
        # 確保滴藥線的圖例在最前
        drop_line_handle = [h for h, l in zip(handles, labels) if 'Reagent Drop' in l]
        other_handles = [h for h, l in zip(handles, labels) if 'Reagent Drop' not in l]
        drop_line_label = [l for l in labels if 'Reagent Drop' in l]
        other_labels = [l for l in labels if 'Reagent Drop' not in l]

        if other_handles: # 只有在有曲線時才顯示圖例
            self.ax.legend(drop_line_handle + other_handles, drop_line_label + other_labels)

        self.fig.tight_layout()
        self.canvas.draw()
        
    def clear_all(self):
        """清除所有選擇和圖表"""
        self.lanolin_listbox.selection_clear(0, tk.END)
        self.profenofos_listbox.selection_clear(0, tk.END)
        self.initialize_plot()

    def export_plot(self):
        """匯出當前圖表為圖片檔案"""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[
                ("PNG file", "*.png"),
                ("SVG file", "*.svg"),
                ("All files", "*.*"),
            ]
        )
        if not file_path:
            return
        try:
            self.fig.savefig(file_path, dpi=300, bbox_inches="tight")
            messagebox.showinfo("Success", f"Plot successfully saved to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save plot:\n{e}")

# ============================ 3. 應用程式啟動 ==========================================
if __name__ == "__main__":
    app = CurveAnalyzerApp()
    app.mainloop()