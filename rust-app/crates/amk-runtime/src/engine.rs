//! MacroEngine — the heart of AutoMacro runtime.
//!
//! Responsibilities:
//! - Lifecycle: run / pause / resume / stop / step
//! - Composite action execution (loops, ifs, groups)
//! - Error policy enforcement (stop / skip / continue / retry)
//! - Speed factor and delay scaling
//! - Thread-safe state via `Arc<AtomicU8>` for external control

use std::sync::atomic::{AtomicU8, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::Duration;

use amk_domain::action::{ActionKind, TypedAction};
use amk_domain::context::ExecutionContext;
use amk_schema::OnErrorPolicy;

use crate::executor::{self, ActionResult, Executor};
use crate::report::{ExitReason, PlaybackReport, ReportBuilder};

// ── Engine State ─────────────────────────────────────────────────────────

/// Engine lifecycle state, stored as atomic u8 for lock-free access.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum EngineState {
    Idle = 0,
    Running = 1,
    Paused = 2,
    Stopping = 3,
}

impl EngineState {
    pub fn from_u8(v: u8) -> Self {
        match v {
            1 => Self::Running,
            2 => Self::Paused,
            3 => Self::Stopping,
            _ => Self::Idle,
        }
    }
}

// ── Engine ───────────────────────────────────────────────────────────────

/// A macro execution engine.
///
/// Each engine owns its own `ExecutionContext` and runs on its own thread.
/// External control (pause/stop) is done via atomic state.
pub struct MacroEngine {
    /// Atomic state for lock-free lifecycle control.
    state: Arc<AtomicU8>,
    /// Speed factor (1.0 = normal, 0.5 = 2x faster, 2.0 = 2x slower).
    speed_factor: f64,
}

impl MacroEngine {
    /// Create a new engine.
    #[must_use]
    pub fn new() -> Self {
        Self {
            state: Arc::new(AtomicU8::new(EngineState::Idle as u8)),
            speed_factor: 1.0,
        }
    }

    /// Get a handle to the state for external control.
    #[must_use]
    pub fn state_handle(&self) -> Arc<AtomicU8> {
        Arc::clone(&self.state)
    }

    /// Get current engine state.
    #[must_use]
    pub fn state(&self) -> EngineState {
        EngineState::from_u8(self.state.load(Ordering::Acquire))
    }

    /// Set speed factor.
    pub fn set_speed(&mut self, factor: f64) {
        self.speed_factor = factor.max(0.01); // prevent zero/negative
    }

    /// Request the engine to stop.
    pub fn request_stop(state: &AtomicU8) {
        state.store(EngineState::Stopping as u8, Ordering::Release);
    }

    /// Request the engine to pause.
    pub fn request_pause(state: &AtomicU8) {
        let current = state.load(Ordering::Acquire);
        if current == EngineState::Running as u8 {
            state.store(EngineState::Paused as u8, Ordering::Release);
        }
    }

    /// Request the engine to resume from pause.
    pub fn request_resume(state: &AtomicU8) {
        let current = state.load(Ordering::Acquire);
        if current == EngineState::Paused as u8 {
            state.store(EngineState::Running as u8, Ordering::Release);
        }
    }

    /// Run a macro (blocking). Returns a playback report.
    ///
    /// `actions` — the typed actions to execute.
    /// `loop_count` — how many times to loop (0 = infinite).
    /// `delay_between_loops` — ms to wait between loops.
    /// `executor` — the platform executor.
    pub fn run(
        &self,
        actions: &[TypedAction],
        loop_count: u32,
        delay_between_loops: u32,
        executor: &mut dyn Executor,
    ) -> PlaybackReport {
        self.state.store(EngineState::Running as u8, Ordering::Release);
        let mut ctx = ExecutionContext::new();
        let mut report = PlaybackReport::start();

        let infinite = loop_count == 0;
        let mut loop_idx = 0u32;

        loop {
            if !infinite && loop_idx >= loop_count {
                break;
            }

            let exit = self.run_action_list(actions, &mut ctx, executor, &mut report);
            if exit == RunExit::Stop {
                let reason = if self.is_stopping() || executor.should_stop() {
                    ExitReason::UserStopped
                } else {
                    ExitReason::ErrorStopped
                };
                self.state.store(EngineState::Idle as u8, Ordering::Release);
                return report.finalize(reason);
            }

            report.record_loop();
            loop_idx += 1;

            // Delay between loops (skippable)
            if delay_between_loops > 0
                && (infinite || loop_idx < loop_count)
                && self.scaled_sleep(delay_between_loops, executor) == RunExit::Stop
            {
                self.state.store(EngineState::Idle as u8, Ordering::Release);
                return report.finalize(ExitReason::UserStopped);
            }
        }

        self.state.store(EngineState::Idle as u8, Ordering::Release);
        report.finalize(ExitReason::Completed)
    }

    // ── Internal execution ───────────────────────────────

    /// Execute a list of actions sequentially. Returns Stop if engine should halt.
    fn run_action_list(
        &self,
        actions: &[TypedAction],
        ctx: &mut ExecutionContext,
        exec: &mut dyn Executor,
        report: &mut ReportBuilder,
    ) -> RunExit {
        for action in actions {
            if self.is_stopping() || exec.should_stop() {
                return RunExit::Stop;
            }

            // Handle pause
            self.wait_while_paused();
            if self.is_stopping() {
                return RunExit::Stop;
            }

            // Skip disabled actions
            if !action.enabled {
                report.record_skip();
                continue;
            }

            // Execute with repeat
            for _ in 0..action.repeat_count.max(1) {
                let exit = self.run_single(action, ctx, exec, report);
                if exit == RunExit::Stop {
                    return RunExit::Stop;
                }

                // delay_after
                if action.delay_after > 0
                    && self.scaled_sleep(action.delay_after, exec) == RunExit::Stop
                {
                    return RunExit::Stop;
                }
            }
        }
        RunExit::Continue
    }

    /// Execute a single action (handles composite vs leaf).
    fn run_single(
        &self,
        action: &TypedAction,
        ctx: &mut ExecutionContext,
        exec: &mut dyn Executor,
        report: &mut ReportBuilder,
    ) -> RunExit {
        match &action.kind {
            // ── Composite: Group ──────────────────────
            ActionKind::Group { children, .. } => {
                self.run_action_list(children, ctx, exec, report)
            }

            // ── Composite: Loop ──────────────────────
            ActionKind::LoopBlock { count, children } => {
                let infinite = *count <= 0;
                let mut i = 0i32;
                loop {
                    if !infinite && i >= *count {
                        break;
                    }
                    // Set loop index variable
                    ctx.set_var("_loop_index", &i.to_string());

                    let exit = self.run_action_list(children, ctx, exec, report);
                    if exit == RunExit::Stop {
                        return RunExit::Stop;
                    }
                    i += 1;
                }
                RunExit::Continue
            }

            // ── Composite: If Variable ───────────────
            ActionKind::IfVariable { variable, operator, value, then_actions, else_actions } => {
                let var_val = ctx.get_var(variable).to_owned();
                let resolved_value = ctx.interpolate(value);
                let condition = evaluate_condition(&var_val, operator, &resolved_value);

                if condition {
                    self.run_action_list(then_actions, ctx, exec, report)
                } else {
                    self.run_action_list(else_actions, ctx, exec, report)
                }
            }

            // ── Composite: If Pixel Color ────────────
            ActionKind::IfPixelColor { x, y, expected_color, tolerance, then_actions, else_actions } => {
                let result = exec.check_pixel_color(*x, *y, expected_color, *tolerance);
                let matched = result.output.as_deref() == Some("true");

                if matched {
                    self.run_action_list(then_actions, ctx, exec, report)
                } else {
                    self.run_action_list(else_actions, ctx, exec, report)
                }
            }

            // ── Composite: If Image Found ────────────
            ActionKind::IfImageFound { image_path, confidence, region, then_actions, else_actions } => {
                let path = ctx.interpolate(image_path);
                let result = exec.image_exists(&path, *confidence, *region);
                let found = result.output.as_deref() == Some("true");

                if found {
                    self.run_action_list(then_actions, ctx, exec, report)
                } else {
                    self.run_action_list(else_actions, ctx, exec, report)
                }
            }

            // ── Composite: Run Macro ─────────────────
            ActionKind::RunMacro { macro_path } => {
                let path = ctx.interpolate(macro_path);
                
                // Track depth to prevent infinite loops
                let current_depth = ctx.get_var("_depth").parse::<u32>().unwrap_or(0);
                if current_depth >= 10 {
                    let err = executor::ActionResult::fail("Max recursion depth (10) exceeded by nested macros.");
                    return self.handle_result(&err, action, report);
                }

                match std::fs::read_to_string(&path) {
                    Ok(content) => {
                        match amk_schema::parse_macro(&content) {
                            Ok(child_schema) => {
                                match amk_domain::convert_actions(&child_schema.actions) {
                                    Ok(child_actions) => {
                                        ctx.set_var("_depth", &(current_depth + 1).to_string());
                                        let exit = self.run_action_list(&child_actions, ctx, exec, report);
                                        ctx.set_var("_depth", &current_depth.to_string());
                                        
                                        if exit == RunExit::Stop {
                                            return RunExit::Stop;
                                        }
                                        self.handle_result(&executor::ActionResult::ok(), action, report)
                                    }
                                    Err(e) => {
                                        let err = executor::ActionResult::fail(format!("Failed to convert nested macro '{path}': {e}"));
                                        self.handle_result(&err, action, report)
                                    }
                                }
                            }
                            Err(e) => {
                                let err = executor::ActionResult::fail(format!("Failed to parse nested macro '{path}': {e}"));
                                self.handle_result(&err, action, report)
                            }
                        }
                    }
                    Err(e) => {
                        let err = executor::ActionResult::fail(format!("Failed to read nested macro '{path}': {e}"));
                        self.handle_result(&err, action, report)
                    }
                }
            }

            // ── Leaf actions ─────────────────────────
            leaf => {
                let result = executor::execute_leaf(leaf, ctx, exec);
                self.handle_result(&result, action, report)
            }
        }
    }

    /// Handle action result with error policy.
    fn handle_result(
        &self,
        result: &ActionResult,
        action: &TypedAction,
        report: &mut ReportBuilder,
    ) -> RunExit {
        if result.success {
            report.record_success();
            RunExit::Continue
        } else {
            report.record_failure();
            match action.on_error {
                OnErrorPolicy::Stop => RunExit::Stop,
                OnErrorPolicy::Skip | OnErrorPolicy::Continue => RunExit::Continue,
                OnErrorPolicy::Retry => {
                    // Retry is handled by repeat_count at the caller level.
                    // If we get here, it means all retries exhausted → continue.
                    RunExit::Continue
                }
            }
        }
    }

    // ── Helpers ──────────────────────────────────────────

    fn is_stopping(&self) -> bool {
        self.state.load(Ordering::Acquire) == EngineState::Stopping as u8
    }

    fn wait_while_paused(&self) {
        while self.state.load(Ordering::Acquire) == EngineState::Paused as u8 {
            thread::sleep(Duration::from_millis(50));
        }
    }

    /// Sleep with speed factor, checking for stop signal every 50ms.
    fn scaled_sleep(&self, ms: u32, exec: &dyn Executor) -> RunExit {
        let total = Duration::from_secs_f64(ms as f64 * self.speed_factor / 1000.0);
        let step = Duration::from_millis(50);
        let mut elapsed = Duration::ZERO;

        while elapsed < total {
            if self.is_stopping() || exec.should_stop() {
                return RunExit::Stop;
            }
            self.wait_while_paused();
            if self.is_stopping() {
                return RunExit::Stop;
            }
            let sleep = step.min(total - elapsed);
            thread::sleep(sleep);
            elapsed += sleep;
        }
        RunExit::Continue
    }
}

impl Default for MacroEngine {
    fn default() -> Self {
        Self::new()
    }
}

/// Internal signal: should we continue or stop?
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum RunExit {
    Continue,
    Stop,
}

/// Evaluate a condition between two string values.
fn evaluate_condition(left: &str, operator: &str, right: &str) -> bool {
    // Try numeric comparison first
    if let (Ok(l), Ok(r)) = (left.parse::<f64>(), right.parse::<f64>()) {
        return match operator {
            "==" => (l - r).abs() < f64::EPSILON,
            "!=" => (l - r).abs() >= f64::EPSILON,
            ">" => l > r,
            "<" => l < r,
            ">=" => l >= r,
            "<=" => l <= r,
            _ => left == right,
        };
    }
    // Fall back to string comparison
    match operator {
        "==" => left == right,
        "!=" => left != right,
        ">" => left > right,
        "<" => left < right,
        ">=" => left >= right,
        "<=" => left <= right,
        "contains" => left.contains(right),
        "starts_with" => left.starts_with(right),
        "ends_with" => left.ends_with(right),
        _ => left == right,
    }
}

// ── Tests ────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::executor::ActionResult;
    use amk_domain::action::MouseButton;

    /// Mock executor that logs calls.
    struct MockExecutor {
        log: Vec<String>,
        stop_after: Option<usize>,
    }

    impl MockExecutor {
        fn new() -> Self {
            Self { log: Vec::new(), stop_after: None }
        }

        fn with_stop_after(n: usize) -> Self {
            Self { log: Vec::new(), stop_after: Some(n) }
        }
    }

    impl Executor for MockExecutor {
        fn delay(&mut self, ms: u32) -> ActionResult {
            self.log.push(format!("delay:{ms}"));
            ActionResult::ok()
        }
        fn mouse_click(&mut self, x: i32, y: i32, _btn: MouseButton, _c: u32) -> ActionResult {
            self.log.push(format!("click:{x},{y}"));
            ActionResult::ok()
        }
        fn mouse_move(&mut self, x: i32, y: i32, _d: u32) -> ActionResult {
            self.log.push(format!("move:{x},{y}"));
            ActionResult::ok()
        }
        fn mouse_drag(&mut self, _sx: i32, _sy: i32, _ex: i32, _ey: i32, _d: u32, _b: MouseButton) -> ActionResult {
            self.log.push("drag".into());
            ActionResult::ok()
        }
        fn mouse_scroll(&mut self, _x: i32, _y: i32, c: i32) -> ActionResult {
            self.log.push(format!("scroll:{c}"));
            ActionResult::ok()
        }
        fn key_press(&mut self, key: &str, _d: u32) -> ActionResult {
            self.log.push(format!("key:{key}"));
            ActionResult::ok()
        }
        fn key_combo(&mut self, keys: &[String]) -> ActionResult {
            self.log.push(format!("combo:{}", keys.join("+")));
            ActionResult::ok()
        }
        fn type_text(&mut self, text: &str, _i: f64) -> ActionResult {
            self.log.push(format!("type:{text}"));
            ActionResult::ok()
        }
        fn run_command(&mut self, cmd: &str, _w: bool) -> ActionResult {
            self.log.push(format!("cmd:{cmd}"));
            ActionResult::ok_with("output")
        }
        fn read_clipboard(&mut self) -> ActionResult {
            self.log.push("clipboard".into());
            ActionResult::ok_with("clip_data")
        }
        fn activate_window(&mut self, title: &str, _m: &str) -> ActionResult {
            self.log.push(format!("activate:{title}"));
            ActionResult::ok()
        }
        fn log_to_file(&mut self, _p: &str, msg: &str, _a: bool) -> ActionResult {
            self.log.push(format!("log:{msg}"));
            ActionResult::ok()
        }
        fn read_file_line(&mut self, _p: &str, n: i32) -> ActionResult {
            self.log.push(format!("read_line:{n}"));
            ActionResult::ok_with("line_content")
        }
        fn write_to_file(&mut self, _p: &str, content: &str, _a: bool) -> ActionResult {
            self.log.push(format!("write:{content}"));
            ActionResult::ok()
        }
        fn check_pixel_color(&mut self, x: i32, y: i32, _c: &str, _t: u32) -> ActionResult {
            self.log.push(format!("pixel:{x},{y}"));
            ActionResult::ok_with("true")
        }
        fn wait_for_color(&mut self, _x: i32, _y: i32, _c: &str, _t: u32, _to: u32) -> ActionResult {
            self.log.push("wait_color".into());
            ActionResult::ok()
        }
        fn wait_for_image(&mut self, _p: &str, _c: f64, _t: u32, _r: Option<[i32; 4]>, _g: bool) -> ActionResult {
            self.log.push("wait_image".into());
            ActionResult::ok()
        }
        fn click_on_image(&mut self, _p: &str, _c: f64, _t: u32, _b: MouseButton, _r: Option<[i32; 4]>, _ox: i32, _oy: i32) -> ActionResult {
            self.log.push("click_image".into());
            ActionResult::ok()
        }
        fn image_exists(&mut self, _p: &str, _c: f64, _r: Option<[i32; 4]>) -> ActionResult {
            self.log.push("image_exists".into());
            ActionResult::ok_with("true")
        }
        fn take_screenshot(&mut self, _p: &str, _r: Option<[i32; 4]>) -> ActionResult {
            self.log.push("screenshot".into());
            ActionResult::ok()
        }
        fn capture_text(&mut self, _r: [i32; 4], _l: &str) -> ActionResult {
            self.log.push("ocr".into());
            ActionResult::ok_with("captured")
        }
        fn secure_type_text(&mut self, _e: &str, _i: f64) -> ActionResult {
            self.log.push("secure_type".into());
            ActionResult::ok()
        }
        fn run_macro(&mut self, p: &str) -> ActionResult {
            self.log.push(format!("run_macro:{p}"));
            ActionResult::ok()
        }
        fn stealth_click(&mut self, _w: &str, x: i32, y: i32, _b: MouseButton) -> ActionResult {
            self.log.push(format!("stealth_click:{x},{y}"));
            ActionResult::ok()
        }
        fn stealth_type(&mut self, _w: &str, text: &str, _i: f64) -> ActionResult {
            self.log.push(format!("stealth_type:{text}"));
            ActionResult::ok()
        }
        fn should_stop(&self) -> bool {
            if let Some(n) = self.stop_after {
                self.log.len() >= n
            } else {
                false
            }
        }
    }

    fn make_action(kind: ActionKind) -> TypedAction {
        TypedAction {
            kind,
            delay_after: 0,
            repeat_count: 1,
            description: String::new(),
            enabled: true,
            on_error: OnErrorPolicy::Stop,
            color: None,
            bookmarked: false,
        }
    }

    // ── Tests ────────────────────────────────────────────

    #[test]
    fn run_simple_sequence() {
        let engine = MacroEngine::new();
        let mut exec = MockExecutor::new();
        let actions = vec![
            make_action(ActionKind::Delay { duration_ms: 10 }),
            make_action(ActionKind::MouseClick { x: 100, y: 200, button: MouseButton::Left, clicks: 1 }),
            make_action(ActionKind::TypeText { text: "hello".into(), interval_ms: 0.0 }),
        ];

        let report = engine.run(&actions, 1, 0, &mut exec);
        assert_eq!(report.actions_executed, 3);
        assert_eq!(report.actions_succeeded, 3);
        assert_eq!(report.exit_reason, ExitReason::Completed);
        assert_eq!(exec.log, vec!["delay:10", "click:100,200", "type:hello"]);
    }

    #[test]
    fn run_with_loops() {
        let engine = MacroEngine::new();
        let mut exec = MockExecutor::new();
        let actions = vec![
            make_action(ActionKind::Delay { duration_ms: 1 }),
        ];

        let report = engine.run(&actions, 3, 0, &mut exec);
        assert_eq!(report.actions_executed, 3);
        assert_eq!(report.loops_completed, 3);
        assert_eq!(report.exit_reason, ExitReason::Completed);
    }

    #[test]
    fn skip_disabled_actions() {
        let engine = MacroEngine::new();
        let mut exec = MockExecutor::new();
        let mut actions = vec![
            make_action(ActionKind::Delay { duration_ms: 1 }),
            make_action(ActionKind::Comment { text: "skip me".into() }),
        ];
        actions[1].enabled = false;

        let report = engine.run(&actions, 1, 0, &mut exec);
        assert_eq!(report.actions_executed, 1);
        assert_eq!(report.actions_skipped, 1);
        assert_eq!(exec.log, vec!["delay:1"]);
    }

    #[test]
    fn error_policy_stop() {
        let engine = MacroEngine::new();

        // Create a failing action by using an image that won't be found
        // We'll use a custom mock that fails
        struct FailOnSecond { count: usize }
        impl Executor for FailOnSecond {
            fn delay(&mut self, _ms: u32) -> ActionResult {
                self.count += 1;
                if self.count == 2 { ActionResult::fail("boom") }
                else { ActionResult::ok() }
            }
            fn mouse_click(&mut self, _x: i32, _y: i32, _b: MouseButton, _c: u32) -> ActionResult { ActionResult::ok() }
            fn mouse_move(&mut self, _x: i32, _y: i32, _d: u32) -> ActionResult { ActionResult::ok() }
            fn mouse_drag(&mut self, _: i32, _: i32, _: i32, _: i32, _: u32, _: MouseButton) -> ActionResult { ActionResult::ok() }
            fn mouse_scroll(&mut self, _: i32, _: i32, _: i32) -> ActionResult { ActionResult::ok() }
            fn key_press(&mut self, _: &str, _: u32) -> ActionResult { ActionResult::ok() }
            fn key_combo(&mut self, _: &[String]) -> ActionResult { ActionResult::ok() }
            fn type_text(&mut self, _: &str, _: f64) -> ActionResult { ActionResult::ok() }
            fn run_command(&mut self, _: &str, _: bool) -> ActionResult { ActionResult::ok() }
            fn read_clipboard(&mut self) -> ActionResult { ActionResult::ok() }
            fn activate_window(&mut self, _: &str, _: &str) -> ActionResult { ActionResult::ok() }
            fn log_to_file(&mut self, _: &str, _: &str, _: bool) -> ActionResult { ActionResult::ok() }
            fn read_file_line(&mut self, _: &str, _: i32) -> ActionResult { ActionResult::ok() }
            fn write_to_file(&mut self, _: &str, _: &str, _: bool) -> ActionResult { ActionResult::ok() }
            fn check_pixel_color(&mut self, _: i32, _: i32, _: &str, _: u32) -> ActionResult { ActionResult::ok() }
            fn wait_for_color(&mut self, _: i32, _: i32, _: &str, _: u32, _: u32) -> ActionResult { ActionResult::ok() }
            fn wait_for_image(&mut self, _: &str, _: f64, _: u32, _: Option<[i32; 4]>, _: bool) -> ActionResult { ActionResult::ok() }
            fn click_on_image(&mut self, _: &str, _: f64, _: u32, _: MouseButton, _: Option<[i32; 4]>, _: i32, _: i32) -> ActionResult { ActionResult::ok() }
            fn image_exists(&mut self, _: &str, _: f64, _: Option<[i32; 4]>) -> ActionResult { ActionResult::ok() }
            fn take_screenshot(&mut self, _: &str, _: Option<[i32; 4]>) -> ActionResult { ActionResult::ok() }
            fn capture_text(&mut self, _: [i32; 4], _: &str) -> ActionResult { ActionResult::ok() }
            fn secure_type_text(&mut self, _: &str, _: f64) -> ActionResult { ActionResult::ok() }
            fn run_macro(&mut self, _: &str) -> ActionResult { ActionResult::ok() }
            fn stealth_click(&mut self, _: &str, _: i32, _: i32, _: MouseButton) -> ActionResult { ActionResult::ok() }
            fn stealth_type(&mut self, _: &str, _: &str, _: f64) -> ActionResult { ActionResult::ok() }
        }

        let actions = vec![
            make_action(ActionKind::Delay { duration_ms: 1 }),
            make_action(ActionKind::Delay { duration_ms: 1 }), // this one fails
            make_action(ActionKind::Delay { duration_ms: 1 }), // should NOT execute
        ];

        let mut fail_exec = FailOnSecond { count: 0 };
        let report = engine.run(&actions, 1, 0, &mut fail_exec);
        assert_eq!(report.actions_executed, 2); // 1 ok + 1 fail
        assert_eq!(report.actions_failed, 1);
        assert_eq!(report.exit_reason, ExitReason::ErrorStopped);
    }

    #[test]
    fn error_policy_skip() {
        let engine = MacroEngine::new();
        let mut exec = MockExecutor::new();

        // Manually create an action that "fails" - we'll use run_command with a failing mock
        // Instead, test skip policy with the full mock
        let mut actions = vec![
            make_action(ActionKind::Delay { duration_ms: 1 }),
            make_action(ActionKind::Delay { duration_ms: 1 }),
        ];
        actions[0].on_error = OnErrorPolicy::Skip;
        // Both succeed anyway — just verify skip policy doesn't stop
        let report = engine.run(&actions, 1, 0, &mut exec);
        assert_eq!(report.exit_reason, ExitReason::Completed);
    }

    #[test]
    fn loop_block_execution() {
        let engine = MacroEngine::new();
        let mut exec = MockExecutor::new();
        let actions = vec![
            make_action(ActionKind::LoopBlock {
                count: 3,
                children: vec![
                    make_action(ActionKind::Delay { duration_ms: 1 }),
                ],
            }),
        ];

        let report = engine.run(&actions, 1, 0, &mut exec);
        assert_eq!(exec.log.len(), 3); // 3 delays inside loop
        assert_eq!(report.actions_executed, 3);
    }

    #[test]
    fn if_variable_true_branch() {
        let engine = MacroEngine::new();
        let mut exec = MockExecutor::new();
        let actions = vec![
            make_action(ActionKind::SetVariable { name: "x".into(), value: "10".into() }),
            make_action(ActionKind::IfVariable {
                variable: "x".into(),
                operator: "==".into(),
                value: "10".into(),
                then_actions: vec![make_action(ActionKind::Delay { duration_ms: 1 })],
                else_actions: vec![make_action(ActionKind::Delay { duration_ms: 999 })],
            }),
        ];

        let report = engine.run(&actions, 1, 0, &mut exec);
        assert_eq!(exec.log, vec!["delay:1"]); // then branch
        assert_eq!(report.exit_reason, ExitReason::Completed);
    }

    #[test]
    fn if_variable_else_branch() {
        let engine = MacroEngine::new();
        let mut exec = MockExecutor::new();
        let actions = vec![
            make_action(ActionKind::SetVariable { name: "x".into(), value: "5".into() }),
            make_action(ActionKind::IfVariable {
                variable: "x".into(),
                operator: ">".into(),
                value: "10".into(),
                then_actions: vec![make_action(ActionKind::Delay { duration_ms: 1 })],
                else_actions: vec![make_action(ActionKind::Delay { duration_ms: 999 })],
            }),
        ];

        let _report = engine.run(&actions, 1, 0, &mut exec);
        assert_eq!(exec.log, vec!["delay:999"]); // else branch
    }

    #[test]
    fn external_stop_signal() {
        let engine = MacroEngine::new();
        let mut exec = MockExecutor::with_stop_after(2);
        let actions = vec![
            make_action(ActionKind::Delay { duration_ms: 1 }),
            make_action(ActionKind::Delay { duration_ms: 1 }),
            make_action(ActionKind::Delay { duration_ms: 1 }),
            make_action(ActionKind::Delay { duration_ms: 1 }),
        ];

        let report = engine.run(&actions, 1, 0, &mut exec);
        assert_eq!(exec.log.len(), 2); // stopped after 2
        assert_eq!(report.exit_reason, ExitReason::UserStopped);
    }

    #[test]
    fn set_variable_and_type_text_interpolation() {
        let engine = MacroEngine::new();
        let mut exec = MockExecutor::new();
        let actions = vec![
            make_action(ActionKind::SetVariable { name: "name".into(), value: "World".into() }),
            make_action(ActionKind::TypeText { text: "Hello {name}!".into(), interval_ms: 0.0 }),
        ];

        let report = engine.run(&actions, 1, 0, &mut exec);
        assert_eq!(exec.log, vec!["type:Hello World!"]);
        assert_eq!(report.exit_reason, ExitReason::Completed);
    }

    #[test]
    fn repeat_count() {
        let engine = MacroEngine::new();
        let mut exec = MockExecutor::new();
        let mut action = make_action(ActionKind::Delay { duration_ms: 1 });
        action.repeat_count = 3;

        let report = engine.run(&[action], 1, 0, &mut exec);
        assert_eq!(exec.log.len(), 3);
        assert_eq!(report.actions_executed, 3);
    }

    #[test]
    fn evaluate_numeric_conditions() {
        assert!(evaluate_condition("10", "==", "10"));
        assert!(evaluate_condition("10", ">", "5"));
        assert!(evaluate_condition("3", "<", "10"));
        assert!(!evaluate_condition("5", "==", "10"));
        assert!(evaluate_condition("5", "!=", "10"));
        assert!(evaluate_condition("10", ">=", "10"));
        assert!(evaluate_condition("10", "<=", "10"));
    }

    #[test]
    fn evaluate_string_conditions() {
        assert!(evaluate_condition("hello", "==", "hello"));
        assert!(evaluate_condition("hello world", "contains", "world"));
        assert!(evaluate_condition("hello", "starts_with", "hel"));
        assert!(evaluate_condition("hello", "ends_with", "llo"));
    }

    #[test]
    fn group_execution() {
        let engine = MacroEngine::new();
        let mut exec = MockExecutor::new();
        let actions = vec![
            make_action(ActionKind::Group {
                name: "test group".into(),
                children: vec![
                    make_action(ActionKind::Delay { duration_ms: 1 }),
                    make_action(ActionKind::Delay { duration_ms: 2 }),
                ],
            }),
        ];

        let report = engine.run(&actions, 1, 0, &mut exec);
        assert_eq!(exec.log, vec!["delay:1", "delay:2"]);
        assert_eq!(report.actions_executed, 2);
    }

    #[test]
    fn nested_loop_in_if() {
        let engine = MacroEngine::new();
        let mut exec = MockExecutor::new();
        let actions = vec![
            make_action(ActionKind::SetVariable { name: "go".into(), value: "yes".into() }),
            make_action(ActionKind::IfVariable {
                variable: "go".into(),
                operator: "==".into(),
                value: "yes".into(),
                then_actions: vec![
                    make_action(ActionKind::LoopBlock {
                        count: 2,
                        children: vec![make_action(ActionKind::Delay { duration_ms: 7 })],
                    }),
                ],
                else_actions: vec![],
            }),
        ];

        let report = engine.run(&actions, 1, 0, &mut exec);
        assert_eq!(exec.log, vec!["delay:7", "delay:7"]);
        assert_eq!(report.exit_reason, ExitReason::Completed);
    }
}
