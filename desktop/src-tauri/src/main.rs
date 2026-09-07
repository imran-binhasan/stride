// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod capture;
mod commands;
mod telemetry;

use commands::{get_daemon_status, start_tracking, stop_tracking};

fn main() {
    env_logger::init();

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            start_tracking,
            stop_tracking,
            get_daemon_status
        ])
        .run(tauri::generate_context!())
        .expect("error while running Stride Companion desktop application");
}
