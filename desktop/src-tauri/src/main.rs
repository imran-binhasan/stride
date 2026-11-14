#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use std::sync::{Arc, Mutex};
use stride_desktop_lib::commands::*;
use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    Manager,
};
fn main() {
    env_logger::init();
    let shared: Shared = Arc::new(Mutex::new(Companion::default()));
    start_worker(shared.clone());
    tauri::Builder::default()
        .manage(shared)
        .setup(|app| {
            let show = MenuItem::with_id(app, "show", "Show tracker", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Stop timer and quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show, &quit])?;
            let mut tray = TrayIconBuilder::new()
                .menu(&menu)
                .on_menu_event(|app, event| {
                    if event.id.as_ref() == "quit" {
                        let handle = app.clone();
                        let shared = app.state::<Shared>().inner().clone();
                        tauri::async_runtime::spawn_blocking(move || {
                            if shutdown(&shared).is_ok() {
                                handle.exit(0);
                            } else if let Some(window) = handle.get_webview_window("main") {
                                let _ = window.show();
                            }
                        });
                    }
                    if event.id.as_ref() == "show" {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                });
            if let Some(icon) = app.default_window_icon() {
                tray = tray.icon(icon.clone());
            }
            tray.build(app)?;
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .invoke_handler(tauri::generate_handler![
            connect,
            read_api,
            select_organization,
            start_tracking,
            stop_tracking,
            get_daemon_status,
            configure_tracking,
            resolve_idle,
            disconnect
        ])
        .run(tauri::generate_context!())
        .expect("Could not start Stride Companion");
}
