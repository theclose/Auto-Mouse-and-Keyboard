//! Top toolbar with run controls, file operations, and editing actions.

use eframe::egui;
use crate::app::{AutoMacroApp, RunState};
use crate::theme;

/// Common "Add Action" types organized in groups.
const ADD_ACTION_GROUPS: &[(&str, &[(&str, &str)])] = &[
    ("🖱 Mouse", &[
        ("mouse_click", "Click"),
        ("mouse_double_click", "Double Click"),
        ("mouse_right_click", "Right Click"),
        ("mouse_move", "Move"),
        ("mouse_drag", "Drag"),
        ("mouse_scroll", "Scroll"),
    ]),
    ("⌨ Keyboard", &[
        ("key_press", "Key Press"),
        ("key_combo", "Key Combo"),
        ("type_text", "Type Text"),
        ("hotkey", "Hotkey"),
    ]),
    ("⏱ Timing", &[
        ("delay", "Delay"),
    ]),
    ("📌 Variables", &[
        ("set_variable", "Set Variable"),
        ("comment", "Comment"),
    ]),
    ("🔀 Control Flow", &[
        ("if_variable", "If Variable"),
        ("if_pixel_color", "If Pixel Color"),
        ("if_image_found", "If Image Found"),
        ("loop_block", "Loop Block"),
        ("group", "Group"),
    ]),
    ("🖼 Image / Pixel", &[
        ("wait_for_image", "Wait for Image"),
        ("click_on_image", "Click on Image"),
        ("image_exists", "Image Exists"),
        ("check_pixel_color", "Check Pixel Color"),
        ("wait_for_color", "Wait for Color"),
        ("capture_text", "Capture Text (OCR)"),
    ]),
    ("⚙ System", &[
        ("run_command", "Run Command"),
        ("activate_window", "Activate Window"),
        ("take_screenshot", "Screenshot"),
        ("log_to_file", "Log to File"),
        ("read_file_line", "Read File Line"),
        ("write_to_file", "Write to File"),
        ("read_clipboard", "Read Clipboard"),
        ("run_macro", "Run Macro"),
    ]),
    ("👻 Stealth", &[
        ("stealth_click", "Stealth Click"),
        ("stealth_type", "Stealth Type"),
        ("secure_type_text", "Secure Type"),
    ]),
];

pub fn draw(app: &mut AutoMacroApp, ui: &mut egui::Ui) {
    ui.horizontal(|ui| {
        ui.spacing_mut().item_spacing.x = 4.0;

        // ── Logo / Title ──
        let title = if app.dirty { "⚡ AutoMacro *" } else { "⚡ AutoMacro" };
        ui.label(
            egui::RichText::new(title)
                .font(theme::font_header())
                .color(theme::ACCENT_LIGHT),
        );

        ui.separator();

        // ── File Operations ──
        if ui.button(egui::RichText::new("📄").font(theme::font_button()))
            .on_hover_text("New Macro (Ctrl+N)")
            .clicked()
        {
            app.new_macro();
        }

        if ui.button(egui::RichText::new("📂").font(theme::font_button()))
            .on_hover_text("Open Macro")
            .clicked()
        {
            if let Some(path) = rfd_open_macro() {
                app.load_macro_file(&path);
            }
        }

        let can_save = app.current_macro.is_some();
        if ui.add_enabled(can_save,
            egui::Button::new(egui::RichText::new("💾").font(theme::font_button()))
        ).on_hover_text("Save (Ctrl+S)")
            .clicked()
        {
            app.save_macro();
        }

        ui.separator();

        // ── Run Controls ──
        let has_macro = app.current_macro.is_some() && !app.typed_actions.is_empty();

        match app.run_state {
            RunState::Idle => {
                if ui.add_enabled(has_macro,
                    egui::Button::new(egui::RichText::new("▶ Run").color(theme::SUCCESS).font(theme::font_button()))
                ).clicked() {
                    app.start_run();
                }
            }
            RunState::Running => {
                if ui.button(egui::RichText::new("⏸").color(theme::WARNING).font(theme::font_button())).clicked() {
                    app.pause_run();
                }
                if ui.button(egui::RichText::new("⏹").color(theme::ERROR).font(theme::font_button())).clicked() {
                    app.stop_run();
                }
            }
            RunState::Paused => {
                if ui.button(egui::RichText::new("▶").color(theme::SUCCESS).font(theme::font_button())).clicked() {
                    app.resume_run();
                }
                if ui.button(egui::RichText::new("⏹").color(theme::ERROR).font(theme::font_button())).clicked() {
                    app.stop_run();
                }
            }
        }

        ui.separator();

        // ── Settings ──
        ui.label(egui::RichText::new("Loops:").color(theme::TEXT_SECONDARY).font(theme::font_small()));
        ui.add(egui::DragValue::new(&mut app.loop_count).range(0..=9999).speed(0.5));
        if app.loop_count == 0 {
            ui.label(egui::RichText::new("∞").color(theme::ACCENT_LIGHT).font(theme::font_small()));
        }

        ui.label(egui::RichText::new("Speed:").color(theme::TEXT_SECONDARY).font(theme::font_small()));
        ui.add(egui::DragValue::new(&mut app.speed_factor).range(0.1..=10.0).speed(0.05).suffix("x"));

        ui.separator();

        // ── Action Editing ──
        let has_selection = app.selected_action_idx.is_some();

        // Add Action dropdown
        let add_resp = ui.button(egui::RichText::new("➕").font(theme::font_button()));
        if add_resp.on_hover_text("Add Action").clicked() {
            app.show_add_action_menu = !app.show_add_action_menu;
        }

        if ui.add_enabled(has_selection,
            egui::Button::new(egui::RichText::new("✏").font(theme::font_button()))
        ).on_hover_text("Edit (Enter / Double-click)")
           .clicked()
        {
            app.edit_selected_action();
        }

        let multi_count = app.selected_actions.len();
        let delete_label = if multi_count > 1 { format!("🗑{}", multi_count) } else { "🗑".into() };
        if ui.add_enabled(has_selection,
            egui::Button::new(egui::RichText::new(delete_label).font(theme::font_button()))
        ).on_hover_text(if multi_count > 1 { format!("Delete {} selected (Del)", multi_count) } else { "Delete (Del)".into() })
           .clicked()
        {
            if multi_count > 1 {
                app.show_confirm_delete = true;
            } else {
                app.delete_selected_action();
            }
        }

        if ui.add_enabled(has_selection,
            egui::Button::new(egui::RichText::new("📋").font(theme::font_button()))
        ).on_hover_text("Duplicate (Ctrl+D)")
           .clicked()
        {
            app.duplicate_selected_action();
        }

        if ui.add_enabled(has_selection,
            egui::Button::new(egui::RichText::new("⬆").font(theme::font_small()))
        ).on_hover_text("Move Up")
           .clicked()
        {
            app.move_action_up();
        }
        if ui.add_enabled(has_selection,
            egui::Button::new(egui::RichText::new("⬇").font(theme::font_small()))
        ).on_hover_text("Move Down")
           .clicked()
        {
            app.move_action_down();
        }

        ui.separator();

        // ── Undo / Redo ──
        let can_undo = !app.undo_stack.is_empty();
        let can_redo = !app.redo_stack.is_empty();

        if ui.add_enabled(can_undo,
            egui::Button::new(egui::RichText::new("↩").font(theme::font_button()))
        ).on_hover_text(format!("Undo (Ctrl+Z) [{}]", app.undo_stack.len()))
           .clicked()
        {
            app.undo();
        }
        if ui.add_enabled(can_redo,
            egui::Button::new(egui::RichText::new("↪").font(theme::font_button()))
        ).on_hover_text(format!("Redo (Ctrl+Y) [{}]", app.redo_stack.len()))
           .clicked()
        {
            app.redo();
        }

        ui.separator();

        // ── Settings ──
        if ui.button(egui::RichText::new("⚙").font(theme::font_button()))
            .on_hover_text("Settings")
            .clicked()
        {
            app.show_settings = !app.show_settings;
        }

        if ui.button(egui::RichText::new("📖").font(theme::font_button()))
            .on_hover_text("Help (F1)")
            .clicked()
        {
            app.help_state.open = !app.help_state.open;
        }

        // Coordinate Picker
        let picker_label = if app.coord_picker.active { "🎯✓" } else { "🎯" };
        if ui.button(egui::RichText::new(picker_label).font(theme::font_button()))
            .on_hover_text("Coordinate Picker (Ctrl+G)")
            .clicked()
        {
            app.coord_picker.active = !app.coord_picker.active;
        }

        // Optimizer
        if ui.button(egui::RichText::new("🔍").font(theme::font_button()))
            .on_hover_text("Macro Optimizer (Ctrl+H)")
            .clicked()
        {
            app.show_optimizer = !app.show_optimizer;
        }

        // Recording
        let rec_label = if app.recording.active { "🔴 REC" } else { "🔴" };
        let rec_color = if app.recording.active { theme::ERROR } else { theme::TEXT_SECONDARY };
        if ui.button(egui::RichText::new(rec_label).color(rec_color).font(theme::font_button()))
            .on_hover_text("Macro Recorder (Ctrl+R)")
            .clicked()
        {
            app.show_recording = !app.show_recording;
        }

        // Screenshot
        if ui.button(egui::RichText::new("📸").font(theme::font_button()))
            .on_hover_text("Screenshot Capture")
            .clicked()
        {
            app.screenshot.show = !app.screenshot.show;
        }

        // Multi-Run
        if ui.button(egui::RichText::new("📋").font(theme::font_button()))
            .on_hover_text("Multi-Run Queue")
            .clicked()
        {
            app.multi_run.show = !app.multi_run.show;
        }

        // Scheduler
        let sched_count = app.scheduler.entries.iter().filter(|e| e.enabled).count();
        let sched_label = if sched_count > 0 { format!("📅{}", sched_count) } else { "📅".into() };
        if ui.button(egui::RichText::new(sched_label).font(theme::font_button()))
            .on_hover_text("Scheduler")
            .clicked()
        {
            app.scheduler.open = !app.scheduler.open;
        }

        // Debugger
        if ui.button(egui::RichText::new("🔬").font(theme::font_button()))
            .on_hover_text("Debugger")
            .clicked()
        {
            app.debugger.open = !app.debugger.open;
        }

        // Export
        if ui.button(egui::RichText::new("📤").font(theme::font_button()))
            .on_hover_text("Export Macro")
            .clicked()
        {
            app.export.open = !app.export.open;
        }

        // ── ≡ Menu dropdown ──
        let menu_resp = ui.menu_button(egui::RichText::new("≡").font(theme::font_button()), |ui| {
            // Templates
            ui.menu_button("📦 Templates", |ui| {
                if ui.button("🖱 Click Sequence").clicked() {
                    app.insert_template("click_sequence");
                    ui.close_menu();
                }
                if ui.button("⌨ Type and Enter").clicked() {
                    app.insert_template("type_and_enter");
                    ui.close_menu();
                }
                if ui.button("🔐 Login Flow").clicked() {
                    app.insert_template("login_flow");
                    ui.close_menu();
                }
                if ui.button("🔁 Loop Clicks").clicked() {
                    app.insert_template("loop_clicks");
                    ui.close_menu();
                }
                if ui.button("📸 Screenshot + Log").clicked() {
                    app.insert_template("screenshot_log");
                    ui.close_menu();
                }
            });

            // Recent Files
            if !app.recent_files.is_empty() {
                ui.menu_button(format!("📋 Recent ({})", app.recent_files.len()), |ui| {
                    let files = app.recent_files.clone();
                    for path in &files {
                        let name = std::path::Path::new(path)
                            .file_name()
                            .map(|n| n.to_string_lossy().to_string())
                            .unwrap_or_else(|| path.clone());
                        if ui.button(&name).clicked() {
                            app.load_macro_file(path);
                            ui.close_menu();
                        }
                    }
                });
            }

            ui.separator();

            if ui.button("ℹ About").clicked() {
                app.show_about = !app.show_about;
                ui.close_menu();
            }
        });
        menu_resp.response.on_hover_text("Menu: Templates, Recent, About");

        // ── Right-aligned status ──
        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
            match app.run_state {
                RunState::Idle => {
                    ui.label(egui::RichText::new("● Ready").color(theme::MUTED).font(theme::font_small()));
                }
                RunState::Running => {
                    ui.label(egui::RichText::new("● Running").color(theme::SUCCESS).font(theme::font_small()));
                }
                RunState::Paused => {
                    ui.label(egui::RichText::new("● Paused").color(theme::WARNING).font(theme::font_small()));
                }
            }
        });
    });

    // ── Add Action dropdown popup ──
    if app.show_add_action_menu {
        egui::Area::new(egui::Id::new("add_action_menu"))
            .fixed_pos(egui::pos2(350.0, 42.0))
            .order(egui::Order::Foreground)
            .show(ui.ctx(), |ui| {
                egui::Frame::popup(ui.style()).show(ui, |ui| {
                    ui.set_min_width(220.0);
                    ui.label(egui::RichText::new("Add Action").font(theme::font_header()).color(theme::ACCENT_LIGHT));

                    // Search input
                    ui.horizontal(|ui| {
                        ui.label("🔍");
                        ui.add(egui::TextEdit::singleline(&mut app.add_action_filter)
                            .hint_text("Search actions...")
                            .desired_width(160.0)
                            .font(theme::font_small()));
                        if !app.add_action_filter.is_empty() && ui.small_button("✕").clicked() {
                            app.add_action_filter.clear();
                        }
                    });
                    ui.separator();

                    let filter_lower = app.add_action_filter.to_lowercase();
                    let mut added = false;

                    egui::ScrollArea::vertical().max_height(400.0).show(ui, |ui| {
                        for (group_name, actions) in ADD_ACTION_GROUPS {
                            // Filter: check if any action in group matches
                            let visible_actions: Vec<_> = actions.iter()
                                .filter(|(t, n)| {
                                    filter_lower.is_empty()
                                        || t.to_lowercase().contains(&filter_lower)
                                        || n.to_lowercase().contains(&filter_lower)
                                })
                                .collect();

                            if visible_actions.is_empty() {
                                continue;
                            }

                            ui.label(egui::RichText::new(*group_name).color(theme::TEXT_SECONDARY).font(theme::font_small()));
                            for (action_type, display_name) in visible_actions {
                                if ui.button(*display_name).clicked() {
                                    app.add_action(action_type);
                                    added = true;
                                }
                            }
                            ui.add_space(2.0);
                        }

                        if !filter_lower.is_empty() {
                            let total_visible = ADD_ACTION_GROUPS.iter()
                                .flat_map(|(_, acts)| acts.iter())
                                .filter(|(t, n)| t.to_lowercase().contains(&filter_lower) || n.to_lowercase().contains(&filter_lower))
                                .count();
                            if total_visible == 0 {
                                ui.colored_label(theme::TEXT_DIM, "No matching action types");
                            }
                        }
                    });

                    if added {
                        app.add_action_filter.clear();
                        app.show_add_action_menu = false;
                    }
                });
            });

        // Close on Escape
        if ui.ctx().input(|i| i.key_pressed(egui::Key::Escape)) {
            app.show_add_action_menu = false;
        }
    }
}

fn rfd_open_macro() -> Option<String> {
    rfd::FileDialog::new()
        .set_title("Open Macro File")
        .add_filter("AutoMacro JSON", &["json"])
        .pick_file()
        .map(|p| p.to_string_lossy().into_owned())
}
