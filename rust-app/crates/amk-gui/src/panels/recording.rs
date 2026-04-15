//! Recording Panel — Record mouse/keyboard actions into the macro.
//!
//! Uses a background thread with Win32 GetAsyncKeyState + GetCursorPos polling
//! to detect mouse clicks and key presses, converting them into macro actions.

use eframe::egui;
use crate::app::AutoMacroApp;
use crate::theme;
use std::sync::{Arc, Mutex};
use std::sync::atomic::{AtomicBool, Ordering};

/// Recorded event from the polling thread.
#[derive(Clone, Debug)]
pub enum RecordedEvent {
    MouseClick { x: i32, y: i32, button: String, timestamp_ms: u64 },
    KeyPress { key: String, timestamp_ms: u64 },
}

/// State for the recording panel.
pub struct RecordingState {
    pub active: bool,
    #[allow(dead_code)]
    pub record_mouse_moves: bool,
    pub min_delay_ms: u32,
    pub events: Arc<Mutex<Vec<RecordedEvent>>>,
    pub recording_flag: Arc<AtomicBool>,
    pub thread_handle: Option<std::thread::JoinHandle<()>>,
}

impl Default for RecordingState {
    fn default() -> Self {
        Self {
            active: false,
            record_mouse_moves: false,
            min_delay_ms: 50,
            events: Arc::new(Mutex::new(Vec::new())),
            recording_flag: Arc::new(AtomicBool::new(false)),
            thread_handle: None,
        }
    }
}

impl RecordingState {
    /// Start recording in a background thread.
    pub fn start(&mut self) {
        self.recording_flag.store(true, Ordering::Release);
        if let Ok(mut events) = self.events.lock() {
            events.clear();
        }

        let flag = Arc::clone(&self.recording_flag);
        let events = Arc::clone(&self.events);
        let min_delay = self.min_delay_ms;

        let handle = std::thread::Builder::new()
            .name("amk-recorder".into())
            .spawn(move || {
                record_loop(flag, events, min_delay);
            })
            .expect("Failed to spawn recorder thread");

        self.thread_handle = Some(handle);
        self.active = true;
    }

    /// Stop recording.
    pub fn stop(&mut self) {
        self.recording_flag.store(false, Ordering::Release);
        if let Some(handle) = self.thread_handle.take() {
            let _ = handle.join();
        }
        self.active = false;
    }

    /// Get recorded events count.
    pub fn event_count(&self) -> usize {
        self.events.lock().map(|e| e.len()).unwrap_or(0)
    }

    /// Take all recorded events.
    pub fn take_events(&self) -> Vec<RecordedEvent> {
        self.events.lock().map(|mut e| std::mem::take(&mut *e)).unwrap_or_default()
    }
}

/// Polling loop that detects mouse clicks and key presses via GetAsyncKeyState.
fn record_loop(
    flag: Arc<AtomicBool>,
    events: Arc<Mutex<Vec<RecordedEvent>>>,
    _min_delay: u32,
) {
    use std::time::Instant;

    let start = Instant::now();

    // Track previous state to detect transitions
    let mut prev_lmb = false;
    let mut prev_rmb = false;
    let mut prev_keys: [bool; 256] = [false; 256];

    while flag.load(Ordering::Acquire) {
        let elapsed_ms = start.elapsed().as_millis() as u64;
        let (cx, cy) = amk_platform::input::cursor_pos();

        // Left mouse button (VK_LBUTTON = 0x01)
        let lmb_down = amk_platform::input::is_key_pressed(0x01);
        if lmb_down && !prev_lmb {
            if let Ok(mut evs) = events.lock() {
                evs.push(RecordedEvent::MouseClick {
                    x: cx, y: cy, button: "left".into(), timestamp_ms: elapsed_ms,
                });
            }
        }
        prev_lmb = lmb_down;

        // Right mouse button (VK_RBUTTON = 0x02)
        let rmb_down = amk_platform::input::is_key_pressed(0x02);
        if rmb_down && !prev_rmb {
            if let Ok(mut evs) = events.lock() {
                evs.push(RecordedEvent::MouseClick {
                    x: cx, y: cy, button: "right".into(), timestamp_ms: elapsed_ms,
                });
            }
        }
        prev_rmb = rmb_down;

        // Key presses (skip modifiers and mouse buttons)
        for vk in 0x08u16..0xFFu16 {
            // Skip mouse buttons and modifier-only keys for the key list
            if vk <= 0x06 { continue; } // Mouse buttons
            let down = amk_platform::input::is_key_pressed(vk);
            if down && !prev_keys[vk as usize] {
                if let Some(name) = vk_to_name(vk) {
                    if let Ok(mut evs) = events.lock() {
                        evs.push(RecordedEvent::KeyPress {
                            key: name, timestamp_ms: elapsed_ms,
                        });
                    }
                }
            }
            prev_keys[vk as usize] = down;
        }

        std::thread::sleep(std::time::Duration::from_millis(10));
    }
}

/// Convert VK code to human-readable key name (subset).
fn vk_to_name(vk: u16) -> Option<String> {
    let name = match vk {
        0x08 => "backspace", 0x09 => "tab", 0x0D => "enter", 0x1B => "escape",
        0x20 => "space", 0x21 => "pageup", 0x22 => "pagedown",
        0x23 => "end", 0x24 => "home",
        0x25 => "left", 0x26 => "up", 0x27 => "right", 0x28 => "down",
        0x2D => "insert", 0x2E => "delete",
        0x30..=0x39 => return Some(format!("{}", (vk - 0x30))),
        0x41..=0x5A => return Some(format!("{}", (vk as u8 as char).to_lowercase())),
        0x70..=0x7B => return Some(format!("f{}", vk - 0x70 + 1)),
        _ => return None,
    };
    Some(name.into())
}

/// Draw the recording panel UI.
pub fn draw_recording_window(app: &mut AutoMacroApp, ctx: &egui::Context) {
    if !app.show_recording {
        return;
    }

    let mut open = true;
    egui::Window::new("🔴 Macro Recorder")
        .id(egui::Id::new("recorder_dialog"))
        .open(&mut open)
        .resizable(true)
        .collapsible(false)
        .default_width(350.0)
        .default_height(300.0)
        .show(ctx, |ui| {
            // Status
            let is_active = app.recording.active;
            if is_active {
                ui.horizontal(|ui| {
                    ui.label(egui::RichText::new("🔴 RECORDING").color(theme::ERROR).font(egui::FontId::proportional(16.0)));
                    ui.label(egui::RichText::new(format!("{} events", app.recording.event_count())).color(theme::TEXT_DIM));
                });
                ctx.request_repaint_after(std::time::Duration::from_millis(200));
            } else {
                ui.label(egui::RichText::new("⏹ Stopped").color(theme::TEXT_DIM));
            }

            ui.add_space(4.0);
            ui.separator();
            ui.add_space(4.0);

            // Settings (only when not recording)
            if !is_active {
                ui.horizontal(|ui| {
                    ui.label("Min delay filter:");
                    ui.add(egui::DragValue::new(&mut app.recording.min_delay_ms)
                        .range(10..=1000).speed(10).suffix(" ms"));
                });
                ui.add_space(4.0);
            }

            // Controls
            ui.horizontal(|ui| {
                if !is_active {
                    if ui.button(egui::RichText::new("🔴 Start Recording").color(theme::ERROR).font(theme::font_button())).clicked() {
                        app.recording.start();
                        app.log_event("Recording started".into());
                    }
                } else {
                    if ui.button(egui::RichText::new("⏹ Stop").color(theme::WARNING).font(theme::font_button())).clicked() {
                        app.recording.stop();
                        app.log_event(format!("Recording stopped ({} events)", app.recording.event_count()));
                    }
                }

                if !is_active && app.recording.event_count() > 0 {
                    ui.separator();
                    if ui.button(egui::RichText::new("✅ Insert into Macro").color(theme::SUCCESS).font(theme::font_button())).clicked() {
                        insert_recorded_events(app);
                    }
                    if ui.button(egui::RichText::new("🗑 Clear").font(theme::font_button())).clicked() {
                        if let Ok(mut evs) = app.recording.events.lock() {
                            evs.clear();
                        }
                    }
                }
            });

            ui.add_space(4.0);

            // Event list preview
            if let Ok(events) = app.recording.events.lock() {
                if !events.is_empty() {
                    ui.separator();
                    ui.label(egui::RichText::new(format!("Recorded Events ({})", events.len())).color(theme::ACCENT_LIGHT).font(theme::font_button()));
                    ui.add_space(2.0);

                    egui::ScrollArea::vertical().max_height(200.0).show(ui, |ui| {
                        for (i, event) in events.iter().enumerate() {
                            let text = match event {
                                RecordedEvent::MouseClick { x, y, button, timestamp_ms } => {
                                    format!("#{} [{:.1}s] 🖱 {} click ({},{})", i + 1, *timestamp_ms as f64 / 1000.0, button, x, y)
                                }
                                RecordedEvent::KeyPress { key, timestamp_ms } => {
                                    format!("#{} [{:.1}s] ⌨ key [{}]", i + 1, *timestamp_ms as f64 / 1000.0, key)
                                }
                            };
                            ui.label(egui::RichText::new(text).font(egui::FontId::monospace(10.0)).color(theme::TEXT_SECONDARY));
                        }
                    });
                }
            }

            ui.add_space(4.0);
            ui.colored_label(theme::TEXT_DIM, "Tip: Start recording, then interact with your desktop.");
            ui.colored_label(theme::TEXT_DIM, "Press Stop to finish, then Insert to add to macro.");
        });
    app.show_recording = open;
}

/// Convert recorded events into typed actions and insert into the macro.
fn insert_recorded_events(app: &mut AutoMacroApp) {
    let events = app.recording.take_events();
    if events.is_empty() { return; }

    app.push_undo();

    let mut prev_time_ms = 0u64;
    for event in &events {
        let event_time = match event {
            RecordedEvent::MouseClick { timestamp_ms, .. } => *timestamp_ms,
            RecordedEvent::KeyPress { timestamp_ms, .. } => *timestamp_ms,
        };

        // Insert delay between events
        let delta = event_time.saturating_sub(prev_time_ms);
        if delta > 30 {
            app.add_action_with_params("delay", serde_json::json!({"ms": delta}));
        }
        prev_time_ms = event_time;

        // Insert the action
        match event {
            RecordedEvent::MouseClick { x, y, button, .. } => {
                app.add_action_with_params("mouse_click", serde_json::json!({
                    "x": x, "y": y, "button": button, "clicks": 1
                }));
            }
            RecordedEvent::KeyPress { key, .. } => {
                app.add_action_with_params("key_press", serde_json::json!({
                    "key": key, "duration": 0
                }));
            }
        }
    }

    app.recompile_actions();
    app.dirty = true;
    app.log_event(format!("Inserted {} recorded events", events.len()));
}
