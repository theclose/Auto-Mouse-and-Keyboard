#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
//! AutoMacro GUI — desktop macro automation interface.

mod app;
mod theme;
mod panels;

use eframe::egui;

fn main() -> eframe::Result<()> {
    init_tracing();

    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_title("AutoMacro — Macro Automation")
            .with_inner_size([1100.0, 700.0])
            .with_min_inner_size([800.0, 500.0]),
        ..Default::default()
    };

    eframe::run_native(
        "AutoMacro",
        options,
        Box::new(|cc| Ok(Box::new(app::AutoMacroApp::new(cc)))),
    )
}

/// Initialize tracing.
/// - Debug builds: log to stderr (console visible).
/// - Release builds: log to file `automacro.log` next to the exe
///   (since windows_subsystem="windows" has no console).
fn init_tracing() {
    use tracing_subscriber::fmt;
    use tracing_subscriber::EnvFilter;

    let filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| "info".into());

    #[cfg(debug_assertions)]
    {
        fmt()
            .with_env_filter(filter)
            .with_target(false)
            .init();
    }

    #[cfg(not(debug_assertions))]
    {
        // In release, write to a log file next to the exe
        let log_path = std::env::current_exe()
            .ok()
            .and_then(|p| p.parent().map(|d| d.join("automacro.log")))
            .unwrap_or_else(|| std::path::PathBuf::from("automacro.log"));

        let file = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&log_path);

        match file {
            Ok(f) => {
                fmt()
                    .with_env_filter(filter)
                    .with_target(false)
                    .with_ansi(false)
                    .with_writer(f)
                    .init();
            }
            Err(_) => {
                // Fallback: silent (no console in release)
                fmt()
                    .with_env_filter(filter)
                    .with_target(false)
                    .init();
            }
        }
    }
}
