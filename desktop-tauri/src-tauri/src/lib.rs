pub mod analysis;
pub mod commands;
pub mod config;
pub mod exclusions;
pub mod filesystem;
pub mod metadata;
pub mod models;
pub mod plotting;
pub mod statistics;

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .invoke_handler(tauri::generate_handler![
            commands::list_folder_levels,
            commands::load_metadata,
            commands::save_metadata,
            commands::list_samples_in_folder,
            commands::build_plot_payload,
            commands::run_statistics,
            commands::choose_export_path,
            commands::choose_csv_export_path,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
