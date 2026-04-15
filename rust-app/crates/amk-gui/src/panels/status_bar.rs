//! Bottom status bar — enhanced with clipboard/undo indicators.

use eframe::egui;
use crate::app::{AutoMacroApp, RunState};
use crate::theme;

pub fn draw(app: &AutoMacroApp, ui: &mut egui::Ui) {
    ui.horizontal(|ui| {
        // Macro name + file info
        if let Some(ref doc) = app.current_macro {
            let dirty_mark = if app.dirty { " *" } else { "" };
            ui.label(
                egui::RichText::new(format!("📄 {}{dirty_mark}", doc.name))
                    .color(if app.dirty { theme::WARNING } else { theme::TEXT_SECONDARY })
                    .font(theme::font_small()),
            );
            ui.separator();

            // Action count
            let enabled = app.typed_actions.iter().filter(|a| a.enabled).count();
            let total = app.typed_actions.len();
            let count_text = if enabled < total {
                format!("{enabled}/{total} actions")
            } else {
                format!("{total} actions")
            };
            ui.label(egui::RichText::new(count_text).color(theme::TEXT_DIM).font(theme::font_small()));

            if let Some(ref path) = app.current_file_path {
                ui.separator();
                let filename = std::path::Path::new(path)
                    .file_name()
                    .map(|n| n.to_string_lossy().to_string())
                    .unwrap_or_default();
                ui.label(egui::RichText::new(filename).color(theme::TEXT_DIM).font(theme::font_small()));
            }
        } else {
            ui.label(egui::RichText::new("No macro loaded").color(theme::TEXT_DIM).font(theme::font_small()));
        }

        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
            // Clipboard indicator
            if !app.copied_actions.is_empty() {
                ui.label(egui::RichText::new(format!("📋{}", app.copied_actions.len())).color(theme::TEXT_DIM).font(theme::font_small()));
                ui.separator();
            }

            // Undo/Redo indicator
            if !app.undo_stack.is_empty() || !app.redo_stack.is_empty() {
                ui.label(
                    egui::RichText::new(format!("↩{} ↪{}", app.undo_stack.len(), app.redo_stack.len()))
                        .color(theme::TEXT_DIM)
                        .font(theme::font_small()),
                );
                ui.separator();
            }

            // Live coordinates when picker active
            if app.coord_picker.active {
                ui.label(
                    egui::RichText::new(format!("🎯 {},{}", app.coord_picker.last_x, app.coord_picker.last_y))
                        .color(theme::ACCENT_LIGHT)
                        .font(egui::FontId::monospace(10.0)),
                );
                ui.separator();
            }

            // Run stats
            if let Some(ref report) = app.last_report {
                let (stats_color, stats_icon) = if report.actions_failed > 0 {
                    (theme::ERROR, "✗")
                } else {
                    (theme::SUCCESS, "✓")
                };
                ui.label(
                    egui::RichText::new(format!(
                        "{stats_icon} {} ok · {} fail · {:.1?}",
                        report.actions_succeeded,
                        report.actions_failed,
                        report.duration,
                    ))
                    .color(stats_color)
                    .font(theme::font_small()),
                );
                ui.separator();
            }

            // Status message with contextual color
            if !app.status_message.is_empty() {
                let color = if app.status_message.contains('⚠') || app.status_message.contains("error") {
                    theme::ERROR
                } else {
                    match app.run_state {
                        RunState::Running => theme::SUCCESS,
                        RunState::Paused => theme::WARNING,
                        RunState::Idle => theme::TEXT_SECONDARY,
                    }
                };
                ui.label(egui::RichText::new(&app.status_message).color(color).font(theme::font_small()));
            }
        });
    });
}
