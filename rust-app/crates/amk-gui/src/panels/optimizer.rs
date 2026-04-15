//! Macro Optimizer — analyze macro and provide improvement hints.
//!
//! Scans the action list for common inefficiencies and suggests fixes.

use amk_domain::action::{ActionKind, TypedAction};
use eframe::egui;
use crate::app::AutoMacroApp;
use crate::theme;

/// A single optimization hint.
struct Hint {
    severity: Severity,
    action_idx: Option<usize>,
    message: String,
}

#[derive(Clone, Copy)]
enum Severity {
    Info,
    Warning,
    Error,
}

impl Severity {
    fn icon(self) -> &'static str {
        match self {
            Severity::Info => "💡",
            Severity::Warning => "⚠",
            Severity::Error => "❌",
        }
    }
    fn color(self) -> egui::Color32 {
        match self {
            Severity::Info => theme::TEXT_SECONDARY,
            Severity::Warning => theme::WARNING,
            Severity::Error => theme::ERROR,
        }
    }
}

/// Draw the optimizer hints dialog.
pub fn draw(app: &AutoMacroApp, ui: &mut egui::Ui) {
    let hints = analyze(&app.typed_actions);

    ui.group(|ui| {
        ui.label(
            egui::RichText::new(format!("🔍  Optimizer ({} hints)", hints.len()))
                .color(theme::ACCENT_LIGHT)
                .font(theme::font_button()),
        );
        ui.add_space(4.0);

        if hints.is_empty() {
            ui.colored_label(theme::SUCCESS, "✅ No issues found. Macro looks good!");
        } else {
            for hint in &hints {
                ui.horizontal(|ui| {
                    ui.label(
                        egui::RichText::new(hint.severity.icon())
                            .color(hint.severity.color()),
                    );
                    if let Some(idx) = hint.action_idx {
                        ui.label(
                            egui::RichText::new(format!("#{}", idx + 1))
                                .color(theme::TEXT_DIM)
                                .font(egui::FontId::monospace(10.0)),
                        );
                    }
                    ui.label(
                        egui::RichText::new(&hint.message)
                            .color(hint.severity.color())
                            .font(theme::font_small()),
                    );
                });
            }
        }
    });
}

/// Analyze the macro and generate hints.
fn analyze(actions: &[TypedAction]) -> Vec<Hint> {
    let mut hints = Vec::new();

    if actions.is_empty() {
        return hints;
    }

    // Check for common issues
    for (i, action) in actions.iter().enumerate() {
        // Very short delays (< 10ms) are suspicious
        if let ActionKind::Delay { duration_ms } = &action.kind {
            if *duration_ms < 10 && *duration_ms > 0 {
                hints.push(Hint {
                    severity: Severity::Warning,
                    action_idx: Some(i),
                    message: format!("Very short delay ({}ms) — may be unreliable", duration_ms),
                });
            }
            if *duration_ms > 30000 {
                hints.push(Hint {
                    severity: Severity::Info,
                    action_idx: Some(i),
                    message: format!("Long delay ({}s) — consider using wait_for_image instead", duration_ms / 1000),
                });
            }
        }

        // Consecutive clicks at same position could be double-click
        if i + 1 < actions.len() {
            if let (
                ActionKind::MouseClick { x: x1, y: y1, .. },
                ActionKind::MouseClick { x: x2, y: y2, .. },
            ) = (&action.kind, &actions[i + 1].kind)
            {
                if x1 == x2 && y1 == y2 {
                    hints.push(Hint {
                        severity: Severity::Info,
                        action_idx: Some(i),
                        message: "Consecutive clicks at same position — consider using double_click".into(),
                    });
                }
            }
        }

        // Disabled actions
        if !action.enabled {
            hints.push(Hint {
                severity: Severity::Info,
                action_idx: Some(i),
                message: "Disabled action — remove if no longer needed".into(),
            });
        }

        // Very high repeat count
        if action.repeat_count > 100 {
            hints.push(Hint {
                severity: Severity::Warning,
                action_idx: Some(i),
                message: format!("High repeat count ({}×) — consider using loop_block", action.repeat_count),
            });
        }

        // Mouse click at (0,0) is suspicious
        if let ActionKind::MouseClick { x: 0, y: 0, .. } = &action.kind {
            hints.push(Hint {
                severity: Severity::Warning,
                action_idx: Some(i),
                message: "Click at (0,0) — likely uninitialized coordinates".into(),
            });
        }

        // Empty type_text
        if let ActionKind::TypeText { text, .. } = &action.kind {
            if text.is_empty() {
                hints.push(Hint {
                    severity: Severity::Error,
                    action_idx: Some(i),
                    message: "Empty type_text — nothing will be typed".into(),
                });
            }
        }

        // Empty run_command
        if let ActionKind::RunCommand { command, .. } = &action.kind {
            if command.is_empty() {
                hints.push(Hint {
                    severity: Severity::Error,
                    action_idx: Some(i),
                    message: "Empty run_command — no command specified".into(),
                });
            }
        }
    }

    // Global hints
    let disabled_count = actions.iter().filter(|a| !a.enabled).count();
    if disabled_count > 3 {
        hints.push(Hint {
            severity: Severity::Info,
            action_idx: None,
            message: format!("{disabled_count} disabled actions — consider cleaning up"),
        });
    }

    if actions.len() > 50 {
        hints.push(Hint {
            severity: Severity::Info,
            action_idx: None,
            message: format!("{} actions — consider splitting into sub-macros with run_macro", actions.len()),
        });
    }

    hints
}
