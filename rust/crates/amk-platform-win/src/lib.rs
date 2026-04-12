use std::mem::size_of;
use std::ptr::{null, null_mut};
use std::thread;
use std::time::{Duration, Instant};

use thiserror::Error;
use windows_sys::Win32::Foundation::{BOOL, HWND, LPARAM};
use windows_sys::Win32::Graphics::Gdi::{GetDC, GetPixel, ReleaseDC};
use windows_sys::Win32::System::DataExchange::{CloseClipboard, GetClipboardData, OpenClipboard};
use windows_sys::Win32::System::Memory::{GlobalLock, GlobalUnlock};
use windows_sys::Win32::System::Ole::CF_UNICODETEXT;
use windows_sys::Win32::System::Threading::{AttachThreadInput, GetCurrentThreadId};
use windows_sys::Win32::UI::Input::KeyboardAndMouse::{
    INPUT, INPUT_0, INPUT_KEYBOARD, KEYBDINPUT, KEYEVENTF_KEYUP, KEYEVENTF_UNICODE,
    MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP, MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP,
    MOUSEEVENTF_WHEEL, SendInput, mouse_event,
};
use windows_sys::Win32::UI::WindowsAndMessaging::{
    BringWindowToTop, EnumWindows, FindWindowW, GetForegroundWindow, GetWindowTextW,
    GetWindowThreadProcessId, IsIconic, IsWindowVisible, SW_RESTORE, SW_SHOW, SetCursorPos,
    SetForegroundWindow, ShowWindow,
};

pub const MOD_ALT: u32 = 0x0001;
pub const MOD_CONTROL: u32 = 0x0002;
pub const MOD_SHIFT: u32 = 0x0004;
pub const MOD_WIN: u32 = 0x0008;
pub const MOD_NOREPEAT: u32 = 0x4000;
const WHEEL_DELTA: i32 = 120;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HotkeyBinding {
    pub text: String,
    pub modifiers: u32,
    pub virtual_key: u32,
}

#[derive(Debug, Error, Clone, PartialEq, Eq)]
pub enum HotkeyParseError {
    #[error("unknown hotkey part: {0}")]
    UnknownPart(String),
    #[error("missing main key in hotkey: {0}")]
    MissingMainKey(String),
}

#[derive(Debug, Error, Clone, PartialEq, Eq)]
pub enum PlatformError {
    #[error("unknown key: {0}")]
    UnknownKey(String),
    #[error("clipboard is unavailable")]
    ClipboardUnavailable,
    #[error("clipboard does not contain Unicode text")]
    ClipboardNotText,
    #[error("window not found: {0}")]
    WindowNotFound(String),
    #[error("screen pixel read failed at ({x}, {y})")]
    PixelReadFailed { x: i32, y: i32 },
}

pub fn parse_hotkey(input: &str) -> Result<HotkeyBinding, HotkeyParseError> {
    let mut modifiers = 0_u32;
    let mut virtual_key = 0_u32;

    for raw_part in input.split('+') {
        let part = raw_part.trim().to_uppercase();
        match part.as_str() {
            "CTRL" | "CONTROL" => modifiers |= MOD_CONTROL,
            "ALT" => modifiers |= MOD_ALT,
            "SHIFT" => modifiers |= MOD_SHIFT,
            "WIN" | "WINDOWS" => modifiers |= MOD_WIN,
            _ => {
                virtual_key = u32::from(
                    virtual_key_from_name(&part)
                        .ok_or_else(|| HotkeyParseError::UnknownPart(part.to_string()))?,
                );
            }
        }
    }

    if virtual_key == 0 {
        return Err(HotkeyParseError::MissingMainKey(input.to_string()));
    }

    Ok(HotkeyBinding {
        text: input.to_string(),
        modifiers: modifiers | MOD_NOREPEAT,
        virtual_key,
    })
}

pub fn virtual_key_from_name(input: &str) -> Option<u16> {
    let key = input.trim().to_uppercase();
    match key.as_str() {
        "SPACE" => Some(0x20),
        "RETURN" | "ENTER" => Some(0x0D),
        "TAB" => Some(0x09),
        "BACK" | "BACKSPACE" => Some(0x08),
        "DELETE" => Some(0x2E),
        "INSERT" => Some(0x2D),
        "HOME" => Some(0x24),
        "END" => Some(0x23),
        "PAGEUP" => Some(0x21),
        "PAGEDOWN" => Some(0x22),
        "LEFT" => Some(0x25),
        "UP" => Some(0x26),
        "RIGHT" => Some(0x27),
        "DOWN" => Some(0x28),
        "ESC" | "ESCAPE" => Some(0x1B),
        "CAPSLOCK" => Some(0x14),
        "NUMLOCK" => Some(0x90),
        "PRINTSCREEN" => Some(0x2C),
        "CTRL" | "CONTROL" => Some(0x11),
        "SHIFT" => Some(0x10),
        "ALT" => Some(0x12),
        "WIN" | "WINDOWS" => Some(0x5B),
        part if (2..=3).contains(&part.len()) && part.starts_with('F') => {
            let suffix = part[1..].parse::<u16>().ok()?;
            (1..=24).contains(&suffix).then_some(0x6F + suffix)
        }
        part if part.len() == 1 => Some(part.as_bytes()[0] as u16),
        _ => None,
    }
}

pub fn press_key(name: &str) -> Result<(), PlatformError> {
    let key = virtual_key_from_name(name).ok_or_else(|| PlatformError::UnknownKey(name.into()))?;
    send_virtual_key(key, true);
    send_virtual_key(key, false);
    Ok(())
}

pub fn press_key_combo(keys: &[String]) -> Result<(), PlatformError> {
    if keys.is_empty() {
        return Ok(());
    }

    let mut resolved = Vec::with_capacity(keys.len());
    for key in keys {
        resolved.push(
            virtual_key_from_name(key).ok_or_else(|| PlatformError::UnknownKey(key.clone()))?,
        );
    }

    for key in &resolved {
        send_virtual_key(*key, true);
    }
    for key in resolved.iter().rev() {
        send_virtual_key(*key, false);
    }
    Ok(())
}

pub fn type_text(text: &str, interval: Duration) -> Result<(), PlatformError> {
    for unit in text.encode_utf16() {
        send_unicode_unit(unit, true);
        send_unicode_unit(unit, false);
        if !interval.is_zero() {
            thread::sleep(interval);
        }
    }
    Ok(())
}

pub fn move_cursor(x: i32, y: i32) -> Result<(), PlatformError> {
    unsafe {
        SetCursorPos(x, y);
    }
    Ok(())
}

pub fn mouse_click(x: i32, y: i32, button: &str) -> Result<(), PlatformError> {
    move_cursor(x, y)?;
    match button.to_ascii_lowercase().as_str() {
        "right" => {
            send_mouse_event(MOUSEEVENTF_RIGHTDOWN, 0);
            send_mouse_event(MOUSEEVENTF_RIGHTUP, 0);
        }
        _ => {
            send_mouse_event(MOUSEEVENTF_LEFTDOWN, 0);
            send_mouse_event(MOUSEEVENTF_LEFTUP, 0);
        }
    }
    Ok(())
}

pub fn mouse_double_click(x: i32, y: i32) -> Result<(), PlatformError> {
    mouse_click(x, y, "left")?;
    thread::sleep(Duration::from_millis(50));
    mouse_click(x, y, "left")
}

pub fn drag_cursor(
    start_x: i32,
    start_y: i32,
    end_x: i32,
    end_y: i32,
    duration: Duration,
    button: &str,
) -> Result<(), PlatformError> {
    let steps = ((duration.as_millis() / 15).max(1)) as i32;
    move_cursor(start_x, start_y)?;
    match button.to_ascii_lowercase().as_str() {
        "right" => send_mouse_event(MOUSEEVENTF_RIGHTDOWN, 0),
        _ => send_mouse_event(MOUSEEVENTF_LEFTDOWN, 0),
    }

    for step in 1..=steps {
        let x = start_x + ((end_x - start_x) * step / steps);
        let y = start_y + ((end_y - start_y) * step / steps);
        move_cursor(x, y)?;
        if !duration.is_zero() {
            thread::sleep(duration / steps as u32);
        }
    }

    match button.to_ascii_lowercase().as_str() {
        "right" => send_mouse_event(MOUSEEVENTF_RIGHTUP, 0),
        _ => send_mouse_event(MOUSEEVENTF_LEFTUP, 0),
    }
    Ok(())
}

pub fn scroll_mouse(x: i32, y: i32, clicks: i32) -> Result<(), PlatformError> {
    move_cursor(x, y)?;
    send_mouse_event(MOUSEEVENTF_WHEEL, clicks.saturating_mul(WHEEL_DELTA));
    Ok(())
}

pub fn read_clipboard_text() -> Result<String, PlatformError> {
    unsafe {
        if OpenClipboard(null_mut()) == 0 {
            return Err(PlatformError::ClipboardUnavailable);
        }

        let result = (|| {
            let handle = GetClipboardData(CF_UNICODETEXT as u32);
            if handle.is_null() {
                return Err(PlatformError::ClipboardNotText);
            }

            let ptr = GlobalLock(handle) as *const u16;
            if ptr.is_null() {
                return Err(PlatformError::ClipboardUnavailable);
            }

            let mut len = 0usize;
            while *ptr.add(len) != 0 {
                len += 1;
            }
            let slice = std::slice::from_raw_parts(ptr, len);
            let text = String::from_utf16_lossy(slice);
            GlobalUnlock(handle);
            Ok(text)
        })();

        CloseClipboard();
        result
    }
}

pub fn activate_window(title: &str, exact_match: bool) -> Result<(), PlatformError> {
    let hwnd = if exact_match {
        unsafe { FindWindowW(null(), wide_null(title).as_ptr()) }
    } else {
        find_window_partial(title)
    };

    if hwnd.is_null() {
        return Err(PlatformError::WindowNotFound(title.to_string()));
    }

    unsafe {
        if IsIconic(hwnd) != 0 {
            ShowWindow(hwnd, SW_RESTORE);
        }
        if SetForegroundWindow(hwnd) != 0 {
            return Ok(());
        }

        BringWindowToTop(hwnd);
        if GetForegroundWindow() == hwnd {
            return Ok(());
        }

        let fg = GetForegroundWindow();
        let fg_thread = GetWindowThreadProcessId(fg, null_mut());
        let target_thread = GetWindowThreadProcessId(hwnd, null_mut());
        let current_thread = GetCurrentThreadId();
        if fg_thread != target_thread {
            AttachThreadInput(current_thread, target_thread, 1);
            AttachThreadInput(current_thread, fg_thread, 1);
            SetForegroundWindow(hwnd);
            AttachThreadInput(current_thread, fg_thread, 0);
            AttachThreadInput(current_thread, target_thread, 0);
            if GetForegroundWindow() == hwnd {
                return Ok(());
            }
        }

        ShowWindow(hwnd, SW_SHOW);
        SetForegroundWindow(hwnd);
        if GetForegroundWindow() == hwnd {
            return Ok(());
        }
    }

    Err(PlatformError::WindowNotFound(title.to_string()))
}

pub fn get_pixel_color(x: i32, y: i32) -> Result<(u8, u8, u8), PlatformError> {
    unsafe {
        let hdc = GetDC(null_mut());
        if hdc.is_null() {
            return Err(PlatformError::PixelReadFailed { x, y });
        }
        let color = GetPixel(hdc, x, y);
        ReleaseDC(null_mut(), hdc);
        if color == u32::MAX {
            return Err(PlatformError::PixelReadFailed { x, y });
        }
        let r = (color & 0xFF) as u8;
        let g = ((color >> 8) & 0xFF) as u8;
        let b = ((color >> 16) & 0xFF) as u8;
        Ok((r, g, b))
    }
}

pub fn check_pixel_color(
    x: i32,
    y: i32,
    r: u8,
    g: u8,
    b: u8,
    tolerance: u8,
) -> Result<bool, PlatformError> {
    let (pr, pg, pb) = get_pixel_color(x, y)?;
    Ok(pr.abs_diff(r) <= tolerance && pg.abs_diff(g) <= tolerance && pb.abs_diff(b) <= tolerance)
}

pub fn wait_for_pixel_color(
    x: i32,
    y: i32,
    r: u8,
    g: u8,
    b: u8,
    tolerance: u8,
    timeout: Duration,
    poll_interval: Duration,
) -> Result<bool, PlatformError> {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if check_pixel_color(x, y, r, g, b, tolerance)? {
            return Ok(true);
        }
        thread::sleep(poll_interval);
    }
    Ok(false)
}

fn send_virtual_key(key: u16, key_down: bool) {
    unsafe {
        let mut input = INPUT {
            r#type: INPUT_KEYBOARD,
            Anonymous: INPUT_0 {
                ki: KEYBDINPUT {
                    wVk: key,
                    wScan: 0,
                    dwFlags: if key_down { 0 } else { KEYEVENTF_KEYUP },
                    time: 0,
                    dwExtraInfo: 0,
                },
            },
        };
        SendInput(1, &mut input, size_of::<INPUT>() as i32);
    }
}

fn send_unicode_unit(unit: u16, key_down: bool) {
    unsafe {
        let mut input = INPUT {
            r#type: INPUT_KEYBOARD,
            Anonymous: INPUT_0 {
                ki: KEYBDINPUT {
                    wVk: 0,
                    wScan: unit,
                    dwFlags: if key_down {
                        KEYEVENTF_UNICODE
                    } else {
                        KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
                    },
                    time: 0,
                    dwExtraInfo: 0,
                },
            },
        };
        SendInput(1, &mut input, size_of::<INPUT>() as i32);
    }
}

fn send_mouse_event(flags: u32, data: i32) {
    unsafe {
        mouse_event(flags, 0, 0, data, 0);
    }
}

fn wide_null(value: &str) -> Vec<u16> {
    value.encode_utf16().chain(Some(0)).collect()
}

struct WindowSearch<'a> {
    query: &'a str,
    result: HWND,
}

unsafe extern "system" fn enum_windows_proc(hwnd: HWND, lparam: LPARAM) -> BOOL {
    let state = unsafe { &mut *(lparam as *mut WindowSearch<'_>) };
    if unsafe { IsWindowVisible(hwnd) } == 0 {
        return 1;
    }

    let mut buffer = vec![0u16; 512];
    let len = unsafe { GetWindowTextW(hwnd, buffer.as_mut_ptr(), buffer.len() as i32) };
    if len <= 0 {
        return 1;
    }

    let title = String::from_utf16_lossy(&buffer[..len as usize]).to_ascii_lowercase();
    if title.contains(&state.query.to_ascii_lowercase()) {
        state.result = hwnd;
        0
    } else {
        1
    }
}

fn find_window_partial(query: &str) -> HWND {
    let mut state = WindowSearch {
        query,
        result: null_mut(),
    };
    unsafe {
        EnumWindows(Some(enum_windows_proc), &mut state as *mut _ as isize);
    }
    state.result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_simple_function_key() {
        let binding = parse_hotkey("F6").expect("hotkey should parse");
        assert_eq!(binding.virtual_key, 0x75);
        assert_eq!(binding.modifiers, MOD_NOREPEAT);
    }

    #[test]
    fn parses_modifier_combo() {
        let binding = parse_hotkey("CTRL+SHIFT+F9").expect("combo should parse");
        assert_eq!(binding.virtual_key, 0x78);
        assert_eq!(binding.modifiers, MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT);
    }

    #[test]
    fn maps_common_virtual_keys() {
        assert_eq!(virtual_key_from_name("enter"), Some(0x0D));
        assert_eq!(virtual_key_from_name("a"), Some(b'A' as u16));
        assert_eq!(virtual_key_from_name("f12"), Some(0x7B));
    }
}
