//! Screenshot Capture — take full screen or region captures.
//!
//! Uses amk-platform::capture for Win32 GDI capture.

use eframe::egui;
use crate::app::AutoMacroApp;
use crate::theme;

/// State for screenshot capture.
#[derive(Default)]
pub struct ScreenshotState {
    pub show: bool,
    pub last_path: Option<String>,
    pub capture_mode: CaptureMode,
    pub region_x: i32,
    pub region_y: i32,
    pub region_w: i32,
    pub region_h: i32,
}

#[derive(Default, Clone, Copy, PartialEq)]
pub enum CaptureMode {
    #[default]
    FullScreen,
    Region,
}

/// Draw the screenshot capture dialog.
pub fn draw_screenshot_window(app: &mut AutoMacroApp, ctx: &egui::Context) {
    if !app.screenshot.show {
        return;
    }

    let mut open = true;
    egui::Window::new("📸 Screenshot Capture")
        .id(egui::Id::new("screenshot_dialog"))
        .open(&mut open)
        .resizable(false)
        .collapsible(false)
        .default_width(320.0)
        .show(ctx, |ui| {
            // Mode selection
            ui.horizontal(|ui| {
                ui.label("Mode:");
                ui.selectable_value(&mut app.screenshot.capture_mode, CaptureMode::FullScreen, "Full Screen");
                ui.selectable_value(&mut app.screenshot.capture_mode, CaptureMode::Region, "Region");
            });

            ui.add_space(4.0);

            // Region settings (only when Region mode)
            if app.screenshot.capture_mode == CaptureMode::Region {
                ui.group(|ui| {
                    ui.label(egui::RichText::new("Region").color(theme::ACCENT_LIGHT).font(theme::font_small()));
                    egui::Grid::new("region_grid")
                        .num_columns(4)
                        .spacing([8.0, 4.0])
                        .show(ui, |ui| {
                            ui.label("X:");
                            ui.add(egui::DragValue::new(&mut app.screenshot.region_x).range(0..=9999));
                            ui.label("Y:");
                            ui.add(egui::DragValue::new(&mut app.screenshot.region_y).range(0..=9999));
                            ui.end_row();
                            ui.label("W:");
                            ui.add(egui::DragValue::new(&mut app.screenshot.region_w).range(1..=9999));
                            ui.label("H:");
                            ui.add(egui::DragValue::new(&mut app.screenshot.region_h).range(1..=9999));
                            ui.end_row();
                        });

                    // Use coord picker values
                    if app.coord_picker.active {
                        ui.horizontal(|ui| {
                            if ui.small_button("← Use Picker Position").clicked() {
                                app.screenshot.region_x = app.coord_picker.last_x;
                                app.screenshot.region_y = app.coord_picker.last_y;
                            }
                        });
                    }
                });
                ui.add_space(4.0);
            }

            ui.separator();
            ui.add_space(4.0);

            // Capture button
            if ui.button(egui::RichText::new("📸 Capture Now").color(theme::SUCCESS).font(theme::font_button())).clicked() {
                do_capture(app);
            }

            // Last saved path
            if let Some(ref path) = app.screenshot.last_path {
                ui.add_space(4.0);
                ui.horizontal(|ui| {
                    ui.label(egui::RichText::new("Saved:").color(theme::TEXT_DIM).font(theme::font_small()));
                    ui.label(egui::RichText::new(path).color(theme::SUCCESS).font(theme::font_small()));
                });
            }
        });
    app.screenshot.show = open;
}

/// Perform the screen capture.
fn do_capture(app: &mut AutoMacroApp) {
    let (x, y, w, h) = match app.screenshot.capture_mode {
        CaptureMode::FullScreen => {
            let (sw, sh) = amk_platform::input::screen_size();
            (0, 0, sw, sh)
        }
        CaptureMode::Region => {
            (app.screenshot.region_x, app.screenshot.region_y,
             app.screenshot.region_w, app.screenshot.region_h)
        }
    };

    if w <= 0 || h <= 0 {
        app.log_event("⚠ Invalid capture dimensions".into());
        return;
    }

    // Ask for save path
    let save_path = rfd::FileDialog::new()
        .set_title("Save Screenshot")
        .add_filter("BMP Image", &["bmp"])
        .add_filter("All Files", &["*"])
        .set_file_name(format!("screenshot_{}.bmp", chrono::Local::now().format("%Y%m%d_%H%M%S")))
        .save_file();

    let Some(path) = save_path else {
        return;
    };

    let path_str = path.to_string_lossy().to_string();

    // Capture
    match amk_platform::capture::capture_region(x, y, w, h) {
        Ok((data, cw, ch)) => {
            match amk_platform::capture::save_bmp(&path_str, &data, cw, ch) {
                Ok(()) => {
                    let size_kb = std::fs::metadata(&path_str)
                        .map(|m| m.len() / 1024)
                        .unwrap_or(0);
                    app.screenshot.last_path = Some(path_str.clone());
                    app.log_event(format!("📸 Screenshot saved: {} ({}×{}, {}KB)", path_str, cw, ch, size_kb));
                }
                Err(e) => {
                    app.log_event(format!("⚠ Save failed: {}", e));
                }
            }
        }
        Err(e) => {
            app.log_event(format!("⚠ Capture failed: {}", e));
        }
    }
}
