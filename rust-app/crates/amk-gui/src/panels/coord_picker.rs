//! Coordinate Picker — live mouse position display + paste into editor.
//!
//! Uses Win32 GetCursorPos to show real-time screen coordinates.
//! Can copy coordinates to clipboard for pasting into mouse actions.

use eframe::egui;
use crate::app::AutoMacroApp;
use crate::theme;

/// State for coordinate picker.
#[derive(Default)]
pub struct CoordPickerState {
    pub active: bool,
    pub last_x: i32,
    pub last_y: i32,
    pub frozen: bool,
    pub frozen_x: i32,
    pub frozen_y: i32,
}

/// Draw the coordinate picker as an always-visible widget in Properties or a floating window.
pub fn draw_picker_window(app: &mut AutoMacroApp, ctx: &egui::Context) {
    if !app.coord_picker.active {
        return;
    }

    // Continuously poll cursor position
    if !app.coord_picker.frozen {
        let (x, y) = amk_platform::input::cursor_pos();
        app.coord_picker.last_x = x;
        app.coord_picker.last_y = y;
        // Request repaint to keep updating
        ctx.request_repaint_after(std::time::Duration::from_millis(50));
    }

    let mut open = app.coord_picker.active;
    egui::Window::new("🎯 Coordinate Picker")
        .id(egui::Id::new("coord_picker"))
        .open(&mut open)
        .resizable(false)
        .collapsible(false)
        .default_width(250.0)
        .anchor(egui::Align2::RIGHT_TOP, [-10.0, 40.0])
        .show(ctx, |ui| {
            let (display_x, display_y) = if app.coord_picker.frozen {
                (app.coord_picker.frozen_x, app.coord_picker.frozen_y)
            } else {
                (app.coord_picker.last_x, app.coord_picker.last_y)
            };

            // Big coordinate display
            ui.vertical_centered(|ui| {
                ui.label(
                    egui::RichText::new(format!("X: {}  Y: {}", display_x, display_y))
                        .font(egui::FontId::monospace(20.0))
                        .color(theme::ACCENT_LIGHT),
                );
            });

            ui.add_space(4.0);
            ui.separator();
            ui.add_space(4.0);

            ui.horizontal(|ui| {
                // Freeze/Unfreeze toggle
                let freeze_label = if app.coord_picker.frozen {
                    "▶ Resume"
                } else {
                    "⏸ Freeze"
                };
                if ui.button(freeze_label).clicked() {
                    if !app.coord_picker.frozen {
                        // Freeze at current position
                        app.coord_picker.frozen_x = app.coord_picker.last_x;
                        app.coord_picker.frozen_y = app.coord_picker.last_y;
                    }
                    app.coord_picker.frozen = !app.coord_picker.frozen;
                }

                // Copy coordinates
                if ui.button("📋 Copy").clicked() {
                    let coord_str = format!("{}, {}", display_x, display_y);
                    ui.ctx().copy_text(coord_str);
                    app.log_event(format!("Copied coordinates: ({}, {})", display_x, display_y));
                }
            });

            ui.add_space(4.0);

            // Screen info
            let (sw, sh) = amk_platform::input::screen_size();
            ui.label(
                egui::RichText::new(format!("Screen: {}×{}", sw, sh))
                    .color(theme::TEXT_DIM)
                    .font(theme::font_small()),
            );

            ui.label(
                egui::RichText::new("Move mouse to see coordinates. Press Freeze to lock.")
                    .color(theme::TEXT_DIM)
                    .font(theme::font_small()),
            );
        });
    app.coord_picker.active = open;
}
