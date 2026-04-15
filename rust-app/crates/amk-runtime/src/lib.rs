//! Macro engine, executor, and playback runtime for AutoMacro.
//!
//! The runtime layer converts typed actions into real execution via an `Executor` trait.
//! The `MacroEngine` manages lifecycle (run/pause/resume/stop/step) and error policies.

pub mod engine;
pub mod executor;
pub mod report;

pub use engine::{MacroEngine, EngineState};
pub use executor::Executor;
pub use report::PlaybackReport;

// Re-export domain for convenience
pub use amk_domain;
