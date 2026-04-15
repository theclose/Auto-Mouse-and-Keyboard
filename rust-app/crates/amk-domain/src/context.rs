//! Execution context — per-engine variable store and state.
//!
//! Each `MacroEngine` gets its own `ExecutionContext`. Thread-safe by ownership
//! (one context per thread, no sharing needed).

use std::collections::HashMap;

/// Runtime state for a single macro execution.
#[derive(Debug, Clone)]
pub struct ExecutionContext {
    /// User-defined variables (name → value as string).
    variables: HashMap<String, String>,
    /// Last action result (for chaining).
    last_result: Option<String>,
    /// Actions executed count.
    action_count: u64,
    /// Successful actions.
    success_count: u64,
    /// Failed actions.
    fail_count: u64,
}

impl ExecutionContext {
    /// Create a new, empty context.
    #[must_use]
    pub fn new() -> Self {
        Self {
            variables: HashMap::new(),
            last_result: None,
            action_count: 0,
            success_count: 0,
            fail_count: 0,
        }
    }

    /// Reset all state for a new run.
    pub fn reset(&mut self) {
        self.variables.clear();
        self.last_result = None;
        self.action_count = 0;
        self.success_count = 0;
        self.fail_count = 0;
    }

    // ── Variables ─────────────────────────────────────────

    /// Set a variable.
    pub fn set_var(&mut self, name: &str, value: &str) {
        self.variables.insert(name.to_owned(), value.to_owned());
    }

    /// Get a variable value. Returns empty string if not found.
    #[must_use]
    pub fn get_var(&self, name: &str) -> &str {
        self.variables.get(name).map_or("", String::as_str)
    }

    /// Check if a variable exists.
    #[must_use]
    pub fn has_var(&self, name: &str) -> bool {
        self.variables.contains_key(name)
    }

    /// Get all variables as a snapshot (for UI display).
    #[must_use]
    pub fn snapshot_vars(&self) -> Vec<(String, String)> {
        let mut out: Vec<_> = self.variables.iter()
            .map(|(k, v)| (k.clone(), v.clone()))
            .collect();
        out.sort_by(|a, b| a.0.cmp(&b.0));
        out
    }

    /// Interpolate `{var_name}` placeholders in a string.
    #[must_use]
    pub fn interpolate(&self, template: &str) -> String {
        let mut result = template.to_owned();
        for (name, value) in &self.variables {
            let placeholder = format!("{{{name}}}");
            result = result.replace(&placeholder, value);
        }
        result
    }

    // ── Stats ────────────────────────────────────────────

    /// Record that an action was executed.
    pub fn record_action(&mut self, success: bool) {
        self.action_count += 1;
        if success {
            self.success_count += 1;
        } else {
            self.fail_count += 1;
        }
    }

    /// Set the last action result.
    pub fn set_last_result(&mut self, result: &str) {
        self.last_result = Some(result.to_owned());
    }

    /// Get the last action result.
    #[must_use]
    pub fn last_result(&self) -> Option<&str> {
        self.last_result.as_deref()
    }

    #[must_use]
    pub fn action_count(&self) -> u64 {
        self.action_count
    }

    #[must_use]
    pub fn success_count(&self) -> u64 {
        self.success_count
    }

    #[must_use]
    pub fn fail_count(&self) -> u64 {
        self.fail_count
    }
}

impl Default for ExecutionContext {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn new_context_is_empty() {
        let ctx = ExecutionContext::new();
        assert_eq!(ctx.get_var("x"), "");
        assert!(!ctx.has_var("x"));
        assert_eq!(ctx.action_count(), 0);
    }

    #[test]
    fn set_and_get_var() {
        let mut ctx = ExecutionContext::new();
        ctx.set_var("count", "42");
        assert_eq!(ctx.get_var("count"), "42");
        assert!(ctx.has_var("count"));
    }

    #[test]
    fn interpolation() {
        let mut ctx = ExecutionContext::new();
        ctx.set_var("name", "World");
        ctx.set_var("num", "3");
        assert_eq!(ctx.interpolate("Hello {name} #{num}!"), "Hello World #3!");
    }

    #[test]
    fn interpolation_missing_var_unchanged() {
        let ctx = ExecutionContext::new();
        assert_eq!(ctx.interpolate("Hello {missing}"), "Hello {missing}");
    }

    #[test]
    fn record_stats() {
        let mut ctx = ExecutionContext::new();
        ctx.record_action(true);
        ctx.record_action(true);
        ctx.record_action(false);
        assert_eq!(ctx.action_count(), 3);
        assert_eq!(ctx.success_count(), 2);
        assert_eq!(ctx.fail_count(), 1);
    }

    #[test]
    fn reset_clears_all() {
        let mut ctx = ExecutionContext::new();
        ctx.set_var("x", "1");
        ctx.record_action(true);
        ctx.set_last_result("ok");
        ctx.reset();
        assert_eq!(ctx.get_var("x"), "");
        assert_eq!(ctx.action_count(), 0);
        assert!(ctx.last_result().is_none());
    }

    #[test]
    fn snapshot_sorted() {
        let mut ctx = ExecutionContext::new();
        ctx.set_var("z", "last");
        ctx.set_var("a", "first");
        let snap = ctx.snapshot_vars();
        assert_eq!(snap[0].0, "a");
        assert_eq!(snap[1].0, "z");
    }
}
