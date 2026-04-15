// build.rs — Add MSYS2 lib path for shlwapi and other system libs needed by egui
fn main() {
    // Try environment variable first, then known paths
    let msys2_lib = std::env::var("MSYS2_LIB_PATH")
        .ok()
        .or_else(|| {
            let candidates = [
                "C:/Ruby40-x64/msys64/ucrt64/lib",
                "C:/msys64/ucrt64/lib",
                "C:/tools/msys64/ucrt64/lib",
            ];
            candidates.iter()
                .find(|p| std::path::Path::new(p).is_dir())
                .map(|s| s.to_string())
        });

    if let Some(lib_path) = msys2_lib {
        println!("cargo:rustc-link-search=native={lib_path}");
    } else {
        println!("cargo:warning=MSYS2 ucrt64/lib not found. Set MSYS2_LIB_PATH env var if linking fails.");
    }
}
