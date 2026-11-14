//! Authenticated transport. Tokens remain in native memory and never enter localStorage.
use reqwest::blocking::Client;
use reqwest::{Method, Url};
use serde_json::{json, Value};
use std::time::Duration;

pub struct Session {
    pub base: String,
    access: String,
    refresh: String,
    pub org_id: Option<String>,
    client: Client,
}

pub fn validate_base(value: &str) -> Result<String, String> {
    let url = Url::parse(value).map_err(|_| "Enter an absolute server URL".to_string())?;
    let local = matches!(url.host_str(), Some("localhost" | "127.0.0.1" | "[::1]"));
    if (url.scheme() != "https" && !(url.scheme() == "http" && local))
        || !url.username().is_empty()
        || url.password().is_some()
        || url.query().is_some()
        || url.fragment().is_some()
    {
        return Err("Use HTTPS, or HTTP on localhost for development".into());
    }
    Ok(value.trim_end_matches('/').to_string())
}

impl Session {
    pub fn login(base: &str, email: &str, password: &str) -> Result<Self, String> {
        let mut session = Self {
            base: validate_base(base)?,
            access: String::new(),
            refresh: String::new(),
            org_id: None,
            client: Client::builder()
                .timeout(Duration::from_secs(15))
                .redirect(reqwest::redirect::Policy::none())
                .build()
                .map_err(|e| e.to_string())?,
        };
        let tokens = session.request(
            Method::POST,
            "/auth/login",
            Some(json!({"email":email,"password":password})),
        )?;
        session.set_tokens(&tokens)?;
        Ok(session)
    }

    fn set_tokens(&mut self, tokens: &Value) -> Result<(), String> {
        self.access = tokens["access_token"]
            .as_str()
            .ok_or("Invalid login response")?
            .into();
        self.refresh = tokens["refresh_token"]
            .as_str()
            .ok_or("Missing refresh token")?
            .into();
        Ok(())
    }

    pub fn request(
        &mut self,
        method: Method,
        path: &str,
        payload: Option<Value>,
    ) -> Result<Value, String> {
        for attempt in 0..2 {
            let mut req = self
                .client
                .request(method.clone(), format!("{}{path}", self.base));
            if !self.access.is_empty() {
                req = req.bearer_auth(&self.access);
            }
            if let Some(org) = &self.org_id {
                req = req.header("X-Org-ID", org);
            }
            if let Some(body) = &payload {
                req = req.json(body);
            }
            let response = req.send().map_err(|_| {
                "Server is unreachable. Your timer state is retained; retry when connected."
                    .to_string()
            })?;
            if response.status().as_u16() == 401 && attempt == 0 && !self.refresh.is_empty() {
                let refreshed = self
                    .client
                    .post(format!("{}/auth/refresh", self.base))
                    .json(&json!({"refresh_token":self.refresh}))
                    .send()
                    .map_err(|_| "Session refresh failed")?;
                if !refreshed.status().is_success() {
                    return Err("Session expired. Sign in again.".into());
                }
                self.set_tokens(
                    &refreshed
                        .json::<Value>()
                        .map_err(|_| "Invalid refresh response")?,
                )?;
                continue;
            }
            let status = response.status();
            if status.as_u16() == 204 {
                return Ok(Value::Null);
            }
            let body: Value = response
                .json()
                .map_err(|_| format!("Invalid server response ({status})"))?;
            if !status.is_success() {
                let message = body["error"]
                    .as_str()
                    .or(body["detail"].as_str())
                    .unwrap_or("Request failed");
                return Err(format!("{status}: {message}"));
            }
            return Ok(body);
        }
        Err("Session refresh failed".into())
    }

    pub fn logout(&mut self) -> Result<(), String> {
        self.request(
            Method::POST,
            "/auth/logout",
            Some(json!({"refresh_token":self.refresh})),
        )?;
        self.access.clear();
        self.refresh.clear();
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn rejects_remote_plaintext_and_embedded_credentials() {
        assert!(validate_base("http://example.com/api/v1").is_err());
        assert!(validate_base("https://user:secret@example.com").is_err());
        assert!(validate_base("https://example.com/?token=secret").is_err());
        assert!(validate_base("http://localhost:8000/api/v1").is_ok());
        assert_eq!(
            validate_base("https://example.com/api/v1/").unwrap(),
            "https://example.com/api/v1"
        );
    }
}
