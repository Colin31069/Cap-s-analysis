use std::path::PathBuf;

use tauri::AppHandle;
use tauri_plugin_dialog::DialogExt;

use crate::analysis::process_single_file;
use crate::config::{COLOR_PALETTE, DEFAULT_ROOT_PATH, LINE_STYLE_CYCLE};
use crate::exclusions::{current_excluded_file_names, max_excluded_samples, dixon_q_exception_allowed};
use crate::filesystem::{get_subfolders, list_xlsx_files};
use crate::metadata::{load_experiment_metadata, save_experiment_metadata};
use crate::models::{
    AppError, ExperimentMetadata, FolderLevelsRequest, FolderLevelsResponse,
    ListSamplesResponse, PlotRequest, PlotResponse, SampleInfo,
    SaveMetadataRequest, StatisticsRequest, StatisticsResponse,
};
use crate::plotting::{build_overlay_group_label, build_plot_series, build_plot_title, display_mode_to_y_unit};
use crate::statistics::{build_statistical_analysis, format_statistics_result, statistics_result_to_csv};

fn resolve_root(root_path: &str) -> PathBuf {
    if root_path.trim().is_empty() { PathBuf::from(DEFAULT_ROOT_PATH) } else { PathBuf::from(root_path) }
}

// ── Folder navigation ──────────────────────────────────────────────────────────

#[tauri::command]
pub fn list_folder_levels(request: FolderLevelsRequest) -> Result<FolderLevelsResponse, AppError> {
    let root = resolve_root(&request.root_path);
    let l1_options = get_subfolders(&root);
    let selected_l1 = request.l1.as_ref().filter(|v| l1_options.contains(v)).cloned();
    let l2_options = selected_l1
        .as_ref()
        .map(|l1| get_subfolders(&root.join(l1)))
        .unwrap_or_default();
    let selected_l2 = request.l2.as_ref().filter(|v| l2_options.contains(v)).cloned();
    let l3_options = match (selected_l1.as_ref(), selected_l2.as_ref()) {
        (Some(l1), Some(l2)) => get_subfolders(&root.join(l1).join(l2)),
        _ => Vec::new(),
    };
    Ok(FolderLevelsResponse { l1_options, l2_options, l3_options })
}

// ── Metadata ───────────────────────────────────────────────────────────────────

#[tauri::command]
pub fn load_metadata(folder_path: String) -> Result<ExperimentMetadata, AppError> {
    let path = PathBuf::from(&folder_path);
    if !path.is_dir() {
        return Err(AppError::new("not_a_directory", format!("{folder_path} is not a directory.")));
    }
    let (metadata, warning) = load_experiment_metadata(&path);
    if let Some(w) = warning {
        eprintln!("metadata warning: {w}");
    }
    Ok(metadata)
}

#[tauri::command]
pub fn save_metadata(request: SaveMetadataRequest) -> Result<(), AppError> {
    let path = PathBuf::from(&request.folder_path);
    if !path.is_dir() {
        return Err(AppError::new("not_a_directory", format!("{} is not a directory.", request.folder_path)));
    }
    save_experiment_metadata(&path, &request.metadata)
}

// ── Sample list ────────────────────────────────────────────────────────────────

#[tauri::command]
pub fn list_samples_in_folder(
    root_path: String,
    l1: String,
    l2: String,
    l3: String,
) -> Result<ListSamplesResponse, AppError> {
    let target = resolve_root(&root_path).join(&l1).join(&l2).join(&l3);
    if !target.is_dir() {
        return Err(AppError::new("folder_not_found", "Folder not found."));
    }
    let all_files = list_xlsx_files(&target);
    let (metadata, _) = load_experiment_metadata(&target);
    let excluded_names = current_excluded_file_names(&metadata.excluded_samples, &all_files);

    let samples: Vec<SampleInfo> = all_files
        .iter()
        .map(|f| {
            let included = !excluded_names.contains(f);
            let excl_entry = metadata.excluded_samples.iter().find(|e| e.file_name.eq_ignore_ascii_case(f));
            SampleInfo {
                file_name: f.clone(),
                sample_name: std::path::Path::new(f)
                    .file_stem()
                    .and_then(|s| s.to_str())
                    .unwrap_or(f)
                    .to_string(),
                included,
                reason: excl_entry.map(|e| e.reason.clone()).unwrap_or_default(),
                method: excl_entry.map(|e| e.method.clone()).unwrap_or_default(),
            }
        })
        .collect();

    let max_exclusions = max_excluded_samples(all_files.len());
    let current_exclusions = excluded_names.len();
    let dixon_exception_available = dixon_q_exception_allowed(all_files.len());

    Ok(ListSamplesResponse {
        samples,
        max_exclusions,
        current_exclusions,
        dixon_exception_available,
        metadata,
    })
}

// ── Plot ───────────────────────────────────────────────────────────────────────

#[tauri::command]
pub fn build_plot_payload(request: PlotRequest) -> Result<PlotResponse, AppError> {
    if request.l1.is_empty() || request.l2.is_empty() || request.l3.is_empty() {
        return Err(AppError::new("missing_path", "Please select all folder levels before plotting."));
    }
    let root = resolve_root(&request.root_path);
    let target_dir = root.join(&request.l1).join(&request.l2).join(&request.l3);
    if !target_dir.is_dir() {
        return Err(AppError::new("folder_not_found", "Folder not found."));
    }

    let all_files = list_xlsx_files(&target_dir);
    if all_files.is_empty() {
        return Err(AppError::new("no_files", "No .xlsx files found in this folder."));
    }

    let (metadata, _) = load_experiment_metadata(&target_dir);
    let excluded_names = current_excluded_file_names(&metadata.excluded_samples, &all_files);
    let params = request.analysis_params();

    let group_color: Option<String> = if request.use_group_color {
        Some(request.group_color.clone().unwrap_or_else(|| COLOR_PALETTE[0].to_string()))
    } else {
        None
    };

    let is_overlay_with_group_color = request.overlay && request.use_group_color;
    let mut series = Vec::new();
    let mut baseline_warning_count = 0usize;
    let mut timing_warning_count = 0usize;
    let mut line_style_idx = 0usize;

    for file_name in &all_files {
        if excluded_names.contains(file_name) { continue; }
        let file_path = target_dir.join(file_name);
        let Some(signal) = process_single_file(&file_path, &params) else { continue };

        let line_style = if request.use_group_color {
            LINE_STYLE_CYCLE[line_style_idx % LINE_STYLE_CYCLE.len()]
        } else { "-" };
        line_style_idx += 1;

        let sample_name = std::path::Path::new(file_name)
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or(file_name);

        if signal.baseline_warning_status != "ok" { baseline_warning_count += 1; }
        if !signal.timing_warning_details.is_empty() { timing_warning_count += 1; }

        series.push(build_plot_series(&signal, sample_name, &request, line_style, group_color.clone(), is_overlay_with_group_color));
    }

    // If overlay + group_color, add one invisible "group" trace for the legend swatch
    if is_overlay_with_group_color && !series.is_empty() {
        let group_label = build_overlay_group_label(&request.l3, &metadata);
        series.push(crate::models::PlotSeries {
            sample_name: "__group_legend__".to_string(),
            x: vec![],
            y: vec![],
            drop_time: 0.0,
            line_style: "-".to_string(),
            color: group_color.clone(),
            legend_label: group_label,
            baseline_warning_status: "ok".to_string(),
            timing_warning_details: Vec::new(),
            drop_detection_source: "window".to_string(),
        });
    }

    let title = build_plot_title(&request.l3, &metadata, &request.custom_title);

    Ok(PlotResponse {
        title,
        y_unit: display_mode_to_y_unit(&request.display_mode),
        series,
        settings: request,
        baseline_warning_count,
        timing_warning_count,
    })
}

// ── Statistics ─────────────────────────────────────────────────────────────────

#[tauri::command]
pub fn run_statistics(request: StatisticsRequest) -> Result<StatisticsResponse, AppError> {
    if request.l1.is_empty() || request.l2.is_empty() {
        return Err(AppError::new("missing_path", "Please select L1 and L2 folder levels."));
    }
    let root = resolve_root(&request.root_path);
    let stats_root = root.join(&request.l1).join(&request.l2);
    if !stats_root.is_dir() {
        return Err(AppError::new("folder_not_found", "The selected folder does not exist."));
    }
    let root_path_label = format!("{} / {} / {}", request.root_path, request.l1, request.l2);
    let params = request.analysis_params();
    let result = build_statistical_analysis(&stats_root, &root_path_label, &params);
    Ok(StatisticsResponse {
        text: format_statistics_result(&result),
        csv: statistics_result_to_csv(&result),
    })
}

// ── Export ─────────────────────────────────────────────────────────────────────

#[tauri::command]
pub fn choose_export_path(
    app: AppHandle,
    suggested_name: Option<String>,
) -> Result<Option<String>, AppError> {
    let file_name = suggested_name.unwrap_or_else(|| "skin-analysis-plot.png".to_string());
    let selected = app
        .dialog()
        .file()
        .add_filter("PNG image", &["png"])
        .set_file_name(&file_name)
        .blocking_save_file();
    let path = selected
        .map(|fp| fp.into_path())
        .transpose()
        .map_err(|e| AppError::new("dialog_error", e.to_string()))?;
    Ok(path.map(|p| p.to_string_lossy().into_owned()))
}

#[tauri::command]
pub fn choose_csv_export_path(
    app: AppHandle,
    suggested_name: Option<String>,
) -> Result<Option<String>, AppError> {
    let file_name = suggested_name.unwrap_or_else(|| "skin-analysis-statistics.csv".to_string());
    let selected = app
        .dialog()
        .file()
        .add_filter("CSV file", &["csv"])
        .set_file_name(&file_name)
        .blocking_save_file();
    let path = selected
        .map(|fp| fp.into_path())
        .transpose()
        .map_err(|e| AppError::new("dialog_error", e.to_string()))?;
    Ok(path.map(|p| p.to_string_lossy().into_owned()))
}
