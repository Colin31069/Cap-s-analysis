pub mod analysis;
pub mod commands;
pub mod config;
pub mod filesystem;
pub mod models;
pub mod plotting;

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .invoke_handler(tauri::generate_handler![
            commands::list_folder_levels,
            commands::build_plot_payload,
            commands::choose_export_path
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
