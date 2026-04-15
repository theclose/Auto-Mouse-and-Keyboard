//! Typed action model — one variant per action type, with validated parameters.
//!
//! Each variant contains only the fields relevant to that action type.
//! This eliminates the bag-of-strings problem from `RawAction::params`.

use amk_schema::OnErrorPolicy;

/// Mouse button specifier.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum MouseButton {
    #[default]
    Left,
    Right,
    Middle,
}

/// A fully typed, validated action.
#[derive(Debug, Clone, PartialEq)]
pub struct TypedAction {
    /// The specific action and its parameters.
    pub kind: ActionKind,
    /// Delay (ms) after this action completes.
    pub delay_after: u32,
    /// Repeat count.
    pub repeat_count: u32,
    /// User description.
    pub description: String,
    /// Whether this action is enabled.
    pub enabled: bool,
    /// Error handling policy.
    pub on_error: OnErrorPolicy,
    /// UI color tag.
    pub color: Option<String>,
    /// Bookmark flag.
    pub bookmarked: bool,
}

/// All 36 action types as a strongly-typed enum.
///
/// Composite actions (if_*, loop_block, group) contain children as `Vec<TypedAction>`.
#[derive(Debug, Clone, PartialEq)]
#[allow(clippy::large_enum_variant)]
pub enum ActionKind {
    // ── Timing ─────────────────────────────────
    Delay {
        duration_ms: u32,
    },

    // ── Variables ──────────────────────────────
    SetVariable {
        name: String,
        value: String,
    },
    SplitString {
        input: String,
        delimiter: String,
        output_prefix: String,
    },

    // ── Meta ───────────────────────────────────
    Comment {
        text: String,
    },
    Group {
        name: String,
        children: Vec<TypedAction>,
    },

    // ── System ─────────────────────────────────
    RunCommand {
        command: String,
        wait: bool,
        capture_output: String, // variable name, empty = don't capture
    },
    LogToFile {
        file_path: String,
        message: String,
        append: bool,
    },
    ReadFileLine {
        file_path: String,
        line_number: i32, // -1 = random
        output_var: String,
    },
    WriteToFile {
        file_path: String,
        content: String,
        append: bool,
    },
    ReadClipboard {
        output_var: String,
    },
    ActivateWindow {
        title: String,
        match_type: String, // "exact", "contains", "regex"
    },

    // ── Keyboard ───────────────────────────────
    KeyPress {
        key: String,
        duration_ms: u32,
    },
    KeyCombo {
        keys: Vec<String>,
    },
    TypeText {
        text: String,
        interval_ms: f64,
    },
    Hotkey {
        keys: Vec<String>,
    },

    // ── Mouse ──────────────────────────────────
    MouseClick {
        x: i32,
        y: i32,
        button: MouseButton,
        clicks: u32,
    },
    MouseDoubleClick {
        x: i32,
        y: i32,
        button: MouseButton,
    },
    MouseRightClick {
        x: i32,
        y: i32,
    },
    MouseMove {
        x: i32,
        y: i32,
        duration_ms: u32,
    },
    MouseDrag {
        start_x: i32,
        start_y: i32,
        end_x: i32,
        end_y: i32,
        duration_ms: u32,
        button: MouseButton,
    },
    MouseScroll {
        x: i32,
        y: i32,
        clicks: i32, // positive = up, negative = down
    },

    // ── Pixel ──────────────────────────────────
    CheckPixelColor {
        x: i32,
        y: i32,
        expected_color: String,    // hex "#RRGGBB"
        tolerance: u32,
        result_var: String,
    },
    WaitForColor {
        x: i32,
        y: i32,
        expected_color: String,
        tolerance: u32,
        timeout_ms: u32,
    },

    // ── Image ──────────────────────────────────
    WaitForImage {
        image_path: String,
        confidence: f64,
        timeout_ms: u32,
        region: Option<[i32; 4]>, // [x, y, w, h]
        grayscale: bool,
    },
    ClickOnImage {
        image_path: String,
        confidence: f64,
        timeout_ms: u32,
        button: MouseButton,
        region: Option<[i32; 4]>,
        offset_x: i32,
        offset_y: i32,
    },
    ImageExists {
        image_path: String,
        confidence: f64,
        result_var: String,
        region: Option<[i32; 4]>,
    },
    TakeScreenshot {
        file_path: String,
        region: Option<[i32; 4]>,
    },

    // ── OCR ────────────────────────────────────
    CaptureText {
        region: [i32; 4], // [x, y, w, h]
        output_var: String,
        language: String,
    },

    // ── Security ───────────────────────────────
    SecureTypeText {
        encrypted_text: String,
        interval_ms: f64,
    },

    // ── Macro ──────────────────────────────────
    RunMacro {
        macro_path: String,
    },

    // ── Stealth (Win32 PostMessage) ────────────
    StealthClick {
        window_title: String,
        x: i32,
        y: i32,
        button: MouseButton,
    },
    StealthType {
        window_title: String,
        text: String,
        interval_ms: f64,
    },

    // ── Composite (branching/looping) ──────────
    IfVariable {
        variable: String,
        operator: String,  // "==", "!=", ">", "<", ">=", "<="
        value: String,
        then_actions: Vec<TypedAction>,
        else_actions: Vec<TypedAction>,
    },
    IfPixelColor {
        x: i32,
        y: i32,
        expected_color: String,
        tolerance: u32,
        then_actions: Vec<TypedAction>,
        else_actions: Vec<TypedAction>,
    },
    IfImageFound {
        image_path: String,
        confidence: f64,
        region: Option<[i32; 4]>,
        then_actions: Vec<TypedAction>,
        else_actions: Vec<TypedAction>,
    },
    LoopBlock {
        count: i32, // -1 = infinite
        children: Vec<TypedAction>,
    },
}
