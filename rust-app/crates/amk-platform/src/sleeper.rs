//! Interruptible sleeper utility to prevent blocking long durations.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::{Duration, Instant};

/// A utility to sleep in small chunks, allowing an atomic flag to interrupt the sleep.
pub struct SmartSleeper {
    stop_flag: Arc<AtomicBool>,
    chunk_ms: u64,
}

impl SmartSleeper {
    /// Create a new sleeper bound to a stop flag.
    pub fn new(stop_flag: Arc<AtomicBool>) -> Self {
        Self {
            stop_flag,
            chunk_ms: 15, // 15ms base resolution (good for UI responsiveness)
        }
    }

    /// Sleep for a total duration in milliseconds. Returns true if fully slept, false if interrupted by stop_flag.
    pub fn sleep(&self, ms: u32) -> bool {
        if ms == 0 {
            return !self.stop_flag.load(Ordering::Relaxed);
        }

        let target = Instant::now() + Duration::from_millis(ms as u64);
        
        while Instant::now() < target {
            if self.stop_flag.load(Ordering::Relaxed) {
                return false;
            }

            let remain = target.saturating_duration_since(Instant::now());
            if remain.as_millis() == 0 {
                break;
            }

            let sleep_time = if remain.as_millis() > self.chunk_ms as u128 {
                Duration::from_millis(self.chunk_ms)
            } else {
                remain
            };

            thread::sleep(sleep_time);
        }

        !self.stop_flag.load(Ordering::Relaxed)
    }

    /// Wait until a condition is true or timeout is reached. Yields CPU execution safely.
    /// Returns true if the condition returns true, false if timeout or interrupted.
    pub fn wait_until<F>(&self, timeout_ms: u32, mut condition: F) -> bool
    where
        F: FnMut() -> bool,
    {
        let target = Instant::now() + Duration::from_millis(timeout_ms as u64);
        while Instant::now() < target {
            if self.stop_flag.load(Ordering::Relaxed) {
                return false;
            }

            if condition() {
                return true;
            }

            thread::sleep(Duration::from_millis(15));
        }
        false
    }
}
