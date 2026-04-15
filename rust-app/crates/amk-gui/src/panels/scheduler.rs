//! Scheduler panel — schedule macros to run at specific times.
//!
//! Features:
//! - Add scheduled tasks with specific time or interval
//! - Enable/disable individual schedules
//! - One-shot or recurring (daily, interval-based)
//! - Visual next-run countdown

use eframe::egui;
use crate::app::AutoMacroApp;
use crate::theme;

/// A single scheduled task.
#[derive(Debug, Clone)]
pub struct ScheduleEntry {
    pub macro_name: String,
    pub schedule_type: ScheduleType,
    pub enabled: bool,
    pub last_run: Option<chrono::DateTime<chrono::Local>>,
    pub next_run: Option<chrono::DateTime<chrono::Local>>,
}

/// How a schedule triggers.
#[derive(Debug, Clone, PartialEq)]
pub enum ScheduleType {
    /// Run once at a specific time.
    Once { hour: u32, minute: u32 },
    /// Repeat every N minutes.
    Interval { minutes: u32 },
    /// Run daily at a specific time.
    Daily { hour: u32, minute: u32 },
}

impl std::fmt::Display for ScheduleType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ScheduleType::Once { hour, minute } => write!(f, "Once at {:02}:{:02}", hour, minute),
            ScheduleType::Interval { minutes } => write!(f, "Every {} min", minutes),
            ScheduleType::Daily { hour, minute } => write!(f, "Daily {:02}:{:02}", hour, minute),
        }
    }
}

/// State for the scheduler panel.
#[derive(Debug, Clone, Default)]
pub struct SchedulerState {
    pub open: bool,
    pub entries: Vec<ScheduleEntry>,
    // New entry form
    pub new_macro_name: String,
    pub new_type_idx: usize, // 0=Once, 1=Interval, 2=Daily
    pub new_hour: u32,
    pub new_minute: u32,
    pub new_interval: u32,
}

impl SchedulerState {
    /// Check if any schedule should trigger now.
    pub fn check_triggers(&mut self) -> Option<String> {
        let now = chrono::Local::now();
        for entry in &mut self.entries {
            if !entry.enabled { continue; }
            if let Some(next) = entry.next_run {
                if now >= next {
                    let name = entry.macro_name.clone();
                    entry.last_run = Some(now);
                    // Calculate next run
                    entry.next_run = match &entry.schedule_type {
                        ScheduleType::Once { .. } => {
                            entry.enabled = false;
                            None
                        }
                        ScheduleType::Interval { minutes } => {
                            Some(now + chrono::Duration::minutes(*minutes as i64))
                        }
                        ScheduleType::Daily { hour, minute } => {
                            let next = now.date_naive().succ_opt()
                                .and_then(|d| d.and_hms_opt(*hour, *minute, 0))
                                .and_then(|dt| dt.and_local_timezone(chrono::Local).earliest());
                            if next.is_none() {
                                entry.enabled = false;
                            }
                            next
                        }
                    };
                    return Some(name);
                }
            }
        }
        None
    }
}

pub fn draw_scheduler_window(app: &mut AutoMacroApp, ctx: &egui::Context) {
    if !app.scheduler.open { return; }

    let mut open = true;
    egui::Window::new("📅 Scheduler")
        .id(egui::Id::new("scheduler_window"))
        .open(&mut open)
        .resizable(true)
        .collapsible(true)
        .default_width(420.0)
        .default_height(350.0)
        .show(ctx, |ui| {
            ui.label(egui::RichText::new("Schedule macros to run automatically")
                .color(theme::TEXT_SECONDARY).font(theme::font_small()));
            ui.add_space(4.0);

            // ── Add new schedule ──
            ui.group(|ui| {
                ui.label(egui::RichText::new("➕ New Schedule").color(theme::ACCENT_LIGHT).font(theme::font_small()));
                ui.add_space(4.0);

                egui::Grid::new("sched_new_grid").num_columns(2).spacing([12.0, 4.0]).show(ui, |ui| {
                    ui.label("Macro:");
                    // Combo from available macros
                    let macro_names: Vec<String> = app.macro_entries.iter()
                        .map(|e| e.name.clone())
                        .collect();
                    egui::ComboBox::from_id_salt("sched_macro")
                        .selected_text(if app.scheduler.new_macro_name.is_empty() { "Select..." } else { &app.scheduler.new_macro_name })
                        .show_ui(ui, |ui| {
                            for name in &macro_names {
                                if ui.selectable_label(app.scheduler.new_macro_name == *name, name).clicked() {
                                    app.scheduler.new_macro_name = name.clone();
                                }
                            }
                        });
                    ui.end_row();

                    ui.label("Type:");
                    ui.horizontal(|ui| {
                        ui.selectable_value(&mut app.scheduler.new_type_idx, 0, "Once");
                        ui.selectable_value(&mut app.scheduler.new_type_idx, 1, "Interval");
                        ui.selectable_value(&mut app.scheduler.new_type_idx, 2, "Daily");
                    });
                    ui.end_row();

                    match app.scheduler.new_type_idx {
                        0 | 2 => {
                            ui.label("Time:");
                            ui.horizontal(|ui| {
                                ui.add(egui::DragValue::new(&mut app.scheduler.new_hour).range(0..=23).suffix("h"));
                                ui.label(":");
                                ui.add(egui::DragValue::new(&mut app.scheduler.new_minute).range(0..=59).suffix("m"));
                            });
                        }
                        1 => {
                            ui.label("Every:");
                            ui.add(egui::DragValue::new(&mut app.scheduler.new_interval).range(1..=1440).suffix(" min"));
                        }
                        _ => {}
                    }
                    ui.end_row();
                });

                ui.add_space(4.0);
                if ui.add_enabled(!app.scheduler.new_macro_name.is_empty(),
                    egui::Button::new(egui::RichText::new("➕ Add Schedule").color(theme::SUCCESS).font(theme::font_small()))
                ).clicked() {
                    let now = chrono::Local::now();
                    let stype = match app.scheduler.new_type_idx {
                        0 => ScheduleType::Once { hour: app.scheduler.new_hour, minute: app.scheduler.new_minute },
                        1 => ScheduleType::Interval { minutes: app.scheduler.new_interval.max(1) },
                        _ => ScheduleType::Daily { hour: app.scheduler.new_hour, minute: app.scheduler.new_minute },
                    };

                    // Calculate initial next_run
                    let next = match &stype {
                        ScheduleType::Once { hour, minute } | ScheduleType::Daily { hour, minute } => {
                            let today = now.date_naive();
                            today.and_hms_opt(*hour, *minute, 0)
                                .and_then(|dt| dt.and_local_timezone(chrono::Local).earliest())
                                .map(|target| {
                                    if target <= now {
                                        target + chrono::Duration::days(1)
                                    } else {
                                        target
                                    }
                                })
                        }
                        ScheduleType::Interval { minutes } => {
                            Some(now + chrono::Duration::minutes(*minutes as i64))
                        }
                    };

                    app.scheduler.entries.push(ScheduleEntry {
                        macro_name: app.scheduler.new_macro_name.clone(),
                        schedule_type: stype,
                        enabled: true,
                        last_run: None,
                        next_run: next,
                    });
                    app.log_event(format!("Added schedule for '{}'", app.scheduler.new_macro_name));
                }
            });

            ui.add_space(8.0);

            // ── Schedule list ──
            if app.scheduler.entries.is_empty() {
                ui.colored_label(theme::TEXT_DIM, "No scheduled tasks. Add one above.");
            } else {
                let mut remove_idx = None;
                for (i, entry) in app.scheduler.entries.iter_mut().enumerate() {
                    ui.horizontal(|ui| {
                        ui.checkbox(&mut entry.enabled, "");
                        let color = if entry.enabled { theme::TEXT_PRIMARY } else { theme::TEXT_DIM };
                        ui.label(egui::RichText::new(&entry.macro_name).color(color));
                        ui.label(egui::RichText::new(format!("({})", entry.schedule_type)).color(theme::TEXT_SECONDARY).font(theme::font_small()));

                        // Next run countdown
                        if let Some(next) = entry.next_run {
                            let now = chrono::Local::now();
                            let diff = next.signed_duration_since(now);
                            if diff.num_seconds() > 0 {
                                let mins = diff.num_minutes();
                                let secs = diff.num_seconds() % 60;
                                ui.label(egui::RichText::new(format!("⏱ {}m{}s", mins, secs))
                                    .color(theme::ACCENT_LIGHT).font(theme::font_small()));
                            }
                        }

                        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                            if ui.small_button("🗑").clicked() {
                                remove_idx = Some(i);
                            }
                        });
                    });
                }
                if let Some(idx) = remove_idx {
                    app.scheduler.entries.remove(idx);
                }
            }
        });

    if !open { app.scheduler.open = false; }
}
