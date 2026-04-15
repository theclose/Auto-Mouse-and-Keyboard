//! Convert `RawAction` (untyped JSON) → `TypedAction` (validated domain model).
//!
//! This is the bridge between persistence (schema) and execution (runtime).
//! Invalid params produce clear error messages rather than panics.

use amk_schema::{normalize_action_type, RawAction};
use serde_json::Value;
use thiserror::Error;

use crate::action::{ActionKind, MouseButton, TypedAction};

/// Errors during raw → typed conversion.
#[derive(Debug, Error)]
pub enum ConvertError {
    #[error("unknown action type: {0}")]
    UnknownType(String),

    #[error("missing required param '{param}' for action '{action_type}'")]
    MissingParam {
        action_type: String,
        param: String,
    },

    #[error("invalid param '{param}' for action '{action_type}': {reason}")]
    InvalidParam {
        action_type: String,
        param: String,
        reason: String,
    },
}

// ── Helper extractors ────────────────────────────────────────────────────

fn str_param(params: &Value, key: &str) -> String {
    params.get(key)
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_owned()
}

fn str_param_or(params: &Value, key: &str, default: &str) -> String {
    params.get(key)
        .and_then(Value::as_str)
        .unwrap_or(default)
        .to_owned()
}

fn u32_param(params: &Value, key: &str, default: u32) -> u32 {
    params.get(key)
        .and_then(|v| v.as_u64().or_else(|| v.as_f64().map(|f| f as u64)))
        .map(|v| v as u32)
        .unwrap_or(default)
}

fn i32_param(params: &Value, key: &str, default: i32) -> i32 {
    params.get(key)
        .and_then(|v| v.as_i64().or_else(|| v.as_f64().map(|f| f as i64)))
        .map(|v| v as i32)
        .unwrap_or(default)
}

fn f64_param(params: &Value, key: &str, default: f64) -> f64 {
    params.get(key)
        .and_then(|v| v.as_f64())
        .unwrap_or(default)
}

fn bool_param(params: &Value, key: &str, default: bool) -> bool {
    params.get(key)
        .and_then(Value::as_bool)
        .unwrap_or(default)
}

fn region_param(params: &Value) -> Option<[i32; 4]> {
    params.get("region").and_then(|v| {
        let arr = v.as_array()?;
        if arr.len() == 4 {
            Some([
                arr[0].as_i64()? as i32,
                arr[1].as_i64()? as i32,
                arr[2].as_i64()? as i32,
                arr[3].as_i64()? as i32,
            ])
        } else {
            None
        }
    })
}

fn mouse_button_param(params: &Value, key: &str) -> MouseButton {
    match params.get(key).and_then(Value::as_str).unwrap_or("left") {
        "right" => MouseButton::Right,
        "middle" => MouseButton::Middle,
        _ => MouseButton::Left,
    }
}

fn string_list_param(params: &Value, key: &str) -> Vec<String> {
    params.get(key)
        .and_then(Value::as_array)
        .map(|arr| {
            arr.iter()
                .filter_map(Value::as_str)
                .map(str::to_owned)
                .collect()
        })
        // Also support comma-separated string
        .or_else(|| {
            params.get(key)
                .and_then(Value::as_str)
                .map(|s| s.split(',').map(|p| p.trim().to_owned()).collect())
        })
        .unwrap_or_default()
}

// ── Main conversion ──────────────────────────────────────────────────────

/// Convert a single `RawAction` into a `TypedAction`.
pub fn convert_action(raw: &RawAction) -> Result<TypedAction, ConvertError> {
    let kind = convert_kind(raw)?;
    Ok(TypedAction {
        kind,
        delay_after: raw.delay_after,
        repeat_count: raw.repeat_count,
        description: raw.description.clone(),
        enabled: raw.enabled,
        on_error: raw.on_error,
        color: raw.color.clone(),
        bookmarked: raw.bookmarked,
    })
}

/// Convert a list of `RawAction`s.
pub fn convert_actions(raws: &[RawAction]) -> Result<Vec<TypedAction>, ConvertError> {
    raws.iter().map(convert_action).collect()
}

fn convert_children(raws: &[RawAction]) -> Result<Vec<TypedAction>, ConvertError> {
    convert_actions(raws)
}

fn convert_kind(raw: &RawAction) -> Result<ActionKind, ConvertError> {
    let p = &raw.params;
    let action_type = normalize_action_type(&raw.action_type);

    match action_type {
        "delay" => Ok(ActionKind::Delay {
            duration_ms: u32_param(p, "duration", u32_param(p, "ms", 1000)),
        }),

        "set_variable" => Ok(ActionKind::SetVariable {
            name: str_param(p, "name"),
            value: str_param(p, "value"),
        }),

        "split_string" => Ok(ActionKind::SplitString {
            input: str_param(p, "input"),
            delimiter: str_param_or(p, "delimiter", ","),
            output_prefix: str_param_or(p, "output_prefix", "split"),
        }),

        "comment" => Ok(ActionKind::Comment {
            text: str_param(p, "text"),
        }),

        "group" => Ok(ActionKind::Group {
            name: str_param_or(p, "name", "Group"),
            children: convert_children(&raw.sub_actions)?,
        }),

        "run_command" => Ok(ActionKind::RunCommand {
            command: str_param(p, "command"),
            wait: bool_param(p, "wait", true),
            capture_output: str_param(p, "capture_output"),
        }),

        "log_to_file" => Ok(ActionKind::LogToFile {
            file_path: str_param(p, "file_path"),
            message: str_param(p, "message"),
            append: bool_param(p, "append", true),
        }),

        "read_file_line" => Ok(ActionKind::ReadFileLine {
            file_path: str_param(p, "file_path"),
            line_number: i32_param(p, "line_number", 1),
            output_var: str_param_or(p, "output_var", "file_line"),
        }),

        "write_to_file" => Ok(ActionKind::WriteToFile {
            file_path: str_param(p, "file_path"),
            content: str_param(p, "content"),
            append: bool_param(p, "append", false),
        }),

        "read_clipboard" => Ok(ActionKind::ReadClipboard {
            output_var: str_param_or(p, "output_var", "clipboard"),
        }),

        "activate_window" => Ok(ActionKind::ActivateWindow {
            title: str_param(p, "title"),
            match_type: str_param_or(p, "match_type", "contains"),
        }),

        "key_press" => Ok(ActionKind::KeyPress {
            key: str_param(p, "key"),
            duration_ms: u32_param(p, "duration", 0),
        }),

        "key_combo" => Ok(ActionKind::KeyCombo {
            keys: string_list_param(p, "keys"),
        }),

        "type_text" => Ok(ActionKind::TypeText {
            text: str_param(p, "text"),
            interval_ms: f64_param(p, "interval", 0.02) * 1000.0,
        }),

        "hotkey" => Ok(ActionKind::Hotkey {
            keys: string_list_param(p, "keys"),
        }),

        "mouse_click" => Ok(ActionKind::MouseClick {
            x: i32_param(p, "x", 0),
            y: i32_param(p, "y", 0),
            button: mouse_button_param(p, "button"),
            clicks: u32_param(p, "clicks", 1),
        }),

        "mouse_double_click" => Ok(ActionKind::MouseDoubleClick {
            x: i32_param(p, "x", 0),
            y: i32_param(p, "y", 0),
            button: mouse_button_param(p, "button"),
        }),

        "mouse_right_click" => Ok(ActionKind::MouseRightClick {
            x: i32_param(p, "x", 0),
            y: i32_param(p, "y", 0),
        }),

        "mouse_move" => Ok(ActionKind::MouseMove {
            x: i32_param(p, "x", 0),
            y: i32_param(p, "y", 0),
            duration_ms: u32_param(p, "duration", 0),
        }),

        "mouse_drag" => Ok(ActionKind::MouseDrag {
            start_x: i32_param(p, "start_x", i32_param(p, "x", 0)),
            start_y: i32_param(p, "start_y", i32_param(p, "y", 0)),
            end_x: i32_param(p, "end_x", 0),
            end_y: i32_param(p, "end_y", 0),
            duration_ms: u32_param(p, "duration", 500),
            button: mouse_button_param(p, "button"),
        }),

        "mouse_scroll" => Ok(ActionKind::MouseScroll {
            x: i32_param(p, "x", 0),
            y: i32_param(p, "y", 0),
            clicks: i32_param(p, "clicks", 3),
        }),

        "check_pixel_color" => Ok(ActionKind::CheckPixelColor {
            x: i32_param(p, "x", 0),
            y: i32_param(p, "y", 0),
            expected_color: str_param(p, "color"),
            tolerance: u32_param(p, "tolerance", 10),
            result_var: str_param_or(p, "result_var", "pixel_match"),
        }),

        "wait_for_color" => Ok(ActionKind::WaitForColor {
            x: i32_param(p, "x", 0),
            y: i32_param(p, "y", 0),
            expected_color: str_param(p, "color"),
            tolerance: u32_param(p, "tolerance", 10),
            timeout_ms: u32_param(p, "timeout", 10000),
        }),

        "wait_for_image" => Ok(ActionKind::WaitForImage {
            image_path: str_param(p, "image_path"),
            confidence: f64_param(p, "confidence", 0.8),
            timeout_ms: u32_param(p, "timeout", 10000),
            region: region_param(p),
            grayscale: bool_param(p, "grayscale", false),
        }),

        "click_on_image" => Ok(ActionKind::ClickOnImage {
            image_path: str_param(p, "image_path"),
            confidence: f64_param(p, "confidence", 0.8),
            timeout_ms: u32_param(p, "timeout", 10000),
            button: mouse_button_param(p, "button"),
            region: region_param(p),
            offset_x: i32_param(p, "offset_x", 0),
            offset_y: i32_param(p, "offset_y", 0),
        }),

        "image_exists" => Ok(ActionKind::ImageExists {
            image_path: str_param(p, "image_path"),
            confidence: f64_param(p, "confidence", 0.8),
            result_var: str_param_or(p, "result_var", "image_found"),
            region: region_param(p),
        }),

        "take_screenshot" => Ok(ActionKind::TakeScreenshot {
            file_path: str_param(p, "file_path"),
            region: region_param(p),
        }),

        "capture_text" => Ok(ActionKind::CaptureText {
            region: region_param(p).unwrap_or([0, 0, 0, 0]),
            output_var: str_param_or(p, "output_var", "captured_text"),
            language: str_param_or(p, "language", "eng"),
        }),

        "secure_type_text" => Ok(ActionKind::SecureTypeText {
            encrypted_text: str_param(p, "encrypted_text"),
            interval_ms: f64_param(p, "interval", 0.02) * 1000.0,
        }),

        "run_macro" => Ok(ActionKind::RunMacro {
            macro_path: str_param(p, "macro_path"),
        }),

        "stealth_click" => Ok(ActionKind::StealthClick {
            window_title: str_param(p, "window_title"),
            x: i32_param(p, "x", 0),
            y: i32_param(p, "y", 0),
            button: mouse_button_param(p, "button"),
        }),

        "stealth_type" => Ok(ActionKind::StealthType {
            window_title: str_param(p, "window_title"),
            text: str_param(p, "text"),
            interval_ms: f64_param(p, "interval", 0.02) * 1000.0,
        }),

        "if_variable" => Ok(ActionKind::IfVariable {
            variable: str_param(p, "variable"),
            operator: str_param_or(p, "operator", "=="),
            value: str_param(p, "value"),
            then_actions: convert_children(&raw.sub_actions)?,
            else_actions: convert_children(&raw.else_actions)?,
        }),

        "if_pixel_color" => Ok(ActionKind::IfPixelColor {
            x: i32_param(p, "x", 0),
            y: i32_param(p, "y", 0),
            expected_color: str_param(p, "color"),
            tolerance: u32_param(p, "tolerance", 10),
            then_actions: convert_children(&raw.sub_actions)?,
            else_actions: convert_children(&raw.else_actions)?,
        }),

        "if_image_found" => Ok(ActionKind::IfImageFound {
            image_path: str_param(p, "image_path"),
            confidence: f64_param(p, "confidence", 0.8),
            region: region_param(p),
            then_actions: convert_children(&raw.sub_actions)?,
            else_actions: convert_children(&raw.else_actions)?,
        }),

        "loop_block" => Ok(ActionKind::LoopBlock {
            count: i32_param(p, "count", i32_param(p, "iterations", 1)),
            children: convert_children(&raw.sub_actions)?,
        }),

        unknown => Err(ConvertError::UnknownType(unknown.to_owned())),
    }
}

// ── Tests ────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    fn macros_dir() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../../macros")
    }

    fn load_fixture(name: &str) -> amk_schema::MacroDocument {
        let path = macros_dir().join(name);
        let content = std::fs::read_to_string(&path).unwrap();
        amk_schema::parse_macro(&content).unwrap()
    }

    #[test]
    fn convert_example_macro() {
        let doc = load_fixture("example.json");
        let typed = convert_actions(&doc.actions).expect("should convert");
        assert_eq!(typed.len(), 4);
    }

    #[test]
    fn convert_all_fixtures() {
        let dir = macros_dir();
        let mut total = 0;
        let mut converted = 0;
        for entry in std::fs::read_dir(dir).unwrap() {
            let entry = entry.unwrap();
            let name = entry.file_name().into_string().unwrap();
            if name.ends_with(".json") && name != ".triggers.json" {
                let doc = load_fixture(&name);
                total += 1;
                match convert_actions(&doc.actions) {
                    Ok(actions) => {
                        assert!(!actions.is_empty() || name == "example.json",
                            "{name}: expected actions");
                        converted += 1;
                    }
                    Err(e) => {
                        panic!("Failed to convert {name}: {e}");
                    }
                }
            }
        }
        assert!(total >= 15, "expected ≥15 fixtures");
        assert_eq!(total, converted, "all fixtures should convert");
    }

    #[test]
    fn convert_delay() {
        let raw = RawAction {
            action_type: "delay".into(),
            params: serde_json::json!({"duration": 500}),
            delay_after: 0,
            repeat_count: 1,
            description: String::new(),
            enabled: true,
            on_error: Default::default(),
            color: None,
            bookmarked: false,
            sub_actions: vec![],
            else_actions: vec![],
        };
        let typed = convert_action(&raw).unwrap();
        assert!(matches!(typed.kind, ActionKind::Delay { duration_ms: 500 }));
    }

    #[test]
    fn convert_mouse_click() {
        let raw = RawAction {
            action_type: "click".into(), // legacy alias!
            params: serde_json::json!({"x": 100, "y": 200, "button": "right"}),
            delay_after: 50,
            repeat_count: 2,
            description: "test".into(),
            enabled: true,
            on_error: Default::default(),
            color: None,
            bookmarked: false,
            sub_actions: vec![],
            else_actions: vec![],
        };
        let typed = convert_action(&raw).unwrap();
        match &typed.kind {
            ActionKind::MouseClick { x, y, button, clicks } => {
                assert_eq!(*x, 100);
                assert_eq!(*y, 200);
                assert_eq!(*button, MouseButton::Right);
                assert_eq!(*clicks, 1);
            }
            _ => panic!("expected MouseClick"),
        }
        assert_eq!(typed.delay_after, 50);
        assert_eq!(typed.repeat_count, 2);
    }

    #[test]
    fn convert_unknown_type_errors() {
        let raw = RawAction {
            action_type: "nonexistent_action".into(),
            params: serde_json::json!({}),
            delay_after: 0,
            repeat_count: 1,
            description: String::new(),
            enabled: true,
            on_error: Default::default(),
            color: None,
            bookmarked: false,
            sub_actions: vec![],
            else_actions: vec![],
        };
        let err = convert_action(&raw).unwrap_err();
        assert!(matches!(err, ConvertError::UnknownType(_)));
    }

    #[test]
    fn convert_type_text() {
        let raw = RawAction {
            action_type: "type_text".into(),
            params: serde_json::json!({"text": "hello", "interval": 0.05}),
            delay_after: 0,
            repeat_count: 1,
            description: String::new(),
            enabled: true,
            on_error: Default::default(),
            color: None,
            bookmarked: false,
            sub_actions: vec![],
            else_actions: vec![],
        };
        let typed = convert_action(&raw).unwrap();
        match &typed.kind {
            ActionKind::TypeText { text, interval_ms } => {
                assert_eq!(text, "hello");
                assert!((interval_ms - 50.0).abs() < 0.1);
            }
            _ => panic!("expected TypeText"),
        }
    }
}
