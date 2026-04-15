//! Action tree panel — shows typed actions in an interactive, selectable list.
//!
//! Features:
//! - Click to select, double-click to edit, right-click to toggle enable
//! - Arrow keys for navigation, Enter to edit, Space to toggle, Del to delete
//! - Alternating row backgrounds for readability
//! - Left accent bar on selected action
//! - Color-coded icons per action type

use eframe::egui;
use amk_domain::action::{ActionKind, TypedAction};
use crate::app::AutoMacroApp;
use crate::theme;

pub fn draw(app: &mut AutoMacroApp, ui: &mut egui::Ui) {
    ui.vertical(|ui| {
        // Header with action count + filter
        ui.horizontal(|ui| {
            ui.label(
                egui::RichText::new("📋  Actions")
                    .font(theme::font_header())
                    .color(theme::TEXT_PRIMARY),
            );
            if !app.typed_actions.is_empty() {
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    ui.label(
                        egui::RichText::new(format!("{} total", app.typed_actions.len()))
                            .color(theme::TEXT_DIM)
                            .font(theme::font_small()),
                    );
                    // Count enabled vs disabled
                    let enabled = app.typed_actions.iter().filter(|a| a.enabled).count();
                    let disabled = app.typed_actions.len() - enabled;
                    if disabled > 0 {
                        ui.label(
                            egui::RichText::new(format!("({disabled} disabled)"))
                                .color(theme::TEXT_DIM)
                                .font(theme::font_small()),
                        );
                    }
                });
            }
        });
        ui.add_space(2.0);
        ui.separator();

        // Search/filter input
        if !app.typed_actions.is_empty() {
            ui.horizontal(|ui| {
                ui.label(egui::RichText::new("🔍").font(theme::font_small()));
                let resp = ui.add(
                    egui::TextEdit::singleline(&mut app.action_filter)
                        .hint_text("Filter actions...")
                        .desired_width(ui.available_width() - 30.0)
                        .font(theme::font_small()),
                );
                if !app.action_filter.is_empty()
                    && ui.small_button("✕").clicked() {
                        app.action_filter.clear();
                        resp.request_focus();
                    }
            });
            ui.add_space(2.0);
        }

        if app.typed_actions.is_empty() {
            draw_empty_state(app, ui);
            return;
        }

        // Collect click events to avoid borrow conflicts
        let mut clicked_idx: Option<usize> = None;
        let mut edit_idx: Option<usize> = None;
        let mut context_menu_idx: Option<usize> = None;
        let action_count = app.typed_actions.len();
        let filter = app.action_filter.to_lowercase();

        // Collect modifier state before the iterator
        let shift_held = ui.ctx().input(|i| i.modifiers.shift);
        let ctrl_held = ui.ctx().input(|i| i.modifiers.ctrl);

        egui::ScrollArea::vertical()
            .auto_shrink([false, false])
            .show(ui, |ui| {
                let selected = app.selected_action_idx;
                for (i, action) in app.typed_actions.iter().enumerate() {
                    // Filter: skip non-matching actions
                    if !filter.is_empty() {
                        let (name, _, _) = action_info(&action.kind);
                        if !name.to_lowercase().contains(&filter) {
                            continue;
                        }
                    }

                    let is_primary = selected == Some(i);
                    let is_multi = app.selected_actions.contains(&i);
                    let is_selected = is_primary || is_multi;
                    let is_even = i % 2 == 0;
                    let has_bp = app.debugger.has_breakpoint(i);
                    let resp = draw_action_row(action, i, is_selected, is_even, has_bp, ui);

                    if resp.clicked() {
                        clicked_idx = Some(i);
                    }
                    if resp.double_clicked() {
                        edit_idx = Some(i);
                    }
                    if resp.secondary_clicked() {
                        clicked_idx = Some(i);
                        context_menu_idx = Some(i);
                    }
                }
            });

        // Show "no matches" hint when filter removes everything
        if !filter.is_empty() && clicked_idx.is_none() && edit_idx.is_none() && context_menu_idx.is_none() {
            // Check if any row was actually rendered
            let visible = app.typed_actions.iter().any(|a| {
                let (name, _, _) = action_info(&a.kind);
                name.to_lowercase().contains(&filter)
            });
            if !visible {
                ui.add_space(20.0);
                ui.colored_label(theme::TEXT_DIM, format!("No actions matching '{}'", app.action_filter));
            }
        }

        // Apply click after iteration (no borrow conflict)
        if let Some(idx) = clicked_idx {
            if shift_held {
                // Shift+Click: range select from anchor to clicked index
                if let Some(anchor) = app.selected_action_idx {
                    let lo = anchor.min(idx);
                    let hi = anchor.max(idx);
                    app.selected_actions.clear();
                    for j in lo..=hi {
                        app.selected_actions.insert(j);
                    }
                } else {
                    app.selected_action_idx = Some(idx);
                    app.selected_actions.clear();
                    app.selected_actions.insert(idx);
                }
            } else if ctrl_held {
                // Ctrl+Click: toggle individual selection
                if app.selected_actions.contains(&idx) {
                    app.selected_actions.remove(&idx);
                    if app.selected_action_idx == Some(idx) {
                        app.selected_action_idx = app.selected_actions.iter().next().copied();
                    }
                } else {
                    app.selected_actions.insert(idx);
                    app.selected_action_idx = Some(idx);
                }
            } else {
                // Plain click: single select (clear multi)
                app.selected_action_idx = Some(idx);
                app.selected_actions.clear();
                app.selected_actions.insert(idx);
            }
        }
        if let Some(idx) = edit_idx {
            app.selected_action_idx = Some(idx);
            app.edit_selected_action();
        }
        if let Some(idx) = context_menu_idx {
            app.selected_action_idx = Some(idx);
            app.show_context_menu = true;
            app.context_menu_pos = ui.ctx().input(|i| i.pointer.interact_pos().unwrap_or_default());
        }

        // Context menu (rendered outside iterator loop to avoid borrow conflict)
        if app.show_context_menu {
            let menu_pos = app.context_menu_pos;
            let area_resp = egui::Area::new(egui::Id::new("action_ctx_menu"))
                .fixed_pos(menu_pos)
                .order(egui::Order::Foreground)
                .show(ui.ctx(), |ui| {
                    egui::Frame::popup(ui.style()).show(ui, |ui| {
                        ui.set_min_width(160.0);
                        super::execution_panel::draw_context_menu(app, ui);
                    });
                });
            // Close when clicking outside the menu
            if ui.ctx().input(|i| i.pointer.any_pressed()) {
                if let Some(pos) = ui.ctx().input(|i| i.pointer.interact_pos()) {
                    if !area_resp.response.rect.contains(pos) {
                        app.show_context_menu = false;
                    }
                }
            }
            // Also close on Escape
            if ui.ctx().input(|i| i.key_pressed(egui::Key::Escape)) {
                app.show_context_menu = false;
            }
        }

        // Keyboard shortcuts (only when editor is NOT open)
        if app.editing_action_idx.is_none() {
            let ctx = ui.ctx().clone();

            // Arrow key navigation
            if ctx.input(|i| i.key_pressed(egui::Key::ArrowUp)) {
                if let Some(idx) = app.selected_action_idx {
                    if idx > 0 {
                        app.selected_action_idx = Some(idx - 1);
                    }
                } else if action_count > 0 {
                    app.selected_action_idx = Some(action_count - 1);
                }
            }
            if ctx.input(|i| i.key_pressed(egui::Key::ArrowDown)) {
                if let Some(idx) = app.selected_action_idx {
                    if idx + 1 < action_count {
                        app.selected_action_idx = Some(idx + 1);
                    }
                } else if action_count > 0 {
                    app.selected_action_idx = Some(0);
                }
            }

            // Move with Ctrl+Arrow
            if ctx.input(|i| i.modifiers.ctrl && i.key_pressed(egui::Key::ArrowUp)) {
                app.move_action_up();
            }
            if ctx.input(|i| i.modifiers.ctrl && i.key_pressed(egui::Key::ArrowDown)) {
                app.move_action_down();
            }

            if ctx.input(|i| i.key_pressed(egui::Key::Delete)) {
                app.delete_selected_action();
            }
            if ctx.input(|i| i.key_pressed(egui::Key::Enter)) {
                app.edit_selected_action();
            }
            if ctx.input(|i| i.key_pressed(egui::Key::Space)) {
                app.toggle_selected_action();
            }
        }
    });
}

fn draw_empty_state(app: &mut AutoMacroApp, ui: &mut egui::Ui) {
    ui.vertical_centered(|ui| {
        ui.add_space(60.0);
        ui.label(
            egui::RichText::new("No actions loaded.")
                .color(theme::TEXT_DIM)
                .font(egui::FontId::proportional(16.0)),
        );
        ui.add_space(8.0);
        ui.label(
            egui::RichText::new("Select a macro from the left panel\nor click ➕ to add actions.")
                .color(theme::TEXT_DIM)
                .font(egui::FontId::proportional(13.0)),
        );
        ui.add_space(16.0);
        if ui.button(
            egui::RichText::new("📄  New Macro")
                .color(theme::ACCENT_LIGHT)
                .font(theme::font_button()),
        ).clicked() {
            app.new_macro();
        }
    });
}

fn draw_action_row(
    action: &TypedAction,
    index: usize,
    is_selected: bool,
    is_even: bool,
    has_breakpoint: bool,
    ui: &mut egui::Ui,
) -> egui::Response {
    let (name, icon, _children) = action_info(&action.kind);
    let color = theme::action_color(&name);
    let row_height = 30.0;

    // Alternating row background
    let base_bg = if is_even {
        egui::Color32::from_rgba_premultiplied(38, 38, 54, 255) // BG_CARD
    } else {
        egui::Color32::from_rgba_premultiplied(34, 34, 48, 255) // slightly darker
    };
    let bg = if is_selected { theme::BG_SELECTED } else { base_bg };

    let resp = ui.allocate_ui_with_layout(
        egui::Vec2::new(ui.available_width(), row_height),
        egui::Layout::left_to_right(egui::Align::Center),
        |ui| {
            let rect = ui.max_rect();
            let hovered = ui.rect_contains_pointer(rect);
            let fill = if hovered && !is_selected { theme::BG_HOVER } else { bg };

            // Background
            ui.painter().rect_filled(rect, 2.0, fill);

            // Left accent bar for selected
            if is_selected {
                let bar = egui::Rect::from_min_size(
                    rect.left_top(),
                    egui::vec2(3.0, rect.height()),
                );
                ui.painter().rect_filled(bar, 1.0, theme::ACCENT);
            }

            ui.add_space(if is_selected { 10.0 } else { 8.0 });

            // Enable indicator (colored dot)
            let dot_color = if action.enabled { color } else { theme::TEXT_DIM };
            ui.label(egui::RichText::new("●").color(dot_color).font(egui::FontId::proportional(8.0)));

            // Index number
            ui.label(
                egui::RichText::new(format!("{:>2}", index + 1))
                    .color(theme::TEXT_DIM)
                    .font(egui::FontId::monospace(10.0)),
            );

            // Icon + type name
            let name_color = if action.enabled { color } else { theme::TEXT_DIM };
            ui.label(
                egui::RichText::new(format!("{icon} {name}"))
                    .color(name_color)
                    .font(egui::FontId::proportional(12.5)),
            );

            // Description (params summary)
            let desc = action_description(&action.kind);
            if !desc.is_empty() {
                ui.label(
                    egui::RichText::new(desc)
                        .color(if action.enabled { theme::TEXT_SECONDARY } else { theme::TEXT_DIM })
                        .font(egui::FontId::proportional(11.0)),
                );
            }

            // Right-aligned badges
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                if has_breakpoint {
                    ui.label(egui::RichText::new("🔴").font(egui::FontId::proportional(8.0)));
                }
                if !action.enabled {
                    ui.label(
                        egui::RichText::new("OFF")
                            .color(theme::TEXT_DIM)
                            .font(egui::FontId::proportional(9.0)),
                    );
                }
                if action.delay_after > 0 {
                    ui.label(
                        egui::RichText::new(format!("+{}ms", action.delay_after))
                            .color(theme::TEXT_DIM)
                            .font(egui::FontId::proportional(9.0)),
                    );
                }
                if action.repeat_count > 1 {
                    ui.label(
                        egui::RichText::new(format!("×{}", action.repeat_count))
                            .color(theme::WARNING)
                            .font(egui::FontId::proportional(9.0)),
                    );
                }
            });
        },
    );

    resp.response.interact(egui::Sense::click())
}

fn action_info(kind: &ActionKind) -> (String, &'static str, Option<&Vec<TypedAction>>) {
    match kind {
        ActionKind::Delay { .. } => ("Delay".into(), "⏱", None),
        ActionKind::SetVariable { .. } => ("Set Variable".into(), "📌", None),
        ActionKind::SplitString { .. } => ("Split String".into(), "✂", None),
        ActionKind::Comment { .. } => ("Comment".into(), "💬", None),
        ActionKind::Group { name, children } => (format!("Group: {name}"), "📂", Some(children)),
        ActionKind::RunCommand { .. } => ("Run Command".into(), "⚙", None),
        ActionKind::LogToFile { .. } => ("Log to File".into(), "📝", None),
        ActionKind::ReadFileLine { .. } => ("Read File Line".into(), "📖", None),
        ActionKind::WriteToFile { .. } => ("Write to File".into(), "💾", None),
        ActionKind::ReadClipboard { .. } => ("Read Clipboard".into(), "📋", None),
        ActionKind::ActivateWindow { .. } => ("Activate Window".into(), "🪟", None),
        ActionKind::KeyPress { .. } => ("Key Press".into(), "⌨", None),
        ActionKind::KeyCombo { .. } => ("Key Combo".into(), "⌨", None),
        ActionKind::TypeText { .. } => ("Type Text".into(), "⌨", None),
        ActionKind::Hotkey { .. } => ("Hotkey".into(), "⌨", None),
        ActionKind::MouseClick { .. } => ("Mouse Click".into(), "🖱", None),
        ActionKind::MouseDoubleClick { .. } => ("Double Click".into(), "🖱", None),
        ActionKind::MouseRightClick { .. } => ("Right Click".into(), "🖱", None),
        ActionKind::MouseMove { .. } => ("Mouse Move".into(), "🖱", None),
        ActionKind::MouseDrag { .. } => ("Mouse Drag".into(), "🖱", None),
        ActionKind::MouseScroll { .. } => ("Mouse Scroll".into(), "🖱", None),
        ActionKind::CheckPixelColor { .. } => ("Check Pixel".into(), "🎨", None),
        ActionKind::WaitForColor { .. } => ("Wait for Color".into(), "🎨", None),
        ActionKind::WaitForImage { .. } => ("Wait for Image".into(), "🖼", None),
        ActionKind::ClickOnImage { .. } => ("Click on Image".into(), "🖼", None),
        ActionKind::ImageExists { .. } => ("Image Exists".into(), "🖼", None),
        ActionKind::TakeScreenshot { .. } => ("Screenshot".into(), "📸", None),
        ActionKind::CaptureText { .. } => ("Capture Text".into(), "🔍", None),
        ActionKind::SecureTypeText { .. } => ("Secure Type".into(), "🔒", None),
        ActionKind::RunMacro { .. } => ("Run Macro".into(), "🔗", None),
        ActionKind::StealthClick { .. } => ("Stealth Click".into(), "👻", None),
        ActionKind::StealthType { .. } => ("Stealth Type".into(), "👻", None),
        ActionKind::IfVariable { then_actions, .. } => ("If Variable".into(), "🔀", Some(then_actions)),
        ActionKind::IfPixelColor { then_actions, .. } => ("If Pixel".into(), "🔀", Some(then_actions)),
        ActionKind::IfImageFound { then_actions, .. } => ("If Image".into(), "🔀", Some(then_actions)),
        ActionKind::LoopBlock { children, .. } => ("Loop".into(), "🔁", Some(children)),
    }
}

fn action_description(kind: &ActionKind) -> String {
    match kind {
        ActionKind::Delay { duration_ms } => format_duration(*duration_ms),
        ActionKind::SetVariable { name, value } => format!("{name} = \"{value}\""),
        ActionKind::SplitString { input, delimiter, output_prefix, .. } => format!("{input} → '{delimiter}' → {output_prefix}"),
        ActionKind::Comment { text } => truncate(text, 45),
        ActionKind::MouseClick { x, y, button, clicks } => {
            let btn = match button { amk_domain::action::MouseButton::Right => "R", amk_domain::action::MouseButton::Middle => "M", _ => "" };
            if *clicks > 1 { format!("({x},{y}) {btn}×{clicks}") } else { format!("({x},{y}) {btn}") }
        }
        ActionKind::MouseDoubleClick { x, y, .. } => format!("({x},{y})"),
        ActionKind::MouseRightClick { x, y } => format!("({x},{y})"),
        ActionKind::MouseMove { x, y, duration_ms } => {
            if *duration_ms > 0 { format!("→({x},{y}) {duration_ms}ms") } else { format!("→({x},{y})") }
        }
        ActionKind::MouseDrag { start_x, start_y, end_x, end_y, .. } => format!("({start_x},{start_y})→({end_x},{end_y})"),
        ActionKind::MouseScroll { clicks, .. } => format!("{clicks} clicks"),
        ActionKind::KeyPress { key, duration_ms } => {
            if *duration_ms > 0 { format!("[{key}] hold {duration_ms}ms") } else { format!("[{key}]") }
        }
        ActionKind::KeyCombo { keys } | ActionKind::Hotkey { keys } => keys.join("+"),
        ActionKind::TypeText { text, .. } => format!("\"{}\"", truncate(text, 30)),
        ActionKind::SecureTypeText { .. } => "***".into(),
        ActionKind::RunCommand { command, .. } => truncate(command, 35),
        ActionKind::ActivateWindow { title, .. } => format!("\"{}\"", truncate(title, 30)),
        ActionKind::Group { name, children } => format!("{name} ({} items)", children.len()),
        ActionKind::LoopBlock { count, children } => {
            let c = if *count <= 0 { "∞".into() } else { format!("{count}") };
            format!("{c}× ({} items)", children.len())
        }
        ActionKind::IfVariable { variable, operator, value, then_actions, else_actions } => {
            let else_str = if else_actions.is_empty() { String::new() } else { format!(" else:{}", else_actions.len()) };
            format!("{variable}{operator}{value} then:{}{else_str}", then_actions.len())
        }
        ActionKind::IfPixelColor { x, y, expected_color, then_actions, .. } => {
            format!("({x},{y}) {expected_color} then:{}", then_actions.len())
        }
        ActionKind::IfImageFound { image_path, then_actions, .. } => {
            format!("{} then:{}", truncate(image_path, 20), then_actions.len())
        }
        ActionKind::RunMacro { macro_path } => truncate(macro_path, 30),
        ActionKind::LogToFile { file_path, .. } => truncate(file_path, 30),
        ActionKind::ReadFileLine { file_path, line_number, .. } => format!("{} L{}", truncate(file_path, 20), line_number),
        ActionKind::WriteToFile { file_path, .. } => truncate(file_path, 30),
        ActionKind::ReadClipboard { output_var } => format!("→ {output_var}"),
        ActionKind::TakeScreenshot { file_path, .. } => truncate(file_path, 30),
        ActionKind::CheckPixelColor { x, y, expected_color, result_var, .. } => format!("({x},{y}) {expected_color} → {result_var}"),
        ActionKind::WaitForColor { x, y, expected_color, timeout_ms, .. } => format!("({x},{y}) {expected_color} ({}ms)", timeout_ms),
        ActionKind::WaitForImage { image_path, timeout_ms, .. } => format!("{} ({}ms)", truncate(image_path, 20), timeout_ms),
        ActionKind::ClickOnImage { image_path, .. } => truncate(image_path, 30),
        ActionKind::ImageExists { image_path, result_var, .. } => format!("{} → {result_var}", truncate(image_path, 20)),
        ActionKind::CaptureText { output_var, .. } => format!("→ {output_var}"),
        ActionKind::StealthClick { window_title, x, y, .. } => format!("\"{}\" ({x},{y})", truncate(window_title, 15)),
        ActionKind::StealthType { window_title, text, .. } => format!("\"{}\" \"{}\"", truncate(window_title, 12), truncate(text, 12)),
    }
}

fn format_duration(ms: u32) -> String {
    if ms < 1000 { format!("{ms}ms") }
    else if ms < 60000 { format!("{:.1}s", ms as f64 / 1000.0) }
    else { format!("{:.0}m{:.0}s", ms as f64 / 60000.0, (ms % 60000) as f64 / 1000.0) }
}

fn truncate(s: &str, max: usize) -> String {
    if s.len() <= max { s.to_owned() } else { format!("{}…", &s[..max - 1]) }
}
