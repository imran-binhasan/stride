use crate::api::Session;
use image::{DynamicImage, ImageFormat};
use reqwest::Method;
use serde_json::json;
use std::io::Cursor;

pub fn capture_and_upload(
    session: &mut Session,
    entry_id: &str,
    blur: bool,
    score: f64,
) -> Result<(), String> {
    let monitors = xcap::Monitor::all().map_err(|e| format!("Screen permission: {e}"))?;
    let monitor = monitors.first().ok_or("No screen is available")?;
    let image = monitor
        .capture_image()
        .map_err(|e| format!("Screen capture failed: {e}"))?;
    let mut image = DynamicImage::ImageRgba8(image);
    if blur {
        image = image.blur(18.0);
    }
    let mut bytes = Cursor::new(Vec::new());
    image
        .write_to(&mut bytes, ImageFormat::Png)
        .map_err(|e| e.to_string())?;
    let reservation = session.request(
        Method::POST,
        "/time-tracking/screenshots/presigned-url",
        Some(json!({
            "time_entry_id": entry_id, "file_extension":"png", "is_blurred":blur
        })),
    )?;
    let url = reservation["upload_url"]
        .as_str()
        .ok_or("Missing upload URL")?;
    reqwest::blocking::Client::builder()
        .timeout(std::time::Duration::from_secs(30))
        .redirect(reqwest::redirect::Policy::none())
        .build()
        .map_err(|e| e.to_string())?
        .put(url)
        .header("Content-Type", "image/png")
        .body(bytes.into_inner())
        .send()
        .map_err(|_| "Screenshot upload failed")?
        .error_for_status()
        .map_err(|_| "Storage rejected screenshot")?;
    session.request(
        Method::POST,
        "/time-tracking/screenshots/confirm",
        Some(json!({
            "screenshot_id":reservation["screenshot_id"], "time_entry_id":entry_id,
            "s3_key":reservation["s3_key"], "activity_score":score, "is_blurred":blur
        })),
    )?;
    Ok(())
}
