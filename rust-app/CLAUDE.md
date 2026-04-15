# AutoMacro Rust — AI Context & Guidelines (CLAUDE.md)

## Workspace Architecture
AutoMacro is a 5-layer Rust Cargo Workspace (`c:\Auto Mouse and keyboard\rust-app`):
- `amk-schema`: Raw JSON serialization formats and `FileFormat` traits. NO logic.
- `amk-domain`: Validates raw schema → `TypedAction` and `ActionKind`. NO FFI.
- `amk-runtime`: Engine executor: state control, scaling, repeating, loop evaluation. NO OS calls.
- `amk-platform`: Pure Win32 FFI execution (`input`, `capture`, `stealth`, `vision`, `crypto`).
- `amk-cli` / `amk-gui`: Front-end applications that drive the runtime.

## Build Environment (CRITICAL)
- **Toolchain**: `stable-x86_64-pc-windows-gnu` (pinned in `rust-toolchain.toml`)
- **Linker**: MSYS2 UCRT GCC at `C:/Ruby40-x64/msys64/ucrt64/bin/gcc.exe`
- **NEVER use `-Clink-self-contained=yes`**: This flag causes **STATUS_STACK_OVERFLOW** crashes before `main()` due to a CRT initialization bug in Rust's self-contained MinGW CRT. The MSYS2 system CRT must be used.
- **Stack size**: Set to 16MB via `-Clink-arg=-Wl,--stack,16777216` in `.cargo/config.toml`
- **Library search path**: `build.rs` in `amk-gui` adds `C:/Ruby40-x64/msys64/ucrt64/lib`
- **Target directory**: `C:/AMK/rust-app-target` (external to workspace for faster builds)

## Core Rules for Code Generation
1. **Never use `std::thread::sleep` blindly**. Sleeps MUST use `SmartSleeper` from `amk-platform::sleeper`. The engine depends on 15ms polling of `AtomicBool` for instant cancel/stop.
2. **Handle Win32 with RAII memory safety**. Always wrap `HANDLE` acquisitions in `Drop` structs (`SafeScreenDC`, `SafeMemDC`, `SafeBitmap`). Check `is_null()` immediately after acquisition.
3. **No UI Bridging Threads**. Push `Arc<AtomicBool>` directly from UI → `Win32Executor`. Never spawn polling threads just to bridge a boolean.
4. **Check SendInput return values**. Never discard. Map `ret == 0` to `Result::Err` so the engine knows if UAC/Anti-cheat blocked the operation.
5. **egui v0.31 API**. Constructors changed (e.g. `Rounding` takes 4 properties). Check docs before using.
6. **Instant arithmetic**: Use `saturating_duration_since()` not `duration_since()` to avoid panics from clock races.
7. **Crypto memory**: Always zero-wipe sensitive buffers (`fill(0)`) before `LocalFree`.

## Build & Testing Commands
```bash
# GUI (debug, with console)
cargo run -p amk-gui

# CLI
cargo run -p amk-cli -- run macros/test.json

# All tests (43 tests across workspace)
cargo test --workspace

# CLI subcommands
cargo run -p amk-cli -- validate macros/test.json
cargo run -p amk-cli -- list --dir macros
cargo run -p amk-cli -- info macros/test.json
```

## Known Limitations
- `rfd_open_macro()` in toolbar.rs returns `None` (file dialog not implemented)
- `hotkey.rs` `RegisterHotKey` thread has no cleanup/`UnregisterHotKey` call
- `capture_text` (OCR) returns unsupported error — no OCR backend integrated
- `build.rs` hardcodes MSYS2 path — breaks if MSYS2 is relocated
