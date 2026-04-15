//! Computer Vision utilities for template matching.

use crate::capture;

/// Result of an image search.
pub struct MatchResult {
    pub x: i32,
    pub y: i32,
    pub width: i32,
    pub height: i32,
    pub confidence: f64,
}

/// Search for a template image inside the screen or a region.
pub fn find_image(template_path: &str, region: Option<[i32; 4]>) -> Result<MatchResult, String> {
    // 1. Load the template image using base `image` crate
    let template_img = image::open(template_path)
        .map_err(|e| format!("Failed to load template image at {template_path}: {e}"))?;
    let template_gray = template_img.into_luma8();
    let (tw, th) = template_gray.dimensions();
    let tw = tw as i32;
    let th = th as i32;

    // 2. Determine capture region
    let (cx, cy, cw, ch) = match region {
        Some([rx, ry, rwidth, rheight]) => (rx, ry, rwidth, rheight),
        None => {
            let (sw, sh) = crate::input::screen_size();
            (0, 0, sw, sh)
        }
    };

    if cw < tw || ch < th {
        return Err("Capture region is smaller than the template image".into());
    }

    // 3. Capture the screen via GDI
    let (bgra_buf, cap_w, cap_h) = capture::capture_region(cx, cy, cw, ch)?;

    // 4. Manual SAD (Sum of Absolute Differences) Template Matching to prevent stack bloating
    // Caching template pixels onto heap to avoid repeated lookups
    let mut template_pixels = vec![0u8; (tw * th) as usize];
    for y in 0..th {
        for x in 0..tw {
            template_pixels[(y * tw + x) as usize] = template_gray[(x as u32, y as u32)].0[0];
        }
    }

    let stride = cap_w as usize * 4;
    let mut min_diff = u64::MAX;
    let mut best_x = 0;
    let mut best_y = 0;

    let max_search_x = cap_w - tw;
    let max_search_y = cap_h - th;

    // Fast SAD sweeping
    for y_idx in 0..=max_search_y {
        for x_idx in 0..=max_search_x {
            let mut diff: u64 = 0;
            
            for ty in 0..th {
                let screen_y = y_idx + ty;
                for tx in 0..tw {
                    let screen_x = x_idx + tx;
                    
                    let idx = (screen_y as usize * stride) + (screen_x as usize * 4);
                    let b = bgra_buf[idx] as u32;
                    let g = bgra_buf[idx + 1] as u32;
                    let r = bgra_buf[idx + 2] as u32;
                    
                    let luma = (r * 299 + g * 587 + b * 114) / 1000;
                    let t_luma = template_pixels[(ty * tw + tx) as usize] as u32;
                    
                    diff += luma.abs_diff(t_luma) as u64;
                    if diff >= min_diff {
                        break;
                    }
                }
                if diff >= min_diff {
                    break;
                }
            }
            
            if diff < min_diff {
                min_diff = diff;
                best_x = x_idx;
                best_y = y_idx;
                
                if min_diff == 0 {
                    break;
                }
            }
        }
        if min_diff == 0 {
            break;
        }
    }

    // Max theoretical difference: 255 per pixel.
    let max_possible_diff = (tw * th * 255) as f64;
    let confidence = 1.0 - (min_diff as f64 / max_possible_diff);

    Ok(MatchResult {
        x: cx + best_x,
        y: cy + best_y,
        width: tw,
        height: th,
        confidence,
    })
}
