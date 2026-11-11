//! OS file delivery is a pending receipt, not a second media database.
//! Originals are copied only after an explicit library/meeting confirmation.
use crate::coordinator::CompanionCoordinator;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    fs::{self, File, OpenOptions},
    path::{Path, PathBuf},
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc,
    },
};
static ACTIVE: AtomicBool = AtomicBool::new(false);
#[derive(Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Entry {
    id: String,
    name: String,
    mime: String,
    bytes: u64,
    kind: String,
    state: String,
    received_at: u64,
    source_path: PathBuf,
    #[serde(default)]
    message: Option<String>,
    #[serde(default)]
    key: Option<String>,
    #[serde(default)]
    library_id: Option<String>,
    #[serde(default)]
    target_title: Option<String>,
    #[serde(default)]
    target_identity: Option<String>,
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Data {
    version: u32,
    rows: Vec<Entry>,
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Envelope {
    body: String,
    sha256: String,
}
struct Store {
    path: PathBuf,
    _lock: File,
    rows: Vec<Entry>,
}
fn hash(value: &[u8]) -> String {
    format!("{:x}", Sha256::digest(value))
}
fn sibling(path: &Path, suffix: &str) -> PathBuf {
    let mut name = path.as_os_str().to_os_string();
    name.push(suffix);
    PathBuf::from(name)
}
fn valid_id(id: &str) -> bool {
    uuid::Uuid::parse_str(id).is_ok_and(|v| v.to_string() == id)
}
fn root_path() -> PathBuf {
    sibling(&super::persistence::state_file_path(), ".incoming-v1.json")
}
fn file_lock(path: &Path) -> Result<File, String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|_| "接收目录暂不可写，原文件保留。")?;
    }
    if fs::symlink_metadata(path).is_ok_and(|m| m.file_type().is_symlink()) {
        return Err("接收锁位置无效，原资料保留。".into());
    }
    let file = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .open(path)
        .map_err(|_| "无法打开接收锁，请稍后重试。")?;
    file.try_lock()
        .map_err(|_| "接收项正由另一操作处理，请稍后重试。")?;
    Ok(file)
}
fn operation(id: &str) -> Result<File, String> {
    if !valid_id(id) {
        return Err("接收标识无效。".into());
    }
    file_lock(&sibling(&root_path(), &format!(".{id}.operation.lock")))
}
impl Store {
    fn open() -> Result<Self, String> {
        let path = root_path();
        let lock = file_lock(&sibling(&path, ".lock"))?;
        let rows = match fs::symlink_metadata(&path) {
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Vec::new(),
            Err(_) => return Err("接收清单不可读取，原资料保留。".into()),
            Ok(meta) => {
                if !meta.is_file() || meta.file_type().is_symlink() || meta.len() > 512 * 1024 {
                    return Err("接收清单位置或大小无效，原资料保留。".into());
                }
                let envelope: Envelope =
                    serde_json::from_slice(&fs::read(&path).map_err(|_| "接收清单暂不可读。")?)
                        .map_err(|_| "接收清单损坏，请保留文件后检查。")?;
                if hash(envelope.body.as_bytes()) != envelope.sha256 {
                    return Err("接收清单校验失败，原资料保留。".into());
                }
                let data: Data =
                    serde_json::from_str(&envelope.body).map_err(|_| "接收清单内容无效。")?;
                if data.version != 1 || data.rows.len() > 32 {
                    return Err("接收清单版本或长度无效。".into());
                }
                let mut ids = std::collections::HashSet::new();
                for row in &data.rows {
                    if !valid_id(&row.id)
                        || !ids.insert(&row.id)
                        || row.name.is_empty()
                        || row.name.chars().count() > 200
                        || !row.source_path.is_absolute()
                        || !["ready", "attempting", "complete", "failed"]
                            .contains(&row.state.as_str())
                        || !["media", "document", "image", "unsupported"]
                            .contains(&row.kind.as_str())
                    {
                        return Err("接收清单身份无效，原资料保留。".into());
                    }
                }
                data.rows
            }
        };
        Ok(Self {
            path,
            _lock: lock,
            rows,
        })
    }
    fn save(&self) -> Result<(), String> {
        let body = serde_json::to_string(&Data {
            version: 1,
            rows: self.rows.clone(),
        })
        .map_err(|_| "接收清单无法保存。")?;
        let bytes = serde_json::to_vec(&Envelope {
            sha256: hash(body.as_bytes()),
            body,
        })
        .map_err(|_| "接收清单无法保存。")?;
        if bytes.len() > 512 * 1024 {
            return Err("接收清单已满，请先整理后重试。".into());
        }
        super::export::write_atomic(&self.path, &bytes).map(|_| ())
    }
    fn entry(&self, id: &str) -> Result<&Entry, String> {
        self.rows
            .iter()
            .find(|r| r.id == id)
            .ok_or("这项接收已移除，请重新读取。".into())
    }
    fn set(&mut self, row: Entry) -> Result<(), String> {
        let target = self
            .rows
            .iter_mut()
            .find(|r| r.id == row.id)
            .ok_or("这项接收已移除。")?;
        *target = row;
        self.save()
    }
}
fn classify(path: &Path) -> (&'static str, &'static str) {
    let ext = path
        .extension()
        .and_then(|s| s.to_str())
        .unwrap_or("")
        .to_ascii_lowercase();
    match ext.as_str() {
        "wav" | "mp3" | "m4a" | "mp4" | "aac" | "flac" | "ogg" => {
            ("media", "application/octet-stream")
        }
        "jpg" | "jpeg" => ("image", "image/jpeg"),
        "png" => ("image", "image/png"),
        "webp" => ("image", "image/webp"),
        "pdf" | "docx" | "xlsx" | "pptx" | "txt" | "md" | "csv" => {
            ("document", "application/octet-stream")
        }
        _ => ("unsupported", "application/octet-stream"),
    }
}
pub(crate) fn receive(paths: Vec<PathBuf>, cwd: &Path) -> Result<(), String> {
    if paths.is_empty() || paths.len() > 16 {
        return Err("一次最多接收16个文件，请分批打开。".into());
    }
    let mut additions = Vec::<Entry>::new();
    let mut store = Store::open()?;
    for path in paths {
        let path = if path.is_absolute() {
            path
        } else {
            cwd.join(path)
        };
        let meta =
            fs::symlink_metadata(&path).map_err(|_| "分享文件暂不可读取，请重新选择原文件。")?;
        if !meta.is_file() || meta.file_type().is_symlink() {
            return Err("请打开实际文件；文件夹或快捷链接不会自动导入。".into());
        }
        let path = path
            .canonicalize()
            .map_err(|_| "文件位置已变化，请重新打开。")?;
        let name = path
            .file_name()
            .and_then(|s| s.to_str())
            .filter(|s| {
                !s.is_empty() && s.chars().count() <= 200 && !s.chars().any(char::is_control)
            })
            .ok_or("文件名称无效或过长，请改名后重新打开。")?
            .to_owned();
        if store
            .rows
            .iter()
            .chain(&additions)
            .any(|r| r.state != "complete" && r.source_path == path)
        {
            continue;
        }
        let (kind, mime) = classify(&path);
        additions.push(Entry {
            id: uuid::Uuid::new_v4().to_string(),
            name,
            mime: mime.into(),
            bytes: meta.len(),
            kind: kind.into(),
            state: "ready".into(),
            received_at: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map_err(|_| "系统时间无效。")?
                .as_millis()
                .try_into()
                .map_err(|_| "系统时间无效。")?,
            source_path: path,
            message: None,
            key: None,
            library_id: None,
            target_title: None,
            target_identity: None,
        });
    }
    if store.rows.len() + additions.len() > 32
        || store.rows.iter().filter(|r| r.state != "complete").count() + additions.len() > 16
    {
        return Err("接收清单已满，请先导入或移除待接收项，再重新打开。".into());
    }
    store.rows.extend(additions);
    store.save()
}
fn view(store: &Store, running: bool) -> Result<serde_json::Value, String> {
    let rows = store
        .rows
        .iter()
        .map(|row| {
            let mut value = serde_json::to_value(row).map_err(|_| "接收结果不可读取。")?;
            value.as_object_mut().unwrap().remove("sourcePath");
            value.as_object_mut().unwrap().remove("targetIdentity");
            Ok(value)
        })
        .collect::<Result<Vec<_>, String>>()?;
    let token = super::audio_editing::context_token()?;
    Ok(
        serde_json::json!({"rows":rows,"libraryId":token,"libraryToken":token,"libraryLabel":"当前 Windows 资料库","running":running}),
    )
}
pub(crate) fn list() -> Result<serde_json::Value, String> {
    let mut store = Store::open()?;
    let mut changed = false;
    let mut running = ACTIVE.load(Ordering::Acquire);
    for row in &mut store.rows {
        if row.state == "attempting" {
            match operation(&row.id) {
                Ok(_) => {
                    row.state = "failed".into();
                    row.message =
                        Some("上次接收尚未确认完成，可在原目标核对并重试。来源文件未改变。".into());
                    changed = true;
                }
                Err(_) => running = true,
            }
        }
    }
    if changed {
        store.save()?;
    }
    view(&store, running)
}
pub(crate) fn remove(id: &str) -> Result<serde_json::Value, String> {
    let _operation = operation(id)?;
    let mut store = Store::open()?;
    store.rows.retain(|r| r.id != id);
    store.save()?;
    view(&store, ACTIVE.load(Ordering::Acquire))
}
fn target_identity(row: &crate::companion_v1::CompanionV1HostSession) -> Result<String, String> {
    super::library_lifecycle::require_available(row)?;
    if !row.audio_stored || !row.retention.audio_cached || row.status == "recording" {
        return Err("请先完整保存这条录音，再附加文件。".into());
    }
    let path = Path::new(row.audio_path.as_deref().ok_or("会议原音尚未保存。")?);
    if !super::audio_storage::owned_recording_reference(
        path,
        &super::audio_storage::recording_root()?,
    ) {
        return Err("会议原音不在当前资料库，未读取其它文件。".into());
    }
    let identity = super::audio_storage::fingerprint(path)?;
    Ok(hash(
        format!(
            "{}\0{}\0{}\0{}",
            row.id,
            path.display(),
            identity.0,
            identity.1
        )
        .as_bytes(),
    ))
}
struct Active;
impl Drop for Active {
    fn drop(&mut self) {
        ACTIVE.store(false, Ordering::Release);
    }
}
pub(crate) fn import(
    coordinator: Arc<CompanionCoordinator>,
    id: &str,
    key: Option<&str>,
    token: &str,
) -> Result<serde_json::Value, String> {
    let _operation = operation(id)?;
    if ACTIVE
        .compare_exchange(false, true, Ordering::AcqRel, Ordering::Acquire)
        .is_err()
    {
        return Err("已有文件正在接收，请等待完成。".into());
    }
    let _active = Active;
    let _lease = coordinator.begin_audio_edit()?;
    if token != super::audio_editing::context_token()? {
        return Err("当前资料库已变化，请重新确认接收目标。".into());
    }
    let mut entry = { Store::open()?.entry(id)?.clone() };
    if entry.kind == "unsupported" {
        return Err("暂不支持此文件格式，请选择音频、Office/PDF文档或常见图片。".into());
    }
    let fixed_id = format!(
        "import-{}",
        uuid::Uuid::parse_str(id)
            .map_err(|_| "接收标识无效。")?
            .simple()
    );
    let snapshot = coordinator.snapshot()?;
    let (destination, title, identity) = if entry.kind == "media" {
        (
            fixed_id,
            format!("新录音 · {}", entry.name),
            "new-recording".to_owned(),
        )
    } else {
        let destination = entry.key.as_deref().or(key).ok_or("请先选择所属会议。")?;
        let row = snapshot
            .host
            .sessions
            .iter()
            .find(|r| r.id == destination)
            .ok_or("所属会议已不存在，请核对资料库。")?;
        (
            destination.to_owned(),
            row.title.clone(),
            target_identity(row)?,
        )
    };
    if key.is_some_and(|requested| requested != destination) {
        return Err("接收目标与已确认的会议不符，请重新读取清单。".into());
    }
    if let Some(prior) = &entry.library_id {
        if prior != token
            || entry.key.as_deref() != Some(destination.as_str())
            || entry.target_identity.as_deref() != Some(identity.as_str())
        {
            return Err(
                "此项已指定其它会议或原音已变化，请回到原资料继续，或移除后重新打开文件。".into(),
            );
        }
    }
    entry.library_id = Some(token.into());
    entry.key = Some(destination.clone());
    entry.target_title = Some(title);
    entry.target_identity = Some(identity);
    Store::open()?.set(entry.clone())?;
    if entry.state == "complete" {
        return list();
    }
    entry.state = "attempting".into();
    entry.message = Some("正在保存原件，来源文件不会修改。".into());
    Store::open()?.set(entry.clone())?;
    let result = (|| {
        if entry.kind == "media" {
            // A fixed native row ID makes a lost reply/restart retry a read of the committed row.
            let loaded = super::session_store::load(&super::persistence::state_file_path());
            if loaded.state.status != "ready" {
                return Err("资料库尚需恢复或重新保存，请先处理后再接收；原文件保留。".into());
            }
            let saved = match loaded.bytes {
                Some(bytes) => super::persistence::migrate_sessions(bytes)
                    .ok_or("资料库尚不可读取，请稍后重试。")?,
                None => Vec::new(),
            };
            if let Some(row) = saved.iter().find(|r| r.id == destination) {
                super::library_lifecycle::require_available(row)?;
                super::import_audio::verify_original(
                    row,
                    &super::audio_storage::recording_root()?,
                )?;
            } else {
                coordinator.import_incoming_audio_file(&entry.source_path, id)?;
            }
        } else {
            let row = snapshot
                .host
                .sessions
                .iter()
                .find(|r| r.id == destination)
                .ok_or("所属会议已不存在。")?;
            if entry.kind == "document" {
                let docs = super::document_context::describe(row)?;
                if docs.rows.iter().any(|r| r.id == id) {
                    super::document_context::original(row, id, docs.revision)?;
                } else {
                    coordinator.change_document_context(super::document_context::Request {
                        session_id: destination.clone(),
                        document_id: id.to_owned(),
                        expected_revision: docs.revision,
                        change: super::document_context::Change::Import(entry.source_path.clone()),
                    })?;
                }
            } else if entry.kind == "image" {
                if row.meeting_notes.iter().any(|note| note.id == id) {
                    super::meeting_note_images::original(row, id)?;
                } else {
                    coordinator.save_meeting_image_note(super::meeting_note_images::Request {
                        session_id: destination.clone(),
                        note_id: id.to_owned(),
                        expected_revision: row.note_revision,
                        text: String::new(),
                        bookmark_id: None,
                        image_path: entry
                            .source_path
                            .to_str()
                            .ok_or("图片路径无法读取。")?
                            .to_owned(),
                        kind: None,
                        references: None,
                    })?;
                }
            }
        }
        Ok::<(), String>(())
    })();
    match result {
        Ok(()) => {
            entry.state = "complete".into();
            entry.message = Some("原件已保存在指定资料库，可在所属录音中查看。".into());
            Store::open()?.set(entry)?;
        }
        Err(error) => {
            entry.state = "failed".into();
            entry.message = Some(error.clone());
            Store::open()?.set(entry)?;
            return Err(error);
        }
    }
    let store = Store::open()?;
    view(&store, false)
}

#[cfg(test)]
mod tests {
    use super::*;
    struct Scope {
        root: PathBuf,
        old: Vec<(&'static str, Option<std::ffi::OsString>)>,
    }
    impl Scope {
        fn new() -> Self {
            let root = std::env::temp_dir()
                .join(format!("companion-incoming-tests-{}", uuid::Uuid::new_v4()));
            fs::create_dir_all(root.join("recordings")).unwrap();
            let old = ["COMPANION_TYPE_STATE_PATH", "COMPANION_TYPE_RECORDING_DIR"]
                .into_iter()
                .map(|key| (key, std::env::var_os(key)))
                .collect();
            std::env::set_var("COMPANION_TYPE_STATE_PATH", root.join("sessions.json"));
            std::env::set_var("COMPANION_TYPE_RECORDING_DIR", root.join("recordings"));
            Self { root, old }
        }
    }
    impl Drop for Scope {
        fn drop(&mut self) {
            for (key, value) in &self.old {
                if let Some(value) = value {
                    std::env::set_var(key, value)
                } else {
                    std::env::remove_var(key)
                }
            }
            let actual = self.root.canonicalize().unwrap();
            assert_eq!(
                actual.parent(),
                Some(std::env::temp_dir().canonicalize().unwrap().as_path())
            );
            assert!(actual
                .file_name()
                .unwrap()
                .to_string_lossy()
                .starts_with("companion-incoming-tests-"));
            fs::remove_dir_all(actual).unwrap();
        }
    }
    #[test]
    fn pending_delivery_is_atomic_bounded_private_and_scoped() {
        let scope = Scope::new();
        let file = scope.root.join("预算 12000.xlsx");
        fs::write(&file, b"public fixture").unwrap();
        receive(vec![file.clone()], &scope.root).unwrap();
        receive(vec![file.clone(), file.clone()], &scope.root).unwrap();
        let current = list().unwrap();
        assert_eq!(current["rows"].as_array().unwrap().len(), 1);
        assert!(current["rows"][0].get("sourcePath").is_none());
        let saved = fs::read(root_path()).unwrap();
        assert!(receive(vec![file, scope.root.join("missing.pdf")], &scope.root).is_err());
        assert_eq!(fs::read(root_path()).unwrap(), saved);
        assert!(receive(vec![scope.root.clone()], &scope.root).is_err());
        assert_eq!(fs::read(root_path()).unwrap(), saved);
        let id = current["rows"][0]["id"].as_str().unwrap();
        {
            let _running = operation(id).unwrap();
            let mut store = Store::open().unwrap();
            let mut entry = store.entry(id).unwrap().clone();
            entry.state = "attempting".into();
            entry.key = Some("original-target".into());
            store.set(entry).unwrap();
            drop(store);
            assert_eq!(list().unwrap()["running"], true);
            assert!(remove(id).is_err());
        }
        let recovered = list().unwrap();
        assert_eq!(recovered["rows"][0]["state"], "failed");
        assert_eq!(recovered["rows"][0]["key"], "original-target");
        remove(id).unwrap();
        assert_eq!(list().unwrap()["rows"].as_array().unwrap().len(), 0);
        assert_eq!(
            fs::read(scope.root.join("预算 12000.xlsx")).unwrap(),
            b"public fixture"
        );
    }
    #[test]
    fn corrupted_pending_receipt_is_not_replaced() {
        let scope = Scope::new();
        let file = scope.root.join("public.txt");
        fs::write(&file, b"public").unwrap();
        receive(vec![file.clone()], &scope.root).unwrap();
        let mut value: serde_json::Value =
            serde_json::from_slice(&fs::read(root_path()).unwrap()).unwrap();
        value["sha256"] = "0".repeat(64).into();
        let damaged = serde_json::to_vec(&value).unwrap();
        fs::write(root_path(), &damaged).unwrap();
        assert!(list().is_err());
        assert!(receive(vec![file], &scope.root).is_err());
        assert_eq!(fs::read(root_path()).unwrap(), damaged);
    }
    #[test]
    fn incoming_media_document_image_retries_preserve_originals_and_existing_content() {
        let scope = Scope::new();
        super::super::session_store::save(&super::super::persistence::state_file_path(), &[])
            .unwrap();
        let audio = scope.root.join("公开接收.wav");
        let mut wav = denzic_host_audio_v1_core::wav::WavWriter::create(&audio).unwrap();
        wav.append_samples(&vec![500; 16000]).unwrap();
        wav.finalize().unwrap();
        drop(wav);
        let original = fs::read(&audio).unwrap();
        let document = scope.root.join("公开材料.txt");
        fs::write(&document, "补充材料，预算待确认；不是录音事实。").unwrap();
        receive(vec![audio.clone(), document.clone()], &scope.root).unwrap();
        let received = list().unwrap();
        let rows = received["rows"].as_array().unwrap();
        let audio_id = rows.iter().find(|r| r["kind"] == "media").unwrap()["id"]
            .as_str()
            .unwrap()
            .to_owned();
        let doc_id = rows.iter().find(|r| r["kind"] == "document").unwrap()["id"]
            .as_str()
            .unwrap()
            .to_owned();
        let token = super::super::audio_editing::context_token().unwrap();
        let coordinator = Arc::new(CompanionCoordinator::new_fixture());
        assert!(import(Arc::clone(&coordinator), &doc_id, None, &token).is_err());
        let result = import(Arc::clone(&coordinator), &audio_id, None, &token).unwrap();
        let key = result["rows"]
            .as_array()
            .unwrap()
            .iter()
            .find(|r| r["id"] == audio_id)
            .unwrap()["key"]
            .as_str()
            .unwrap()
            .to_owned();
        let snapshot = coordinator.snapshot().unwrap();
        assert_eq!(snapshot.host.sessions.len(), 1);
        let row = &snapshot.host.sessions[0];
        assert_eq!(row.id, key);
        assert!(row.transcript_text.is_empty());
        assert!(row.minutes.is_none());
        assert_eq!(
            fs::read(
                super::super::import_audio::verify_original(
                    row,
                    &scope.root.join("recordings").canonicalize().unwrap()
                )
                .unwrap()
            )
            .unwrap(),
            original
        );
        // Emulate a lost completion reply with an unavailable source. The committed
        // private row identity must be verified, never imported as another recording.
        {
            let mut store = Store::open().unwrap();
            let mut entry = store.entry(&audio_id).unwrap().clone();
            entry.state = "failed".into();
            store.set(entry).unwrap();
        }
        fs::rename(&audio, scope.root.join("source-moved.wav")).unwrap();
        import(Arc::clone(&coordinator), &audio_id, None, &token).unwrap();
        assert_eq!(coordinator.snapshot().unwrap().host.sessions.len(), 1);
        import(Arc::clone(&coordinator), &doc_id, Some(&key), &token).unwrap();
        let snapshot = coordinator.snapshot().unwrap();
        let row = &snapshot.host.sessions[0];
        assert_eq!(row.document_context.rows.len(), 1);
        let doc_bytes = fs::read(
            super::super::document_context::original(row, &doc_id, row.document_context.revision)
                .unwrap(),
        )
        .unwrap();
        assert_eq!(doc_bytes, fs::read(&document).unwrap());
        {
            let mut store = Store::open().unwrap();
            let mut entry = store.entry(&doc_id).unwrap().clone();
            entry.state = "failed".into();
            store.set(entry).unwrap();
        }
        fs::rename(&document, scope.root.join("document-moved.txt")).unwrap();
        import(Arc::clone(&coordinator), &doc_id, Some(&key), &token).unwrap();
        assert_eq!(
            coordinator.snapshot().unwrap().host.sessions[0]
                .document_context
                .rows
                .len(),
            1
        );
        assert!(
            import(
                Arc::clone(&coordinator),
                &doc_id,
                Some("another-meeting"),
                &token
            )
            .is_err(),
            "a stale presentation must not silently change or reinterpret the confirmed meeting"
        );
        let picture = scope.root.join("公开白板.png");
        image::RgbImage::from_pixel(16, 12, image::Rgb([25, 40, 60]))
            .save(&picture)
            .unwrap();
        let picture_bytes = fs::read(&picture).unwrap();
        receive(vec![picture], &scope.root).unwrap();
        let id = Store::open()
            .unwrap()
            .rows
            .iter()
            .find(|r| r.kind == "image")
            .unwrap()
            .id
            .clone();
        import(Arc::clone(&coordinator), &id, Some(&key), &token).unwrap();
        let snapshot = coordinator.snapshot().unwrap();
        let row = &snapshot.host.sessions[0];
        assert_eq!(row.meeting_notes.len(), 1);
        assert_eq!(
            fs::read(super::super::meeting_note_images::original(row, &id).unwrap()).unwrap(),
            picture_bytes
        );
        let notes = serde_json::to_vec(&row.meeting_notes).unwrap();
        import(Arc::clone(&coordinator), &id, Some(&key), &token).unwrap();
        let snapshot = coordinator.snapshot().unwrap();
        assert_eq!(
            serde_json::to_vec(&snapshot.host.sessions[0].meeting_notes).unwrap(),
            notes
        );
        assert!(snapshot.host.sessions[0].transcript_text.is_empty());
        let bad = scope.root.join("坏文件.wav");
        fs::write(&bad, b"not audio").unwrap();
        receive(vec![bad], &scope.root).unwrap();
        let bad_id = Store::open()
            .unwrap()
            .rows
            .iter()
            .find(|r| r.name == "坏文件.wav")
            .unwrap()
            .id
            .clone();
        assert!(import(Arc::clone(&coordinator), &bad_id, None, &token).is_err());
        assert_eq!(coordinator.snapshot().unwrap().host.sessions.len(), 1);
        remove(&doc_id).unwrap();
        remove(&id).unwrap();
        remove(&audio_id).unwrap();
        let row = &coordinator.snapshot().unwrap().host.sessions[0];
        assert_eq!(
            fs::read(
                super::super::document_context::original(
                    row,
                    &doc_id,
                    row.document_context.revision
                )
                .unwrap()
            )
            .unwrap(),
            doc_bytes
        );
        assert_eq!(
            fs::read(super::super::meeting_note_images::original(row, &id).unwrap()).unwrap(),
            picture_bytes
        );
        assert_eq!(
            fs::read(
                super::super::import_audio::verify_original(
                    row,
                    &scope.root.join("recordings").canonicalize().unwrap()
                )
                .unwrap()
            )
            .unwrap(),
            original
        );
    }
}
