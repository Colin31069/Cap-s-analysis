from __future__ import annotations

import os
import threading
import tkinter as tk
from itertools import cycle
from tkinter import filedialog, messagebox, simpledialog, ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from matplotlib.patches import Patch

from .analysis import pbs_pre_roll_window_indices, read_xlsx_single, split_index_from_time_sec
from .config import (
    COLOR_PALETTE,
    DATA_COL,
    DEFAULT_BASELINE_DURATION_SEC,
    DEFAULT_BASELINE_WARNING_THRESHOLD_PCT,
    DEFAULT_MEDICINE_COUNT,
    DEFAULT_DRUG_APPLY_TIME_SEC,
    DEFAULT_DRUG_APPLY_TOLERANCE_SEC,
    DIXON_Q_EXCLUSION_METHOD,
    DEFAULT_ROOT_PATH,
    DT_SEC,
    MAX_MEDICINES,
    PBS_BASELINE_PRE_ROLL_POINTS,
)
from .exclusions import current_excluded_samples, max_excluded_samples
from .filesystem import get_subfolders, list_xlsx_files, normalize_directory_path, resolve_directory_path
from .metadata import (
    default_experiment_metadata,
    curve_split_for_file,
    drop_time_override_for_file,
    load_experiment_metadata,
    metadata_file_path,
    save_experiment_metadata,
)
from .models import DropTimeOverride, CurveSplit, ExcludedSample, ExperimentMetadata, MedicineEntry, PlotPayload, PlotItem, PlotSettings, StatisticalAnalysisResult
from .plotting import build_overlay_legend_group_label, build_plot_payload
from .statistics import (
    build_dixon_q_review_for_group,
    build_statistical_analysis,
    format_dixon_exclusion_reason,
    format_statistics_result,
    write_statistics_csv,
)

OVERLAY_LEGEND_FONT_SIZE = 22


EXPORT_FILETYPES = (
    ("PNG image", "*.png"),
    ("PDF document", "*.pdf"),
    ("SVG vector image", "*.svg"),
    ("TIFF image", "*.tif *.tiff"),
    ("JPEG image", "*.jpg *.jpeg"),
    ("WebP image", "*.webp"),
)
SUPPORTED_EXPORT_EXTENSIONS = {
    ".eps",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".pgf",
    ".png",
    ".ps",
    ".raw",
    ".rgba",
    ".svg",
    ".svgz",
    ".tif",
    ".tiff",
    ".webp",
}
DEFAULT_EXPORT_EXTENSION = ".png"


class RawDataViewerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Raw Data Viewer - v3.5")
        self.geometry("1400x900")

        self.root_path = DEFAULT_ROOT_PATH
        self.root_path_var = tk.StringVar(value=self.root_path)

        self.show_drop_lines_var = tk.BooleanVar(value=True)
        self.show_grid_var = tk.BooleanVar(value=True)
        self.overlay_mode_var = tk.BooleanVar(value=False)
        self.display_mode_var = tk.StringVar(value="Norm")
        self.segment_mode_var = tk.StringVar(value="pbs")
        self.group_color_var = tk.BooleanVar(value=True)
        self.baseline_duration_var = tk.StringVar(value=f"{DEFAULT_BASELINE_DURATION_SEC:.1f}")
        self.drug_apply_time_var = tk.StringVar(value=f"{DEFAULT_DRUG_APPLY_TIME_SEC:.1f}")
        self.drug_apply_tolerance_var = tk.StringVar(value=f"{DEFAULT_DRUG_APPLY_TOLERANCE_SEC:.1f}")
        self.baseline_warning_threshold_var = tk.StringVar(
            value=f"{DEFAULT_BASELINE_WARNING_THRESHOLD_PCT:.1f}"
        )

        self.legend_style_var = tk.StringVar(value="Detailed")
        self.leg_show_base = tk.BooleanVar(value=True)
        self.leg_show_delta = tk.BooleanVar(value=False)
        self.experiment_var = tk.StringVar(value="")
        self.custom_plot_title_var = tk.StringVar(value="")
        self.medicine_count_var = tk.StringVar(value=str(DEFAULT_MEDICINE_COUNT))
        self.medicine_name_vars = [tk.StringVar(value="") for _ in range(MAX_MEDICINES)]
        self.medicine_dose_vars = [tk.StringVar(value="") for _ in range(MAX_MEDICINES)]
        self.sample_exclusion_status_var = tk.StringVar(value="")

        self.color_cycler = cycle(COLOR_PALETTE)
        self.is_plotting = False
        self._control_widgets: list[tk.Widget] = []
        self._metadata_widgets: list[tk.Widget] = []
        self._medicine_row_frames: list[ttk.LabelFrame] = []
        self._sample_file_names: list[str] = []
        self._excluded_samples: list[ExcludedSample] = []
        self._curve_splits: list[CurveSplit] = []
        self._drop_time_overrides: list[DropTimeOverride] = []
        self._dixon_suggested_reasons: dict[str, str] = {}
        self._is_loading_metadata = False
        self._metadata_expanded = False
        self._metadata_toggle_text = tk.StringVar(value="")
        self._warning_dialog: tk.Toplevel | None = None
        self._last_default_plot_title = ""
        self._overlay_legend_entries: dict[str, object] = {}
        self._split_pick_sample_file = ""
        self._split_pick_connection_id: int | None = None
        self._last_plot_payload: PlotPayload | None = None
        self._drop_adjust_item: PlotItem | None = None
        self._drop_adjust_line = None
        self._drop_adjust_press_connection_id: int | None = None
        self._drop_adjust_motion_connection_id: int | None = None
        self._drop_adjust_release_connection_id: int | None = None
        self._drop_adjust_is_dragging = False
        self._drop_adjust_current_x = 0.0
        self._plot_line_colors_by_file: dict[str, object] = {}

        self.create_widgets()
        self.custom_plot_title_var.trace_add("write", self._on_custom_plot_title_changed)
        self.refresh_folder_structure(show_errors=False)

    def create_widgets(self) -> None:
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        control_panel = ttk.LabelFrame(main_frame, text="Experiment Selection", padding="8")
        control_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        self.control_canvas = tk.Canvas(control_panel, width=310, highlightthickness=0, borderwidth=0)
        control_scrollbar = ttk.Scrollbar(control_panel, orient=tk.VERTICAL, command=self.control_canvas.yview)
        controls_frame = ttk.Frame(self.control_canvas)

        controls_frame.bind(
            "<Configure>",
            lambda _event: self.control_canvas.configure(scrollregion=self.control_canvas.bbox("all")),
        )
        self.control_canvas.create_window((0, 0), window=controls_frame, anchor="nw")
        self.control_canvas.configure(yscrollcommand=control_scrollbar.set)
        self.control_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        control_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        controls_frame.bind("<Enter>", lambda _event: self.control_canvas.bind_all("<MouseWheel>", self._on_control_mousewheel))
        controls_frame.bind("<Leave>", lambda _event: self.control_canvas.unbind_all("<MouseWheel>"))

        ttk.Label(controls_frame, text="Root Path").pack(anchor=tk.W)
        root_path_frame = ttk.Frame(controls_frame)
        root_path_frame.pack(fill=tk.X, pady=(0, 8))

        self.root_path_entry = ttk.Entry(root_path_frame, textvariable=self.root_path_var)
        self.root_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.root_path_entry.bind("<Return>", self.refresh_folder_structure)
        self._control_widgets.append(self.root_path_entry)

        self.browse_root_btn = ttk.Button(root_path_frame, text="Browse...", command=self.select_root)
        self.browse_root_btn.pack(side=tk.RIGHT)
        self._control_widgets.append(self.browse_root_btn)

        ttk.Label(controls_frame, text="Experiment Folder").pack(anchor=tk.W)
        self.experiment_list = self._create_selection_list(controls_frame, self._on_experiment_selected, height=8)
        self.experiment_list.pack(fill=tk.X, pady=(0, 5))

        self.refresh_btn = ttk.Button(controls_frame, text="↻ Refresh List", command=self.refresh_folder_structure)
        self.refresh_btn.pack(fill=tk.X, pady=5)
        self._control_widgets.append(self.refresh_btn)

        ttk.Label(controls_frame, text="Plot Title (optional)").pack(anchor=tk.W, pady=(8, 0))
        self.custom_plot_title_entry = ttk.Entry(
            controls_frame,
            textvariable=self.custom_plot_title_var,
        )
        self.custom_plot_title_entry.pack(fill=tk.X, pady=(2, 0))
        self._control_widgets.append(self.custom_plot_title_entry)

        ttk.Separator(controls_frame, orient="horizontal").pack(fill="x", pady=10)

        self.metadata_section = ttk.Frame(controls_frame)
        self.metadata_section.pack(fill=tk.X, pady=5)

        self.metadata_toggle_btn = ttk.Button(
            self.metadata_section,
            textvariable=self._metadata_toggle_text,
            command=self._toggle_metadata_section,
        )
        self.metadata_toggle_btn.pack(fill=tk.X)
        self._control_widgets.append(self.metadata_toggle_btn)

        self.metadata_frame = ttk.LabelFrame(self.metadata_section, padding=5)
        self.metadata_frame.pack(fill=tk.X, pady=(5, 0))

        count_frame = ttk.Frame(self.metadata_frame)
        count_frame.pack(fill=tk.X)
        ttk.Label(count_frame, text="Medicine Count").pack(side=tk.LEFT)
        self.medicine_count_combo = ttk.Combobox(
            count_frame,
            textvariable=self.medicine_count_var,
            values=[str(index) for index in range(MAX_MEDICINES + 1)],
            state="readonly",
            width=5,
        )
        self.medicine_count_combo.pack(side=tk.RIGHT)
        self.medicine_count_combo.bind("<<ComboboxSelected>>", self._on_medicine_count_changed)
        self._metadata_widgets.append(self.medicine_count_combo)

        self.medicine_rows_container = ttk.Frame(self.metadata_frame)
        self.medicine_rows_container.pack(fill=tk.X, pady=(8, 0))
        self._build_medicine_rows()
        self._set_visible_medicine_rows(DEFAULT_MEDICINE_COUNT)
        self._set_metadata_expanded(False)

        ttk.Separator(controls_frame, orient="horizontal").pack(fill="x", pady=10)

        sample_exclusion_frame = ttk.LabelFrame(controls_frame, text="Sample Exclusion", padding=5)
        sample_exclusion_frame.pack(fill=tk.X, pady=5)

        ttk.Label(sample_exclusion_frame, textvariable=self.sample_exclusion_status_var).pack(anchor=tk.W)
        self.sample_exclusion_list = tk.Listbox(sample_exclusion_frame, height=6, exportselection=False)
        self.sample_exclusion_list.pack(fill=tk.X, pady=(4, 5))

        sample_exclusion_buttons = ttk.Frame(sample_exclusion_frame)
        sample_exclusion_buttons.pack(fill=tk.X)
        self.exclude_sample_btn = ttk.Button(
            sample_exclusion_buttons,
            text="Exclude Selected",
            command=self.exclude_selected_sample,
        )
        self.exclude_sample_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self._control_widgets.append(self.exclude_sample_btn)

        self.restore_sample_btn = ttk.Button(
            sample_exclusion_buttons,
            text="Restore Selected",
            command=self.restore_selected_sample,
        )
        self.restore_sample_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._control_widgets.append(self.restore_sample_btn)

        self.run_dixon_btn = ttk.Button(
            sample_exclusion_frame,
            text="Run Dixon Q",
            command=self.run_dixon_q_for_current_experiment,
        )
        self.run_dixon_btn.pack(fill=tk.X, pady=(5, 0))
        self._control_widgets.append(self.run_dixon_btn)
        self._refresh_sample_exclusion_list()

        ttk.Separator(controls_frame, orient="horizontal").pack(fill="x", pady=10)

        split_frame = ttk.LabelFrame(controls_frame, text="Curve Split", padding=5)
        split_frame.pack(fill=tk.X, pady=5)

        self.pick_split_btn = ttk.Button(
            split_frame,
            text="Pick Split Point",
            command=self.pick_split_for_selected_sample,
        )
        self.pick_split_btn.pack(fill=tk.X)
        self._control_widgets.append(self.pick_split_btn)

        self.clear_split_btn = ttk.Button(
            split_frame,
            text="Clear Selected Split",
            command=self.clear_split_for_selected_sample,
        )
        self.clear_split_btn.pack(fill=tk.X, pady=(5, 0))
        self._control_widgets.append(self.clear_split_btn)

        self.adjust_drop_btn = ttk.Button(
            split_frame,
            text="Adjust Drop",
            command=self.adjust_drop_for_selected_sample,
        )
        self.adjust_drop_btn.pack(fill=tk.X, pady=(8, 0))
        self._control_widgets.append(self.adjust_drop_btn)

        self.clear_drop_adjustment_btn = ttk.Button(
            split_frame,
            text="Clear Drop Adjustment",
            command=self.clear_drop_adjustment_for_selected_sample,
        )
        self.clear_drop_adjustment_btn.pack(fill=tk.X, pady=(5, 0))
        self._control_widgets.append(self.clear_drop_adjustment_btn)

        ttk.Label(split_frame, text="Plot/analysis segment").pack(anchor=tk.W, pady=(8, 0))
        self.segment_pbs_rb = ttk.Radiobutton(
            split_frame,
            text="PBS Segment",
            variable=self.segment_mode_var,
            value="pbs",
            command=self._refresh_sample_exclusion_list,
        )
        self.segment_pbs_rb.pack(anchor=tk.W)
        self._control_widgets.append(self.segment_pbs_rb)
        self.segment_lanolin_rb = ttk.Radiobutton(
            split_frame,
            text="Lanolin Segment",
            variable=self.segment_mode_var,
            value="lanolin",
            command=self._refresh_sample_exclusion_list,
        )
        self.segment_lanolin_rb.pack(anchor=tk.W)
        self._control_widgets.append(self.segment_lanolin_rb)
        self.segment_full_rb = ttk.Radiobutton(
            split_frame,
            text="Full Curve",
            variable=self.segment_mode_var,
            value="full",
            command=self._refresh_sample_exclusion_list,
        )
        self.segment_full_rb.pack(anchor=tk.W)
        self._control_widgets.append(self.segment_full_rb)

        ttk.Separator(controls_frame, orient="horizontal").pack(fill="x", pady=10)

        ttk.Label(controls_frame, text="Display Unit:").pack(anchor=tk.W)
        self.display_norm_rb = ttk.Radiobutton(
            controls_frame,
            text="Normalized (%)",
            variable=self.display_mode_var,
            value="Norm",
        )
        self.display_norm_rb.pack(anchor=tk.W)
        self._control_widgets.append(self.display_norm_rb)
        self.display_raw_rb = ttk.Radiobutton(
            controls_frame,
            text="Raw Data (pF)",
            variable=self.display_mode_var,
            value="Raw",
        )
        self.display_raw_rb.pack(anchor=tk.W)
        self._control_widgets.append(self.display_raw_rb)
        self.display_base_rb = ttk.Radiobutton(
            controls_frame,
            text="Baseline Only (Raw Baseline Window)",
            variable=self.display_mode_var,
            value="Base",
        )
        self.display_base_rb.pack(anchor=tk.W)
        self._control_widgets.append(self.display_base_rb)
        ttk.Separator(controls_frame, orient="horizontal").pack(fill="x", pady=10)

        timing_frame = ttk.LabelFrame(controls_frame, text="Timing Controls", padding=5)
        timing_frame.pack(fill=tk.X, pady=5)
        ttk.Label(timing_frame, text="Baseline Duration (s)").pack(anchor=tk.W)
        self.baseline_duration_spinbox = ttk.Spinbox(
            timing_frame,
            from_=0.1,
            to=600.0,
            increment=0.1,
            textvariable=self.baseline_duration_var,
            width=8,
        )
        self.baseline_duration_spinbox.pack(anchor=tk.W, pady=(2, 6))
        self._control_widgets.append(self.baseline_duration_spinbox)

        ttk.Label(timing_frame, text="Drug Apply Time (s)").pack(anchor=tk.W)
        self.drug_apply_time_spinbox = ttk.Spinbox(
            timing_frame,
            from_=0.0,
            to=600.0,
            increment=0.1,
            textvariable=self.drug_apply_time_var,
            width=8,
        )
        self.drug_apply_time_spinbox.pack(anchor=tk.W, pady=(2, 6))
        self._control_widgets.append(self.drug_apply_time_spinbox)

        ttk.Label(timing_frame, text="Apply Window +/- (s)").pack(anchor=tk.W)
        self.drug_apply_tolerance_spinbox = ttk.Spinbox(
            timing_frame,
            from_=0.0,
            to=600.0,
            increment=0.1,
            textvariable=self.drug_apply_tolerance_var,
            width=8,
        )
        self.drug_apply_tolerance_spinbox.pack(anchor=tk.W, pady=(2, 0))
        self._control_widgets.append(self.drug_apply_tolerance_spinbox)

        baseline_warning_frame = ttk.LabelFrame(controls_frame, text="Baseline Accuracy", padding=5)
        baseline_warning_frame.pack(fill=tk.X, pady=5)
        ttk.Label(baseline_warning_frame, text="Warning Threshold (%)").pack(anchor=tk.W)
        self.baseline_warning_spinbox = ttk.Spinbox(
            baseline_warning_frame,
            from_=0.0,
            to=100.0,
            increment=0.1,
            textvariable=self.baseline_warning_threshold_var,
            width=8,
        )
        self.baseline_warning_spinbox.pack(anchor=tk.W, pady=(2, 0))
        self._control_widgets.append(self.baseline_warning_spinbox)

        leg_frame = ttk.LabelFrame(controls_frame, text="Legend Customization", padding=5)
        leg_frame.pack(fill=tk.X, pady=5)

        self.legend_simple_rb = ttk.Radiobutton(
            leg_frame,
            text="Simple (e.g., N 1)",
            variable=self.legend_style_var,
            value="Simple",
        )
        self.legend_simple_rb.pack(anchor=tk.W)
        self._control_widgets.append(self.legend_simple_rb)
        self.legend_detailed_rb = ttk.Radiobutton(
            leg_frame,
            text="Detailed",
            variable=self.legend_style_var,
            value="Detailed",
        )
        self.legend_detailed_rb.pack(anchor=tk.W)
        self._control_widgets.append(self.legend_detailed_rb)

        detail_frame = ttk.Frame(leg_frame, padding=(15, 0, 0, 0))
        detail_frame.pack(fill=tk.X)
        self.leg_base_cb = ttk.Checkbutton(detail_frame, text="Baseline (Avg)", variable=self.leg_show_base)
        self.leg_base_cb.pack(anchor=tk.W)
        self._control_widgets.append(self.leg_base_cb)
        self.leg_delta_cb = ttk.Checkbutton(detail_frame, text="Delta (Δ)", variable=self.leg_show_delta)
        self.leg_delta_cb.pack(anchor=tk.W)
        self._control_widgets.append(self.leg_delta_cb)

        ttk.Label(controls_frame, text="Visual Options:", font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(10, 0))
        self.overlay_cb = ttk.Checkbutton(controls_frame, text="Overlay Mode", variable=self.overlay_mode_var)
        self.overlay_cb.pack(anchor=tk.W)
        self._control_widgets.append(self.overlay_cb)
        self.group_color_cb = ttk.Checkbutton(controls_frame, text="Experiment Color", variable=self.group_color_var)
        self.group_color_cb.pack(anchor=tk.W)
        self._control_widgets.append(self.group_color_cb)
        self.drop_lines_cb = ttk.Checkbutton(controls_frame, text="Show Drop Lines", variable=self.show_drop_lines_var)
        self.drop_lines_cb.pack(anchor=tk.W)
        self._control_widgets.append(self.drop_lines_cb)
        self.grid_cb = ttk.Checkbutton(
            controls_frame,
            text="Show Grid",
            variable=self.show_grid_var,
            command=self._on_grid_visibility_changed,
        )
        self.grid_cb.pack(anchor=tk.W)
        self._control_widgets.append(self.grid_cb)

        ttk.Separator(controls_frame, orient="horizontal").pack(fill="x", pady=(10, 10))
        self.plot_btn = ttk.Button(controls_frame, text="LOAD & PLOT", command=self.plot_data)
        self.plot_btn.pack(fill=tk.X, pady=(0, 5))
        self._control_widgets.append(self.plot_btn)
        self.clear_btn = ttk.Button(controls_frame, text="Clear Plot", command=self.clear_plot)
        self.clear_btn.pack(fill=tk.X, pady=5)
        self._control_widgets.append(self.clear_btn)
        self.export_btn = ttk.Button(controls_frame, text="Export Plot", command=self.export_plot)
        self.export_btn.pack(fill=tk.X, pady=5)
        self._control_widgets.append(self.export_btn)
        self.statistics_btn = ttk.Button(controls_frame, text="Statistics", command=self.open_statistics_dialog)
        self.statistics_btn.pack(fill=tk.X, pady=5)
        self._control_widgets.append(self.statistics_btn)

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

    def _build_medicine_rows(self) -> None:
        for index in range(MAX_MEDICINES):
            row_frame = ttk.LabelFrame(self.medicine_rows_container, text=f"Medicine {index + 1}", padding=5)

            ttk.Label(row_frame, text="Name").pack(anchor=tk.W)
            name_entry = ttk.Entry(row_frame, textvariable=self.medicine_name_vars[index])
            name_entry.pack(fill=tk.X, pady=(0, 5))
            name_entry.bind("<FocusOut>", self._on_metadata_field_blur)

            ttk.Label(row_frame, text="Dose").pack(anchor=tk.W)
            dose_entry = ttk.Entry(row_frame, textvariable=self.medicine_dose_vars[index])
            dose_entry.pack(fill=tk.X)
            dose_entry.bind("<FocusOut>", self._on_metadata_field_blur)

            self._medicine_row_frames.append(row_frame)
            self._metadata_widgets.extend([name_entry, dose_entry])

    def set_controls_enabled(self, enabled: bool) -> None:
        self.experiment_list.configure(state="normal" if enabled else "disabled")
        self.sample_exclusion_list.configure(state="normal" if enabled else "disabled")

        for widget in self._control_widgets + self._metadata_widgets:
            try:
                if enabled:
                    widget.state(["!disabled"])
                else:
                    widget.state(["disabled"])
            except tk.TclError:
                pass

        self.update_idletasks()

    def _create_selection_list(self, parent: ttk.Frame, callback, height: int = 2) -> tk.Listbox:
        listbox = tk.Listbox(parent, height=height, exportselection=False)
        listbox.bind("<<ListboxSelect>>", callback if callback is not None else lambda _event: None)
        return listbox

    def _update_metadata_toggle_label(self) -> None:
        prefix = "[-]" if self._metadata_expanded else "[+]"
        self._metadata_toggle_text.set(f"{prefix} Medicine Metadata")

    def _set_metadata_expanded(self, expanded: bool) -> None:
        self._metadata_expanded = expanded
        if expanded:
            if not self.metadata_frame.winfo_manager():
                self.metadata_frame.pack(fill=tk.X, pady=(5, 0))
        elif self.metadata_frame.winfo_manager():
            self.metadata_frame.pack_forget()
        self._update_metadata_toggle_label()

    def _toggle_metadata_section(self) -> None:
        self._set_metadata_expanded(not self._metadata_expanded)

    def _on_control_mousewheel(self, event) -> None:
        delta = 0
        if event.delta:
            delta = -1 * int(event.delta / 120)
        if delta:
            self.control_canvas.yview_scroll(delta, "units")

    def _set_list_values(self, listbox: tk.Listbox, variable: tk.StringVar, values: list[str]) -> None:
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

    def _selected_list_value(self, listbox: tk.Listbox) -> str:
        selection = listbox.curselection()
        if not selection:
            return ""
        return listbox.get(selection[0])

    def _current_experiment_dir(self) -> str:
        experiment_name = self.experiment_var.get().strip()
        if not experiment_name:
            return ""
        return os.path.join(self.root_path, experiment_name)

    def _current_sample_files(self) -> list[str]:
        folder_path = self._current_experiment_dir()
        if not folder_path or not os.path.isdir(folder_path):
            return []
        return list_xlsx_files(folder_path)

    def _get_medicine_count(self) -> int:
        try:
            return max(0, min(MAX_MEDICINES, int(self.medicine_count_var.get())))
        except (TypeError, ValueError):
            return DEFAULT_MEDICINE_COUNT

    def _set_visible_medicine_rows(self, count: int) -> None:
        for index, row_frame in enumerate(self._medicine_row_frames):
            if index < count:
                if not row_frame.winfo_manager():
                    row_frame.pack(fill=tk.X, pady=3)
            elif row_frame.winfo_manager():
                row_frame.pack_forget()

    def _clear_metadata_editor(self) -> None:
        self._apply_metadata_to_editor(default_experiment_metadata())

    def _apply_metadata_to_editor(self, metadata: ExperimentMetadata) -> None:
        self._is_loading_metadata = True
        try:
            count = max(0, min(MAX_MEDICINES, metadata.medicine_count))
            self.medicine_count_var.set(str(count))

            for name_var, dose_var in zip(self.medicine_name_vars, self.medicine_dose_vars):
                name_var.set("")
                dose_var.set("")

            for index, entry in enumerate(metadata.medicines[:count]):
                self.medicine_name_vars[index].set(entry.name)
                self.medicine_dose_vars[index].set(entry.dose)

            self._set_visible_medicine_rows(count)
            self._excluded_samples = list(metadata.excluded_samples)
            self._curve_splits = list(metadata.curve_splits)
            self._drop_time_overrides = list(metadata.drop_time_overrides)
            self._dixon_suggested_reasons.clear()
            if hasattr(self, "sample_exclusion_list"):
                self._refresh_sample_exclusion_list()
        finally:
            self._is_loading_metadata = False

    def _metadata_from_editor(self) -> ExperimentMetadata:
        count = self._get_medicine_count()
        medicines = [
            MedicineEntry(
                name=self.medicine_name_vars[index].get().strip(),
                dose=self.medicine_dose_vars[index].get().strip(),
            )
            for index in range(count)
        ]
        files = self._sample_file_names or self._current_sample_files()
        excluded_samples = current_excluded_samples(self._excluded_samples, files)
        curve_splits = self._current_curve_splits(files)
        drop_time_overrides = self._current_drop_time_overrides(files)
        return ExperimentMetadata(
            medicine_count=count,
            medicines=medicines,
            excluded_samples=excluded_samples,
            curve_splits=curve_splits,
            drop_time_overrides=drop_time_overrides,
        )

    def _current_curve_splits(self, files: list[str]) -> list[CurveSplit]:
        file_keys = {file_name.casefold() for file_name in files}
        split_by_key: dict[str, CurveSplit] = {}
        for entry in self._curve_splits:
            file_name = os.path.basename(entry.file_name.strip())
            if not file_name or file_name.casefold() not in file_keys:
                continue
            split_by_key[file_name.casefold()] = CurveSplit(
                file_name=file_name,
                split_index=max(1, int(entry.split_index)),
                split_time_sec=max(0.0, float(entry.split_time_sec)),
                left_label=entry.left_label,
                right_label=entry.right_label,
            )
        return list(split_by_key.values())

    def _current_drop_time_overrides(self, files: list[str]) -> list[DropTimeOverride]:
        file_keys = {file_name.casefold() for file_name in files}
        override_by_key: dict[tuple[str, str], DropTimeOverride] = {}
        for entry in self._drop_time_overrides:
            file_name = os.path.basename(entry.file_name.strip())
            if not file_name or file_name.casefold() not in file_keys:
                continue
            override_by_key[(file_name.casefold(), entry.segment)] = DropTimeOverride(
                file_name=file_name,
                segment=entry.segment,
                drop_time_sec=max(0.0, float(entry.drop_time_sec)),
            )
        return list(override_by_key.values())

    def _refresh_sample_exclusion_list(self) -> None:
        if not hasattr(self, "sample_exclusion_list"):
            return

        files = self._current_sample_files()
        self._sample_file_names = files
        excluded_samples = current_excluded_samples(self._excluded_samples, files)
        excluded_reason_by_file = {entry.file_name: entry.reason for entry in excluded_samples}
        max_allowed = max_excluded_samples(len(files))
        display_metadata = ExperimentMetadata(
            0,
            [],
            curve_splits=self._current_curve_splits(files),
            drop_time_overrides=self._current_drop_time_overrides(files),
        )
        current_segment = self.segment_mode_var.get()

        self.sample_exclusion_list.delete(0, tk.END)
        for file_name in files:
            excluded_entry = next((entry for entry in excluded_samples if entry.file_name == file_name), None)
            reason = excluded_reason_by_file.get(file_name)
            split_entry = curve_split_for_file(display_metadata, file_name)
            drop_override = drop_time_override_for_file(display_metadata, file_name, current_segment)
            split_suffix = f" [split {split_entry.split_time_sec:.1f}s]" if split_entry is not None else ""
            drop_suffix = " [manual drop]" if drop_override is not None else ""
            if excluded_entry is not None:
                method_suffix = " [Dixon Q]" if excluded_entry.method == DIXON_Q_EXCLUSION_METHOD else ""
                suffix = f" - {reason}" if reason else ""
                self.sample_exclusion_list.insert(tk.END, f"[OUT] {file_name}{split_suffix}{drop_suffix}{method_suffix}{suffix}")
            else:
                self.sample_exclusion_list.insert(tk.END, f"[IN]  {file_name}{split_suffix}{drop_suffix}")

        included_count = len(files) - len(excluded_samples)
        displayed_max_allowed = max(max_allowed, len(excluded_samples))
        if not files:
            self.sample_exclusion_status_var.set("No .xlsx samples")
        else:
            self.sample_exclusion_status_var.set(
                f"n={len(files)}; included={included_count}; excluded={len(excluded_samples)}/{displayed_max_allowed}"
            )

    def _selected_sample_file(self) -> str:
        selection = self.sample_exclusion_list.curselection()
        if not selection:
            return ""
        index = selection[0]
        if index < 0 or index >= len(self._sample_file_names):
            return ""
        return self._sample_file_names[index]

    def _select_sample_file(self, file_name: str) -> None:
        if file_name not in self._sample_file_names:
            self._refresh_sample_exclusion_list()
        if file_name not in self._sample_file_names:
            return
        index = self._sample_file_names.index(file_name)
        self.sample_exclusion_list.selection_clear(0, tk.END)
        self.sample_exclusion_list.selection_set(index)
        self.sample_exclusion_list.activate(index)
        self.sample_exclusion_list.see(index)

    def exclude_selected_sample(self) -> None:
        file_name = self._selected_sample_file()
        if not file_name:
            messagebox.showwarning("No Sample Selected", "Please select a sample to exclude.")
            return

        files = self._current_sample_files()
        if file_name not in files:
            self._refresh_sample_exclusion_list()
            messagebox.showwarning("Sample Missing", "The selected sample is no longer in this folder.")
            return

        excluded_samples = current_excluded_samples(self._excluded_samples, files)
        if any(entry.file_name == file_name for entry in excluded_samples):
            messagebox.showinfo("Already Excluded", f"{file_name} is already excluded.")
            return

        suggested_reason = self._dixon_suggested_reasons.get(file_name, "")
        exclusion_method = DIXON_Q_EXCLUSION_METHOD if suggested_reason else ""
        max_allowed = max_excluded_samples(len(files))
        dixon_exception_allowed = (
            exclusion_method == DIXON_Q_EXCLUSION_METHOD
            and 3 <= len(files) < 5
            and not excluded_samples
        )
        if len(excluded_samples) >= max_allowed and not dixon_exception_allowed:
            messagebox.showwarning(
                "Exclusion Limit",
                f"This folder has n={len(files)}, so at most {max_allowed} sample(s) can be excluded.",
            )
            return

        reason = simpledialog.askstring(
            "Exclude Sample",
            f"Reason for excluding {file_name} (optional):",
            parent=self,
            initialvalue=suggested_reason,
        )
        if reason is None:
            return

        self._excluded_samples = excluded_samples + [
            ExcludedSample(file_name=file_name, reason=reason.strip(), method=exclusion_method)
        ]
        self._dixon_suggested_reasons.pop(file_name, None)
        self._refresh_sample_exclusion_list()
        self._autosave_current_metadata()

    def restore_selected_sample(self) -> None:
        file_name = self._selected_sample_file()
        if not file_name:
            messagebox.showwarning("No Sample Selected", "Please select a sample to restore.")
            return

        files = self._current_sample_files()
        excluded_samples = current_excluded_samples(self._excluded_samples, files)
        if not any(entry.file_name == file_name for entry in excluded_samples):
            messagebox.showinfo("Not Excluded", f"{file_name} is already included.")
            return

        self._excluded_samples = [entry for entry in excluded_samples if entry.file_name != file_name]
        self._dixon_suggested_reasons.pop(file_name, None)
        self._refresh_sample_exclusion_list()
        self._autosave_current_metadata()

    def _disconnect_split_pick(self) -> None:
        if self._split_pick_connection_id is not None:
            self.canvas.mpl_disconnect(self._split_pick_connection_id)
            self._split_pick_connection_id = None
        self._split_pick_sample_file = ""

    def _replace_curve_split(self, curve_split: CurveSplit) -> None:
        key = curve_split.file_name.casefold()
        retained = [
            entry
            for entry in self._current_curve_splits(self._current_sample_files())
            if entry.file_name.casefold() != key
        ]
        self._curve_splits = retained + [curve_split]

    def pick_split_for_selected_sample(self) -> None:
        file_name = self._selected_sample_file()
        if not file_name:
            messagebox.showwarning("No Sample Selected", "Please select a sample before picking a split point.")
            return

        file_path = os.path.join(self._current_experiment_dir(), file_name)
        df = read_xlsx_single(file_path)
        if df is None or df.empty:
            messagebox.showerror("Load Failed", f"Could not load {file_name}.")
            return

        samples = df[DATA_COL].to_numpy(dtype=float)
        if len(samples) < 2:
            messagebox.showwarning("Too Short", "This sample needs at least two data points to split.")
            return

        self._disconnect_split_pick()
        time_sec = np.arange(len(samples), dtype=float) * DT_SEC
        self.ax.clear()
        self.ax.plot(time_sec, samples, color=COLOR_PALETTE[0], lw=1.2)
        self.ax.set_title(f"Pick split point for {file_name}", fontsize=12)
        self.ax.set_xlabel("Original Time (s)")
        self.ax.set_ylabel("Raw Capacitance (pF)")
        self._apply_grid_preference()
        self.fig.tight_layout()
        self.canvas.draw_idle()

        self._split_pick_sample_file = file_name
        self._split_pick_connection_id = self.canvas.mpl_connect("button_press_event", self._on_split_pick_click)
        messagebox.showinfo(
            "Pick Split Point",
            "Click the boundary point on the preview plot.\nLeft side will be lanolin; right side will be PBS.",
        )

    def _on_split_pick_click(self, event) -> None:
        if not self._split_pick_sample_file or event.inaxes is not self.ax or event.xdata is None:
            return

        file_name = self._split_pick_sample_file
        file_path = os.path.join(self._current_experiment_dir(), file_name)
        df = read_xlsx_single(file_path)
        if df is None or df.empty:
            self._disconnect_split_pick()
            messagebox.showerror("Load Failed", f"Could not reload {file_name}.")
            return

        sample_count = len(df[DATA_COL])
        split_index = split_index_from_time_sec(float(event.xdata), sample_count)
        split_time_sec = split_index * DT_SEC
        curve_split = CurveSplit(
            file_name=file_name,
            split_index=split_index,
            split_time_sec=split_time_sec,
        )
        self._replace_curve_split(curve_split)
        self._autosave_current_metadata()
        self._refresh_sample_exclusion_list()
        self._select_sample_file(file_name)

        pre_roll_start_index, _split_index, pre_roll_points = pbs_pre_roll_window_indices(curve_split, sample_count)
        pre_roll_start_time_sec = pre_roll_start_index * DT_SEC
        self.ax.axvspan(
            pre_roll_start_time_sec,
            split_time_sec,
            color=COLOR_PALETTE[2],
            alpha=0.18,
            label="PBS baseline pre-roll",
        )
        self.ax.axvline(split_time_sec, color="black", ls="--", alpha=0.8)
        self.canvas.draw_idle()
        self._disconnect_split_pick()
        if pre_roll_points < PBS_BASELINE_PRE_ROLL_POINTS:
            messagebox.showwarning(
                "Split Saved - Short Baseline",
                (
                    f"{file_name} split saved at {split_time_sec:.1f}s.\n\n"
                    f"PBS baseline pre-roll has {pre_roll_points}/{PBS_BASELINE_PRE_ROLL_POINTS} points before split. "
                    "This sample will still be included and marked in plot/statistics warnings."
                ),
            )
        else:
            messagebox.showinfo(
                "Split Saved",
                (
                    f"{file_name} split saved at {split_time_sec:.1f}s.\n\n"
                    f"PBS baseline pre-roll: {pre_roll_points}/{PBS_BASELINE_PRE_ROLL_POINTS} points."
                ),
            )

    def clear_split_for_selected_sample(self) -> None:
        file_name = self._selected_sample_file()
        if not file_name:
            messagebox.showwarning("No Sample Selected", "Please select a sample before clearing a split point.")
            return

        key = file_name.casefold()
        current_splits = self._current_curve_splits(self._current_sample_files())
        if not any(entry.file_name.casefold() == key for entry in current_splits):
            messagebox.showinfo("No Split", f"{file_name} has no saved split point.")
            return

        self._curve_splits = [entry for entry in current_splits if entry.file_name.casefold() != key]
        self._autosave_current_metadata()
        self._refresh_sample_exclusion_list()
        self._select_sample_file(file_name)
        messagebox.showinfo("Split Cleared", f"{file_name} split point was cleared.")

    def _disconnect_drop_adjust(self, remove_line: bool = True) -> None:
        for connection_id in (
            self._drop_adjust_press_connection_id,
            self._drop_adjust_motion_connection_id,
            self._drop_adjust_release_connection_id,
        ):
            if connection_id is not None:
                self.canvas.mpl_disconnect(connection_id)

        self._drop_adjust_press_connection_id = None
        self._drop_adjust_motion_connection_id = None
        self._drop_adjust_release_connection_id = None
        self._drop_adjust_is_dragging = False
        self._drop_adjust_item = None
        if remove_line and self._drop_adjust_line is not None:
            try:
                self._drop_adjust_line.remove()
            except ValueError:
                pass
            self._drop_adjust_line = None
            self.canvas.draw_idle()

    def _replace_drop_time_override(self, drop_override: DropTimeOverride) -> None:
        key = (drop_override.file_name.casefold(), drop_override.segment)
        retained = [
            entry
            for entry in self._current_drop_time_overrides(self._current_sample_files())
            if (entry.file_name.casefold(), entry.segment) != key
        ]
        self._drop_time_overrides = retained + [drop_override]

    def _plot_item_for_file(self, file_name: str) -> PlotItem | None:
        if self._last_plot_payload is None:
            return None
        for item in self._last_plot_payload.plot_items:
            if item.file_name == file_name:
                return item
        return None

    def adjust_drop_for_selected_sample(self) -> None:
        file_name = self._selected_sample_file()
        if not file_name:
            messagebox.showwarning("No Sample Selected", "Please select a sample before adjusting drop alignment.")
            return
        if self.display_mode_var.get() == "Base":
            messagebox.showwarning("Baseline View", "Drop alignment is not available in Baseline Only mode.")
            return

        item = self._plot_item_for_file(file_name)
        if item is None:
            messagebox.showwarning(
                "Sample Not Plotted",
                "Load a plot that includes the selected sample before adjusting drop alignment.",
            )
            return

        self._disconnect_drop_adjust()
        self._drop_adjust_item = item
        self._drop_adjust_current_x = 0.0
        color = self._plot_line_colors_by_file.get(file_name, "black")
        self._drop_adjust_line = self.ax.axvline(
            x=0.0,
            color=color,
            ls="-",
            lw=2.5,
            alpha=0.95,
        )
        self._drop_adjust_press_connection_id = self.canvas.mpl_connect("button_press_event", self._on_drop_adjust_press)
        self._drop_adjust_motion_connection_id = self.canvas.mpl_connect("motion_notify_event", self._on_drop_adjust_motion)
        self._drop_adjust_release_connection_id = self.canvas.mpl_connect("button_release_event", self._on_drop_adjust_release)
        self.canvas.draw_idle()
        messagebox.showinfo(
            "Adjust Drop",
            (
                f"Drag the highlighted drop handle for {file_name} to the true drop point.\n\n"
                "Only the plot alignment will change; statistics and Delta % stay unchanged."
            ),
        )

    def _set_drop_adjust_x(self, x_value: float) -> None:
        self._drop_adjust_current_x = float(x_value)
        if self._drop_adjust_line is not None:
            self._drop_adjust_line.set_xdata([self._drop_adjust_current_x, self._drop_adjust_current_x])
            self.canvas.draw_idle()

    def _on_drop_adjust_press(self, event) -> None:
        if self._drop_adjust_item is None or event.inaxes is not self.ax or event.xdata is None:
            return
        if getattr(event, "button", 1) != 1:
            return
        self._drop_adjust_is_dragging = True
        self._set_drop_adjust_x(float(event.xdata))

    def _on_drop_adjust_motion(self, event) -> None:
        if not self._drop_adjust_is_dragging or event.inaxes is not self.ax or event.xdata is None:
            return
        self._set_drop_adjust_x(float(event.xdata))

    def _on_drop_adjust_release(self, event) -> None:
        if self._drop_adjust_item is None or not self._drop_adjust_is_dragging:
            return
        if event.inaxes is self.ax and event.xdata is not None:
            self._set_drop_adjust_x(float(event.xdata))

        item = self._drop_adjust_item
        new_drop_time_sec = max(0.0, item.display_drop_time_sec + self._drop_adjust_current_x)
        drop_override = DropTimeOverride(
            file_name=item.file_name,
            segment=self.segment_mode_var.get(),
            drop_time_sec=new_drop_time_sec,
        )
        self._replace_drop_time_override(drop_override)
        self._autosave_current_metadata()
        self._refresh_sample_exclusion_list()
        self._select_sample_file(item.file_name)
        self._disconnect_drop_adjust(remove_line=False)
        self.plot_data()

    def clear_drop_adjustment_for_selected_sample(self) -> None:
        file_name = self._selected_sample_file()
        if not file_name:
            messagebox.showwarning("No Sample Selected", "Please select a sample before clearing drop alignment.")
            return

        segment = self.segment_mode_var.get()
        key = (file_name.casefold(), segment)
        current_overrides = self._current_drop_time_overrides(self._current_sample_files())
        if not any((entry.file_name.casefold(), entry.segment) == key for entry in current_overrides):
            messagebox.showinfo("No Drop Adjustment", f"{file_name} has no manual drop alignment for {segment}.")
            return

        self._drop_time_overrides = [
            entry
            for entry in current_overrides
            if (entry.file_name.casefold(), entry.segment) != key
        ]
        self._autosave_current_metadata()
        self._refresh_sample_exclusion_list()
        self._select_sample_file(file_name)
        self._disconnect_drop_adjust()
        if self._last_plot_payload is not None:
            self.plot_data()
        messagebox.showinfo("Drop Adjustment Cleared", f"{file_name} manual drop alignment was cleared.")

    def run_dixon_q_for_current_experiment(self) -> None:
        if self.is_plotting:
            return

        experiment_name = self.experiment_var.get().strip()
        if not experiment_name:
            messagebox.showwarning("Missing Path", "Please select an experiment folder.")
            self.experiment_list.focus_set()
            return

        target_dir = self._current_experiment_dir()
        if not os.path.isdir(target_dir):
            messagebox.showerror("Error", "Experiment folder not found.")
            self.experiment_list.focus_set()
            return

        files = list_xlsx_files(target_dir)
        if not files:
            messagebox.showinfo("Empty", "No .xlsx files found in this folder.")
            self.experiment_list.focus_set()
            return

        try:
            baseline_duration_sec, drug_apply_time_sec, drug_apply_tolerance_sec = self._get_analysis_timing_settings()
            baseline_warning_threshold_pct = self._get_baseline_warning_threshold_pct()
        except ValueError as exc:
            messagebox.showwarning("Invalid Settings", str(exc))
            return

        self._autosave_current_metadata()
        metadata = self._metadata_from_editor()

        self._set_plotting_state(True)

        def worker() -> None:
            try:
                _samples, recommendations, notes = build_dixon_q_review_for_group(
                    experiment_name,
                    target_dir,
                    metadata.excluded_samples,
                    curve_splits=metadata.curve_splits,
                    baseline_warning_threshold_pct=baseline_warning_threshold_pct,
                    baseline_duration_sec=baseline_duration_sec,
                    drug_apply_time_sec=drug_apply_time_sec,
                    drug_apply_tolerance_sec=drug_apply_tolerance_sec,
                )
                self.after(0, lambda recommendations=recommendations, notes=notes: self._apply_dixon_q_result(recommendations, notes, len(files)))
            except Exception as exc:
                self.after(0, lambda exc=exc: self._dixon_q_failed(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_dixon_q_result(self, recommendations, notes: tuple[str, ...], file_count: int) -> None:
        self._set_plotting_state(False)

        if not recommendations:
            if notes:
                self._show_warning_dialog("Dixon Q Review", ["[Dixon Q Review]", *notes, "", "No recommended exclusion."])
            else:
                messagebox.showinfo("Dixon Q Review", "No Dixon Q recommended exclusion for this experiment folder.")
            return

        recommendation = recommendations[0]
        reason = format_dixon_exclusion_reason(recommendation)
        self._dixon_suggested_reasons[recommendation.file_name] = reason
        self._refresh_sample_exclusion_list()
        self._select_sample_file(recommendation.file_name)

        lines = [
            "[Dixon Q Recommended Exclusion]",
            f"Sample: {recommendation.file_name}",
            f"Side: {recommendation.side}",
            f"Delta %: {recommendation.delta_percent:.4g}",
            f"Nearest Delta %: {recommendation.nearest_delta_percent:.4g}",
            f"Gap / range: {recommendation.gap_delta_percent:.4g} / {recommendation.range_delta_percent:.4g}",
            f"Q: {recommendation.q_statistic:.4g}",
            f"Critical value (alpha={recommendation.alpha:g}): {recommendation.critical_value:.4g}",
            "",
            "The sample has been selected in Sample Exclusion.",
            "Press Exclude Selected to save this recommendation with the Dixon Q reason.",
        ]
        if 3 <= file_count < 5:
            lines.append("Dixon Q exception: this n<5 group may exclude one Dixon-backed sample.")
        if notes:
            lines.extend(["", "Notes", *notes])
        self._show_warning_dialog("Dixon Q Recommendation", lines)

    def _dixon_q_failed(self, exc: Exception) -> None:
        self._set_plotting_state(False)
        messagebox.showerror("Dixon Q Error", f"Failed to run Dixon Q review.\n\n{exc}")

    def _autosave_current_metadata(self, show_errors: bool = True) -> bool:
        if self._is_loading_metadata:
            return False

        folder_path = self._current_experiment_dir()
        if not folder_path or not os.path.isdir(folder_path):
            return False

        try:
            save_experiment_metadata(folder_path, self._metadata_from_editor())
            return True
        except OSError as exc:
            if show_errors:
                messagebox.showwarning(
                    "Metadata Save Failed",
                    f"Could not save metadata for this experiment folder.\n\n{exc}",
                )
            return False

    def _load_selected_experiment_metadata(self) -> None:
        folder_path = self._current_experiment_dir()
        if not folder_path or not os.path.isdir(folder_path):
            self._clear_metadata_editor()
            return

        file_missing = not os.path.exists(metadata_file_path(folder_path))
        metadata, warning_message = load_experiment_metadata(folder_path)
        self._apply_metadata_to_editor(metadata)

        if file_missing or warning_message is not None:
            self._autosave_current_metadata(show_errors=False)

        if warning_message:
            messagebox.showwarning("Metadata Reset", warning_message)

    def _on_experiment_selected(self, _event=None) -> None:
        new_value = self._selected_list_value(self.experiment_list)
        if new_value == self.experiment_var.get():
            return

        self._autosave_current_metadata()
        self.experiment_var.set(new_value)
        self.custom_plot_title_var.set("")
        self._load_selected_experiment_metadata()

    def _on_medicine_count_changed(self, _event=None) -> None:
        if self._is_loading_metadata:
            return

        self._set_visible_medicine_rows(self._get_medicine_count())
        self._autosave_current_metadata()

    def _on_metadata_field_blur(self, _event=None) -> None:
        if self._is_loading_metadata:
            return
        self._autosave_current_metadata()

    def _plot_has_data(self) -> bool:
        return bool(self.ax.lines or self.ax.collections or self.ax.patches)

    def _current_plot_title(self) -> str:
        custom_title = self.custom_plot_title_var.get().strip()
        if custom_title:
            return custom_title
        return self._last_default_plot_title

    def _sync_plot_title_from_editor(self) -> None:
        if not self._last_default_plot_title or not self._plot_has_data():
            return

        self.ax.set_title(self._current_plot_title(), fontsize=12)
        self.fig.tight_layout()
        self.canvas.draw_idle()

    def _on_custom_plot_title_changed(self, *_args) -> None:
        self._sync_plot_title_from_editor()

    def _get_analysis_timing_settings(self) -> tuple[float, float, float]:
        try:
            baseline_duration_sec = float(self.baseline_duration_var.get())
            drug_apply_time_sec = float(self.drug_apply_time_var.get())
            drug_apply_tolerance_sec = float(self.drug_apply_tolerance_var.get())
        except (TypeError, ValueError) as exc:
            raise ValueError("Timing controls must contain valid numbers.") from exc

        if baseline_duration_sec <= 0:
            raise ValueError("Baseline Duration must be greater than 0 seconds.")
        if drug_apply_time_sec < 0:
            raise ValueError("Drug Apply Time must be 0 or greater.")
        if drug_apply_tolerance_sec < 0:
            raise ValueError("Apply Window +/- must be 0 or greater.")

        return baseline_duration_sec, drug_apply_time_sec, drug_apply_tolerance_sec

    def _get_baseline_warning_threshold_pct(self) -> float:
        try:
            value = float(self.baseline_warning_threshold_var.get())
        except (TypeError, ValueError) as exc:
            raise ValueError("Baseline Accuracy Threshold must be a valid number.") from exc

        if value < 0:
            raise ValueError("Baseline Accuracy Threshold must be 0 or greater.")
        return value

    def _set_plotting_state(self, plotting: bool) -> None:
        self.is_plotting = plotting
        self.set_controls_enabled(not plotting)
        self.config(cursor="watch" if plotting else "")
        self.update_idletasks()

    def select_root(self) -> None:
        initial_dir = self.root_path if os.path.isdir(self.root_path) else os.path.expanduser("~")
        folder = filedialog.askdirectory(initialdir=initial_dir)
        if folder:
            self.root_path_var.set(folder)
            self.refresh_folder_structure()

    def refresh_folder_structure(self, _event=None, show_errors: bool = True) -> bool:
        self._autosave_current_metadata()
        previous_experiment = self.experiment_var.get()

        requested_path = self.root_path_var.get()
        normalized_path = normalize_directory_path(requested_path)
        resolved_path = resolve_directory_path(requested_path)

        if resolved_path is None:
            self.root_path = normalized_path
            self.root_path_var.set(normalized_path)
            self._set_list_values(self.experiment_list, self.experiment_var, [])
            self.custom_plot_title_var.set("")
            self._clear_metadata_editor()
            if show_errors:
                if normalized_path:
                    messagebox.showwarning("Invalid Root Path", "Please paste or choose a valid root folder.")
                else:
                    messagebox.showwarning("Missing Root Path", "Please paste or choose a root folder.")
                self.root_path_entry.focus_set()
            return False

        self.root_path = resolved_path
        self.root_path_var.set(self.root_path)
        folders = get_subfolders(self.root_path)
        self._set_list_values(self.experiment_list, self.experiment_var, folders)
        if self.experiment_var.get() != previous_experiment:
            self.custom_plot_title_var.set("")
        if folders:
            self._load_selected_experiment_metadata()
        else:
            self.custom_plot_title_var.set("")
            self._clear_metadata_editor()
        return True

    def clear_plot(self) -> None:
        self._disconnect_split_pick()
        self._disconnect_drop_adjust()
        self.ax.clear()
        self._last_plot_payload = None
        self._last_default_plot_title = ""
        self.ax.set_title("Ready", fontsize=14)
        self.ax.set_xlabel("Time from Drop (s)")
        self.ax.set_ylabel("Value")
        self._apply_grid_preference()
        self.color_cycler = cycle(COLOR_PALETTE)
        self._overlay_legend_entries.clear()
        self._plot_line_colors_by_file.clear()
        self.ax.set_prop_cycle(None)
        self.canvas.draw_idle()

    def _apply_grid_preference(self) -> None:
        self.ax.grid(self.show_grid_var.get(), linestyle=":", alpha=0.6)

    def _on_grid_visibility_changed(self) -> None:
        self._apply_grid_preference()
        self.canvas.draw_idle()

    def _next_group_color(self, is_overlay: bool):
        if not is_overlay:
            return COLOR_PALETTE[0]
        return next(self.color_cycler)

    def _group_color_for_settings(self, settings: PlotSettings):
        if not settings.use_group_color:
            return None

        if settings.is_overlay:
            group_label = build_overlay_legend_group_label(settings)
            if group_label in self._overlay_legend_entries:
                return self._overlay_legend_entries[group_label]

        return self._next_group_color(settings.is_overlay)

    def plot_data(self) -> None:
        if self.is_plotting:
            return
        self._disconnect_split_pick()
        self._disconnect_drop_adjust()

        experiment_name = self.experiment_var.get().strip()
        if not experiment_name:
            messagebox.showwarning("Missing Path", "Please select an experiment folder.")
            self.experiment_list.focus_set()
            return

        target_dir = self._current_experiment_dir()
        if not os.path.exists(target_dir):
            messagebox.showerror("Error", "Experiment folder not found.")
            self.experiment_list.focus_set()
            return

        all_files = list_xlsx_files(target_dir)
        if not all_files:
            messagebox.showinfo("Empty", "No .xlsx files found in this folder.")
            self.experiment_list.focus_set()
            return

        try:
            baseline_duration_sec, drug_apply_time_sec, drug_apply_tolerance_sec = self._get_analysis_timing_settings()
        except ValueError as exc:
            messagebox.showwarning("Invalid Timing", str(exc))
            self.baseline_duration_spinbox.focus_set()
            return

        try:
            baseline_warning_threshold_pct = self._get_baseline_warning_threshold_pct()
        except ValueError as exc:
            messagebox.showwarning("Invalid Threshold", str(exc))
            self.baseline_warning_spinbox.focus_set()
            return

        self._autosave_current_metadata()
        settings = PlotSettings(
            experiment_name=experiment_name,
            target_dir=target_dir,
            all_files=all_files,
            metadata=self._metadata_from_editor(),
            is_overlay=self.overlay_mode_var.get(),
            display_mode=self.display_mode_var.get(),
            use_group_color=self.group_color_var.get(),
            show_drop_lines=self.show_drop_lines_var.get(),
            leg_style=self.legend_style_var.get(),
            show_base=self.leg_show_base.get(),
            show_delta=self.leg_show_delta.get(),
            baseline_duration_sec=baseline_duration_sec,
            drug_apply_time_sec=drug_apply_time_sec,
            drug_apply_tolerance_sec=drug_apply_tolerance_sec,
            baseline_warning_threshold_pct=baseline_warning_threshold_pct,
            custom_title=self.custom_plot_title_var.get().strip(),
            analysis_segment=self.segment_mode_var.get(),
        )
        group_color = self._group_color_for_settings(settings)

        self._set_plotting_state(True)
        threading.Thread(
            target=self._plot_data_worker,
            args=(settings, group_color),
            daemon=True,
        ).start()

    def _plot_data_worker(self, settings: PlotSettings, group_color) -> None:
        try:
            payload = build_plot_payload(settings, group_color)
            self.after(0, lambda payload=payload: self._plot_data_apply(payload))
        except Exception as exc:
            self.after(0, lambda exc=exc: self._plot_data_failed(exc))

    def _plot_data_apply(self, payload: PlotPayload) -> None:
        settings = payload.settings

        if not settings.is_overlay:
            self.clear_plot()

        self._last_plot_payload = payload
        self._last_default_plot_title = payload.title
        self.ax.set_title(self._current_plot_title(), fontsize=12)
        if settings.analysis_segment == "lanolin":
            self.ax.set_xlabel("Original Time (s)")
        else:
            self.ax.set_xlabel("Time from Drop (s)")
        self.ax.set_ylabel(payload.y_unit)
        self._apply_grid_preference()

        count = 0
        first_line_color = None
        for item in payload.plot_items:
            count += 1
            line, = self.ax.plot(
                item.x_plot,
                item.y_plot,
                label=item.label_txt,
                color=item.line_color,
                linestyle=item.line_style,
                alpha=0.8,
                lw=1.5,
            )
            if first_line_color is None:
                first_line_color = line.get_color()
            self._plot_line_colors_by_file[item.file_name] = line.get_color()

            if settings.display_mode != "Base" and settings.show_drop_lines:
                self.ax.axvline(x=item.drop_time, color=line.get_color(), ls="--", alpha=0.3)

        if count > 0:
            if not settings.is_overlay:
                self.ax.set_title(f"{self._current_plot_title()} (n={count})", fontsize=12)
            if settings.is_overlay and settings.use_group_color:
                self._update_overlay_group_legend(settings, first_line_color)
            else:
                self.ax.legend(fontsize="x-small", loc="upper left", bbox_to_anchor=(1.0, 1.0))
            self.fig.tight_layout()
            self.canvas.draw_idle()

        self._set_plotting_state(False)
        self._show_plot_warnings(payload)

    def _update_overlay_group_legend(self, settings: PlotSettings, color) -> None:
        group_label = build_overlay_legend_group_label(settings)
        if not group_label:
            return

        self._overlay_legend_entries[group_label] = color
        handles = [
            Patch(facecolor=entry_color, edgecolor=entry_color, label=entry_label)
            for entry_label, entry_color in self._overlay_legend_entries.items()
        ]
        self.ax.legend(
            handles=handles,
            fontsize=OVERLAY_LEGEND_FONT_SIZE,
            loc="upper left",
            bbox_to_anchor=(1.0, 1.0),
            handlelength=1.0,
            handleheight=1.0,
        )

    def _plot_data_failed(self, exc: Exception) -> None:
        self._set_plotting_state(False)
        self.experiment_list.focus_set()
        messagebox.showerror("Plot Error", f"Failed to load or plot data.\n\n{exc}")

    def _show_warning_dialog(self, title: str, lines: list[str]) -> None:
        if not lines:
            return

        if self._warning_dialog is not None and self._warning_dialog.winfo_exists():
            self._warning_dialog.destroy()

        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.transient(self)
        dialog.resizable(True, True)

        def close_dialog() -> None:
            if self._warning_dialog is dialog:
                self._warning_dialog = None
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", close_dialog)
        frame = ttk.Frame(dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        text_frame = ttk.Frame(frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text_widget = tk.Text(
            text_frame,
            wrap="word",
            height=min(18, max(8, len(lines) + 2)),
            yscrollcommand=scrollbar.set,
        )
        text_widget.insert("1.0", "\n".join(lines))
        text_widget.configure(state="disabled")
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.configure(command=text_widget.yview)

        ttk.Button(frame, text="Close", command=close_dialog).pack(anchor=tk.E, pady=(8, 0))
        dialog.lift()
        dialog.focus_set()
        self._warning_dialog = dialog

    def _build_baseline_warning_lines(self, payload: PlotPayload) -> list[str]:
        flagged_items = [item for item in payload.plot_items if item.baseline_warning_status != "ok"]
        if not flagged_items:
            return []

        status_labels = {"warning": "注意", "inaccurate": "不準確"}
        warning_lines = [
            "[Baseline Accuracy]",
            "The selected baseline window may already be contaminated in these files:",
            f"Threshold: {payload.settings.baseline_warning_threshold_pct:.2f}%",
            "",
        ]

        for item in flagged_items:
            details = "；".join(item.baseline_warning_details) if item.baseline_warning_details else "baseline 偏移"
            warning_lines.append(
                f"N {item.sample_name}: {status_labels[item.baseline_warning_status]} - {details}"
            )

        return warning_lines

    def _build_timing_warning_lines(self, payload: PlotPayload) -> list[str]:
        flagged_items = [item for item in payload.plot_items if item.timing_warning_details]
        if not flagged_items:
            return []

        warning_lines = [
            "[Timing Adjustments]",
            (
                f"Requested timing: baseline {payload.settings.baseline_duration_sec:.1f}s, "
                f"apply {payload.settings.drug_apply_time_sec:.1f}s +/- "
                f"{payload.settings.drug_apply_tolerance_sec:.1f}s"
            ),
            "",
        ]

        for item in flagged_items:
            warning_lines.append(f"N {item.sample_name}: {'; '.join(item.timing_warning_details)}")

        return warning_lines

    def _show_plot_warnings(self, payload: PlotPayload) -> None:
        warning_lines = self._build_baseline_warning_lines(payload)
        timing_lines = self._build_timing_warning_lines(payload)

        if warning_lines and timing_lines:
            warning_lines.append("")
        warning_lines.extend(timing_lines)
        self._show_warning_dialog("Plot Warnings", warning_lines)

    def open_statistics_dialog(self) -> None:
        resolved_root = resolve_directory_path(self.root_path_var.get())
        if resolved_root is None:
            messagebox.showwarning("Invalid Root Path", "Please paste or choose a valid root folder.")
            self.root_path_entry.focus_set()
            return

        self.root_path = resolved_root
        self.root_path_var.set(resolved_root)
        folders = get_subfolders(resolved_root)
        if not folders:
            messagebox.showinfo("No Groups", "No experiment folders were found under this root path.")
            return

        dialog = tk.Toplevel(self)
        dialog.title("Statistical Analysis")
        dialog.transient(self)
        dialog.geometry("980x680")
        dialog.resizable(True, True)

        state: dict[str, StatisticalAnalysisResult | None] = {"result": None}

        outer = ttk.Frame(dialog, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        controls = ttk.Frame(outer)
        controls.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(controls, text=f"Groups: {len(folders)} concentration folder(s)").pack(side=tk.LEFT)

        run_btn = ttk.Button(controls, text="Run One-way ANOVA")
        run_btn.pack(side=tk.LEFT, padx=(0, 6))
        export_btn = ttk.Button(controls, text="Export CSV", state="disabled")
        export_btn.pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(controls, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

        text_frame = ttk.Frame(outer)
        text_frame.pack(fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text_widget = tk.Text(
            text_frame,
            wrap="word",
            yscrollcommand=scrollbar.set,
            font=("Menlo", 11),
        )
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.configure(command=text_widget.yview)

        def set_text(content: str) -> None:
            text_widget.configure(state="normal")
            text_widget.delete("1.0", tk.END)
            text_widget.insert("1.0", content)
            text_widget.configure(state="disabled")

        def set_running(is_running: bool) -> None:
            run_btn.configure(state="disabled" if is_running else "normal")
            if is_running:
                export_btn.configure(state="disabled")
            elif state["result"] is not None:
                export_btn.configure(state="normal")

        def apply_statistics_result(result: StatisticalAnalysisResult) -> None:
            if not dialog.winfo_exists():
                return
            state["result"] = result
            set_text(format_statistics_result(result))
            set_running(False)

        def fail_statistics(exc: Exception) -> None:
            if not dialog.winfo_exists():
                return
            set_running(False)
            messagebox.showerror("Statistics Error", f"Failed to calculate statistics.\n\n{exc}", parent=dialog)

        def run_statistics() -> None:
            try:
                baseline_duration_sec, drug_apply_time_sec, drug_apply_tolerance_sec = self._get_analysis_timing_settings()
                baseline_warning_threshold_pct = self._get_baseline_warning_threshold_pct()
            except ValueError as exc:
                messagebox.showwarning("Invalid Settings", str(exc), parent=dialog)
                return

            state["result"] = None
            set_running(True)
            set_text("Running statistical analysis...\n\nThis scans every direct child folder under the current root.")

            def worker() -> None:
                try:
                    result = build_statistical_analysis(
                        resolved_root,
                        baseline_warning_threshold_pct=baseline_warning_threshold_pct,
                        baseline_duration_sec=baseline_duration_sec,
                        drug_apply_time_sec=drug_apply_time_sec,
                        drug_apply_tolerance_sec=drug_apply_tolerance_sec,
                    )
                    self.after(0, lambda result=result: apply_statistics_result(result))
                except Exception as exc:
                    self.after(0, lambda exc=exc: fail_statistics(exc))

            threading.Thread(target=worker, daemon=True).start()

        def export_statistics() -> None:
            result = state["result"]
            if result is None:
                messagebox.showwarning("No Results", "Run statistics before exporting.", parent=dialog)
                return

            path = filedialog.asksaveasfilename(
                parent=dialog,
                title="Export Statistics",
                defaultextension=".csv",
                filetypes=(("CSV file", "*.csv"), ("All files", "*.*")),
            )
            if not path:
                return
            if not path.lower().endswith(".csv"):
                path = f"{path}.csv"
            try:
                write_statistics_csv(result, path)
            except OSError as exc:
                messagebox.showerror("Export Failed", f"Could not save statistics CSV.\n\n{exc}", parent=dialog)
                return
            messagebox.showinfo("Exported", "Statistics CSV saved successfully.", parent=dialog)

        run_btn.configure(command=run_statistics)
        export_btn.configure(command=export_statistics)
        set_text(
            "Run one-way ANOVA across all concentration folders under the current root.\n\n"
            "Endpoint: Delta % = raw delta pF / each electrode baseline pF * 100.\n"
            "Grouping: each direct child folder under the current root path is one concentration group.\n"
            "This report includes descriptive statistics, robust outlier review, and one-way ANOVA.\n"
            "Outlier candidates are shown for review only and are not automatically excluded."
        )
        dialog.lift()
        run_btn.focus_set()

    def export_plot(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export Plot",
            defaultextension=DEFAULT_EXPORT_EXTENSION,
            filetypes=EXPORT_FILETYPES,
        )
        if path:
            _, extension = os.path.splitext(path)
            if extension.lower() not in SUPPORTED_EXPORT_EXTENSIONS:
                path = f"{path}{DEFAULT_EXPORT_EXTENSION}"
            self.fig.savefig(path, dpi=300, bbox_inches="tight")
            messagebox.showinfo("Exported", "Saved successfully.")
