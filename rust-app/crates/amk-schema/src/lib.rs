//! AutoMacro JSON Schema — parse, validate, and serialize macro/config/trigger files.
//!
//! This crate is the single source of truth for file format compatibility between
//! Python AutoMacro and Rust AutoMacro. It handles:
//! - Legacy action type aliases (e.g. `click` → `mouse_click`)
//! - Default values for missing fields
//! - Round-trip serialization (load → save → load = identical)

use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};
use thiserror::Error;

// ── Error ────────────────────────────────────────────────────────────────

/// Errors that can occur when parsing or saving AutoMacro files.
#[derive(Debug, Error)]
pub enum SchemaError {
    /// JSON syntax or structure error.
    #[error("invalid JSON: {0}")]
    InvalidJson(#[from] serde_json::Error),

    /// File system error (read/write).
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
}

// ── On-Error Policy ──────────────────────────────────────────────────────

/// What to do when an action fails.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "snake_case")]
pub enum OnErrorPolicy {
    /// Stop the entire macro.
    #[default]
    Stop,
    /// Skip the failed action and continue.
    Skip,
    /// Continue execution (alias for Skip, used by older macros).
    Continue,
    /// Retry the action (up to repeat_count).
    Retry,
}

// ── Defaults (consolidated) ──────────────────────────────────────────────

mod defaults {
    pub(crate) const fn repeat_count() -> u32 {
        1
    }
    pub(crate) const fn loop_count() -> u32 {
        1
    }
    pub(crate) const fn click_delay() -> u32 {
        100
    }
    pub(crate) const fn typing_speed() -> u32 {
        50
    }
    pub(crate) const fn image_confidence() -> f64 {
        0.8
    }
    pub(crate) const fn speed_factor() -> f64 {
        1.0
    }
    pub(crate) const fn max_fps() -> u32 {
        30
    }
    pub(crate) const fn memory_limit_mb() -> u32 {
        400
    }
    pub(crate) const fn autosave_interval() -> u32 {
        60
    }
    pub(crate) const fn font_size() -> u32 {
        10
    }
    pub(crate) const fn cooldown_ms() -> u32 {
        5_000
    }
}

// Serde needs functions (not consts) for `#[serde(default = "...")]`
fn default_true() -> bool {
    true
}
fn serde_repeat_count() -> u32 {
    defaults::repeat_count()
}
fn serde_loop_count() -> u32 {
    defaults::loop_count()
}
fn serde_click_delay() -> u32 {
    defaults::click_delay()
}
fn serde_typing_speed() -> u32 {
    defaults::typing_speed()
}
fn serde_image_confidence() -> f64 {
    defaults::image_confidence()
}
fn serde_speed_factor() -> f64 {
    defaults::speed_factor()
}
fn serde_max_fps() -> u32 {
    defaults::max_fps()
}
fn serde_memory_limit_mb() -> u32 {
    defaults::memory_limit_mb()
}
fn serde_font_size() -> u32 {
    defaults::font_size()
}
fn serde_cooldown_ms() -> u32 {
    defaults::cooldown_ms()
}
fn serde_autosave_interval() -> u32 {
    defaults::autosave_interval()
}

// ── Macro Document ───────────────────────────────────────────────────────

/// A complete macro file (.json).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MacroDocument {
    #[serde(default = "MacroDocument::default_name")]
    pub name: String,
    #[serde(default = "MacroDocument::default_version")]
    pub version: String,
    #[serde(default)]
    pub settings: MacroSettings,
    #[serde(default)]
    pub actions: Vec<RawAction>,
}

impl MacroDocument {
    fn default_name() -> String {
        "Untitled".into()
    }
    fn default_version() -> String {
        "1.1".into()
    }
}

impl Default for MacroDocument {
    fn default() -> Self {
        Self {
            name: Self::default_name(),
            version: Self::default_version(),
            settings: MacroSettings::default(),
            actions: Vec::new(),
        }
    }
}

/// Macro-level settings (loop count, delay, etc.).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MacroSettings {
    #[serde(default = "serde_loop_count")]
    pub loop_count: u32,
    #[serde(default)]
    pub delay_between_loops: u32,
    /// Forward-compat: unknown fields are preserved here.
    #[serde(default, flatten)]
    pub extras: Map<String, Value>,
}

impl Default for MacroSettings {
    fn default() -> Self {
        Self {
            loop_count: defaults::loop_count(),
            delay_between_loops: 0,
            extras: Map::new(),
        }
    }
}

// ── Raw Action ───────────────────────────────────────────────────────────

/// A single action as stored in JSON. Untyped params.
///
/// This is the persistence layer — `amk-domain` converts this into typed actions.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RawAction {
    /// Action type string (may be legacy alias).
    #[serde(rename = "type")]
    pub action_type: String,

    /// Untyped parameters (each action type has different params).
    #[serde(default)]
    pub params: Value,

    /// Delay in ms after this action completes.
    #[serde(default)]
    pub delay_after: u32,

    /// How many times to repeat this action.
    #[serde(default = "serde_repeat_count")]
    pub repeat_count: u32,

    /// User-facing description.
    #[serde(default)]
    pub description: String,

    /// Whether this action is enabled (disabled = skipped).
    #[serde(default = "default_true")]
    pub enabled: bool,

    /// What to do if this action fails.
    #[serde(default)]
    pub on_error: OnErrorPolicy,

    /// UI color tag for visual grouping.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub color: Option<String>,

    /// Whether this action is bookmarked.
    #[serde(default)]
    pub bookmarked: bool,

    /// Children for composite actions (if_*, loop_block, group).
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub sub_actions: Vec<RawAction>,

    /// Else-branch for if_* actions.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub else_actions: Vec<RawAction>,
}

impl RawAction {
    /// Get the canonical action type, resolving legacy aliases.
    #[must_use]
    pub fn normalized_type(&self) -> &str {
        normalize_action_type(&self.action_type)
    }

    /// Count total actions including nested sub/else actions.
    #[must_use]
    pub fn deep_count(&self) -> usize {
        1 + self.sub_actions.iter().map(Self::deep_count).sum::<usize>()
            + self.else_actions.iter().map(Self::deep_count).sum::<usize>()
    }
}

/// Map legacy aliases to canonical action types.
#[must_use]
pub fn normalize_action_type(raw: &str) -> &str {
    match raw {
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

/// All 36 canonical action types supported by AutoMacro.
pub const CANONICAL_ACTION_TYPES: &[&str] = &[
    "delay",
    "set_variable",
    "split_string",
    "comment",
    "group",
    "run_command",
    "log_to_file",
    "read_file_line",
    "write_to_file",
    "read_clipboard",
    "activate_window",
    "key_press",
    "key_combo",
    "type_text",
    "hotkey",
    "mouse_click",
    "mouse_double_click",
    "mouse_right_click",
    "mouse_move",
    "mouse_drag",
    "mouse_scroll",
    "check_pixel_color",
    "wait_for_color",
    "wait_for_image",
    "click_on_image",
    "image_exists",
    "take_screenshot",
    "secure_type_text",
    "run_macro",
    "capture_text",
    "if_variable",
    "if_pixel_color",
    "if_image_found",
    "loop_block",
    "stealth_click",
    "stealth_type",
];

// ── Config ───────────────────────────────────────────────────────────────

/// Application configuration (config.json).
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

/// Hotkey bindings.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct HotkeyConfig {
    #[serde(default = "HotkeyConfig::f6")]
    pub start_stop: String,
    #[serde(default = "HotkeyConfig::f7")]
    pub pause_resume: String,
    #[serde(default = "HotkeyConfig::f8")]
    pub emergency_stop: String,
    #[serde(default = "HotkeyConfig::f9")]
    pub record: String,
}

impl HotkeyConfig {
    fn f6() -> String { "F6".into() }
    fn f7() -> String { "F7".into() }
    fn f8() -> String { "F8".into() }
    fn f9() -> String { "F9".into() }
}

impl Default for HotkeyConfig {
    fn default() -> Self {
        Self {
            start_stop: Self::f6(),
            pause_resume: Self::f7(),
            emergency_stop: Self::f8(),
            record: Self::f9(),
        }
    }
}

/// Default values for action parameters.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DefaultsConfig {
    #[serde(default = "serde_click_delay")]
    pub click_delay: u32,
    #[serde(default = "serde_typing_speed")]
    pub typing_speed: u32,
    #[serde(default = "serde_image_confidence")]
    pub image_confidence: f64,
    #[serde(default = "default_true")]
    pub failsafe_enabled: bool,
    #[serde(default = "serde_speed_factor")]
    pub speed_factor: f64,
}

impl Default for DefaultsConfig {
    fn default() -> Self {
        Self {
            click_delay: defaults::click_delay(),
            typing_speed: defaults::typing_speed(),
            image_confidence: defaults::image_confidence(),
            failsafe_enabled: true,
            speed_factor: defaults::speed_factor(),
        }
    }
}

/// UI configuration.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct UiConfig {
    #[serde(default = "UiConfig::default_theme")]
    pub theme: String,
    #[serde(default)]
    pub accent_color: String,
    #[serde(default)]
    pub language: String,
    #[serde(default = "default_true")]
    pub minimize_to_tray: bool,
    #[serde(default = "UiConfig::neg1")]
    pub window_width: i32,
    #[serde(default = "UiConfig::neg1")]
    pub window_height: i32,
    #[serde(default = "UiConfig::neg1")]
    pub window_x: i32,
    #[serde(default = "UiConfig::neg1")]
    pub window_y: i32,
    #[serde(default)]
    pub window_maximized: bool,
    #[serde(default)]
    pub h_splitter_sizes: Vec<i32>,
    #[serde(default)]
    pub v_splitter_sizes: Vec<i32>,
    #[serde(default = "serde_font_size")]
    pub font_size: u32,
}

impl UiConfig {
    fn default_theme() -> String { "dark".into() }
    fn neg1() -> i32 { -1 }
}

impl Default for UiConfig {
    fn default() -> Self {
        Self {
            theme: Self::default_theme(),
            accent_color: String::new(),
            language: String::new(),
            minimize_to_tray: true,
            window_width: -1,
            window_height: -1,
            window_x: -1,
            window_y: -1,
            window_maximized: false,
            h_splitter_sizes: Vec::new(),
            v_splitter_sizes: Vec::new(),
            font_size: defaults::font_size(),
        }
    }
}

/// Performance tuning.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PerformanceConfig {
    #[serde(default = "PerformanceConfig::default_method")]
    pub screenshot_method: String,
    #[serde(default = "serde_max_fps")]
    pub max_fps: u32,
    #[serde(default = "serde_memory_limit_mb")]
    pub memory_limit_mb: u32,
    #[serde(default = "serde_autosave_interval")]
    pub autosave_interval_secs: u32,
}

impl PerformanceConfig {
    fn default_method() -> String { "mss".into() }
}

impl Default for PerformanceConfig {
    fn default() -> Self {
        Self {
            screenshot_method: Self::default_method(),
            max_fps: defaults::max_fps(),
            memory_limit_mb: defaults::memory_limit_mb(),
            autosave_interval_secs: defaults::autosave_interval(),
        }
    }
}

// ── Trigger Config ───────────────────────────────────────────────────────

/// A trigger that auto-starts a macro.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TriggerConfig {
    #[serde(default)]
    pub id: String,
    #[serde(default = "TriggerConfig::default_type")]
    pub trigger_type: String,
    #[serde(default = "default_true")]
    pub enabled: bool,
    #[serde(default)]
    pub macro_file: String,
    #[serde(default = "serde_cooldown_ms")]
    pub cooldown_ms: u32,
    #[serde(default)]
    pub params: Value,
}

impl TriggerConfig {
    fn default_type() -> String { "schedule".into() }
}

// ── Parse API ────────────────────────────────────────────────────────────

/// Parse a macro JSON string into a [`MacroDocument`].
#[must_use = "this returns the parsed document, which should be used"]
pub fn parse_macro(input: &str) -> Result<MacroDocument, SchemaError> {
    Ok(serde_json::from_str(input)?)
}

/// Parse a config JSON string into an [`AppConfig`].
#[must_use = "this returns the parsed config, which should be used"]
pub fn parse_config(input: &str) -> Result<AppConfig, SchemaError> {
    Ok(serde_json::from_str(input)?)
}

/// Parse a triggers JSON string into a vec of [`TriggerConfig`].
#[must_use = "this returns the parsed triggers, which should be used"]
pub fn parse_triggers(input: &str) -> Result<Vec<TriggerConfig>, SchemaError> {
    Ok(serde_json::from_str(input)?)
}

/// Load a macro from a file path.
pub fn load_macro(path: &std::path::Path) -> Result<MacroDocument, SchemaError> {
    let content = std::fs::read_to_string(path)?;
    parse_macro(&content)
}

/// Save a macro to a file path (pretty-printed JSON).
pub fn save_macro(path: &std::path::Path, doc: &MacroDocument) -> Result<(), SchemaError> {
    let content = serde_json::to_string_pretty(doc)?;
    std::fs::write(path, content)?;
    Ok(())
}

// ── Tests ────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    /// Path to macros directory (relative to crate source).
    fn macros_dir() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../../macros")
    }

    /// Load and parse a macro fixture file, panicking on error.
    fn load_fixture(name: &str) -> MacroDocument {
        let path = macros_dir().join(name);
        let content =
            std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("read {name}: {e}"));
        parse_macro(&content).unwrap_or_else(|e| panic!("parse {name}: {e}"))
    }

    // ── Basic parsing ─────────────────────────────────────

    #[test]
    fn parse_example_macro() {
        let doc = load_fixture("example.json");
        assert_eq!(doc.name, "Example - Click and Type");
        assert_eq!(doc.actions.len(), 4);
    }

    #[test]
    fn parse_config_json() {
        let content = std::fs::read_to_string(macros_dir().join("../config.json"))
            .expect("config.json should exist");
        let config = parse_config(&content).expect("config should parse");
        assert_eq!(config.hotkeys.start_stop, "F6");
        assert_eq!(config.performance.memory_limit_mb, 400);
    }

    #[test]
    fn parse_triggers_json() {
        let content = std::fs::read_to_string(macros_dir().join(".triggers.json"))
            .expect(".triggers.json should exist");
        let triggers = parse_triggers(&content).expect("triggers should parse");
        // File may be empty array or populated — just verify it parses
        let _ = triggers; // used
    }

    // ── All fixtures parse without error ──────────────────

    #[test]
    fn all_macro_fixtures_parse() {
        let dir = macros_dir();
        let mut count = 0;
        for entry in std::fs::read_dir(dir).expect("macros dir should exist") {
            let entry = entry.unwrap();
            let name = entry.file_name().into_string().unwrap();
            if name.ends_with(".json") && name != ".triggers.json" {
                let doc = load_fixture(&name);
                assert!(
                    !doc.actions.is_empty() || name == "example.json",
                    "{name} should have actions"
                );
                count += 1;
            }
        }
        assert!(count >= 15, "expected ≥15 fixtures, got {count}");
    }

    // ── Legacy alias normalization ────────────────────────

    #[test]
    fn normalize_legacy_aliases() {
        assert_eq!(normalize_action_type("click"), "mouse_click");
        assert_eq!(normalize_action_type("wait_image"), "wait_for_image");
        assert_eq!(normalize_action_type("set_var"), "set_variable");
        assert_eq!(normalize_action_type("loop"), "loop_block");
        assert_eq!(normalize_action_type("delay"), "delay");
    }

    // ── Roundtrip: parse → serialize → parse → compare ───

    #[test]
    fn roundtrip_example_macro() {
        let original = load_fixture("example.json");
        let serialized = serde_json::to_string_pretty(&original).unwrap();
        let reparsed: MacroDocument = serde_json::from_str(&serialized).unwrap();
        assert_eq!(original, reparsed);
    }

    #[test]
    fn roundtrip_all_fixtures() {
        let dir = macros_dir();
        for entry in std::fs::read_dir(dir).unwrap() {
            let entry = entry.unwrap();
            let name = entry.file_name().into_string().unwrap();
            if name.ends_with(".json") && name != ".triggers.json" {
                let doc = load_fixture(&name);
                let json = serde_json::to_string_pretty(&doc).unwrap();
                let reparsed: MacroDocument = serde_json::from_str(&json)
                    .unwrap_or_else(|e| panic!("roundtrip {name}: {e}"));
                assert_eq!(doc, reparsed, "roundtrip failed for {name}");
            }
        }
    }

    // ── Action type coverage ──────────────────────────────

    #[test]
    fn canonical_types_count() {
        assert_eq!(CANONICAL_ACTION_TYPES.len(), 36);
    }

    #[test]
    fn all_fixture_action_types_are_known() {
        let dir = macros_dir();
        let mut unknown = Vec::new();

        for entry in std::fs::read_dir(dir).unwrap() {
            let entry = entry.unwrap();
            let name = entry.file_name().into_string().unwrap();
            if name.ends_with(".json") && name != ".triggers.json" {
                let doc = load_fixture(&name);
                collect_unknown_types(&doc.actions, &name, &mut unknown);
            }
        }

        assert!(
            unknown.is_empty(),
            "Unknown action types found: {unknown:?}"
        );
    }

    fn collect_unknown_types(actions: &[RawAction], file: &str, out: &mut Vec<String>) {
        for action in actions {
            let normalized = action.normalized_type();
            if !CANONICAL_ACTION_TYPES.contains(&normalized) {
                out.push(format!("{file}: {normalized} (raw: {})", action.action_type));
            }
            collect_unknown_types(&action.sub_actions, file, out);
            collect_unknown_types(&action.else_actions, file, out);
        }
    }

    // ── Default values ───────────────────────────────────

    #[test]
    fn config_defaults_are_sensible() {
        let config = AppConfig::default();
        assert_eq!(config.hotkeys.start_stop, "F6");
        assert_eq!(config.defaults.image_confidence, 0.8);
        assert_eq!(config.performance.memory_limit_mb, 400);
        assert!(config.defaults.failsafe_enabled);
    }

    #[test]
    fn macro_document_defaults() {
        let doc = MacroDocument::default();
        assert_eq!(doc.name, "Untitled");
        assert_eq!(doc.version, "1.1");
        assert_eq!(doc.settings.loop_count, 1);
    }

    // ── On-Error Policy ──────────────────────────────────

    #[test]
    fn on_error_default_is_stop() {
        assert_eq!(OnErrorPolicy::default(), OnErrorPolicy::Stop);
    }

    #[test]
    fn on_error_serde_roundtrip() {
        let json = r#""skip""#;
        let policy: OnErrorPolicy = serde_json::from_str(json).unwrap();
        assert_eq!(policy, OnErrorPolicy::Skip);
        assert_eq!(serde_json::to_string(&policy).unwrap(), r#""skip""#);
    }

    // ── Deep count ───────────────────────────────────────

    #[test]
    fn deep_count_flat_action() {
        let doc = load_fixture("example.json");
        // Each action in example.json is flat (no children)
        for action in &doc.actions {
            assert_eq!(action.deep_count(), 1);
        }
    }
}
