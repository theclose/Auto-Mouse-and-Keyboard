use std::env;
use std::path::PathBuf;

use amk_app::{CliOptions, run_macro_path};
use anyhow::{Result, bail};
use tracing::info;
use tracing_subscriber::EnvFilter;

fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env())
        .with_target(false)
        .compact()
        .init();

    let (path, options) = parse_args()?;
    let result = run_macro_path(&path, &options)?;

    info!("executed macro {}", result.macro_name);
    println!("Macro: {}", result.macro_name);
    println!(
        "Report: total={} success={} failed={} skipped={} duration_ms={}",
        result.report.total,
        result.report.success,
        result.report.failed,
        result.report.skipped,
        result.report.duration_ms
    );
    if let Some(error) = &result.report.first_error {
        println!("First error: {}", error);
    }
    Ok(())
}

fn parse_args() -> Result<(PathBuf, CliOptions)> {
    let mut args = env::args().skip(1);
    let first = args
        .next()
        .ok_or_else(|| anyhow::anyhow!("usage: amk-app [run] <macro.json> [--stop-on-error]"))?;

    let path = if first == "run" {
        args.next()
    } else {
        Some(first)
    }
    .ok_or_else(|| anyhow::anyhow!("missing macro path"))?;

    let mut options = CliOptions::default();
    for arg in args {
        match arg.as_str() {
            "--stop-on-error" => options.stop_on_error = true,
            "--help" | "-h" => {
                bail!("usage: amk-app [run] <macro.json> [--stop-on-error]");
            }
            other => bail!("unknown argument: {other}"),
        }
    }

    Ok((PathBuf::from(path), options))
}
