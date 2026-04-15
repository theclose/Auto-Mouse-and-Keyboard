//! AutoMacro CLI — load and run macro files from the command line.
//!
//! Usage:
//!   automacro run path/to/macro.json [--loops N] [--speed F] [--delay MS]
//!   automacro info path/to/macro.json
//!   automacro list [--dir path/to/macros]
//!   automacro validate path/to/macro.json

use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Instant;

use anyhow::{Context, Result, bail};
use clap::{Parser, Subcommand};
use tracing::{info, warn};

use amk_domain::convert_actions;
use amk_schema::{parse_macro, MacroDocument};
use amk_runtime::engine::MacroEngine;
use amk_runtime::report::ExitReason;
use amk_platform::Win32Executor;

// ── CLI Args ─────────────────────────────────────────────────────────────

#[derive(Parser)]
#[command(
    name = "automacro",
    version,
    about = "AutoMacro — High-performance macro automation for Windows",
    long_about = "Load and execute AutoMacro JSON files with full Win32 \
                  integration: mouse, keyboard, pixel detection, stealth mode."
)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Run a macro file
    Run {
        /// Path to the macro JSON file
        file: PathBuf,

        /// Number of loops (0 = infinite)
        #[arg(short, long, default_value = "1")]
        loops: u32,

        /// Speed factor (1.0 = normal, 0.5 = 2x faster, 2.0 = 2x slower)
        #[arg(short, long, default_value = "1.0")]
        speed: f64,

        /// Delay between loops (ms)
        #[arg(short, long, default_value = "0")]
        delay: u32,

        /// Dry run — parse and convert only, don't execute
        #[arg(long)]
        dry_run: bool,
    },

    /// Show macro information
    Info {
        /// Path to the macro JSON file
        file: PathBuf,
    },

    /// List all macros in a directory
    List {
        /// Directory containing macro JSON files
        #[arg(short, long, default_value = "macros")]
        dir: PathBuf,
    },

    /// Validate a macro file (parse + convert)
    Validate {
        /// Path to the macro JSON file
        file: PathBuf,
    },
}

// ── Main ─────────────────────────────────────────────────────────────────

fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "info".into()),
        )
        .with_target(false)
        .init();

    let cli = Cli::parse();

    match cli.command {
        Commands::Run { file, loops, speed, delay, dry_run } => {
            cmd_run(&file, loops, speed, delay, dry_run)
        }
        Commands::Info { file } => cmd_info(&file),
        Commands::List { dir } => cmd_list(&dir),
        Commands::Validate { file } => cmd_validate(&file),
    }
}

// ── Commands ─────────────────────────────────────────────────────────────

fn cmd_run(file: &PathBuf, loops: u32, speed: f64, delay: u32, dry_run: bool) -> Result<()> {
    let doc = load_macro(file)?;
    let typed = convert_actions(&doc.actions)
        .context("failed to convert actions to typed format")?;

    info!(
        "Loaded: {} ({} actions, {} typed)",
        doc.name,
        doc.actions.len(),
        typed.len()
    );

    if dry_run {
        info!("Dry run — all {} actions parsed and converted successfully.", typed.len());
        return Ok(());
    }

    info!(
        "Starting execution: {} loops, speed={speed}x, delay={delay}ms",
        if loops == 0 { "∞".to_string() } else { loops.to_string() }
    );
    info!("Press Ctrl+C to stop.");

    // Setup Ctrl+C → executor stop bridge
    let stop_flag = Arc::new(AtomicBool::new(false));
    let mut executor = Win32Executor::with_flag(Arc::clone(&stop_flag));

    // Proper Ctrl+C handler via ctrlc crate
    {
        let flag = Arc::clone(&stop_flag);
        ctrlc::set_handler(move || {
            flag.store(true, Ordering::Release);
            eprintln!("\n⏹  Ctrl+C — stopping macro...");
        }).expect("failed to set Ctrl+C handler");
    }

    // Spawn Global hotkey listener for F6 (0x75)
    let _hotkey = amk_platform::hotkey::spawn_stop_hotkey_thread(Arc::clone(&stop_flag), 0x75, 0);

    // Create engine
    let mut engine = MacroEngine::new();
    engine.set_speed(speed);

    // Run
    let start = Instant::now();
    let report = engine.run(&typed, loops, delay, &mut executor);
    let elapsed = start.elapsed();

    // Print report
    println!();
    println!("╔══════════════════════════════════════╗");
    println!("║        AutoMacro — Run Report        ║");
    println!("╠══════════════════════════════════════╣");
    println!("║  Macro:     {:25}║", truncate(&doc.name, 25));
    println!("║  Duration:  {:>22.2?}  ║", elapsed);
    println!("║  Loops:     {:>25}║", report.loops_completed);
    println!("║  Executed:  {:>25}║", report.actions_executed);
    println!("║  Succeeded: {:>25}║", report.actions_succeeded);
    println!("║  Failed:    {:>25}║", report.actions_failed);
    println!("║  Skipped:   {:>25}║", report.actions_skipped);
    println!("║  Exit:      {:>25}║", match report.exit_reason {
        ExitReason::Completed => "Completed ✓",
        ExitReason::UserStopped => "Stopped by user ■",
        ExitReason::ErrorStopped => "Stopped on error ✗",
    });
    println!("╚══════════════════════════════════════╝");

    if report.exit_reason == ExitReason::ErrorStopped {
        bail!("Macro stopped due to error");
    }

    Ok(())
}

fn cmd_info(file: &PathBuf) -> Result<()> {
    let doc = load_macro(file)?;
    let typed = convert_actions(&doc.actions);
    let convert_ok = typed.is_ok();
    let action_count = doc.actions.len();
    let deep: usize = doc.actions.iter().map(|a| a.deep_count()).sum();

    println!("╔══════════════════════════════════════╗");
    println!("║        AutoMacro — Macro Info        ║");
    println!("╠══════════════════════════════════════╣");
    println!("║  Name:      {:25}║", truncate(&doc.name, 25));
    println!("║  File:      {:25}║", truncate(&file.file_name().unwrap_or_default().to_string_lossy(), 25));
    println!("║  Actions:   {:>25}║", action_count);
    println!("║  Deep:      {:>25}║", deep);
    println!("║  Loops:     {:>25}║", doc.settings.loop_count);
    println!("║  Valid:     {:>25}║", if convert_ok { "✓ Yes" } else { "✗ No" });
    println!("╚══════════════════════════════════════╝");

    if let Err(e) = typed {
        warn!("Conversion error: {e}");
    }

    Ok(())
}

fn cmd_list(dir: &PathBuf) -> Result<()> {
    if !dir.is_dir() {
        bail!("Not a directory: {}", dir.display());
    }

    let mut entries: Vec<_> = std::fs::read_dir(dir)?
        .filter_map(Result::ok)
        .filter(|e| {
            e.path().extension().is_some_and(|ext| ext == "json")
                && e.file_name().to_string_lossy() != ".triggers.json"
        })
        .collect();

    entries.sort_by_key(|e| e.file_name());

    println!("╔════╦═══════════════════════════╦════════╦═══════╗");
    println!("║  # ║ Name                      ║ Actions║ Valid ║");
    println!("╠════╬═══════════════════════════╬════════╬═══════╣");

    for (i, entry) in entries.iter().enumerate() {
        let path = entry.path();
        match load_macro(&path) {
            Ok(doc) => {
                let valid = convert_actions(&doc.actions).is_ok();
                println!(
                    "║{:>3} ║ {:25} ║{:>7} ║  {}  ║",
                    i + 1,
                    truncate(&doc.name, 25),
                    doc.actions.len(),
                    if valid { "✓" } else { "✗" }
                );
            }
            Err(_) => {
                println!(
                    "║{:>3} ║ {:25} ║    ERR ║  ✗  ║",
                    i + 1,
                    truncate(&entry.file_name().to_string_lossy(), 25),
                );
            }
        }
    }
    println!("╚════╩═══════════════════════════╩════════╩═══════╝");
    println!("  Found {} macro files in {}", entries.len(), dir.display());

    Ok(())
}

fn cmd_validate(file: &PathBuf) -> Result<()> {
    info!("Validating: {}", file.display());

    let content = std::fs::read_to_string(file)
        .context("failed to read file")?;

    let doc = parse_macro(&content)
        .context("failed to parse macro JSON")?;
    info!("  Parse: ✓ ({} actions)", doc.actions.len());

    let typed = convert_actions(&doc.actions)
        .context("failed to convert actions")?;
    info!("  Convert: ✓ ({} typed actions)", typed.len());

    // Count action types
    let mut type_counts = std::collections::HashMap::new();
    count_types(&typed, &mut type_counts);

    info!("  Action types:");
    let mut types: Vec<_> = type_counts.iter().collect();
    types.sort_by_key(|(_, c)| std::cmp::Reverse(*c));
    for (t, c) in &types {
        info!("    {t}: {c}");
    }

    info!("Validation passed ✓");
    Ok(())
}

// ── Helpers ──────────────────────────────────────────────────────────────

fn load_macro(file: &PathBuf) -> Result<MacroDocument> {
    let content = std::fs::read_to_string(file)
        .with_context(|| format!("cannot read: {}", file.display()))?;
    parse_macro(&content)
        .with_context(|| format!("invalid JSON: {}", file.display()))
}

fn truncate(s: &str, max: usize) -> String {
    if s.len() <= max {
        format!("{s:max$}")
    } else {
        format!("{}…", &s[..max - 1])
    }
}

fn count_types(actions: &[amk_domain::action::TypedAction], map: &mut std::collections::HashMap<String, usize>) {
    for action in actions {
        let name = action_type_name(&action.kind);
        *map.entry(name).or_insert(0) += 1;

        match &action.kind {
            amk_domain::action::ActionKind::Group { children, .. }
            | amk_domain::action::ActionKind::LoopBlock { children, .. } => {
                count_types(children, map);
            }
            amk_domain::action::ActionKind::IfVariable { then_actions, else_actions, .. }
            | amk_domain::action::ActionKind::IfPixelColor { then_actions, else_actions, .. }
            | amk_domain::action::ActionKind::IfImageFound { then_actions, else_actions, .. } => {
                count_types(then_actions, map);
                count_types(else_actions, map);
            }
            _ => {}
        }
    }
}

fn action_type_name(kind: &amk_domain::action::ActionKind) -> String {
    let dbg = format!("{kind:?}");
    dbg.split_once('{')
        .or_else(|| dbg.split_once(' '))
        .map_or_else(|| dbg.clone(), |(name, _)| name.trim().to_owned())
}
