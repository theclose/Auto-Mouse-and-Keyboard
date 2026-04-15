//! Integration tests — full pipeline: JSON → Schema → Domain → Engine → Report
//!
//! These tests validate the entire stack using real macro JSON fixtures.

use amk_domain::action::MouseButton;
use amk_domain::convert_actions;
use amk_runtime::engine::MacroEngine;
use amk_runtime::executor::{ActionResult, Executor};
use amk_runtime::report::ExitReason;
use amk_schema::parse_macro;
use std::path::PathBuf;

/// Path to the macros directory.
fn macros_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../../macros")
}

/// Mock executor that records calls without doing anything.
struct RecordingExecutor {
    log: Vec<String>,
}

impl RecordingExecutor {
    fn new() -> Self {
        Self { log: Vec::new() }
    }
}

impl Executor for RecordingExecutor {
    fn delay(&mut self, ms: u32) -> ActionResult { self.log.push(format!("delay:{ms}")); ActionResult::ok() }
    fn mouse_click(&mut self, x: i32, y: i32, _b: MouseButton, c: u32) -> ActionResult { self.log.push(format!("click:{x},{y}x{c}")); ActionResult::ok() }
    fn mouse_move(&mut self, x: i32, y: i32, _d: u32) -> ActionResult { self.log.push(format!("move:{x},{y}")); ActionResult::ok() }
    fn mouse_drag(&mut self, sx: i32, sy: i32, ex: i32, ey: i32, _d: u32, _b: MouseButton) -> ActionResult { self.log.push(format!("drag:{sx},{sy}->{ex},{ey}")); ActionResult::ok() }
    fn mouse_scroll(&mut self, _x: i32, _y: i32, c: i32) -> ActionResult { self.log.push(format!("scroll:{c}")); ActionResult::ok() }
    fn key_press(&mut self, key: &str, _d: u32) -> ActionResult { self.log.push(format!("key:{key}")); ActionResult::ok() }
    fn key_combo(&mut self, keys: &[String]) -> ActionResult { self.log.push(format!("combo:{}", keys.join("+"))); ActionResult::ok() }
    fn type_text(&mut self, text: &str, _i: f64) -> ActionResult { self.log.push(format!("type:{text}")); ActionResult::ok() }
    fn run_command(&mut self, cmd: &str, _w: bool) -> ActionResult { self.log.push(format!("cmd:{cmd}")); ActionResult::ok_with("output") }
    fn read_clipboard(&mut self) -> ActionResult { self.log.push("clipboard".into()); ActionResult::ok_with("clip") }
    fn activate_window(&mut self, title: &str, _m: &str) -> ActionResult { self.log.push(format!("activate:{title}")); ActionResult::ok() }
    fn log_to_file(&mut self, _p: &str, msg: &str, _a: bool) -> ActionResult { self.log.push(format!("log:{msg}")); ActionResult::ok() }
    fn read_file_line(&mut self, _p: &str, n: i32) -> ActionResult { self.log.push(format!("readline:{n}")); ActionResult::ok_with("line") }
    fn write_to_file(&mut self, _p: &str, c: &str, _a: bool) -> ActionResult { self.log.push(format!("write:{c}")); ActionResult::ok() }
    fn check_pixel_color(&mut self, x: i32, y: i32, _c: &str, _t: u32) -> ActionResult { self.log.push(format!("pixel:{x},{y}")); ActionResult::ok_with("true") }
    fn wait_for_color(&mut self, _x: i32, _y: i32, _c: &str, _t: u32, _to: u32) -> ActionResult { self.log.push("wait_color".into()); ActionResult::ok() }
    fn wait_for_image(&mut self, _p: &str, _c: f64, _t: u32, _r: Option<[i32; 4]>, _g: bool) -> ActionResult { self.log.push("wait_image".into()); ActionResult::ok() }
    fn click_on_image(&mut self, _p: &str, _c: f64, _t: u32, _b: MouseButton, _r: Option<[i32; 4]>, _ox: i32, _oy: i32) -> ActionResult { self.log.push("click_image".into()); ActionResult::ok() }
    fn image_exists(&mut self, _p: &str, _c: f64, _r: Option<[i32; 4]>) -> ActionResult { self.log.push("image_exists".into()); ActionResult::ok_with("true") }
    fn take_screenshot(&mut self, _p: &str, _r: Option<[i32; 4]>) -> ActionResult { self.log.push("screenshot".into()); ActionResult::ok() }
    fn capture_text(&mut self, _r: [i32; 4], _l: &str) -> ActionResult { self.log.push("ocr".into()); ActionResult::ok_with("text") }
    fn secure_type_text(&mut self, _e: &str, _i: f64) -> ActionResult { self.log.push("secure_type".into()); ActionResult::ok() }
    fn run_macro(&mut self, p: &str) -> ActionResult { self.log.push(format!("run_macro:{p}")); ActionResult::ok() }
    fn stealth_click(&mut self, _w: &str, x: i32, y: i32, _b: MouseButton) -> ActionResult { self.log.push(format!("stealth_click:{x},{y}")); ActionResult::ok() }
    fn stealth_type(&mut self, _w: &str, text: &str, _i: f64) -> ActionResult { self.log.push(format!("stealth_type:{text}")); ActionResult::ok() }
}

// ── Integration Tests ────────────────────────────────────────────────────

#[test]
fn full_pipeline_example_macro() {
    let path = macros_dir().join("example.json");
    let content = std::fs::read_to_string(&path).expect("example.json should exist");
    let doc = parse_macro(&content).expect("should parse");
    let typed = convert_actions(&doc.actions).expect("should convert");

    assert!(!typed.is_empty(), "example should have actions");

    let engine = MacroEngine::new();
    let mut exec = RecordingExecutor::new();
    let report = engine.run(&typed, 1, 0, &mut exec);

    assert_eq!(report.exit_reason, ExitReason::Completed);
    assert_eq!(report.actions_executed, typed.len() as u64);
    assert_eq!(report.actions_failed, 0);
    assert!(!exec.log.is_empty(), "should have executed something");
}

#[test]
fn all_fixtures_convert_successfully() {
    let dir = macros_dir();
    let mut count = 0;
    for entry in std::fs::read_dir(&dir).expect("macros dir") {
        let entry = entry.unwrap();
        let name = entry.file_name().into_string().unwrap();
        if name.ends_with(".json") && name != ".triggers.json" {
            let content = std::fs::read_to_string(entry.path()).unwrap();
            let doc = parse_macro(&content)
                .unwrap_or_else(|e| panic!("{name}: parse failed: {e}"));
            let typed = convert_actions(&doc.actions)
                .unwrap_or_else(|e| panic!("{name}: convert failed: {e}"));
            assert!(
                !typed.is_empty() || name == "example.json",
                "{name} should have typed actions"
            );
            count += 1;
        }
    }
    assert!(count >= 15, "expected >= 15 fixtures, got {count}");
}

#[test]
fn engine_respects_disabled_actions() {
    let json = r#"{
        "name": "test_disabled",
        "actions": [
            { "type": "delay", "params": { "ms": 10 } },
            { "type": "delay", "params": { "ms": 20 }, "enabled": false },
            { "type": "delay", "params": { "ms": 30 } }
        ]
    }"#;
    let doc = parse_macro(json).unwrap();
    let typed = convert_actions(&doc.actions).unwrap();
    let engine = MacroEngine::new();
    let mut exec = RecordingExecutor::new();
    let report = engine.run(&typed, 1, 0, &mut exec);

    assert_eq!(report.exit_reason, ExitReason::Completed);
    assert_eq!(exec.log, vec!["delay:10", "delay:30"]);
    assert_eq!(report.actions_skipped, 1);
}

#[test]
fn engine_handles_composite_loop_from_json() {
    let json = r#"{
        "name": "test_loop",
        "actions": [
            {
                "type": "loop_block",
                "params": { "count": 3 },
                "sub_actions": [
                    { "type": "delay", "params": { "ms": 1 } }
                ]
            }
        ]
    }"#;
    let doc = parse_macro(json).unwrap();
    let typed = convert_actions(&doc.actions).unwrap();
    let engine = MacroEngine::new();
    let mut exec = RecordingExecutor::new();
    let report = engine.run(&typed, 1, 0, &mut exec);

    assert_eq!(report.exit_reason, ExitReason::Completed);
    assert_eq!(exec.log.len(), 3); // 3 delays inside loop
}

#[test]
fn engine_handles_if_variable_from_json() {
    let json = r#"{
        "name": "test_if",
        "actions": [
            { "type": "set_variable", "params": { "name": "x", "value": "hello" } },
            {
                "type": "if_variable",
                "params": { "variable": "x", "operator": "==", "value": "hello" },
                "sub_actions": [
                    { "type": "delay", "params": { "ms": 1 } }
                ],
                "else_actions": [
                    { "type": "delay", "params": { "ms": 999 } }
                ]
            }
        ]
    }"#;
    let doc = parse_macro(json).unwrap();
    let typed = convert_actions(&doc.actions).unwrap();
    let engine = MacroEngine::new();
    let mut exec = RecordingExecutor::new();
    let report = engine.run(&typed, 1, 0, &mut exec);

    assert_eq!(report.exit_reason, ExitReason::Completed);
    assert_eq!(exec.log, vec!["delay:1"]); // then branch
}

#[test]
fn engine_variable_interpolation_from_json() {
    let json = r#"{
        "name": "test_interp",
        "actions": [
            { "type": "set_variable", "params": { "name": "user", "value": "World" } },
            { "type": "type_text", "params": { "text": "Hello {user}!", "interval_ms": 0 } }
        ]
    }"#;
    let doc = parse_macro(json).unwrap();
    let typed = convert_actions(&doc.actions).unwrap();
    let engine = MacroEngine::new();
    let mut exec = RecordingExecutor::new();
    let report = engine.run(&typed, 1, 0, &mut exec);

    assert_eq!(report.exit_reason, ExitReason::Completed);
    assert_eq!(exec.log, vec!["type:Hello World!"]);
}
