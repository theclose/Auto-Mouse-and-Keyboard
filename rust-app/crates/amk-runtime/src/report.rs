//! Playback report — statistics collected during a macro run.

use std::time::{Duration, Instant};

/// Summary of a completed (or stopped) macro run.
#[derive(Debug, Clone)]
pub struct PlaybackReport {
    /// Total actions executed (including repeats).
    pub actions_executed: u64,
    /// Actions that succeeded.
    pub actions_succeeded: u64,
    /// Actions that failed.
    pub actions_failed: u64,
    /// Actions skipped (disabled or error-policy skip).
    pub actions_skipped: u64,
    /// Loops completed.
    pub loops_completed: u32,
    /// Wall-clock duration.
    pub duration: Duration,
    /// How the run ended.
    pub exit_reason: ExitReason,
}

/// Why the engine stopped.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ExitReason {
    /// All actions completed normally.
    Completed,
    /// Stopped by user (hotkey or UI).
    UserStopped,
    /// Stopped due to an action error with on_error=Stop.
    ErrorStopped,
}

impl PlaybackReport {
    /// Create a new report tracker (call `finalize` when done).
    pub(crate) fn start() -> ReportBuilder {
        ReportBuilder {
            start: Instant::now(),
            executed: 0,
            succeeded: 0,
            failed: 0,
            skipped: 0,
            loops: 0,
        }
    }
}

/// Builder that accumulates stats during a run.
pub(crate) struct ReportBuilder {
    start: Instant,
    executed: u64,
    succeeded: u64,
    failed: u64,
    skipped: u64,
    loops: u32,
}

impl ReportBuilder {
    pub fn record_success(&mut self) {
        self.executed += 1;
        self.succeeded += 1;
    }

    pub fn record_failure(&mut self) {
        self.executed += 1;
        self.failed += 1;
    }

    pub fn record_skip(&mut self) {
        self.skipped += 1;
    }

    pub fn record_loop(&mut self) {
        self.loops += 1;
    }

    pub fn finalize(self, reason: ExitReason) -> PlaybackReport {
        PlaybackReport {
            actions_executed: self.executed,
            actions_succeeded: self.succeeded,
            actions_failed: self.failed,
            actions_skipped: self.skipped,
            loops_completed: self.loops,
            duration: self.start.elapsed(),
            exit_reason: reason,
        }
    }
}
