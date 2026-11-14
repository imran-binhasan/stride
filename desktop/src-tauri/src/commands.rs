use crate::{api::Session, capture::capture_and_upload, telemetry::InputSampler};
use chrono::{DateTime, Utc};
use reqwest::Method;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{
    sync::{Arc, Mutex},
    time::{Duration, Instant},
};
use tauri::State;

#[derive(Clone, Serialize, Default)]
pub struct DaemonStatus {
    pub connected: bool,
    pub entry: Option<Value>,
    pub activity_score: Option<f64>,
    pub screenshots: u32,
    pub input_available: bool,
    pub paused_for_idle: bool,
    pub idle_gap: Option<Value>,
    pub idle_since: Option<String>,
    pub error: Option<String>,
}
#[derive(Clone, Deserialize)]
pub struct Preferences {
    pub screenshots_enabled: bool,
    pub blur: bool,
    pub screenshot_interval_seconds: u64,
    pub randomize: bool,
    pub idle_threshold_seconds: u64,
}
impl Default for Preferences {
    fn default() -> Self {
        Self {
            screenshots_enabled: false,
            blur: true,
            screenshot_interval_seconds: 600,
            randomize: true,
            idle_threshold_seconds: 300,
        }
    }
}
#[derive(Default)]
pub struct Companion {
    session: Option<Session>,
    status: DaemonStatus,
    preferences: Preferences,
    generation: u64,
}
pub type Shared = Arc<Mutex<Companion>>;

fn read_path(path: &str) -> bool {
    // The webview cannot ask the native transport to send credentials to arbitrary URLs.
    !path.contains("..")
        && !path.contains('?')
        && !path.contains('#')
        && !path.contains('\\')
        && (path == "/organizations"
            || path == "/auth/me"
            || path == "/time-tracking/timer/active"
            || (path.starts_with("/organizations/") && path.ends_with("/workspaces"))
            || path.starts_with("/projects/workspace/")
            || path.starts_with("/tasks/project/"))
}

#[tauri::command]
pub async fn connect(
    state: State<'_, Shared>,
    base: String,
    email: String,
    password: String,
) -> Result<DaemonStatus, String> {
    let shared = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        let session = Session::login(&base, &email, &password)?;
        let mut app = shared.lock().map_err(|_| "Tracker state unavailable")?;
        if app.status.entry.is_some() {
            return Err("Stop tracking before reconnecting".into());
        }
        app.session = Some(session);
        app.status = DaemonStatus {
            connected: true,
            ..DaemonStatus::default()
        };
        Ok(app.status.clone())
    })
    .await
    .map_err(|e| e.to_string())?
}
#[tauri::command]
pub async fn read_api(state: State<'_, Shared>, path: String) -> Result<Value, String> {
    if !read_path(&path) {
        return Err("Unsupported request".into());
    }
    let shared = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        let mut app = shared.lock().map_err(|_| "Tracker state unavailable")?;
        app.session
            .as_mut()
            .ok_or("Sign in first")?
            .request(Method::GET, &path, None)
    })
    .await
    .map_err(|e| e.to_string())?
}
#[tauri::command]
pub async fn select_organization(
    state: State<'_, Shared>,
    org_id: String,
) -> Result<DaemonStatus, String> {
    let shared = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        let mut app = shared.lock().map_err(|_| "Tracker state unavailable")?;
        if app.status.entry.is_some() {
            return Err("Stop tracking before switching organization".into());
        }
        let session = app.session.as_mut().ok_or("Sign in first")?;
        let orgs = session.request(Method::GET, "/organizations", None)?;
        if !orgs
            .as_array()
            .ok_or("Invalid organizations response")?
            .iter()
            .any(|o| o["id"].as_str() == Some(&org_id))
        {
            return Err("Organization membership required".into());
        }
        session.org_id = Some(org_id);
        let active = session.request(Method::GET, "/time-tracking/timer/active", None)?;
        app.status.entry = if active.is_null() { None } else { Some(active) };
        app.status.paused_for_idle = false;
        app.generation += 1;
        Ok(app.status.clone())
    })
    .await
    .map_err(|e| e.to_string())?
}
#[tauri::command]
pub async fn start_tracking(
    state: State<'_, Shared>,
    task_id: String,
) -> Result<DaemonStatus, String> {
    let shared = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        let mut app = shared.lock().map_err(|_| "Tracker state unavailable")?;
        if app.status.idle_gap.is_some() {
            return Err("Keep or discard the idle interval before starting".into());
        }
        if app.status.entry.is_some() {
            return Err("A timer is already running".into());
        }
        let entry = app.session.as_mut().ok_or("Sign in first")?.request(
            Method::POST,
            "/time-tracking/timer/start",
            Some(json!({"task_id":task_id})),
        )?;
        app.status.entry = Some(entry);
        app.status.paused_for_idle = false;
        app.status.error = None;
        app.status.activity_score = None;
        app.generation += 1;
        Ok(app.status.clone())
    })
    .await
    .map_err(|e| e.to_string())?
}
fn stop(app: &mut Companion, idle: bool) -> Result<(), String> {
    let entry = app.status.entry.clone().ok_or("No active timer")?;
    app.session.as_mut().ok_or("Sign in first")?.request(
        Method::POST,
        "/time-tracking/timer/stop",
        Some(json!({"time_entry_id":entry["id"],"idle_since":if idle {app.status.idle_since.clone()} else {None}})),
    )?;
    if idle {
        app.status.idle_gap = Some(
            json!({"task_id":entry["task_id"],"start_time":app.status.idle_since,
            "end_time":Utc::now().to_rfc3339(),"is_billable":entry["is_billable"],"notes":"Idle interval retained by employee"}),
        );
    }
    app.status.entry = None;
    app.status.paused_for_idle = idle;
    app.generation += 1;
    Ok(())
}
#[tauri::command]
pub async fn stop_tracking(state: State<'_, Shared>) -> Result<DaemonStatus, String> {
    let shared = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        let mut app = shared.lock().map_err(|_| "Tracker state unavailable")?;
        stop(&mut app, false)?;
        Ok(app.status.clone())
    })
    .await
    .map_err(|e| e.to_string())?
}
#[tauri::command]
pub fn get_daemon_status(state: State<'_, Shared>) -> Result<DaemonStatus, String> {
    Ok(state
        .lock()
        .map_err(|_| "Tracker state unavailable")?
        .status
        .clone())
}
#[tauri::command]
pub fn configure_tracking(
    state: State<'_, Shared>,
    preferences: Preferences,
) -> Result<(), String> {
    if !(60..=3600).contains(&preferences.screenshot_interval_seconds)
        || !(60..=3600).contains(&preferences.idle_threshold_seconds)
    {
        return Err("Capture and idle intervals must be between 60 and 3600 seconds".into());
    }
    state
        .lock()
        .map_err(|_| "Tracker state unavailable")?
        .preferences = preferences;
    Ok(())
}
#[tauri::command]
pub async fn disconnect(state: State<'_, Shared>) -> Result<(), String> {
    let shared = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        let mut app = shared.lock().map_err(|_| "Tracker state unavailable")?;
        if app.status.entry.is_some() {
            stop(&mut app, false)?;
        }
        if let Some(session) = app.session.as_mut() {
            session.logout()?;
        }
        *app = Companion::default();
        Ok(())
    })
    .await
    .map_err(|e| e.to_string())?
}

pub fn start_worker(shared: Shared) {
    std::thread::spawn(move || {
        let mut sampler = InputSampler::new();
        let mut generation = 0;
        let mut period_start = Utc::now();
        let mut last_heartbeat = Instant::now();
        let mut last_capture = Instant::now();
        let mut next_capture = 600;
        loop {
            std::thread::sleep(Duration::from_millis(100));
            if let Some(input) = sampler.as_mut() {
                input.poll();
            }
            let Ok(mut app) = shared.lock() else { break };
            app.status.input_available = sampler.is_some();
            if app.generation != generation {
                generation = app.generation;
                period_start = Utc::now();
                last_heartbeat = Instant::now();
                last_capture = Instant::now();
                next_capture = app.preferences.screenshot_interval_seconds;
                if let Some(input) = sampler.as_mut() {
                    input.reset();
                    input.last_input = Instant::now();
                }
            }
            let Some(entry) = app.status.entry.clone() else {
                continue;
            };
            let Some(id) = entry["id"].as_str() else {
                continue;
            };
            if last_heartbeat.elapsed() < Duration::from_secs(30) {
                continue;
            }
            let now = Utc::now();
            let idle = sampler.as_ref().is_some_and(|s| {
                s.last_input.elapsed().as_secs() >= app.preferences.idle_threshold_seconds
            });
            if let Some(input) = sampler.as_mut() {
                let payload = json!({"time_entry_id":id,"period_start":period_start,"period_end":now,
                    "keystroke_count":input.keys,"mouse_distance_px":input.distance,"is_idle":idle});
                let result = app.session.as_mut().unwrap().request(
                    Method::POST,
                    "/time-tracking/telemetry/heartbeat",
                    Some(payload),
                );
                match result {
                    Ok(value) => {
                        app.status.activity_score = value["activity_score"].as_f64();
                        app.status.error = None;
                    }
                    Err(error) => {
                        app.status.error = Some(error);
                    }
                }
                // Never backfill fabricated activity after a connection gap.
                input.reset();
            }
            period_start = now;
            last_heartbeat = Instant::now();
            if idle {
                let seconds = sampler.as_ref().unwrap().last_input.elapsed().as_secs();
                app.status.idle_since =
                    Some((now - chrono::Duration::seconds(seconds as i64)).to_rfc3339());
                if let Err(error) = stop(&mut app, true) {
                    app.status.error = Some(error);
                }
                continue;
            }
            if app.preferences.screenshots_enabled
                && last_capture.elapsed().as_secs() >= next_capture
            {
                let blur = app.preferences.blur;
                let score = app.status.activity_score.unwrap_or(0.0);
                match capture_and_upload(app.session.as_mut().unwrap(), id, blur, score) {
                    Ok(()) => app.status.screenshots += 1,
                    Err(error) => app.status.error = Some(error),
                }
                last_capture = Instant::now();
                let interval = app.preferences.screenshot_interval_seconds;
                next_capture = if app.preferences.randomize {
                    rand::random_range(interval / 2..=interval + interval / 2)
                } else {
                    interval
                };
            }
            // Check for timers stopped or replaced in the web app.
            match app.session.as_mut().unwrap().request(
                Method::GET,
                "/time-tracking/timer/active",
                None,
            ) {
                Ok(active) if active["id"] != entry["id"] => {
                    app.status.entry = if active.is_null() { None } else { Some(active) };
                    app.generation += 1;
                }
                Err(error) => app.status.error = Some(error),
                _ => {}
            }
        }
    });
}

pub fn elapsed_seconds(start: &str) -> i64 {
    DateTime::parse_from_rfc3339(start)
        .map(|dt| (Utc::now() - dt.with_timezone(&Utc)).num_seconds().max(0))
        .unwrap_or(0)
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn bridge_rejects_arbitrary_urls_and_paths() {
        assert!(!read_path("https://evil.example"));
        assert!(!read_path("/organizations/../../auth/refresh/workspaces"));
        assert!(!read_path("/auth/logout"));
        assert!(read_path("/tasks/project/123"));
        assert!(read_path("/organizations"));
    }
}

pub fn shutdown(shared: &Shared) -> Result<(), String> {
    let mut app = shared.lock().map_err(|_| "Tracker state unavailable")?;
    if app.status.entry.is_some() {
        if let Err(error) = stop(&mut app, false) {
            app.status.error = Some(error.clone());
            return Err(error);
        }
    }
    Ok(())
}

#[tauri::command]
pub async fn resolve_idle(state: State<'_, Shared>, keep: bool) -> Result<DaemonStatus, String> {
    let shared = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        let mut app = shared.lock().map_err(|_| "Tracker state unavailable")?;
        if let Some(gap) = app.status.idle_gap.clone() {
            if keep {
                app.session.as_mut().ok_or("Sign in first")?.request(
                    Method::POST,
                    "/time-tracking/entries",
                    Some(gap),
                )?;
            }
            app.status.idle_gap = None;
            app.status.idle_since = None;
            app.status.paused_for_idle = false;
        }
        Ok(app.status.clone())
    })
    .await
    .map_err(|e| e.to_string())?
}
