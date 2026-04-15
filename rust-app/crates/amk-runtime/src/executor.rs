//! Executor trait — the interface between engine and platform.
//!
//! The engine calls `Executor::execute()` for each action. Platform-specific
//! implementations (Win32, mock) fulfill the actual mouse/keyboard/image work.

use amk_domain::action::{ActionKind, MouseButton};
use amk_domain::context::ExecutionContext;

/// Result of executing a single action.
#[derive(Debug, Clone)]
pub struct ActionResult {
    /// Whether the action succeeded.
    pub success: bool,
    /// Optional output value (e.g. captured text, pixel check result).
    pub output: Option<String>,
    /// Error message if failed.
    pub error: Option<String>,
}

impl ActionResult {
    /// Create a successful result with no output.
    #[must_use]
    pub fn ok() -> Self {
        Self { success: true, output: None, error: None }
    }

    /// Create a successful result with output.
    #[must_use]
    pub fn ok_with(output: impl Into<String>) -> Self {
        Self { success: true, output: Some(output.into()), error: None }
    }

    /// Create a failed result.
    #[must_use]
    pub fn fail(error: impl Into<String>) -> Self {
        Self { success: false, output: None, error: Some(error.into()) }
    }
}

/// Trait for executing individual actions.
///
/// Implement this for each platform (Win32, mock for tests).
/// The engine handles control flow (loops, ifs, error policies) — the executor
/// only needs to handle leaf actions.
#[allow(clippy::too_many_arguments)]
pub trait Executor: Send {
    // ── Timing ─────────────────────────────────
    fn delay(&mut self, ms: u32) -> ActionResult;

    // ── Mouse ──────────────────────────────────
    fn mouse_click(&mut self, x: i32, y: i32, button: MouseButton, clicks: u32) -> ActionResult;
    fn mouse_move(&mut self, x: i32, y: i32, duration_ms: u32) -> ActionResult;
    fn mouse_drag(&mut self, sx: i32, sy: i32, ex: i32, ey: i32, dur: u32, btn: MouseButton) -> ActionResult;
    fn mouse_scroll(&mut self, x: i32, y: i32, clicks: i32) -> ActionResult;

    // ── Keyboard ───────────────────────────────
    fn key_press(&mut self, key: &str, duration_ms: u32) -> ActionResult;
    fn key_combo(&mut self, keys: &[String]) -> ActionResult;
    fn type_text(&mut self, text: &str, interval_ms: f64) -> ActionResult;

    // ── System ─────────────────────────────────
    fn run_command(&mut self, command: &str, wait: bool) -> ActionResult;
    fn read_clipboard(&mut self) -> ActionResult;
    fn activate_window(&mut self, title: &str, match_type: &str) -> ActionResult;

    // ── File I/O ───────────────────────────────
    fn log_to_file(&mut self, path: &str, message: &str, append: bool) -> ActionResult;
    fn read_file_line(&mut self, path: &str, line: i32) -> ActionResult;
    fn write_to_file(&mut self, path: &str, content: &str, append: bool) -> ActionResult;

    // ── Image/Pixel ────────────────────────────
    fn check_pixel_color(&mut self, x: i32, y: i32, color: &str, tolerance: u32) -> ActionResult;
    fn wait_for_color(&mut self, x: i32, y: i32, color: &str, tolerance: u32, timeout: u32) -> ActionResult;
    fn wait_for_image(&mut self, path: &str, confidence: f64, timeout: u32, region: Option<[i32; 4]>, grayscale: bool) -> ActionResult;
    fn click_on_image(&mut self, path: &str, confidence: f64, timeout: u32, btn: MouseButton, region: Option<[i32; 4]>, ox: i32, oy: i32) -> ActionResult;
    fn image_exists(&mut self, path: &str, confidence: f64, region: Option<[i32; 4]>) -> ActionResult;
    fn take_screenshot(&mut self, path: &str, region: Option<[i32; 4]>) -> ActionResult;

    // ── OCR ────────────────────────────────────
    fn capture_text(&mut self, region: [i32; 4], language: &str) -> ActionResult;

    // ── Security ───────────────────────────────
    fn secure_type_text(&mut self, encrypted: &str, interval_ms: f64) -> ActionResult;

    // ── Macro ──────────────────────────────────
    fn run_macro(&mut self, path: &str) -> ActionResult;

    // ── Stealth ────────────────────────────────
    fn stealth_click(&mut self, window: &str, x: i32, y: i32, btn: MouseButton) -> ActionResult;
    fn stealth_type(&mut self, window: &str, text: &str, interval_ms: f64) -> ActionResult;

    /// Check if engine should stop (e.g. external stop signal).
    fn should_stop(&self) -> bool { false }
}

/// Execute a single `ActionKind` with the given executor and context.
///
/// This function handles the dispatch and variable side-effects
/// but NOT control flow (loops, ifs) — that's the engine's job.
pub fn execute_leaf(
    kind: &ActionKind,
    ctx: &mut ExecutionContext,
    exec: &mut dyn Executor,
) -> ActionResult {
    match kind {
        ActionKind::Delay { duration_ms } => exec.delay(*duration_ms),

        ActionKind::SetVariable { name, value } => {
            let resolved = ctx.interpolate(value);
            ctx.set_var(name, &resolved);
            ActionResult::ok()
        }

        ActionKind::SplitString { input, delimiter, output_prefix } => {
            let resolved = ctx.interpolate(input);
            let parts: Vec<&str> = resolved.split(&ctx.interpolate(delimiter)).collect();
            ctx.set_var(&format!("{output_prefix}_count"), &parts.len().to_string());
            for (i, part) in parts.iter().enumerate() {
                ctx.set_var(&format!("{output_prefix}_{i}"), part);
            }
            ActionResult::ok()
        }

        ActionKind::Comment { .. } => ActionResult::ok(),

        ActionKind::RunCommand { command, wait, capture_output } => {
            let cmd = ctx.interpolate(command);
            let result = exec.run_command(&cmd, *wait);
            if !capture_output.is_empty() {
                if let Some(ref out) = result.output {
                    ctx.set_var(capture_output, out);
                }
            }
            result
        }

        ActionKind::LogToFile { file_path, message, append } => {
            let path = ctx.interpolate(file_path);
            let msg = ctx.interpolate(message);
            exec.log_to_file(&path, &msg, *append)
        }

        ActionKind::ReadFileLine { file_path, line_number, output_var } => {
            let path = ctx.interpolate(file_path);
            let result = exec.read_file_line(&path, *line_number);
            if let Some(ref out) = result.output {
                ctx.set_var(output_var, out);
            }
            result
        }

        ActionKind::WriteToFile { file_path, content, append } => {
            let path = ctx.interpolate(file_path);
            let text = ctx.interpolate(content);
            exec.write_to_file(&path, &text, *append)
        }

        ActionKind::ReadClipboard { output_var } => {
            let result = exec.read_clipboard();
            if let Some(ref out) = result.output {
                ctx.set_var(output_var, out);
            }
            result
        }

        ActionKind::ActivateWindow { title, match_type } => {
            let t = ctx.interpolate(title);
            exec.activate_window(&t, match_type)
        }

        ActionKind::KeyPress { key, duration_ms } => {
            let k = ctx.interpolate(key);
            exec.key_press(&k, *duration_ms)
        }

        ActionKind::KeyCombo { keys } => exec.key_combo(keys),
        ActionKind::Hotkey { keys } => exec.key_combo(keys),

        ActionKind::TypeText { text, interval_ms } => {
            let t = ctx.interpolate(text);
            exec.type_text(&t, *interval_ms)
        }

        ActionKind::MouseClick { x, y, button, clicks } =>
            exec.mouse_click(*x, *y, *button, *clicks),

        ActionKind::MouseDoubleClick { x, y, button } =>
            exec.mouse_click(*x, *y, *button, 2),

        ActionKind::MouseRightClick { x, y } =>
            exec.mouse_click(*x, *y, MouseButton::Right, 1),

        ActionKind::MouseMove { x, y, duration_ms } =>
            exec.mouse_move(*x, *y, *duration_ms),

        ActionKind::MouseDrag { start_x, start_y, end_x, end_y, duration_ms, button } =>
            exec.mouse_drag(*start_x, *start_y, *end_x, *end_y, *duration_ms, *button),

        ActionKind::MouseScroll { x, y, clicks } =>
            exec.mouse_scroll(*x, *y, *clicks),

        ActionKind::CheckPixelColor { x, y, expected_color, tolerance, result_var } => {
            let result = exec.check_pixel_color(*x, *y, expected_color, *tolerance);
            if let Some(ref out) = result.output {
                ctx.set_var(result_var, out);
            }
            result
        }

        ActionKind::WaitForColor { x, y, expected_color, tolerance, timeout_ms } =>
            exec.wait_for_color(*x, *y, expected_color, *tolerance, *timeout_ms),

        ActionKind::WaitForImage { image_path, confidence, timeout_ms, region, grayscale } => {
            let path = ctx.interpolate(image_path);
            exec.wait_for_image(&path, *confidence, *timeout_ms, *region, *grayscale)
        }

        ActionKind::ClickOnImage { image_path, confidence, timeout_ms, button, region, offset_x, offset_y } => {
            let path = ctx.interpolate(image_path);
            exec.click_on_image(&path, *confidence, *timeout_ms, *button, *region, *offset_x, *offset_y)
        }

        ActionKind::ImageExists { image_path, confidence, result_var, region } => {
            let path = ctx.interpolate(image_path);
            let result = exec.image_exists(&path, *confidence, *region);
            if let Some(ref out) = result.output {
                ctx.set_var(result_var, out);
            }
            result
        }

        ActionKind::TakeScreenshot { file_path, region } => {
            let path = ctx.interpolate(file_path);
            exec.take_screenshot(&path, *region)
        }

        ActionKind::CaptureText { region, output_var, language } => {
            let result = exec.capture_text(*region, language);
            if let Some(ref out) = result.output {
                ctx.set_var(output_var, out);
            }
            result
        }

        ActionKind::SecureTypeText { encrypted_text, interval_ms } =>
            exec.secure_type_text(encrypted_text, *interval_ms),


        ActionKind::StealthClick { window_title, x, y, button } => {
            let win = ctx.interpolate(window_title);
            exec.stealth_click(&win, *x, *y, *button)
        }

        ActionKind::StealthType { window_title, text, interval_ms } => {
            let win = ctx.interpolate(window_title);
            let t = ctx.interpolate(text);
            exec.stealth_type(&win, &t, *interval_ms)
        }

        ActionKind::RunMacro { .. } => {
            unreachable!("RunMacro is intercepted and evaluated natively by MacroEngine.")
        }

        // Composite actions are NOT handled here — they're handled by the engine
        ActionKind::IfVariable { .. }
        | ActionKind::IfPixelColor { .. }
        | ActionKind::IfImageFound { .. }
        | ActionKind::LoopBlock { .. }
        | ActionKind::Group { .. } => {
            ActionResult::fail("composite actions must be handled by engine")
        }
    }
}
