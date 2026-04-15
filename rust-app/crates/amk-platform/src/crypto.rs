//! Cryptography bindings using Windows DPAPI (Data Protection API).
//! Used for securely storing and typing passwords in macros.

use std::ptr;
use windows_sys::Win32::Security::Cryptography::*;
use windows_sys::Win32::Foundation::*;

/// Decrypts a Base64 encoded string using Windows DPAPI `CryptUnprotectData`.
/// This can only decrypt data encrypted by the same user account on the same machine.
pub fn decrypt_string(encrypted_base64: &str) -> Result<String, String> {
    use base64::{engine::general_purpose, Engine as _};

    let encrypted_bytes = general_purpose::STANDARD.decode(encrypted_base64)
        .map_err(|e| format!("Base64 decode error: {e}"))?;

    let data_in = CRYPT_INTEGER_BLOB {
        cbData: encrypted_bytes.len() as u32,
        pbData: encrypted_bytes.as_ptr() as *mut u8,
    };

    let mut data_out = CRYPT_INTEGER_BLOB { cbData: 0, pbData: ptr::null_mut() };

    unsafe {
        let success = CryptUnprotectData(
            &data_in,
            ptr::null_mut(),
            ptr::null_mut(),
            ptr::null_mut(),
            ptr::null_mut(),
            0,
            &mut data_out,
        );

        if success == 0 {
            return Err("CryptUnprotectData failed. Data might be corrupted or from a different user/machine.".into());
        }

        let slice = std::slice::from_raw_parts(data_out.pbData, data_out.cbData as usize);
        let cleartext = String::from_utf8(slice.to_vec())
            .map_err(|_| "Decrypted data is not valid UTF-8".to_string());

        // Zero out sensitive data before freeing
        let wipe_slice = std::slice::from_raw_parts_mut(data_out.pbData, data_out.cbData as usize);
        wipe_slice.fill(0);

        LocalFree(data_out.pbData as *mut std::ffi::c_void);
        
        cleartext
    }
}
