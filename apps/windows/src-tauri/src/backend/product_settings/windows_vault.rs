//! Immutable per-save bundles in the current user's Windows Credential Manager.
use super::{storage::Vault, CompanionProductSecrets, CredentialBlocks};
use std::{ffi::c_void, ptr};
use uuid::Uuid;

#[repr(C)]
struct FileTime {
    low: u32,
    high: u32,
}
#[repr(C)]
struct CredentialW {
    flags: u32,
    credential_type: u32,
    target_name: *mut u16,
    comment: *mut u16,
    last_written: FileTime,
    credential_blob_size: u32,
    credential_blob: *mut u8,
    persist: u32,
    attribute_count: u32,
    attributes: *mut c_void,
    target_alias: *mut u16,
    user_name: *mut u16,
}
#[link(name = "Advapi32")]
extern "system" {
    fn CredWriteW(credential: *const CredentialW, flags: u32) -> i32;
    fn CredReadW(
        target: *const u16,
        kind: u32,
        flags: u32,
        credential: *mut *mut CredentialW,
    ) -> i32;
    fn CredDeleteW(target: *const u16, kind: u32, flags: u32) -> i32;
    fn CredFree(buffer: *mut c_void);
}

pub(super) struct WindowsVault {
    pub base: String,
}
impl WindowsVault {
    fn target(&self, generation: Option<Uuid>) -> Result<Vec<u16>, String> {
        if self.base.is_empty() || self.base.contains('\0') || self.base.len() > 400 {
            return Err("安全凭据目标名称无效，未保存。".into());
        }
        let name = generation.map_or_else(
            || self.base.clone(),
            |id| format!("{}.snapshot.{id}", self.base),
        );
        Ok(name.encode_utf16().chain(Some(0)).collect())
    }
    pub fn write_legacy(&self, secrets: &CompanionProductSecrets) -> Result<(), String> {
        self.write_target(None, secrets)
    }
    pub fn delete_legacy(&self) -> Result<(), String> {
        self.delete_target(None)
    }
    fn write_target(
        &self,
        generation: Option<Uuid>,
        secrets: &CompanionProductSecrets,
    ) -> Result<(), String> {
        let json = serde_json::to_string(secrets).map_err(|_| "无法编码安全凭据，未保存。")?;
        let mut blob: Vec<u8> = json.encode_utf16().flat_map(u16::to_le_bytes).collect();
        if blob.len() > 2560 {
            return Err("安全凭据内容过长，原配置未覆盖。".into());
        }
        let mut target = self.target(generation)?;
        let record = CredentialW {
            flags: 0,
            credential_type: 1,
            target_name: target.as_mut_ptr(),
            comment: ptr::null_mut(),
            last_written: FileTime { low: 0, high: 0 },
            credential_blob_size: blob.len() as u32,
            credential_blob: blob.as_mut_ptr(),
            persist: 2,
            attribute_count: 0,
            attributes: ptr::null_mut(),
            target_alias: ptr::null_mut(),
            user_name: ptr::null_mut(),
        };
        if unsafe { CredWriteW(&record, 0) } == 0 {
            return Err("系统安全凭据保存失败，原配置未覆盖。".into());
        }
        Ok(())
    }
    fn delete_target(&self, generation: Option<Uuid>) -> Result<(), String> {
        let target = self.target(generation)?;
        if unsafe { CredDeleteW(target.as_ptr(), 1, 0) } == 0
            && std::io::Error::last_os_error().raw_os_error() != Some(1168)
        {
            return Err("无法清理未提交的设置凭据，请稍后重试。".into());
        }
        Ok(())
    }
}
impl Vault for WindowsVault {
    fn read(&self, generation: Option<Uuid>) -> Result<Option<CompanionProductSecrets>, String> {
        let target = self.target(generation)?;
        let mut raw: *mut CredentialW = ptr::null_mut();
        if unsafe { CredReadW(target.as_ptr(), 1, 0, &mut raw) } == 0 {
            if std::io::Error::last_os_error().raw_os_error() == Some(1168) {
                return Ok(None);
            }
            return Err("系统安全凭据读取失败，原配置已保留。".into());
        }
        if raw.is_null() {
            return Err("系统安全凭据响应无效，原配置已保留。".into());
        }
        let bytes = unsafe {
            let record = &*raw;
            if record.credential_blob.is_null()
                || record.credential_blob_size == 0
                || record.credential_blob_size > 2560
                || record.credential_blob_size % 2 != 0
            {
                CredFree(raw.cast());
                return Err("安全凭据内容损坏，原配置已保留。".into());
            }
            let bytes = std::slice::from_raw_parts(
                record.credential_blob,
                record.credential_blob_size as usize,
            )
            .to_vec();
            CredFree(raw.cast());
            bytes
        };
        let words: Vec<u16> = bytes
            .chunks_exact(2)
            .map(|p| u16::from_le_bytes([p[0], p[1]]))
            .collect();
        let json = String::from_utf16(&words).map_err(|_| "安全凭据内容损坏，原配置已保留。")?;
        let secrets =
            serde_json::from_str(&json).map_err(|_| "安全凭据内容损坏，原配置已保留。")?;
        Ok(Some(secrets))
    }
    fn write(&self, generation: Uuid, secrets: &CompanionProductSecrets) -> Result<(), String> {
        // Fresh UUID targets must not replace an existing snapshot.
        if self.read(Some(generation))?.is_some() {
            return Err("设置凭据身份重复，未保存。".into());
        }
        self.write_target(Some(generation), secrets)
    }
    fn delete(&self, generation: Uuid) -> Result<(), String> {
        self.delete_target(Some(generation))
    }
    fn clear_legacy(&self, blocks: &CredentialBlocks) -> Result<(), String> {
        if let Some(mut secrets) = self.read(None)? {
            if blocks.volc_app_key { secrets.volc_app_key.clear(); }
            if blocks.volc_access_key { secrets.volc_access_key.clear(); }
            if blocks.openai_asr_api_key { secrets.openai_asr_api_key.clear(); }
            if blocks.deepseek_api_key { secrets.deepseek_api_key.clear(); }
            if secrets.is_empty() { self.delete_target(None) } else { self.write_target(None, &secrets) }
        } else { Ok(()) }
    }
}
