//! Left panel — macro file list.

use eframe::egui;
use crate::app::AutoMacroApp;
use crate::theme;

pub fn draw(app: &mut AutoMacroApp, ui: &mut egui::Ui) {
    ui.vertical(|ui| {
        ui.label(
            egui::RichText::new("📁  Macros")
                .font(theme::font_header())
                .color(theme::TEXT_PRIMARY),
        );
        ui.add_space(4.0);

        if ui.button(egui::RichText::new("🔄 Refresh").font(theme::font_small())).clicked() {
            app.refresh_macro_list();
        }
        ui.add_space(2.0);

        // Search/filter
        if !app.macro_entries.is_empty() {
            ui.horizontal(|ui| {
                ui.label(egui::RichText::new("🔍").font(theme::font_small()));
                let resp = ui.add(
                    egui::TextEdit::singleline(&mut app.macro_filter)
                        .hint_text("Filter...")
                        .desired_width(ui.available_width() - 30.0)
                        .font(theme::font_small()),
                );
                if !app.macro_filter.is_empty()
                    && ui.small_button("✕").clicked() {
                        app.macro_filter.clear();
                        resp.request_focus();
                    }
            });
        }

        ui.add_space(2.0);
        ui.separator();
        ui.add_space(4.0);

        // Collect the clicked index (avoid borrow conflict)
        let mut clicked_idx: Option<usize> = None;

        egui::ScrollArea::vertical().show(ui, |ui| {
            let selected = app.selected_macro_idx;
            let filter = app.macro_filter.to_lowercase();
            for (i, entry) in app.macro_entries.iter().enumerate() {
                // R10: Skip entries that don't match filter
                if !filter.is_empty() && !entry.name.to_lowercase().contains(&filter) {
                    continue;
                }
                let is_selected = selected == Some(i);
                let bg = if is_selected { theme::BG_SELECTED } else { theme::BG_CARD };

                let resp = ui.allocate_ui_with_layout(
                    egui::Vec2::new(ui.available_width(), 40.0),
                    egui::Layout::left_to_right(egui::Align::Center),
                    |ui| {
                        let rect = ui.max_rect();
                        let hovered = ui.rect_contains_pointer(rect);
                        let fill = if hovered && !is_selected { theme::BG_HOVER } else { bg };

                        ui.painter().rect_filled(rect, 4.0, fill);
                        if is_selected {
                            let stroke = egui::Stroke::new(1.0, theme::ACCENT);
                            let r = rect;
                            ui.painter().line_segment([r.left_top(), r.right_top()], stroke);
                            ui.painter().line_segment([r.right_top(), r.right_bottom()], stroke);
                            ui.painter().line_segment([r.right_bottom(), r.left_bottom()], stroke);
                            ui.painter().line_segment([r.left_bottom(), r.left_top()], stroke);
                        }

                        ui.add_space(8.0);
                        ui.vertical(|ui| {
                            ui.label(
                                egui::RichText::new(&entry.name)
                                    .color(if is_selected { theme::ACCENT_LIGHT } else { theme::TEXT_PRIMARY })
                                    .font(egui::FontId::proportional(13.0)),
                            );
                            ui.label(
                                egui::RichText::new(format!("{} actions", entry.action_count))
                                    .color(theme::TEXT_DIM)
                                    .font(theme::font_small()),
                            );
                        });
                    },
                );

                if resp.response.clicked() {
                    clicked_idx = Some(i);
                }
                ui.add_space(2.0);
            }
        });

        // Handle click after iteration ends (no borrow conflict)
        if let Some(idx) = clicked_idx {
            app.selected_macro_idx = Some(idx);
            let path = app.macro_entries[idx].path.clone();
            app.load_macro_file(&path);
        }
    });
}
