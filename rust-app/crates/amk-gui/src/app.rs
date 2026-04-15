//! Main application state and lifecycle.

use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, AtomicU8, Ordering};
use std::sync::Arc;

use eframe::egui;

use amk_domain::action::TypedAction;
use amk_domain::convert_actions;
use amk_runtime::engine::{EngineState, MacroEngine};
use amk_runtime::report::PlaybackReport;
use amk_schema::{MacroDocument, parse_macro};

use crate::{panels, theme};

// ── State ────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RunState {
    Idle,
    Running,
    Paused,
}

/// Entry in the macro file list.
#[derive(Clone)]
pub struct MacroEntry {
    pub name: String,
    pub path: String,
    pub action_count: usize,
}

/// Main application state.
pub struct AutoMacroApp {
    // ── Macro data ──
    pub current_macro: Option<MacroDocument>,
    pub typed_actions: Vec<TypedAction>,
    pub macro_entries: Vec<MacroEntry>,
    pub selected_macro_idx: Option<usize>,
    pub macros_dir: PathBuf,
    /// Path to the currently loaded macro file (for Save).
    pub current_file_path: Option<String>,
    /// Whether unsaved changes exist.
    pub dirty: bool,

    // ── Run state ──
    pub run_state: RunState,
    pub loop_count: u32,
    pub speed_factor: f64,
    pub engine_state: Arc<AtomicU8>,
    pub stop_flag: Arc<AtomicBool>,
    pub last_report: Option<PlaybackReport>,
    pub status_message: String,

    // ── Action editing ──
    pub selected_action_idx: Option<usize>,
    pub selected_actions: std::collections::BTreeSet<usize>,
    pub editing_action_idx: Option<usize>,
    pub editing_backup: Option<amk_schema::RawAction>,
    pub show_add_action_menu: bool,
    pub show_confirm_delete: bool,

    // ── Undo/Redo ──
    pub undo_stack: Vec<Vec<amk_schema::RawAction>>,
    pub redo_stack: Vec<Vec<amk_schema::RawAction>>,

    // ── Settings ──
    pub show_settings: bool,
    pub settings_tab: usize,
    pub default_delay: u32,
    pub stop_on_error: bool,
    pub loop_delay: u32,
    pub hotkey_start_stop: String,
    pub hotkey_pause: String,
    pub hotkey_emergency: String,
    pub hotkey_record: String,
    pub max_fps: u32,
    pub autosave_interval_secs: u32,

    // ── Help ──
    pub help_state: panels::help::HelpState,

    // ── Clipboard ──
    pub copied_actions: Vec<amk_schema::RawAction>,

    // ── Log ──
    pub log_messages: Vec<String>,

    // ── UI state ──
    pub right_tab: usize,
    pub action_filter: String,
    pub show_context_menu: bool,
    pub context_menu_pos: egui::Pos2,
    pub recent_files: Vec<String>,
    pub last_autosave: std::time::Instant,
    pub show_about: bool,
    pub macro_filter: String,
    pub add_action_filter: String,
    actions_hash: u64,
    pub coord_picker: panels::coord_picker::CoordPickerState,
    pub show_optimizer: bool,
    pub recording: panels::recording::RecordingState,
    pub show_recording: bool,
    pub screenshot: panels::screenshot::ScreenshotState,
    pub multi_run: panels::multi_run::MultiRunState,
    pub scheduler: panels::scheduler::SchedulerState,
    pub debugger: panels::debugger::DebuggerState,
    pub export: panels::export::ExportState,
    pub theme_mode: theme::ThemeMode,
    pub(crate) theme_applied: bool,
    run_thread: Option<std::thread::JoinHandle<()>>,
}

impl AutoMacroApp {
    pub fn new(_cc: &eframe::CreationContext<'_>) -> Self {
        // Find macros directory
        let macros_dir = find_macros_dir();

        let mut app = Self {
            current_macro: None,
            typed_actions: Vec::new(),
            macro_entries: Vec::new(),
            selected_macro_idx: None,
            macros_dir,
            current_file_path: None,
            dirty: false,
            run_state: RunState::Idle,
            loop_count: 1,
            speed_factor: 1.0,
            engine_state: Arc::new(AtomicU8::new(EngineState::Idle as u8)),
            stop_flag: Arc::new(AtomicBool::new(false)),
            last_report: None,
            status_message: String::new(),
            selected_action_idx: None,
            selected_actions: std::collections::BTreeSet::new(),
            editing_action_idx: None,
            editing_backup: None,
            show_add_action_menu: false,
            show_confirm_delete: false,
            undo_stack: Vec::new(),
            redo_stack: Vec::new(),
            show_settings: false,
            settings_tab: 0,
            default_delay: 0,
            stop_on_error: false,
            loop_delay: 0,
            hotkey_start_stop: "F6".into(),
            hotkey_pause: "F7".into(),
            hotkey_emergency: "F8".into(),
            hotkey_record: "F9".into(),
            max_fps: 30,
            autosave_interval_secs: 60,
            help_state: Default::default(),
            copied_actions: Vec::new(),
            log_messages: Vec::new(),
            right_tab: 0,
            action_filter: String::new(),
            show_context_menu: false,
            context_menu_pos: egui::Pos2::ZERO,
            recent_files: Vec::new(),
            last_autosave: std::time::Instant::now(),
            show_about: false,
            macro_filter: String::new(),
            add_action_filter: String::new(),
            actions_hash: 0,
            coord_picker: Default::default(),
            show_optimizer: false,
            recording: Default::default(),
            show_recording: false,
            screenshot: Default::default(),
            multi_run: Default::default(),
            scheduler: Default::default(),
            debugger: Default::default(),
            export: Default::default(),
            theme_mode: theme::ThemeMode::Dark,
            theme_applied: false,
            run_thread: None,
        };

        app.refresh_macro_list();

        // R1: Load config.json for hotkeys/defaults/recent_files
        app.load_config();

        app
    }

    /// Load config from config.json (hotkeys, defaults, recent files).
    fn load_config(&mut self) {
        let config_path = self.macros_dir.parent().unwrap_or(&self.macros_dir).join("config.json");
        if let Ok(content) = std::fs::read_to_string(&config_path) {
            if let Ok(config) = amk_schema::parse_config(&content) {
                // Hotkeys
                self.hotkey_start_stop = config.hotkeys.start_stop;
                self.hotkey_pause = config.hotkeys.pause_resume;
                self.hotkey_emergency = config.hotkeys.emergency_stop;
                self.hotkey_record = config.hotkeys.record;
                // Defaults
                self.default_delay = config.defaults.click_delay;
                self.speed_factor = config.defaults.speed_factor;
                self.stop_on_error = !config.defaults.failsafe_enabled;
                // UI
                self.theme_mode = match config.ui.theme.as_str() {
                    "light" => theme::ThemeMode::Light,
                    _ => theme::ThemeMode::Dark,
                };
                self.theme_applied = false; // force re-apply
                // Performance
                self.max_fps = config.performance.max_fps;
                self.autosave_interval_secs = config.performance.autosave_interval_secs;
                // Recent files
                self.recent_files = config.recent_files;
                self.log_event("Config loaded".into());
            }
        }
    }

    /// Save current config to config.json.
    pub fn save_config(&self) {
        let config = amk_schema::AppConfig {
            hotkeys: amk_schema::HotkeyConfig {
                start_stop: self.hotkey_start_stop.clone(),
                pause_resume: self.hotkey_pause.clone(),
                emergency_stop: self.hotkey_emergency.clone(),
                record: self.hotkey_record.clone(),
            },
            defaults: amk_schema::DefaultsConfig {
                click_delay: self.default_delay,
                typing_speed: 50,
                image_confidence: 0.8,
                failsafe_enabled: !self.stop_on_error,
                speed_factor: self.speed_factor,
            },
            ui: amk_schema::UiConfig {
                theme: match self.theme_mode {
                    theme::ThemeMode::Light => "light".into(),
                    theme::ThemeMode::Dark => "dark".into(),
                },
                ..Default::default()
            },
            performance: amk_schema::PerformanceConfig {
                max_fps: self.max_fps,
                autosave_interval_secs: self.autosave_interval_secs,
                ..Default::default()
            },
            recent_files: self.recent_files.clone(),
        };
        let config_path = self.macros_dir.parent().unwrap_or(&self.macros_dir).join("config.json");
        if let Ok(json) = serde_json::to_string_pretty(&config) {
            let _ = std::fs::write(&config_path, json);
        }
    }

    // ── Macro loading ────────────────────────────────────

    pub fn load_macro_file(&mut self, path: &str) {
        match std::fs::read_to_string(path) {
            Ok(content) => match parse_macro(&content) {
                Ok(doc) => {
                    let msg;
                    match convert_actions(&doc.actions) {
                        Ok(typed) => {
                            msg = format!("Loaded: {} ({} actions)", doc.name, typed.len());
                            self.typed_actions = typed;
                            self.current_macro = Some(doc);
                            self.current_file_path = Some(path.to_string());
                            self.dirty = false;
                            self.selected_action_idx = None;
                        }
                        Err(e) => {
                            msg = format!("Convert error: {e}");
                            self.typed_actions.clear();
                            self.current_macro = Some(doc);
                            self.current_file_path = Some(path.to_string());
                        }
                    }
                    self.undo_stack.clear();
                    self.redo_stack.clear();
                    self.add_recent_file(path);
                    self.log_event(msg);
                }
                Err(e) => {
                    self.log_event(format!("Parse error: {e}"));
                }
            },
            Err(e) => {
                self.log_event(format!("Read error: {e}"));
            }
        }
    }

    /// Track recently opened files (max 10).
    pub fn add_recent_file(&mut self, path: &str) {
        let p = path.to_string();
        self.recent_files.retain(|f| f != &p);
        self.recent_files.insert(0, p);
        if self.recent_files.len() > 10 {
            self.recent_files.truncate(10);
        }
    }

    /// Autosave if dirty and configurable interval elapsed.
    pub fn autosave_if_needed(&mut self) {
        if !self.dirty { return; }
        if self.last_autosave.elapsed().as_secs() < self.autosave_interval_secs as u64 { return; }
        if let Some(ref path) = self.current_file_path.clone() {
            self.save_macro_to(path);
            self.last_autosave = std::time::Instant::now();
            self.log_event("Auto-saved".into());
        }
    }

    /// Insert a template macro (pre-built snippet).
    pub fn insert_template(&mut self, name: &str) {
        self.push_undo();
        let actions: Vec<amk_schema::RawAction> = match name {
            "click_sequence" => vec![
                make_raw("mouse_click", &[("x", "100"), ("y", "200"), ("button", "left")]),
                make_raw("delay", &[("duration_ms", "500")]),
                make_raw("mouse_click", &[("x", "300"), ("y", "400"), ("button", "left")]),
            ],
            "type_and_enter" => vec![
                make_raw("type_text", &[("text", "Hello World"), ("interval_ms", "30")]),
                make_raw("delay", &[("duration_ms", "200")]),
                make_raw("key_press", &[("key", "enter")]),
            ],
            "login_flow" => vec![
                make_raw("comment", &[("text", "── Login Flow ──")]),
                make_raw("mouse_click", &[("x", "500"), ("y", "300"), ("button", "left")]),
                make_raw("type_text", &[("text", "username"), ("interval_ms", "30")]),
                make_raw("key_press", &[("key", "tab")]),
                make_raw("type_text", &[("text", "password"), ("interval_ms", "30")]),
                make_raw("key_press", &[("key", "enter")]),
                make_raw("delay", &[("duration_ms", "2000")]),
            ],
            "loop_clicks" => vec![
                make_raw("comment", &[("text", "── Repeat clicks ──")]),
                make_raw("mouse_click", &[("x", "400"), ("y", "300"), ("button", "left")]),
                make_raw("delay", &[("duration_ms", "1000")]),
            ],
            "screenshot_log" => vec![
                make_raw("take_screenshot", &[("file_path", "screenshot.png")]),
                make_raw("log_to_file", &[("file_path", "log.txt"), ("message", "Screenshot taken"), ("append", "true")]),
            ],
            _ => return,
        };

        if let Some(ref mut doc) = self.current_macro {
            let insert_idx = self.selected_action_idx
                .map(|i| i + 1)
                .unwrap_or(doc.actions.len());
            for (offset, action) in actions.into_iter().enumerate() {
                let pos = (insert_idx + offset).min(doc.actions.len());
                doc.actions.insert(pos, action);
            }
            self.dirty = true;
        } else {
            // Create new macro with template
            let doc = amk_schema::MacroDocument {
                name: name.replace('_', " "),
                actions,
                ..Default::default()
            };
            self.current_macro = Some(doc);
        }
        self.recompile_actions();
        self.log_event(format!("Inserted template: {}", name.replace('_', " ")));
    }

    // ── Editing ──────────────────────────────────

    /// Add action from type name + params JSON (used by recording module).
    pub fn add_action_with_params(&mut self, kind: &str, params: serde_json::Value) {
        let raw = amk_schema::RawAction {
            action_type: kind.into(),
            params,
            enabled: true,
            description: String::new(),
            delay_after: 0,
            repeat_count: 1,
            on_error: Default::default(),
            color: None,
            bookmarked: false,
            sub_actions: Vec::new(),
            else_actions: Vec::new(),
        };
        if let Some(ref mut doc) = self.current_macro {
            doc.actions.push(raw);
        }
    }


    /// Snapshot current actions for undo before mutation.
    pub fn push_undo(&mut self) {
        if let Some(ref doc) = self.current_macro {
            self.undo_stack.push(doc.actions.clone());
            self.redo_stack.clear(); // new edit invalidates redo
            // Cap at 50 history entries
            if self.undo_stack.len() > 50 {
                self.undo_stack.remove(0);
            }
        }
    }

    /// Undo last action edit.
    pub fn undo(&mut self) {
        if let Some(snapshot) = self.undo_stack.pop() {
            if let Some(ref mut doc) = self.current_macro {
                // Save current state for redo
                self.redo_stack.push(doc.actions.clone());
                doc.actions = snapshot;
            }
            self.recompile_actions();
            self.dirty = true;
            self.status_message = format!("Undo ({})", self.undo_stack.len());
        }
    }

    /// Redo last undone edit.
    pub fn redo(&mut self) {
        if let Some(snapshot) = self.redo_stack.pop() {
            if let Some(ref mut doc) = self.current_macro {
                // Save current state for undo
                self.undo_stack.push(doc.actions.clone());
                doc.actions = snapshot;
            }
            self.recompile_actions();
            self.dirty = true;
            self.log_event(format!("Redo ({})", self.redo_stack.len()));
        }
    }

    /// Create a new empty macro.
    pub fn new_macro(&mut self) {
        use amk_schema::MacroDocument;
        self.current_macro = Some(MacroDocument::default());
        self.typed_actions.clear();
        self.current_file_path = None;
        self.dirty = false;
        self.selected_action_idx = None;
        self.undo_stack.clear();
        self.redo_stack.clear();
        self.log_event("New macro created".into());
    }

    /// Save the current macro to its file path.
    pub fn save_macro(&mut self) {
        if let Some(ref path) = self.current_file_path.clone() {
            self.save_macro_to(path);
        } else {
            self.save_macro_as();
        }
    }

    /// Save As — open file dialog then save.
    pub fn save_macro_as(&mut self) {
        if let Some(path) = rfd::FileDialog::new()
            .set_title("Save Macro As")
            .add_filter("AutoMacro JSON", &["json"])
            .set_directory(&self.macros_dir)
            .save_file()
        {
            let path_str = path.to_string_lossy().to_string();
            self.save_macro_to(&path_str);
            self.current_file_path = Some(path_str);
        }
    }

    /// Open macro from file dialog (Ctrl+O).
    pub fn open_macro_dialog(&mut self) {
        if let Some(path) = rfd::FileDialog::new()
            .set_title("Open Macro")
            .add_filter("AutoMacro JSON", &["json"])
            .set_directory(&self.macros_dir)
            .pick_file()
        {
            let path_str = path.to_string_lossy().to_string();
            self.load_macro_file(&path_str);
        }
    }

    fn save_macro_to(&mut self, path: &str) {
        if let Some(ref doc) = self.current_macro {
            match amk_schema::save_macro(std::path::Path::new(path), doc) {
                Ok(()) => {
                    self.dirty = false;
                    self.log_event(format!("Saved: {}", path));
                    self.refresh_macro_list();
                }
                Err(e) => {
                    self.log_event(format!("Save error: {e}"));
                }
            }
        }
    }

    /// Re-convert raw actions → typed actions after editing.
    /// Uses a hash to skip recompile when actions haven't changed.
    pub fn recompile_actions(&mut self) {
        if let Some(ref doc) = self.current_macro {
            // Fast hash check: skip if raw actions are identical
            use std::hash::{Hash, Hasher};
            let mut hasher = std::collections::hash_map::DefaultHasher::new();
            // Hash the serialized form for cheap comparison
            if let Ok(json) = serde_json::to_string(&doc.actions) {
                json.hash(&mut hasher);
            }
            let new_hash = hasher.finish();
            if new_hash == self.actions_hash {
                return; // no change
            }
            self.actions_hash = new_hash;

            match convert_actions(&doc.actions) {
                Ok(typed) => {
                    self.typed_actions = typed;
                }
                Err(e) => {
                    self.status_message = format!("Convert error: {e}");
                }
            }
        }
    }

    /// Delete the selected action.
    pub fn delete_selected_action(&mut self) {
        // Multi-select delete: collect all indices to remove
        let indices: Vec<usize> = if self.selected_actions.len() > 1 {
            self.selected_actions.iter().copied().collect()
        } else if let Some(idx) = self.selected_action_idx {
            vec![idx]
        } else {
            return;
        };

        self.push_undo();
        let mut count = 0;
        if let Some(ref mut doc) = self.current_macro {
            // Remove in reverse order to preserve indices
            for &idx in indices.iter().rev() {
                if idx < doc.actions.len() {
                    doc.actions.remove(idx);
                    count += 1;
                }
            }
            // Adjust selection
            if doc.actions.is_empty() {
                self.selected_action_idx = None;
            } else {
                let new_idx = indices.iter().copied().min().unwrap_or(0);
                self.selected_action_idx = Some(new_idx.min(doc.actions.len().saturating_sub(1)));
            }
        }
        if count > 0 {
            self.selected_actions.clear();
            if let Some(idx) = self.selected_action_idx {
                self.selected_actions.insert(idx);
            }
            self.dirty = true;
            self.recompile_actions();
            if count == 1 {
                self.log_event(format!("Deleted action #{}", indices[0] + 1));
            } else {
                self.log_event(format!("Deleted {} actions", count));
            }
        }
    }

    /// Toggle enable/disable for the selected action.
    pub fn toggle_selected_action(&mut self) {
        self.push_undo();
        let indices: Vec<usize> = if self.selected_actions.len() > 1 {
            self.selected_actions.iter().copied().collect()
        } else if let Some(idx) = self.selected_action_idx {
            vec![idx]
        } else {
            return;
        };

        let mut count = 0;
        if let Some(ref mut doc) = self.current_macro {
            for &idx in &indices {
                if idx < doc.actions.len() {
                    doc.actions[idx].enabled = !doc.actions[idx].enabled;
                    count += 1;
                }
            }
        }
        if count > 0 {
            self.dirty = true;
            self.recompile_actions();
            if count == 1 {
                self.log_event(format!("Toggled action #{}", indices[0] + 1));
            } else {
                self.log_event(format!("Toggled {} actions", count));
            }
        }
    }

    /// Move selected action up.
    pub fn move_action_up(&mut self) {
        self.push_undo();
        let moved = if let Some(idx) = self.selected_action_idx {
            if idx > 0 {
                if let Some(ref mut doc) = self.current_macro {
                    doc.actions.swap(idx, idx - 1);
                    self.selected_action_idx = Some(idx - 1);
                    true
                } else { false }
            } else { false }
        } else { false };
        if moved {
            self.dirty = true;
            self.recompile_actions();
        }
    }

    /// Move selected action down.
    pub fn move_action_down(&mut self) {
        self.push_undo();
        let moved = if let Some(idx) = self.selected_action_idx {
            if let Some(ref mut doc) = self.current_macro {
                if idx + 1 < doc.actions.len() {
                    doc.actions.swap(idx, idx + 1);
                    self.selected_action_idx = Some(idx + 1);
                    true
                } else { false }
            } else { false }
        } else { false };
        if moved {
            self.dirty = true;
            self.recompile_actions();
        }
    }

    /// Add a new raw action of the given type.
    pub fn add_action(&mut self, action_type: &str) {
        self.push_undo();
        use amk_schema::RawAction;
        let insert_idx = self.selected_action_idx
            .map(|i| i + 1)
            .unwrap_or_else(|| {
                self.current_macro.as_ref().map_or(0, |d| d.actions.len())
            });

        let raw = RawAction {
            action_type: action_type.to_string(),
            params: default_params_for(action_type),
            delay_after: 0,
            repeat_count: 1,
            description: String::new(),
            enabled: true,
            on_error: Default::default(),
            color: None,
            bookmarked: false,
            sub_actions: vec![],
            else_actions: vec![],
        };

        // Ensure we have a document
        if self.current_macro.is_none() {
            self.new_macro();
        }

        if let Some(ref mut doc) = self.current_macro {
            doc.actions.insert(insert_idx, raw);
        }
        self.dirty = true;
        self.recompile_actions();
        self.selected_action_idx = Some(insert_idx);
        self.log_event(format!("Added: {action_type}"));
    }

    /// Duplicate selected action.
    pub fn duplicate_selected_action(&mut self) {
        self.push_undo();
        let duped = if let Some(idx) = self.selected_action_idx {
            if let Some(ref mut doc) = self.current_macro {
                if idx < doc.actions.len() {
                    let clone = doc.actions[idx].clone();
                    doc.actions.insert(idx + 1, clone);
                    self.selected_action_idx = Some(idx + 1);
                    Some(idx)
                } else { None }
            } else { None }
        } else { None };
        if let Some(idx) = duped {
            self.dirty = true;
            self.recompile_actions();
            self.log_event(format!("Duplicated action #{}", idx + 1));
        }
    }

    /// Open the action editor for the selected action.
    pub fn edit_selected_action(&mut self) {
        if let Some(idx) = self.selected_action_idx {
            if let Some(ref doc) = self.current_macro {
                if idx < doc.actions.len() {
                    self.editing_backup = Some(doc.actions[idx].clone());
                    self.editing_action_idx = Some(idx);
                }
            }
        }
    }

    /// Copy selected action(s) to clipboard (internal + system JSON).
    pub fn copy_selected_action(&mut self) {
        let indices: Vec<usize> = if self.selected_actions.len() > 1 {
            self.selected_actions.iter().copied().collect()
        } else if let Some(idx) = self.selected_action_idx {
            vec![idx]
        } else {
            return;
        };

        if let Some(ref doc) = self.current_macro {
            let actions: Vec<_> = indices.iter()
                .filter(|&&i| i < doc.actions.len())
                .map(|&i| doc.actions[i].clone())
                .collect();
            if actions.is_empty() { return; }

            // Also copy to system clipboard as JSON for sharing
            if let Ok(json) = serde_json::to_string_pretty(&actions) {
                let _ = arboard::Clipboard::new().and_then(|mut cb| cb.set_text(json));
            }

            let n = actions.len();
            self.copied_actions = actions;
            self.log_event(format!("Copied {} action(s) to clipboard", n));
        }
    }

    /// Paste clipboard actions after selection.
    pub fn paste_actions(&mut self) {
        if self.copied_actions.is_empty() { return; }
        self.push_undo();
        let insert_idx = self.selected_action_idx
            .map(|i| i + 1)
            .unwrap_or(0);
        if let Some(ref mut doc) = self.current_macro {
            for (offset, action) in self.copied_actions.clone().into_iter().enumerate() {
                let pos = (insert_idx + offset).min(doc.actions.len());
                doc.actions.insert(pos, action);
            }
            self.selected_action_idx = Some(insert_idx);
            self.dirty = true;
        }
        let n = self.copied_actions.len();
        self.recompile_actions();
        self.log_event(format!("Pasted {} action(s)", n));
    }

    /// Add a timestamped log message.
    pub fn log_event(&mut self, msg: String) {
        let now = chrono::Local::now().format("%H:%M:%S");
        self.log_messages.push(format!("[{now}] {msg}"));
        self.status_message = msg;
        // Cap at 500 log entries
        if self.log_messages.len() > 500 {
            self.log_messages.drain(0..100);
        }
    }

    /// Enable all actions.
    pub fn enable_all_actions(&mut self) {
        self.push_undo();
        if let Some(ref mut doc) = self.current_macro {
            for a in &mut doc.actions { a.enabled = true; }
        }
        self.dirty = true;
        self.recompile_actions();
        self.log_event("Enabled all actions".into());
    }

    /// Disable all actions.
    pub fn disable_all_actions(&mut self) {
        self.push_undo();
        if let Some(ref mut doc) = self.current_macro {
            for a in &mut doc.actions { a.enabled = false; }
        }
        self.dirty = true;
        self.recompile_actions();
        self.log_event("Disabled all actions".into());
    }
    pub fn refresh_macro_list(&mut self) {
        self.macro_entries.clear();

        if let Ok(entries) = std::fs::read_dir(&self.macros_dir) {
            let mut items: Vec<_> = entries
                .filter_map(Result::ok)
                .filter(|e| {
                    e.path().extension().is_some_and(|ext| ext == "json")
                        && e.file_name().to_string_lossy() != ".triggers.json"
                })
                .collect();

            items.sort_by_key(|e| e.file_name());

            for entry in items {
                let path_str = entry.path().to_string_lossy().to_string();
                let name = match std::fs::read_to_string(entry.path()) {
                    Ok(content) => parse_macro(&content)
                        .map(|doc| (doc.name.clone(), doc.actions.len()))
                        .unwrap_or_else(|_| (entry.file_name().to_string_lossy().to_string(), 0)),
                    Err(_) => (entry.file_name().to_string_lossy().to_string(), 0),
                };

                self.macro_entries.push(MacroEntry {
                    name: name.0,
                    path: path_str,
                    action_count: name.1,
                });
            }
        }

        self.status_message = format!("Found {} macros in {:?}", self.macro_entries.len(), self.macros_dir);
    }

    // ── Run controls ─────────────────────────────────────

    pub fn start_run(&mut self) {
        if self.typed_actions.is_empty() {
            self.log_event("No actions to run".into());
            return;
        }

        self.run_state = RunState::Running;
        self.stop_flag.store(false, Ordering::Release);
        self.log_event(format!("Running {} actions ({}× speed {:.1}×)", self.typed_actions.len(), if self.loop_count == 0 { "∞".into() } else { format!("{}", self.loop_count) }, self.speed_factor));

        let actions = self.typed_actions.clone();
        let loops = self.loop_count;
        let speed = self.speed_factor;
        let loop_delay = self.loop_delay;
        let engine_state = Arc::clone(&self.engine_state);
        let stop_flag = Arc::clone(&self.stop_flag);

        // Run in background thread with panic recovery
        let handle = std::thread::Builder::new()
            .name("amk-macro-runner".into())
            .spawn(move || {
                let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                    let mut engine = MacroEngine::new();
                    engine.set_speed(speed);
                    let mut executor = amk_platform::Win32Executor::with_flag(Arc::clone(&stop_flag));
                    let _report = engine.run(&actions, loops, loop_delay, &mut executor);
                }));

                if let Err(panic_info) = result {
                    let msg = if let Some(s) = panic_info.downcast_ref::<&str>() {
                        s.to_string()
                    } else if let Some(s) = panic_info.downcast_ref::<String>() {
                        s.clone()
                    } else {
                        "Unknown panic in macro runner".into()
                    };
                    eprintln!("[ERROR] Macro runner panicked: {}", msg);
                }

                // Signal done regardless of panic
                engine_state.store(EngineState::Idle as u8, Ordering::Release);
            })
            .expect("failed to spawn macro runner thread");
        self.run_thread = Some(handle);
    }

    pub fn pause_run(&mut self) {
        MacroEngine::request_pause(&self.engine_state);
        self.run_state = RunState::Paused;
        self.log_event("Paused".into());
    }

    pub fn resume_run(&mut self) {
        MacroEngine::request_resume(&self.engine_state);
        self.run_state = RunState::Running;
        self.log_event("Resumed".into());
    }

    pub fn stop_run(&mut self) {
        self.stop_flag.store(true, Ordering::Release);
        MacroEngine::request_stop(&self.engine_state);
        self.run_state = RunState::Idle;
        self.log_event("Stopped by user".into());
    }
}

impl eframe::App for AutoMacroApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        // Apply theme (once at start, and whenever mode changes)
        if !self.theme_applied {
            theme::apply_theme_mode(ctx, self.theme_mode);
            self.theme_applied = true;
        }

        // R9: Dynamic window title
        {
            let macro_name = self.current_macro.as_ref()
                .map(|d| d.name.as_str())
                .unwrap_or("No macro");
            let dirty_mark = if self.dirty { " •" } else { "" };
            let title = format!("AutoMacro — {macro_name}{dirty_mark}");
            ctx.send_viewport_cmd(egui::ViewportCommand::Title(title));
        }

        // Autosave (every 60s if dirty)
        self.autosave_if_needed();

        // Check if engine finished or thread panicked
        if self.run_state == RunState::Running {
            // Check for thread panic first
            if let Some(ref handle) = self.run_thread {
                if handle.is_finished() {
                    // Safe: we just checked is_finished() via the ref above
                    if let Some(handle) = self.run_thread.take() {
                        match handle.join() {
                            Ok(()) => {
                                self.log_event("Completed".into());
                            }
                            Err(_) => {
                                self.log_event("⚠ Macro thread crashed (panic)".into());
                            }
                        }
                    }
                    self.run_state = RunState::Idle;
                    self.engine_state.store(EngineState::Idle as u8, Ordering::Release);
                }
            } else {
                // Fallback: check engine state directly
                let state = EngineState::from_u8(self.engine_state.load(Ordering::Acquire));
                if state == EngineState::Idle {
                    self.run_state = RunState::Idle;
                    self.log_event("Completed".into());
                }
            }
            // Request repaint while running
            ctx.request_repaint_after(std::time::Duration::from_millis(100));
        } else {
            // Idle: use max_fps setting to save CPU
            let ms = 1000 / self.max_fps.max(1);
            ctx.request_repaint_after(std::time::Duration::from_millis(ms as u64));
        }

        // ── Keyboard shortcuts ──
        // Save As (Ctrl+Shift+S must come BEFORE Ctrl+S to avoid conflict)
        if ctx.input(|i| i.modifiers.ctrl && i.modifiers.shift && i.key_pressed(egui::Key::S)) {
            self.save_macro_as();
        } else if ctx.input(|i| i.modifiers.ctrl && i.key_pressed(egui::Key::S)) {
            self.save_macro();
        }
        if ctx.input(|i| i.modifiers.ctrl && i.key_pressed(egui::Key::N)) {
            if self.dirty {
                // Auto-save if dirty before creating new
                self.save_macro();
            }
            self.new_macro();
        }
        if ctx.input(|i| i.modifiers.ctrl && i.key_pressed(egui::Key::O)) {
            self.open_macro_dialog();
        }
        if ctx.input(|i| i.modifiers.ctrl && i.key_pressed(egui::Key::D)) {
            self.duplicate_selected_action();
        }
        if ctx.input(|i| i.modifiers.ctrl && i.key_pressed(egui::Key::Z)) {
            self.undo();
        }
        if ctx.input(|i| i.modifiers.ctrl && i.key_pressed(egui::Key::Y)) {
            self.redo();
        }
        if ctx.input(|i| i.modifiers.ctrl && i.key_pressed(egui::Key::C)) {
            self.copy_selected_action();
        }
        if ctx.input(|i| i.modifiers.ctrl && i.key_pressed(egui::Key::V)) {
            self.paste_actions();
        }
        if ctx.input(|i| i.modifiers.ctrl && i.key_pressed(egui::Key::A))
            && !self.typed_actions.is_empty() {
                self.selected_action_idx = Some(0);
            }
        if ctx.input(|i| i.key_pressed(egui::Key::F1)) {
            self.help_state.open = !self.help_state.open;
        }
        if ctx.input(|i| i.modifiers.ctrl && i.key_pressed(egui::Key::G)) {
            self.coord_picker.active = !self.coord_picker.active;
        }
        if ctx.input(|i| i.modifiers.ctrl && i.key_pressed(egui::Key::H)) {
            self.show_optimizer = !self.show_optimizer;
        }
        // Escape — close dialogs/menus (priority order)
        if ctx.input(|i| i.key_pressed(egui::Key::Escape)) {
            if self.editing_action_idx.is_some() {
                // Cancel editor (restore backup)
                if let (Some(idx), Some(backup)) = (self.editing_action_idx, self.editing_backup.take()) {
                    if let Some(ref mut doc) = self.current_macro {
                        if idx < doc.actions.len() {
                            doc.actions[idx] = backup;
                        }
                    }
                }
                self.editing_action_idx = None;
            } else if self.show_context_menu {
                self.show_context_menu = false;
            } else if self.show_optimizer {
                self.show_optimizer = false;
            } else if self.coord_picker.active {
                self.coord_picker.active = false;
            } else if self.show_settings {
                self.show_settings = false;
                self.save_config();
            } else if self.help_state.open {
                self.help_state.open = false;
            } else if self.show_about {
                self.show_about = false;
            }
        }

        // ── Top toolbar ──
        egui::TopBottomPanel::top("toolbar").show(ctx, |ui| {
            ui.add_space(4.0);
            panels::toolbar::draw(self, ui);
            ui.add_space(4.0);
        });

        // ── Bottom status bar ──
        egui::TopBottomPanel::bottom("statusbar")
            .exact_height(28.0)
            .show(ctx, |ui| {
                panels::status_bar::draw(self, ui);
            });

        // ── Left panel: macro list ──
        egui::SidePanel::left("macro_list")
            .default_width(220.0)
            .min_width(180.0)
            .max_width(350.0)
            .show(ctx, |ui| {
                panels::macro_list::draw(self, ui);
            });

        // ── Right panel: execution / properties ──
        egui::SidePanel::right("right_panel")
            .default_width(300.0)
            .min_width(250.0)
            .max_width(450.0)
            .show(ctx, |ui| {
                panels::execution_panel::draw(self, ui);
            });

        // ── Central panel: action tree ──
        egui::CentralPanel::default().show(ctx, |ui| {
            panels::action_tree::draw(self, ui);
        });

        // ── Action editor window (modal) ──
        if let Some(idx) = self.editing_action_idx {
            let mut should_close = false;
            let mut should_cancel = false;

            if let Some(ref mut doc) = self.current_macro {
                if idx < doc.actions.len() {
                    let result = panels::action_editor::draw_editor(
                        ctx,
                        &mut doc.actions[idx],
                        idx,
                    );
                    match result {
                        panels::action_editor::EditorResult::Applied => {
                            should_close = true;
                        }
                        panels::action_editor::EditorResult::Cancelled => {
                            should_cancel = true;
                        }
                        panels::action_editor::EditorResult::Open => {}
                    }
                }
            }

            if should_close {
                self.editing_action_idx = None;
                self.editing_backup = None;
                self.dirty = true;
                self.recompile_actions();
            }
            if should_cancel {
                // Restore backup
                if let Some(backup) = self.editing_backup.take() {
                    if let Some(ref mut doc) = self.current_macro {
                        if idx < doc.actions.len() {
                            doc.actions[idx] = backup;
                        }
                    }
                }
                self.editing_action_idx = None;
                self.recompile_actions();
            }
        }

        // ── Settings window ──
        if self.show_settings {
            panels::settings::draw_settings(self, ctx);
        }

        // ── Help window ──
        if self.help_state.open {
            panels::help::draw_help(&mut self.help_state, ctx);
        }

        // ── About window ──
        if self.show_about {
            let mut open = true;
            egui::Window::new("ℹ  About AutoMacro")
                .id(egui::Id::new("about_dialog"))
                .open(&mut open)
                .resizable(false)
                .collapsible(false)
                .default_width(320.0)
                .anchor(egui::Align2::CENTER_CENTER, [0.0, 0.0])
                .show(ctx, |ui| {
                    ui.vertical_centered(|ui| {
                        ui.add_space(8.0);
                        ui.label(egui::RichText::new("⚡ AutoMacro").font(egui::FontId::proportional(24.0)).color(theme::ACCENT_LIGHT));
                        ui.label(egui::RichText::new(format!("v{}", env!("CARGO_PKG_VERSION"))).color(theme::TEXT_SECONDARY));
                        ui.add_space(8.0);
                        ui.label("Desktop macro automation tool");
                        ui.label(egui::RichText::new("Built with Rust + egui").color(theme::TEXT_DIM).font(theme::font_small()));
                        ui.add_space(8.0);
                        ui.label(egui::RichText::new("by TungDo").color(theme::TEXT_SECONDARY));
                        ui.add_space(8.0);
                        ui.separator();
                        ui.add_space(4.0);
                        ui.horizontal(|ui| {
                            ui.label(egui::RichText::new("Macros:").color(theme::TEXT_DIM).font(theme::font_small()));
                            ui.label(egui::RichText::new(format!("{}", self.macro_entries.len())).font(theme::font_small()));
                            ui.separator();
                            ui.label(egui::RichText::new("Actions:").color(theme::TEXT_DIM).font(theme::font_small()));
                            ui.label(egui::RichText::new(format!("{}", self.typed_actions.len())).font(theme::font_small()));
                        });
                    });
                });
            self.show_about = open;
        }

        // ── Coordinate Picker window ──
        panels::coord_picker::draw_picker_window(self, ctx);

        // ── Optimizer window ──
        if self.show_optimizer {
            let mut open = true;
            egui::Window::new("🔍 Macro Optimizer")
                .id(egui::Id::new("optimizer_dialog"))
                .open(&mut open)
                .resizable(true)
                .collapsible(true)
                .default_width(380.0)
                .default_height(300.0)
                .show(ctx, |ui| {
                    egui::ScrollArea::vertical().show(ui, |ui| {
                        panels::optimizer::draw(self, ui);
                    });
                });
            self.show_optimizer = open;
        }

        // ── Recording window ──
        panels::recording::draw_recording_window(self, ctx);

        // ── Screenshot window ──
        panels::screenshot::draw_screenshot_window(self, ctx);

        // ── Multi-Run window ──
        panels::multi_run::draw_multi_run_window(self, ctx);

        // ── Multi-run: advance queue when current run finishes ──
        if let Some(idx) = self.multi_run.running_idx {
            if self.run_state == RunState::Idle {
                // Current run finished — mark as done and advance
                if idx < self.multi_run.queue.len() {
                    self.multi_run.queue[idx].status = panels::multi_run::EntryStatus::Done;
                }
                // Find next enabled pending entry
                let next = self.multi_run.queue.iter().position(|e| {
                    e.enabled && matches!(e.status, panels::multi_run::EntryStatus::Pending)
                });
                if let Some(next_idx) = next {
                    self.multi_run.queue[next_idx].status = panels::multi_run::EntryStatus::Running;
                    self.multi_run.running_idx = Some(next_idx);
                    let path = self.multi_run.queue[next_idx].path.clone();
                    let loops = self.multi_run.queue[next_idx].loops;
                    self.load_macro_file(&path);
                    self.loop_count = loops;
                    self.log_event(format!("Multi-Run: Starting '{}' ({}×)", self.multi_run.queue[next_idx].name, loops));
                    self.start_run();
                } else {
                    self.multi_run.running_idx = None;
                    self.log_event("Multi-Run: Queue completed".into());
                }
            }
        }

        // ── Scheduler window ──
        panels::scheduler::draw_scheduler_window(self, ctx);

        // ── Scheduler trigger check (once per second) ──
        if self.run_state == RunState::Idle {
            if let Some(macro_name) = self.scheduler.check_triggers() {
                self.log_event(format!("Scheduler triggered: {}", macro_name));
                // Load and run the scheduled macro
                let macro_path = self.macros_dir.join(format!("{}.json", macro_name));
                if macro_path.exists() {
                    self.load_macro_file(&macro_path.to_string_lossy());
                    self.start_run();
                }
            }
        }

        // ── Debugger window ──
        panels::debugger::draw_debugger_window(self, ctx);

        // ── Export window ──
        panels::export::draw_export_window(self, ctx);

        // ── Confirmation Dialog ──
        if self.show_confirm_delete {
            let mut open = true;
            egui::Window::new("⚠ Confirm Delete")
                .id(egui::Id::new("confirm_delete"))
                .open(&mut open)
                .collapsible(false)
                .resizable(false)
                .anchor(egui::Align2::CENTER_CENTER, [0.0, 0.0])
                .show(ctx, |ui| {
                    let count = self.selected_actions.len().max(1);
                    ui.label(egui::RichText::new(format!("Delete {} action(s)?", count))
                        .color(theme::WARNING).font(theme::font_button()));
                    ui.add_space(8.0);
                    ui.horizontal(|ui| {
                        if ui.button(egui::RichText::new("✅ Yes, Delete").color(theme::ERROR).font(theme::font_button())).clicked() {
                            self.delete_selected_action();
                            self.show_confirm_delete = false;
                        }
                        ui.add_space(16.0);
                        if ui.button(egui::RichText::new("❌ Cancel").font(theme::font_button())).clicked() {
                            self.show_confirm_delete = false;
                        }
                    });
                });
            if !open {
                self.show_confirm_delete = false;
            }
        }
    }

    /// Save config and clean up on app close.
    fn on_exit(&mut self, _gl: Option<&eframe::glow::Context>) {
        // Stop recording if active
        if self.recording.active {
            self.recording.stop();
        }
        self.save_config();
    }
}

// ── Helpers ──────────────────────────────────────────────────────────────

fn find_macros_dir() -> PathBuf {
    // Try relative paths from executable
    let candidates = [
        PathBuf::from("../macros"),
        PathBuf::from("../../macros"),
        PathBuf::from("../../../macros"),
        PathBuf::from("macros"),
    ];

    for candidate in &candidates {
        if candidate.is_dir() {
            return candidate.clone();
        }
    }

    // Fallback to current dir
    std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
}

/// Return sensible default params JSON for each action type.
fn default_params_for(action_type: &str) -> serde_json::Value {
    use serde_json::json;
    match action_type {
        "delay" => json!({"ms": 1000}),
        "mouse_click" => json!({"x": 0, "y": 0, "button": "left", "clicks": 1}),
        "mouse_double_click" => json!({"x": 0, "y": 0, "button": "left"}),
        "mouse_right_click" => json!({"x": 0, "y": 0}),
        "mouse_move" => json!({"x": 0, "y": 0, "duration": 0}),
        "mouse_drag" => json!({"start_x": 0, "start_y": 0, "end_x": 100, "end_y": 100, "duration": 500}),
        "mouse_scroll" => json!({"x": 0, "y": 0, "clicks": 3}),
        "key_press" => json!({"key": "a", "duration": 0}),
        "key_combo" => json!({"keys": ["ctrl", "c"]}),
        "type_text" => json!({"text": "", "interval": 0.02}),
        "hotkey" => json!({"keys": ["alt", "tab"]}),
        "set_variable" => json!({"name": "var1", "value": ""}),
        "comment" => json!({"text": ""}),
        "group" => json!({"name": "New Group"}),
        "run_command" => json!({"command": "", "wait": true}),
        "log_to_file" => json!({"file_path": "log.txt", "message": "", "append": true}),
        "activate_window" => json!({"title": "", "match_type": "contains"}),
        "if_variable" => json!({"variable": "", "operator": "==", "value": ""}),
        "loop_block" => json!({"count": 3}),
        "take_screenshot" => json!({"file_path": "screenshot.bmp"}),
        _ => json!({}),
    }
}

/// Helper to create a RawAction for templates.
fn make_raw(action_type: &str, params: &[(&str, &str)]) -> amk_schema::RawAction {
    let mut p = serde_json::Map::new();
    for (k, v) in params {
        p.insert(k.to_string(), serde_json::Value::String(v.to_string()));
    }
    amk_schema::RawAction {
        action_type: action_type.to_string(),
        params: serde_json::Value::Object(p),
        delay_after: 0,
        repeat_count: 1,
        description: String::new(),
        enabled: true,
        on_error: amk_schema::OnErrorPolicy::Stop,
        color: None,
        bookmarked: false,
        sub_actions: Vec::new(),
        else_actions: Vec::new(),
    }
}
