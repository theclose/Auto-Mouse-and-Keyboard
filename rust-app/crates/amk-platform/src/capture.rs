//! Screen capture and pixel reading via Win32 GDI.

use std::ptr;
use windows_sys::Win32::Graphics::Gdi::*;

// ── RAII Wrappers for GDI resources ──────────────────────────────────────

struct SafeScreenDC(HDC);
impl Drop for SafeScreenDC {
    fn drop(&mut self) {
        if !self.0.is_null() {
            unsafe { ReleaseDC(ptr::null_mut(), self.0); }
        }
    }
}

struct SafeMemDC(HDC);
impl Drop for SafeMemDC {
    fn drop(&mut self) {
        if !self.0.is_null() {
            unsafe { DeleteDC(self.0); }
        }
    }
}

struct SafeBitmap(HBITMAP);
impl Drop for SafeBitmap {
    fn drop(&mut self) {
        if !self.0.is_null() {
            unsafe { DeleteObject(self.0); }
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────

/// Read pixel color at screen coordinate (x, y).
/// Returns `Ok((r, g, b))` or `Err` if GDI fails.
pub fn get_pixel_color(x: i32, y: i32) -> Result<(u8, u8, u8), String> {
    unsafe {
        let raw_hdc = GetDC(ptr::null_mut());
        if raw_hdc.is_null() {
            return Err("GetDC returned NULL".into());
        }
        let _hdc = SafeScreenDC(raw_hdc);

        let color = GetPixel(raw_hdc, x, y);
        if color == CLR_INVALID {
            return Err("GetPixel returned CLR_INVALID".into());
        }

        let r = (color & 0xFF) as u8;
        let g = ((color >> 8) & 0xFF) as u8;
        let b = ((color >> 16) & 0xFF) as u8;
        Ok((r, g, b))
    }
}

/// Check if pixel at (x, y) matches expected hex color within tolerance.
/// `hex_color` format: "#RRGGBB" or "RRGGBB"
pub fn check_pixel_match(x: i32, y: i32, hex_color: &str, tolerance: u32) -> Result<bool, String> {
    let expected = parse_hex_color(hex_color).ok_or("Invalid hex color format")?;
    let (er, eg, eb) = expected;

    let (ar, ag, ab) = get_pixel_color(x, y)?;
    let diff = (ar as i32 - er as i32).unsigned_abs()
        + (ag as i32 - eg as i32).unsigned_abs()
        + (ab as i32 - eb as i32).unsigned_abs();

    Ok(diff <= tolerance)
}

/// Parse a hex color string into (r, g, b).
fn parse_hex_color(s: &str) -> Option<(u8, u8, u8)> {
    let s = s.strip_prefix('#').unwrap_or(s);
    if s.len() != 6 {
        return None;
    }
    let r = u8::from_str_radix(&s[0..2], 16).ok()?;
    let g = u8::from_str_radix(&s[2..4], 16).ok()?;
    let b = u8::from_str_radix(&s[4..6], 16).ok()?;
    Some((r, g, b))
}

/// Capture a region of the screen to raw BGRA pixel data.
/// Returns (data, width, height) or Error string on failure.
pub fn capture_region(x: i32, y: i32, w: i32, h: i32) -> Result<(Vec<u8>, i32, i32), String> {
    if w <= 0 || h <= 0 {
        return Err("Invalid dimensions for capture".into());
    }

    unsafe {
        let raw_screen_dc = GetDC(ptr::null_mut());
        if raw_screen_dc.is_null() {
            return Err("GetDC failed".into());
        }
        let _screen_dc = SafeScreenDC(raw_screen_dc);

        let raw_mem_dc = CreateCompatibleDC(raw_screen_dc);
        if raw_mem_dc.is_null() {
            return Err("CreateCompatibleDC failed".into());
        }
        let _mem_dc = SafeMemDC(raw_mem_dc);

        let raw_hbmp = CreateCompatibleBitmap(raw_screen_dc, w, h);
        if raw_hbmp.is_null() {
            return Err("CreateCompatibleBitmap failed".into());
        }
        let _hbmp = SafeBitmap(raw_hbmp);

        let old_obj = SelectObject(raw_mem_dc, raw_hbmp);
        if old_obj.is_null() {
            return Err("SelectObject failed".into());
        }

        let blt_res = BitBlt(raw_mem_dc, 0, 0, w, h, raw_screen_dc, x, y, SRCCOPY);
        if blt_res == 0 {
            SelectObject(raw_mem_dc, old_obj); // restore
            return Err("BitBlt failed".into());
        }

        // Properly initialize BITMAPINFOHEADER without mem::zeroed() for safety
        let bmi_header = BITMAPINFOHEADER {
            biSize: std::mem::size_of::<BITMAPINFOHEADER>() as u32,
            biWidth: w,
            biHeight: -h, // top-down
            biPlanes: 1,
            biBitCount: 32,
            biCompression: BI_RGB,
            biSizeImage: 0,
            biXPelsPerMeter: 0,
            biYPelsPerMeter: 0,
            biClrUsed: 0,
            biClrImportant: 0,
        };

        let mut bmi = BITMAPINFO {
            bmiHeader: bmi_header,
            bmiColors: [RGBQUAD { rgbBlue: 0, rgbGreen: 0, rgbRed: 0, rgbReserved: 0 }],
        };

        let buf_size = (w * h * 4) as usize;
        let mut buf = vec![0u8; buf_size];
        
        let lines = GetDIBits(raw_mem_dc, raw_hbmp, 0, h as u32, buf.as_mut_ptr().cast(), &mut bmi, DIB_RGB_COLORS);
        
        SelectObject(raw_mem_dc, old_obj); // cleanup before dropping

        if lines == 0 {
            return Err("GetDIBits failed".into());
        }

        Ok((buf, w, h))
    }
}

/// Save captured BGRA buffer as a BMP file.
pub fn save_bmp(path: &str, data: &[u8], width: i32, height: i32) -> std::io::Result<()> {
    use std::io::Write;

    let row_size = ((width * 3 + 3) / 4) * 4;
    let pixel_size = (row_size * height) as usize;
    let file_size = 54 + pixel_size;

    let mut f = std::fs::File::create(path)?;

    // BMP header
    f.write_all(&[0x42, 0x4D])?;
    f.write_all(&(file_size as u32).to_le_bytes())?;
    f.write_all(&[0, 0, 0, 0])?;
    f.write_all(&54u32.to_le_bytes())?;

    // DIB header
    f.write_all(&40u32.to_le_bytes())?;
    f.write_all(&width.to_le_bytes())?;
    f.write_all(&height.to_le_bytes())?;
    f.write_all(&1u16.to_le_bytes())?;
    f.write_all(&24u16.to_le_bytes())?;
    f.write_all(&0u32.to_le_bytes())?;
    f.write_all(&(pixel_size as u32).to_le_bytes())?;
    f.write_all(&2835u32.to_le_bytes())?;
    f.write_all(&2835u32.to_le_bytes())?;
    f.write_all(&0u32.to_le_bytes())?;
    f.write_all(&0u32.to_le_bytes())?;

    // Pixel data: BGRA → BGR, flip vertical
    let stride = width as usize * 4;
    for row in (0..height as usize).rev() {
        let row_start = row * stride;
        let mut row_buf = vec![0u8; row_size as usize];
        for col in 0..width as usize {
            let src = row_start + col * 4;
            let dst = col * 3;
            row_buf[dst] = data[src];
            row_buf[dst + 1] = data[src + 1];
            row_buf[dst + 2] = data[src + 2];
        }
        f.write_all(&row_buf)?;
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_hex_colors() {
        assert_eq!(parse_hex_color("#FF0000"), Some((255, 0, 0)));
        assert_eq!(parse_hex_color("00FF00"), Some((0, 255, 0)));
        assert_eq!(parse_hex_color("#0000FF"), Some((0, 0, 255)));
        assert_eq!(parse_hex_color("invalid"), None);
        assert_eq!(parse_hex_color("#FFF"), None);
    }
}
