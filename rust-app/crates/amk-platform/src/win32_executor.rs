//! Full Win32 implementation of the `Executor` trait.
//!
//! This connects the engine to real Windows API calls.

use std::io::{BufRead, Write};
use std::process::Command;
use std::sync::atomic::AtomicBool;
use std::sync::Arc;

use amk_domain::action::MouseButton;
use amk_runtime::executor::{ActionResult, Executor};

use crate::{capture, clipboard, input, sleeper::SmartSleeper, stealth, window};

/// Win32-based executor for AutoMacro.
pub struct Win32Executor {
    /// External stop signal (shared with engine).
    stop_flag: Arc<AtomicBool>,
    /// Utility for interruptible sleeps.
    sleeper: SmartSleeper,
}

impl Win32Executor {
    /// Create a new executor using the provided stop_flag.
    /// If none provided, creates an autonomous one.
    #[must_use]
    pub fn new() -> Self {
        let flag = Arc::new(AtomicBool::new(false));
        Self::with_flag(flag)
    }

    /// Create with an existing shared flag.
    pub fn with_flag(stop_flag: Arc<AtomicBool>) -> Self {
        Self {
            sleeper: SmartSleeper::new(Arc::clone(&stop_flag)),
            stop_flag,
        }
    }

    /// Get a handle to the stop flag for external control.
    #[must_use]
    pub fn stop_handle(&self) -> Arc<AtomicBool> {
        Arc::clone(&self.stop_flag)
    }
}

impl Default for Win32Executor {
    fn default() -> Self {
        Self::new()
    }
}

impl Executor for Win32Executor {
    fn delay(&mut self, ms: u32) -> ActionResult {
        if self.sleeper.sleep(ms) {
            ActionResult::ok()
        } else {
            ActionResult::fail("delay interrupted")
        }
    }

    fn mouse_click(&mut self, x: i32, y: i32, button: MouseButton, clicks: u32) -> ActionResult {
        match input::mouse_click_at(x, y, button, clicks, &self.sleeper) {
            Ok(()) => ActionResult::ok(),
            Err(e) => ActionResult::fail(e),
        }
    }

    fn mouse_move(&mut self, x: i32, y: i32, duration_ms: u32) -> ActionResult {
        match input::mouse_move_smooth(x, y, duration_ms, &self.sleeper) {
            Ok(()) => ActionResult::ok(),
            Err(e) => ActionResult::fail(e),
        }
    }

    fn mouse_drag(&mut self, sx: i32, sy: i32, ex: i32, ey: i32, dur: u32, btn: MouseButton) -> ActionResult {
        match input::mouse_drag(sx, sy, ex, ey, dur, btn, &self.sleeper) {
            Ok(()) => ActionResult::ok(),
            Err(e) => ActionResult::fail(e),
        }
    }

    fn mouse_scroll(&mut self, x: i32, y: i32, clicks: i32) -> ActionResult {
        match input::mouse_scroll_at(x, y, clicks, &self.sleeper) {
            Ok(()) => ActionResult::ok(),
            Err(e) => ActionResult::fail(e),
        }
    }

    fn key_press(&mut self, key: &str, duration_ms: u32) -> ActionResult {
        match input::key_press(key, duration_ms, &self.sleeper) {
            Ok(()) => ActionResult::ok(),
            Err(e) => ActionResult::fail(e),
        }
    }

    fn key_combo(&mut self, keys: &[String]) -> ActionResult {
        match input::key_combo(keys, &self.sleeper) {
            Ok(()) => ActionResult::ok(),
            Err(e) => ActionResult::fail(e),
        }
    }

    fn type_text(&mut self, text: &str, interval_ms: f64) -> ActionResult {
        match input::type_text(text, interval_ms, &self.sleeper) {
            Ok(()) => ActionResult::ok(),
            Err(e) => ActionResult::fail(e),
        }
    }

    fn run_command(&mut self, command: &str, wait: bool) -> ActionResult {
        if wait {
            match Command::new("cmd").args(["/C", command]).output() {
                Ok(out) => {
                    let stdout = String::from_utf8_lossy(&out.stdout).into_owned();
                    if out.status.success() {
                        ActionResult::ok_with(stdout.trim())
                    } else {
                        let stderr = String::from_utf8_lossy(&out.stderr);
                        ActionResult::fail(format!("exit {}: {}", out.status, stderr.trim()))
                    }
                }
                Err(e) => ActionResult::fail(format!("spawn error: {e}")),
            }
        } else {
            match Command::new("cmd").args(["/C", command]).spawn() {
                Ok(_) => ActionResult::ok(),
                Err(e) => ActionResult::fail(format!("spawn error: {e}")),
            }
        }
    }

    fn read_clipboard(&mut self) -> ActionResult {
        let text = clipboard::read_clipboard();
        ActionResult::ok_with(text)
    }

    fn activate_window(&mut self, title: &str, match_type: &str) -> ActionResult {
        if window::find_and_activate(title, match_type) {
            ActionResult::ok()
        } else {
            ActionResult::fail(format!("window not found: {title}"))
        }
    }

    fn log_to_file(&mut self, path: &str, message: &str, append: bool) -> ActionResult {
        let result = if append {
            std::fs::OpenOptions::new().create(true).append(true).open(path)
                .and_then(|mut f| writeln!(f, "{message}"))
        } else {
            std::fs::write(path, message).map(|_| ())
        };
        match result {
            Ok(()) => ActionResult::ok(),
            Err(e) => ActionResult::fail(format!("file error: {e}")),
        }
    }

    fn read_file_line(&mut self, path: &str, line: i32) -> ActionResult {
        match std::fs::File::open(path) {
            Ok(file) => {
                let reader = std::io::BufReader::new(file);
                let lines: Vec<String> = reader.lines().map_while(Result::ok).collect();

                if lines.is_empty() {
                    return ActionResult::ok_with("");
                }

                let idx = if line < 0 {
                    // Random line
                    use std::time::SystemTime;
                    let seed = SystemTime::now()
                        .duration_since(SystemTime::UNIX_EPOCH)
                        .unwrap_or_default()
                        .subsec_nanos() as usize;
                    seed % lines.len()
                } else {
                    (line as usize).saturating_sub(1).min(lines.len() - 1)
                };

                ActionResult::ok_with(&lines[idx])
            }
            Err(e) => ActionResult::fail(format!("read error: {e}")),
        }
    }

    fn write_to_file(&mut self, path: &str, content: &str, append: bool) -> ActionResult {
        let result = if append {
            std::fs::OpenOptions::new().create(true).append(true).open(path)
                .and_then(|mut f| f.write_all(content.as_bytes()))
        } else {
            std::fs::write(path, content)
        };
        match result {
            Ok(()) => ActionResult::ok(),
            Err(e) => ActionResult::fail(format!("write error: {e}")),
        }
    }

    fn check_pixel_color(&mut self, x: i32, y: i32, color: &str, tolerance: u32) -> ActionResult {
        match capture::check_pixel_match(x, y, color, tolerance) {
            Ok(matched) => ActionResult::ok_with(if matched { "true" } else { "false" }),
            Err(e) => ActionResult::fail(e),
        }
    }

    fn wait_for_color(&mut self, x: i32, y: i32, color: &str, tolerance: u32, timeout: u32) -> ActionResult {
        let matched = self.sleeper.wait_until(timeout, || {
            capture::check_pixel_match(x, y, color, tolerance).unwrap_or(false)
        });
        if matched {
            ActionResult::ok_with("true")
        } else {
            ActionResult::fail("timeout or interrupted waiting for color")
        }
    }

    fn wait_for_image(&mut self, path: &str, confidence: f64, timeout: u32, region: Option<[i32; 4]>, _grayscale: bool) -> ActionResult {
        let matched = self.sleeper.wait_until(timeout, || {
            match crate::vision::find_image(path, region) {
                Ok(res) => res.confidence >= confidence,
                Err(_) => false,
            }
        });
        if matched {
            ActionResult::ok_with("true")
        } else {
            ActionResult::fail("timeout waiting for image")
        }
    }

    fn click_on_image(&mut self, path: &str, confidence: f64, timeout: u32, btn: MouseButton, region: Option<[i32; 4]>, ox: i32, oy: i32) -> ActionResult {
        let mut target_x = 0;
        let mut target_y = 0;
        let found = self.sleeper.wait_until(timeout, || {
            match crate::vision::find_image(path, region) {
                Ok(res) if res.confidence >= confidence => {
                    target_x = res.x + (res.width / 2) + ox;
                    target_y = res.y + (res.height / 2) + oy;
                    true
                }
                _ => false,
            }
        });

        if !found {
            return ActionResult::fail("image not found for clicking");
        }
        
        match input::mouse_click_at(target_x, target_y, btn, 1, &self.sleeper) {
            Ok(()) => ActionResult::ok(),
            Err(e) => ActionResult::fail(e),
        }
    }

    fn image_exists(&mut self, path: &str, confidence: f64, region: Option<[i32; 4]>) -> ActionResult {
        match crate::vision::find_image(path, region) {
            Ok(res) => {
                let exists = res.confidence >= confidence;
                ActionResult::ok_with(if exists { "true" } else { "false" })
            }
            Err(e) => ActionResult::fail(format!("image error: {e}")),
        }
    }

    fn take_screenshot(&mut self, path: &str, region: Option<[i32; 4]>) -> ActionResult {
        let (x, y, w, h) = match region {
            Some([rx, ry, rw, rh]) => (rx, ry, rw, rh),
            None => {
                let (sw, sh) = input::screen_size();
                (0, 0, sw, sh)
            }
        };

        match capture::capture_region(x, y, w, h) {
            Ok((data, width, height)) => {
                match capture::save_bmp(path, &data, width, height) {
                    Ok(()) => ActionResult::ok(),
                    Err(e) => ActionResult::fail(format!("save error: {e}")),
                }
            }
            Err(e) => ActionResult::fail(format!("capture failed: {e}")),
        }
    }

    fn capture_text(&mut self, _region: [i32; 4], _language: &str) -> ActionResult {
        ActionResult::fail("OCR is unsupported in the standalone fast-build version.")
    }

    fn secure_type_text(&mut self, encrypted: &str, interval_ms: f64) -> ActionResult {
        match crate::crypto::decrypt_string(encrypted) {
            Ok(cleartext) => {
                match input::type_text(&cleartext, interval_ms, &self.sleeper) {
                    Ok(()) => ActionResult::ok(),
                    Err(e) => ActionResult::fail(e),
                }
            }
            Err(e) => ActionResult::fail(format!("decryption error: {e}")),
        }
    }

    fn run_macro(&mut self, _path: &str) -> ActionResult {
        ActionResult::fail("Nested macros are natively evaluated by Engine; you should not see this.")
    }

    fn stealth_click(&mut self, win_title: &str, x: i32, y: i32, btn: MouseButton) -> ActionResult {
        match stealth::stealth_click(win_title, x, y, btn, &self.sleeper) {
            Ok(()) => ActionResult::ok(),
            Err(e) => ActionResult::fail(e),
        }
    }

    fn stealth_type(&mut self, win_title: &str, text: &str, interval_ms: f64) -> ActionResult {
        match stealth::stealth_type(win_title, text, interval_ms, &self.sleeper) {
            Ok(()) => ActionResult::ok(),
            Err(e) => ActionResult::fail(e),
        }
    }

    fn should_stop(&self) -> bool {
        self.stop_flag.load(std::sync::atomic::Ordering::Relaxed)
    }
}
