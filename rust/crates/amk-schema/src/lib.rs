use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum SchemaError {
    #[error("invalid JSON: {0}")]
    InvalidJson(#[from] serde_json::Error),
}

fn default_true() -> bool {
    true
}

fn default_repeat_count() -> u32 {
    1
}

fn default_on_error() -> String {
    "stop".to_string()
}

fn default_loop_count() -> u32 {
    1
}

fn default_schedule_mode() -> String {
    "interval".to_string()
}

fn default_trigger_type() -> String {
    "schedule".to_string()
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MacroSettings {
    #[serde(default = "default_loop_count")]
    pub loop_count: u32,
    #[serde(default)]
    pub delay_between_loops: u32,
    #[serde(default, flatten)]
    pub extras: Map<String, Value>,
}

impl Default for MacroSettings {
    fn default() -> Self {
        Self {
            loop_count: default_loop_count(),
            delay_between_loops: 0,
            extras: Map::new(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RawAction {
    #[serde(rename = "type")]
    pub action_type: String,
    #[serde(default)]
    pub params: Value,
    #[serde(default)]
    pub delay_after: u32,
    #[serde(default = "default_repeat_count")]
    pub repeat_count: u32,
    #[serde(default)]
    pub description: String,
    #[serde(default = "default_true")]
    pub enabled: bool,
    #[serde(default = "default_on_error")]
    pub on_error: String,
    #[serde(default)]
    pub color: Option<String>,
    #[serde(default)]
    pub bookmarked: bool,
}

impl RawAction {
    pub fn normalized_type(&self) -> &str {
        match self.action_type.as_str() {
            "screenshot" => "take_screenshot",
            "click" => "mouse_click",
            "double_click" => "mouse_double_click",
            "right_click" => "mouse_right_click",
            "drag" => "mouse_drag",
            "scroll" => "mouse_scroll",
            "move" => "mouse_move",
            "press" => "key_press",
            "combo" => "key_combo",
            "wait_image" => "wait_for_image",
            "find_image" => "image_exists",
            "check_pixel" => "check_pixel_color",
            "wait_color" => "wait_for_color",
            "set_var" => "set_variable",
            "if_var" => "if_variable",
            "loop" => "loop_block",
            other => other,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct MacroDocument {
    #[serde(default = "default_name")]
    pub name: String,
    #[serde(default = "default_macro_version")]
    pub version: String,
    #[serde(default)]
    pub settings: MacroSettings,
    #[serde(default)]
    pub actions: Vec<RawAction>,
}

fn default_name() -> String {
    "Untitled".to_string()
}

fn default_macro_version() -> String {
    "1.1".to_string()
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct HotkeyConfig {
    #[serde(default = "default_hotkey_start")]
    pub start_stop: String,
    #[serde(default = "default_hotkey_pause")]
    pub pause_resume: String,
    #[serde(default = "default_hotkey_stop")]
    pub emergency_stop: String,
    #[serde(default = "default_hotkey_record")]
    pub record: String,
}

fn default_hotkey_start() -> String {
    "F6".to_string()
}

fn default_hotkey_pause() -> String {
    "F7".to_string()
}

fn default_hotkey_stop() -> String {
    "F8".to_string()
}

fn default_hotkey_record() -> String {
    "F9".to_string()
}

impl Default for HotkeyConfig {
    fn default() -> Self {
        Self {
            start_stop: default_hotkey_start(),
            pause_resume: default_hotkey_pause(),
            emergency_stop: default_hotkey_stop(),
            record: default_hotkey_record(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DefaultsConfig {
    #[serde(default = "default_click_delay")]
    pub click_delay: u32,
    #[serde(default = "default_typing_speed")]
    pub typing_speed: u32,
    #[serde(default = "default_image_confidence")]
    pub image_confidence: f64,
    #[serde(default = "default_true")]
    pub failsafe_enabled: bool,
    #[serde(default = "default_speed_factor")]
    pub speed_factor: f64,
}

fn default_click_delay() -> u32 {
    100
}

fn default_typing_speed() -> u32 {
    50
}

fn default_image_confidence() -> f64 {
    0.8
}

fn default_speed_factor() -> f64 {
    1.0
}

impl Default for DefaultsConfig {
    fn default() -> Self {
        Self {
            click_delay: default_click_delay(),
            typing_speed: default_typing_speed(),
            image_confidence: default_image_confidence(),
            failsafe_enabled: true,
            speed_factor: default_speed_factor(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct UiConfig {
    #[serde(default = "default_ui_theme")]
    pub theme: String,
    #[serde(default = "default_ui_accent")]
    pub accent_color: String,
    #[serde(default = "default_ui_language")]
    pub language: String,
    #[serde(default = "default_true")]
    pub minimize_to_tray: bool,
    #[serde(default = "default_neg_one")]
    pub window_width: i32,
    #[serde(default = "default_neg_one")]
    pub window_height: i32,
    #[serde(default = "default_neg_one")]
    pub window_x: i32,
    #[serde(default = "default_neg_one")]
    pub window_y: i32,
    #[serde(default)]
    pub window_maximized: bool,
    #[serde(default)]
    pub h_splitter_sizes: Vec<i32>,
    #[serde(default)]
    pub v_splitter_sizes: Vec<i32>,
    #[serde(default = "default_font_size")]
    pub font_size: u32,
}

fn default_ui_theme() -> String {
    "dark".to_string()
}

fn default_ui_accent() -> String {
    "Tím".to_string()
}

fn default_ui_language() -> String {
    "en".to_string()
}

fn default_neg_one() -> i32 {
    -1
}

fn default_font_size() -> u32 {
    10
}

impl Default for UiConfig {
    fn default() -> Self {
        Self {
            theme: default_ui_theme(),
            accent_color: default_ui_accent(),
            language: default_ui_language(),
            minimize_to_tray: true,
            window_width: -1,
            window_height: -1,
            window_x: -1,
            window_y: -1,
            window_maximized: false,
            h_splitter_sizes: Vec::new(),
            v_splitter_sizes: Vec::new(),
            font_size: default_font_size(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PerformanceConfig {
    #[serde(default = "default_screenshot_method")]
    pub screenshot_method: String,
    #[serde(default = "default_max_fps")]
    pub max_fps: u32,
    #[serde(default = "default_memory_limit")]
    pub memory_limit_mb: u32,
}

fn default_screenshot_method() -> String {
    "mss".to_string()
}

fn default_max_fps() -> u32 {
    30
}

fn default_memory_limit() -> u32 {
    400
}

impl Default for PerformanceConfig {
    fn default() -> Self {
        Self {
            screenshot_method: default_screenshot_method(),
            max_fps: default_max_fps(),
            memory_limit_mb: default_memory_limit(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct AppConfig {
    #[serde(default)]
    pub hotkeys: HotkeyConfig,
    #[serde(default)]
    pub defaults: DefaultsConfig,
    #[serde(default)]
    pub ui: UiConfig,
    #[serde(default)]
    pub performance: PerformanceConfig,
    #[serde(default)]
    pub recent_files: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TriggerConfig {
    #[serde(default)]
    pub id: String,
    #[serde(default = "default_trigger_type")]
    pub trigger_type: String,
    #[serde(default = "default_true")]
    pub enabled: bool,
    #[serde(default)]
    pub macro_file: String,
    #[serde(default = "default_trigger_cooldown")]
    pub cooldown_ms: u32,
    #[serde(default)]
    pub params: Value,
}

fn default_trigger_cooldown() -> u32 {
    5_000
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ScheduleTriggerParams {
    #[serde(default = "default_schedule_mode")]
    pub mode: String,
    #[serde(default = "default_schedule_interval")]
    pub interval_min: u32,
    #[serde(default = "default_schedule_time")]
    pub time: String,
    #[serde(default = "default_weekdays")]
    pub weekdays: Vec<u8>,
}

fn default_schedule_interval() -> u32 {
    5
}

fn default_schedule_time() -> String {
    "08:00".to_string()
}

fn default_weekdays() -> Vec<u8> {
    vec![0, 1, 2, 3, 4]
}

impl Default for ScheduleTriggerParams {
    fn default() -> Self {
        Self {
            mode: default_schedule_mode(),
            interval_min: default_schedule_interval(),
            time: default_schedule_time(),
            weekdays: default_weekdays(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct WindowFocusTriggerParams {
    #[serde(default = "default_window_match_type")]
    pub match_type: String,
    #[serde(default)]
    pub match_value: String,
}

fn default_window_match_type() -> String {
    "title_contains".to_string()
}

impl Default for WindowFocusTriggerParams {
    fn default() -> Self {
        Self {
            match_type: default_window_match_type(),
            match_value: String::new(),
        }
    }
}

pub fn parse_macro_str(input: &str) -> Result<MacroDocument, SchemaError> {
    Ok(serde_json::from_str(input)?)
}

pub fn parse_config_str(input: &str) -> Result<AppConfig, SchemaError> {
    Ok(serde_json::from_str(input)?)
}

pub fn parse_triggers_str(input: &str) -> Result<Vec<TriggerConfig>, SchemaError> {
    Ok(serde_json::from_str(input)?)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_example_macro() {
        let raw = include_str!("../../../../macros/example.json");
        let macro_doc = parse_macro_str(raw).expect("example macro should parse");
        assert_eq!(macro_doc.name, "Example - Click and Type");
        assert_eq!(macro_doc.actions.len(), 4);
        assert_eq!(macro_doc.actions[1].normalized_type(), "mouse_click");
    }

    #[test]
    fn parses_current_config() {
        let raw = include_str!("../../../../config.json");
        let config = parse_config_str(raw).expect("config should parse");
        assert_eq!(config.hotkeys.start_stop, "F6");
        assert_eq!(config.performance.memory_limit_mb, 400);
    }

    #[test]
    fn parses_empty_triggers_file() {
        let raw = include_str!("../../../../macros/.triggers.json");
        let triggers = parse_triggers_str(raw).expect("triggers should parse");
        assert!(triggers.is_empty());
    }
}
