use std::fs;
use std::io::{BufRead, BufReader, Write};
use std::path::{Component, Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::Duration;

use amk_domain::action::{
    Action, ActionKind, CheckPixelColorAction, KeyChordAction, KeyPressAction, LogToFileAction,
    MouseClickAction, MouseDoubleClickAction, MouseDragAction, MouseMoveAction,
    MouseRightClickAction, MouseScrollAction, ReadClipboardAction, ReadFileLineAction,
    RunCommandAction, RunMacroAction, TypeTextAction, WaitForColorAction, WriteToFileAction,
};
use amk_domain::{ActionModelError, ExecutionContext, ExecutionSnapshot, PixelSample};
use amk_platform_win::{
    PlatformError, activate_window, check_pixel_color, drag_cursor, mouse_click,
    mouse_double_click, move_cursor, press_key, press_key_combo, read_clipboard_text, scroll_mouse,
    type_text, wait_for_pixel_color,
};
use amk_runtime::{
    ActionExecutor, PlaybackReport, RuntimeCheckpoint, RuntimeError, RuntimeOptions,
    run_actions_with_options,
};
use amk_schema::{MacroDocument, parse_macro_str};
use anyhow::{Context, Result, anyhow, bail};
use serde_json::{Value, json};
use time::OffsetDateTime;
use time::format_description::well_known::Rfc3339;
use wait_timeout::ChildExt;

const MAX_MACRO_DEPTH: i64 = 10;
#[derive(Debug, Clone)]
pub struct MacroRunResult {
    pub macro_name: String,
    pub report: PlaybackReport,
    pub snapshot: ExecutionSnapshot,
}

#[derive(Debug, Clone, Default)]
pub struct CliOptions {
    pub stop_on_error: bool,
}

#[derive(Debug, Default)]
pub struct HeadlessExecutor;

pub fn run_macro_path(path: impl AsRef<Path>, cli: &CliOptions) -> Result<MacroRunResult> {
    let path = fs::canonicalize(path.as_ref())
        .with_context(|| format!("cannot resolve macro path `{}`", path.as_ref().display()))?;
    let document = load_macro_document(&path)?;
    let actions = convert_actions(&document)?;

    let context = ExecutionContext::new();
    let mut executor = HeadlessExecutor;

    let mut snapshot = ExecutionSnapshot::default();
    snapshot.variables.insert(
        "__current_macro_file__".to_string(),
        json!(path.display().to_string()),
    );
    snapshot.variables.insert(
        "__current_macro_dir__".to_string(),
        json!(
            path.parent()
                .unwrap_or_else(|| Path::new("."))
                .display()
                .to_string()
        ),
    );
    snapshot
        .variables
        .insert("__macro_depth__".to_string(), json!(0));

    let options = RuntimeOptions {
        loop_count: document.settings.loop_count,
        loop_delay_ms: document.settings.delay_between_loops,
        stop_on_error: cli.stop_on_error,
        resume_from: Some(RuntimeCheckpoint {
            action_index: 0,
            context: snapshot,
        }),
        ..RuntimeOptions::default()
    };

    let report = run_actions_with_options(&actions, &context, &mut executor, &options, None, None)
        .map_err(anyhow_from_runtime)?;

    Ok(MacroRunResult {
        macro_name: document.name,
        report,
        snapshot: context.snapshot(),
    })
}

fn load_macro_document(path: &Path) -> Result<MacroDocument> {
    let raw = fs::read_to_string(path)
        .with_context(|| format!("cannot read macro `{}`", path.display()))?;
    parse_macro_str(&raw).map_err(|error| anyhow!("invalid macro JSON: {error}"))
}

fn convert_actions(document: &MacroDocument) -> Result<Vec<Action>> {
    document
        .actions
        .clone()
        .into_iter()
        .map(Action::from_raw)
        .collect::<std::result::Result<Vec<_>, ActionModelError>>()
        .map_err(|error| anyhow!("cannot convert action model: {error}"))
}

impl ActionExecutor for HeadlessExecutor {
    fn execute_atomic(
        &mut self,
        action: &Action,
        context: &ExecutionContext,
    ) -> std::result::Result<bool, RuntimeError> {
        match &action.kind {
            ActionKind::MouseClick(value) => execute_mouse_click(value, context),
            ActionKind::MouseDoubleClick(value) => execute_mouse_double_click(value, context),
            ActionKind::MouseRightClick(value) => execute_mouse_right_click(value, context),
            ActionKind::MouseMove(value) => execute_mouse_move(value, context),
            ActionKind::MouseDrag(value) => execute_mouse_drag(value, context),
            ActionKind::MouseScroll(value) => execute_mouse_scroll(value),
            ActionKind::KeyPress(value) => execute_key_press(value, context),
            ActionKind::KeyCombo(value) | ActionKind::Hotkey(value) => {
                execute_key_combo(value, context)
            }
            ActionKind::TypeText(value) => execute_type_text(value, context),
            ActionKind::CheckPixelColor(value) => execute_check_pixel(value, context),
            ActionKind::WaitForColor(value) => execute_wait_for_color(value, context),
            ActionKind::ActivateWindow(value) => {
                let title = interpolate(context, &value.window_title);
                activate_window(&title, value.exact_match).map_err(runtime_from_platform)?;
                Ok(true)
            }
            ActionKind::LogToFile(value) => execute_log_to_file(value, context),
            ActionKind::ReadClipboard(value) => execute_read_clipboard(value, context),
            ActionKind::ReadFileLine(value) => execute_read_file_line(value, context),
            ActionKind::WriteToFile(value) => execute_write_to_file(value, context),
            ActionKind::RunMacro(value) => self.execute_run_macro(value, context),
            ActionKind::RunCommand(value) => execute_run_command(value, context),
            unsupported => Err(RuntimeError::Message(format!(
                "unsupported atomic action in headless Rust runner: {:?}",
                unsupported
            ))),
        }
    }
}

impl HeadlessExecutor {
    fn execute_run_macro(
        &mut self,
        action: &RunMacroAction,
        context: &ExecutionContext,
    ) -> std::result::Result<bool, RuntimeError> {
        let depth = value_as_i64(context.get_var("__macro_depth__").as_ref()).unwrap_or(0);
        if depth >= MAX_MACRO_DEPTH {
            return Ok(false);
        }

        let macro_path = resolve_runtime_path(context, &action.macro_path)
            .map_err(|error| RuntimeError::Message(error.to_string()))?;
        if macro_path.extension().and_then(|ext| ext.to_str()) != Some("json") {
            return Ok(false);
        }

        let document = load_macro_document(&macro_path)
            .map_err(|error| RuntimeError::Message(error.to_string()))?;
        let actions =
            convert_actions(&document).map_err(|error| RuntimeError::Message(error.to_string()))?;

        let previous_file = context.get_var("__current_macro_file__");
        let previous_dir = context.get_var("__current_macro_dir__");
        let mut snapshot = context.snapshot();
        snapshot.variables.insert(
            "__macro_depth__".to_string(),
            json!(depth.saturating_add(1)),
        );
        snapshot.variables.insert(
            "__current_macro_file__".to_string(),
            json!(macro_path.display().to_string()),
        );
        snapshot.variables.insert(
            "__current_macro_dir__".to_string(),
            json!(
                macro_path
                    .parent()
                    .unwrap_or_else(|| Path::new("."))
                    .display()
                    .to_string()
            ),
        );

        let options = RuntimeOptions {
            loop_count: document.settings.loop_count,
            loop_delay_ms: document.settings.delay_between_loops,
            resume_from: Some(RuntimeCheckpoint {
                action_index: 0,
                context: snapshot,
            }),
            ..RuntimeOptions::default()
        };

        let result = run_actions_with_options(&actions, context, self, &options, None, None)
            .map_err(anyhow_from_runtime)
            .map(|report| report.failed == 0);

        restore_var(context, "__current_macro_file__", previous_file);
        restore_var(context, "__current_macro_dir__", previous_dir);
        context.set_var("__macro_depth__", depth);

        result.map_err(|error| RuntimeError::Message(error.to_string()))
    }
}

fn execute_mouse_click(
    action: &MouseClickAction,
    context: &ExecutionContext,
) -> std::result::Result<bool, RuntimeError> {
    let (x, y) = resolve_click_coords(
        context,
        action.x,
        action.y,
        action.dynamic_x.as_deref(),
        action.dynamic_y.as_deref(),
        action.context_image.as_deref(),
    );
    mouse_click(x, y, "left").map_err(runtime_from_platform)?;
    Ok(true)
}

fn execute_mouse_double_click(
    action: &MouseDoubleClickAction,
    context: &ExecutionContext,
) -> std::result::Result<bool, RuntimeError> {
    let (x, y) = resolve_click_coords(
        context,
        action.x,
        action.y,
        action.dynamic_x.as_deref(),
        action.dynamic_y.as_deref(),
        action.context_image.as_deref(),
    );
    mouse_double_click(x, y).map_err(runtime_from_platform)?;
    Ok(true)
}

fn execute_mouse_right_click(
    action: &MouseRightClickAction,
    context: &ExecutionContext,
) -> std::result::Result<bool, RuntimeError> {
    let (x, y) = resolve_click_coords(
        context,
        action.x,
        action.y,
        action.dynamic_x.as_deref(),
        action.dynamic_y.as_deref(),
        action.context_image.as_deref(),
    );
    mouse_click(x, y, "right").map_err(runtime_from_platform)?;
    Ok(true)
}

fn execute_mouse_move(
    action: &MouseMoveAction,
    context: &ExecutionContext,
) -> std::result::Result<bool, RuntimeError> {
    let x = resolve_dynamic_i32(context, action.dynamic_x.as_deref(), action.x);
    let y = resolve_dynamic_i32(context, action.dynamic_y.as_deref(), action.y);
    move_cursor(x, y).map_err(runtime_from_platform)?;
    Ok(true)
}

fn execute_mouse_drag(
    action: &MouseDragAction,
    context: &ExecutionContext,
) -> std::result::Result<bool, RuntimeError> {
    let x = resolve_dynamic_i32(context, action.dynamic_x.as_deref(), action.x);
    let y = resolve_dynamic_i32(context, action.dynamic_y.as_deref(), action.y);
    drag_cursor(
        action.start_x,
        action.start_y,
        x,
        y,
        duration_from_secs(action.duration),
        &action.button,
    )
    .map_err(runtime_from_platform)?;
    Ok(true)
}

fn execute_mouse_scroll(action: &MouseScrollAction) -> std::result::Result<bool, RuntimeError> {
    if action.clicks == 0 {
        return Ok(true);
    }
    scroll_mouse(action.x, action.y, action.clicks).map_err(runtime_from_platform)?;
    Ok(true)
}

fn execute_key_press(
    action: &KeyPressAction,
    context: &ExecutionContext,
) -> std::result::Result<bool, RuntimeError> {
    let key = interpolate(context, &action.key);
    press_key(&key).map_err(runtime_from_platform)?;
    Ok(true)
}

fn execute_key_combo(
    action: &KeyChordAction,
    context: &ExecutionContext,
) -> std::result::Result<bool, RuntimeError> {
    let keys = action
        .keys
        .iter()
        .map(|key| interpolate(context, key))
        .collect::<Vec<_>>();
    press_key_combo(&keys).map_err(runtime_from_platform)?;
    Ok(true)
}

fn execute_type_text(
    action: &TypeTextAction,
    context: &ExecutionContext,
) -> std::result::Result<bool, RuntimeError> {
    let text = interpolate(context, &action.text);
    type_text(&text, duration_from_secs(action.interval)).map_err(runtime_from_platform)?;
    Ok(true)
}

fn execute_check_pixel(
    action: &CheckPixelColorAction,
    context: &ExecutionContext,
) -> std::result::Result<bool, RuntimeError> {
    let matched = check_pixel_color(
        action.x,
        action.y,
        action.r as u8,
        action.g as u8,
        action.b as u8,
        action.tolerance as u8,
    )
    .map_err(runtime_from_platform)?;
    let (r, g, b) =
        amk_platform_win::get_pixel_color(action.x, action.y).map_err(runtime_from_platform)?;
    context.set_pixel_color(PixelSample {
        x: action.x,
        y: action.y,
        r: r as i32,
        g: g as i32,
        b: b as i32,
    });
    context.set_var("pixel_matched", matched);
    Ok(true)
}

fn execute_wait_for_color(
    action: &WaitForColorAction,
    _context: &ExecutionContext,
) -> std::result::Result<bool, RuntimeError> {
    wait_for_pixel_color(
        action.x,
        action.y,
        action.r as u8,
        action.g as u8,
        action.b as u8,
        action.tolerance as u8,
        Duration::from_millis(action.timeout_ms as u64),
        Duration::from_millis(100),
    )
    .map_err(runtime_from_platform)
}

fn execute_log_to_file(
    action: &LogToFileAction,
    context: &ExecutionContext,
) -> std::result::Result<bool, RuntimeError> {
    let message = interpolate(context, &action.message);
    let path = resolve_runtime_path(context, &action.file_path)
        .map_err(|error| RuntimeError::Message(error.to_string()))?;
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(runtime_from_io)?;
    }
    rotate_if_needed(&path, 5 * 1024 * 1024).map_err(runtime_from_io)?;
    let timestamp = OffsetDateTime::now_local()
        .unwrap_or_else(|_| OffsetDateTime::now_utc())
        .format(&Rfc3339)
        .unwrap_or_else(|_| "1970-01-01T00:00:00Z".to_string());
    let mut file = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&path)
        .map_err(runtime_from_io)?;
    writeln!(file, "[{timestamp}] {message}").map_err(runtime_from_io)?;
    Ok(true)
}

fn execute_read_clipboard(
    action: &ReadClipboardAction,
    context: &ExecutionContext,
) -> std::result::Result<bool, RuntimeError> {
    let text = read_clipboard_text().map_err(runtime_from_platform)?;
    context.set_var(&action.var_name, text);
    Ok(true)
}

fn execute_read_file_line(
    action: &ReadFileLineAction,
    context: &ExecutionContext,
) -> std::result::Result<bool, RuntimeError> {
    let path = resolve_runtime_path(context, &action.file_path)
        .map_err(|error| RuntimeError::Message(error.to_string()))?;
    let line_expr = interpolate(context, &action.line_number);
    let line_number = line_expr.trim().parse::<usize>().unwrap_or(0);
    if line_number == 0 {
        return Ok(false);
    }
    let file = fs::File::open(&path).map_err(runtime_from_io)?;
    let reader = BufReader::new(file);
    let value = reader
        .lines()
        .nth(line_number - 1)
        .transpose()
        .map_err(runtime_from_io)?
        .unwrap_or_default();
    context.set_var(&action.var_name, value);
    Ok(true)
}

fn execute_write_to_file(
    action: &WriteToFileAction,
    context: &ExecutionContext,
) -> std::result::Result<bool, RuntimeError> {
    let path = resolve_runtime_path(context, &action.file_path)
        .map_err(|error| RuntimeError::Message(error.to_string()))?;
    let text = interpolate(context, &action.text);
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(runtime_from_io)?;
    }
    if action.mode.eq_ignore_ascii_case("append") {
        rotate_if_needed(&path, 10 * 1024 * 1024).map_err(runtime_from_io)?;
    }
    let mut file = fs::OpenOptions::new()
        .create(true)
        .write(true)
        .append(action.mode.eq_ignore_ascii_case("append"))
        .truncate(!action.mode.eq_ignore_ascii_case("append"))
        .open(&path)
        .map_err(runtime_from_io)?;
    writeln!(file, "{text}").map_err(runtime_from_io)?;
    Ok(true)
}

fn execute_run_command(
    action: &RunCommandAction,
    context: &ExecutionContext,
) -> std::result::Result<bool, RuntimeError> {
    let command = interpolate(context, &action.command);
    if command.trim().is_empty() {
        return Ok(true);
    }

    let timeout = Duration::from_secs(action.timeout.max(1) as u64);
    let working_dir = match action.working_dir.as_deref() {
        Some(path) if !path.trim().is_empty() => Some(
            resolve_runtime_path(context, path)
                .map_err(|error| RuntimeError::Message(error.to_string()))?,
        ),
        _ => None,
    };

    let mut child = Command::new("cmd")
        .args(["/C", &command])
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .current_dir(
            working_dir
                .clone()
                .unwrap_or_else(|| current_macro_dir(context)),
        )
        .spawn()
        .map_err(runtime_from_io)?;

    let status = child.wait_timeout(timeout).map_err(runtime_from_io)?;
    let output = if let Some(status) = status {
        let output = child.wait_with_output().map_err(runtime_from_io)?;
        (status.code().unwrap_or(-1), output.stdout, output.stderr)
    } else {
        child.kill().map_err(runtime_from_io)?;
        let output = child.wait_with_output().map_err(runtime_from_io)?;
        if let Some(var_name) = &action.var_name {
            context.set_var(var_name, "__TIMEOUT__");
        }
        context.set_var("__exit_code__", -1);
        if !output.stderr.is_empty() {
            context.set_var(
                "__stderr__",
                String::from_utf8_lossy(&output.stderr).to_string(),
            );
        }
        return Ok(false);
    };

    let stdout = String::from_utf8_lossy(&output.1).trim().to_string();
    let stderr = String::from_utf8_lossy(&output.2).trim().to_string();
    if let Some(var_name) = &action.var_name {
        context.set_var(var_name, stdout.clone());
    }
    context.set_var("__exit_code__", output.0);
    if !stderr.is_empty() {
        context.set_var("__stderr__", stderr.clone());
    }

    if output.0 != 0 && !action.ignore_exit_code {
        return Ok(false);
    }
    Ok(true)
}

fn resolve_click_coords(
    context: &ExecutionContext,
    fallback_x: i32,
    fallback_y: i32,
    dynamic_x: Option<&str>,
    dynamic_y: Option<&str>,
    context_image: Option<&str>,
) -> (i32, i32) {
    let x = resolve_dynamic_i32(context, dynamic_x, fallback_x);
    let y = resolve_dynamic_i32(context, dynamic_y, fallback_y);
    match context_image.and_then(|path| context.get_image_center(Some(path))) {
        Some(coords) => coords,
        None => (x, y),
    }
}

fn resolve_dynamic_i32(context: &ExecutionContext, dynamic: Option<&str>, fallback: i32) -> i32 {
    dynamic
        .map(|value| interpolate(context, value))
        .and_then(|value| value.trim().parse::<f64>().ok())
        .map(|value| value.round() as i32)
        .unwrap_or(fallback)
}

fn interpolate(context: &ExecutionContext, value: &str) -> String {
    if value.contains("${") {
        context.interpolate(value)
    } else {
        value.to_string()
    }
}

fn resolve_runtime_path(context: &ExecutionContext, raw: &str) -> Result<PathBuf> {
    let rendered = interpolate(context, raw);
    if rendered.trim().is_empty() {
        bail!("empty runtime path");
    }

    let candidate = PathBuf::from(rendered);
    if candidate
        .components()
        .any(|component| matches!(component, Component::ParentDir))
    {
        bail!("parent path traversal is not allowed");
    }

    let resolved = if candidate.is_absolute() {
        candidate
    } else {
        current_macro_dir(context).join(candidate)
    };
    Ok(resolved)
}

fn current_macro_dir(context: &ExecutionContext) -> PathBuf {
    context
        .get_var("__current_macro_dir__")
        .and_then(|value| value.as_str().map(PathBuf::from))
        .unwrap_or_else(|| std::env::current_dir().unwrap_or_else(|_| PathBuf::from(".")))
}

fn rotate_if_needed(path: &Path, max_bytes: u64) -> std::io::Result<()> {
    if !path.exists() {
        return Ok(());
    }
    let metadata = fs::metadata(path)?;
    if metadata.len() <= max_bytes {
        return Ok(());
    }
    let rotated = path.with_extension(format!(
        "{}.1",
        path.extension()
            .and_then(|ext| ext.to_str())
            .unwrap_or("log")
    ));
    if rotated.exists() {
        fs::remove_file(&rotated)?;
    }
    fs::rename(path, rotated)?;
    Ok(())
}

fn restore_var(context: &ExecutionContext, name: &str, previous: Option<Value>) {
    match previous {
        Some(value) => context.set_var(name, value),
        None => context.set_var(name, ""),
    }
}

fn value_as_i64(value: Option<&Value>) -> Option<i64> {
    match value {
        Some(Value::Number(number)) => number.as_i64(),
        Some(Value::String(value)) => value.trim().parse::<i64>().ok(),
        Some(Value::Bool(value)) => Some(i64::from(*value)),
        _ => None,
    }
}

fn duration_from_secs(value: f64) -> Duration {
    if value <= 0.0 {
        Duration::ZERO
    } else {
        Duration::from_secs_f64(value)
    }
}

fn runtime_from_platform(error: PlatformError) -> RuntimeError {
    RuntimeError::Message(error.to_string())
}

fn runtime_from_io(error: std::io::Error) -> RuntimeError {
    RuntimeError::Message(error.to_string())
}

fn anyhow_from_runtime(error: RuntimeError) -> anyhow::Error {
    anyhow!(error.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    fn write_macro(path: &Path, body: &str) {
        fs::write(path, body).expect("macro write should succeed");
    }

    #[test]
    fn runs_system_actions_and_captures_command_output() {
        let temp = tempdir().expect("temp dir");
        let macro_path = temp.path().join("macro.json");
        write_macro(
            &macro_path,
            r#"{
  "name": "System Test",
  "settings": { "loop_count": 1, "delay_between_loops": 0 },
  "actions": [
    { "type": "write_to_file", "params": { "file_path": "data.txt", "text": "alpha,beta,gamma", "mode": "overwrite" } },
    { "type": "read_file_line", "params": { "file_path": "data.txt", "line_number": "1", "var_name": "line" } },
    { "type": "split_string", "params": { "source_var": "line", "delimiter": ",", "field_index": 1, "target_var": "middle" } },
    { "type": "run_command", "params": { "command": "echo ${middle}", "var_name": "cmd", "timeout": 5 } },
    { "type": "log_to_file", "params": { "file_path": "macro.log", "message": "middle=${middle}" } }
  ]
}"#,
        );

        let result = run_macro_path(&macro_path, &CliOptions::default()).expect("macro run");
        assert_eq!(result.report.failed, 0);
        assert_eq!(
            result.snapshot.variables.get("middle"),
            Some(&json!("beta"))
        );
        assert_eq!(result.snapshot.variables.get("cmd"), Some(&json!("beta")));
        assert!(temp.path().join("macro.log").exists());
    }

    #[test]
    fn resolves_nested_macros_relative_to_current_macro_dir() {
        let temp = tempdir().expect("temp dir");
        let child_dir = temp.path().join("nested");
        fs::create_dir_all(&child_dir).expect("child dir");

        let child_macro = child_dir.join("child.json");
        write_macro(
            &child_macro,
            r#"{
  "name": "Child",
  "actions": [
    { "type": "set_variable", "params": { "var_name": "child_value", "value": "done", "operation": "set" } },
    { "type": "write_to_file", "params": { "file_path": "child.txt", "text": "${child_value}", "mode": "overwrite" } }
  ]
}"#,
        );

        let parent_macro = temp.path().join("parent.json");
        write_macro(
            &parent_macro,
            r#"{
  "name": "Parent",
  "actions": [
    { "type": "run_macro", "params": { "macro_path": "nested/child.json" } },
    { "type": "write_to_file", "params": { "file_path": "parent.txt", "text": "${child_value}", "mode": "overwrite" } }
  ]
}"#,
        );

        let result = run_macro_path(&parent_macro, &CliOptions::default()).expect("macro run");
        assert_eq!(result.report.failed, 0);
        assert_eq!(
            fs::read_to_string(child_dir.join("child.txt")).expect("child file"),
            "done\n"
        );
        assert_eq!(
            fs::read_to_string(temp.path().join("parent.txt")).expect("parent file"),
            "done\n"
        );
    }

    #[test]
    fn blocks_parent_path_traversal() {
        let context = ExecutionContext::new();
        context.reset();
        context.set_var("__current_macro_dir__", "C:\\AMK");
        let error = resolve_runtime_path(&context, "..\\evil.txt").expect_err("must fail");
        assert!(error.to_string().contains("traversal"));
    }
}
