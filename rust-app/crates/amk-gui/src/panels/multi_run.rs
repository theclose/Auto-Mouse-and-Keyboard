//! Multi-Run Panel — batch execute multiple macros sequentially.

use eframe::egui;
use crate::app::AutoMacroApp;
use crate::theme;

/// State for multi-run panel.
#[derive(Default)]
pub struct MultiRunState {
    pub show: bool,
    pub queue: Vec<MultiRunEntry>,
    pub running_idx: Option<usize>,
}

/// An entry in the multi-run queue.
#[derive(Clone)]
pub struct MultiRunEntry {
    pub path: String,
    pub name: String,
    pub loops: u32,
    pub enabled: bool,
    pub status: EntryStatus,
}

#[derive(Clone, Default, PartialEq)]
pub enum EntryStatus {
    #[default]
    Pending,
    Running,
    Done,
    #[allow(dead_code)]
    Failed(String),
}

pub fn draw_multi_run_window(app: &mut AutoMacroApp, ctx: &egui::Context) {
    if !app.multi_run.show {
        return;
    }

    let mut open = true;
    egui::Window::new("📋 Multi-Run Queue")
        .id(egui::Id::new("multi_run_dialog"))
        .open(&mut open)
        .resizable(true)
        .collapsible(true)
        .default_width(420.0)
        .default_height(350.0)
        .show(ctx, |ui| {
            // Add macros button
            ui.horizontal(|ui| {
                if ui.button("➕ Add Macros").clicked() {
                    if let Some(paths) = rfd::FileDialog::new()
                        .set_title("Select Macros for Queue")
                        .add_filter("AutoMacro JSON", &["json"])
                        .set_directory(&app.macros_dir)
                        .pick_files()
                    {
                        for path in paths {
                            let name = path.file_stem()
                                .map(|n| n.to_string_lossy().to_string())
                                .unwrap_or_else(|| "Unknown".into());
                            app.multi_run.queue.push(MultiRunEntry {
                                path: path.to_string_lossy().to_string(),
                                name,
                                loops: 1,
                                enabled: true,
                                status: EntryStatus::Pending,
                            });
                        }
                    }
                }

                // Add from current macro list
                if ui.button("📁 Add All Listed").clicked() {
                    for entry in &app.macro_entries {
                        let already = app.multi_run.queue.iter().any(|e| e.path == entry.path);
                        if !already {
                            app.multi_run.queue.push(MultiRunEntry {
                                path: entry.path.clone(),
                                name: entry.name.clone(),
                                loops: 1,
                                enabled: true,
                                status: EntryStatus::Pending,
                            });
                        }
                    }
                }

                if !app.multi_run.queue.is_empty()
                    && ui.button("🗑 Clear").clicked() {
                        app.multi_run.queue.clear();
                    }
            });

            ui.add_space(4.0);
            ui.separator();
            ui.add_space(4.0);

            // Queue list
            if app.multi_run.queue.is_empty() {
                ui.colored_label(theme::TEXT_DIM, "No macros in queue. Add macros to run them sequentially.");
            } else {
                let mut remove_idx = None;

                egui::ScrollArea::vertical().max_height(220.0).show(ui, |ui| {
                    for (i, entry) in app.multi_run.queue.iter_mut().enumerate() {
                        ui.horizontal(|ui| {
                            // Enable checkbox
                            ui.checkbox(&mut entry.enabled, "");

                            // Status icon
                            let (icon, color) = match &entry.status {
                                EntryStatus::Pending => ("⏳", theme::TEXT_DIM),
                                EntryStatus::Running => ("▶", theme::SUCCESS),
                                EntryStatus::Done => ("✅", theme::SUCCESS),
                                EntryStatus::Failed(_) => ("❌", theme::ERROR),
                            };
                            ui.label(egui::RichText::new(icon).color(color));

                            // Name
                            let name_color = if entry.enabled { theme::TEXT_PRIMARY } else { theme::TEXT_DIM };
                            ui.label(egui::RichText::new(&entry.name).color(name_color).font(theme::font_small()));

                            // Loops
                            ui.label(egui::RichText::new("×").color(theme::TEXT_DIM).font(theme::font_small()));
                            ui.add(egui::DragValue::new(&mut entry.loops).range(1..=999).speed(0.3));

                            // Remove
                            if ui.small_button("✕").clicked() {
                                remove_idx = Some(i);
                            }
                        });
                    }
                });

                if let Some(idx) = remove_idx {
                    app.multi_run.queue.remove(idx);
                }
            }

            ui.add_space(4.0);
            ui.separator();
            ui.add_space(4.0);

            // Run controls
            let has_enabled = app.multi_run.queue.iter().any(|e| e.enabled);
            ui.horizontal(|ui| {
                if ui.add_enabled(
                    has_enabled && app.multi_run.running_idx.is_none(),
                    egui::Button::new(egui::RichText::new("▶ Run Queue").color(theme::SUCCESS).font(theme::font_button()))
                ).clicked() {
                    run_queue_sequential(app);
                }

                // Summary
                let total = app.multi_run.queue.len();
                let enabled = app.multi_run.queue.iter().filter(|e| e.enabled).count();
                let done = app.multi_run.queue.iter().filter(|e| matches!(e.status, EntryStatus::Done)).count();
                ui.label(
                    egui::RichText::new(format!("{done}/{enabled} done, {total} total"))
                        .color(theme::TEXT_DIM)
                        .font(theme::font_small()),
                );
            });
        });
    app.multi_run.show = open;
}

/// Run the queue by loading each macro and running it sequentially.
/// Note: this loads the first enabled macro and runs it. When done,
/// the user clicks Run Queue again for the next item (simple approach).
fn run_queue_sequential(app: &mut AutoMacroApp) {
    // Reset all statuses to Pending
    for entry in &mut app.multi_run.queue {
        if entry.enabled {
            entry.status = EntryStatus::Pending;
        }
    }

    // Find first enabled pending entry
    if let Some(idx) = app.multi_run.queue.iter().position(|e| e.enabled && matches!(e.status, EntryStatus::Pending)) {
        app.multi_run.queue[idx].status = EntryStatus::Running;
        app.multi_run.running_idx = Some(idx);
        let path = app.multi_run.queue[idx].path.clone();
        let loops = app.multi_run.queue[idx].loops;

        // Load the macro
        app.load_macro_file(&path);
        app.loop_count = loops;
        app.log_event(format!("Multi-Run: Starting '{}' ({}×)", app.multi_run.queue[idx].name, loops));
        app.start_run();
    }
}
