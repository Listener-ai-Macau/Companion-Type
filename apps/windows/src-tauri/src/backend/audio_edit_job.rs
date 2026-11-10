//! One durable, bounded edit job. Each acknowledged output has a stable ID.
//! Cancellation is observed between atomic publications, including after commit.
use super::{audio_derivation as pcm, audio_editing as edit};
use crate::{
    companion_v1::CompanionV1HostSession,
    coordinator::{CompanionCoordinator, CompanionDeviceOperationLease},
};
use serde::{Deserialize, Serialize};
use std::{
    fs::{self, File, OpenOptions},
    path::PathBuf,
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex, OnceLock,
    },
};
#[derive(Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Output {
    key: String,
    name: String,
    plan: pcm::Plan,
    state: String,
    row: Option<CompanionV1HostSession>,
    sha: Option<String>,
    bytes: Option<u64>,
    sources: Vec<pcm::SourceIdentity>,
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Journal {
    schema: u8,
    id: String,
    library_token: String,
    outputs: Vec<Output>,
    state: String,
    message: String,
}
struct Manager {
    journal: Mutex<Option<Journal>>,
    running: AtomicBool,
    cancel: AtomicBool,
    progress: Mutex<(u64, u64)>,
}
static MANAGER: OnceLock<Arc<Manager>> = OnceLock::new();
fn manager() -> Arc<Manager> {
    MANAGER
        .get_or_init(|| {
            Arc::new(Manager {
                journal: Mutex::new(None),
                running: AtomicBool::new(false),
                cancel: AtomicBool::new(false),
                progress: Mutex::new((0, 0)),
            })
        })
        .clone()
}
fn path() -> PathBuf {
    super::persistence::state_file_path().with_extension("audio-edit-job.json")
}
fn job_lock() -> Result<File, String> {
    let path = path().with_extension("lock");
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let file = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .open(path)
        .map_err(|e| e.to_string())?;
    file.try_lock()
        .map_err(|_| "另一个窗口正在编辑录音，请等待该任务结束。")?;
    Ok(file)
}
fn native_key(value: &str) -> bool {
    value.strip_prefix("edit-").is_some_and(|s| {
        s.len() == 32
            && s.bytes()
                .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
    })
}
fn read() -> Result<Option<Journal>, String> {
    let path = path();
    if !path.exists() {
        return Ok(None);
    }
    let meta = fs::symlink_metadata(&path).map_err(|e| e.to_string())?;
    if !meta.is_file() || meta.file_type().is_symlink() || meta.len() > 4 * 1024 * 1024 {
        return Err("录音编辑任务记录无效；原音保留。".into());
    }
    let job: Journal = serde_json::from_reader(File::open(path).map_err(|e| e.to_string())?)
        .map_err(|_| "编辑任务记录无法读取；原音和成品保留。")?;
    if job.schema != 1
        || job.id.len() != 32
        || !job.id.bytes().all(|b| b.is_ascii_hexdigit())
        || job.outputs.is_empty()
        || job.outputs.len() > 32
        || job
            .outputs
            .iter()
            .any(|o| !native_key(&o.key) || o.name.is_empty() || o.name.len() > 1024)
    {
        return Err("编辑任务身份无效。".into());
    }
    let keys = job
        .outputs
        .iter()
        .map(|o| &o.key)
        .collect::<std::collections::BTreeSet<_>>();
    if keys.len() != job.outputs.len() {
        return Err("编辑任务含重复成品标识。".into());
    }
    for o in &job.outputs {
        if !o.sources.is_empty() {
            o.plan.validate(&o.sources)?;
        }
        if let Some(row) = &o.row {
            let root = super::audio_storage::recording_root()?;
            if row.id != o.key
                || row.source != "derivedAudio"
                || row.audio_path.as_deref()
                    != Some(
                        root.join(format!("{}.wav", o.key))
                            .to_string_lossy()
                            .as_ref(),
                    )
                || o.sha.as_ref().is_none_or(|s| s.len() != 64)
                || o.bytes != Some(o.plan.frames * 2 + 44)
            {
                return Err("已准备成品的身份无效，拒绝写入。".into());
            }
            let original = super::import_audio::original_chunk(row)?;
            if original.path.as_deref()
                != Some(
                    root.join(format!("{}.original.wav", o.key))
                        .to_string_lossy()
                        .as_ref(),
                )
            {
                return Err("成品原文件归属无效。".into());
            }
        }
    }
    Ok(Some(job))
}
fn persist(m: &Manager, job: &Journal) -> Result<(), String> {
    let data = serde_json::to_vec(job).map_err(|e| e.to_string())?;
    super::export::write_atomic(&path(), &data)?;
    *m.journal.lock().map_err(|_| "编辑队列暂不可用。")? = Some(job.clone());
    Ok(())
}
fn view(m: &Manager, job: Option<Journal>, other_running: bool) -> serde_json::Value {
    let running = m.running.load(Ordering::Acquire) || other_running;
    if let Some(job) = job {
        let completed = job.outputs.iter().filter(|o| o.state == "complete").count();
        let interrupted = !running && matches!(job.state.as_str(), "running" | "committing");
        let progress = m.progress.lock().map(|v| *v).unwrap_or_default();
        serde_json::json!({"operation":"derive","id":job.id,"running":running,
            "state":if interrupted{"interrupted"}else{job.state.as_str()},
            "message":if other_running{"另一个窗口正在整理，请在原窗口查看。"}else if interrupted{"上次处理被中断；已保存部分保留，可核对并重试剩余片段。"}else{&job.message},
            "processed":progress.0,"total":progress.1,"completed":completed,"totalOutputs":job.outputs.len(),
            "retryAvailable":!running&&completed<job.outputs.len()&&job.state!="dismissed",
            "outputs":job.outputs.iter().map(|o|serde_json::json!({"key":o.key,"name":o.name,"saved":o.state=="complete"})).collect::<Vec<_>>()})
    } else {
        serde_json::json!({"running":false,"state":"idle","operation":"derive"})
    }
}
pub fn status() -> Result<serde_json::Value, String> {
    let m = manager();
    let job = if m.running.load(Ordering::Acquire) {
        m.journal.lock().map_err(|_| "编辑队列暂不可用。")?.clone()
    } else {
        read()?
    };
    let other_running = !m.running.load(Ordering::Acquire) && job_lock().is_err();
    Ok(view(&m, job, other_running))
}
pub fn cancel(id: &str) -> Result<bool, String> {
    let m = manager();
    let guard = m.journal.lock().map_err(|_| "编辑队列暂不可用。")?;
    if m.running.load(Ordering::Acquire) && guard.as_ref().is_some_and(|j| j.id == id) {
        m.cancel.store(true, Ordering::Release);
        Ok(true)
    } else {
        Ok(false)
    }
}
pub fn start(
    coordinator: Arc<CompanionCoordinator>,
    request: edit::Request,
) -> Result<serde_json::Value, String> {
    if serde_json::to_vec(&request)
        .map_err(|e| e.to_string())?
        .len()
        > 256 * 1024
        || request.outputs.is_empty()
        || request.outputs.len() > 32
        || request.outputs.iter().any(|o| {
            o.name.trim().is_empty()
                || o.name.chars().count() > 256
                || o.name.chars().any(char::is_control)
        })
    {
        return Err("本次编辑请保存1至32份有效命名的录音。".into());
    }
    let m = manager();
    let mut guard = m.journal.lock().map_err(|_| "编辑队列暂不可用。")?;
    if m.running.load(Ordering::Acquire) {
        return Err("已有录音任务正在进行。".into());
    }
    let lock = job_lock()?;
    let lease = coordinator.begin_audio_edit()?;
    if request.library_token != edit::context_token()? {
        return Err("资料库已变化，请重新打开编辑。".into());
    }
    let previous = read()?;
    if previous
        .as_ref()
        .is_some_and(|j| j.outputs.iter().any(|o| o.state != "complete") && j.state != "dismissed")
    {
        return Err("上次编辑尚未收尾，请先核对或重试该任务。".into());
    }
    let job = Journal {
        schema: 1,
        id: uuid::Uuid::new_v4().simple().to_string(),
        library_token: request.library_token,
        outputs: request
            .outputs
            .into_iter()
            .map(|o| Output {
                key: format!("edit-{}", uuid::Uuid::new_v4().simple()),
                name: o.name.trim().into(),
                plan: o.plan,
                state: "pending".into(),
                row: None,
                sha: None,
                bytes: None,
                sources: vec![],
            })
            .collect(),
        state: "running".into(),
        message: "正在核对完整原音…".into(),
    };
    super::export::write_atomic(
        &path(),
        &serde_json::to_vec(&job).map_err(|e| e.to_string())?,
    )?;
    *guard = Some(job.clone());
    m.cancel.store(false, Ordering::Release);
    m.running.store(true, Ordering::Release);
    drop(guard);
    launch(m, coordinator, job, lease, lock)
}
pub fn dismiss(id: &str) -> Result<(), String> {
    let m = manager();
    if m.running.load(Ordering::Acquire) {
        return Err("请先停止当前整理。".into());
    }
    let _lock = job_lock()?;
    let mut job = read()?
        .filter(|j| j.id == id)
        .ok_or("找不到这项编辑任务。")?;
    let root = super::audio_storage::recording_root()?;
    let rows = super::persistence::load_sessions_from(&super::persistence::state_file_path())
        .ok_or("请先恢复资料库，再结束任务。")?;
    for output in &job.outputs {
        if output.state == "complete" || rows.iter().any(|r| r.id == output.key) {
            continue;
        }
        if let Some(row) = &output.row {
            let paths = vec![
                root.join(format!("{}.wav", row.id))
                    .to_string_lossy()
                    .into_owned(),
                root.join(format!("{}.original.wav", row.id))
                    .to_string_lossy()
                    .into_owned(),
                edit::owner_path(row, &root).to_string_lossy().into_owned(),
            ];
            super::audio_artifacts::erase(&root, &paths, &[])?;
        }
    }
    job.state = "dismissed".into();
    job.message = "已结束剩余处理；原音和已保存的成品保留。".into();
    for output in &mut job.outputs {
        if output.state != "complete" {
            output.state = "retired".into();
        }
    }
    persist(&m, &job)
}
pub fn retry(
    coordinator: Arc<CompanionCoordinator>,
    id: &str,
) -> Result<serde_json::Value, String> {
    let m = manager();
    let mut guard = m.journal.lock().map_err(|_| "编辑队列暂不可用。")?;
    if m.running.load(Ordering::Acquire) {
        return Err("已有录音任务正在进行。".into());
    }
    let lock = job_lock()?;
    let lease = coordinator.begin_audio_edit()?;
    let mut job = read()?
        .filter(|j| j.id == id && j.state != "dismissed")
        .ok_or("找不到这项编辑任务。")?;
    if job.library_token != edit::context_token()? {
        return Err("任务属于另一份资料库。".into());
    }
    job.state = "running".into();
    job.message = "正在核对原任务和已保存成品…".into();
    super::export::write_atomic(
        &path(),
        &serde_json::to_vec(&job).map_err(|e| e.to_string())?,
    )?;
    *guard = Some(job.clone());
    m.cancel.store(false, Ordering::Release);
    m.running.store(true, Ordering::Release);
    drop(guard);
    launch(m, coordinator, job, lease, lock)
}
fn launch(
    m: Arc<Manager>,
    coordinator: Arc<CompanionCoordinator>,
    mut job: Journal,
    lease: CompanionDeviceOperationLease,
    lock: File,
) -> Result<serde_json::Value, String> {
    let id = job.id.clone();
    let worker = m.clone();
    let spawn = std::thread::Builder::new()
        .name("companion-audio-edit".into())
        .spawn(move || {
            let _lease = lease;
            let _lock = lock;
            let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                execute(&worker, &coordinator, &mut job)
            }))
            .unwrap_or_else(|_| {
                Err("录音整理意外中断，原音和已保存部分保留，可重新核对任务。".into())
            });
            match result {
                Ok(()) => {
                    job.state = "complete".into();
                    job.message =
                        format!("已另存 {} 份录音，原音和原有内容保留。", job.outputs.len());
                }
                Err(error) => {
                    job.state = if worker.cancel.load(Ordering::Acquire) {
                        "cancelled"
                    } else {
                        "failed"
                    }
                    .into();
                    job.message = error;
                }
            }
            let _ = persist(&worker, &job);
            // Leases are dropped before a subsequent start can observe idle.
            drop(_lock);
            drop(_lease);
            worker.running.store(false, Ordering::Release);
        });
    if spawn.is_err() {
        m.running.store(false, Ordering::Release);
        return Err("编辑尚未启动，任务已保存，可稍后重试。".into());
    }
    Ok(serde_json::json!({"id":id,"started":true}))
}
struct Stage {
    path: PathBuf,
}
impl Stage {
    fn open(id: &str) -> Result<Self, String> {
        let root = super::audio_storage::recording_root()?
            .canonicalize()
            .map_err(|e| e.to_string())?;
        let path = root.join(format!(".audio-edit-{id}"));
        if path.exists() {
            let meta = fs::symlink_metadata(&path).map_err(|e| e.to_string())?;
            if !meta.is_dir() || meta.file_type().is_symlink() {
                return Err("编辑临时目录归属无效。".into());
            }
            // Only this journal's native UUID directory, never a source/backup.
            fs::remove_dir_all(&path).map_err(|e| e.to_string())?;
        }
        fs::create_dir(&path).map_err(|e| e.to_string())?;
        Ok(Self { path })
    }
}
impl Drop for Stage {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.path);
    }
}
fn check(m: &Manager) -> Result<(), String> {
    if m.cancel.load(Ordering::Acquire) {
        return Err("已取消剩余处理；已保存的成品和原音保留，可重试未完成片段。".into());
    }
    if super::lifecycle::PROCESS.requested() {
        return Err("应用正在关闭；已保存部分保留，重开后可重试剩余片段。".into());
    }
    Ok(())
}
fn execute(
    m: &Manager,
    coordinator: &CompanionCoordinator,
    job: &mut Journal,
) -> Result<(), String> {
    let stage = Stage::open(&job.id)?;
    // Reconcile already durable rows first. Their parent may since have been
    // purged; a saved child must not require that parent or be recreated.
    let snapshot = coordinator.snapshot()?;
    for output in &mut job.outputs {
        if output.state == "complete" {
            continue;
        }
        if let Some(saved) = snapshot.host.sessions.iter().find(|r| r.id == output.key) {
            if output.row.is_none()
                || saved.source != "derivedAudio"
                || edit::provenance(saved)?.as_ref()
                    != Some(&output.plan.provenance(&output.sources)?)
            {
                return Err("已保存成品的来源不符，拒绝覆盖。".into());
            }
            output.state = "complete".into();
        }
    }
    persist(m, job)?;
    // Validate all planned ranges before publishing any output.
    let snapshot = coordinator.snapshot()?;
    let keys = job
        .outputs
        .iter()
        .filter(|o| o.state != "complete")
        .flat_map(|o| o.plan.slices.iter().map(|s| s.source_key.clone()))
        .collect::<std::collections::BTreeSet<_>>()
        .into_iter()
        .collect::<Vec<_>>();
    if keys.is_empty() {
        return Ok(());
    }
    let resolved = edit::resolve(&snapshot, &keys)?;
    let identities = resolved.identities();
    for output in job.outputs.iter().filter(|o| o.state != "complete") {
        output.plan.validate(&identities)?;
    }
    for i in 0..job.outputs.len() {
        if job.outputs[i].state == "complete" {
            continue;
        }
        check(m)?;
        let saved = coordinator
            .snapshot()?
            .host
            .sessions
            .into_iter()
            .find(|r| r.id == job.outputs[i].key);
        if let Some(saved) = saved {
            let output = &job.outputs[i];
            if output.row.is_none()
                || saved.source != "derivedAudio"
                || edit::provenance(&saved)?.as_ref()
                    != Some(&output.plan.provenance(&output.sources)?)
            {
                return Err("该成品标识已存在但来源不同，拒绝覆盖。".into());
            }
            job.outputs[i].state = "complete".into();
            persist(m, job)?;
            continue;
        }
        let output = &job.outputs[i];
        let map = output.plan.provenance(&identities)?;
        let bytes = output
            .plan
            .frames
            .checked_mul(2)
            .and_then(|n| n.checked_add(44))
            .ok_or("成品过大。")?;
        if output.state == "filesPublished" {
            let row = output.row.as_ref().ok_or("成品任务记录缺失。")?;
            edit::verify_published(
                row,
                &map,
                bytes,
                output.sha.as_deref().ok_or("成品校验缺失。")?,
            )?;
        } else {
            job.state = "running".into();
            job.message = format!("正在生成第 {} / {} 份录音…", i + 1, job.outputs.len());
            persist(m, job)?;
            let rendered = pcm::render(
                &stage.path,
                &resolved.inputs,
                &job.outputs[i].plan,
                |done, total| {
                    check(m)?;
                    if let Ok(mut progress) = m.progress.lock() {
                        *progress = (done, total);
                    }
                    Ok(())
                },
            )?;
            check(m)?;
            if let Some(expected) = &job.outputs[i].sha {
                if expected != &rendered.sha256 {
                    return Err("重试结果与原任务内容不符，原音保留。".into());
                }
            }
            let row = edit::row(
                &coordinator.snapshot()?,
                &job.outputs[i].key,
                &job.outputs[i].name,
                rendered.frames,
                rendered.bytes,
                &rendered.sha256,
            )?;
            job.outputs[i].row = Some(row.clone());
            job.outputs[i].sha = Some(rendered.sha256.clone());
            job.outputs[i].bytes = Some(rendered.bytes);
            job.outputs[i].sources = map.sources.clone();
            job.outputs[i].state = "prepared".into();
            job.state = "committing".into();
            job.message = format!("正在确认第 {} 份；停止请求会在本份保存后生效。", i + 1);
            persist(m, job)?;
            edit::publish(
                &row,
                &map,
                &rendered.temporary,
                rendered.bytes,
                &rendered.sha256,
            )?;
            let _ = fs::remove_file(&rendered.temporary);
            job.outputs[i].state = "filesPublished".into();
            persist(m, job)?;
        }
        let output = &job.outputs[i];
        coordinator.commit_audio_edit(
            output.row.clone().ok_or("成品身份缺失。")?,
            &map.sources,
            &job.library_token,
        )?;
        job.outputs[i].state = "complete".into();
        persist(m, job)?;
    }
    Ok(())
}
