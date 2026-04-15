//! Mouse and keyboard input via Win32 SendInput.

use std::mem;

use windows_sys::Win32::UI::Input::KeyboardAndMouse::*;
use windows_sys::Win32::UI::WindowsAndMessaging::*;

use amk_domain::action::MouseButton;
use crate::sleeper::SmartSleeper;

// ── Virtual-key mapping ──────────────────────────────────────────────────

/// Convert a key name string to a Windows Virtual Key code.
#[must_use]
pub fn key_to_vk(key: &str) -> u16 {
    match key.to_lowercase().as_str() {
        // Letters
        "a" => 0x41, "b" => 0x42, "c" => 0x43, "d" => 0x44,
        "e" => 0x45, "f" => 0x46, "g" => 0x47, "h" => 0x48,
        "i" => 0x49, "j" => 0x4A, "k" => 0x4B, "l" => 0x4C,
        "m" => 0x4D, "n" => 0x4E, "o" => 0x4F, "p" => 0x50,
        "q" => 0x51, "r" => 0x52, "s" => 0x53, "t" => 0x54,
        "u" => 0x55, "v" => 0x56, "w" => 0x57, "x" => 0x58,
        "y" => 0x59, "z" => 0x5A,
        // Numbers
        "0" => 0x30, "1" => 0x31, "2" => 0x32, "3" => 0x33,
        "4" => 0x34, "5" => 0x35, "6" => 0x36, "7" => 0x37,
        "8" => 0x38, "9" => 0x39,
        // Function keys
        "f1" => VK_F1, "f2" => VK_F2, "f3" => VK_F3, "f4" => VK_F4,
        "f5" => VK_F5, "f6" => VK_F6, "f7" => VK_F7, "f8" => VK_F8,
        "f9" => VK_F9, "f10" => VK_F10, "f11" => VK_F11, "f12" => VK_F12,
        // Modifiers
        "shift" | "lshift" => VK_LSHIFT, "rshift" => VK_RSHIFT,
        "ctrl" | "control" | "lctrl" => VK_LCONTROL, "rctrl" => VK_RCONTROL,
        "alt" | "lalt" => VK_LMENU, "ralt" => VK_RMENU,
        "win" | "lwin" | "super" => VK_LWIN, "rwin" => VK_RWIN,
        // Navigation
        "enter" | "return" => VK_RETURN,
        "tab" => VK_TAB,
        "space" | " " => VK_SPACE,
        "backspace" | "back" => VK_BACK,
        "delete" | "del" => VK_DELETE,
        "insert" | "ins" => VK_INSERT,
        "escape" | "esc" => VK_ESCAPE,
        "home" => VK_HOME, "end" => VK_END,
        "pageup" | "pgup" => VK_PRIOR,
        "pagedown" | "pgdn" => VK_NEXT,
        // Arrow keys
        "up" => VK_UP, "down" => VK_DOWN,
        "left" => VK_LEFT, "right" => VK_RIGHT,
        // Misc
        "capslock" | "caps" => VK_CAPITAL,
        "numlock" => VK_NUMLOCK,
        "scrolllock" => VK_SCROLL,
        "printscreen" | "prtsc" => VK_SNAPSHOT,
        "pause" => VK_PAUSE,
        // Punctuation
        ";" | "semicolon" => VK_OEM_1,
        "=" | "equals" | "plus" => VK_OEM_PLUS,
        "," | "comma" => VK_OEM_COMMA,
        "-" | "minus" => VK_OEM_MINUS,
        "." | "period" => VK_OEM_PERIOD,
        "/" | "slash" => VK_OEM_2,
        "`" | "backtick" => VK_OEM_3,
        "[" => VK_OEM_4,
        "\\" | "backslash" => VK_OEM_5,
        "]" => VK_OEM_6,
        "'" | "quote" => VK_OEM_7,
        _ => 0,
    }
}

// ── Mouse ────────────────────────────────────────────────────────────────

/// Move mouse to absolute screen position using SendInput.
pub fn mouse_move_to(x: i32, y: i32) -> Result<(), String> {
    let (sx, sy) = screen_size();
    let abs_x = (x as f64 / sx as f64 * 65535.0) as i32;
    let abs_y = (y as f64 / sy as f64 * 65535.0) as i32;

    let mut input: INPUT = unsafe { mem::zeroed() };
    input.r#type = INPUT_MOUSE;
    input.Anonymous.mi.dx = abs_x;
    input.Anonymous.mi.dy = abs_y;
    input.Anonymous.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE;

    let sent = unsafe { SendInput(1, &input, mem::size_of::<INPUT>() as i32) };
    if sent == 0 {
        Err("SendInput blocked or failed".into())
    } else {
        Ok(())
    }
}

/// Smooth mouse move with duration.
pub fn mouse_move_smooth(x: i32, y: i32, duration_ms: u32, sleeper: &SmartSleeper) -> Result<(), String> {
    if duration_ms == 0 {
        return mouse_move_to(x, y);
    }

    let (cur_x, cur_y) = cursor_pos();
    let steps = (duration_ms / 10).max(1);
    let dx = (x - cur_x) as f64 / steps as f64;
    let dy = (y - cur_y) as f64 / steps as f64;
    let step_time = duration_ms / steps;

    for i in 1..=steps {
        let nx = cur_x + (dx * i as f64) as i32;
        let ny = cur_y + (dy * i as f64) as i32;
        mouse_move_to(nx, ny)?;
        if !sleeper.sleep(step_time) {
            break;
        }
    }
    Ok(())
}

/// Click mouse at position.
pub fn mouse_click_at(x: i32, y: i32, button: MouseButton, clicks: u32, sleeper: &SmartSleeper) -> Result<(), String> {
    mouse_move_to(x, y)?;
    if !sleeper.sleep(5) { return Ok(()); } // settle

    let (down_flag, up_flag) = match button {
        MouseButton::Left => (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
        MouseButton::Right => (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
        MouseButton::Middle => (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
    };

    for _ in 0..clicks.max(1) {
        send_mouse_event(down_flag, 0)?;
        if !sleeper.sleep(10) { break; }
        send_mouse_event(up_flag, 0)?;
        if !sleeper.sleep(30) { break; }
    }
    Ok(())
}

/// Drag mouse from start to end.
pub fn mouse_drag(sx: i32, sy: i32, ex: i32, ey: i32, dur_ms: u32, button: MouseButton, sleeper: &SmartSleeper) -> Result<(), String> {
    let down_flag = match button {
        MouseButton::Left => MOUSEEVENTF_LEFTDOWN,
        MouseButton::Right => MOUSEEVENTF_RIGHTDOWN,
        MouseButton::Middle => MOUSEEVENTF_MIDDLEDOWN,
    };
    let up_flag = match button {
        MouseButton::Left => MOUSEEVENTF_LEFTUP,
        MouseButton::Right => MOUSEEVENTF_RIGHTUP,
        MouseButton::Middle => MOUSEEVENTF_MIDDLEUP,
    };

    mouse_move_to(sx, sy)?;
    if !sleeper.sleep(30) { return Ok(()); }
    send_mouse_event(down_flag, 0)?;
    if !sleeper.sleep(30) {
        let _ = send_mouse_event(up_flag, 0); // Cleanup
        return Ok(());
    }
    mouse_move_smooth(ex, ey, dur_ms, sleeper)?;
    if sleeper.sleep(30) {
        send_mouse_event(up_flag, 0)?;
    } else {
        let _ = send_mouse_event(up_flag, 0);
    }
    Ok(())
}

/// Scroll mouse wheel.
pub fn mouse_scroll_at(x: i32, y: i32, clicks: i32, sleeper: &SmartSleeper) -> Result<(), String> {
    mouse_move_to(x, y)?;
    if sleeper.sleep(5) {
        send_mouse_event(MOUSEEVENTF_WHEEL, clicks * 120)?;
    }
    Ok(())
}

fn send_mouse_event(flags: MOUSE_EVENT_FLAGS, data: i32) -> Result<(), String> {
    let mut input: INPUT = unsafe { mem::zeroed() };
    input.r#type = INPUT_MOUSE;
    input.Anonymous.mi.dwFlags = flags;
    input.Anonymous.mi.mouseData = data as u32;
    let sent = unsafe { SendInput(1, &input, mem::size_of::<INPUT>() as i32) };
    if sent == 0 {
        Err("SendInput blocked or failed".into())
    } else {
        Ok(())
    }
}

// ── Keyboard ─────────────────────────────────────────────────────────────

/// Press and release a single key.
pub fn key_press(key: &str, hold_ms: u32, sleeper: &SmartSleeper) -> Result<(), String> {
    let vk = key_to_vk(key);
    if vk == 0 { return Ok(()); }
    
    send_key_event(vk, 0)?; // down
    
    let sleep_val = if hold_ms > 0 { hold_ms } else { 10 };
    if !sleeper.sleep(sleep_val) {
        let _ = send_key_event(vk, KEYEVENTF_KEYUP);
        return Ok(());
    }
    
    send_key_event(vk, KEYEVENTF_KEYUP) // up
}

/// Press a key combination (e.g. Ctrl+C).
pub fn key_combo(keys: &[String], sleeper: &SmartSleeper) -> Result<(), String> {
    // Press all keys down
    for key in keys {
        let vk = key_to_vk(key);
        if vk != 0 {
            send_key_event(vk, 0)?;
            if !sleeper.sleep(10) { break; }
        }
    }
    
    if sleeper.sleep(20) {
        // Release all keys in reverse
        for key in keys.iter().rev() {
            let vk = key_to_vk(key);
            if vk != 0 {
                let _ = send_key_event(vk, KEYEVENTF_KEYUP);
                if !sleeper.sleep(10) { break; }
            }
        }
    } else {
        // Interrupted, attempt cleanup
        for key in keys.iter().rev() {
            let vk = key_to_vk(key);
            if vk != 0 {
                let _ = send_key_event(vk, KEYEVENTF_KEYUP);
            }
        }
    }
    Ok(())
}

/// Type text character by character using Unicode SendInput.
pub fn type_text(text: &str, interval_ms: f64, sleeper: &SmartSleeper) -> Result<(), String> {
    let delay_ms = interval_ms.max(1.0) as u32;
    for ch in text.chars() {
        type_unicode_char(ch)?;
        if !sleeper.sleep(delay_ms) {
            break;
        }
    }
    Ok(())
}

fn type_unicode_char(ch: char) -> Result<(), String> {
    let code = ch as u16;
    let mut down: INPUT = unsafe { mem::zeroed() };
    down.r#type = INPUT_KEYBOARD;
    down.Anonymous.ki.wScan = code;
    down.Anonymous.ki.dwFlags = KEYEVENTF_UNICODE;

    let mut up: INPUT = unsafe { mem::zeroed() };
    up.r#type = INPUT_KEYBOARD;
    up.Anonymous.ki.wScan = code;
    up.Anonymous.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP;

    let inputs = [down, up];
    let sent = unsafe { SendInput(2, inputs.as_ptr(), mem::size_of::<INPUT>() as i32) };
    if sent < 2 {
        Err("SendInput blocked or failed".into())
    } else {
        Ok(())
    }
}

fn send_key_event(vk: u16, flags: KEYBD_EVENT_FLAGS) -> Result<(), String> {
    let mut input: INPUT = unsafe { mem::zeroed() };
    input.r#type = INPUT_KEYBOARD;
    input.Anonymous.ki.wVk = vk;
    input.Anonymous.ki.dwFlags = flags;
    let sent = unsafe { SendInput(1, &input, mem::size_of::<INPUT>() as i32) };
    if sent == 0 {
        Err("SendInput blocked or failed".into())
    } else {
        Ok(())
    }
}

// ── Helpers ──────────────────────────────────────────────────────────────

/// Get current cursor position.
#[must_use]
pub fn cursor_pos() -> (i32, i32) {
    let mut point = windows_sys::Win32::Foundation::POINT { x: 0, y: 0 };
    unsafe { GetCursorPos(&mut point); }
    (point.x, point.y)
}

/// Get the full virtual screen dimensions (spans all monitors).
#[must_use]
pub fn screen_size() -> (i32, i32) {
    unsafe {
        (
            GetSystemMetrics(SM_CXVIRTUALSCREEN),
            GetSystemMetrics(SM_CYVIRTUALSCREEN),
        )
    }
}

/// Check if a virtual key is currently pressed (async key state).
/// vk: Windows Virtual Key code (e.g. 0x01 = left mouse, 0x41 = 'A').
#[must_use]
pub fn is_key_pressed(vk: u16) -> bool {
    unsafe { GetAsyncKeyState(vk as i32) & (0x8000u16 as i16) != 0 }
}
