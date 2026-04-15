//! Windows platform layer for AutoMacro.
//!
//! Modules:
//! - `input` — Mouse and keyboard via SendInput
//! - `window` — Window management (find, activate, enumerate)
//! - `clipboard` — Clipboard read/write
//! - `capture` — Screen capture and pixel reading
//! - `stealth` — PostMessage-based stealth input
//! - `win32_executor` — Full `Executor` trait implementation

pub mod input;
pub mod window;
pub mod clipboard;
pub mod crypto;
pub mod capture;
pub mod vision;
pub mod hotkey;
pub mod stealth;
pub mod sleeper;
pub mod win32_executor;

pub use win32_executor::Win32Executor;
