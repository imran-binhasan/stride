use serde::{Deserialize, Serialize};
use tauri::State;

#[derive(Serialize, Deserialize)]
pub struct DaemonStatus {
    pub is_tracking: bool,
    pub active_task_id: Option<String>,
    pub current_activity_score: f32,
}

#[tauri::command]
pub fn start_tracking(task_id: String) -> DaemonStatus {
    DaemonStatus {
        is_tracking: true,
        active_task_id: Some(task_id),
        current_activity_score: 100.0,
    }
}

#[tauri::command]
pub fn stop_tracking() -> DaemonStatus {
    DaemonStatus {
        is_tracking: false,
        active_task_id: None,
        current_activity_score: 0.0,
    }
}

#[tauri::command]
pub fn get_daemon_status() -> DaemonStatus {
    DaemonStatus {
        is_tracking: false,
        active_task_id: None,
        current_activity_score: 0.0,
    }
}
