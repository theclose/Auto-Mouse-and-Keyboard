//! Typed action model and execution context for AutoMacro.
//!
//! This crate converts raw JSON actions (`amk_schema::RawAction`) into strongly-typed
//! Rust enums with validated parameters. This is the core domain layer — no I/O, no UI.

pub mod action;
pub mod context;
mod convert;

pub use action::ActionKind;
pub use context::ExecutionContext;
pub use convert::{ConvertError, convert_action, convert_actions};

// Re-export schema for convenience
pub use amk_schema;
