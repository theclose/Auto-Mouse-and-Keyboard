//! Help dialog — searchable guide for AutoMacro (F1).

use eframe::egui;
use crate::theme;

#[derive(Default)]
pub struct HelpState {
    pub open: bool,
    pub search: String,
    pub section: usize,
}


const SECTIONS: &[(&str, &str)] = &[
    ("🚀 Getting Started", r#"
Welcome to AutoMacro! This guide will help you get started.

1. Create a new macro (Ctrl+N) or open an existing one (📂)
2. Add actions using ➕ button in the toolbar
3. Configure each action by double-clicking or pressing Enter
4. Press ▶ Run to execute your macro

Macros are saved as JSON files in your macros directory.
"#),
    ("🖱 Mouse Actions", r#"
Mouse Click — Click at specific coordinates (x, y)
  • Left, Right, Middle button support
  • Configurable click count

Double Click — Double-click at (x, y)

Right Click — Right-click at (x, y)

Mouse Move — Move cursor to (x, y)
  • Optional duration for smooth movement

Mouse Drag — Drag from (x1,y1) to (x2,y2)
  • Configurable duration and button

Mouse Scroll — Scroll wheel up/down
"#),
    ("⌨ Keyboard Actions", r#"
Key Press — Press and release a single key
  • Optional hold duration (ms)

Key Combo — Press multiple keys simultaneously
  • Example: ["ctrl", "shift", "s"]

Type Text — Type a string character by character
  • Configurable typing interval (ms)

Hotkey — Send a keyboard shortcut
"#),
    ("⏱ Timing & Flow", r#"
Delay — Wait for specified milliseconds

Loop Block — Repeat a group of actions
  • Set count to 0 for infinite loop
  • Contains child actions

If Variable — Conditional execution
  • Compare variable with value
  • Then/Else action branches

Group — Organize actions into named groups
"#),
    ("📌 Variables", r#"
Set Variable — Store a value with a name
  • name = "value"

Variables can be used in conditions (If Variable)
and referenced in other action parameters.

Comment — Add notes to your macro
  • Not executed, just for documentation
"#),
    ("⚙ System Actions", r#"
Run Command — Execute a system command
  • Optional wait for completion
  • Capture output to variable

Activate Window — Focus a window by title
  • Match types: exact, contains, regex

Log to File — Write text to a log file
  • Append or overwrite mode

Take Screenshot — Capture screen to file

Run Macro — Execute another macro file
"#),
    ("🖼 Image Actions", r#"
Wait for Image — Wait until an image appears on screen
  • Configurable confidence threshold
  • Timeout in milliseconds

Click on Image — Find and click on an image
  • Searches the screen for a template image
  • Click at the center of the found region

Image Exists — Check if an image is on screen

If Pixel Color — Check pixel color at (x, y)
  • Then/Else branches for conditional logic

If Image Found — Branch based on image detection
"#),
    ("📅 Scheduler", r#"
Schedule macros to run automatically. Open via 📅 button.

Schedule Types:
  • Once — run at a specific time, then disable
  • Interval — repeat every N minutes
  • Daily — run at the same time every day

Features:
  • Enable/disable individual schedules
  • Live countdown timer shows next trigger
  • Auto-loads and runs the scheduled macro
  • Multiple schedules can be active simultaneously
"#),
    ("🔬 Debugger", r#"
Step-through macro execution. Open via 🔬 button.

Controls:
  ⏭ Step      Execute one action, then pause
  ⏸ Pause     Pause running execution
  ▶ Continue   Resume normal execution
  ⏹ Stop      Stop execution entirely

Breakpoints:
  • Right-click an action → Set Breakpoint
  • 🔴 appears on actions with breakpoints
  • Clear all breakpoints from debugger panel

Variable Watch:
  • Add variable names to watch list
  • Shows default values from Set Variable actions
"#),
    ("🔀 Multi-Select", r#"
Select multiple actions at once:

  Ctrl+Click    Toggle individual selection
  Shift+Click   Range select (from anchor)
  Click         Normal single select

Multi-select operations:
  • Delete — removes all selected actions
  • Toggle — enable/disable all selected
  • Copy — copies all to clipboard (+ system JSON)
  • Confirmation dialog for bulk deletes (>1)

The delete button shows count (🗑3) when multiple selected.
"#),
    ("⌨ Shortcuts Reference", r#"
File Operations:
  Ctrl+N        New macro
  Ctrl+O        Open macro
  Ctrl+S        Save macro
  Ctrl+Shift+S  Save As

Edit Operations:
  Ctrl+Z      Undo
  Ctrl+Y      Redo
  Ctrl+C      Copy action(s) — also to system clipboard
  Ctrl+V      Paste action(s)
  Ctrl+D      Duplicate action
  Ctrl+A      Select first action
  Del         Delete action(s)
  Enter       Edit action
  Space       Toggle enable/disable
  Escape      Close dialogs/cancel editor

Navigation:
  ↑ ↓         Select previous/next action
  Ctrl+↑ ↓    Move action up/down
  Ctrl+Click  Toggle multi-select
  Shift+Click Range select

Tools:
  Ctrl+G      Coordinate Picker toggle
  Ctrl+H      Macro Optimizer
  F1          Help dialog
  📅          Scheduler
  🔬          Debugger
  📋          Multi-Run Queue

Mouse:
  Double-click    Edit action
  Right-click     Context menu (with breakpoint toggle)
"#),
];

pub fn draw_help(state: &mut HelpState, ctx: &egui::Context) {
    let mut open = state.open;

    egui::Window::new("📖  Help — AutoMacro Guide")
        .id(egui::Id::new("help_dialog"))
        .open(&mut open)
        .resizable(true)
        .collapsible(true)
        .default_width(550.0)
        .default_height(500.0)
        .show(ctx, |ui| {
            // Search bar
            ui.horizontal(|ui| {
                ui.label("🔍");
                ui.add(
                    egui::TextEdit::singleline(&mut state.search)
                        .hint_text("Search help...")
                        .desired_width(200.0),
                );
                if !state.search.is_empty() && ui.small_button("✕").clicked() {
                    state.search.clear();
                }
            });
            ui.separator();

            // Two-column layout: sections nav + content
            ui.columns(2, |cols| {
                // Left: section list
                cols[0].vertical(|ui| {
                    ui.set_min_width(140.0);
                    for (i, (title, _)) in SECTIONS.iter().enumerate() {
                        if ui.selectable_label(state.section == i, *title).clicked() {
                            state.section = i;
                        }
                    }
                });

                // Right: content
                egui::ScrollArea::vertical().show(&mut cols[1], |ui| {
                    let search = state.search.to_lowercase();

                    if search.is_empty() {
                        // Show current section
                        if state.section < SECTIONS.len() {
                            let (title, content) = SECTIONS[state.section];
                            ui.label(egui::RichText::new(title).color(theme::ACCENT_LIGHT).font(egui::FontId::proportional(16.0)));
                            ui.add_space(4.0);
                            ui.label(content.trim());
                        }
                    } else {
                        // Search all sections
                        let mut found = false;
                        for (title, content) in SECTIONS {
                            if title.to_lowercase().contains(&search) || content.to_lowercase().contains(&search) {
                                ui.label(egui::RichText::new(*title).color(theme::ACCENT_LIGHT).font(theme::font_button()));
                                ui.add_space(2.0);
                                // Show relevant lines
                                for line in content.lines() {
                                    if line.to_lowercase().contains(&search) || line.trim().is_empty() {
                                        ui.label(line);
                                    }
                                }
                                ui.add_space(8.0);
                                found = true;
                            }
                        }
                        if !found {
                            ui.colored_label(theme::TEXT_DIM, "No results found.");
                        }
                    }
                });
            });
        });

    state.open = open;
}
