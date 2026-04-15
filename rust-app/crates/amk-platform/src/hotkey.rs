//! Global Hotkey listener utilizing Win32 `RegisterHotKey`.
//! Useful to stop macros autonomously via system-wide hooks.

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::thread;

use windows_sys::Win32::UI::WindowsAndMessaging::{
    GetMessageW, PostThreadMessageW, MSG, WM_HOTKEY, WM_QUIT,
};
use windows_sys::Win32::UI::Input::KeyboardAndMouse::{RegisterHotKey, UnregisterHotKey};
use windows_sys::Win32::System::Threading::GetCurrentThreadId;

/// Handle to a running hotkey listener thread.
/// When dropped, sends WM_QUIT to shut down the message pump cleanly.
pub struct HotkeyHandle {
    thread_id: u32,
    _handle: thread::JoinHandle<()>,
}

impl Drop for HotkeyHandle {
    fn drop(&mut self) {
        unsafe {
            // Post WM_QUIT to break the message loop
            PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0);
        }
        // Note: we don't join here to avoid blocking the UI thread.
        // The thread will exit promptly after receiving WM_QUIT.
    }
}

/// Spawns a background OS thread that registers a system-wide hotkey.
/// When the hotkey is pressed, it flips the shared atomic flag to `true`.
///
/// Returns a `HotkeyHandle` that will clean up the hotkey when dropped.
///
/// Note: Due to Win32 architecture, `RegisterHotKey` requires a message pump.
/// Therefore, we start a dedicated thread for this.
pub fn spawn_stop_hotkey_thread(
    stop_flag: Arc<AtomicBool>,
    vk_code: u32,
    modifiers: u32,
) -> Option<HotkeyHandle> {
    // Use a channel to pass the thread ID back from the spawned thread
    let (tx, rx) = std::sync::mpsc::channel::<u32>();

    let handle = thread::spawn(move || {
        unsafe {
            let tid = GetCurrentThreadId();
            let _ = tx.send(tid);

            // Register hotkey with ID 1
            if RegisterHotKey(std::ptr::null_mut(), 1, modifiers, vk_code) == 0 {
                tracing::warn!("Failed to register stopping hotkey. Another application might be using it.");
                return;
            }

            let mut msg: MSG = std::mem::zeroed();
            
            // Blocking message pump — exits on WM_QUIT
            while GetMessageW(&mut msg, std::ptr::null_mut(), 0, 0) > 0 {
                if msg.message == WM_HOTKEY && msg.wParam == 1 {
                    stop_flag.store(true, Ordering::Release);
                    tracing::info!("Global Stop Hotkey Pressed!");
                }
            }

            // Clean up
            UnregisterHotKey(std::ptr::null_mut(), 1);
        }
    });

    // Wait for thread to report its ID (with timeout)
    match rx.recv_timeout(std::time::Duration::from_secs(2)) {
        Ok(thread_id) => Some(HotkeyHandle {
            thread_id,
            _handle: handle,
        }),
        Err(_) => {
            tracing::warn!("Hotkey thread failed to start within timeout");
            None
        }
    }
}
