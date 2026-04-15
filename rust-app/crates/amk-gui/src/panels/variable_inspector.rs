//! Variable Inspector Panel — shows live variable state during execution.
//!
//! Displays all set_variable actions' names and their default values,
//! and can be extended to show live values during macro execution.

use eframe::egui;
use amk_domain::action::ActionKind;
use crate::app::AutoMacroApp;
use crate::theme;

/// Draw the variable inspector as a collapsible section.
pub fn draw(app: &AutoMacroApp, ui: &mut egui::Ui) {
    // Collect all variables from actions
    let mut vars: Vec<(&str, &str)> = Vec::new();
    collect_variables(&app.typed_actions, &mut vars);

    ui.group(|ui| {
        ui.label(
            egui::RichText::new(format!("📌  Variables ({})", vars.len()))
                .color(theme::ACCENT_LIGHT)
                .font(theme::font_button()),
        );
        ui.add_space(2.0);

        if vars.is_empty() {
            ui.colored_label(theme::TEXT_DIM, "No variables defined.");
            ui.colored_label(
                theme::TEXT_DIM,
                "Add 'Set Variable' actions to see them here.",
            );
        } else {
            egui::Grid::new("var_inspector_grid")
                .num_columns(2)
                .spacing([12.0, 3.0])
                .striped(true)
                .show(ui, |ui| {
                    // Header
                    ui.label(
                        egui::RichText::new("Name")
                            .color(theme::TEXT_DIM)
                            .font(theme::font_small()),
                    );
                    ui.label(
                        egui::RichText::new("Default Value")
                            .color(theme::TEXT_DIM)
                            .font(theme::font_small()),
                    );
                    ui.end_row();

                    for (name, value) in &vars {
                        ui.label(
                            egui::RichText::new(*name)
                                .color(theme::ACCENT_LIGHT)
                                .font(egui::FontId::monospace(11.0)),
                        );
                        ui.label(
                            egui::RichText::new(format!("\"{}\"", truncate(value, 30)))
                                .color(theme::TEXT_SECONDARY)
                                .font(egui::FontId::monospace(11.0)),
                        );
                        ui.end_row();
                    }
                });
        }
    });
}

fn collect_variables<'a>(
    actions: &'a [amk_domain::action::TypedAction],
    out: &mut Vec<(&'a str, &'a str)>,
) {
    for action in actions {
        match &action.kind {
            ActionKind::SetVariable { name, value } => {
                // Only add if not already present
                if !out.iter().any(|(n, _)| *n == name.as_str()) {
                    out.push((name.as_str(), value.as_str()));
                }
            }
            ActionKind::Group { children, .. }
            | ActionKind::LoopBlock { children, .. } => {
                collect_variables(children, out);
            }
            ActionKind::IfVariable {
                then_actions,
                else_actions,
                ..
            }
            | ActionKind::IfPixelColor {
                then_actions,
                else_actions,
                ..
            }
            | ActionKind::IfImageFound {
                then_actions,
                else_actions,
                ..
            } => {
                collect_variables(then_actions, out);
                collect_variables(else_actions, out);
            }
            _ => {}
        }
    }
}

fn truncate(s: &str, max: usize) -> String {
    if s.len() <= max {
        s.to_owned()
    } else {
        format!("{}…", &s[..max.saturating_sub(1)])
    }
}
