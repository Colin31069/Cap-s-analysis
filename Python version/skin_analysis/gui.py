from __future__ import annotations

import os
import threading
import tkinter as tk
from itertools import cycle
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from .config import COLOR_PALETTE, DEFAULT_MEDICINE_COUNT, DEFAULT_ROOT_PATH, MAX_MEDICINES
from .filesystem import get_subfolders, list_xlsx_files, normalize_directory_path, resolve_directory_path
from .metadata import (
    default_experiment_metadata,
    load_experiment_metadata,
    metadata_file_path,
    save_experiment_metadata,
)
from .models import ExperimentMetadata, MedicineEntry, PlotPayload, PlotSettings
from .plotting import build_plot_payload


class RawDataViewerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Raw Data Viewer - v3.5")
        self.geometry("1400x900")

        self.root_path = DEFAULT_ROOT_PATH
        self.root_path_var = tk.StringVar(value=self.root_path)

        self.show_drop_lines_var = tk.BooleanVar(value=True)
        self.overlay_mode_var = tk.BooleanVar(value=False)
        self.display_mode_var = tk.StringVar(value="Norm")
        self.group_color_var = tk.BooleanVar(value=True)

        self.legend_style_var = tk.StringVar(value="Detailed")
        self.leg_show_base = tk.BooleanVar(value=True)
        self.leg_show_delta = tk.BooleanVar(value=False)
        self.experiment_var = tk.StringVar(value="")
        self.medicine_count_var = tk.StringVar(value=str(DEFAULT_MEDICINE_COUNT))
        self.medicine_name_vars = [tk.StringVar(value="") for _ in range(MAX_MEDICINES)]
        self.medicine_dose_vars = [tk.StringVar(value="") for _ in range(MAX_MEDICINES)]

        self.color_cycler = cycle(COLOR_PALETTE)
        self.is_plotting = False
        self._control_widgets: list[tk.Widget] = []
        self._metadata_widgets: list[tk.Widget] = []
        self._medicine_row_frames: list[ttk.LabelFrame] = []
        self._is_loading_metadata = False
        self._metadata_expanded = False
        self._metadata_toggle_text = tk.StringVar(value="")

        self.create_widgets()
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
            text="Baseline Only (Raw 20s)",
            variable=self.display_mode_var,
            value="Base",
        )
        self.display_base_rb.pack(anchor=tk.W)
        self._control_widgets.append(self.display_base_rb)
        ttk.Separator(controls_frame, orient="horizontal").pack(fill="x", pady=10)

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
        return ExperimentMetadata(medicine_count=count, medicines=medicines)

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

        requested_path = self.root_path_var.get()
        normalized_path = normalize_directory_path(requested_path)
        resolved_path = resolve_directory_path(requested_path)

        if resolved_path is None:
            self.root_path = normalized_path
            self.root_path_var.set(normalized_path)
            self._set_list_values(self.experiment_list, self.experiment_var, [])
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
        if folders:
            self._load_selected_experiment_metadata()
        else:
            self._clear_metadata_editor()
        return True

    def clear_plot(self) -> None:
        self.ax.clear()
        self.ax.set_title("Ready", fontsize=14)
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Value")
        self.ax.grid(True, linestyle=":", alpha=0.6)
        self.color_cycler = cycle(COLOR_PALETTE)
        self.ax.set_prop_cycle(None)
        self.canvas.draw_idle()

    def _next_group_color(self, is_overlay: bool):
        if not is_overlay:
            return COLOR_PALETTE[0]
        return next(self.color_cycler)

    def plot_data(self) -> None:
        if self.is_plotting:
            return

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
        )
        group_color = self._next_group_color(settings.is_overlay) if settings.use_group_color else None

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

        self.ax.set_title(payload.title, fontsize=12)
        self.ax.set_ylabel(payload.y_unit)

        count = 0
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

            if settings.display_mode != "Base" and settings.show_drop_lines:
                self.ax.axvline(x=item.drop_time, color=line.get_color(), ls="--", alpha=0.3)

        if count > 0:
            self.ax.legend(fontsize="x-small", loc="upper left", bbox_to_anchor=(1.0, 1.0))
            self.fig.tight_layout()
            self.canvas.draw_idle()

        self._set_plotting_state(False)

    def _plot_data_failed(self, exc: Exception) -> None:
        self._set_plotting_state(False)
        self.experiment_list.focus_set()
        messagebox.showerror("Plot Error", f"Failed to load or plot data.\n\n{exc}")

    def export_plot(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".png")
        if path:
            self.fig.savefig(path, dpi=300, bbox_inches="tight")
            messagebox.showinfo("Exported", "Saved successfully.")
