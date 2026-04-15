//! Action editor — egui window for editing a single RawAction's parameters.
//!
//! Opens as a modal-like window when editing_action_idx is Some.
//! Edits are applied directly to the MacroDocument's raw actions.

use eframe::egui;
use amk_schema::RawAction;
use crate::theme;

/// Draw the action editor window. Returns true if the window was closed.
pub fn draw_editor(
    ctx: &egui::Context,
    action: &mut RawAction,
    index: usize,
) -> EditorResult {
    let mut result = EditorResult::Open;

    let title = format!("Edit Action #{} — {}", index + 1, &action.action_type);

    egui::Window::new(title)
        .id(egui::Id::new("action_editor"))
        .resizable(true)
        .collapsible(false)
        .default_width(420.0)
        .default_height(350.0)
        .anchor(egui::Align2::CENTER_CENTER, [0.0, 0.0])
        .show(ctx, |ui| {
            egui::ScrollArea::vertical().show(ui, |ui| {
                ui.set_min_width(380.0);

                // ── Common fields ──
                ui.group(|ui| {
                    ui.label(egui::RichText::new("Common Settings").color(theme::ACCENT_LIGHT).font(theme::font_button()));
                    ui.add_space(4.0);

                    egui::Grid::new("common_grid")
                        .num_columns(2)
                        .spacing([12.0, 6.0])
                        .show(ui, |ui| {
                            ui.label("Type:");
                            ui.label(egui::RichText::new(&action.action_type).color(theme::ACCENT_LIGHT));
                            ui.end_row();

                            ui.label("Enabled:");
                            ui.checkbox(&mut action.enabled, "");
                            ui.end_row();

                            let mut delay = action.delay_after as i32;
                            ui.label("Delay After (ms):");
                            if ui.add(egui::DragValue::new(&mut delay).range(0..=60000).speed(10).suffix(" ms")).changed() {
                                action.delay_after = delay.max(0) as u32;
                            }
                            ui.end_row();

                            let mut repeat = action.repeat_count as i32;
                            ui.label("Repeat:");
                            if ui.add(egui::DragValue::new(&mut repeat).range(1..=9999).speed(0.5).suffix("×")).changed() {
                                action.repeat_count = repeat.max(1) as u32;
                            }
                            ui.end_row();

                            ui.label("Description:");
                            ui.add(egui::TextEdit::singleline(&mut action.description).desired_width(200.0));
                            ui.end_row();
                        });
                });

                ui.add_space(8.0);

                // ── Type-specific params ──
                ui.group(|ui| {
                    ui.label(egui::RichText::new("Parameters").color(theme::ACCENT_LIGHT).font(theme::font_button()));
                    ui.add_space(4.0);
                    draw_params(ui, &action.action_type.clone(), &mut action.params);
                });

                ui.add_space(12.0);

                // ── Buttons ──
                ui.horizontal(|ui| {
                    if ui.button(
                        egui::RichText::new("✅  Apply & Close").color(theme::SUCCESS).font(theme::font_button()),
                    ).clicked() {
                        result = EditorResult::Applied;
                    }
                    ui.add_space(16.0);
                    if ui.button(
                        egui::RichText::new("❌  Cancel").color(theme::ERROR).font(theme::font_button()),
                    ).clicked() {
                        result = EditorResult::Cancelled;
                    }
                });
            });
        });

    result
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum EditorResult {
    Open,
    Applied,
    Cancelled,
}

// ── Parameter editors per action type ────────────────────────────────────

fn draw_params(ui: &mut egui::Ui, action_type: &str, params: &mut serde_json::Value) {
    match action_type {
        "delay" => {
            param_i32(ui, params, "ms", "Duration (ms)", 0, 300_000, 10);
        }
        "mouse_click" => {
            param_xy(ui, params);
            param_button(ui, params);
            param_i32(ui, params, "clicks", "Clicks", 1, 10, 1);
        }
        "mouse_double_click" => {
            param_xy(ui, params);
            param_button(ui, params);
        }
        "mouse_right_click" => {
            param_xy(ui, params);
        }
        "mouse_move" => {
            param_xy(ui, params);
            param_i32(ui, params, "duration", "Duration (ms)", 0, 10000, 10);
        }
        "mouse_drag" => {
            egui::Grid::new("drag_grid").num_columns(2).spacing([12.0, 6.0]).show(ui, |ui| {
                ui.label("Start X:"); param_drag_i32_inline(ui, params, "start_x"); ui.end_row();
                ui.label("Start Y:"); param_drag_i32_inline(ui, params, "start_y"); ui.end_row();
                ui.label("End X:"); param_drag_i32_inline(ui, params, "end_x"); ui.end_row();
                ui.label("End Y:"); param_drag_i32_inline(ui, params, "end_y"); ui.end_row();
            });
            param_i32(ui, params, "duration", "Duration (ms)", 0, 10000, 10);
            param_button(ui, params);
        }
        "mouse_scroll" => {
            param_xy(ui, params);
            param_i32(ui, params, "clicks", "Scroll clicks", -100, 100, 1);
        }
        "key_press" => {
            param_string(ui, params, "key", "Key");
            param_i32(ui, params, "duration", "Hold (ms)", 0, 10000, 10);
        }
        "key_combo" | "hotkey" => {
            param_key_list(ui, params, "keys", "Keys (comma-separated)");
        }
        "type_text" => {
            param_string_multiline(ui, params, "text", "Text");
            param_f64(ui, params, "interval", "Interval (sec)", 0.0, 1.0, 0.01);
        }
        "set_variable" => {
            param_string(ui, params, "name", "Variable Name");
            param_string(ui, params, "value", "Value");
        }
        "comment" => {
            param_string_multiline(ui, params, "text", "Comment Text");
        }
        "group" => {
            param_string(ui, params, "name", "Group Name");
        }
        "run_command" => {
            param_string(ui, params, "command", "Command");
            param_bool(ui, params, "wait", "Wait for completion");
            param_string(ui, params, "capture_output", "Output Variable");
        }
        "log_to_file" => {
            param_string(ui, params, "file_path", "File Path");
            param_string_multiline(ui, params, "message", "Message");
            param_bool(ui, params, "append", "Append mode");
        }
        "read_file_line" => {
            param_string(ui, params, "file_path", "File Path");
            param_i32(ui, params, "line_number", "Line Number", -1, 999999, 1);
            param_string(ui, params, "output_var", "Output Variable");
        }
        "write_to_file" => {
            param_string(ui, params, "file_path", "File Path");
            param_string_multiline(ui, params, "content", "Content");
            param_bool(ui, params, "append", "Append mode");
        }
        "read_clipboard" => {
            param_string(ui, params, "output_var", "Output Variable");
        }
        "activate_window" => {
            param_string(ui, params, "title", "Window Title");
            param_combo(ui, params, "match_type", "Match Type", &["contains", "exact", "regex"]);
        }
        "if_variable" => {
            param_string(ui, params, "variable", "Variable Name");
            param_combo(ui, params, "operator", "Operator", &["==", "!=", ">", "<", ">=", "<="]);
            param_string(ui, params, "value", "Compare Value");
            ui.label(egui::RichText::new("Sub-actions are edited inline in the tree.").color(theme::TEXT_DIM).font(theme::font_small()));
        }
        "if_pixel_color" => {
            param_xy(ui, params);
            param_string(ui, params, "color", "Expected Color (#RRGGBB)");
            param_i32(ui, params, "tolerance", "Tolerance", 0, 255, 1);
        }
        "if_image_found" => {
            param_string(ui, params, "image_path", "Image Path");
            param_f64(ui, params, "confidence", "Confidence", 0.0, 1.0, 0.05);
        }
        "loop_block" => {
            param_i32(ui, params, "count", "Iterations (-1=∞)", -1, 999999, 1);
        }
        "check_pixel_color" => {
            param_xy(ui, params);
            param_string(ui, params, "color", "Expected Color (#RRGGBB)");
            param_i32(ui, params, "tolerance", "Tolerance", 0, 255, 1);
            param_string(ui, params, "result_var", "Result Variable");
        }
        "wait_for_color" => {
            param_xy(ui, params);
            param_string(ui, params, "color", "Expected Color (#RRGGBB)");
            param_i32(ui, params, "tolerance", "Tolerance", 0, 255, 1);
            param_i32(ui, params, "timeout", "Timeout (ms)", 0, 300000, 100);
        }
        "wait_for_image" => {
            param_string(ui, params, "image_path", "Image Path");
            param_f64(ui, params, "confidence", "Confidence", 0.0, 1.0, 0.05);
            param_i32(ui, params, "timeout", "Timeout (ms)", 0, 300000, 100);
        }
        "click_on_image" => {
            param_string(ui, params, "image_path", "Image Path");
            param_f64(ui, params, "confidence", "Confidence", 0.0, 1.0, 0.05);
            param_i32(ui, params, "timeout", "Timeout (ms)", 0, 300000, 100);
            param_button(ui, params);
        }
        "take_screenshot" => {
            param_string(ui, params, "file_path", "Save Path");
        }
        "capture_text" => {
            param_string(ui, params, "output_var", "Output Variable");
            param_string(ui, params, "language", "Language (e.g. eng)");
        }
        "run_macro" => {
            param_string(ui, params, "macro_path", "Macro Path");
        }
        "stealth_click" => {
            param_string(ui, params, "window_title", "Window Title");
            param_xy(ui, params);
            param_button(ui, params);
        }
        "stealth_type" => {
            param_string(ui, params, "window_title", "Window Title");
            param_string(ui, params, "text", "Text");
            param_f64(ui, params, "interval", "Interval (sec)", 0.0, 1.0, 0.01);
        }
        "secure_type_text" => {
            param_string(ui, params, "text", "Text (encrypted on save)");
            param_f64(ui, params, "interval", "Interval (sec)", 0.0, 1.0, 0.01);
        }
        "split_string" => {
            param_string(ui, params, "input_var", "Input Variable");
            param_string(ui, params, "delimiter", "Delimiter");
            param_string(ui, params, "output_var", "Output Variable");
            param_i32(ui, params, "index", "Index", 0, 9999, 1);
        }
        "image_exists" => {
            param_string(ui, params, "image_path", "Image Path");
            param_f64(ui, params, "confidence", "Confidence", 0.0, 1.0, 0.05);
            param_string(ui, params, "result_var", "Result Variable");
        }
        _ => {
            ui.label(egui::RichText::new("No parameter editor for this action type.").color(theme::TEXT_DIM));
            // Show raw JSON for unknown types
            let json_str = serde_json::to_string_pretty(params).unwrap_or_default();
            ui.label(egui::RichText::new(json_str).font(theme::font_small()).color(theme::TEXT_SECONDARY));
        }
    }
}

// ── Param helper widgets ─────────────────────────────────────────────────

fn param_xy(ui: &mut egui::Ui, params: &mut serde_json::Value) {
    egui::Grid::new("xy_grid").num_columns(2).spacing([12.0, 6.0]).show(ui, |ui| {
        ui.label("X:");
        param_drag_i32_inline(ui, params, "x");
        ui.end_row();
        ui.label("Y:");
        param_drag_i32_inline(ui, params, "y");
        ui.end_row();
    });
}

fn param_drag_i32_inline(ui: &mut egui::Ui, params: &mut serde_json::Value, key: &str) {
    let mut val = params.get(key).and_then(|v| v.as_i64()).unwrap_or(0) as i32;
    if ui.add(egui::DragValue::new(&mut val).speed(1)).changed() {
        params[key] = serde_json::json!(val);
    }
}

fn param_i32(ui: &mut egui::Ui, params: &mut serde_json::Value, key: &str, label: &str, min: i32, max: i32, speed: i32) {
    let mut val = params.get(key).and_then(|v| v.as_i64()).unwrap_or(0) as i32;
    ui.horizontal(|ui| {
        ui.label(format!("{label}:"));
        if ui.add(egui::DragValue::new(&mut val).range(min..=max).speed(speed)).changed() {
            params[key] = serde_json::json!(val);
        }
    });
}

fn param_f64(ui: &mut egui::Ui, params: &mut serde_json::Value, key: &str, label: &str, min: f64, max: f64, speed: f64) {
    let mut val = params.get(key).and_then(|v| v.as_f64()).unwrap_or(0.0);
    ui.horizontal(|ui| {
        ui.label(format!("{label}:"));
        if ui.add(egui::DragValue::new(&mut val).range(min..=max).speed(speed)).changed() {
            params[key] = serde_json::json!(val);
        }
    });
}

fn param_string(ui: &mut egui::Ui, params: &mut serde_json::Value, key: &str, label: &str) {
    let mut val = params.get(key).and_then(|v| v.as_str()).unwrap_or("").to_string();
    ui.horizontal(|ui| {
        ui.label(format!("{label}:"));
        if ui.add(egui::TextEdit::singleline(&mut val).desired_width(200.0)).changed() {
            params[key] = serde_json::json!(val);
        }
    });
}

fn param_string_multiline(ui: &mut egui::Ui, params: &mut serde_json::Value, key: &str, label: &str) {
    let mut val = params.get(key).and_then(|v| v.as_str()).unwrap_or("").to_string();
    ui.label(format!("{label}:"));
    if ui.add(egui::TextEdit::multiline(&mut val).desired_width(f32::INFINITY).desired_rows(3)).changed() {
        params[key] = serde_json::json!(val);
    }
}

fn param_bool(ui: &mut egui::Ui, params: &mut serde_json::Value, key: &str, label: &str) {
    let mut val = params.get(key).and_then(|v| v.as_bool()).unwrap_or(false);
    if ui.checkbox(&mut val, label).changed() {
        params[key] = serde_json::json!(val);
    }
}

fn param_button(ui: &mut egui::Ui, params: &mut serde_json::Value) {
    let current = params.get("button").and_then(|v| v.as_str()).unwrap_or("left").to_string();
    let mut selected = match current.as_str() {
        "right" => 1,
        "middle" => 2,
        _ => 0,
    };
    ui.horizontal(|ui| {
        ui.label("Button:");
        if ui.selectable_value(&mut selected, 0, "Left").clicked()
            || ui.selectable_value(&mut selected, 1, "Right").clicked()
            || ui.selectable_value(&mut selected, 2, "Middle").clicked()
        {
            let btn = match selected { 1 => "right", 2 => "middle", _ => "left" };
            params["button"] = serde_json::json!(btn);
        }
    });
}

fn param_combo(ui: &mut egui::Ui, params: &mut serde_json::Value, key: &str, label: &str, options: &[&str]) {
    let current = params.get(key).and_then(|v| v.as_str()).unwrap_or(options[0]).to_string();
    ui.horizontal(|ui| {
        ui.label(format!("{label}:"));
        egui::ComboBox::from_id_salt(key)
            .selected_text(&current)
            .show_ui(ui, |ui| {
                for opt in options {
                    if ui.selectable_label(current == *opt, *opt).clicked() {
                        params[key] = serde_json::json!(*opt);
                    }
                }
            });
    });
}

fn param_key_list(ui: &mut egui::Ui, params: &mut serde_json::Value, key: &str, label: &str) {
    // Convert array to comma-separated string for editing
    let current = params.get(key)
        .and_then(|v| v.as_array())
        .map(|arr| arr.iter().filter_map(|v| v.as_str()).collect::<Vec<_>>().join(", "))
        .or_else(|| params.get(key).and_then(|v| v.as_str()).map(|s| s.to_string()))
        .unwrap_or_default();
    let mut val = current;
    ui.horizontal(|ui| {
        ui.label(format!("{label}:"));
        if ui.add(egui::TextEdit::singleline(&mut val).desired_width(200.0)).changed() {
            let keys: Vec<serde_json::Value> = val.split(',')
                .map(|s| serde_json::json!(s.trim()))
                .collect();
            params[key] = serde_json::json!(keys);
        }
    });
}
