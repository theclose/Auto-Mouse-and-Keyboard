use std::path::Path;

use amk_schema::RawAction;
use serde::de::DeserializeOwned;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use thiserror::Error;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CommonActionData {
    pub delay_after: u32,
    pub repeat_count: u32,
    pub description: String,
    pub enabled: bool,
    pub on_error: String,
    pub color: Option<String>,
    pub bookmarked: bool,
}

impl Default for CommonActionData {
    fn default() -> Self {
        Self {
            delay_after: 0,
            repeat_count: 1,
            description: String::new(),
            enabled: true,
            on_error: "stop".to_string(),
            color: None,
            bookmarked: false,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Action {
    pub common: CommonActionData,
    pub kind: ActionKind,
}

#[derive(Debug, Error)]
pub enum ActionModelError {
    #[error("unknown action type: {0}")]
    UnknownActionType(String),
    #[error("invalid params for `{action_type}`: {source}")]
    InvalidParams {
        action_type: String,
        #[source]
        source: serde_json::Error,
    },
    #[error("invalid legacy else_action_json for `{action_type}`: {source}")]
    InvalidElseActionJson {
        action_type: String,
        #[source]
        source: serde_json::Error,
    },
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum ActionKind {
    Delay(DelayAction),
    LoopBlock(LoopBlockAction),
    IfImageFound(IfImageFoundAction),
    IfPixelColor(IfPixelColorAction),
    IfVariable(IfVariableAction),
    SetVariable(SetVariableAction),
    SplitString(SplitStringAction),
    Comment(CommentAction),
    Group(GroupAction),
    MouseClick(MouseClickAction),
    MouseDoubleClick(MouseDoubleClickAction),
    MouseRightClick(MouseRightClickAction),
    MouseMove(MouseMoveAction),
    MouseDrag(MouseDragAction),
    MouseScroll(MouseScrollAction),
    KeyPress(KeyPressAction),
    KeyCombo(KeyChordAction),
    TypeText(TypeTextAction),
    Hotkey(KeyChordAction),
    WaitForImage(WaitForImageAction),
    ClickOnImage(ClickOnImageAction),
    ImageExists(ImageExistsAction),
    TakeScreenshot(TakeScreenshotAction),
    CheckPixelColor(CheckPixelColorAction),
    WaitForColor(WaitForColorAction),
    ActivateWindow(ActivateWindowAction),
    LogToFile(LogToFileAction),
    ReadClipboard(ReadClipboardAction),
    ReadFileLine(ReadFileLineAction),
    WriteToFile(WriteToFileAction),
    SecureTypeText(SecureTypeTextAction),
    RunMacro(RunMacroAction),
    CaptureText(CaptureTextAction),
    RunCommand(RunCommandAction),
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct DelayAction {
    pub duration_ms: u32,
    pub dynamic_ms: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct LoopBlockAction {
    pub iterations: u32,
    pub sub_actions: Vec<Action>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct IfImageFoundAction {
    pub image_path: String,
    pub confidence: f64,
    pub timeout_ms: u32,
    pub region_x: i32,
    pub region_y: i32,
    pub region_w: i32,
    pub region_h: i32,
    pub then_actions: Vec<Action>,
    pub else_actions: Vec<Action>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct IfPixelColorAction {
    pub x: i32,
    pub y: i32,
    pub r: i32,
    pub g: i32,
    pub b: i32,
    pub tolerance: i32,
    pub then_actions: Vec<Action>,
    pub else_actions: Vec<Action>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct IfVariableAction {
    pub var_name: String,
    pub operator: String,
    pub compare_value: String,
    pub then_actions: Vec<Action>,
    pub else_actions: Vec<Action>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct SetVariableAction {
    pub var_name: String,
    pub value: String,
    pub operation: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct SplitStringAction {
    pub source_var: String,
    pub delimiter: String,
    pub field_index: usize,
    pub target_var: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct CommentAction {
    pub text: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct GroupAction {
    pub name: String,
    pub children: Vec<Action>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct MouseClickAction {
    pub x: i32,
    pub y: i32,
    pub duration: f64,
    pub context_image: Option<String>,
    pub dynamic_x: Option<String>,
    pub dynamic_y: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct MouseDoubleClickAction {
    pub x: i32,
    pub y: i32,
    pub context_image: Option<String>,
    pub dynamic_x: Option<String>,
    pub dynamic_y: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct MouseRightClickAction {
    pub x: i32,
    pub y: i32,
    pub context_image: Option<String>,
    pub dynamic_x: Option<String>,
    pub dynamic_y: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct MouseMoveAction {
    pub x: i32,
    pub y: i32,
    pub duration: f64,
    pub dynamic_x: Option<String>,
    pub dynamic_y: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct MouseDragAction {
    pub x: i32,
    pub y: i32,
    pub start_x: i32,
    pub start_y: i32,
    pub duration: f64,
    pub button: String,
    pub dynamic_x: Option<String>,
    pub dynamic_y: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct MouseScrollAction {
    pub x: i32,
    pub y: i32,
    pub clicks: i32,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct KeyPressAction {
    pub key: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct KeyChordAction {
    pub keys: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct TypeTextAction {
    pub text: String,
    pub interval: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct WaitForImageAction {
    pub image_path: String,
    pub confidence: f64,
    pub timeout_ms: u32,
    pub region_x: i32,
    pub region_y: i32,
    pub region_w: i32,
    pub region_h: i32,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct ClickOnImageAction {
    pub image_path: String,
    pub confidence: f64,
    pub timeout_ms: u32,
    pub button: String,
    pub region_x: i32,
    pub region_y: i32,
    pub region_w: i32,
    pub region_h: i32,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct ImageExistsAction {
    pub image_path: String,
    pub confidence: f64,
    pub region_x: i32,
    pub region_y: i32,
    pub region_w: i32,
    pub region_h: i32,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct TakeScreenshotAction {
    pub save_dir: String,
    pub filename_pattern: String,
    pub region_x: i32,
    pub region_y: i32,
    pub region_w: i32,
    pub region_h: i32,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct CheckPixelColorAction {
    pub x: i32,
    pub y: i32,
    pub r: i32,
    pub g: i32,
    pub b: i32,
    pub tolerance: i32,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct WaitForColorAction {
    pub x: i32,
    pub y: i32,
    pub r: i32,
    pub g: i32,
    pub b: i32,
    pub tolerance: i32,
    pub timeout_ms: u32,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct ActivateWindowAction {
    pub window_title: String,
    pub exact_match: bool,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct LogToFileAction {
    pub message: String,
    pub file_path: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct ReadClipboardAction {
    pub var_name: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct ReadFileLineAction {
    pub file_path: String,
    pub line_number: String,
    pub var_name: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct WriteToFileAction {
    pub file_path: String,
    pub text: String,
    pub mode: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct SecureTypeTextAction {
    pub encrypted_text: String,
    pub interval: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct RunMacroAction {
    pub macro_path: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct CaptureTextAction {
    pub x: i32,
    pub y: i32,
    pub width: i32,
    pub height: i32,
    pub var_name: String,
    pub lang: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct RunCommandAction {
    pub command: String,
    pub timeout: u32,
    pub var_name: Option<String>,
    pub working_dir: Option<String>,
    pub ignore_exit_code: bool,
}

#[derive(Debug, Clone, PartialEq, Deserialize)]
#[serde(untagged)]
enum KeyListInput {
    One(String),
    Many(Vec<String>),
}

impl KeyListInput {
    fn into_vec(self) -> Vec<String> {
        match self {
            Self::One(value) => value
                .split('+')
                .map(str::trim)
                .filter(|part| !part.is_empty())
                .map(ToString::to_string)
                .collect(),
            Self::Many(values) => values,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
struct DelayParamsRaw {
    #[serde(default)]
    duration_ms: u32,
    #[serde(default)]
    dynamic_ms: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
struct MouseClickParamsRaw {
    #[serde(default)]
    x: i32,
    #[serde(default)]
    y: i32,
    #[serde(default)]
    duration: f64,
    #[serde(default)]
    context_image: Option<String>,
    #[serde(default)]
    dynamic_x: Option<String>,
    #[serde(default)]
    dynamic_y: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
struct MouseDoubleClickParamsRaw {
    #[serde(default)]
    x: i32,
    #[serde(default)]
    y: i32,
    #[serde(default)]
    context_image: Option<String>,
    #[serde(default)]
    dynamic_x: Option<String>,
    #[serde(default)]
    dynamic_y: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
struct MouseMoveParamsRaw {
    #[serde(default)]
    x: i32,
    #[serde(default)]
    y: i32,
    #[serde(default)]
    duration: f64,
    #[serde(default)]
    dynamic_x: Option<String>,
    #[serde(default)]
    dynamic_y: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
struct MouseDragParamsRaw {
    #[serde(default)]
    x: i32,
    #[serde(default)]
    y: i32,
    #[serde(default)]
    start_x: i32,
    #[serde(default)]
    start_y: i32,
    #[serde(default)]
    duration: f64,
    #[serde(default = "default_left_button")]
    button: String,
    #[serde(default)]
    dynamic_x: Option<String>,
    #[serde(default)]
    dynamic_y: Option<String>,
}

fn default_left_button() -> String {
    "left".to_string()
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
struct MouseScrollParamsRaw {
    #[serde(default)]
    x: i32,
    #[serde(default)]
    y: i32,
    #[serde(default)]
    clicks: i32,
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
struct KeyPressParamsRaw {
    #[serde(default)]
    key: String,
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
struct KeyChordParamsRaw {
    #[serde(default)]
    keys: Option<KeyListInput>,
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
struct TypeTextParamsRaw {
    #[serde(default)]
    text: String,
    #[serde(default)]
    interval: f64,
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
struct ImageSearchParamsRaw {
    #[serde(default, alias = "template_path")]
    image_path: String,
    #[serde(default)]
    confidence: f64,
    #[serde(default)]
    timeout_ms: u32,
    #[serde(default)]
    button: String,
    #[serde(default)]
    region_x: i32,
    #[serde(default)]
    region_y: i32,
    #[serde(default)]
    region_w: i32,
    #[serde(default)]
    region_h: i32,
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
struct ScreenshotParamsRaw {
    #[serde(default)]
    save_dir: String,
    #[serde(default)]
    filename_pattern: String,
    #[serde(default)]
    save_path: String,
    #[serde(default)]
    region_x: i32,
    #[serde(default)]
    region_y: i32,
    #[serde(default)]
    region_w: i32,
    #[serde(default)]
    region_h: i32,
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
struct PixelParamsRaw {
    #[serde(default)]
    x: i32,
    #[serde(default)]
    y: i32,
    #[serde(default)]
    r: i32,
    #[serde(default)]
    g: i32,
    #[serde(default)]
    b: i32,
    #[serde(default)]
    tolerance: i32,
    #[serde(default)]
    timeout_ms: u32,
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
struct ActivateWindowParamsRaw {
    #[serde(default, alias = "title")]
    window_title: String,
    #[serde(default)]
    exact_match: bool,
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
struct LogToFileParamsRaw {
    #[serde(default, alias = "text")]
    message: String,
    #[serde(default)]
    file_path: String,
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
struct ReadClipboardParamsRaw {
    #[serde(default = "default_clipboard_var")]
    var_name: String,
}

fn default_clipboard_var() -> String {
    "clipboard".to_string()
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
struct ReadFileLineParamsRaw {
    #[serde(default)]
    file_path: String,
    #[serde(default)]
    line_number: Option<String>,
    #[serde(default)]
    line_index_var: Option<String>,
    #[serde(default)]
    var_name: Option<String>,
    #[serde(default)]
    target_var: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
struct WriteToFileParamsRaw {
    #[serde(default)]
    file_path: String,
    #[serde(default)]
    text: String,
    #[serde(default = "default_append_mode")]
    mode: String,
}

fn default_append_mode() -> String {
    "append".to_string()
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
struct SecureTypeTextParamsRaw {
    #[serde(default)]
    encrypted_text: String,
    #[serde(default)]
    interval: f64,
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
struct RunMacroParamsRaw {
    #[serde(default)]
    macro_path: String,
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
struct CaptureTextParamsRaw {
    #[serde(default)]
    x: i32,
    #[serde(default)]
    y: i32,
    #[serde(default)]
    width: i32,
    #[serde(default)]
    height: i32,
    #[serde(default = "default_ocr_var")]
    var_name: String,
    #[serde(default = "default_ocr_lang")]
    lang: String,
}

fn default_ocr_var() -> String {
    "ocr_text".to_string()
}

fn default_ocr_lang() -> String {
    "eng".to_string()
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
struct RunCommandParamsRaw {
    #[serde(default)]
    command: String,
    #[serde(default = "default_command_timeout")]
    timeout: u32,
    #[serde(default)]
    var_name: Option<String>,
    #[serde(default)]
    working_dir: Option<String>,
    #[serde(default)]
    ignore_exit_code: bool,
}

fn default_command_timeout() -> u32 {
    30
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
struct LoopBlockParamsRaw {
    #[serde(default = "default_iterations")]
    iterations: u32,
    #[serde(default)]
    sub_actions: Vec<RawAction>,
}

fn default_iterations() -> u32 {
    1
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
struct ConditionalImageParamsRaw {
    #[serde(default, alias = "template_path")]
    image_path: String,
    #[serde(default)]
    confidence: f64,
    #[serde(default)]
    timeout_ms: u32,
    #[serde(default)]
    region_x: i32,
    #[serde(default)]
    region_y: i32,
    #[serde(default)]
    region_w: i32,
    #[serde(default)]
    region_h: i32,
    #[serde(default)]
    then_actions: Vec<RawAction>,
    #[serde(default)]
    else_actions: Vec<RawAction>,
    #[serde(default)]
    else_action_json: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
struct ConditionalPixelParamsRaw {
    #[serde(default)]
    x: i32,
    #[serde(default)]
    y: i32,
    #[serde(default)]
    r: i32,
    #[serde(default)]
    g: i32,
    #[serde(default)]
    b: i32,
    #[serde(default)]
    tolerance: i32,
    #[serde(default)]
    then_actions: Vec<RawAction>,
    #[serde(default)]
    else_actions: Vec<RawAction>,
    #[serde(default)]
    else_action_json: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
struct ConditionalVarParamsRaw {
    #[serde(default)]
    var_name: String,
    #[serde(default = "default_var_operator")]
    operator: String,
    #[serde(default)]
    compare_value: String,
    #[serde(default)]
    then_actions: Vec<RawAction>,
    #[serde(default)]
    else_actions: Vec<RawAction>,
    #[serde(default)]
    else_action_json: Option<String>,
}

fn default_var_operator() -> String {
    "==".to_string()
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
struct SetVariableParamsRaw {
    #[serde(default)]
    var_name: String,
    #[serde(default)]
    value: String,
    #[serde(default = "default_set_operation")]
    operation: String,
}

fn default_set_operation() -> String {
    "set".to_string()
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
struct SplitStringParamsRaw {
    #[serde(default)]
    source_var: String,
    #[serde(default = "default_comma")]
    delimiter: String,
    #[serde(default)]
    field_index: usize,
    #[serde(default)]
    target_var: String,
}

fn default_comma() -> String {
    ",".to_string()
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
struct CommentParamsRaw {
    #[serde(default)]
    text: String,
}

#[derive(Debug, Clone, PartialEq, Deserialize, Default)]
struct GroupParamsRaw {
    #[serde(default = "default_group_name")]
    name: String,
    #[serde(default)]
    children: Vec<RawAction>,
}

fn default_group_name() -> String {
    "Group".to_string()
}

impl Action {
    pub fn action_type(&self) -> &'static str {
        match &self.kind {
            ActionKind::Delay(_) => "delay",
            ActionKind::LoopBlock(_) => "loop_block",
            ActionKind::IfImageFound(_) => "if_image_found",
            ActionKind::IfPixelColor(_) => "if_pixel_color",
            ActionKind::IfVariable(_) => "if_variable",
            ActionKind::SetVariable(_) => "set_variable",
            ActionKind::SplitString(_) => "split_string",
            ActionKind::Comment(_) => "comment",
            ActionKind::Group(_) => "group",
            ActionKind::MouseClick(_) => "mouse_click",
            ActionKind::MouseDoubleClick(_) => "mouse_double_click",
            ActionKind::MouseRightClick(_) => "mouse_right_click",
            ActionKind::MouseMove(_) => "mouse_move",
            ActionKind::MouseDrag(_) => "mouse_drag",
            ActionKind::MouseScroll(_) => "mouse_scroll",
            ActionKind::KeyPress(_) => "key_press",
            ActionKind::KeyCombo(_) => "key_combo",
            ActionKind::TypeText(_) => "type_text",
            ActionKind::Hotkey(_) => "hotkey",
            ActionKind::WaitForImage(_) => "wait_for_image",
            ActionKind::ClickOnImage(_) => "click_on_image",
            ActionKind::ImageExists(_) => "image_exists",
            ActionKind::TakeScreenshot(_) => "take_screenshot",
            ActionKind::CheckPixelColor(_) => "check_pixel_color",
            ActionKind::WaitForColor(_) => "wait_for_color",
            ActionKind::ActivateWindow(_) => "activate_window",
            ActionKind::LogToFile(_) => "log_to_file",
            ActionKind::ReadClipboard(_) => "read_clipboard",
            ActionKind::ReadFileLine(_) => "read_file_line",
            ActionKind::WriteToFile(_) => "write_to_file",
            ActionKind::SecureTypeText(_) => "secure_type_text",
            ActionKind::RunMacro(_) => "run_macro",
            ActionKind::CaptureText(_) => "capture_text",
            ActionKind::RunCommand(_) => "run_command",
        }
    }

    pub fn is_composite(&self) -> bool {
        matches!(
            self.kind,
            ActionKind::LoopBlock(_)
                | ActionKind::IfImageFound(_)
                | ActionKind::IfPixelColor(_)
                | ActionKind::IfVariable(_)
                | ActionKind::Group(_)
        )
    }

    pub fn from_raw(raw: RawAction) -> Result<Self, ActionModelError> {
        let normalized_type = raw.normalized_type().to_string();
        let common = CommonActionData {
            delay_after: raw.delay_after,
            repeat_count: raw.repeat_count.max(1),
            description: raw.description.clone(),
            enabled: raw.enabled,
            on_error: raw.on_error.clone(),
            color: raw.color.clone(),
            bookmarked: raw.bookmarked,
        };

        let kind = match normalized_type.as_str() {
            "delay" => {
                let params = decode_params::<DelayParamsRaw>(&raw)?;
                ActionKind::Delay(DelayAction {
                    duration_ms: params.duration_ms,
                    dynamic_ms: params.dynamic_ms,
                })
            }
            "loop_block" => {
                let params = decode_params::<LoopBlockParamsRaw>(&raw)?;
                ActionKind::LoopBlock(LoopBlockAction {
                    iterations: params.iterations,
                    sub_actions: map_actions(params.sub_actions)?,
                })
            }
            "if_image_found" => {
                let params = decode_params::<ConditionalImageParamsRaw>(&raw)?;
                let else_actions = merge_legacy_else_actions(
                    params.else_actions,
                    params.else_action_json,
                    normalized_type.as_str(),
                )?;
                ActionKind::IfImageFound(IfImageFoundAction {
                    image_path: params.image_path,
                    confidence: params.confidence,
                    timeout_ms: params.timeout_ms,
                    region_x: params.region_x,
                    region_y: params.region_y,
                    region_w: params.region_w,
                    region_h: params.region_h,
                    then_actions: map_actions(params.then_actions)?,
                    else_actions,
                })
            }
            "if_pixel_color" => {
                let params = decode_params::<ConditionalPixelParamsRaw>(&raw)?;
                let else_actions = merge_legacy_else_actions(
                    params.else_actions,
                    params.else_action_json,
                    normalized_type.as_str(),
                )?;
                ActionKind::IfPixelColor(IfPixelColorAction {
                    x: params.x,
                    y: params.y,
                    r: params.r,
                    g: params.g,
                    b: params.b,
                    tolerance: params.tolerance,
                    then_actions: map_actions(params.then_actions)?,
                    else_actions,
                })
            }
            "if_variable" => {
                let params = decode_params::<ConditionalVarParamsRaw>(&raw)?;
                let else_actions = merge_legacy_else_actions(
                    params.else_actions,
                    params.else_action_json,
                    normalized_type.as_str(),
                )?;
                ActionKind::IfVariable(IfVariableAction {
                    var_name: params.var_name,
                    operator: params.operator,
                    compare_value: params.compare_value,
                    then_actions: map_actions(params.then_actions)?,
                    else_actions,
                })
            }
            "set_variable" => {
                let params = decode_params::<SetVariableParamsRaw>(&raw)?;
                ActionKind::SetVariable(SetVariableAction {
                    var_name: params.var_name,
                    value: params.value,
                    operation: params.operation,
                })
            }
            "split_string" => {
                let params = decode_params::<SplitStringParamsRaw>(&raw)?;
                ActionKind::SplitString(SplitStringAction {
                    source_var: params.source_var,
                    delimiter: params.delimiter,
                    field_index: params.field_index,
                    target_var: params.target_var,
                })
            }
            "comment" => {
                let params = decode_params::<CommentParamsRaw>(&raw)?;
                ActionKind::Comment(CommentAction { text: params.text })
            }
            "group" => {
                let params = decode_params::<GroupParamsRaw>(&raw)?;
                ActionKind::Group(GroupAction {
                    name: params.name,
                    children: map_actions(params.children)?,
                })
            }
            "mouse_click" => {
                let params = decode_params::<MouseClickParamsRaw>(&raw)?;
                ActionKind::MouseClick(MouseClickAction {
                    x: params.x,
                    y: params.y,
                    duration: params.duration,
                    context_image: params.context_image,
                    dynamic_x: params.dynamic_x,
                    dynamic_y: params.dynamic_y,
                })
            }
            "mouse_double_click" => {
                let params = decode_params::<MouseDoubleClickParamsRaw>(&raw)?;
                ActionKind::MouseDoubleClick(MouseDoubleClickAction {
                    x: params.x,
                    y: params.y,
                    context_image: params.context_image,
                    dynamic_x: params.dynamic_x,
                    dynamic_y: params.dynamic_y,
                })
            }
            "mouse_right_click" => {
                let params = decode_params::<MouseDoubleClickParamsRaw>(&raw)?;
                ActionKind::MouseRightClick(MouseRightClickAction {
                    x: params.x,
                    y: params.y,
                    context_image: params.context_image,
                    dynamic_x: params.dynamic_x,
                    dynamic_y: params.dynamic_y,
                })
            }
            "mouse_move" => {
                let params = decode_params::<MouseMoveParamsRaw>(&raw)?;
                ActionKind::MouseMove(MouseMoveAction {
                    x: params.x,
                    y: params.y,
                    duration: params.duration,
                    dynamic_x: params.dynamic_x,
                    dynamic_y: params.dynamic_y,
                })
            }
            "mouse_drag" => {
                let params = decode_params::<MouseDragParamsRaw>(&raw)?;
                ActionKind::MouseDrag(MouseDragAction {
                    x: params.x,
                    y: params.y,
                    start_x: params.start_x,
                    start_y: params.start_y,
                    duration: params.duration,
                    button: params.button,
                    dynamic_x: params.dynamic_x,
                    dynamic_y: params.dynamic_y,
                })
            }
            "mouse_scroll" => {
                let params = decode_params::<MouseScrollParamsRaw>(&raw)?;
                ActionKind::MouseScroll(MouseScrollAction {
                    x: params.x,
                    y: params.y,
                    clicks: params.clicks,
                })
            }
            "key_press" => {
                let params = decode_params::<KeyPressParamsRaw>(&raw)?;
                ActionKind::KeyPress(KeyPressAction { key: params.key })
            }
            "key_combo" => {
                let params = decode_params::<KeyChordParamsRaw>(&raw)?;
                ActionKind::KeyCombo(KeyChordAction {
                    keys: params.keys.map(KeyListInput::into_vec).unwrap_or_default(),
                })
            }
            "type_text" => {
                let params = decode_params::<TypeTextParamsRaw>(&raw)?;
                ActionKind::TypeText(TypeTextAction {
                    text: params.text,
                    interval: params.interval,
                })
            }
            "hotkey" => {
                let params = decode_params::<KeyChordParamsRaw>(&raw)?;
                ActionKind::Hotkey(KeyChordAction {
                    keys: params.keys.map(KeyListInput::into_vec).unwrap_or_default(),
                })
            }
            "wait_for_image" => {
                let params = decode_params::<ImageSearchParamsRaw>(&raw)?;
                ActionKind::WaitForImage(WaitForImageAction {
                    image_path: params.image_path,
                    confidence: params.confidence,
                    timeout_ms: params.timeout_ms,
                    region_x: params.region_x,
                    region_y: params.region_y,
                    region_w: params.region_w,
                    region_h: params.region_h,
                })
            }
            "click_on_image" => {
                let params = decode_params::<ImageSearchParamsRaw>(&raw)?;
                ActionKind::ClickOnImage(ClickOnImageAction {
                    image_path: params.image_path,
                    confidence: params.confidence,
                    timeout_ms: params.timeout_ms,
                    button: params.button,
                    region_x: params.region_x,
                    region_y: params.region_y,
                    region_w: params.region_w,
                    region_h: params.region_h,
                })
            }
            "image_exists" => {
                let params = decode_params::<ImageSearchParamsRaw>(&raw)?;
                ActionKind::ImageExists(ImageExistsAction {
                    image_path: params.image_path,
                    confidence: params.confidence,
                    region_x: params.region_x,
                    region_y: params.region_y,
                    region_w: params.region_w,
                    region_h: params.region_h,
                })
            }
            "take_screenshot" => {
                let params = decode_params::<ScreenshotParamsRaw>(&raw)?;
                let (save_dir, filename_pattern) = normalize_screenshot_params(&params);
                ActionKind::TakeScreenshot(TakeScreenshotAction {
                    save_dir,
                    filename_pattern,
                    region_x: params.region_x,
                    region_y: params.region_y,
                    region_w: params.region_w,
                    region_h: params.region_h,
                })
            }
            "check_pixel_color" => {
                let params = decode_params::<PixelParamsRaw>(&raw)?;
                ActionKind::CheckPixelColor(CheckPixelColorAction {
                    x: params.x,
                    y: params.y,
                    r: params.r,
                    g: params.g,
                    b: params.b,
                    tolerance: params.tolerance,
                })
            }
            "wait_for_color" => {
                let params = decode_params::<PixelParamsRaw>(&raw)?;
                ActionKind::WaitForColor(WaitForColorAction {
                    x: params.x,
                    y: params.y,
                    r: params.r,
                    g: params.g,
                    b: params.b,
                    tolerance: params.tolerance,
                    timeout_ms: params.timeout_ms,
                })
            }
            "activate_window" => {
                let params = decode_params::<ActivateWindowParamsRaw>(&raw)?;
                ActionKind::ActivateWindow(ActivateWindowAction {
                    window_title: params.window_title,
                    exact_match: params.exact_match,
                })
            }
            "log_to_file" => {
                let params = decode_params::<LogToFileParamsRaw>(&raw)?;
                ActionKind::LogToFile(LogToFileAction {
                    message: params.message,
                    file_path: params.file_path,
                })
            }
            "read_clipboard" => {
                let params = decode_params::<ReadClipboardParamsRaw>(&raw)?;
                ActionKind::ReadClipboard(ReadClipboardAction {
                    var_name: params.var_name,
                })
            }
            "read_file_line" => {
                let params = decode_params::<ReadFileLineParamsRaw>(&raw)?;
                ActionKind::ReadFileLine(ReadFileLineAction {
                    file_path: params.file_path,
                    line_number: params
                        .line_number
                        .or_else(|| params.line_index_var.map(|name| format!("${{{name}}}")))
                        .unwrap_or_else(|| "1".to_string()),
                    var_name: params
                        .var_name
                        .or(params.target_var)
                        .unwrap_or_else(|| "line".to_string()),
                })
            }
            "write_to_file" => {
                let params = decode_params::<WriteToFileParamsRaw>(&raw)?;
                ActionKind::WriteToFile(WriteToFileAction {
                    file_path: params.file_path,
                    text: params.text,
                    mode: params.mode,
                })
            }
            "secure_type_text" => {
                let params = decode_params::<SecureTypeTextParamsRaw>(&raw)?;
                ActionKind::SecureTypeText(SecureTypeTextAction {
                    encrypted_text: params.encrypted_text,
                    interval: params.interval,
                })
            }
            "run_macro" => {
                let params = decode_params::<RunMacroParamsRaw>(&raw)?;
                ActionKind::RunMacro(RunMacroAction {
                    macro_path: params.macro_path,
                })
            }
            "capture_text" => {
                let params = decode_params::<CaptureTextParamsRaw>(&raw)?;
                ActionKind::CaptureText(CaptureTextAction {
                    x: params.x,
                    y: params.y,
                    width: params.width,
                    height: params.height,
                    var_name: params.var_name,
                    lang: params.lang,
                })
            }
            "run_command" => {
                let params = decode_params::<RunCommandParamsRaw>(&raw)?;
                ActionKind::RunCommand(RunCommandAction {
                    command: params.command,
                    timeout: params.timeout,
                    var_name: params.var_name,
                    working_dir: params.working_dir,
                    ignore_exit_code: params.ignore_exit_code,
                })
            }
            other => return Err(ActionModelError::UnknownActionType(other.to_string())),
        };

        Ok(Self { common, kind })
    }

    pub fn to_raw(&self) -> RawAction {
        let params = match &self.kind {
            ActionKind::Delay(value) => json!({
                "duration_ms": value.duration_ms,
                "dynamic_ms": value.dynamic_ms,
            }),
            ActionKind::LoopBlock(value) => json!({
                "iterations": value.iterations,
                "sub_actions": value.sub_actions.iter().map(Action::to_raw).collect::<Vec<_>>(),
            }),
            ActionKind::IfImageFound(value) => json!({
                "image_path": value.image_path,
                "confidence": value.confidence,
                "timeout_ms": value.timeout_ms,
                "region_x": value.region_x,
                "region_y": value.region_y,
                "region_w": value.region_w,
                "region_h": value.region_h,
                "then_actions": value.then_actions.iter().map(Action::to_raw).collect::<Vec<_>>(),
                "else_actions": value.else_actions.iter().map(Action::to_raw).collect::<Vec<_>>(),
            }),
            ActionKind::IfPixelColor(value) => json!({
                "x": value.x,
                "y": value.y,
                "r": value.r,
                "g": value.g,
                "b": value.b,
                "tolerance": value.tolerance,
                "then_actions": value.then_actions.iter().map(Action::to_raw).collect::<Vec<_>>(),
                "else_actions": value.else_actions.iter().map(Action::to_raw).collect::<Vec<_>>(),
            }),
            ActionKind::IfVariable(value) => json!({
                "var_name": value.var_name,
                "operator": value.operator,
                "compare_value": value.compare_value,
                "then_actions": value.then_actions.iter().map(Action::to_raw).collect::<Vec<_>>(),
                "else_actions": value.else_actions.iter().map(Action::to_raw).collect::<Vec<_>>(),
            }),
            ActionKind::SetVariable(value) => json!({
                "var_name": value.var_name,
                "value": value.value,
                "operation": value.operation,
            }),
            ActionKind::SplitString(value) => json!({
                "source_var": value.source_var,
                "delimiter": value.delimiter,
                "field_index": value.field_index,
                "target_var": value.target_var,
            }),
            ActionKind::Comment(value) => json!({ "text": value.text }),
            ActionKind::Group(value) => json!({
                "name": value.name,
                "children": value.children.iter().map(Action::to_raw).collect::<Vec<_>>(),
            }),
            ActionKind::MouseClick(value) => json!({
                "x": value.x,
                "y": value.y,
                "duration": value.duration,
                "context_image": value.context_image,
                "dynamic_x": value.dynamic_x,
                "dynamic_y": value.dynamic_y,
            }),
            ActionKind::MouseDoubleClick(value) => json!({
                "x": value.x,
                "y": value.y,
                "context_image": value.context_image,
                "dynamic_x": value.dynamic_x,
                "dynamic_y": value.dynamic_y,
            }),
            ActionKind::MouseRightClick(value) => json!({
                "x": value.x,
                "y": value.y,
                "context_image": value.context_image,
                "dynamic_x": value.dynamic_x,
                "dynamic_y": value.dynamic_y,
            }),
            ActionKind::MouseMove(value) => json!({
                "x": value.x,
                "y": value.y,
                "duration": value.duration,
                "dynamic_x": value.dynamic_x,
                "dynamic_y": value.dynamic_y,
            }),
            ActionKind::MouseDrag(value) => json!({
                "x": value.x,
                "y": value.y,
                "start_x": value.start_x,
                "start_y": value.start_y,
                "duration": value.duration,
                "button": value.button,
                "dynamic_x": value.dynamic_x,
                "dynamic_y": value.dynamic_y,
            }),
            ActionKind::MouseScroll(value) => json!({
                "x": value.x,
                "y": value.y,
                "clicks": value.clicks,
            }),
            ActionKind::KeyPress(value) => json!({ "key": value.key }),
            ActionKind::KeyCombo(value) | ActionKind::Hotkey(value) => {
                json!({ "keys": value.keys })
            }
            ActionKind::TypeText(value) => json!({
                "text": value.text,
                "interval": value.interval,
            }),
            ActionKind::WaitForImage(value) => json!({
                "image_path": value.image_path,
                "confidence": value.confidence,
                "timeout_ms": value.timeout_ms,
                "region_x": value.region_x,
                "region_y": value.region_y,
                "region_w": value.region_w,
                "region_h": value.region_h,
            }),
            ActionKind::ClickOnImage(value) => json!({
                "image_path": value.image_path,
                "confidence": value.confidence,
                "timeout_ms": value.timeout_ms,
                "button": value.button,
                "region_x": value.region_x,
                "region_y": value.region_y,
                "region_w": value.region_w,
                "region_h": value.region_h,
            }),
            ActionKind::ImageExists(value) => json!({
                "image_path": value.image_path,
                "confidence": value.confidence,
                "region_x": value.region_x,
                "region_y": value.region_y,
                "region_w": value.region_w,
                "region_h": value.region_h,
            }),
            ActionKind::TakeScreenshot(value) => json!({
                "save_dir": value.save_dir,
                "filename_pattern": value.filename_pattern,
                "region_x": value.region_x,
                "region_y": value.region_y,
                "region_w": value.region_w,
                "region_h": value.region_h,
            }),
            ActionKind::CheckPixelColor(value) => json!({
                "x": value.x,
                "y": value.y,
                "r": value.r,
                "g": value.g,
                "b": value.b,
                "tolerance": value.tolerance,
            }),
            ActionKind::WaitForColor(value) => json!({
                "x": value.x,
                "y": value.y,
                "r": value.r,
                "g": value.g,
                "b": value.b,
                "tolerance": value.tolerance,
                "timeout_ms": value.timeout_ms,
            }),
            ActionKind::ActivateWindow(value) => json!({
                "window_title": value.window_title,
                "exact_match": value.exact_match,
            }),
            ActionKind::LogToFile(value) => json!({
                "message": value.message,
                "file_path": value.file_path,
            }),
            ActionKind::ReadClipboard(value) => json!({ "var_name": value.var_name }),
            ActionKind::ReadFileLine(value) => json!({
                "file_path": value.file_path,
                "line_number": value.line_number,
                "var_name": value.var_name,
            }),
            ActionKind::WriteToFile(value) => json!({
                "file_path": value.file_path,
                "text": value.text,
                "mode": value.mode,
            }),
            ActionKind::SecureTypeText(value) => json!({
                "encrypted_text": value.encrypted_text,
                "interval": value.interval,
            }),
            ActionKind::RunMacro(value) => json!({ "macro_path": value.macro_path }),
            ActionKind::CaptureText(value) => json!({
                "x": value.x,
                "y": value.y,
                "width": value.width,
                "height": value.height,
                "var_name": value.var_name,
                "lang": value.lang,
            }),
            ActionKind::RunCommand(value) => json!({
                "command": value.command,
                "timeout": value.timeout,
                "var_name": value.var_name,
                "working_dir": value.working_dir,
                "ignore_exit_code": value.ignore_exit_code,
            }),
        };

        RawAction {
            action_type: self.action_type().to_string(),
            params,
            delay_after: self.common.delay_after,
            repeat_count: self.common.repeat_count,
            description: self.common.description.clone(),
            enabled: self.common.enabled,
            on_error: self.common.on_error.clone(),
            color: self.common.color.clone(),
            bookmarked: self.common.bookmarked,
        }
    }
}

fn decode_params<T: DeserializeOwned + Default>(raw: &RawAction) -> Result<T, ActionModelError> {
    let params = if raw.params.is_null() {
        Value::Object(Default::default())
    } else {
        raw.params.clone()
    };
    serde_json::from_value(params).map_err(|source| ActionModelError::InvalidParams {
        action_type: raw.normalized_type().to_string(),
        source,
    })
}

fn map_actions(raw_actions: Vec<RawAction>) -> Result<Vec<Action>, ActionModelError> {
    raw_actions.into_iter().map(Action::from_raw).collect()
}

fn merge_legacy_else_actions(
    else_actions: Vec<RawAction>,
    else_action_json: Option<String>,
    action_type: &str,
) -> Result<Vec<Action>, ActionModelError> {
    if !else_actions.is_empty() {
        return map_actions(else_actions);
    }

    let Some(payload) = else_action_json else {
        return Ok(Vec::new());
    };

    if payload.trim().is_empty() {
        return Ok(Vec::new());
    }

    let parsed: Value = serde_json::from_str(&payload).map_err(|source| {
        ActionModelError::InvalidElseActionJson {
            action_type: action_type.to_string(),
            source,
        }
    })?;

    match parsed {
        Value::Object(_) => {
            let raw_action = serde_json::from_value(parsed).map_err(|source| {
                ActionModelError::InvalidElseActionJson {
                    action_type: action_type.to_string(),
                    source,
                }
            })?;
            Ok(vec![Action::from_raw(raw_action)?])
        }
        Value::Array(values) => {
            let mut actions = Vec::with_capacity(values.len());
            for value in values {
                let raw_action = serde_json::from_value(value).map_err(|source| {
                    ActionModelError::InvalidElseActionJson {
                        action_type: action_type.to_string(),
                        source,
                    }
                })?;
                actions.push(Action::from_raw(raw_action)?);
            }
            Ok(actions)
        }
        _ => Ok(Vec::new()),
    }
}

fn normalize_screenshot_params(params: &ScreenshotParamsRaw) -> (String, String) {
    if !params.save_dir.is_empty() {
        let pattern = if params.filename_pattern.is_empty() {
            "screenshot_%Y%m%d_%H%M%S.png".to_string()
        } else {
            params.filename_pattern.clone()
        };
        return (params.save_dir.clone(), pattern);
    }

    if params.save_path.is_empty() {
        return (
            "macros/screenshots".to_string(),
            "screenshot_%Y%m%d_%H%M%S.png".to_string(),
        );
    }

    let path = Path::new(&params.save_path);
    let save_dir = path
        .parent()
        .and_then(|parent| parent.to_str())
        .filter(|value| !value.is_empty())
        .unwrap_or("macros/screenshots")
        .to_string();
    let filename_pattern = path
        .file_name()
        .and_then(|name| name.to_str())
        .filter(|value| !value.is_empty())
        .unwrap_or("screenshot_%Y%m%d_%H%M%S.png")
        .to_string();
    (save_dir, filename_pattern)
}

#[cfg(test)]
mod tests {
    use super::*;
    use amk_schema::parse_macro_str;

    #[test]
    fn converts_example_macro_to_typed_actions() {
        let raw = include_str!("../../../../macros/example.json");
        let doc = parse_macro_str(raw).expect("macro should parse");
        let typed = doc
            .actions
            .into_iter()
            .map(Action::from_raw)
            .collect::<Result<Vec<_>, _>>()
            .expect("actions should convert");
        assert_eq!(typed.len(), 4);
        assert_eq!(typed[0].action_type(), "delay");
        assert_eq!(typed[1].action_type(), "mouse_click");
        assert_eq!(typed[2].action_type(), "type_text");
    }

    #[test]
    fn supports_key_combo_string_input() {
        let raw = RawAction {
            action_type: "key_combo".to_string(),
            params: json!({ "keys": "ctrl+shift+s" }),
            delay_after: 0,
            repeat_count: 1,
            description: String::new(),
            enabled: true,
            on_error: "stop".to_string(),
            color: None,
            bookmarked: false,
        };

        let action = Action::from_raw(raw).expect("conversion should succeed");
        match action.kind {
            ActionKind::KeyCombo(chord) => {
                assert_eq!(chord.keys, vec!["ctrl", "shift", "s"]);
            }
            other => panic!("unexpected variant: {other:?}"),
        }
    }

    #[test]
    fn preserves_roundtrip_shape_for_delay() {
        let raw = RawAction {
            action_type: "delay".to_string(),
            params: json!({ "duration_ms": 250 }),
            delay_after: 10,
            repeat_count: 2,
            description: "demo".to_string(),
            enabled: true,
            on_error: "retry:1".to_string(),
            color: Some("red".to_string()),
            bookmarked: true,
        };

        let typed = Action::from_raw(raw.clone()).expect("conversion should succeed");
        let roundtrip = typed.to_raw();
        assert_eq!(roundtrip.action_type, "delay");
        assert_eq!(roundtrip.delay_after, raw.delay_after);
        assert_eq!(roundtrip.repeat_count, raw.repeat_count);
        assert_eq!(roundtrip.description, raw.description);
    }
}
