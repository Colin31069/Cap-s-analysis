use std::path::PathBuf;

use tauri::AppHandle;
use tauri_plugin_dialog::DialogExt;

use crate::analysis::process_single_file;
use crate::config::{COLOR_PALETTE, DEFAULT_ROOT_PATH, LINE_STYLE_CYCLE};
use crate::filesystem::{get_subfolders, list_xlsx_files};
use crate::models::{AppError, FolderLevelsRequest, FolderLevelsResponse, PlotRequest, PlotResponse};
use crate::plotting::{build_plot_series, display_mode_to_y_unit};

#[tauri::command]
pub fn list_folder_levels(request: FolderLevelsRequest) -> Result<FolderLevelsResponse, AppError> {
    let root_path = if request.root_path.trim().is_empty() {
        PathBuf::from(DEFAULT_ROOT_PATH)
    } else {
        PathBuf::from(&request.root_path)
    };

    let l1_options = get_subfolders(&root_path);
    let selected_l1 = request
        .l1
        .as_ref()
        .filter(|value| l1_options.contains(value))
        .cloned();
    let l2_options = selected_l1
        .as_ref()
        .map(|l1| get_subfolders(&root_path.join(l1)))
        .unwrap_or_default();
    let selected_l2 = request
        .l2
        .as_ref()
        .filter(|value| l2_options.contains(value))
        .cloned();
    let l3_options = match (selected_l1.as_ref(), selected_l2.as_ref()) {
        (Some(l1), Some(l2)) => get_subfolders(&root_path.join(l1).join(l2)),
        _ => Vec::new(),
    };

    Ok(FolderLevelsResponse {
        l1_options,
        l2_options,
        l3_options,
    })
}

#[tauri::command]
pub fn build_plot_payload(request: PlotRequest) -> Result<PlotResponse, AppError> {
    if request.l1.is_empty() || request.l2.is_empty() || request.l3.is_empty() {
        return Err(AppError::new(
            "missing_path",
            "Please select all folder levels before plotting.",
        ));
    }

    let root_path = if request.root_path.trim().is_empty() {
        PathBuf::from(DEFAULT_ROOT_PATH)
    } else {
        PathBuf::from(&request.root_path)
    };
    let target_dir = root_path.join(&request.l1).join(&request.l2).join(&request.l3);
    if !target_dir.is_dir() {
        return Err(AppError::new("folder_not_found", "Folder not found."));
    }

    let all_files = list_xlsx_files(&target_dir);
    if all_files.is_empty() {
        return Err(AppError::new("no_files", "No .xlsx files found in this folder."));
    }

    let group_color = if request.use_group_color {
        Some(
            request
                .group_color
                .clone()
                .unwrap_or_else(|| COLOR_PALETTE[0].to_string()),
        )
    } else {
        None
    };

    let mut series = Vec::new();
    for (index, file_name) in all_files.iter().enumerate() {
        let file_path = target_dir.join(file_name);
        let Some(signal) = process_single_file(&file_path) else {
            continue;
        };

        let line_style = if request.use_group_color {
            LINE_STYLE_CYCLE[index % LINE_STYLE_CYCLE.len()]
        } else {
            "-"
        };
        let sample_name = std::path::Path::new(file_name)
            .file_stem()
            .and_then(|stem| stem.to_str())
            .unwrap_or(file_name);
        series.push(build_plot_series(
            &signal,
            sample_name,
            &request,
            line_style,
            group_color.clone(),
        ));
    }

    Ok(PlotResponse {
        title: format!("{} | {} | {}", request.l1, request.l2, request.l3),
        y_unit: display_mode_to_y_unit(&request.display_mode),
        series,
        settings: request,
    })
}

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
        .map(|file_path| file_path.into_path())
        .transpose()
        .map_err(|error| AppError::new("dialog_error", error.to_string()))?;

    Ok(path.map(|path| path.to_string_lossy().into_owned()))
}
