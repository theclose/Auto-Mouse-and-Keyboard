//! Right panel — Tabbed layout: ▶ Controls | 🔍 Properties | 📋 Log
//!
//! Tab 1: Playback controls (loop, speed, step mode) + execution report
//! Tab 2: Properties of selected action (read-only params)
//! Tab 3: Application log (timestamped events)

use eframe::egui;
use amk_domain::action::ActionKind;
use crate::app::{AutoMacroApp, RunState};
use crate::theme;

pub fn draw(app: &mut AutoMacroApp, ui: &mut egui::Ui) {
    // Tab bar
    ui.horizontal(|ui| {
        if ui.selectable_label(app.right_tab == 0, "▶ Controls").clicked() {
            app.right_tab = 0;
        }
        if ui.selectable_label(app.right_tab == 1, "🔍 Properties").clicked() {
            app.right_tab = 1;
        }
        let log_label = if app.log_messages.is_empty() {
            "📋 Log".to_string()
        } else {
            format!("📋 Log ({})", app.log_messages.len())
        };
        if ui.selectable_label(app.right_tab == 2, log_label).clicked() {
            app.right_tab = 2;
        }
    });
    ui.separator();

    egui::ScrollArea::vertical().auto_shrink([false, false]).show(ui, |ui| {
        match app.right_tab {
            0 => draw_controls_tab(app, ui),
            1 => draw_properties_tab(app, ui),
            2 => draw_log_tab(app, ui),
            _ => {}
        }
    });
}

// ═══════════════════════════════════════════════════════════════════
// Tab 0: Controls
// ═══════════════════════════════════════════════════════════════════

fn draw_controls_tab(app: &mut AutoMacroApp, ui: &mut egui::Ui) {
    // ── Playback config ──
    ui.group(|ui| {
        ui.label(
            egui::RichText::new("⚙  Playback Config")
                .color(theme::ACCENT_LIGHT)
                .font(theme::font_button()),
        );
        ui.add_space(4.0);

        egui::Grid::new("playback_cfg")
            .num_columns(2)
            .spacing([12.0, 6.0])
            .show(ui, |ui| {
                ui.label("Loops:");
                let loop_prefix = if app.loop_count == 0 { "∞ " } else { "" };
                ui.add(egui::DragValue::new(&mut app.loop_count)
                    .range(0..=9999)
                    .speed(0.5)
                    .prefix(loop_prefix));
                ui.end_row();

                ui.label("Loop delay:");
                ui.add(egui::DragValue::new(&mut app.loop_delay)
                    .range(0..=60000)
                    .speed(10)
                    .suffix(" ms"));
                ui.end_row();

                ui.label("Speed:");
                ui.add(egui::Slider::new(&mut app.speed_factor, 0.1..=5.0)
                    .text("×")
                    .step_by(0.1));
                ui.end_row();

                ui.label("Stop on error:");
                ui.checkbox(&mut app.stop_on_error, "");
                ui.end_row();

                ui.label("Default delay:");
                ui.add(egui::DragValue::new(&mut app.default_delay)
                    .range(0..=10000)
                    .speed(10)
                    .suffix(" ms"));
                ui.end_row();
            });
    });

    ui.add_space(8.0);

    // ── Run state / report ──
    match app.run_state {
        RunState::Idle => draw_idle_report(app, ui),
        RunState::Running | RunState::Paused => draw_running_state(app, ui),
    }

    ui.add_space(8.0);

    // ── Quick tips ──
    ui.collapsing("💡 Shortcuts", |ui| {
        let tips = [
            ("Ctrl+N", "New macro"),
            ("Ctrl+O", "Open macro"),
            ("Ctrl+S", "Save macro"),
            ("Ctrl+Shift+S", "Save As"),
            ("Ctrl+Z/Y", "Undo / Redo"),
            ("Ctrl+C/V", "Copy / Paste action"),
            ("Ctrl+D", "Duplicate action"),
            ("Del", "Delete action"),
            ("Enter", "Edit action"),
            ("Space", "Toggle enable"),
            ("↑↓", "Navigate"),
            ("Ctrl+↑↓", "Reorder"),
            ("Ctrl+G", "Coordinate Picker"),
            ("Ctrl+H", "Optimizer"),
            ("F1", "Help"),
            ("Esc", "Close dialog"),
        ];
        egui::Grid::new("tips_grid")
            .num_columns(2)
            .spacing([8.0, 2.0])
            .show(ui, |ui| {
                for (key, desc) in tips {
                    ui.label(egui::RichText::new(key).color(theme::ACCENT_LIGHT).font(egui::FontId::monospace(10.0)));
                    ui.label(egui::RichText::new(desc).color(theme::TEXT_DIM).font(theme::font_small()));
                    ui.end_row();
                }
            });
    });
}

fn draw_idle_report(app: &AutoMacroApp, ui: &mut egui::Ui) {
    if let Some(ref report) = app.last_report {
        ui.group(|ui| {
            ui.label(
                egui::RichText::new("📊  Last Run Report")
                    .color(theme::ACCENT_LIGHT)
                    .font(theme::font_button()),
            );
            ui.add_space(4.0);

            egui::Grid::new("report_grid")
                .num_columns(2)
                .spacing([12.0, 4.0])
                .show(ui, |ui| {
                    ui.label(egui::RichText::new("Result:").color(theme::TEXT_SECONDARY));
                    let (icon, color) = match report.exit_reason {
                        amk_runtime::report::ExitReason::Completed => ("✅ Completed", theme::SUCCESS),
                        amk_runtime::report::ExitReason::UserStopped => ("⏹ Stopped", theme::WARNING),
                        amk_runtime::report::ExitReason::ErrorStopped => ("❌ Error", theme::ERROR),
                    };
                    ui.label(egui::RichText::new(icon).color(color));
                    ui.end_row();

                    ui.label(egui::RichText::new("Executed:").color(theme::TEXT_SECONDARY));
                    ui.label(format!("{}", report.actions_executed));
                    ui.end_row();

                    ui.label(egui::RichText::new("Succeeded:").color(theme::TEXT_SECONDARY));
                    ui.label(egui::RichText::new(format!("{}", report.actions_succeeded)).color(theme::SUCCESS));
                    ui.end_row();

                    if report.actions_failed > 0 {
                        ui.label(egui::RichText::new("Failed:").color(theme::TEXT_SECONDARY));
                        ui.label(egui::RichText::new(format!("{}", report.actions_failed)).color(theme::ERROR));
                        ui.end_row();
                    }

                    if report.actions_skipped > 0 {
                        ui.label(egui::RichText::new("Skipped:").color(theme::TEXT_SECONDARY));
                        ui.label(format!("{}", report.actions_skipped));
                        ui.end_row();
                    }

                    if report.loops_completed > 0 {
                        ui.label(egui::RichText::new("Loops:").color(theme::TEXT_SECONDARY));
                        ui.label(format!("{}", report.loops_completed));
                        ui.end_row();
                    }

                    ui.label(egui::RichText::new("Duration:").color(theme::TEXT_SECONDARY));
                    ui.label(format_elapsed(report.duration.as_secs_f64()));
                    ui.end_row();
                });
        });
    } else {
        ui.colored_label(theme::TEXT_DIM, "Ready to run. Press ▶ Run to start.");
    }
}

fn draw_running_state(app: &AutoMacroApp, ui: &mut egui::Ui) {
    ui.group(|ui| {
        let (text, color) = if app.run_state == RunState::Paused {
            ("⏸ PAUSED", theme::WARNING)
        } else {
            ("▶ RUNNING", theme::SUCCESS)
        };
        ui.label(egui::RichText::new(text).color(color).font(egui::FontId::proportional(16.0)));
        ui.add_space(4.0);

        let total = app.typed_actions.len();
        if total > 0 {
            ui.add(egui::ProgressBar::new(0.5).text(format!("{} actions", total)).animate(true));
        }
    });
}

// ═══════════════════════════════════════════════════════════════════
// Tab 1: Properties
// ═══════════════════════════════════════════════════════════════════

fn draw_properties_tab(app: &AutoMacroApp, ui: &mut egui::Ui) {
    // R6: Macro-level stats always shown
    if let Some(ref doc) = app.current_macro {
        ui.group(|ui| {
            ui.label(egui::RichText::new("📊 Macro Info").color(theme::ACCENT_LIGHT).font(theme::font_button()));
            ui.add_space(2.0);
            egui::Grid::new("macro_stats")
                .num_columns(2)
                .spacing([12.0, 3.0])
                .show(ui, |ui| {
                    prop_row(ui, "Name", &doc.name);
                    prop_row(ui, "Total", &format!("{} actions", app.typed_actions.len()));
                    let enabled = app.typed_actions.iter().filter(|a| a.enabled).count();
                    let disabled = app.typed_actions.len() - enabled;
                    prop_row(ui, "Enabled", &format!("{enabled}"));
                    if disabled > 0 { prop_row(ui, "Disabled", &format!("{disabled}")); }
                    prop_row(ui, "Loops", &(if app.loop_count == 0 { "∞".into() } else { format!("{}", app.loop_count) }).to_string());
                    if let Some(ref path) = app.current_file_path {
                        let name = std::path::Path::new(path).file_name()
                            .map(|n| n.to_string_lossy().to_string())
                            .unwrap_or_else(|| path.clone());
                        prop_row(ui, "File", &name);
                    }
                });
        });
        ui.add_space(4.0);
    }

    let Some(idx) = app.selected_action_idx else {
        ui.colored_label(theme::TEXT_DIM, "Select an action to view details.");
        return;
    };
    if idx >= app.typed_actions.len() { return; }
    let action = &app.typed_actions[idx];

    // Common props
    ui.group(|ui| {
        ui.label(egui::RichText::new(format!("Action #{}", idx + 1)).color(theme::ACCENT_LIGHT).font(theme::font_button()));
        ui.add_space(4.0);

        egui::Grid::new("props_common")
            .num_columns(2)
            .spacing([12.0, 3.0])
            .show(ui, |ui| {
                let (name, icon) = action_info_mini(&action.kind);
                prop_row(ui, "Type", &format!("{icon} {name}"));
                prop_row(ui, "Enabled", if action.enabled { "✅ Yes" } else { "❌ No" });
                if action.delay_after > 0 { prop_row(ui, "Delay After", &format!("{}ms", action.delay_after)); }
                if action.repeat_count > 1 { prop_row(ui, "Repeat", &format!("{}×", action.repeat_count)); }
                if !action.description.is_empty() { prop_row(ui, "Note", &action.description); }
            });
    });

    ui.add_space(4.0);

    // Type-specific params
    ui.group(|ui| {
        ui.label(egui::RichText::new("Parameters").color(theme::TEXT_SECONDARY).font(theme::font_small()));
        ui.add_space(2.0);
        draw_kind_params(&action.kind, ui);
    });

    ui.add_space(8.0);

    // Variable inspector
    super::variable_inspector::draw(app, ui);
}

fn draw_kind_params(kind: &ActionKind, ui: &mut egui::Ui) {
    egui::Grid::new("props_params")
        .num_columns(2)
        .spacing([12.0, 3.0])
        .show(ui, |ui| {
            match kind {
                ActionKind::Delay { duration_ms } => { prop_row(ui, "Duration", &format!("{}ms", duration_ms)); }
                ActionKind::MouseClick { x, y, button, clicks } => {
                    prop_row(ui, "Position", &format!("({x}, {y})"));
                    prop_row(ui, "Button", &format!("{button:?}"));
                    prop_row(ui, "Clicks", &format!("{clicks}"));
                }
                ActionKind::MouseMove { x, y, duration_ms } => {
                    prop_row(ui, "Target", &format!("({x}, {y})"));
                    prop_row(ui, "Duration", &format!("{}ms", duration_ms));
                }
                ActionKind::MouseDrag { start_x, start_y, end_x, end_y, duration_ms, button } => {
                    prop_row(ui, "From", &format!("({start_x}, {start_y})"));
                    prop_row(ui, "To", &format!("({end_x}, {end_y})"));
                    prop_row(ui, "Duration", &format!("{}ms", duration_ms));
                    prop_row(ui, "Button", &format!("{button:?}"));
                }
                ActionKind::KeyPress { key, duration_ms } => {
                    prop_row(ui, "Key", key);
                    prop_row(ui, "Hold", &format!("{}ms", duration_ms));
                }
                ActionKind::KeyCombo { keys } | ActionKind::Hotkey { keys } => {
                    prop_row(ui, "Keys", &keys.join(" + "));
                }
                ActionKind::TypeText { text, interval_ms } => {
                    prop_row(ui, "Text", &format!("\"{}\"", truncate(text, 40)));
                    prop_row(ui, "Interval", &format!("{:.0}ms", interval_ms));
                }
                ActionKind::SetVariable { name, value } => {
                    prop_row(ui, "Name", name);
                    prop_row(ui, "Value", value);
                }
                ActionKind::Comment { text } => { prop_row(ui, "Text", text); }
                ActionKind::RunCommand { command, wait, capture_output } => {
                    prop_row(ui, "Command", command);
                    prop_row(ui, "Wait", &format!("{wait}"));
                    if !capture_output.is_empty() { prop_row(ui, "Output→", capture_output); }
                }
                ActionKind::ActivateWindow { title, match_type } => {
                    prop_row(ui, "Title", title);
                    prop_row(ui, "Match", match_type);
                }
                ActionKind::IfVariable { variable, operator, value, then_actions, else_actions } => {
                    prop_row(ui, "Condition", &format!("{variable} {operator} {value}"));
                    prop_row(ui, "Then", &format!("{} actions", then_actions.len()));
                    if !else_actions.is_empty() { prop_row(ui, "Else", &format!("{} actions", else_actions.len())); }
                }
                ActionKind::LoopBlock { count, children } => {
                    let count_str = if *count <= 0 { "∞".to_string() } else { format!("{count}") };
                    prop_row(ui, "Iterations", &count_str);
                    prop_row(ui, "Body", &format!("{} actions", children.len()));
                }
                ActionKind::WaitForImage { image_path, confidence, timeout_ms, .. } => {
                    prop_row(ui, "Image", image_path);
                    prop_row(ui, "Confidence", &format!("{:.0}%", confidence * 100.0));
                    prop_row(ui, "Timeout", &format!("{}ms", timeout_ms));
                }
                ActionKind::ClickOnImage { image_path, confidence, button, .. } => {
                    prop_row(ui, "Image", image_path);
                    prop_row(ui, "Confidence", &format!("{:.0}%", confidence * 100.0));
                    prop_row(ui, "Button", &format!("{button:?}"));
                }
                ActionKind::RunMacro { macro_path } => { prop_row(ui, "Macro", macro_path); }
                ActionKind::LogToFile { file_path, message, append } => {
                    prop_row(ui, "File", file_path);
                    prop_row(ui, "Message", &truncate(message, 40));
                    prop_row(ui, "Append", &format!("{append}"));
                }
                _ => {
                    ui.label(egui::RichText::new("(no detailed params)").color(theme::TEXT_DIM));
                    ui.end_row();
                }
            }
        });
}

// ═══════════════════════════════════════════════════════════════════
// Tab 2: Log
// ═══════════════════════════════════════════════════════════════════

fn draw_log_tab(app: &mut AutoMacroApp, ui: &mut egui::Ui) {
    ui.horizontal(|ui| {
        ui.label(egui::RichText::new("📋  Application Log").color(theme::ACCENT_LIGHT).font(theme::font_button()));
        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
            if ui.small_button("🗑 Clear").clicked() {
                app.log_messages.clear();
            }
            ui.label(egui::RichText::new(format!("{} entries", app.log_messages.len())).color(theme::TEXT_DIM).font(theme::font_small()));
        });
    });
    ui.separator();

    if app.log_messages.is_empty() {
        ui.add_space(20.0);
        ui.colored_label(theme::TEXT_DIM, "No log entries yet.");
        ui.colored_label(theme::TEXT_DIM, "Actions and events will appear here.");
        return;
    }

    // Show log in reverse order (newest first)
    for msg in app.log_messages.iter().rev() {
        ui.label(egui::RichText::new(msg).color(theme::TEXT_SECONDARY).font(egui::FontId::monospace(10.0)));
    }
}

// ═══════════════════════════════════════════════════════════════════
// Context Menu (called from action_tree)
// ═══════════════════════════════════════════════════════════════════

pub fn draw_context_menu(app: &mut AutoMacroApp, ui: &mut egui::Ui) {
    let mut close = false;
    if ui.button("✏  Edit").clicked() {
        app.edit_selected_action();
        close = true;
    }
    ui.separator();
    if ui.button("📋  Copy (Ctrl+C)").clicked() {
        app.copy_selected_action();
        close = true;
    }
    if ui.add_enabled(!app.copied_actions.is_empty(), egui::Button::new("📌  Paste (Ctrl+V)")).clicked() {
        app.paste_actions();
        close = true;
    }
    if ui.button("🔁  Duplicate (Ctrl+D)").clicked() {
        app.duplicate_selected_action();
        close = true;
    }
    ui.separator();
    if ui.button("⬆  Move Up").clicked() {
        app.move_action_up();
        close = true;
    }
    if ui.button("⬇  Move Down").clicked() {
        app.move_action_down();
        close = true;
    }
    ui.separator();
    if ui.button("✅  Enable All").clicked() {
        app.enable_all_actions();
        close = true;
    }
    if ui.button("⬜  Disable All").clicked() {
        app.disable_all_actions();
        close = true;
    }
    ui.separator();
    if ui.button("🗑  Delete (Del)").clicked() {
        app.delete_selected_action();
        close = true;
    }
    ui.separator();
    // Debugger: toggle breakpoint
    if let Some(idx) = app.selected_action_idx {
        let has_bp = app.debugger.has_breakpoint(idx);
        let bp_label = if has_bp { "🔴  Remove Breakpoint" } else { "⭕  Set Breakpoint" };
        if ui.button(bp_label).clicked() {
            app.debugger.toggle_breakpoint(idx);
            close = true;
        }
    }
    if close {
        app.show_context_menu = false;
    }
}

// ═══════════════════════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════════════════════

fn prop_row(ui: &mut egui::Ui, label: &str, value: &str) {
    ui.label(egui::RichText::new(format!("{label}:")).color(theme::TEXT_DIM).font(theme::font_small()));
    ui.label(egui::RichText::new(value).font(theme::font_small()));
    ui.end_row();
}

fn action_info_mini(kind: &ActionKind) -> (String, &'static str) {
    match kind {
        ActionKind::Delay { .. } => ("Delay".into(), "⏱"),
        ActionKind::MouseClick { .. } => ("Mouse Click".into(), "🖱"),
        ActionKind::MouseDoubleClick { .. } => ("Double Click".into(), "🖱"),
        ActionKind::MouseRightClick { .. } => ("Right Click".into(), "🖱"),
        ActionKind::MouseMove { .. } => ("Mouse Move".into(), "🖱"),
        ActionKind::MouseDrag { .. } => ("Mouse Drag".into(), "🖱"),
        ActionKind::MouseScroll { .. } => ("Mouse Scroll".into(), "🖱"),
        ActionKind::KeyPress { .. } => ("Key Press".into(), "⌨"),
        ActionKind::KeyCombo { .. } => ("Key Combo".into(), "⌨"),
        ActionKind::TypeText { .. } => ("Type Text".into(), "⌨"),
        ActionKind::Hotkey { .. } => ("Hotkey".into(), "⌨"),
        ActionKind::SetVariable { .. } => ("Set Variable".into(), "📌"),
        ActionKind::SplitString { .. } => ("Split String".into(), "✂"),
        ActionKind::Comment { .. } => ("Comment".into(), "💬"),
        ActionKind::Group { .. } => ("Group".into(), "📂"),
        ActionKind::RunCommand { .. } => ("Run Command".into(), "⚙"),
        ActionKind::LogToFile { .. } => ("Log to File".into(), "📝"),
        ActionKind::ReadFileLine { .. } => ("Read File Line".into(), "📖"),
        ActionKind::WriteToFile { .. } => ("Write to File".into(), "💾"),
        ActionKind::ReadClipboard { .. } => ("Read Clipboard".into(), "📋"),
        ActionKind::ActivateWindow { .. } => ("Activate Window".into(), "🪟"),
        ActionKind::IfVariable { .. } => ("If Variable".into(), "🔀"),
        ActionKind::IfPixelColor { .. } => ("If Pixel Color".into(), "🔀"),
        ActionKind::IfImageFound { .. } => ("If Image Found".into(), "🔀"),
        ActionKind::LoopBlock { .. } => ("Loop Block".into(), "🔁"),
        ActionKind::RunMacro { .. } => ("Run Macro".into(), "🔗"),
        ActionKind::CheckPixelColor { .. } => ("Check Pixel".into(), "🎨"),
        ActionKind::WaitForColor { .. } => ("Wait for Color".into(), "🎨"),
        ActionKind::WaitForImage { .. } => ("Wait for Image".into(), "🖼"),
        ActionKind::ClickOnImage { .. } => ("Click on Image".into(), "🖼"),
        ActionKind::ImageExists { .. } => ("Image Exists".into(), "🖼"),
        ActionKind::TakeScreenshot { .. } => ("Screenshot".into(), "📸"),
        ActionKind::CaptureText { .. } => ("Capture Text".into(), "🔍"),
        ActionKind::SecureTypeText { .. } => ("Secure Type".into(), "🔒"),
        ActionKind::StealthClick { .. } => ("Stealth Click".into(), "👻"),
        ActionKind::StealthType { .. } => ("Stealth Type".into(), "👻"),
    }
}

fn format_elapsed(secs: f64) -> String {
    if secs < 1.0 { format!("{:.0}ms", secs * 1000.0) }
    else if secs < 60.0 { format!("{:.1}s", secs) }
    else { format!("{:.0}m {:.0}s", secs / 60.0, secs % 60.0) }
}

fn truncate(s: &str, max: usize) -> String {
    if s.len() <= max { s.to_owned() } else { format!("{}…", &s[..max.min(s.len()) - 1]) }
}
