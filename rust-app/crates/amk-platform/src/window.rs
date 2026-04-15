#![allow(clippy::not_unsafe_ptr_arg_deref)]
//! Window management: find, activate, enumerate.

use std::ffi::OsStr;
use std::os::windows::ffi::OsStrExt;

use windows_sys::Win32::Foundation::*;
use windows_sys::Win32::UI::WindowsAndMessaging::*;

/// Find a window by title (contains match).
#[must_use]
pub fn find_window_contains(title: &str) -> Option<HWND> {
    let target = title.to_lowercase();
    let mut found: HWND = std::ptr::null_mut();

    unsafe {
        EnumWindows(Some(enum_callback), &mut (&target, &mut found) as *mut _ as LPARAM);
    }
    if found.is_null() { None } else { Some(found) }
}

unsafe extern "system" fn enum_callback(hwnd: HWND, lparam: LPARAM) -> BOOL {
    unsafe {
        let data = &mut *(lparam as *mut (&String, &mut HWND));
        let target = data.0;
        let found = &mut data.1;

        let mut buf = [0u16; 512];
        let len = GetWindowTextW(hwnd, buf.as_mut_ptr(), 512);
        if len > 0 {
            let title = String::from_utf16_lossy(&buf[..len as usize]).to_lowercase();
            if title.contains(target.as_str()) {
                **found = hwnd;
                return FALSE; // stop enumeration
            }
        }
        TRUE // continue
    }
}

/// Find a window by exact title.
#[must_use]
pub fn find_window_exact(title: &str) -> Option<HWND> {
    let wide: Vec<u16> = OsStr::new(title).encode_wide().chain(Some(0)).collect();
    let hwnd = unsafe { FindWindowW(std::ptr::null(), wide.as_ptr()) };
    if hwnd.is_null() { None } else { Some(hwnd) }
}

/// Activate (bring to foreground) a window by handle.
pub fn activate_window(hwnd: HWND) -> bool {
    unsafe {
        if SetForegroundWindow(hwnd) != FALSE {
            return true;
        }
        ShowWindow(hwnd, SW_MINIMIZE);
        ShowWindow(hwnd, SW_RESTORE);
        SetForegroundWindow(hwnd) != FALSE
    }
}

/// Find and activate a window by title.
pub fn find_and_activate(title: &str, match_type: &str) -> bool {
    let hwnd = match match_type {
        "exact" => find_window_exact(title),
        _ => find_window_contains(title),
    };

    match hwnd {
        Some(h) => activate_window(h),
        None => false,
    }
}

/// Get the title of a window.
#[must_use]
pub fn get_window_title(hwnd: HWND) -> String {
    let mut buf = [0u16; 512];
    let len = unsafe { GetWindowTextW(hwnd, buf.as_mut_ptr(), 512) };
    if len > 0 {
        String::from_utf16_lossy(&buf[..len as usize])
    } else {
        String::new()
    }
}
