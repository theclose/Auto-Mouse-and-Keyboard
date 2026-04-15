//! Stealth input via Win32 PostMessage — sends events to a window without focus.

use windows_sys::Win32::UI::WindowsAndMessaging::*;
use windows_sys::Win32::Foundation::*;

use amk_domain::action::MouseButton;
use crate::window;
use crate::sleeper::SmartSleeper;

/// Send a stealth mouse click to a window by title.
pub fn stealth_click(window_title: &str, x: i32, y: i32, button: MouseButton, sleeper: &SmartSleeper) -> Result<(), String> {
    let hwnd = match window::find_window_contains(window_title) {
        Some(h) => h,
        None => return Err(format!("stealth click: window not found: {window_title}")),
    };

    let lparam = make_lparam(x, y);
    let (down_msg, up_msg) = match button {
        MouseButton::Left => (WM_LBUTTONDOWN, WM_LBUTTONUP),
        MouseButton::Right => (WM_RBUTTONDOWN, WM_RBUTTONUP),
        MouseButton::Middle => (WM_MBUTTONDOWN, WM_MBUTTONUP),
    };

    unsafe {
        PostMessageW(hwnd, down_msg, 0, lparam);
    }
    
    if sleeper.sleep(20) {
        unsafe {
            PostMessageW(hwnd, up_msg, 0, lparam);
        }
    } else {
        // Cleanup if interrupted
        unsafe {
            PostMessageW(hwnd, up_msg, 0, lparam);
        }
    }
    Ok(())
}

/// Send stealth keystrokes to a window by title.
pub fn stealth_type(window_title: &str, text: &str, interval_ms: f64, sleeper: &SmartSleeper) -> Result<(), String> {
    let hwnd = match window::find_window_contains(window_title) {
        Some(h) => h,
        None => return Err(format!("stealth type: window not found: {window_title}")),
    };

    let delay_ms = interval_ms.max(1.0) as u32;

    for ch in text.chars() {
        let code = ch as u32;
        unsafe {
            PostMessageW(hwnd, WM_CHAR, code as WPARAM, 0);
        }
        if !sleeper.sleep(delay_ms) {
            break;
        }
    }
    Ok(())
}

/// Pack x, y into LPARAM for mouse messages.
fn make_lparam(x: i32, y: i32) -> LPARAM {
    ((y as u32 & 0xFFFF) << 16 | (x as u32 & 0xFFFF)) as LPARAM
}
