from __future__ import annotations

import os
from concurrent.futures import CancelledError
from dataclasses import replace
from queue import Empty, SimpleQueue
import threading
from time import monotonic
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from .analysis import CapacitanceCache
from .filesystem import discover_experiment_folders, list_xlsx_files, resolve_directory_path
from .models import AnalysisProgress, ErrorBandPayload, ErrorBandSettings, PlotAppearance
from .plotting import (
    build_error_band_payload, render_error_band_plot,
    validate_error_band_settings, write_error_band_csv, LEGEND_POSITIONS,
    COLOR_GROUP_OPTIONS, color_group_name, resolve_group_colors,
)

EXPORT_FILETYPES = (
    ("PNG image", "*.png"),
    ("PDF document", "*.pdf"),
    ("SVG vector image", "*.svg"),
)


class ErrorBandViewerApp(tk.Tk):
    """Small, read-only workflow for plotting multiple replicate groups."""

    UNIT_OPTIONS = {
        "ΔC：扣除 baseline（pF）": "Delta",
        "相對變化（%）": "DeltaPct",
        "原始電容（pF）": "Raw",
    }

    def __init__(self) -> None:
        super().__init__()
        self.title("Cap-s data analysis")
        self.geometry("1180x780")
        self.minsize(960, 660)
        self.path_var = tk.StringVar()
        self.title_var = tk.StringVar()
        self.unit_var = tk.StringVar(value=next(iter(self.UNIT_OPTIONS)))
        self.band_var = tk.StringVar(value="SEM")
        self.grid_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="先選擇放置 Excel 資料的資料夾。")
        self.progress_var = tk.StringVar()
        self.selection_var = tk.StringVar()
        self.folder_summary_var = tk.StringVar()
        self.analysis_progress_var = tk.StringVar()
        self.analysis_percent_var = tk.DoubleVar(value=0)
        self.band_hint_var = tk.StringVar()
        self.timing_vars = {
            "sample_interval_sec": tk.StringVar(value="0.1"),
            "baseline_duration_sec": tk.StringVar(value="20"),
            "drug_apply_time_sec": tk.StringVar(value="25"),
            "drug_apply_tolerance_sec": tk.StringVar(value="5"),
        }
        self._data_root = ""
        self._groups: dict[str, bool] = {}
        self._labels: dict[str, str] = {}
        self._rows: dict[str, str] = {}
        self._payload: ErrorBandPayload | None = None
        self._settings_dirty = False
        self._busy = False
        self._results = SimpleQueue()
        self._poll_id: str | None = None
        self._controls: list[tk.Widget] = []
        self._combos: list[ttk.Combobox] = []
        self._advanced_open = False
        self._current_step = 1
        self._appearance = PlotAppearance()
        self._data_cache = CapacitanceCache()
        self._cancel_event = threading.Event()
        self._analysis_progress = AnalysisProgress(0, 0, "準備資料")
        self._run_started_at = 0.0
        self._phase_started_at = 0.0
        self._timing_lines: list[str] = []
        self._last_elapsed_sec = 0.0
        background = ttk.Style(self).lookup("TFrame", "background") or self.cget("background")
        self._background_color = background
        self._hint_color = "#9CA3AF" if sum(self.winfo_rgb(background)) < 3 * 32768 else "#667085"
        from matplotlib import rcParams
        from matplotlib.font_manager import fontManager

        available_fonts = {font.name for font in fontManager.ttflist}
        for font in ("Microsoft JhengHei", "PingFang TC", "PingFang HK", "Heiti TC", "Noto Sans CJK TC", "Arial Unicode MS"):
            if font in available_fonts:
                rcParams["font.sans-serif"] = [font, "DejaVu Sans"]
                break
        self._create_band_widgets()
        self.title_var.trace_add("write", lambda *_: self._redraw())
        self.unit_var.trace_add("write", self._on_analysis_changed)
        self.path_var.trace_add("write", self._on_analysis_changed)
        for variable in self.timing_vars.values():
            variable.trace_add("write", self._on_analysis_changed)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._redraw()

    def _create_band_widgets(self) -> None:
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill=tk.BOTH, expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)
        ttk.Label(outer, text="Cap-s data analysis", font=("TkDefaultFont", 20, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(outer, textvariable=self.progress_var, foreground=self._hint_color).grid(row=1, column=0, sticky="w", pady=(4, 14))
        body = ttk.Frame(outer)
        body.grid(row=2, column=0, sticky="nsew")
        left_column = ttk.Frame(body)
        left_column.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 18))
        scroll_area = ttk.Frame(left_column)
        scroll_area.pack(fill=tk.BOTH, expand=True)
        self.controls_canvas = tk.Canvas(scroll_area, width=310, highlightthickness=0, background=self._background_color)
        self.controls_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        controls_scrollbar = ttk.Scrollbar(scroll_area, orient=tk.VERTICAL, command=self.controls_canvas.yview)
        controls_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.controls_canvas.configure(yscrollcommand=controls_scrollbar.set)
        sidebar = ttk.Frame(self.controls_canvas)
        controls_window = self.controls_canvas.create_window((0, 0), window=sidebar, anchor="nw")
        sidebar.bind("<Configure>", lambda _: self.controls_canvas.configure(scrollregion=self.controls_canvas.bbox("all")))
        self.controls_canvas.bind("<Configure>", lambda event: self.controls_canvas.itemconfigure(controls_window, width=event.width))
        self.bind("<MouseWheel>", self._scroll_controls)

        self._step_frames = {step: ttk.Frame(sidebar) for step in (1, 2, 3)}
        folder_step, group_step, plot_step = (self._step_frames[step] for step in (1, 2, 3))

        data = ttk.LabelFrame(folder_step, text="1  選擇資料夾", padding=10)
        data.pack(fill=tk.X)
        ttk.Label(data, text="選擇放置 Excel 資料的資料夾。", wraplength=270).pack(anchor=tk.W, pady=(0, 10))
        self._button(data, "選擇資料夾…", self.choose_root).pack(fill=tk.X, pady=(0, 10))
        ttk.Label(data, text="或貼上資料夾路徑", foreground=self._hint_color).pack(anchor=tk.W)
        self.path_entry = ttk.Entry(data, textvariable=self.path_var, width=30)
        self.path_entry.pack(fill=tk.X, pady=(4, 0))
        self.path_entry.bind("<Return>", lambda _: self._next_step())
        self._controls.append(self.path_entry)

        ttk.Label(group_step, textvariable=self.folder_summary_var, foreground=self._hint_color, wraplength=285).pack(anchor=tk.W, pady=(0, 10))
        groups = ttk.LabelFrame(group_step, text="2  勾選比較組別", padding=10)
        groups.pack(fill=tk.X)
        self.group_tree = ttk.Treeview(groups, columns=("use", "group", "files"), show="headings", height=6, selectmode="browse")
        for column, title, width in (("use", "選", 32), ("group", "組別／圖例名稱", 184), ("files", "檔案", 40)):
            self.group_tree.heading(column, text=title)
            self.group_tree.column(column, width=width, minwidth=width if column != "group" else 100, stretch=column == "group", anchor=tk.W if column == "group" else tk.CENTER)
        self.group_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(groups, orient=tk.VERTICAL, command=self.group_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.group_tree.configure(yscrollcommand=scrollbar.set)
        self.group_tree.bind("<ButtonRelease-1>", self._toggle_group)
        self.group_tree.bind("<Double-1>", self._rename_group)
        self.group_tree.bind("<space>", self._toggle_group)
        selection = ttk.Frame(group_step)
        selection.pack(fill=tk.X, pady=(10, 0))
        self._button(selection, "全選", lambda: self._select_groups(True)).pack(side=tk.LEFT)
        self._button(selection, "全不選", lambda: self._select_groups(False)).pack(side=tk.LEFT, padx=5)
        ttk.Label(group_step, textvariable=self.selection_var).pack(anchor=tk.W, pady=(10, 4))
        ttk.Label(group_step, text="點選「選」欄勾選；雙擊名稱可修改圖例。", foreground=self._hint_color, wraplength=285).pack(anchor=tk.W)

        options = ttk.LabelFrame(plot_step, text="3  製圖與匯出", padding=10)
        options.pack(fill=tk.X)
        ttk.Label(options, text="顯示單位").pack(anchor=tk.W)
        unit = ttk.Combobox(options, textvariable=self.unit_var, values=tuple(self.UNIT_OPTIONS), state="readonly", width=29)
        unit.pack(fill=tk.X, pady=(3, 8))
        self._combos.append(unit)
        band_row = ttk.Frame(options)
        band_row.pack(fill=tk.X)
        ttk.Label(band_row, text="陰影範圍").pack(side=tk.LEFT)
        band = ttk.Combobox(band_row, textvariable=self.band_var, values=("SD", "SEM"), state="readonly", width=8)
        band.pack(side=tk.RIGHT)
        band.bind("<<ComboboxSelected>>", lambda _: self._redraw())
        self._combos.append(band)
        ttk.Label(options, textvariable=self.band_hint_var, foreground=self._hint_color).pack(anchor=tk.W, pady=(4, 8))
        ttk.Label(options, text="圖表標題（可留空）").pack(anchor=tk.W)
        title = ttk.Entry(options, textvariable=self.title_var)
        title.pack(fill=tk.X, pady=(3, 8))
        self._controls.append(title)
        grid = ttk.Checkbutton(options, text="顯示格線", variable=self.grid_var, command=self._redraw)
        grid.pack(anchor=tk.W)
        self._controls.append(grid)

        self.advanced_button = self._button(plot_step, "▸ 進階：取樣與時間對齊", self._toggle_advanced)
        self.advanced_button.pack(fill=tk.X, pady=(10, 5))
        self.advanced_frame = ttk.Frame(plot_step, padding=(10, 0))
        for row, (name, label) in enumerate((
            ("sample_interval_sec", "取樣間隔（s）"),
            ("baseline_duration_sec", "Baseline 長度（s）"),
            ("drug_apply_time_sec", "施加時間（s）"),
            ("drug_apply_tolerance_sec", "搜尋 ±（s）"),
        )):
            ttk.Label(self.advanced_frame, text=label).grid(row=row, column=0, sticky="w", pady=2)
            entry = ttk.Entry(self.advanced_frame, textvariable=self.timing_vars[name], width=10)
            entry.grid(row=row, column=1, sticky="e", padx=(12, 0), pady=2)
            self._controls.append(entry)

        navigation = ttk.Frame(left_column)
        navigation.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        self.back_button = self._button(navigation, "上一步", self._previous_step)
        self.back_button.pack(side=tk.LEFT)
        self.next_button = self._button(navigation, "下一步：勾選組別", self._next_step)
        self.next_button.pack(side=tk.RIGHT)
        self.actions = ttk.Frame(left_column)
        self.plot_button = self._button(self.actions, "製作誤差區域圖", self.plot_data)
        self.plot_button.pack(fill=tk.X, ipady=5)
        self.analysis_panel = ttk.Frame(self.actions)
        ttk.Label(self.analysis_panel, textvariable=self.analysis_progress_var, wraplength=285).pack(fill=tk.X, pady=(4, 6))
        ttk.Progressbar(self.analysis_panel, variable=self.analysis_percent_var, maximum=100).pack(fill=tk.X)
        self.cancel_button = ttk.Button(self.analysis_panel, text="取消分析", command=self._cancel_analysis)
        self.cancel_button.pack(fill=tk.X, pady=(6, 0))
        self.style_button = self._button(self.actions, "圖例與顏色…", self.edit_appearance)
        self.exports = ttk.Frame(self.actions)
        self.export_button = self._button(self.exports, "匯出圖片…", self.export_plot)
        self.export_button.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.csv_button = self._button(self.exports, "匯出 CSV…", self.export_csv)
        self.csv_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
        self.export_button.configure(state="disabled")
        self.csv_button.configure(state="disabled")

        plot = ttk.Frame(body)
        plot.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.fig = Figure(figsize=(8, 5.5), dpi=100, layout="constrained")
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.toolbar = NavigationToolbar2Tk(self.canvas, plot, pack_toolbar=False)
        footer = ttk.Frame(outer)
        footer.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(footer, textvariable=self.status_var, wraplength=850).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.report_button = ttk.Button(footer, text="分析明細／注意事項", command=self.show_report, state="disabled")
        self._controls.append(self.report_button)
        self._show_step(1)

    def _update_navigation(self) -> None:
        count = sum(self._groups.values())
        self.selection_var.set(f"已選擇 {count} 組")
        self.folder_summary_var.set(f"資料夾：{os.path.basename(self._data_root)}")
        labels = ("選擇資料夾", "勾選組別", "製圖與匯出")
        self.progress_var.set(" → ".join(f"【{index} {label}】" if index == self._current_step else f"{index} {label}" for index, label in enumerate(labels, 1)))
        self.back_button.configure(state="normal" if self._current_step > 1 and not self._busy else "disabled")
        can_continue = bool(self.path_var.get().strip()) if self._current_step == 1 else count > 0
        self.next_button.configure(state="normal" if can_continue and not self._busy else "disabled")
        self.next_button.configure(text="下一步：勾選組別" if self._current_step == 1 else "下一步：製圖與匯出")

    def _show_step(self, step: int) -> None:
        if self._busy:
            return
        if step >= 2 and (not self._groups or resolve_directory_path(self.path_var.get()) != self._data_root):
            step = 1
        elif step == 3 and not any(self._groups.values()):
            step = 2
        self._current_step = step
        for frame in self._step_frames.values():
            frame.pack_forget()
        self._step_frames[step].pack(fill=tk.X)
        self.controls_canvas.yview_moveto(0)
        self.actions.pack_forget()
        self.next_button.pack_forget()
        if step == 3:
            self.actions.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        else:
            self.next_button.pack(side=tk.RIGHT)
        self._update_navigation()
        self._redraw()

    def _next_step(self) -> None:
        if self._busy:
            return
        if self._current_step == 1:
            self.load_groups()
        elif self._current_step == 2 and any(self._groups.values()):
            self._show_step(3)
            self.status_var.set("確認圖表設定，再按「製作誤差區域圖」。")

    def _previous_step(self) -> None:
        if not self._busy and self._current_step > 1:
            self._show_step(self._current_step - 1)
            self.status_var.set("可重新選擇資料夾。" if self._current_step == 1 else "勾選要比較的組別，再按下一步。")

    def _button(self, parent, text, command) -> ttk.Button:
        button = ttk.Button(parent, text=text, command=command)
        self._controls.append(button)
        return button

    def _scroll_controls(self, event) -> None:
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget is self.controls_canvas:
                # macOS sends small deltas; Windows sends multiples of 120.
                delta = -int(event.delta / 120) if abs(event.delta) >= 120 else -int(event.delta)
                self.controls_canvas.yview_scroll(delta, "units")
                return
            widget = getattr(widget, "master", None)

    def choose_root(self) -> None:
        path = filedialog.askdirectory(parent=self, title="選擇包含各組實驗的根目錄", initialdir=self._data_root or os.path.expanduser("~"))
        if path:
            self.path_var.set(path)
            self.load_groups()

    def load_groups(self) -> bool:
        if self._busy:
            return False
        root = resolve_directory_path(self.path_var.get())
        if root is None:
            messagebox.showwarning("資料夾不存在", "請選擇或貼上有效的資料根目錄。", parent=self)
            return False
        try:
            groups = [(name, list_xlsx_files(os.path.join(root, name))) for name in discover_experiment_folders(root)]
        except OSError as exc:
            messagebox.showwarning("無法讀取資料夾", f"無法完成三層資料夾掃描，請確認目錄權限與雲端檔案狀態。\n\n{exc}", parent=self)
            return False
        if root != self._data_root:
            self._appearance = PlotAppearance()
        self._data_root = root
        self.path_var.set(root)
        self._groups.clear()
        self._labels.clear()
        self._rows.clear()
        self.group_tree.delete(*self.group_tree.get_children())
        for name, files in groups:
            if files:
                label = os.path.basename(root) if name == os.curdir else name
                self._groups[name] = True
                self._labels[name] = label
                row = self.group_tree.insert("", tk.END, values=("✓", label, len(files)))
                self._rows[row] = name
        self._on_analysis_changed()
        self._show_step(2 if self._groups else 1)
        self.status_var.set(f"找到 {len(self._groups)} 組實驗。勾選要比較的組別，再按下一步。" if self._groups else "找不到實驗組；請選擇含有 Excel 的資料夾，支援往下三層。")
        return bool(self._groups)

    def _toggle_group(self, event) -> None:
        if self._busy:
            return
        if event.keysym == "space":
            row = self.group_tree.focus()
        else:
            if self.group_tree.identify_column(event.x) != "#1":
                return
            row = self.group_tree.identify_row(event.y)
        if row not in self._rows:
            return
        name = self._rows[row]
        self._groups[name] = not self._groups[name]
        self.group_tree.set(row, "use", "✓" if self._groups[name] else "")
        self._on_analysis_changed()

    def _rename_group(self, event) -> None:
        if self._busy or self.group_tree.identify_column(event.x) != "#2":
            return
        row = self.group_tree.identify_row(event.y)
        if row not in self._rows:
            return
        name = self._rows[row]
        label = simpledialog.askstring("圖例名稱", f"{name} 的圖例名稱：", initialvalue=self._labels[name], parent=self)
        if label is not None:
            self._labels[name] = label.strip() or name
            self.group_tree.set(row, "group", self._labels[name])
            if self._payload:
                self._payload = replace(self._payload, groups=tuple(replace(group, legend_label=self._labels.get(group.group_name, group.group_name)) for group in self._payload.groups))
                self._redraw()

    def _select_groups(self, selected: bool) -> None:
        if self._busy:
            return
        for row, name in self._rows.items():
            self._groups[name] = selected
            self.group_tree.set(row, "use", "✓" if selected else "")
        self._on_analysis_changed()

    def _toggle_advanced(self) -> None:
        self._advanced_open = not self._advanced_open
        if self._advanced_open:
            self.advanced_frame.pack(fill=tk.X, after=self.advanced_button)
        else:
            self.advanced_frame.pack_forget()
        self.advanced_button.configure(text=("▾" if self._advanced_open else "▸") + " 進階：取樣與時間對齊")

    def _on_analysis_changed(self, *_args) -> None:
        if self._payload:
            self._settings_dirty = True
            self.export_button.configure(state="disabled")
            self.csv_button.configure(state="disabled")
            self.status_var.set("資料或分析設定已變更，請重新製圖後匯出。")
        self._update_navigation()
        self._redraw()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for control in self._controls:
            control.configure(state="disabled" if busy else "normal")
        for combo in self._combos:
            combo.configure(state="disabled" if busy else "readonly")
        if not busy:
            exportable = bool(self._payload and self._payload.groups and not self._settings_dirty)
            self.export_button.configure(state="normal" if exportable else "disabled")
            self.csv_button.configure(state="normal" if exportable else "disabled")
            self.report_button.configure(state="normal" if self._payload else "disabled")
        self.plot_button.configure(text="分析中…" if busy else "製作誤差區域圖")
        self.analysis_panel.pack_forget()
        if busy:
            self.analysis_panel.pack(fill=tk.X, pady=6)
            self.cancel_button.configure(state="normal", text="取消分析")
        self._update_navigation()

    def _cancel_analysis(self) -> None:
        if self._busy:
            self._cancel_event.set()
            self.cancel_button.configure(state="disabled", text="正在取消…")
            self.status_var.set("已要求取消；若正在等待雲端檔案，需等目前讀取返回後安全停止。")

    def _refresh_analysis_progress(self) -> None:
        progress = self._analysis_progress
        elapsed = monotonic() - self._run_started_at
        waiting = monotonic() - self._phase_started_at
        count = f"已處理 {progress.completed}/{progress.total} 個檔案" if progress.total else "正在確認檔案數量"
        detail = f"{progress.stage}：{progress.item}" if progress.item else progress.stage
        text = f"{count} · 已經過 {elapsed:.0f} 秒\n{detail}"
        if self._cancel_event.is_set():
            text += "\n已要求取消，正在等待目前讀取安全結束。"
        elif waiting >= 10 and progress.stage in ("讀取 Excel", "讀取組別設定", "掃描檔案"):
            text += f"\n此讀取已等待 {waiting:.0f} 秒。可能涉及雲端同步或檔案讀取；可將資料下載至本機後重試。"
        self.analysis_progress_var.set(text)
        self.analysis_percent_var.set(100 * progress.completed / progress.total if progress.total else 0)

    def plot_data(self) -> None:
        if self._busy or self._current_step != 3:
            return
        if resolve_directory_path(self.path_var.get()) != self._data_root or not self._groups:
            self._show_step(1)
            return
        selected = [name for name, included in self._groups.items() if included]
        if not selected:
            self._show_step(2)
            messagebox.showwarning("尚未選擇組別", "請至少勾選一組含有 Excel 資料的實驗。", parent=self)
            return
        try:
            settings = ErrorBandSettings(display_mode=self.UNIT_OPTIONS[self.unit_var.get()], **{name: float(variable.get()) for name, variable in self.timing_vars.items()})
            validate_error_band_settings(settings)
        except (ValueError, KeyError) as exc:
            messagebox.showwarning("設定無效", f"請檢查進階參數。\n\n{exc}", parent=self)
            return
        root, labels = self._data_root, dict(self._labels)
        self._cancel_event.clear()
        self._run_started_at = self._phase_started_at = monotonic()
        self._analysis_progress = AnalysisProgress(0, 0, "準備資料")
        self._timing_lines = []
        self._refresh_analysis_progress()
        self._settings_dirty = True
        self._set_busy(True)
        self._redraw()
        self.status_var.set("正在讀取 Excel、對齊反應起點並計算平均與誤差範圍…")

        def worker() -> None:
            try:
                payload = build_error_band_payload(
                    root, selected, settings,
                    progress=lambda progress: self._results.put(("progress", progress)),
                    cancelled=self._cancel_event.is_set,
                    data_cache=self._data_cache,
                )
                payload = replace(payload, groups=tuple(replace(group, legend_label=labels[group.group_name]) for group in payload.groups))
                self._results.put(("done", payload))
            except CancelledError:
                self._results.put(("cancelled", None))
            except Exception as exc:
                self._results.put(("error", exc))

        threading.Thread(target=worker, daemon=True).start()
        # Poll from Tk's main thread; the worker never calls Tk or Matplotlib.
        self._poll_id = self.after(80, self._poll_result)

    def _poll_result(self) -> None:
        self._poll_id = None
        outcome = None
        while True:
            try:
                kind, result = self._results.get_nowait()
            except Empty:
                break
            if kind == "progress":
                if (result.stage, result.item) != (self._analysis_progress.stage, self._analysis_progress.item):
                    self._phase_started_at = monotonic()
                self._analysis_progress = result
                if result.duration_sec:
                    self._timing_lines.append(f"{result.stage}：{result.item} — {result.duration_sec:.3f} 秒")
            else:
                outcome = kind, result
                break
        if outcome is None:
            self._refresh_analysis_progress()
            self._poll_id = self.after(80, self._poll_result)
            return
        kind, result = outcome
        self._last_elapsed_sec = monotonic() - self._run_started_at
        if kind == "cancelled" or self._cancel_event.is_set():
            self.status_var.set("分析已取消，未採用未完成的結果。可以修改設定後重試。")
            self._redraw()
        elif kind == "done":
            self._payload = result
            self._settings_dirty = False
            self._redraw()
            n = sum(group.n for group in result.groups)
            self.status_var.set(f"已製作 {len(result.groups)} 組、共 {n} 筆樣本；資料處理 {self._last_elapsed_sec:.1f} 秒。注意事項 {len(result.warnings)} 則。" if result.groups else "沒有可製圖的有效資料；請查看分析明細。")
        else:
            self.status_var.set("分析失敗；請檢查檔案或設定後重試。")
            messagebox.showerror("分析失敗", str(result), parent=self)
        self._set_busy(False)

    def _redraw(self) -> None:
        self.band_hint_var.set("SD：顯示重複樣本的分散程度" if self.band_var.get() == "SD" else "SEM：顯示平均值的標準誤")
        plot_ready = bool(self._current_step == 3 and self._payload and self._payload.groups and not self._settings_dirty)
        self.exports.pack_forget()
        self.toolbar.pack_forget()
        self.report_button.pack_forget()
        self.style_button.pack_forget()
        if plot_ready:
            render_error_band_plot(self.ax, self._payload, self.band_var.get(), self.title_var.get(), self.grid_var.get(), appearance=self._appearance)
            self.style_button.pack(fill=tk.X, pady=(6, 0))
            self.exports.pack(fill=tk.X, pady=6)
            self.toolbar.pack(fill=tk.X)
        else:
            self.ax.clear()
            self.ax.set_axis_off()
            heading, hint = {
                1: ("選擇資料夾", "從左側選擇放置 Excel 資料的資料夾。"),
                2: ("勾選比較組別", "至少選擇一組，完成後按下一步。"),
                3: ("製作誤差區域圖", "確認左側設定，再按製圖按鈕。"),
            }[self._current_step]
            if self._busy:
                heading, hint = "正在分析資料…", "製圖完成後，這裡會顯示平均曲線與誤差範圍。"
            self.ax.text(.5, .55, heading, fontsize=22, color="#344054", ha="center", transform=self.ax.transAxes)
            self.ax.text(.5, .45, hint, fontsize=12, color="#667085", ha="center", transform=self.ax.transAxes)
        if self._current_step == 3 and self._payload and not self._settings_dirty:
            self.report_button.pack(side=tk.RIGHT, padx=(10, 0))
        # ax.clear does not restore axis visibility after an empty preview.
        if plot_ready:
            self.ax.set_axis_on()
        self.canvas.draw_idle()

    def edit_appearance(self) -> None:
        if self._busy or not self._payload or not self._payload.groups or self._settings_dirty:
            return
        dialog = tk.Toplevel(self)
        dialog.title("圖例與顏色")
        dialog.transient(self)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="選擇曲線，再按「挑選顏色」；開啟同組同色後，可在下表預覽分組。", wraplength=560).pack(anchor=tk.W, pady=(0, 8))
        table_frame = ttk.Frame(frame)
        table_frame.pack(fill=tk.BOTH, expand=True)
        table = ttk.Treeview(table_frame, columns=("group", "color_group", "color"), show="headings", height=8, selectmode="browse")
        table.heading("group", text="組別／圖例名稱")
        table.heading("color_group", text="同色組")
        table.heading("color", text="顏色")
        table.column("group", width=300)
        table.column("color_group", width=150)
        table.column("color", width=90, stretch=False)
        table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=table.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        table.configure(yscrollcommand=scroll.set)
        draft_colors = dict(self._appearance.group_colors)
        draft_parent_colors = dict(self._appearance.parent_colors)
        draft_folder_colors = dict(self._appearance.folder_colors)
        show_error_label = tk.BooleanVar(value=self._appearance.show_error_label)
        same_group_color = tk.BooleanVar(value=self._appearance.same_group_color)
        color_basis = tk.StringVar(value=next(label for label, value in COLOR_GROUP_OPTIONS.items() if value == self._appearance.color_group_by))
        row_names = {}
        displayed_colors = resolve_group_colors(self._payload.groups, self._appearance, self._payload.root_path)
        for group in self._payload.groups:
            name = color_group_name(group.group_name, self._payload.root_path, self._appearance.color_group_by) if same_group_color.get() else "—"
            row = table.insert("", tk.END, values=(group.legend_label or group.group_name, name, displayed_colors[group.group_name]))
            row_names[row] = group.group_name
        if table.get_children():
            table.selection_set(table.get_children()[0])

        def refresh_colors() -> None:
            basis = COLOR_GROUP_OPTIONS[color_basis.get()]
            preview = replace(self._appearance, group_colors=draft_colors, parent_colors=draft_parent_colors, folder_colors=draft_folder_colors, same_group_color=same_group_color.get(), color_group_by=basis)
            displayed_colors.update(resolve_group_colors(self._payload.groups, preview, self._payload.root_path))
            for row, name in row_names.items():
                table.set(row, "color", displayed_colors[name])
                table.set(row, "color_group", color_group_name(name, self._payload.root_path, basis) if same_group_color.get() else "—")
            basis_combo.configure(state="readonly" if same_group_color.get() else "disabled")

        def choose_color() -> None:
            selected = table.selection()
            if not selected:
                return
            row = selected[0]
            name = row_names[row]
            _rgb, color = colorchooser.askcolor(parent=dialog, color=displayed_colors[name], title="選擇曲線與陰影顏色")
            if color:
                if same_group_color.get():
                    basis = COLOR_GROUP_OPTIONS[color_basis.get()]
                    custom = draft_folder_colors if basis == "excel_folder" else draft_parent_colors
                    custom[color_group_name(name, self._payload.root_path, basis)] = color
                else:
                    draft_colors[name] = color
                refresh_colors()

        ttk.Button(frame, text="挑選顏色…", command=choose_color).pack(anchor=tk.W, pady=(8, 12))
        options = ttk.Frame(frame)
        options.pack(fill=tk.X)
        position = tk.StringVar(value=next(label for label, value in LEGEND_POSITIONS.items() if value == self._appearance.legend_position))
        columns = tk.StringVar(value=str(self._appearance.legend_columns))
        font_size = tk.StringVar(value=str(self._appearance.legend_font_size))
        for row, (label, variable, values) in enumerate((
            ("圖例位置", position, tuple(LEGEND_POSITIONS)),
            ("圖例欄數", columns, ("1", "2", "3", "4")),
            ("圖例字級", font_size, tuple(str(size) for size in range(6, 19))),
        )):
            ttk.Label(options, text=label).grid(row=row, column=0, sticky="w", pady=4)
            ttk.Combobox(options, textvariable=variable, values=values, state="readonly", width=18).grid(row=row, column=1, sticky="ew", padx=(16, 0), pady=4)
        ttk.Checkbutton(frame, text="顯示 Mean ± SEM／SD 文字", variable=show_error_label).pack(anchor=tk.W, pady=(10, 4))
        ttk.Checkbutton(frame, text="同組使用同一顏色", variable=same_group_color, command=refresh_colors).pack(anchor=tk.W)
        basis_row = ttk.Frame(frame)
        basis_row.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(basis_row, text="分組依據").pack(side=tk.LEFT)
        basis_combo = ttk.Combobox(basis_row, textvariable=color_basis, values=tuple(COLOR_GROUP_OPTIONS), state="readonly" if same_group_color.get() else "disabled", width=24)
        basis_combo.pack(side=tk.LEFT, padx=(12, 0))
        basis_combo.bind("<<ComboboxSelected>>", lambda _: refresh_colors())
        ttk.Label(frame, text="依名稱相同者配色，支援任意文字與單位；各曲線仍獨立計算。", foreground=self._hint_color, wraplength=540).pack(anchor=tk.W, pady=(4, 0))
        ttk.Label(frame, text="套用後不需重新讀取 Excel；圖例也可直接拖曳。\n圖片匯出會保留目前的顏色與圖例位置。", foreground=self._hint_color).pack(anchor=tk.W, pady=(12, 8))

        def apply() -> None:
            self._appearance = PlotAppearance(
                group_colors=dict(draft_colors),
                legend_position=LEGEND_POSITIONS[position.get()],
                legend_columns=int(columns.get()),
                legend_font_size=int(font_size.get()),
                show_error_label=show_error_label.get(),
                same_group_color=same_group_color.get(),
                parent_colors=dict(draft_parent_colors),
                folder_colors=dict(draft_folder_colors),
                color_group_by=COLOR_GROUP_OPTIONS[color_basis.get()],
            )
            self._redraw()
            self.status_var.set("已套用圖例與顏色；可直接匯出圖片。")

        def reset() -> None:
            draft_colors.clear()
            draft_parent_colors.clear()
            draft_folder_colors.clear()
            show_error_label.set(False)
            same_group_color.set(False)
            color_basis.set("上層資料夾名稱")
            position.set("右側圖外")
            columns.set("1")
            font_size.set("9")
            refresh_colors()
            apply()

        buttons = ttk.Frame(frame)
        buttons.pack(fill=tk.X)
        ttk.Button(buttons, text="恢復預設", command=reset).pack(side=tk.LEFT)
        ttk.Button(buttons, text="套用", command=apply).pack(side=tk.RIGHT)
        ttk.Button(buttons, text="關閉", command=dialog.destroy).pack(side=tk.RIGHT, padx=8)

    def show_report(self) -> None:
        if not self._payload:
            return
        payload = self._payload
        lines = [f"資料根目錄：{payload.root_path}", "每個檔案視為一筆獨立重複樣本。", "各組僅使用全部納入樣本共有的時間範圍；不補值、不延伸尾端。", "SD 使用樣本標準差（ddof=1）；SEM = SD / √n。", f"取樣間隔：{payload.settings.sample_interval_sec:g} s；baseline：{payload.settings.baseline_duration_sec:g} s", f"施加時間：{payload.settings.drug_apply_time_sec:g} ± {payload.settings.drug_apply_tolerance_sec:g} s", ""]
        for group in payload.groups:
            lines.extend((f"{group.group_name}：n={group.n}；時間 {group.time_sec[0]:g} ～ {group.time_sec[-1]:g} s", "納入：" + ", ".join(group.sample_names), ""))
        lines.append("注意事項")
        lines.extend(payload.warnings or ("無。",))
        lines.extend(("", f"本次資料處理耗時：{self._last_elapsed_sec:.2f} 秒（不含圖形繪製）", "讀取完成耗時包含 Excel 解析或記憶體快取查詢，不能單獨視為雲端下載時間。", *self._timing_lines))
        dialog = tk.Toplevel(self)
        dialog.title("分析明細／注意事項")
        dialog.geometry("760x500")
        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(frame)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        text = tk.Text(frame, wrap="word", yscrollcommand=scroll.set)
        text.pack(fill=tk.BOTH, expand=True)
        scroll.configure(command=text.yview)
        text.insert("1.0", "\n".join(lines))
        text.configure(state="disabled")

    def export_plot(self) -> None:
        if not self._payload or not self._payload.groups or self._settings_dirty:
            return
        path = filedialog.asksaveasfilename(parent=self, title="匯出圖片", initialfile="cap-s-sem.png", defaultextension=".png", filetypes=EXPORT_FILETYPES[:3])
        if path:
            try:
                self.fig.savefig(path, dpi=300, bbox_inches="tight")
            except Exception as exc:
                messagebox.showerror("匯出失敗", str(exc), parent=self)
                return
            self.status_var.set(f"已匯出圖片：{os.path.basename(path)}")

    def export_csv(self) -> None:
        if not self._payload or not self._payload.groups or self._settings_dirty:
            return
        path = filedialog.asksaveasfilename(parent=self, title="匯出平均值與誤差範圍", initialfile="cap-s-curves.csv", defaultextension=".csv", filetypes=(("CSV", "*.csv"),))
        if path:
            try:
                write_error_band_csv(self._payload, path, self.band_var.get())
            except OSError as exc:
                messagebox.showerror("匯出失敗", str(exc), parent=self)
                return
            self.status_var.set(f"已匯出統計曲線：{os.path.basename(path)}")

    def _close(self) -> None:
        self._cancel_event.set()
        if self._poll_id is not None:
            self.after_cancel(self._poll_id)
        self.destroy()
