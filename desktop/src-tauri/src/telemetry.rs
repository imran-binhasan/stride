//! Aggregate input transitions only. Key values and window titles are never persisted or sent.
use device_query::{DeviceQuery, DeviceState, Keycode};
use std::time::Instant;

pub struct InputSampler {
    device: DeviceState,
    previous_keys: Vec<Keycode>,
    previous_mouse: (i32, i32),
    pub keys: u32,
    pub distance: u32,
    pub last_input: Instant,
}
impl InputSampler {
    pub fn new() -> Option<Self> {
        let device = DeviceState::checked_new()?;
        let previous_mouse = device.get_mouse().coords;
        Some(Self {
            device,
            previous_keys: vec![],
            previous_mouse,
            keys: 0,
            distance: 0,
            last_input: Instant::now(),
        })
    }
    pub fn poll(&mut self) {
        let keys = self.device.get_keys();
        let pressed = keys
            .iter()
            .filter(|k| !self.previous_keys.contains(k))
            .count() as u32;
        let mouse = self.device.get_mouse();
        let distance = mouse_distance(self.previous_mouse, mouse.coords);
        if pressed > 0 || distance > 0 || mouse.button_pressed.iter().any(|b| *b) {
            self.last_input = Instant::now();
        }
        self.keys = self.keys.saturating_add(pressed);
        self.distance = self.distance.saturating_add(distance);
        self.previous_keys = keys;
        self.previous_mouse = mouse.coords;
    }
    pub fn reset(&mut self) {
        self.keys = 0;
        self.distance = 0;
    }
}
fn mouse_distance(a: (i32, i32), b: (i32, i32)) -> u32 {
    let dx = f64::from(a.0) - f64::from(b.0);
    let dy = f64::from(a.1) - f64::from(b.1);
    dx.hypot(dy).min(u32::MAX as f64) as u32
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn distance_handles_negative_monitor_coordinates() {
        assert_eq!(mouse_distance((-3, -4), (0, 0)), 5);
        assert_eq!(mouse_distance((0, 0), (0, 0)), 0);
        assert!(mouse_distance((i32::MIN, 0), (i32::MAX, 0)) > 0);
    }
}
