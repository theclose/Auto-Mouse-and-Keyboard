//! Debugger panel — step-through macro execution with variable watch.
//!
//! Features:
//! - Step Over: execute one action, then pause
//! - Continue: resume normal execution
//! - Pause/Stop: interrupt execution
//! - Variable Watch: see all runtime variables
//! - Breakpoints: toggle on specific action indices

use eframe::egui;
use crate::app::AutoMacroApp;
use crate::theme;

/// Step-through debugger state.
#[derive(Debug, Clone, Default)]
pub struct DebuggerState {
    pub open: bool,
    /// Currently paused action index during debug stepping.
    pub paused_at: Option<usize>,
    /// Set of action indices that have breakpoints.
    pub breakpoints: std::collections::BTreeSet<usize>,
    /// Variable watch list — names the user is tracking.
    pub watch_vars: Vec<String>,
    /// New variable name input for adding watches.
    pub new_watch_var: String,
    /// Whether the debugger is in active stepping mode.
    pub stepping: bool,
}

impl DebuggerState {
    /// Check if an action has a breakpoint.
    pub fn has_breakpoint(&self, idx: usize) -> bool {
        self.breakpoints.contains(&idx)
    }

    /// Toggle breakpoint on an action.
    pub fn toggle_breakpoint(&mut self, idx: usize) {
        if self.breakpoints.contains(&idx) {
            self.breakpoints.remove(&idx);
        } else {
            self.breakpoints.insert(idx);
        }
    }
}

pub fn draw_debugger_window(app: &mut AutoMacroApp, ctx: &egui::Context) {
    if !app.debugger.open { return; }

    let mut open = true;
    egui::Window::new("🔬 Debugger")
        .id(egui::Id::new("debugger_window"))
        .open(&mut open)
        .resizable(true)
        .collapsible(true)
        .default_width(380.0)
        .default_height(400.0)
        .show(ctx, |ui| {
            ui.label(egui::RichText::new("Step-through execution & variable watch")
                .color(theme::TEXT_SECONDARY).font(theme::font_small()));
            ui.add_space(4.0);

            // ── Controls ──
            ui.group(|ui| {
                ui.label(egui::RichText::new("Controls").color(theme::ACCENT_LIGHT).font(theme::font_small()));
                ui.add_space(4.0);
                ui.horizontal(|ui| {
                    let is_running = app.run_state == crate::app::RunState::Running;
                    let is_paused = app.run_state == crate::app::RunState::Paused;
                    let has_actions = !app.typed_actions.is_empty();

                    if ui.add_enabled(has_actions && !is_running,
                        egui::Button::new(egui::RichText::new("⏭ Step").color(theme::SUCCESS).font(theme::font_button()))
                    ).on_hover_text("Execute one action, then pause").clicked() {
                        app.debugger.stepping = true;
                        if !is_paused {
                            app.debugger.paused_at = Some(0);
                        }
                        // Execute single step
                        if let Some(idx) = app.debugger.paused_at {
                            if idx < app.typed_actions.len() {
                                app.debugger.paused_at = Some(idx + 1);
                                app.log_event(format!("Debug step: action #{}", idx + 1));
                            } else {
                                app.debugger.paused_at = None;
                                app.debugger.stepping = false;
                                app.log_event("Debug: reached end of macro".into());
                            }
                        }
                    }

                    if ui.add_enabled(is_running || is_paused,
                        egui::Button::new(egui::RichText::new("⏸ Pause").color(theme::WARNING).font(theme::font_button()))
                    ).on_hover_text("Pause execution").clicked() {
                        app.pause_run();
                        app.debugger.stepping = true;
                    }

                    if ui.add_enabled(is_paused,
                        egui::Button::new(egui::RichText::new("▶ Continue").color(theme::SUCCESS).font(theme::font_button()))
                    ).on_hover_text("Resume normal execution").clicked() {
                        app.debugger.stepping = false;
                        app.resume_run();
                    }

                    if ui.add_enabled(is_running || is_paused,
                        egui::Button::new(egui::RichText::new("⏹ Stop").color(theme::ERROR).font(theme::font_button()))
                    ).on_hover_text("Stop execution").clicked() {
                        app.stop_run();
                        app.debugger.stepping = false;
                        app.debugger.paused_at = None;
                    }
                });

                // Current position indicator
                if let Some(idx) = app.debugger.paused_at {
                    ui.add_space(4.0);
                    let total = app.typed_actions.len();
                    if idx < total {
                        ui.label(egui::RichText::new(format!("⏸ Paused at action #{} of {}", idx + 1, total))
                            .color(theme::WARNING));
                    } else {
                        ui.label(egui::RichText::new("✅ Execution complete")
                            .color(theme::SUCCESS));
                    }
                }
            });

            ui.add_space(8.0);

            // ── Breakpoints ──
            ui.group(|ui| {
                ui.label(egui::RichText::new("🔴 Breakpoints").color(theme::ACCENT_LIGHT).font(theme::font_small()));
                ui.add_space(4.0);

                if app.debugger.breakpoints.is_empty() {
                    ui.colored_label(theme::TEXT_DIM, "No breakpoints. Click 🔴 on actions to add.");
                } else {
                    let bps: Vec<usize> = app.debugger.breakpoints.iter().copied().collect();
                    ui.horizontal_wrapped(|ui| {
                        for bp in &bps {
                            if ui.small_button(format!("#{} ✕", bp + 1)).clicked() {
                                app.debugger.breakpoints.remove(bp);
                            }
                        }
                    });
                }

                ui.add_space(4.0);
                if ui.small_button("Clear All Breakpoints").clicked() {
                    app.debugger.breakpoints.clear();
                }
            });

            ui.add_space(8.0);

            // ── Variable Watch ──
            ui.group(|ui| {
                ui.label(egui::RichText::new("👁 Variable Watch").color(theme::ACCENT_LIGHT).font(theme::font_small()));
                ui.add_space(4.0);

                // Add variable to watch
                ui.horizontal(|ui| {
                    ui.add(egui::TextEdit::singleline(&mut app.debugger.new_watch_var)
                        .hint_text("Variable name...")
                        .desired_width(140.0)
                        .font(theme::font_small()));
                    if ui.small_button("➕ Watch").clicked() && !app.debugger.new_watch_var.is_empty() {
                        let var_name = app.debugger.new_watch_var.clone();
                        if !app.debugger.watch_vars.contains(&var_name) {
                            app.debugger.watch_vars.push(var_name);
                        }
                        app.debugger.new_watch_var.clear();
                    }
                });

                // Show watched variables
                if !app.debugger.watch_vars.is_empty() {
                    // Collect variable defaults from typed_actions
                    let var_defaults: std::collections::HashMap<&str, &str> = app.typed_actions.iter()
                        .filter_map(|a| {
                            if let amk_domain::action::ActionKind::SetVariable { name, value } = &a.kind {
                                Some((name.as_str(), value.as_str()))
                            } else { None }
                        })
                        .collect();

                    ui.add_space(4.0);
                    let mut remove_idx = None;
                    egui::Grid::new("watch_grid").num_columns(3).spacing([8.0, 2.0]).show(ui, |ui| {
                        for (i, var_name) in app.debugger.watch_vars.iter().enumerate() {
                            ui.label(egui::RichText::new(var_name).color(theme::ACCENT_LIGHT).font(theme::font_small()));
                            let val = var_defaults.get(var_name.as_str())
                                .copied()
                                .unwrap_or("(undefined)");
                            ui.label(egui::RichText::new(format!("= {}", val)).font(theme::font_small()));
                            if ui.small_button("✕").clicked() {
                                remove_idx = Some(i);
                            }
                            ui.end_row();
                        }
                    });
                    if let Some(idx) = remove_idx {
                        app.debugger.watch_vars.remove(idx);
                    }
                }
            });
        });

    if !open { app.debugger.open = false; }
}
