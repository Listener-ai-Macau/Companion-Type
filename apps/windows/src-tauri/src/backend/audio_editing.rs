//! Non-destructive local edits. Provenance references are never deletion ownership.
use super::{
    audio_artifacts::{self, Purpose},
    audio_derivation::{self as pcm, Provenance, SourceIdentity},
};
use crate::companion_v1::{CompanionV1AudioChunk, CompanionV1HostSession, CompanionV1Snapshot};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeSet,
    fs::{self, File},
    path::{Path, PathBuf},
};
#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct OutputRequest {
    pub name: String,
    pub plan: pcm::Plan,
}
#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Request {
    pub library_token: String,
    pub outputs: Vec<OutputRequest>,
}
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Sources {
    pub library_token: String,
    pub sources: Vec<SourceIdentity>,
}
pub(super) struct Resolved {
    pub inputs: Vec<pcm::Input>,
    pub _leases: Vec<Option<File>>,
}
impl Resolved {
    pub fn identities(&self) -> Vec<SourceIdentity> {
        self.inputs.iter().map(|i| i.source.clone()).collect()
    }
}
pub fn context_token() -> Result<String, String> {
    let root = super::audio_storage::recording_root()?
        .canonicalize()
        .map_err(|e| e.to_string())?;
    Ok(format!(
        "{:x}",
        Sha256::digest(
            format!(
                "Companion local edit library v1\0{}\0{}",
                root.to_string_lossy(),
                super::persistence::state_file_path().to_string_lossy()
            )
            .as_bytes()
        )
    ))
}
pub(crate) fn available(snapshot: &CompanionV1Snapshot) -> Result<(), String> {
    if snapshot.host.persistence.status != "ready"
        || snapshot.meeting.active
        || snapshot.device.recording
        || snapshot.host.sessions.iter().any(|r| {
            r.status == "recording"
                || matches!(
                    r.recovery.stage.as_str(),
                    "transcribing" | "generatingMinutes"
                )
        })
    {
        return Err("请先完成录音和整理，并保存资料库，再编辑音频。".into());
    }
    Ok(())
}
fn file_in_root(path: &Path, root: &Path) -> Result<PathBuf, String> {
    let meta = fs::symlink_metadata(path).map_err(|_| "完整本机原音尚未就绪。")?;
    let actual = path.canonicalize().map_err(|_| "本机原音已移动。")?;
    if !meta.is_file() || meta.file_type().is_symlink() || actual.parent() != Some(root) {
        return Err("编辑只使用当前资料库已核对的本机原音。".into());
    }
    Ok(actual)
}
pub(super) fn resolve(snapshot: &CompanionV1Snapshot, keys: &[String]) -> Result<Resolved, String> {
    available(snapshot)?;
    if keys.is_empty()
        || keys.len() > 128
        || keys.iter().collect::<BTreeSet<_>>().len() != keys.len()
    {
        return Err("请选择有效的录音来源。".into());
    }
    let root = super::audio_storage::recording_root()?
        .canonicalize()
        .map_err(|e| e.to_string())?;
    let mut inputs = Vec::new();
    let mut leases = Vec::new();
    for key in keys {
        let row = snapshot
            .host
            .sessions
            .iter()
            .find(|r| &r.id == key)
            .ok_or("原录音已不在当前资料库。")?;
        super::library_lifecycle::require_available(row)?;
        if row.capture_incomplete
            || row.recorder_control_uncertain
            || !row.audio_stored
            || !row.retention.audio_cached
            || matches!(
                row.pending_reason.as_deref(),
                Some("needs_device_sync" | "needs_local_audio" | "capture_incomplete")
            )
        {
            return Err("请先接收或恢复完整原音，再进行编辑。".into());
        }
        let mut hash = Sha256::new();
        hash.update(b"Companion immutable edit source v1\0");
        hash.update(key.as_bytes());
        hash.update(row.source.as_bytes());
        let mut parts = Vec::new();
        let frames;
        let meeting;
        if row.source == "hostMeeting" {
            let tracks = row.meeting_tracks.as_ref().ok_or("会议双音轨尚未保存。")?;
            for part in tracks.microphone.iter().chain(&tracks.system) {
                let path = file_in_root(Path::new(&part.path), &root)?;
                leases.push(audio_artifacts::usage(&path)?);
            }
            super::meeting_audio_recovery::verify_tracks(tracks, row.audio_bytes, row.duration_ms)?;
            let mut maximum = 0;
            for (tag, track) in [(0u8, &tracks.microphone), (1u8, &tracks.system)] {
                hash.update([tag]);
                hash.update((track.len() as u64).to_le_bytes());
                let mut total = 0u64;
                for part in track {
                    let path = file_in_root(Path::new(&part.path), &root)?;
                    let (actual, sha256) = pcm::probe(&path)?;
                    if part.first_sample != total || actual != part.samples {
                        return Err("会议音轨不连续或不完整。".into());
                    }
                    total = total.checked_add(actual).ok_or("会议音轨长度无效。")?;
                    hash.update(actual.to_le_bytes());
                    hash.update(sha256.as_bytes());
                    parts.push(pcm::InputPart { path, sha256 });
                }
                maximum = maximum.max(total);
            }
            frames = maximum;
            meeting = Some(tracks.clone());
        } else {
            let paths = if let Some(parts) = super::host_segmented_capture::saved_parts(row)? {
                parts.into_iter().map(|p| p.0).collect::<Vec<_>>()
            } else if row.device_recording_key.is_some() {
                super::recording_wire::receiver::Receiver::verified_audio_parts(row)?
                    .into_iter()
                    .map(|p| p.0)
                    .collect()
            } else {
                vec![super::meeting_workspace::local_audio_path(snapshot, key)?]
            };
            let mut total = 0u64;
            hash.update((paths.len() as u64).to_le_bytes());
            for path in paths {
                let path = file_in_root(&path, &root)?;
                leases.push(audio_artifacts::usage(&path)?);
                let (actual, sha256) = pcm::probe(&path)?;
                total = total.checked_add(actual).ok_or("原音长度无效。")?;
                hash.update(actual.to_le_bytes());
                hash.update(sha256.as_bytes());
                parts.push(pcm::InputPart { path, sha256 });
            }
            frames = total;
            meeting = None;
        }
        if frames == 0 {
            return Err("这条录音没有完整采样。".into());
        }
        inputs.push(pcm::Input {
            source: SourceIdentity {
                key: key.clone(),
                identity: format!("{:x}", hash.finalize()),
                frames,
                sample_rate: 16000,
            },
            parts,
            meeting,
        });
    }
    Ok(Resolved {
        inputs,
        _leases: leases,
    })
}
pub fn sources(snapshot: &CompanionV1Snapshot, keys: &[String]) -> Result<Sources, String> {
    let resolved = resolve(snapshot, keys)?;
    Ok(Sources {
        library_token: context_token()?,
        sources: resolved.identities(),
    })
}
pub fn owner_path(row: &CompanionV1HostSession, root: &Path) -> PathBuf {
    owner_path_id(&row.id, root)
}
fn owner_path_id(id: &str, root: &Path) -> PathBuf {
    root.join(format!(
        "audio-edit-owner-{:x}.json",
        Sha256::digest(id.as_bytes())
    ))
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Owner {
    schema: u8,
    session_id: String,
    audio_sha256: String,
    provenance: Provenance,
}
fn owner(id: &str, sha: &str, provenance: &Provenance) -> Result<Vec<u8>, String> {
    provenance.validate()?;
    serde_json::to_vec(&Owner {
        schema: 1,
        session_id: id.into(),
        audio_sha256: sha.into(),
        provenance: provenance.clone(),
    })
    .map_err(|e| e.to_string())
}
pub fn provenance(row: &CompanionV1HostSession) -> Result<Option<Provenance>, String> {
    if row.source != "derivedAudio" {
        return Ok(None);
    }
    let root = super::audio_storage::recording_root()?;
    let path = owner_path(row, &root);
    let meta = fs::symlink_metadata(&path).map_err(|_| "录音来源记录缺失，原录音未改动。")?;
    if !meta.is_file() || meta.file_type().is_symlink() || meta.len() > 1024 * 1024 {
        return Err("录音来源记录无效。".into());
    }
    let bytes = fs::read(&path).map_err(|e| e.to_string())?;
    audio_artifacts::verify_owned_leaf(
        &path,
        Purpose::SessionReceipt,
        bytes.len() as u64,
        &format!("{:x}", Sha256::digest(&bytes)),
    )?;
    let item: Owner = serde_json::from_slice(&bytes).map_err(|_| "录音来源记录已损坏。")?;
    if item.schema != 1 || item.session_id != row.id || item.audio_sha256.len() != 64 {
        return Err("录音来源身份不符。".into());
    }
    item.provenance.validate()?;
    if row.audio_stored {
        let original = super::import_audio::original_chunk(row)?;
        if original.id.rsplit('-').next() != Some(item.audio_sha256.as_str()) {
            return Err("录音内容与来源身份不符。".into());
        }
    }
    Ok(Some(item.provenance))
}
pub fn source_target(
    snapshot: &CompanionV1Snapshot,
    id: &str,
    index: usize,
) -> Result<serde_json::Value, String> {
    let row = snapshot
        .host
        .sessions
        .iter()
        .find(|r| r.id == id)
        .ok_or("这份成品已不存在。")?;
    super::library_lifecycle::require_available(row)?;
    let map = provenance(row)?.ok_or("这条录音没有编辑来源。")?;
    let slice = map.plan.slices.get(index).ok_or("来源区间无效。")?;
    let resolved = resolve(snapshot, &[slice.source_key.clone()])?;
    if resolved.inputs[0].source.identity != slice.source_identity {
        return Err("原录音已变化，不能沿旧时间定位。".into());
    }
    Ok(serde_json::json!({"sessionId":slice.source_key,"positionMs":slice.start_frame/16}))
}
pub(super) fn row(
    snapshot: &CompanionV1Snapshot,
    id: &str,
    name: &str,
    frames: u64,
    bytes: u64,
    sha: &str,
) -> Result<CompanionV1HostSession, String> {
    let root = super::audio_storage::recording_root()?;
    let now = super::connection_timestamp();
    let mut request = crate::control_request(
        crate::companion_v1::CompanionV1ControlAction::MeetingStart,
        Some(id.into()),
    );
    request.title = Some(name.into());
    request.prompt_id = Some(crate::companion_v1::CAPTURE_ONLY_PROMPT.into());
    request.meeting_mode = Some("offlineStore".into());
    let mut row = crate::companion_v1::create_host_session(snapshot, &request, &now);
    row.source = "derivedAudio".into();
    row.status = "captured".into();
    row.started_at = None;
    row.stopped_at = None;
    row.audio_path = Some(
        root.join(format!("{id}.wav"))
            .to_string_lossy()
            .into_owned(),
    );
    row.audio_stored = true;
    row.retention.audio_cached = true;
    row.duration_ms = frames / 16;
    row.audio_bytes = bytes;
    row.chunks = super::seal_companion_v1_session_chunks(&row, &now, row.duration_ms, Some(bytes));
    row.chunks.push(CompanionV1AudioChunk {
        id: format!("{id}-imported-original-{sha}"),
        path: Some(
            root.join(format!("{id}.original.wav"))
                .to_string_lossy()
                .into_owned(),
        ),
        started_at: None,
        stopped_at: None,
        duration_ms: row.duration_ms,
        bytes,
        status: "importedOriginal".into(),
    });
    Ok(row)
}
pub(super) fn publish(
    row: &CompanionV1HostSession,
    map: &Provenance,
    prepared: &Path,
    bytes: u64,
    sha: &str,
) -> Result<(), String> {
    let root = super::audio_storage::recording_root()?;
    let anchor = root.join(format!("{}.wav", row.id));
    let original = root.join(format!("{}.original.wav", row.id));
    let owner_path = owner_path(row, &root);
    super::owned_attachments::copy_new(
        &anchor,
        &anchor,
        Purpose::Recording,
        prepared,
        bytes,
        sha,
        || Ok(()),
    )?;
    super::owned_attachments::copy_new(
        &anchor,
        &original,
        Purpose::ImportedOriginal,
        prepared,
        bytes,
        sha,
        || Ok(()),
    )?;
    let data = owner(&row.id, sha, map)?;
    super::owned_attachments::write_new(&owner_path, &owner_path, Purpose::SessionReceipt, &data)?;
    Ok(())
}
pub(super) fn verify_published(
    row: &CompanionV1HostSession,
    map: &Provenance,
    bytes: u64,
    sha: &str,
) -> Result<(), String> {
    let root = super::audio_storage::recording_root()?;
    let anchor = root.join(format!("{}.wav", row.id));
    audio_artifacts::verify_owned_leaf(&anchor, Purpose::Recording, bytes, sha)?;
    super::import_audio::verify_original(row, &root)?;
    if provenance(row)?.as_ref() != Some(map) {
        return Err("已保存成品的来源不符，拒绝覆盖。".into());
    }
    Ok(())
}
pub(super) fn validate_sources(
    snapshot: &CompanionV1Snapshot,
    expected: &[SourceIdentity],
) -> Result<(), String> {
    let actual = resolve(
        snapshot,
        &expected.iter().map(|s| s.key.clone()).collect::<Vec<_>>(),
    )?;
    if actual.identities() != expected {
        return Err("提交前原音已变化，请重新读取编辑。".into());
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::backend::{CompanionBackend, FixtureCompanionBackend};
    #[test]
    #[ignore = "isolated recording and index environment; native candidate builder runs explicitly"]
    fn derived_recording_exact_pcm_backup_restore_and_scoped_purge() {
        let dir =
            std::env::temp_dir().join(format!("companion-audio-edit-{}", uuid::Uuid::new_v4()));
        let audio = dir.join("recordings");
        fs::create_dir_all(&audio).unwrap();
        std::env::set_var("COMPANION_TYPE_RECORDING_DIR", &audio);
        std::env::set_var("COMPANION_TYPE_STATE_PATH", dir.join("sessions.json"));
        super::super::session_store::save(&dir.join("sessions.json"), &[]).unwrap();
        let input = dir.join("public-generated.wav");
        let mut file = denzic_host_audio_v1_core::wav::WavWriter::create(&input).unwrap();
        file.append_samples(&(0..32017).map(|i| (i % 25000) as i16).collect::<Vec<_>>())
            .unwrap();
        file.finalize().unwrap();
        drop(file);
        let user_bytes = fs::read(&input).unwrap();
        let backend = FixtureCompanionBackend::new();
        let snapshot = backend.import_audio_file(&input).unwrap();
        let parent = snapshot.host.sessions[0].clone();
        let original = fs::read(parent.audio_path.as_ref().unwrap()).unwrap();
        let set = resolve(&snapshot, &[parent.id.clone()]).unwrap();
        let identity = set.identities()[0].clone();
        assert_eq!(
            identity.frames, 32017,
            "never lose the partial final millisecond"
        );
        let plan = pcm::Plan {
            schema: 1,
            sample_rate: 16000,
            frames: 27,
            slices: vec![
                pcm::Slice {
                    source_key: parent.id.clone(),
                    source_identity: identity.identity.clone(),
                    start_frame: 31997,
                    end_frame: 32017,
                    output_start_frame: 0,
                    output_end_frame: 20,
                },
                pcm::Slice {
                    source_key: parent.id.clone(),
                    source_identity: identity.identity.clone(),
                    start_frame: 3,
                    end_frame: 10,
                    output_start_frame: 20,
                    output_end_frame: 27,
                },
            ],
        };
        let stage = dir.join("stage");
        fs::create_dir(&stage).unwrap();
        let rendered = pcm::render(&stage, &set.inputs, &plan, |_, _| Ok(())).unwrap();
        let map = plan.provenance(&set.identities()).unwrap();
        let id = format!("edit-{}", uuid::Uuid::new_v4().simple());
        let child = row(
            &snapshot,
            &id,
            "公开生成PCM · 尾段与重排",
            rendered.frames,
            rendered.bytes,
            &rendered.sha256,
        )
        .unwrap();
        publish(
            &child,
            &map,
            &rendered.temporary,
            rendered.bytes,
            &rendered.sha256,
        )
        .unwrap();
        // Post-publication retry uses the exact same leaves, never overwrites.
        publish(
            &child,
            &map,
            &rendered.temporary,
            rendered.bytes,
            &rendered.sha256,
        )
        .unwrap();
        verify_published(&child, &map, rendered.bytes, &rendered.sha256).unwrap();
        let before = backend.snapshot().unwrap();
        assert!(
            !before.host.sessions.iter().any(|r| r.id == id),
            "preparation is not a library row"
        );
        backend
            .commit_audio_edit(child.clone(), &map.sources, &context_token().unwrap())
            .unwrap();
        // Simulate a row ACK committed before the task receipt. A later user
        // rename must survive exact-job adoption, not be replaced by old row.
        super::super::session_store::update_checked(
            &super::super::persistence::state_file_path(),
            |rows| {
                rows.iter_mut().find(|r| r.id == id).unwrap().title = "已经修改的成品标题".into();
                Ok(())
            },
        )
        .unwrap();
        backend
            .commit_audio_edit(child.clone(), &map.sources, &context_token().unwrap())
            .unwrap();
        assert_eq!(
            backend
                .snapshot()
                .unwrap()
                .host
                .sessions
                .iter()
                .find(|r| r.id == id)
                .unwrap()
                .title,
            "已经修改的成品标题"
        );
        let mut snapshot = backend.snapshot().unwrap();
        snapshot.host.selected_session_id = Some(id.clone());
        assert_eq!(snapshot.host.sessions.len(), 2);
        assert!(
            child.transcript_text.is_empty()
                && child.minutes.is_none()
                && child.meeting_notes.is_empty()
        );
        let actual = fs::read(child.audio_path.as_ref().unwrap()).unwrap();
        let expected = [
            &original[44 + 31997 * 2..44 + 32017 * 2],
            &original[44 + 3 * 2..44 + 10 * 2],
        ]
        .concat();
        assert_eq!(&actual[44..], expected);
        assert_eq!(provenance(&child).unwrap(), Some(map.clone()));
        assert_eq!(
            source_target(&snapshot, &id, 0).unwrap()["positionMs"],
            31997 / 16
        );
        let export = dir.join("export.wav");
        super::super::audio_export::export(&snapshot, &id, &export).unwrap();
        assert_eq!(fs::read(export).unwrap(), actual);
        drop(set);
        let backups = dir.join("backups");
        fs::create_dir(&backups).unwrap();
        let backup = super::super::library_backup::save(&snapshot, &audio, &backups).unwrap();
        let target = dir.join("restored");
        fs::create_dir(&target).unwrap();
        std::env::set_var("COMPANION_TYPE_RECORDING_DIR", &target);
        let rows =
            super::super::library_backup::restore_files(Path::new(&backup.path), &target).unwrap();
        let mut restored = snapshot.clone();
        restored.host.sessions = rows;
        let restored_child = restored
            .host
            .sessions
            .iter()
            .find(|r| r.id == id)
            .unwrap()
            .clone();
        assert_eq!(provenance(&restored_child).unwrap(), Some(map));
        assert_eq!(
            resolve(&restored, &[parent.id.clone()])
                .unwrap()
                .identities()[0],
            identity,
            "identity survives a new root"
        );
        let parent_restored = restored
            .host
            .sessions
            .iter()
            .find(|r| r.id == parent.id)
            .unwrap()
            .audio_path
            .clone()
            .unwrap();
        let manager = super::super::privacy::PrivacyManager::for_handoff_test(
            target.canonicalize().unwrap(),
            dir.join("legacy"),
        );
        let erased = manager.erase_selected_audio(&restored);
        assert_eq!(erased.failed_files, 0);
        assert!(owner_path(&restored_child, &target).is_file());
        let child_mut = restored
            .host
            .sessions
            .iter_mut()
            .find(|r| r.id == id)
            .unwrap();
        child_mut.audio_stored = false;
        child_mut.retention.audio_cached = false;
        child_mut.audio_path = None;
        child_mut.chunks.clear();
        assert!(
            provenance(child_mut).unwrap().is_some(),
            "audio cleanup keeps textual source mapping"
        );
        let erased = manager.erase_selected_recording(&restored);
        assert_eq!(erased.failed_files, 0);
        assert!(!owner_path(&restored_child, &target).exists());
        assert_eq!(fs::read(parent_restored).unwrap(), original);
        assert_eq!(fs::read(&input).unwrap(), user_bytes);
        std::env::remove_var("COMPANION_TYPE_RECORDING_DIR");
        std::env::remove_var("COMPANION_TYPE_STATE_PATH");
        fs::remove_dir_all(dir).unwrap();
    }
}
