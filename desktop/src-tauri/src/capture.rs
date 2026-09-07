use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::error::Error;

#[derive(Debug, Serialize, Deserialize)]
pub struct PresignedUrlResponse {
    pub screenshot_id: String,
    pub upload_url: String,
    pub s3_key: String,
    pub expires_in_seconds: u32,
}

pub struct CaptureEngine {
    client: Client,
}

impl CaptureEngine {
    pub fn new() -> Self {
        Self {
            client: Client::new(),
        }
    }

    pub async fn upload_screen_sample(
        &self,
        upload_url: &str,
        image_bytes: Vec<u8>,
    ) -> Result<(), Box<dyn Error + Send + Sync>> {
        self.client
            .put(upload_url)
            .header("Content-Type", "image/jpeg")
            .body(image_bytes)
            .send()
            .await?;
        Ok(())
    }
}
