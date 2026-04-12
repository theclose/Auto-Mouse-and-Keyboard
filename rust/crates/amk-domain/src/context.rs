use std::collections::{BTreeMap, HashMap};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use once_cell::sync::Lazy;
use parking_lot::Mutex;
use regex::Regex;
use serde::{Deserialize, Serialize};
use serde_json::Value;

static VAR_PATTERN: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"\$\{(\w+)\}").expect("variable regex must compile"));

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct Rect {
    pub x: i32,
    pub y: i32,
    pub width: i32,
    pub height: i32,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ImageMatch {
    pub template_path: String,
    pub rect: Rect,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct PixelSample {
    pub x: i32,
    pub y: i32,
    pub r: i32,
    pub g: i32,
    pub b: i32,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct ExecutionSnapshot {
    pub variables: BTreeMap<String, Value>,
    pub iteration_count: u64,
    pub action_count: u64,
    pub error_count: u64,
    pub last_image_match: Option<ImageMatch>,
    pub last_pixel_color: Option<PixelSample>,
}

#[derive(Debug, Clone)]
struct RoiCache {
    key: String,
    rect: Rect,
    captured_at: Instant,
}

#[derive(Debug, Clone, Default)]
struct ExecutionState {
    variables: BTreeMap<String, Value>,
    last_image_match: Option<ImageMatch>,
    last_pixel_color: Option<PixelSample>,
    roi_history: HashMap<String, Vec<Rect>>,
    roi_cache: Option<RoiCache>,
    iteration_count: u64,
    action_count: u64,
    error_count: u64,
    started_at: Option<Instant>,
}

#[derive(Debug, Default)]
pub struct ExecutionContext {
    state: Mutex<ExecutionState>,
}

impl ExecutionContext {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn set_var<V>(&self, name: impl Into<String>, value: V)
    where
        V: Into<Value>,
    {
        self.state
            .lock()
            .variables
            .insert(name.into(), value.into());
    }

    pub fn get_var(&self, name: &str) -> Option<Value> {
        self.state.lock().variables.get(name).cloned()
    }

    pub fn get_all_vars(&self) -> BTreeMap<String, Value> {
        self.state.lock().variables.clone()
    }

    pub fn set_image_match(&self, template_path: impl Into<String>, rect: Rect) {
        let template_path = template_path.into();
        let mut state = self.state.lock();
        state.last_image_match = Some(ImageMatch {
            template_path: template_path.clone(),
            rect,
        });
        let history = state.roi_history.entry(template_path).or_default();
        history.push(rect);
        if history.len() > 10 {
            let drain_until = history.len() - 10;
            history.drain(0..drain_until);
        }
        state.roi_cache = None;
    }

    pub fn get_image_match(&self, template_path: Option<&str>) -> Option<ImageMatch> {
        let state = self.state.lock();
        let candidate = state.last_image_match.clone()?;
        if let Some(path) = template_path {
            if candidate.template_path != path {
                return None;
            }
        }
        Some(candidate)
    }

    pub fn get_image_center(&self, template_path: Option<&str>) -> Option<(i32, i32)> {
        let image = self.get_image_match(template_path)?;
        Some((
            image.rect.x + (image.rect.width / 2),
            image.rect.y + (image.rect.height / 2),
        ))
    }

    pub fn suggest_roi(&self, template_path: &str, margin: i32) -> Option<Rect> {
        let state = self.state.lock();
        let history = state.roi_history.get(template_path)?;
        if history.len() < 2 {
            return None;
        }
        let recent = &history[history.len().saturating_sub(5)..];
        let len = recent.len() as i32;
        let avg_x = recent.iter().map(|rect| rect.x).sum::<i32>() / len;
        let avg_y = recent.iter().map(|rect| rect.y).sum::<i32>() / len;
        let avg_w = recent.iter().map(|rect| rect.width).sum::<i32>() / len;
        let avg_h = recent.iter().map(|rect| rect.height).sum::<i32>() / len;
        Some(Rect {
            x: (avg_x - margin).max(0),
            y: (avg_y - margin).max(0),
            width: avg_w + (margin * 2),
            height: avg_h + (margin * 2),
        })
    }

    pub fn suggest_roi_cached(
        &self,
        template_path: &str,
        margin: i32,
        ttl: Duration,
    ) -> Option<Rect> {
        {
            let state = self.state.lock();
            if let Some(cache) = &state.roi_cache {
                if cache.key == template_path && cache.captured_at.elapsed() < ttl {
                    return Some(cache.rect);
                }
            }
        }

        let rect = self.suggest_roi(template_path, margin)?;
        self.state.lock().roi_cache = Some(RoiCache {
            key: template_path.to_string(),
            rect,
            captured_at: Instant::now(),
        });
        Some(rect)
    }

    pub fn set_pixel_color(&self, sample: PixelSample) {
        self.state.lock().last_pixel_color = Some(sample);
    }

    pub fn get_pixel_color(&self) -> Option<PixelSample> {
        self.state.lock().last_pixel_color
    }

    pub fn record_action(&self, success: bool) {
        let mut state = self.state.lock();
        state.action_count += 1;
        if !success {
            state.error_count += 1;
        }
    }

    pub fn set_iteration_count(&self, iteration_count: u64) {
        self.state.lock().iteration_count = iteration_count;
    }

    pub fn elapsed(&self) -> Duration {
        let state = self.state.lock();
        state
            .started_at
            .map(|start| start.elapsed())
            .unwrap_or_else(|| Duration::from_secs(0))
    }

    pub fn reset(&self) {
        let mut state = self.state.lock();
        *state = ExecutionState {
            started_at: Some(Instant::now()),
            ..ExecutionState::default()
        };
    }

    pub fn snapshot(&self) -> ExecutionSnapshot {
        let state = self.state.lock();
        ExecutionSnapshot {
            variables: state.variables.clone(),
            iteration_count: state.iteration_count,
            action_count: state.action_count,
            error_count: state.error_count,
            last_image_match: state.last_image_match.clone(),
            last_pixel_color: state.last_pixel_color,
        }
    }

    pub fn restore(&self, snapshot: &ExecutionSnapshot) {
        let mut state = self.state.lock();
        state.variables = snapshot.variables.clone();
        state.iteration_count = snapshot.iteration_count;
        state.action_count = snapshot.action_count;
        state.error_count = snapshot.error_count;
        state.last_image_match = snapshot.last_image_match.clone();
        state.last_pixel_color = snapshot.last_pixel_color;
    }

    pub fn interpolate(&self, text: &str) -> String {
        VAR_PATTERN
            .replace_all(text, |captures: &regex::Captures<'_>| {
                let name = captures.get(1).map(|m| m.as_str()).unwrap_or_default();
                self.resolve_placeholder(name)
            })
            .into_owned()
    }

    fn resolve_placeholder(&self, name: &str) -> String {
        match name {
            "__timestamp__" => SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs()
                .to_string(),
            "__iteration__" => self.state.lock().iteration_count.to_string(),
            "__action_count__" => self.state.lock().action_count.to_string(),
            "__error_count__" => self.state.lock().error_count.to_string(),
            "__last_img_x__" => self
                .get_image_center(None)
                .map(|(x, _)| x.to_string())
                .unwrap_or_else(|| "0".to_string()),
            "__last_img_y__" => self
                .get_image_center(None)
                .map(|(_, y)| y.to_string())
                .unwrap_or_else(|| "0".to_string()),
            variable => self
                .get_var(variable)
                .map(|value| value_to_string(&value))
                .unwrap_or_else(|| format!("${{{variable}}}")),
        }
    }
}

fn value_to_string(value: &Value) -> String {
    match value {
        Value::Null => String::new(),
        Value::Bool(value) => value.to_string(),
        Value::Number(value) => value.to_string(),
        Value::String(value) => value.clone(),
        Value::Array(_) | Value::Object(_) => value.to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn interpolates_user_and_system_variables() {
        let context = ExecutionContext::new();
        context.reset();
        context.set_var("name", "Alice");
        context.set_iteration_count(7);
        let rendered = context.interpolate("Hello ${name} #${__iteration__}");
        assert_eq!(rendered, "Hello Alice #7");
    }

    #[test]
    fn keeps_missing_variables_unresolved() {
        let context = ExecutionContext::new();
        let rendered = context.interpolate("X=${missing}");
        assert_eq!(rendered, "X=${missing}");
    }

    #[test]
    fn computes_roi_from_recent_history() {
        let context = ExecutionContext::new();
        context.set_image_match(
            "needle.png",
            Rect {
                x: 100,
                y: 100,
                width: 20,
                height: 20,
            },
        );
        context.set_image_match(
            "needle.png",
            Rect {
                x: 110,
                y: 120,
                width: 20,
                height: 20,
            },
        );
        let roi = context
            .suggest_roi("needle.png", 10)
            .expect("roi should exist");
        assert_eq!(roi.x, 95);
        assert_eq!(roi.y, 100);
    }

    #[test]
    fn snapshot_roundtrip_restores_variables() {
        let context = ExecutionContext::new();
        context.reset();
        context.set_var("count", json!(3));
        context.record_action(false);
        let snapshot = context.snapshot();

        let restored = ExecutionContext::new();
        restored.restore(&snapshot);
        assert_eq!(restored.get_var("count"), Some(json!(3)));
        assert_eq!(restored.snapshot().error_count, 1);
    }
}
