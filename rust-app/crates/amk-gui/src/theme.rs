//! Color theme and styling.

use eframe::egui::{self, Color32, FontId, Stroke, Vec2};

/// Theme mode selection.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum ThemeMode {
    #[default]
    Dark,
    Light,
}

// ── Dark Colors ──────────────────────────────────────────────────────────

pub const BG_DARK: Color32 = Color32::from_rgb(22, 22, 30);
pub const BG_PANEL: Color32 = Color32::from_rgb(30, 30, 42);
pub const BG_CARD: Color32 = Color32::from_rgb(38, 38, 54);
pub const BG_HOVER: Color32 = Color32::from_rgb(48, 48, 68);
pub const BG_SELECTED: Color32 = Color32::from_rgb(55, 48, 80);

pub const ACCENT: Color32 = Color32::from_rgb(120, 90, 220);
pub const ACCENT_LIGHT: Color32 = Color32::from_rgb(160, 140, 255);

pub const SUCCESS: Color32 = Color32::from_rgb(80, 200, 120);
pub const WARNING: Color32 = Color32::from_rgb(255, 180, 50);
pub const ERROR: Color32 = Color32::from_rgb(240, 80, 80);
pub const MUTED: Color32 = Color32::from_rgb(120, 120, 150);

pub const TEXT_PRIMARY: Color32 = Color32::from_rgb(230, 230, 245);
pub const TEXT_SECONDARY: Color32 = Color32::from_rgb(170, 170, 195);
pub const TEXT_DIM: Color32 = Color32::from_rgb(110, 110, 140);

pub const BORDER: Color32 = Color32::from_rgb(55, 55, 75);

// Action type colors
pub const COLOR_MOUSE: Color32 = Color32::from_rgb(100, 180, 255);
pub const COLOR_KEYBOARD: Color32 = Color32::from_rgb(255, 170, 100);
pub const COLOR_DELAY: Color32 = Color32::from_rgb(160, 160, 180);
pub const COLOR_CONTROL: Color32 = Color32::from_rgb(180, 130, 255);
pub const COLOR_SYSTEM: Color32 = Color32::from_rgb(120, 220, 180);
pub const COLOR_IMAGE: Color32 = Color32::from_rgb(255, 140, 180);
pub const COLOR_FILE: Color32 = Color32::from_rgb(200, 200, 120);

// ── Style ────────────────────────────────────────────────────────────────

#[allow(dead_code)]
pub fn apply_theme(ctx: &egui::Context) {
    apply_theme_mode(ctx, ThemeMode::Dark);
}

pub fn apply_theme_mode(ctx: &egui::Context, mode: ThemeMode) {
    let mut style = (*ctx.style()).clone();

    let visuals = match mode {
        ThemeMode::Dark => {
            let mut v = egui::Visuals::dark();
            v.panel_fill = BG_DARK;
            v.window_fill = BG_PANEL;
            v.faint_bg_color = BG_CARD;
            v.extreme_bg_color = Color32::from_rgb(18, 18, 24);
            v.widgets.noninteractive.bg_fill = BG_CARD;
            v.widgets.noninteractive.fg_stroke = Stroke::new(1.0, TEXT_SECONDARY);
            v.widgets.inactive.bg_fill = BG_CARD;
            v.widgets.inactive.fg_stroke = Stroke::new(1.0, TEXT_PRIMARY);
            v.widgets.hovered.bg_fill = BG_HOVER;
            v.widgets.hovered.fg_stroke = Stroke::new(1.0, TEXT_PRIMARY);
            v.widgets.active.bg_fill = ACCENT;
            v.widgets.active.fg_stroke = Stroke::new(1.0, Color32::WHITE);
            v.selection.bg_fill = BG_SELECTED;
            v.selection.stroke = Stroke::new(1.0, ACCENT_LIGHT);
            v.window_stroke = Stroke::new(1.0, BORDER);
            v
        }
        ThemeMode::Light => {
            let mut v = egui::Visuals::light();
            v.panel_fill = Color32::from_rgb(245, 245, 250);
            v.window_fill = Color32::from_rgb(252, 252, 255);
            v.faint_bg_color = Color32::from_rgb(235, 235, 245);
            v.extreme_bg_color = Color32::WHITE;
            v.widgets.noninteractive.bg_fill = Color32::from_rgb(230, 230, 240);
            v.widgets.noninteractive.fg_stroke = Stroke::new(1.0, Color32::from_rgb(80, 80, 100));
            v.widgets.inactive.bg_fill = Color32::from_rgb(225, 225, 240);
            v.widgets.inactive.fg_stroke = Stroke::new(1.0, Color32::from_rgb(40, 40, 60));
            v.widgets.hovered.bg_fill = Color32::from_rgb(210, 210, 230);
            v.widgets.hovered.fg_stroke = Stroke::new(1.0, Color32::from_rgb(30, 30, 50));
            v.widgets.active.bg_fill = Color32::from_rgb(100, 70, 200);
            v.widgets.active.fg_stroke = Stroke::new(1.0, Color32::WHITE);
            v.selection.bg_fill = Color32::from_rgb(200, 190, 240);
            v.selection.stroke = Stroke::new(1.0, Color32::from_rgb(100, 70, 200));
            v.window_stroke = Stroke::new(1.0, Color32::from_rgb(200, 200, 215));
            v
        }
    };

    style.visuals = visuals;
    style.spacing.item_spacing = Vec2::new(8.0, 6.0);
    style.spacing.button_padding = Vec2::new(12.0, 6.0);

    ctx.set_style(style);
}

/// Get color for an action type.
pub fn action_color(kind_name: &str) -> Color32 {
    match kind_name {
        s if s.starts_with("Mouse") || s.starts_with("Double") || s.starts_with("Right") => COLOR_MOUSE,
        s if s.starts_with("Key") || s.starts_with("Type") || s.starts_with("Hotkey") => COLOR_KEYBOARD,
        "Delay" | "Comment" => COLOR_DELAY,
        s if s.starts_with("If") || s.starts_with("Loop") || s.starts_with("Group") => COLOR_CONTROL,
        s if s.starts_with("Run") || s.starts_with("Activate") || s.starts_with("Read") => COLOR_SYSTEM,
        s if s.contains("Image") || s.contains("Pixel") || s.contains("Screenshot") || s.contains("Color") => COLOR_IMAGE,
        s if s.contains("File") || s.starts_with("Log") || s.starts_with("Write") => COLOR_FILE,
        _ => TEXT_SECONDARY,
    }
}

/// Button font.
pub fn font_button() -> FontId {
    FontId::proportional(14.0)
}

/// Header font.
pub fn font_header() -> FontId {
    FontId::proportional(18.0)
}

/// Small font.
pub fn font_small() -> FontId {
    FontId::proportional(11.0)
}
