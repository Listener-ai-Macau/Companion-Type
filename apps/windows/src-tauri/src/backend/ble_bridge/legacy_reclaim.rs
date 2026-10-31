//! Exact replay of a legacy device receipt lost after the host saved audio.
//! Segmented recordings have their own receiver and do not use these intents.
use super::CompanionSyncedRecording;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{fs::{self, File, OpenOptions}, io::Read, path::{Path, PathBuf}};

const PREFIX: &str = ".legacy-reclaim-";

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub(super) struct Intent {
    schema: u8,
    device: String,
    recording_id: u32,
    total_length: u32,
    duration_ms: u32,
    capture_incomplete: bool,
    device_sha256: String,
    audio_path: String,
    audio_sha256: String,
    cursor: Option<super::super::recording_transfer::Source>,
}

fn hash_file(path: &Path) -> Result<String, String> {
    let meta = fs::symlink_metadata(path).map_err(|e| format!("读取已保存录音失败：{e}"))?;
    if !meta.is_file() || meta.file_type().is_symlink() { return Err("已保存录音不可用".into()); }
    let mut file = File::open(path).map_err(|e| format!("打开已保存录音失败：{e}"))?;
    let mut hash = Sha256::new();
    let mut buffer = [0u8; 65536];
    loop {
        let n = file.read(&mut buffer).map_err(|e| format!("校验已保存录音失败：{e}"))?;
        if n == 0 { break; }
        hash.update(&buffer[..n]);
    }
    Ok(format!("{:x}", hash.finalize()))
}

impl Intent {
    fn key(&self) -> String {
        let identity = format!("{}\0{}\0{}\0{}", self.device.trim().to_ascii_lowercase(),
            self.recording_id, self.total_length, self.device_sha256);
        format!("{:x}", Sha256::digest(identity.as_bytes()))
    }
    fn path(&self, root: &Path) -> PathBuf { root.join(format!("{PREFIX}{}.json", self.key())) }
    pub(super) fn id(&self) -> u32 { self.recording_id }
    pub(super) fn len(&self) -> u32 { self.total_length }
    pub(super) fn audio_path(&self) -> &Path { Path::new(&self.audio_path) }
    pub(super) fn release_cursor(&self, root: &Path) -> Result<(), String> {
        match &self.cursor {
            Some(source) => {
                if !super::super::device_connection::same_device_id(&source.device, &self.device)
                    || source.recording_id != self.recording_id || source.total_length != self.total_length {
                    return Err("续传记录与设备录音不匹配".into());
                }
                let part = super::super::recording_transfer::path(root, source)?;
                if !part.exists() { return Ok(()); }
                if hash_file(&part)? != self.device_sha256 { return Err("续传文件与已确认录音不匹配".into()); }
                super::super::recording_transfer::release(root, source.clone())
            }
            None => Ok(()),
        }
    }
    pub(super) fn confirmed_recording(&self) -> CompanionSyncedRecording {
        CompanionSyncedRecording { recording_id: self.recording_id, duration_ms: self.duration_ms,
            total_length: self.total_length, sha256: self.device_sha256.clone(),
            recording_path: self.audio_path.clone(), device_reclaimed: true,
            capture_incomplete: self.capture_incomplete }
    }
    pub(super) fn digest(&self) -> Result<[u8; 32], String> {
        if self.device_sha256.len() != 64 || !self.device_sha256.bytes().all(|b| b.is_ascii_hexdigit()) {
            return Err("设备录音校验值不可用".into());
        }
        let mut bytes = [0u8; 32];
        for (i, byte) in bytes.iter_mut().enumerate() {
            *byte = u8::from_str_radix(&self.device_sha256[i * 2..i * 2 + 2], 16).map_err(|e| e.to_string())?;
        }
        Ok(bytes)
    }
    fn matches(&self, row: &crate::companion_v1::CompanionV1HostSession) -> bool {
        matches!(row.source.as_str(), "boardDevice" | "deviceFlash") && row.device_recording_key.is_none()
            && row.source_device_id.as_deref().is_some_and(|d| super::super::device_connection::same_device_id(d, &self.device))
            && row.device_recording_id == Some(self.recording_id)
            && row.device_total_length == Some(self.total_length)
            && row.device_sha256.as_deref() == Some(self.device_sha256.as_str())
            && row.audio_stored && row.audio_path.as_deref() == Some(self.audio_path.as_str())
    }
    pub(super) fn verify(&self, state: &Path) -> Result<(), String> {
        self.digest()?;
        if self.schema != 1 || self.total_length == 0 || self.device.is_empty() { return Err("录音确认记录不可用".into()); }
        let loaded = super::super::session_store::load(state);
        if loaded.state.status == "blocked" { return Err("会议库不可用".into()); }
        let rows: Vec<crate::companion_v1::CompanionV1HostSession> = serde_json::from_slice(
            loaded.bytes.as_deref().ok_or("会议已不存在")?).map_err(|e| e.to_string())?;
        let matching: Vec<_> = rows.iter().filter(|row| self.matches(row)).collect();
        if matching.len() != 1 || matching[0].device_reclaimed { return Err("录音已确认或与会议库不再匹配".into()); }
        if hash_file(self.audio_path())? != self.audio_sha256 { return Err("本地录音已改变".into()); }
        Ok(())
    }
    pub(super) fn confirm(&self, state: &Path) -> Result<(), String> {
        super::super::session_store::update_checked(state, |rows| {
            let matching: Vec<_> = rows.iter_mut().filter(|row| self.matches(row)).collect();
            if matching.len() != 1 { return Err("录音与会议库不再匹配".into()); }
            matching.into_iter().next().unwrap().device_reclaimed = true;
            Ok(())
        })
    }
    pub(super) fn remove(&self, root: &Path) -> Result<(), String> {
        match fs::remove_file(self.path(root)) {
            Ok(()) => Ok(()),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(()),
            Err(e) => Err(format!("清理录音确认记录失败：{e}")),
        }
    }
}

pub(super) fn prepare(root: &Path, state: &Path, device: &str, item: &CompanionSyncedRecording,
    cursor: Option<super::super::recording_transfer::Source>) -> Result<(Intent, File), String> {
    let intent = Intent { schema: 1, device: device.into(), recording_id: item.recording_id,
        total_length: item.total_length, duration_ms: item.duration_ms,
        capture_incomplete: item.capture_incomplete, device_sha256: item.sha256.clone(),
        audio_path: item.recording_path.clone(), audio_sha256: hash_file(Path::new(&item.recording_path))?, cursor };
    let guard = lock(root, &intent)?;
    intent.verify(state)?;
    let path = intent.path(root);
    if fs::symlink_metadata(&path).is_ok_and(|m| !m.is_file() || m.file_type().is_symlink()) {
        return Err("录音确认记录路径不可用".into());
    }
    super::super::export::write_atomic(&path, &serde_json::to_vec(&intent).map_err(|e| e.to_string())?)?;
    Ok((intent, guard))
}

/// Ignore damaged/foreign entries; they must not stop ordinary recordings.
pub(super) fn candidates(root: &Path, device: &str, selected: Option<u32>, present: &[u32]) -> Vec<Intent> {
    let Ok(files) = fs::read_dir(root) else { return Vec::new(); };
    let mut out = Vec::new();
    for file in files.flatten() {
        let path = file.path();
        let name = file.file_name();
        let name = name.to_string_lossy();
        if !name.starts_with(PREFIX) || !name.ends_with(".json") { continue; }
        let Ok(meta) = fs::symlink_metadata(&path) else { continue; };
        if !meta.is_file() || meta.file_type().is_symlink() || meta.len() > 16384 { continue; }
        let Ok(bytes) = fs::read(&path) else { continue; };
        let Ok(intent) = serde_json::from_slice::<Intent>(&bytes) else { continue; };
        if intent.path(root) != path || !super::super::device_connection::same_device_id(&intent.device, device)
            || selected.is_some_and(|id| id != intent.recording_id) || present.contains(&intent.recording_id) { continue; }
        out.push(intent);
    }
    out.sort_by_key(|i| i.recording_id);
    out
}

/// Serialize replay attempts between app processes, including while waiting for BLE.
pub(super) fn lock(root: &Path, intent: &Intent) -> Result<File, String> {
    let path = root.join(format!("{PREFIX}{}.lock", intent.key()));
    if fs::symlink_metadata(&path).is_ok_and(|m| !m.is_file() || m.file_type().is_symlink()) { return Err("录音确认锁不可用".into()); }
    let file = OpenOptions::new().create(true).truncate(false).read(true).write(true).open(path).map_err(|e| e.to_string())?;
    file.try_lock().map_err(|e| e.to_string())?;
    Ok(file)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn lost_reply_can_be_replayed_only_for_exact_unchanged_local_recording() {
        let root = std::env::temp_dir().join(format!("companion-reclaim-{}", uuid::Uuid::new_v4()));
        fs::create_dir_all(&root).unwrap();
        let state = root.join("sessions.json");
        let wav = root.join("meeting.wav");
        let original = vec![42u8; 96];
        fs::write(&wav, &original).unwrap();
        let device = "AA:BB:CC:DD:EE:FF";
        let item = CompanionSyncedRecording { recording_id: 17, duration_ms: 1000, total_length: 32,
            sha256: "ab".repeat(32), recording_path: wav.to_string_lossy().into_owned(),
            device_reclaimed: false, capture_incomplete: false };
        super::super::super::checkpoint_received_recording(&state, device, &item).unwrap();
        let (intent, guard) = prepare(&root, &state, device, &item, None).unwrap();
        assert!(lock(&root, &intent).is_err(), "another process must not replay during an active consume");
        drop(guard); // process/connection ends before its receipt is saved
        assert!(candidates(&root, "11:22:33:44:55:66", None, &[]).is_empty());
        assert!(candidates(&root, device, Some(18), &[]).is_empty());
        assert!(candidates(&root, device, None, &[17]).is_empty());
        let recovered = candidates(&root, device, None, &[]);
        assert_eq!(recovered.len(), 1);
        assert_eq!(recovered[0].digest().unwrap(), [0xabu8; 32]);
        let _guard = lock(&root, &recovered[0]).unwrap();
        recovered[0].verify(&state).unwrap();
        fs::write(&wav, b"changed").unwrap();
        assert!(recovered[0].verify(&state).is_err(), "never consume after local audio changed");
        fs::write(&wav, &original).unwrap();
        recovered[0].verify(&state).unwrap();
        super::super::super::session_store::update(&state, |rows| {
            rows[0].audio_path = Some("different.wav".into());
            rows[0].title = "用户修改的会议名称".into();
        }).unwrap();
        assert!(recovered[0].verify(&state).is_err(), "never use an audio file no longer owned by the meeting");
        super::super::super::session_store::update(&state, |rows| rows[0].audio_path = Some(item.recording_path.clone())).unwrap();
        recovered[0].verify(&state).unwrap();
        let before = super::super::super::session_store::load(&state);
        let stale_rows: Vec<crate::companion_v1::CompanionV1HostSession> = serde_json::from_slice(&before.bytes.unwrap()).unwrap();
        let mut snapshot = crate::companion_v1::fixture_snapshot();
        snapshot.device.device_id = Some(device.into());
        snapshot.host.sessions = stale_rows;
        // This corresponds to a matching real device receipt, not catalog absence.
        recovered[0].confirm(&state).unwrap();
        super::super::super::merge_synced_recordings(&mut snapshot, &[recovered[0].confirmed_recording()]);
        assert!(snapshot.host.sessions[0].device_reclaimed, "normal sync must see the recovered confirmation");
        assert_eq!(snapshot.host.sessions[0].title, "用户修改的会议名称");
        assert!(recovered[0].verify(&state).is_err());
        recovered[0].remove(&root).unwrap();
        assert!(candidates(&root, device, None, &[]).is_empty());
        let loaded = super::super::super::session_store::load(&state);
        let rows: Vec<crate::companion_v1::CompanionV1HostSession> = serde_json::from_slice(&loaded.bytes.unwrap()).unwrap();
        assert!(rows.iter().find(|row| row.device_recording_id == Some(17)).unwrap().device_reclaimed);
        assert_eq!(rows[0].title, "用户修改的会议名称");
        assert_eq!(fs::read(&wav).unwrap(), original);
    }
}
