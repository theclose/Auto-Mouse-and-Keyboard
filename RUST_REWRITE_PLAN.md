# Auto Macro 100% Rust Rewrite

Mục tiêu của tài liệu này là khóa scope rewrite toàn bộ ứng dụng sang Rust, không giữ Python trong sản phẩm cuối.

## Mục tiêu bắt buộc

- Thay thế toàn bộ `main.py`, `core/`, `gui/`, `modules/` bằng binary Rust.
- Giữ tương thích file dữ liệu hiện có:
  - `config.json`
  - `macros/*.json`
  - `macros/.triggers.json`
- Giữ đầy đủ feature hiện có:
  - 34 action types
  - macro engine
  - recorder mouse/keyboard
  - image recognition
  - pixel checks
  - hotkeys toàn cục
  - trigger scheduler/window focus
  - settings/config
  - autosave/undo-redo
  - tray/logging/crash handling
  - help/templates

## Workspace Rust

Workspace mới nằm tại [rust/Cargo.toml](/C:/Auto%20Mouse%20and%20keyboard/rust/Cargo.toml).

Crates hiện tại:

- `amk-schema`
  - Raw JSON schema tương thích file cũ.
  - Parse macro/config/trigger.
  - Chuẩn hóa type aliases legacy.
- `amk-domain`
  - Typed action model cho toàn bộ 34 action types.
  - `ExecutionContext` và snapshot/interpolation cơ sở.
- `amk-runtime`
  - Runtime contract, event bus, playback report, executor interface.
- `amk-platform-win`
  - Lớp Win32-native. Hiện đã bắt đầu bằng hotkey parsing.
- `amk-app`
  - Entry binary cho app Rust mới.

## Mapping Python -> Rust

### Entry / Shell

- `main.py` -> `amk-app`
- logging startup -> `tracing` + rolling file logger
- crash handler -> `amk-app` + Windows crash/report module

### Schema / Domain

- `core/action.py` -> `amk-schema` + `amk-domain::action`
- `core/execution_context.py` -> `amk-domain::context`
- `core/engine_context.py` -> `amk-runtime` runtime state

### Runtime

- `core/engine.py` -> `amk-runtime`
- `core/scheduler.py` -> `amk-runtime` composite executor
- `core/smart_hints.py` -> `amk-domain` validator/analyzer
- `core/autosave.py` -> `amk-runtime` background save service
- `core/trigger_manager.py` + `core/triggers.py` -> `amk-runtime`

### Windows Platform

- `core/hotkey_manager.py` -> `amk-platform-win::hotkeys`
- `core/recorder.py` -> `amk-platform-win::hooks`
- `core/secure.py` -> `amk-platform-win::dpapi`
- `modules/keyboard.py` -> `amk-platform-win::input`
- `modules/mouse.py` -> `amk-platform-win::input`
- `modules/pixel.py` -> `amk-platform-win::screen`
- `modules/system.py` window/clipboard/process parts -> `amk-platform-win`

### Vision

- `modules/screen.py` -> `amk-platform-win::capture` hoặc crate vision riêng
- `modules/image.py` -> crate vision riêng hoặc `amk-platform-win::vision`
- OCR -> module riêng trong platform layer

### UI

- `gui/main_window.py`
- `gui/action_editor.py`
- `gui/action_tree_model.py`
- `gui/settings_dialog.py`
- `gui/trigger_dialog.py`
- `gui/tray.py`
- `gui/panels/*`

Toàn bộ phần trên sẽ được thay bằng Rust UI. Không tái dùng PyQt.

## Quy tắc rewrite

- Không port line-by-line. Port theo behavior và contract.
- Không giữ registry bằng import side-effect.
- Mọi action phải có:
  - typed params
  - roundtrip schema test
  - runtime executor test
  - UI editor mapping
- Không coi docs Python là nguồn chân lý khi conflict với code/test.
- Test parity phải dựa trên macro fixtures thật trong `macros/`.

## Phase triển khai

### Phase 0: Lock baseline

- Đóng băng behavior hiện tại bằng fixtures.
- Thu thập macro/config/trigger mẫu.
- Ghi nhận các sai lệch giữa docs và code thật.

### Phase 1: Schema + Typed Model

- Hoàn thiện `amk-schema`.
- Hoàn thiện `amk-domain::ActionKind` cho toàn bộ action set.
- Bổ sung migration/alias/legacy parsing.

Exit condition:

- Load được toàn bộ macro JSON hiện có bằng Rust.
- Roundtrip JSON không mất dữ liệu cần thiết.

### Phase 2: Runtime Core

- Port `MacroEngine`.
- Port `ExecutionContext`.
- Port composite execution:
  - `loop_block`
  - `if_image_found`
  - `if_pixel_color`
  - `if_variable`
  - `group`
- Port on-error policy, looping, stop/pause/resume/step, checkpoint.

Exit condition:

- Headless runtime Rust chạy được macro JSON với mock executors.

### Phase 3: Win32 Platform

- Global hotkeys bằng `RegisterHotKey`.
- SendInput cho keyboard/mouse.
- Clipboard/window activation.
- Pixel read / screen capture.
- DPAPI encryption.
- Recorder hooks low-level.

Exit condition:

- Runtime có thể thao tác desktop thật trên Windows bằng Rust.

### Phase 4: Vision + OCR

- Capture backend hiệu năng cao.
- Template cache / ROI cache / grayscale path.
- OpenCV template matching.
- OCR integration.

Exit condition:

- Action image/pixel/OCR đạt parity chức năng với Python.

### Phase 5: Rust UI

- Main window
- Action tree editor
- Per-action editor form cho 34 action types
- Playback/recording/settings/triggers/help/panels
- System tray

Exit condition:

- Người dùng có thể dùng app Rust mà không cần Python UI.

### Phase 6: Product Cutover

- Build/package Windows executable từ Rust.
- Di chuyển assets/runtime folders.
- Chuyển README/build docs sang Rust.
- Xóa Python khỏi đường chạy sản phẩm.

Exit condition:

- Artifact phát hành không cần Python, PyQt, PyInstaller.

## Thứ tự action port

1. `delay`
2. `set_variable`
3. `split_string`
4. `comment`
5. `group`
6. `run_command`
7. `log_to_file`
8. `read_file_line`
9. `write_to_file`
10. `read_clipboard`
11. `activate_window`
12. `key_press`
13. `key_combo`
14. `type_text`
15. `hotkey`
16. `mouse_click`
17. `mouse_double_click`
18. `mouse_right_click`
19. `mouse_move`
20. `mouse_drag`
21. `mouse_scroll`
22. `check_pixel_color`
23. `wait_for_color`
24. `wait_for_image`
25. `click_on_image`
26. `image_exists`
27. `take_screenshot`
28. `secure_type_text`
29. `run_macro`
30. `capture_text`
31. `if_variable`
32. `if_pixel_color`
33. `if_image_found`
34. `loop_block`

## Nguyên tắc cutover

- Python chỉ là baseline tham chiếu trong giai đoạn rewrite.
- Sản phẩm cuối không phụ thuộc Python.
- Chỉ khi Rust UI + runtime + platform đã hoàn tất mới xóa hẳn code Python khỏi repo hoặc archive.
