use std::str::Chars;
use std::thread;
use std::time::{Duration, Instant};

use amk_domain::action::{
    Action, ActionKind, DelayAction, GroupAction, IfImageFoundAction, IfPixelColorAction,
    IfVariableAction, LoopBlockAction, SetVariableAction, SplitStringAction,
};
use amk_domain::{ExecutionContext, ExecutionSnapshot};
use csv::ReaderBuilder;
use flume::{Receiver, Sender};
use serde::{Deserialize, Serialize};
use serde_json::{Number, Value};
use thiserror::Error;
use tracing::warn;

const DEFAULT_RETRY_DELAY_MS: u64 = 1_000;
const DEFAULT_SLEEP_QUANTUM_MS: u64 = 25;
const DEFAULT_MAX_COMPOSITE_DEPTH: usize = 16;
const DEFAULT_MAX_INFINITE_LOOP_DURATION_MS: u64 = 24 * 60 * 60 * 1_000;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct PlaybackReport {
    pub total: usize,
    pub success: usize,
    pub failed: usize,
    pub skipped: usize,
    pub duration_ms: u64,
    pub first_error: Option<String>,
    pub first_error_index: Option<usize>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RuntimeCheckpoint {
    pub action_index: usize,
    pub context: ExecutionSnapshot,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RuntimeOptions {
    pub loop_count: u32,
    pub loop_delay_ms: u32,
    pub stop_on_error: bool,
    pub speed_factor: f64,
    pub step_mode: bool,
    pub retry_delay_ms: u64,
    pub sleep_quantum_ms: u64,
    pub max_composite_depth: usize,
    pub max_infinite_loop_duration_ms: u64,
    pub resume_from: Option<RuntimeCheckpoint>,
}

impl Default for RuntimeOptions {
    fn default() -> Self {
        Self {
            loop_count: 1,
            loop_delay_ms: 0,
            stop_on_error: false,
            speed_factor: 1.0,
            step_mode: false,
            retry_delay_ms: DEFAULT_RETRY_DELAY_MS,
            sleep_quantum_ms: DEFAULT_SLEEP_QUANTUM_MS,
            max_composite_depth: DEFAULT_MAX_COMPOSITE_DEPTH,
            max_infinite_loop_duration_ms: DEFAULT_MAX_INFINITE_LOOP_DURATION_MS,
            resume_from: None,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum EngineEvent {
    Started,
    LoopProgress {
        current: usize,
        total: Option<usize>,
    },
    Progress {
        current: usize,
        total: usize,
        action_type: String,
    },
    NestedProgress {
        path: Vec<usize>,
        action_type: String,
    },
    Paused,
    Resumed,
    Stopped(PlaybackReport),
    Failed(String),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum EngineCommand {
    Pause,
    Resume,
    Stop,
    StepNext,
}

#[derive(Debug, Error, Clone, PartialEq, Eq)]
pub enum RuntimeError {
    #[error("{0}")]
    Message(String),
}

impl RuntimeError {
    fn message(value: impl Into<String>) -> Self {
        Self::Message(value.into())
    }
}

pub trait ActionExecutor {
    fn execute_atomic(
        &mut self,
        action: &Action,
        context: &ExecutionContext,
    ) -> Result<bool, RuntimeError>;

    fn evaluate_image_found(
        &mut self,
        action: &IfImageFoundAction,
        _context: &ExecutionContext,
    ) -> Result<bool, RuntimeError> {
        Err(RuntimeError::message(format!(
            "image evaluation not implemented for {}",
            action.image_path
        )))
    }

    fn evaluate_pixel_color(
        &mut self,
        action: &IfPixelColorAction,
        _context: &ExecutionContext,
    ) -> Result<bool, RuntimeError> {
        Err(RuntimeError::message(format!(
            "pixel evaluation not implemented for ({}, {})",
            action.x, action.y
        )))
    }
}

pub struct EngineBus {
    pub commands_tx: Sender<EngineCommand>,
    pub commands_rx: Receiver<EngineCommand>,
    pub events_tx: Sender<EngineEvent>,
    pub events_rx: Receiver<EngineEvent>,
}

impl EngineBus {
    pub fn new() -> Self {
        let (commands_tx, commands_rx) = flume::unbounded();
        let (events_tx, events_rx) = flume::unbounded();
        Self {
            commands_tx,
            commands_rx,
            events_tx,
            events_rx,
        }
    }
}

pub fn run_actions<E: ActionExecutor>(
    actions: &[Action],
    context: &ExecutionContext,
    executor: &mut E,
    events: Option<&Sender<EngineEvent>>,
) -> Result<PlaybackReport, RuntimeError> {
    run_actions_with_options(
        actions,
        context,
        executor,
        &RuntimeOptions::default(),
        None,
        events,
    )
}

pub fn run_actions_with_bus<E: ActionExecutor>(
    actions: &[Action],
    context: &ExecutionContext,
    executor: &mut E,
    options: &RuntimeOptions,
    bus: &EngineBus,
) -> Result<PlaybackReport, RuntimeError> {
    run_actions_with_options(
        actions,
        context,
        executor,
        options,
        Some(&bus.commands_rx),
        Some(&bus.events_tx),
    )
}

pub fn run_actions_with_options<E: ActionExecutor>(
    actions: &[Action],
    context: &ExecutionContext,
    executor: &mut E,
    options: &RuntimeOptions,
    commands: Option<&Receiver<EngineCommand>>,
    events: Option<&Sender<EngineEvent>>,
) -> Result<PlaybackReport, RuntimeError> {
    let runner = RuntimeRunner::new(context, executor, options, commands, events);
    Ok(runner.run(actions))
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum ErrorPolicy {
    Stop,
    Skip,
    Retry(usize),
}

#[derive(Debug, Clone)]
struct ActionRunOutcome {
    success: bool,
    error: Option<RuntimeError>,
}

impl ActionRunOutcome {
    fn success() -> Self {
        Self {
            success: true,
            error: None,
        }
    }

    fn failure(error: Option<RuntimeError>) -> Self {
        Self {
            success: false,
            error,
        }
    }
}

struct RuntimeRunner<'a, E> {
    context: &'a ExecutionContext,
    executor: &'a mut E,
    options: &'a RuntimeOptions,
    commands: Option<&'a Receiver<EngineCommand>>,
    events: Option<&'a Sender<EngineEvent>>,
    report: PlaybackReport,
    last_checkpoint: Option<RuntimeCheckpoint>,
    paused: bool,
    stopped: bool,
}

impl<'a, E: ActionExecutor> RuntimeRunner<'a, E> {
    fn new(
        context: &'a ExecutionContext,
        executor: &'a mut E,
        options: &'a RuntimeOptions,
        commands: Option<&'a Receiver<EngineCommand>>,
        events: Option<&'a Sender<EngineEvent>>,
    ) -> Self {
        Self {
            context,
            executor,
            options,
            commands,
            events,
            report: PlaybackReport::default(),
            last_checkpoint: None,
            paused: false,
            stopped: false,
        }
    }

    fn run(mut self, actions: &[Action]) -> PlaybackReport {
        self.context.reset();
        if let Some(checkpoint) = &self.options.resume_from {
            self.context.restore(&checkpoint.context);
            self.last_checkpoint = Some(checkpoint.clone());
        }

        self.report.total = actions.len();
        let started_at = Instant::now();
        self.emit(EngineEvent::Started);

        let total_loops = if self.options.loop_count == 0 {
            None
        } else {
            Some(self.options.loop_count as usize)
        };
        let resume_from_index = self
            .options
            .resume_from
            .as_ref()
            .map(|checkpoint| checkpoint.action_index)
            .unwrap_or(0)
            .min(actions.len());

        let mut loop_index = 0usize;
        while !self.stopped {
            loop_index += 1;
            self.emit(EngineEvent::LoopProgress {
                current: loop_index,
                total: total_loops,
            });

            let start_index = if loop_index == 1 {
                resume_from_index
            } else {
                0
            };
            if !self.run_action_list(actions, start_index) {
                break;
            }

            if let Some(total) = total_loops {
                if loop_index >= total {
                    break;
                }
            }

            if self.options.loop_delay_ms > 0
                && !self.interruptible_sleep(
                    self.scaled_duration(Duration::from_millis(self.options.loop_delay_ms as u64)),
                )
            {
                break;
            }
        }

        self.report.duration_ms = started_at.elapsed().as_millis() as u64;
        self.emit(EngineEvent::Stopped(self.report.clone()));
        self.report
    }

    fn run_action_list(&mut self, actions: &[Action], start_index: usize) -> bool {
        for (index, action) in actions.iter().enumerate().skip(start_index) {
            if !self.check_pause_or_stop() {
                return false;
            }

            self.context.set_iteration_count((index + 1) as u64);
            self.emit(EngineEvent::Progress {
                current: index + 1,
                total: actions.len(),
                action_type: action.action_type().to_string(),
            });
            self.last_checkpoint = Some(RuntimeCheckpoint {
                action_index: index,
                context: self.context.snapshot(),
            });

            let outcome = self.run_action_with_policy(action, &[index], 0);
            if outcome.success {
                self.context.record_action(true);
                self.report.success += 1;
            } else {
                self.context.record_action(false);
                self.report.failed += 1;
                let message = outcome
                    .error
                    .as_ref()
                    .map(ToString::to_string)
                    .unwrap_or_else(|| {
                        format!(
                            "action {} returned unsuccessful result",
                            action.action_type()
                        )
                    });
                self.report.first_error.get_or_insert(message.clone());
                self.report.first_error_index.get_or_insert(index);
                self.emit(EngineEvent::Failed(message));

                if self.options.stop_on_error {
                    return false;
                }
            }

            if self.options.step_mode && !self.stopped {
                self.set_paused(true);
            }
        }

        true
    }

    fn run_action_with_policy(
        &mut self,
        action: &Action,
        path: &[usize],
        depth: usize,
    ) -> ActionRunOutcome {
        if !action.common.enabled {
            return ActionRunOutcome::success();
        }

        let repeats = action.common.repeat_count.max(1);
        let policy = parse_error_policy(&action.common.on_error);
        for _ in 0..repeats {
            let outcome = self.run_action_once_with_policy(action, path, depth, policy);
            if !outcome.success {
                return outcome;
            }

            if action.common.delay_after > 0
                && !self.interruptible_sleep(
                    self.scaled_duration(Duration::from_millis(action.common.delay_after as u64)),
                )
            {
                return ActionRunOutcome::success();
            }
        }

        ActionRunOutcome::success()
    }

    fn run_action_once_with_policy(
        &mut self,
        action: &Action,
        path: &[usize],
        depth: usize,
        policy: ErrorPolicy,
    ) -> ActionRunOutcome {
        let attempts = match policy {
            ErrorPolicy::Retry(retries) => retries.saturating_add(1),
            ErrorPolicy::Stop | ErrorPolicy::Skip => 1,
        };

        for attempt in 0..attempts {
            match self.execute_action_once(action, path, depth) {
                Ok(true) => return ActionRunOutcome::success(),
                Ok(false) => match policy {
                    ErrorPolicy::Skip => return ActionRunOutcome::success(),
                    ErrorPolicy::Retry(retries) if attempt < retries => {
                        if !self.interruptible_sleep(
                            self.scaled_duration(Duration::from_millis(
                                self.options.retry_delay_ms,
                            )),
                        ) {
                            return ActionRunOutcome::success();
                        }
                    }
                    ErrorPolicy::Stop | ErrorPolicy::Retry(_) => {
                        return ActionRunOutcome::failure(Some(RuntimeError::message(format!(
                            "action {} returned unsuccessful result at {:?}",
                            action.action_type(),
                            path
                        ))));
                    }
                },
                Err(error) => {
                    match policy {
                        ErrorPolicy::Skip => return ActionRunOutcome::success(),
                        ErrorPolicy::Retry(retries) if attempt < retries => {
                            if !self.interruptible_sleep(self.scaled_duration(
                                Duration::from_millis(self.options.retry_delay_ms),
                            )) {
                                return ActionRunOutcome::success();
                            }
                        }
                        ErrorPolicy::Stop | ErrorPolicy::Retry(_) => {
                            return ActionRunOutcome::failure(Some(error));
                        }
                    }
                }
            }
        }

        ActionRunOutcome::failure(Some(RuntimeError::message(format!(
            "action {} exhausted retry policy at {:?}",
            action.action_type(),
            path
        ))))
    }

    fn execute_action_once(
        &mut self,
        action: &Action,
        path: &[usize],
        depth: usize,
    ) -> Result<bool, RuntimeError> {
        match &action.kind {
            ActionKind::Delay(value) => self.execute_delay(value),
            ActionKind::LoopBlock(value) => self.execute_loop_block(value, path, depth),
            ActionKind::IfImageFound(value) => self.execute_if_image_found(value, path, depth),
            ActionKind::IfPixelColor(value) => self.execute_if_pixel_color(value, path, depth),
            ActionKind::IfVariable(value) => self.execute_if_variable(value, path, depth),
            ActionKind::SetVariable(value) => self.execute_set_variable(value),
            ActionKind::SplitString(value) => self.execute_split_string(value),
            ActionKind::Comment(_) => Ok(true),
            ActionKind::Group(value) => self.execute_group(value, path, depth),
            _ => self.executor.execute_atomic(action, self.context),
        }
    }

    fn execute_delay(&mut self, action: &DelayAction) -> Result<bool, RuntimeError> {
        let mut duration_ms = action.duration_ms as u64;
        if let Some(dynamic_ms) = &action.dynamic_ms {
            let rendered = self.context.interpolate(dynamic_ms);
            if let Ok(parsed) = rendered.trim().parse::<f64>() {
                duration_ms = parsed.max(0.0).round() as u64;
            }
        }

        if duration_ms == 0 {
            return Ok(true);
        }

        let _ = self.interruptible_sleep(self.scaled_duration(Duration::from_millis(duration_ms)));
        Ok(true)
    }

    fn execute_loop_block(
        &mut self,
        action: &LoopBlockAction,
        path: &[usize],
        depth: usize,
    ) -> Result<bool, RuntimeError> {
        self.ensure_composite_depth(depth + 1, "loop_block")?;
        let started = Instant::now();
        let mut iteration = 0u32;

        loop {
            if self.stopped {
                return Ok(true);
            }

            iteration = iteration.saturating_add(1);
            self.context.set_iteration_count(iteration as u64);

            if action.iterations == 0
                && started.elapsed()
                    > Duration::from_millis(self.options.max_infinite_loop_duration_ms)
            {
                warn!("loop_block hit infinite-loop safety timeout");
                return Ok(true);
            }

            if take_control_flag(self.context, "__break__") {
                break;
            }

            for (child_index, child) in action.sub_actions.iter().enumerate() {
                if !self.check_pause_or_stop() {
                    return Ok(true);
                }

                if take_control_flag(self.context, "__continue__") {
                    break;
                }

                let child_path = extend_path(path, child_index);
                self.emit(EngineEvent::NestedProgress {
                    path: child_path.clone(),
                    action_type: child.action_type().to_string(),
                });
                let outcome = self.run_action_with_policy(child, &child_path, depth + 1);
                if !outcome.success {
                    return Ok(false);
                }
            }

            if action.iterations > 0 && iteration >= action.iterations {
                break;
            }
        }

        Ok(true)
    }

    fn execute_group(
        &mut self,
        action: &GroupAction,
        path: &[usize],
        depth: usize,
    ) -> Result<bool, RuntimeError> {
        self.ensure_composite_depth(depth + 1, "group")?;
        for (child_index, child) in action.children.iter().enumerate() {
            if !self.check_pause_or_stop() {
                return Ok(true);
            }

            let child_path = extend_path(path, child_index);
            self.emit(EngineEvent::NestedProgress {
                path: child_path.clone(),
                action_type: child.action_type().to_string(),
            });
            let outcome = self.run_action_with_policy(child, &child_path, depth + 1);
            if !outcome.success {
                return Ok(false);
            }
        }
        Ok(true)
    }

    fn execute_if_image_found(
        &mut self,
        action: &IfImageFoundAction,
        path: &[usize],
        depth: usize,
    ) -> Result<bool, RuntimeError> {
        self.ensure_composite_depth(depth + 1, "if_image_found")?;
        let matched = self.executor.evaluate_image_found(action, self.context)?;
        let branch = if matched {
            &action.then_actions
        } else {
            &action.else_actions
        };
        self.run_branch(branch, path, depth + 1)
    }

    fn execute_if_pixel_color(
        &mut self,
        action: &IfPixelColorAction,
        path: &[usize],
        depth: usize,
    ) -> Result<bool, RuntimeError> {
        self.ensure_composite_depth(depth + 1, "if_pixel_color")?;
        let matched = self.executor.evaluate_pixel_color(action, self.context)?;
        let branch = if matched {
            &action.then_actions
        } else {
            &action.else_actions
        };
        self.run_branch(branch, path, depth + 1)
    }

    fn execute_if_variable(
        &mut self,
        action: &IfVariableAction,
        path: &[usize],
        depth: usize,
    ) -> Result<bool, RuntimeError> {
        self.ensure_composite_depth(depth + 1, "if_variable")?;
        let var_name = self.context.interpolate(&action.var_name);
        let compare_value = self.context.interpolate(&action.compare_value);
        let current = self.context.get_var(&var_name);
        let matched = compare_values(current.as_ref(), &compare_value, &action.operator);
        let branch = if matched {
            &action.then_actions
        } else {
            &action.else_actions
        };
        self.run_branch(branch, path, depth + 1)
    }

    fn run_branch(
        &mut self,
        branch: &[Action],
        path: &[usize],
        depth: usize,
    ) -> Result<bool, RuntimeError> {
        for (child_index, child) in branch.iter().enumerate() {
            if !self.check_pause_or_stop() {
                return Ok(true);
            }

            let child_path = extend_path(path, child_index);
            self.emit(EngineEvent::NestedProgress {
                path: child_path.clone(),
                action_type: child.action_type().to_string(),
            });
            let outcome = self.run_action_with_policy(child, &child_path, depth);
            if !outcome.success {
                return Ok(false);
            }
        }

        Ok(true)
    }

    fn execute_set_variable(&mut self, action: &SetVariableAction) -> Result<bool, RuntimeError> {
        if action.var_name.trim().is_empty() {
            return Ok(true);
        }

        match action.operation.as_str() {
            "set" => {
                self.context
                    .set_var(&action.var_name, infer_scalar_value(&action.value));
            }
            "increment" => {
                let current = self
                    .context
                    .get_var(&action.var_name)
                    .as_ref()
                    .and_then(value_as_i64)
                    .unwrap_or(0);
                let step = action.value.trim().parse::<i64>().unwrap_or(1);
                self.context.set_var(&action.var_name, current + step);
            }
            "decrement" => {
                let current = self
                    .context
                    .get_var(&action.var_name)
                    .as_ref()
                    .and_then(value_as_i64)
                    .unwrap_or(0);
                let step = action.value.trim().parse::<i64>().unwrap_or(1);
                self.context.set_var(&action.var_name, current - step);
            }
            "add" => {
                apply_binary_float(self.context, &action.var_name, &action.value, |a, b| a + b);
            }
            "subtract" => {
                apply_binary_float(self.context, &action.var_name, &action.value, |a, b| a - b);
            }
            "multiply" => {
                apply_binary_float(self.context, &action.var_name, &action.value, |a, b| a * b);
            }
            "divide" => {
                apply_binary_float_checked(
                    self.context,
                    &action.var_name,
                    &action.value,
                    |a, b| (b != 0.0).then_some(a / b),
                );
            }
            "modulo" => {
                apply_binary_float_checked(
                    self.context,
                    &action.var_name,
                    &action.value,
                    |a, b| (b != 0.0).then_some(a % b),
                );
            }
            "concat" => {
                let current = self
                    .context
                    .get_var(&action.var_name)
                    .map(|value| value_to_string(&value))
                    .unwrap_or_default();
                let addition = self.context.interpolate(&action.value);
                self.context.set_var(
                    &action.var_name,
                    Value::String(format!("{current}{addition}")),
                );
            }
            "eval" => {
                let expr = self.context.interpolate(&action.value);
                if let Ok(result) = evaluate_numeric_expression(&expr) {
                    self.context.set_var(&action.var_name, result);
                }
            }
            other => {
                warn!("unknown set_variable operation `{other}`");
            }
        }

        Ok(true)
    }

    fn execute_split_string(&mut self, action: &SplitStringAction) -> Result<bool, RuntimeError> {
        let source = self
            .context
            .get_var(&action.source_var)
            .map(|value| value_to_string(&value))
            .unwrap_or_default();

        let parts = if action.delimiter == "," {
            parse_csv_row(&source).unwrap_or_else(|| {
                source
                    .split(&action.delimiter)
                    .map(ToString::to_string)
                    .collect()
            })
        } else {
            source
                .split(&action.delimiter)
                .map(ToString::to_string)
                .collect()
        };

        let result = parts
            .get(action.field_index)
            .map(|value| value.trim().to_string())
            .unwrap_or_default();
        self.context
            .set_var(&action.target_var, Value::String(result));
        Ok(true)
    }

    fn ensure_composite_depth(&self, depth: usize, action_type: &str) -> Result<(), RuntimeError> {
        if depth > self.options.max_composite_depth {
            return Err(RuntimeError::message(format!(
                "max composite depth {} exceeded in {}",
                self.options.max_composite_depth, action_type
            )));
        }
        Ok(())
    }

    fn check_pause_or_stop(&mut self) -> bool {
        self.drain_commands();
        while self.paused && !self.stopped {
            match self.commands {
                Some(commands) => match commands
                    .recv_timeout(Duration::from_millis(self.options.sleep_quantum_ms.max(1)))
                {
                    Ok(command) => self.handle_command(command),
                    Err(flume::RecvTimeoutError::Timeout) => {}
                    Err(flume::RecvTimeoutError::Disconnected) => break,
                },
                None => thread::sleep(Duration::from_millis(self.options.sleep_quantum_ms.max(1))),
            }
        }
        !self.stopped
    }

    fn interruptible_sleep(&mut self, duration: Duration) -> bool {
        if duration.is_zero() {
            return !self.stopped;
        }

        let quantum = Duration::from_millis(self.options.sleep_quantum_ms.max(1));
        let deadline = Instant::now() + duration;
        while Instant::now() < deadline {
            if !self.check_pause_or_stop() {
                return false;
            }

            let now = Instant::now();
            if now >= deadline {
                break;
            }
            let remaining = deadline.saturating_duration_since(now);
            thread::sleep(remaining.min(quantum));
        }
        !self.stopped
    }

    fn drain_commands(&mut self) {
        let Some(commands) = self.commands else {
            return;
        };
        while let Ok(command) = commands.try_recv() {
            self.handle_command(command);
        }
    }

    fn handle_command(&mut self, command: EngineCommand) {
        match command {
            EngineCommand::Pause => self.set_paused(true),
            EngineCommand::Resume | EngineCommand::StepNext => self.set_paused(false),
            EngineCommand::Stop => {
                self.stopped = true;
                self.paused = false;
            }
        }
    }

    fn set_paused(&mut self, paused: bool) {
        if self.paused == paused {
            return;
        }
        self.paused = paused;
        self.emit(if paused {
            EngineEvent::Paused
        } else {
            EngineEvent::Resumed
        });
    }

    fn scaled_duration(&self, duration: Duration) -> Duration {
        let factor = self.options.speed_factor.clamp(0.1, 10.0);
        if factor == 1.0 {
            return duration;
        }
        let millis = duration.as_secs_f64() * 1_000.0 / factor;
        Duration::from_millis(millis.max(0.0).round() as u64)
    }

    fn emit(&self, event: EngineEvent) {
        if let Some(events) = self.events {
            let _ = events.send(event);
        }
    }
}

fn parse_error_policy(raw: &str) -> ErrorPolicy {
    if raw == "skip" {
        return ErrorPolicy::Skip;
    }
    if let Some(value) = raw.strip_prefix("retry:") {
        return ErrorPolicy::Retry(value.parse::<usize>().unwrap_or(3).max(1));
    }
    ErrorPolicy::Stop
}

fn extend_path(path: &[usize], next: usize) -> Vec<usize> {
    let mut full = Vec::with_capacity(path.len() + 1);
    full.extend_from_slice(path);
    full.push(next);
    full
}

fn take_control_flag(context: &ExecutionContext, name: &str) -> bool {
    let active = context.get_var(name).as_ref().is_some_and(value_truthy);
    if active {
        context.set_var(name, false);
    }
    active
}

fn compare_values(current: Option<&Value>, compare_value: &str, operator: &str) -> bool {
    let lhs_numeric = current.and_then(value_as_f64);
    let rhs_numeric = compare_value.trim().parse::<f64>().ok();
    if let (Some(lhs), Some(rhs)) = (lhs_numeric, rhs_numeric) {
        return match operator {
            "==" => lhs == rhs,
            "!=" => lhs != rhs,
            ">" => lhs > rhs,
            "<" => lhs < rhs,
            ">=" => lhs >= rhs,
            "<=" => lhs <= rhs,
            _ => lhs == rhs,
        };
    }

    let lhs = current.map(value_to_string).unwrap_or_default();
    let rhs = compare_value.to_string();
    match operator {
        "==" => lhs == rhs,
        "!=" => lhs != rhs,
        ">" => lhs > rhs,
        "<" => lhs < rhs,
        ">=" => lhs >= rhs,
        "<=" => lhs <= rhs,
        _ => lhs == rhs,
    }
}

fn infer_scalar_value(value: &str) -> Value {
    let trimmed = value.trim();
    if let Ok(parsed) = trimmed.parse::<i64>() {
        return Value::Number(Number::from(parsed));
    }
    if let Ok(parsed) = trimmed.parse::<f64>() {
        if let Some(number) = Number::from_f64(parsed) {
            return Value::Number(number);
        }
    }
    Value::String(value.to_string())
}

fn apply_binary_float(
    context: &ExecutionContext,
    var_name: &str,
    rhs: &str,
    op: impl FnOnce(f64, f64) -> f64,
) {
    apply_binary_float_checked(context, var_name, rhs, |left, right| Some(op(left, right)));
}

fn apply_binary_float_checked(
    context: &ExecutionContext,
    var_name: &str,
    rhs: &str,
    op: impl FnOnce(f64, f64) -> Option<f64>,
) {
    let Some(current) = context.get_var(var_name).as_ref().and_then(value_as_f64) else {
        return;
    };
    let rhs = context.interpolate(rhs);
    let Ok(rhs) = rhs.trim().parse::<f64>() else {
        return;
    };
    let Some(result) = op(current, rhs) else {
        return;
    };
    if let Some(number) = Number::from_f64(result) {
        context.set_var(var_name, Value::Number(number));
    }
}

fn parse_csv_row(input: &str) -> Option<Vec<String>> {
    let mut reader = ReaderBuilder::new()
        .has_headers(false)
        .from_reader(input.as_bytes());
    let record = reader.records().next()?.ok()?;
    Some(record.iter().map(ToString::to_string).collect())
}

fn value_as_i64(value: &Value) -> Option<i64> {
    match value {
        Value::Number(number) => number
            .as_i64()
            .or_else(|| number.as_u64().and_then(|value| i64::try_from(value).ok()))
            .or_else(|| number.as_f64().map(|value| value as i64)),
        Value::String(value) => value
            .trim()
            .parse::<i64>()
            .ok()
            .or_else(|| value.trim().parse::<f64>().ok().map(|value| value as i64)),
        Value::Bool(value) => Some(i64::from(*value)),
        _ => None,
    }
}

fn value_as_f64(value: &Value) -> Option<f64> {
    match value {
        Value::Number(number) => number.as_f64(),
        Value::String(value) => value.trim().parse::<f64>().ok(),
        Value::Bool(value) => Some(if *value { 1.0 } else { 0.0 }),
        _ => None,
    }
}

fn value_truthy(value: &Value) -> bool {
    match value {
        Value::Null => false,
        Value::Bool(value) => *value,
        Value::Number(number) => number.as_f64().is_some_and(|value| value != 0.0),
        Value::String(value) => {
            let normalized = value.trim().to_ascii_lowercase();
            !normalized.is_empty() && normalized != "0" && normalized != "false"
        }
        Value::Array(values) => !values.is_empty(),
        Value::Object(values) => !values.is_empty(),
    }
}

fn value_to_string(value: &Value) -> String {
    match value {
        Value::Null => String::new(),
        Value::Bool(value) => value.to_string(),
        Value::Number(value) => value.to_string(),
        Value::String(value) => value.clone(),
        Value::Array(_) | Value::Object(_) => value.to_string(),
    }
}

fn evaluate_numeric_expression(expr: &str) -> Result<Value, RuntimeError> {
    let mut parser = ExprParser::new(expr);
    let value = parser.parse_expression()?;
    parser.skip_whitespace();
    if parser.peek().is_some() {
        return Err(RuntimeError::message(format!(
            "unexpected trailing input in expression `{expr}`"
        )));
    }
    number_to_value(value)
}

fn number_to_value(value: f64) -> Result<Value, RuntimeError> {
    Number::from_f64(value)
        .map(Value::Number)
        .ok_or_else(|| RuntimeError::message("expression produced non-finite value"))
}

struct ExprParser<'a> {
    chars: std::iter::Peekable<Chars<'a>>,
}

impl<'a> ExprParser<'a> {
    fn new(input: &'a str) -> Self {
        Self {
            chars: input.chars().peekable(),
        }
    }

    fn parse_expression(&mut self) -> Result<f64, RuntimeError> {
        self.parse_additive()
    }

    fn parse_additive(&mut self) -> Result<f64, RuntimeError> {
        let mut value = self.parse_multiplicative()?;
        loop {
            self.skip_whitespace();
            if self.consume('+') {
                value += self.parse_multiplicative()?;
            } else if self.consume('-') {
                value -= self.parse_multiplicative()?;
            } else {
                break;
            }
        }
        Ok(value)
    }

    fn parse_multiplicative(&mut self) -> Result<f64, RuntimeError> {
        let mut value = self.parse_power()?;
        loop {
            self.skip_whitespace();
            if self.consume_str("//") {
                let rhs = self.parse_power()?;
                if rhs == 0.0 {
                    return Err(RuntimeError::message("division by zero"));
                }
                value = (value / rhs).floor();
            } else if self.consume('*') {
                let rhs = self.parse_power()?;
                value *= rhs;
            } else if self.consume('/') {
                let rhs = self.parse_power()?;
                if rhs == 0.0 {
                    return Err(RuntimeError::message("division by zero"));
                }
                value /= rhs;
            } else if self.consume('%') {
                let rhs = self.parse_power()?;
                if rhs == 0.0 {
                    return Err(RuntimeError::message("modulo by zero"));
                }
                value %= rhs;
            } else {
                break;
            }
        }
        Ok(value)
    }

    fn parse_power(&mut self) -> Result<f64, RuntimeError> {
        let base = self.parse_unary()?;
        self.skip_whitespace();
        if self.consume_str("**") {
            let exponent = self.parse_power()?;
            if exponent.abs() > 1_000.0 {
                return Err(RuntimeError::message("exponent too large"));
            }
            Ok(base.powf(exponent))
        } else {
            Ok(base)
        }
    }

    fn parse_unary(&mut self) -> Result<f64, RuntimeError> {
        self.skip_whitespace();
        if self.consume('+') {
            return self.parse_unary();
        }
        if self.consume('-') {
            return Ok(-self.parse_unary()?);
        }
        self.parse_primary()
    }

    fn parse_primary(&mut self) -> Result<f64, RuntimeError> {
        self.skip_whitespace();
        if self.consume('(') {
            let value = self.parse_expression()?;
            self.skip_whitespace();
            if !self.consume(')') {
                return Err(RuntimeError::message("missing closing parenthesis"));
            }
            return Ok(value);
        }

        self.parse_number()
    }

    fn parse_number(&mut self) -> Result<f64, RuntimeError> {
        self.skip_whitespace();
        let mut buffer = String::new();
        while let Some(ch) = self.peek() {
            if ch.is_ascii_digit() || ch == '.' {
                buffer.push(ch);
                self.chars.next();
            } else {
                break;
            }
        }

        if buffer.is_empty() {
            return Err(RuntimeError::message("expected number"));
        }

        buffer
            .parse::<f64>()
            .map_err(|_| RuntimeError::message(format!("invalid number `{buffer}`")))
    }

    fn skip_whitespace(&mut self) {
        while matches!(self.peek(), Some(ch) if ch.is_whitespace()) {
            self.chars.next();
        }
    }

    fn peek(&mut self) -> Option<char> {
        self.chars.peek().copied()
    }

    fn consume(&mut self, ch: char) -> bool {
        if self.peek() == Some(ch) {
            self.chars.next();
            true
        } else {
            false
        }
    }

    fn consume_str(&mut self, expected: &str) -> bool {
        let mut clone = self.chars.clone();
        for ch in expected.chars() {
            if clone.next() != Some(ch) {
                return false;
            }
        }
        self.chars = clone;
        true
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use amk_domain::action::{
        CommonActionData, KeyPressAction, MouseClickAction, SetVariableAction, SplitStringAction,
    };
    use serde_json::json;

    #[derive(Default)]
    struct NoopExecutor {
        calls: usize,
        fail_next: usize,
    }

    impl ActionExecutor for NoopExecutor {
        fn execute_atomic(
            &mut self,
            _action: &Action,
            _context: &ExecutionContext,
        ) -> Result<bool, RuntimeError> {
            self.calls += 1;
            if self.fail_next > 0 {
                self.fail_next -= 1;
                return Ok(false);
            }
            Ok(true)
        }
    }

    fn delay_action() -> Action {
        Action {
            common: CommonActionData::default(),
            kind: ActionKind::Delay(DelayAction {
                duration_ms: 0,
                dynamic_ms: None,
            }),
        }
    }

    #[test]
    fn counts_successful_actions() {
        let context = ExecutionContext::new();
        let mut executor = NoopExecutor::default();
        let report =
            run_actions(&[delay_action()], &context, &mut executor, None).expect("run succeeds");
        assert_eq!(report.success, 1);
        assert_eq!(report.total, 1);
    }

    #[test]
    fn evaluates_if_variable_then_branch() {
        let actions = [
            Action {
                common: CommonActionData::default(),
                kind: ActionKind::SetVariable(SetVariableAction {
                    var_name: "count".to_string(),
                    value: "2".to_string(),
                    operation: "set".to_string(),
                }),
            },
            Action {
                common: CommonActionData::default(),
                kind: ActionKind::IfVariable(IfVariableAction {
                    var_name: "count".to_string(),
                    operator: ">=".to_string(),
                    compare_value: "2".to_string(),
                    then_actions: vec![Action {
                        common: CommonActionData::default(),
                        kind: ActionKind::SetVariable(SetVariableAction {
                            var_name: "result".to_string(),
                            value: "done".to_string(),
                            operation: "set".to_string(),
                        }),
                    }],
                    else_actions: Vec::new(),
                }),
            },
        ];

        let context = ExecutionContext::new();
        let mut executor = NoopExecutor::default();
        let report = run_actions(&actions, &context, &mut executor, None).expect("run succeeds");
        assert_eq!(report.success, 2);
        assert_eq!(context.get_var("result"), Some(json!("done")));
    }

    #[test]
    fn retries_atomic_action_using_retry_policy() {
        let action = Action {
            common: CommonActionData {
                on_error: "retry:1".to_string(),
                ..CommonActionData::default()
            },
            kind: ActionKind::MouseClick(MouseClickAction::default()),
        };

        let context = ExecutionContext::new();
        let mut executor = NoopExecutor {
            fail_next: 1,
            ..NoopExecutor::default()
        };
        let options = RuntimeOptions {
            retry_delay_ms: 0,
            ..RuntimeOptions::default()
        };
        let report =
            run_actions_with_options(&[action], &context, &mut executor, &options, None, None)
                .expect("run succeeds");

        assert_eq!(report.success, 1);
        assert_eq!(executor.calls, 2);
    }

    #[test]
    fn continues_after_failure_when_stop_on_error_is_disabled() {
        let first = Action {
            common: CommonActionData::default(),
            kind: ActionKind::MouseClick(MouseClickAction::default()),
        };
        let second = Action {
            common: CommonActionData::default(),
            kind: ActionKind::KeyPress(KeyPressAction {
                key: "A".to_string(),
            }),
        };

        let context = ExecutionContext::new();
        let mut executor = NoopExecutor {
            fail_next: 1,
            ..NoopExecutor::default()
        };
        let report =
            run_actions(&[first, second], &context, &mut executor, None).expect("run succeeds");
        assert_eq!(report.failed, 1);
        assert_eq!(report.success, 1);
        assert_eq!(executor.calls, 2);
    }

    #[test]
    fn executes_loop_block_children() {
        let loop_action = Action {
            common: CommonActionData::default(),
            kind: ActionKind::LoopBlock(LoopBlockAction {
                iterations: 3,
                sub_actions: vec![Action {
                    common: CommonActionData::default(),
                    kind: ActionKind::SetVariable(SetVariableAction {
                        var_name: "counter".to_string(),
                        value: "1".to_string(),
                        operation: "increment".to_string(),
                    }),
                }],
            }),
        };

        let context = ExecutionContext::new();
        let mut executor = NoopExecutor::default();
        let report =
            run_actions(&[loop_action], &context, &mut executor, None).expect("run succeeds");
        assert_eq!(report.success, 1);
        assert_eq!(context.get_var("counter"), Some(json!(3)));
    }

    #[test]
    fn splits_csv_fields_into_target_variable() {
        let actions = [
            Action {
                common: CommonActionData::default(),
                kind: ActionKind::SetVariable(SetVariableAction {
                    var_name: "csv".to_string(),
                    value: "alpha,\"beta,gamma\",delta".to_string(),
                    operation: "set".to_string(),
                }),
            },
            Action {
                common: CommonActionData::default(),
                kind: ActionKind::SplitString(SplitStringAction {
                    source_var: "csv".to_string(),
                    delimiter: ",".to_string(),
                    field_index: 1,
                    target_var: "item".to_string(),
                }),
            },
        ];

        let context = ExecutionContext::new();
        let mut executor = NoopExecutor::default();
        let report = run_actions(&actions, &context, &mut executor, None).expect("run succeeds");

        assert_eq!(report.success, 2);
        assert_eq!(context.get_var("item"), Some(json!("beta,gamma")));
    }

    #[test]
    fn evaluates_numeric_set_variable_expression() {
        let action = Action {
            common: CommonActionData::default(),
            kind: ActionKind::SetVariable(SetVariableAction {
                var_name: "result".to_string(),
                value: "(10+5)*2".to_string(),
                operation: "eval".to_string(),
            }),
        };

        let context = ExecutionContext::new();
        let mut executor = NoopExecutor::default();
        let report = run_actions(&[action], &context, &mut executor, None).expect("run succeeds");

        assert_eq!(report.success, 1);
        assert_eq!(context.get_var("result"), Some(json!(30.0)));
    }
}
