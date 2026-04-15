//! Export panel — export macros in multiple formats.
//!
//! Supported formats:
//! - JSON (pretty) — shared/readable format
//! - Python script — pyautogui compatible
//! - Compact JSON — minified for clipboard

use eframe::egui;
use crate::app::AutoMacroApp;
use crate::theme;

/// Export state.
#[derive(Debug, Clone, Default)]
pub struct ExportState {
    pub open: bool,
    pub format_idx: usize, // 0=JSON, 1=Python, 2=Compact JSON
    pub preview: String,
    pub exported: bool,
}

pub fn draw_export_window(app: &mut AutoMacroApp, ctx: &egui::Context) {
    if !app.export.open { return; }

    let mut open = true;
    egui::Window::new("📤 Export Macro")
        .id(egui::Id::new("export_window"))
        .open(&mut open)
        .resizable(true)
        .collapsible(true)
        .default_width(500.0)
        .default_height(400.0)
        .show(ctx, |ui| {
            if app.current_macro.is_none() {
                ui.colored_label(theme::TEXT_DIM, "No macro loaded. Open a macro first.");
                return;
            }

            ui.label(egui::RichText::new("Export current macro to different formats")
                .color(theme::TEXT_SECONDARY).font(theme::font_small()));
            ui.add_space(4.0);

            // Format selector
            ui.horizontal(|ui| {
                ui.label("Format:");
                ui.selectable_value(&mut app.export.format_idx, 0, "📄 JSON (Pretty)");
                ui.selectable_value(&mut app.export.format_idx, 1, "🐍 Python Script");
                ui.selectable_value(&mut app.export.format_idx, 2, "📋 Compact JSON");
            });

            ui.add_space(8.0);

            // Generate preview
            ui.horizontal(|ui| {
                if ui.button(egui::RichText::new("🔄 Preview").color(theme::ACCENT_LIGHT).font(theme::font_small())).clicked() {
                    if let Some(ref doc) = app.current_macro {
                        app.export.preview = match app.export.format_idx {
                            0 => serde_json::to_string_pretty(doc).unwrap_or_default(),
                            1 => generate_python_script(doc),
                            2 => serde_json::to_string(doc).unwrap_or_default(),
                            _ => String::new(),
                        };
                        app.export.exported = false;
                    }
                }

                if !app.export.preview.is_empty() {
                    ui.label(egui::RichText::new(format!("({} chars)", app.export.preview.len()))
                        .color(theme::TEXT_DIM).font(theme::font_small()));
                }
            });

            // Preview area
            if !app.export.preview.is_empty() {
                ui.add_space(4.0);
                egui::ScrollArea::vertical().max_height(250.0).show(ui, |ui| {
                    ui.add(egui::TextEdit::multiline(&mut app.export.preview.as_str())
                        .code_editor()
                        .desired_width(f32::INFINITY)
                        .font(egui::FontId::monospace(10.0)));
                });
            }

            ui.add_space(8.0);

            // Actions
            ui.horizontal(|ui| {
                // Copy to clipboard
                if ui.add_enabled(!app.export.preview.is_empty(),
                    egui::Button::new(egui::RichText::new("📋 Copy to Clipboard").color(theme::SUCCESS).font(theme::font_small()))
                ).clicked() {
                    if let Ok(mut clipboard) = arboard::Clipboard::new() {
                        let _ = clipboard.set_text(&app.export.preview);
                        app.log_event("Exported to clipboard".into());
                        app.export.exported = true;
                    }
                }

                // Save to file
                let ext = match app.export.format_idx {
                    1 => "py",
                    _ => "json",
                };
                if ui.add_enabled(!app.export.preview.is_empty(),
                    egui::Button::new(egui::RichText::new("💾 Save to File").color(theme::ACCENT_LIGHT).font(theme::font_small()))
                ).clicked() {
                    let filter_name = match app.export.format_idx {
                        1 => "Python Script",
                        _ => "JSON File",
                    };
                    if let Some(path) = rfd::FileDialog::new()
                        .add_filter(filter_name, &[ext])
                        .save_file()
                    {
                        match std::fs::write(&path, &app.export.preview) {
                            Ok(()) => {
                                app.log_event(format!("Exported to {}", path.display()));
                                app.export.exported = true;
                            }
                            Err(e) => {
                                app.log_event(format!("Export error: {e}"));
                            }
                        }
                    }
                }

                if app.export.exported {
                    ui.label(egui::RichText::new("✅ Exported!").color(theme::SUCCESS));
                }
            });
        });

    if !open { app.export.open = false; }
}

/// Generate a Python script from a macro document.
fn generate_python_script(doc: &amk_schema::MacroDocument) -> String {
    let mut py = String::new();
    py.push_str("#!/usr/bin/env python3\n");
    py.push_str(&format!("\"\"\"Auto-generated from macro: {}\"\"\"\n\n", doc.name));
    py.push_str("import pyautogui\nimport time\n\n");
    py.push_str("pyautogui.FAILSAFE = True\n");
    py.push_str(&format!("pyautogui.PAUSE = {:.2}\n\n", 0.1));

    let loop_count = doc.settings.loop_count;
    if loop_count > 1 {
        py.push_str(&format!("for _loop in range({}):\n", loop_count));
    }

    let indent = if loop_count > 1 { "    " } else { "" };

    for action in &doc.actions {
        if !action.enabled { continue; }
        let line = action_to_python(action, indent);
        if !line.is_empty() {
            py.push_str(&line);
            py.push('\n');
        }
        if action.delay_after > 0 {
            py.push_str(&format!("{}time.sleep({:.3})\n", indent, action.delay_after as f64 / 1000.0));
        }
    }

    if loop_count > 1 && doc.settings.delay_between_loops > 0 {
        py.push_str(&format!("    time.sleep({:.3})\n", doc.settings.delay_between_loops as f64 / 1000.0));
    }

    py.push_str("\nprint(\"Macro complete!\")\n");
    py
}

fn action_to_python(action: &amk_schema::RawAction, indent: &str) -> String {
    let t = amk_schema::normalize_action_type(&action.action_type);
    let p = &action.params;

    match t {
        "mouse_click" => {
            let x = p.get("x").and_then(|v| v.as_i64()).unwrap_or(0);
            let y = p.get("y").and_then(|v| v.as_i64()).unwrap_or(0);
            let btn = p.get("button").and_then(|v| v.as_str()).unwrap_or("left");
            format!("{}pyautogui.click({}, {}, button='{}')", indent, x, y, btn)
        }
        "mouse_double_click" => {
            let x = p.get("x").and_then(|v| v.as_i64()).unwrap_or(0);
            let y = p.get("y").and_then(|v| v.as_i64()).unwrap_or(0);
            format!("{}pyautogui.doubleClick({}, {})", indent, x, y)
        }
        "mouse_right_click" => {
            let x = p.get("x").and_then(|v| v.as_i64()).unwrap_or(0);
            let y = p.get("y").and_then(|v| v.as_i64()).unwrap_or(0);
            format!("{}pyautogui.rightClick({}, {})", indent, x, y)
        }
        "mouse_move" => {
            let x = p.get("x").and_then(|v| v.as_i64()).unwrap_or(0);
            let y = p.get("y").and_then(|v| v.as_i64()).unwrap_or(0);
            let dur = p.get("duration").and_then(|v| v.as_f64()).unwrap_or(0.0) / 1000.0;
            format!("{}pyautogui.moveTo({}, {}, duration={:.3})", indent, x, y, dur)
        }
        "mouse_drag" => {
            let x1 = p.get("start_x").and_then(|v| v.as_i64()).unwrap_or(0);
            let y1 = p.get("start_y").and_then(|v| v.as_i64()).unwrap_or(0);
            let x2 = p.get("end_x").and_then(|v| v.as_i64()).unwrap_or(0);
            let y2 = p.get("end_y").and_then(|v| v.as_i64()).unwrap_or(0);
            format!("{}pyautogui.moveTo({}, {})\n{}pyautogui.drag({}, {})", indent, x1, y1, indent, x2-x1, y2-y1)
        }
        "mouse_scroll" => {
            let amount = p.get("amount").and_then(|v| v.as_i64()).unwrap_or(3);
            format!("{}pyautogui.scroll({})", indent, amount)
        }
        "key_press" => {
            let key = p.get("key").and_then(|v| v.as_str()).unwrap_or("enter");
            format!("{}pyautogui.press('{}')", indent, key)
        }
        "key_combo" => {
            let keys = p.get("keys").and_then(|v| v.as_array())
                .map(|arr| arr.iter().filter_map(|v| v.as_str()).collect::<Vec<_>>().join("', '"))
                .unwrap_or_default();
            format!("{}pyautogui.hotkey('{}')", indent, keys)
        }
        "type_text" => {
            let text = p.get("text").and_then(|v| v.as_str()).unwrap_or("");
            let interval = p.get("interval").and_then(|v| v.as_f64()).unwrap_or(50.0) / 1000.0;
            format!("{}pyautogui.typewrite({:?}, interval={:.3})", indent, text, interval)
        }
        "delay" => {
            let ms = p.get("ms").and_then(|v| v.as_u64()).unwrap_or(1000);
            format!("{}time.sleep({:.3})", indent, ms as f64 / 1000.0)
        }
        "comment" => {
            let text = p.get("text").and_then(|v| v.as_str()).unwrap_or("");
            format!("{}# {}", indent, text)
        }
        "take_screenshot" => {
            let path = p.get("path").and_then(|v| v.as_str()).unwrap_or("screenshot.png");
            format!("{}pyautogui.screenshot({:?})", indent, path)
        }
        "set_variable" => {
            let name = p.get("name").and_then(|v| v.as_str()).unwrap_or("var");
            let value = p.get("value").and_then(|v| v.as_str()).unwrap_or("");
            format!("{}{} = {:?}", indent, name, value)
        }
        "run_command" => {
            let cmd = p.get("command").and_then(|v| v.as_str()).unwrap_or("");
            format!("{}import subprocess; subprocess.run({:?}, shell=True)", indent, cmd)
        }
        _ => {
            format!("{}# TODO: {} (unsupported for Python export)", indent, t)
        }
    }
}
