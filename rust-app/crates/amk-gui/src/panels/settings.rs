//! Settings dialog — 4-tab configuration like Python version.
//!
//! Tabs: ⌨ Hotkeys | Defaults | 🎨 UI | ⚡ Performance

use eframe::egui;
use crate::app::AutoMacroApp;
use crate::theme;

pub fn draw_settings(app: &mut AutoMacroApp, ctx: &egui::Context) {
    let mut open = app.show_settings;

    egui::Window::new("⚙  Settings")
        .id(egui::Id::new("settings_dialog"))
        .open(&mut open)
        .resizable(true)
        .collapsible(false)
        .default_width(420.0)
        .default_height(400.0)
        .anchor(egui::Align2::CENTER_CENTER, [0.0, 0.0])
        .show(ctx, |ui| {
            // Tab bar
            ui.horizontal(|ui| {
                ui.selectable_value(&mut app.settings_tab, 0, "⌨ Hotkeys");
                ui.selectable_value(&mut app.settings_tab, 1, "📐 Defaults");
                ui.selectable_value(&mut app.settings_tab, 2, "🎨 UI");
                ui.selectable_value(&mut app.settings_tab, 3, "⚡ Performance");
            });
            ui.separator();

            egui::ScrollArea::vertical().show(ui, |ui| {
                ui.set_min_width(380.0);
                match app.settings_tab {
                    0 => draw_hotkeys_tab(app, ui),
                    1 => draw_defaults_tab(app, ui),
                    2 => draw_ui_tab(app, ui),
                    3 => draw_performance_tab(app, ui),
                    _ => {}
                }
            });

            ui.add_space(8.0);
            ui.separator();
            ui.add_space(4.0);

            // About info
            ui.horizontal(|ui| {
                ui.label(egui::RichText::new("AutoMacro").color(theme::ACCENT_LIGHT).font(theme::font_small()));
                ui.label(egui::RichText::new(format!("v{}", env!("CARGO_PKG_VERSION"))).color(theme::TEXT_DIM).font(theme::font_small()));
                ui.label(egui::RichText::new("• Rust + egui").color(theme::TEXT_DIM).font(theme::font_small()));
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    ui.label(egui::RichText::new(format!("Undo: {} | Redo: {}", app.undo_stack.len(), app.redo_stack.len())).color(theme::TEXT_DIM).font(theme::font_small()));
                });
            });
        });

    app.show_settings = open;
}

fn draw_hotkeys_tab(app: &mut AutoMacroApp, ui: &mut egui::Ui) {
    ui.label(
        egui::RichText::new("⌨  Keyboard Hotkeys")
            .color(theme::ACCENT_LIGHT)
            .font(theme::font_button()),
    );
    ui.add_space(4.0);
    ui.label(egui::RichText::new("💡 Configure global hotkeys for macro control").color(theme::TEXT_DIM).font(theme::font_small()));
    ui.add_space(8.0);

    ui.group(|ui| {
        egui::Grid::new("hotkeys_grid")
            .num_columns(2)
            .spacing([12.0, 6.0])
            .show(ui, |ui| {
                ui.label("Start / Stop:");
                ui.add(egui::TextEdit::singleline(&mut app.hotkey_start_stop).desired_width(120.0).hint_text("e.g. F6"));
                ui.end_row();

                ui.label("Pause / Resume:");
                ui.add(egui::TextEdit::singleline(&mut app.hotkey_pause).desired_width(120.0).hint_text("e.g. F7"));
                ui.end_row();

                ui.label("Emergency Stop:");
                ui.add(egui::TextEdit::singleline(&mut app.hotkey_emergency).desired_width(120.0).hint_text("e.g. F8"));
                ui.end_row();

                ui.label("Record:");
                ui.add(egui::TextEdit::singleline(&mut app.hotkey_record).desired_width(120.0).hint_text("e.g. F9"));
                ui.end_row();
            });
    });

    ui.add_space(8.0);

    // Built-in shortcuts reference
    ui.group(|ui| {
        ui.label(egui::RichText::new("Built-in Shortcuts (not configurable)").color(theme::TEXT_SECONDARY).font(theme::font_small()));
        ui.add_space(4.0);
        egui::Grid::new("builtin_shortcuts")
            .num_columns(2)
            .spacing([12.0, 2.0])
            .show(ui, |ui| {
                let shortcuts = [
                    ("Ctrl+N", "New macro"), ("Ctrl+S", "Save macro"),
                    ("Ctrl+Z", "Undo"), ("Ctrl+Y", "Redo"),
                    ("Ctrl+C", "Copy action"), ("Ctrl+V", "Paste action"),
                    ("Ctrl+D", "Duplicate"), ("Del", "Delete"),
                    ("Enter", "Edit"), ("Space", "Toggle enable"),
                    ("↑↓", "Navigate"), ("Ctrl+↑↓", "Reorder"),
                ];
                for (key, desc) in shortcuts {
                    ui.label(egui::RichText::new(key).color(theme::ACCENT_LIGHT).font(egui::FontId::monospace(10.0)));
                    ui.label(egui::RichText::new(desc).font(theme::font_small()));
                    ui.end_row();
                }
            });
    });
}

fn draw_defaults_tab(app: &mut AutoMacroApp, ui: &mut egui::Ui) {
    ui.label(
        egui::RichText::new("📐  Default Values")
            .color(theme::ACCENT_LIGHT)
            .font(theme::font_button()),
    );
    ui.add_space(8.0);

    ui.group(|ui| {
        egui::Grid::new("defaults_grid")
            .num_columns(2)
            .spacing([12.0, 6.0])
            .show(ui, |ui| {
                ui.label("Default click delay:");
                ui.add(egui::DragValue::new(&mut app.default_delay).range(0..=5000).speed(10).suffix(" ms"));
                ui.end_row();

                ui.label("Default loops:");
                ui.add(egui::DragValue::new(&mut app.loop_count).range(0..=9999).speed(0.5));
                ui.end_row();

                ui.label("Default speed:");
                ui.add(egui::DragValue::new(&mut app.speed_factor).range(0.1..=10.0).speed(0.05).suffix("×"));
                ui.end_row();

                ui.label("Loop delay:");
                ui.add(egui::DragValue::new(&mut app.loop_delay).range(0..=60000).speed(10).suffix(" ms"));
                ui.end_row();

                ui.label("Stop on error:");
                ui.checkbox(&mut app.stop_on_error, "Stop macro when action fails");
                ui.end_row();
            });
    });

    ui.add_space(8.0);

    ui.group(|ui| {
        ui.label(egui::RichText::new("📂 Paths").color(theme::TEXT_SECONDARY).font(theme::font_small()));
        ui.add_space(4.0);
        ui.horizontal(|ui| {
            ui.label("Macros directory:");
            ui.label(egui::RichText::new(app.macros_dir.display().to_string()).color(theme::TEXT_DIM).font(theme::font_small()));
        });
    });
}

fn draw_ui_tab(app: &mut AutoMacroApp, ui: &mut egui::Ui) {
    ui.label(
        egui::RichText::new("🎨  Appearance")
            .color(theme::ACCENT_LIGHT)
            .font(theme::font_button()),
    );
    ui.add_space(8.0);

    ui.group(|ui| {
        ui.label(egui::RichText::new("Theme").color(theme::TEXT_SECONDARY).font(theme::font_small()));
        ui.add_space(4.0);

        let prev = app.theme_mode;
        ui.horizontal(|ui| {
            ui.radio_value(&mut app.theme_mode, theme::ThemeMode::Dark, "🌙 Dark");
            ui.radio_value(&mut app.theme_mode, theme::ThemeMode::Light, "☀ Light");
        });

        // Re-apply when changed
        if app.theme_mode != prev {
            app.theme_applied = false;
        }

        ui.add_space(4.0);
        let desc = match app.theme_mode {
            theme::ThemeMode::Dark => "Deep purple dark theme — easy on the eyes for extended sessions",
            theme::ThemeMode::Light => "Clean light theme — great for well-lit environments",
        };
        ui.label(egui::RichText::new(desc).color(theme::TEXT_DIM).font(theme::font_small()));
    });

    ui.add_space(8.0);

    ui.group(|ui| {
        ui.label(egui::RichText::new("UI Info").color(theme::TEXT_SECONDARY).font(theme::font_small()));
        ui.add_space(4.0);
        let action_count = app.typed_actions.len();
        let info: Vec<String> = vec![
            "Action types supported: 36".into(),
            "Panel modules: 18".into(),
            format!("Actions in current macro: {}", action_count),
            "Keyboard shortcuts: 24+".into(),
            format!("Theme: {:?}", app.theme_mode),
        ];
        for line in &info {
            ui.label(egui::RichText::new(line).color(theme::TEXT_DIM).font(theme::font_small()));
        }
    });
}

fn draw_performance_tab(app: &mut AutoMacroApp, ui: &mut egui::Ui) {
    ui.label(
        egui::RichText::new("⚡  Performance")
            .color(theme::ACCENT_LIGHT)
            .font(theme::font_button()),
    );
    ui.add_space(8.0);

    ui.group(|ui| {
        ui.label(egui::RichText::new("Rendering").color(theme::TEXT_SECONDARY).font(theme::font_small()));
        ui.add_space(4.0);
        egui::Grid::new("perf_render_grid").num_columns(2).spacing([12.0, 4.0]).show(ui, |ui| {
            ui.label("Max FPS (idle):");
            ui.add(egui::DragValue::new(&mut app.max_fps).range(5..=120).speed(1).suffix(" fps"));
            ui.end_row();

            ui.label("Autosave interval:");
            ui.add(egui::DragValue::new(&mut app.autosave_interval_secs).range(10..=600).speed(5).suffix(" sec"));
            ui.end_row();
        });
    });

    ui.add_space(8.0);

    ui.group(|ui| {
        ui.label(egui::RichText::new("System Info").color(theme::TEXT_SECONDARY).font(theme::font_small()));
        ui.add_space(4.0);
        let sys_info = [
            format!("Undo stack: {} entries", app.undo_stack.len()),
            format!("Redo stack: {} entries", app.redo_stack.len()),
            format!("Log entries: {}", app.log_messages.len()),
            format!("Macros in dir: {}", app.macro_entries.len()),
            format!("Scheduler entries: {}", app.scheduler.entries.len()),
            format!("Breakpoints: {}", app.debugger.breakpoints.len()),
        ];
        for line in &sys_info {
            ui.label(egui::RichText::new(line).color(theme::TEXT_DIM).font(theme::font_small()));
        }
    });

    ui.add_space(8.0);

    ui.group(|ui| {
        ui.label(egui::RichText::new("Maintenance").color(theme::TEXT_SECONDARY).font(theme::font_small()));
        ui.add_space(4.0);
        ui.horizontal(|ui| {
            if ui.button(egui::RichText::new("🗑 Clear Undo History").font(theme::font_small())).clicked() {
                app.undo_stack.clear();
                app.redo_stack.clear();
                app.log_event("Cleared undo/redo history".into());
            }
            if ui.button(egui::RichText::new("🗑 Clear Log").font(theme::font_small())).clicked() {
                app.log_messages.clear();
            }
        });
    });
}
