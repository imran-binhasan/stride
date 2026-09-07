use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};
use std::sync::Arc;
use tokio::time::{sleep, Duration};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TelemetryPayload {
    pub time_entry_id: String,
    pub period_start: String,
    pub period_end: String,
    pub keystroke_count: u32,
    pub mouse_distance_px: u32,
    pub active_window_title: Option<String>,
    pub is_idle: bool,
}

#[derive(Clone)]
pub struct TelemetryEngine {
    is_running: Arc<AtomicBool>,
    keystroke_counter: Arc<AtomicU32>,
    mouse_distance_counter: Arc<AtomicU32>,
}

impl TelemetryEngine {
    pub fn new() -> Self {
        Self {
            is_running: Arc::new(AtomicBool::new(false)),
            keystroke_counter: Arc::new(AtomicU32::new(0)),
            mouse_distance_counter: Arc::new(AtomicU32::new(0)),
        }
    }

    pub fn start(&self) {
        self.is_running.store(true, Ordering::SeqCst);
    }

    pub fn stop(&self) {
        self.is_running.store(false, Ordering::SeqCst);
    }

    pub fn is_active(&self) -> bool {
        self.is_running.load(Ordering::SeqCst)
    }

    pub fn sample_and_reset(&self) -> (u32, u32, bool) {
        let keys = self.keystroke_counter.swap(0, Ordering::SeqCst);
        let mouse = self.mouse_distance_counter.swap(0, Ordering::SeqCst);
        let is_idle = keys == 0 && mouse == 0;
        (keys, mouse, is_idle)
    }
}
