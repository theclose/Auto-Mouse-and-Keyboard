//! Clipboard read/write via Win32 API.

use std::ffi::OsStr;
use std::os::windows::ffi::OsStrExt;
use std::ptr;

use windows_sys::Win32::Foundation::*;
use windows_sys::Win32::System::DataExchange::*;
use windows_sys::Win32::System::Memory::*;

/// Read text from clipboard. Returns empty string on failure.
#[must_use]
pub fn read_clipboard() -> String {
    unsafe {
        if OpenClipboard(ptr::null_mut()) == 0 {
            return String::new();
        }

        let handle = GetClipboardData(13); // CF_UNICODETEXT = 13
        if handle.is_null() {
            CloseClipboard();
            return String::new();
        }

        let ptr_data = GlobalLock(handle) as *const u16;
        if ptr_data.is_null() {
            CloseClipboard();
            return String::new();
        }

        // Find null terminator
        let mut len = 0usize;
        while *ptr_data.add(len) != 0 {
            len += 1;
            if len > 1_000_000 { break; } // safety limit
        }

        let slice = std::slice::from_raw_parts(ptr_data, len);
        let text = String::from_utf16_lossy(slice);

        GlobalUnlock(handle);
        CloseClipboard();
        text
    }
}

/// Write text to clipboard. Returns true on success.
pub fn write_clipboard(text: &str) -> bool {
    let wide: Vec<u16> = OsStr::new(text).encode_wide().chain(Some(0)).collect();
    let byte_len = wide.len() * 2;

    unsafe {
        if OpenClipboard(ptr::null_mut()) == 0 {
            return false;
        }

        EmptyClipboard();

        let hmem = GlobalAlloc(GMEM_MOVEABLE, byte_len);
        if hmem.is_null() {
            CloseClipboard();
            return false;
        }

        let dest = GlobalLock(hmem) as *mut u16;
        if dest.is_null() {
            GlobalFree(hmem);
            CloseClipboard();
            return false;
        }

        ptr::copy_nonoverlapping(wide.as_ptr(), dest, wide.len());
        GlobalUnlock(hmem);

        let result = SetClipboardData(13, hmem); // CF_UNICODETEXT
        CloseClipboard();
        !result.is_null()
    }
}
