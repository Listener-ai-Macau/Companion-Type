//! A pause belongs to one native sealed-recording sync, independent of the
//! backend's busy workflow lock. It never stops a microphone or deletes audio.
use std::collections::HashSet;
use std::sync::{atomic::{AtomicBool, AtomicU32, AtomicU8, Ordering}, Arc, Mutex, Weak};
use serde::Serialize;
use tokio::sync::Notify;
mod preference;

pub(crate) const PAUSED: &str = "录音同步已暂停；未收齐的设备录音和接收断点保留，点击同步录音可继续。";

#[derive(Default)]
struct Store {
    active: Option<Weak<Job>>,
    paused_devices: HashSet<String>,
    last_paused_device: Option<String>,
    preference_path: Option<std::path::PathBuf>,
    storage_error: Option<String>,
    // An explicit user action may receive one named device even when only
    // the pause-choice file is unreadable. Automatic sync remains disabled.
    manual_recovery_devices: HashSet<String>,
}
static STORE: std::sync::LazyLock<Mutex<Store>> = std::sync::LazyLock::new(|| Mutex::new(preference::load_product()));
static OBSERVER: std::sync::OnceLock<Box<dyn Fn(Status) + Send + Sync>> = std::sync::OnceLock::new();
static BACKGROUND_YIELD: AtomicBool = AtomicBool::new(false);

// The coordinator resets this before acquiring its background lease. A user
// command can request handoff even before the first BLE await creates a Job.
pub(crate) fn prepare_background() { BACKGROUND_YIELD.store(false, Ordering::Release); }
pub(crate) fn yield_background() {
    BACKGROUND_YIELD.store(true, Ordering::Release);
    let job = STORE.lock().ok().and_then(|s| s.active.as_ref().and_then(Weak::upgrade));
    if let Some(job) = job.filter(|j| j.background) { job.signal.notify_one(); }
}

/// Quit interrupts the in-process transfer only. Do not save the user's sync
/// preference, ACK an incomplete segment, or send any microphone control.
pub(crate) fn request_process_shutdown() {
    BACKGROUND_YIELD.store(true,Ordering::Release);
    let job=STORE.lock().ok().and_then(|s|s.active.as_ref().and_then(Weak::upgrade));
    if let Some(job)=job {job.request_pause();}
}

pub(crate) fn bind_app(app: tauri::AppHandle) {
    use tauri::Emitter;
    let _ = OBSERVER.set(Box::new(move |status| { let _ = app.emit("companion-recording-sync", status); }));
}
fn emit_status() {
    if let Some(observer) = OBSERVER.get() {
        if let Ok(status) = status() { observer(status); }
    }
}

fn key(device: &str) -> String { device.replace([':', '-'], "").to_ascii_lowercase() }

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct Status {
    pub job_id: Option<String>,
    pub device_id: Option<String>,
    pub phase: &'static str,
    pub recording_id: u32,
    pub received_bytes: u32,
    pub total_bytes: u32,
    pub pause_requested: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

pub(crate) struct Job {
    id: String,
    device: String,
    paused: AtomicBool,
    signal: Notify,
    phase: AtomicU8,
    recording: AtomicU32,
    received: AtomicU32,
    total: AtomicU32,
    background: bool,
}

impl Job {
    #[cfg(test)]
    fn create(device: &str) -> Arc<Self> { Self::create_kind(device, false) }
    fn create_kind(device: &str, background: bool) -> Arc<Self> {
        Arc::new(Self {
            id: uuid::Uuid::new_v4().to_string(), device: device.into(),
            paused: AtomicBool::new(false), signal: Notify::new(),
            phase: AtomicU8::new(0), recording: AtomicU32::new(0),
            received: AtomicU32::new(0), total: AtomicU32::new(0),
            background,
        })
    }
    pub fn begin(device: &str) -> Result<Arc<Self>, String> {
        Self::begin_kind(device, false)
    }
    pub fn begin_background(device: &str) -> Result<Arc<Self>, String> {
        Self::begin_kind(device, true)
    }
    fn begin_kind(device: &str, background: bool) -> Result<Arc<Self>, String> {
        if super::lifecycle::PROCESS.requested() {return Err(super::lifecycle::CLOSING.into());}
        let mut store = STORE.lock().map_err(|_| "同步暂停状态暂时不可用")?;
        let active = store.active.as_ref().and_then(Weak::upgrade);
        if active.is_some() {
            drop(store);
            drop(active);
            return Err("已有设备录音正在同步，请先完成或暂停。".into());
        }
        admit_job(&mut store, device, background)?;
        let job = Self::create_kind(device, background);
        store.active = Some(Arc::downgrade(&job));
        drop(store);
        emit_status();
        Ok(job)
    }
    pub fn recording(&self, id: u32, total: u32) {
        self.recording.store(id, Ordering::Release);
        self.received.store(0, Ordering::Release);
        self.total.store(total, Ordering::Release);
        self.phase.store(0, Ordering::Release);
        emit_status();
    }
    pub fn received(&self, bytes: u32) {
        let previous = self.received.swap(bytes, Ordering::AcqRel);
        // One UI event per checkpoint-sized progress span, not per BLE packet.
        if previous / 65_536 != bytes / 65_536 || bytes == self.total.load(Ordering::Acquire) { emit_status(); }
    }
    pub fn saving(&self) { self.phase.store(1, Ordering::Release); emit_status(); }
    pub fn reclaiming(&self) { self.phase.store(2, Ordering::Release); emit_status(); }
    pub fn yielded(&self) -> bool { self.background && BACKGROUND_YIELD.load(Ordering::Acquire) }
    pub fn is_paused(&self) -> bool { self.paused.load(Ordering::Acquire) || self.yielded() }
    pub async fn until_paused(&self) {
        loop {
            let notified = self.signal.notified();
            if self.is_paused() { return; }
            // notify_one retains a permit when the request preceded this wait.
            notified.await;
        }
    }
    pub async fn receive<T>(&self, work: impl std::future::Future<Output = Result<T, String>>) -> Result<T, String> {
        tokio::select! {
            biased;
            _ = self.until_paused() => Err(PAUSED.into()),
            result = work => result,
        }
    }
    fn request_pause(&self) {
        self.paused.store(true, Ordering::Release);
        self.signal.notify_one();
    }
    fn status(&self) -> Status {
        Status {
            job_id: Some(self.id.clone()), device_id: Some(self.device.clone()),
            phase: match self.phase.load(Ordering::Acquire) { 1 => "saving", 2 => "reclaiming", _ => "receiving" },
            recording_id: self.recording.load(Ordering::Acquire),
            received_bytes: self.received.load(Ordering::Acquire), total_bytes: self.total.load(Ordering::Acquire),
            pause_requested: self.paused.load(Ordering::Acquire),
            error: None,
        }
    }
}

fn admit_job(store: &mut Store, device: &str, background: bool) -> Result<(), String> {
    if let Some(error) = &store.storage_error {
        if !background && store.manual_recovery_devices.remove(&key(device)) { return Ok(()); }
        return Err(error.clone());
    }
    if store.paused_devices.contains(&key(device)) { return Err(PAUSED.into()); }
    Ok(())
}

impl Drop for Job {
    fn drop(&mut self) { emit_status(); }
}

pub(crate) fn status() -> Result<Status, String> {
    // Do not drop the last upgraded Arc while holding STORE: Job's final
    // notification obtains the current status, including any newer job.
    let (job, last_paused, storage_error) = {
        let store = STORE.lock().map_err(|_| "同步暂停状态暂时不可用")?;
        (store.active.as_ref().and_then(Weak::upgrade), store.last_paused_device.clone(), store.storage_error.clone())
    };
    if let Some(job) = job { let mut status=job.status();status.error=storage_error;return Ok(status); }
    Ok(Status {
        job_id: None, device_id: last_paused.clone(),
        phase: if storage_error.is_some() { "blocked" } else if last_paused.is_some() { "paused" } else { "idle" },
        recording_id: 0, received_bytes: 0, total_bytes: 0, pause_requested: false,
        error: storage_error,
    })
}

pub(crate) fn pause(job_id: &str) -> Result<bool, String> {
    let mut store = STORE.lock().map_err(|_| "同步暂停状态暂时不可用")?;
    let Some(job) = store.active.as_ref().and_then(Weak::upgrade) else { return Ok(false); };
    // A delayed IPC/button click must not pause a different, newer operation.
    if job.id != job_id { drop(store); return Ok(false); }
    store.paused_devices.insert(key(&job.device));
    store.last_paused_device = Some(job.device.clone());
    // Stop the current job even if local storage is unavailable, but never
    // report that a pause survives restart unless the durable write succeeded.
    let saved = preference::save(&store);
    if let Err(error) = &saved { store.storage_error=Some(error.clone()); }
    drop(store);
    job.request_pause();
    emit_status();
    saved.map(|_|true)
}

pub(crate) fn automatic_allowed(device: &str) -> bool {
    // An isolated recording operation already suppresses automatic recovery.
    // Connect must respect the same switch instead of consuming unrelated
    // sealed recordings before the explicit START/STOP path even begins.
    let disabled = std::env::var("COMPANION_TYPE_DISABLE_AUTO_RECOVERY").as_deref() == Ok("1");
    STORE.lock().map(|s| automatic_allowed_for(&s, device, disabled)).unwrap_or(false)
}

// Explicitly following an owned open recording is distinct from recovering
// unrelated sealed backlog. It still cannot undo the user's sync pause.
pub(crate) fn owned_follow_allowed(device: &str) -> bool {
    STORE.lock().map(|s| owned_follow_allowed_for(&s, device)).unwrap_or(false)
}

fn owned_follow_allowed_for(store: &Store, device: &str) -> bool {
    store.storage_error.is_none() && !store.paused_devices.contains(&key(device))
}

fn automatic_allowed_for(store: &Store, device: &str, disabled: bool) -> bool {
    !disabled && owned_follow_allowed_for(store, device)
}

pub(crate) fn resume_explicit(device: Option<&str>) -> Result<(),String> {
    let mut store = STORE.lock().map_err(|_| "同步暂停状态暂时不可用")?;
    preference::resume(&mut store,device)?;
    drop(store);
    emit_status();
    Ok(())
}

#[cfg(test)]
#[path = "recording_sync/restart_tests.rs"]
mod restart_tests;

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn isolated_capture_blocks_connect_backlog_without_changing_device_pause() {
        let mut store = Store::default();
        store.paused_devices.insert(key("AA:BB:CC:DD:EE:01"));
        for device in ["aabbccddee01", "AA:BB:CC:DD:EE:02"] {
            assert!(!automatic_allowed_for(&store, device, true));
        }
        assert!(!automatic_allowed_for(&store, "aabbccddee01", false));
        assert!(automatic_allowed_for(&store, "AA:BB:CC:DD:EE:02", false));
        assert!(!owned_follow_allowed_for(&store, "aabbccddee01"), "an explicit original never resumes user-paused sync");
        assert!(owned_follow_allowed_for(&store, "AA:BB:CC:DD:EE:02"), "isolated connect backlog need not block an exact owned original");
        assert_eq!(store.paused_devices.len(), 1);
    }
    #[test]
    fn pause_is_job_bound_and_blocks_automatic_restart_until_explicit_resume() {
        let job = Job::begin("AA:BB:CC:DD:EE:01").unwrap();
        assert!(Job::begin("AA:BB:CC:DD:EE:02").is_err());
        assert!(!pause("an-old-job").unwrap());
        assert!(!job.is_paused());
        job.recording(7, 100_000);
        job.received(65_632);
        assert!(pause(&job.id).unwrap());
        assert!(pause(&job.id).unwrap());
        assert!(job.is_paused());
        let report = status().unwrap();
        assert_eq!(report.received_bytes, 65_632);
        assert_eq!(report.total_bytes, 100_000);
        assert!(report.pause_requested);
        assert!(!automatic_allowed("aabbccddee01"));
        assert!(automatic_allowed("AA:BB:CC:DD:EE:02"));
        let old_id = job.id.clone();
        drop(job);
        assert_eq!(status().unwrap().phase, "paused");
        assert!(Job::begin("AA:BB:CC:DD:EE:01").is_err());
        resume_explicit(Some("aabbccddee01")).unwrap();
        let next = Job::begin("AA:BB:CC:DD:EE:01").unwrap();
        assert!(!pause(&old_id).unwrap());
        assert!(!next.is_paused());
        next.saving();
        assert_eq!(status().unwrap().phase, "saving");
        next.reclaiming();
        assert_eq!(status().unwrap().phase, "reclaiming");
        drop(next);
        assert_eq!(status().unwrap().phase, "idle");
    }
    #[tokio::test]
    async fn pause_wakes_a_pending_receiver_and_handles_request_before_wait() {
        let job = Job::create("test-only");
        let waiter = job.clone();
        let task = tokio::spawn(async move { waiter.until_paused().await; });
        tokio::task::yield_now().await;
        job.request_pause();
        tokio::time::timeout(std::time::Duration::from_secs(1), task).await.unwrap().unwrap();
        tokio::time::timeout(std::time::Duration::from_secs(1), job.until_paused()).await.unwrap();
    }
    #[tokio::test]
    async fn paused_receive_drops_work_and_preserves_its_real_durable_cursor() {
        use super::super::recording_transfer::{Cursor, Source};
        use sha2::{Digest, Sha256};
        let root = std::env::temp_dir().join(format!("companion-sync-pause-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir(&root).unwrap();
        let body: Vec<u8> = (0..180_000).map(|n| (n % 239) as u8).collect();
        let digest = Sha256::digest(&body);
        let mut prefix = [0; 8];
        prefix.copy_from_slice(&digest[..8]);
        let source = Source { device: "pause-fixture".into(), recording_id: 7,
            codec: 3, source_mode: 1, duration_ms: 90_000, total_length: body.len() as u32,
            sha256_prefix: prefix, content_crc32: crc32fast::hash(&body) };
        let (ready_tx, ready_rx) = tokio::sync::oneshot::channel();
        let task_root = root.clone();
        let task_source = source.clone();
        let task_body = body.clone();
        let job = Job::create("pause-fixture");
        let worker = job.clone();
        let task = tokio::spawn(async move {
            worker.receive(async move {
                let (mut cursor, _) = Cursor::open(&task_root, task_source)?;
                for chunk in task_body[..80_000].chunks(224) { cursor.append(chunk)?; }
                ready_tx.send(()).unwrap();
                std::future::pending::<()>().await;
                Ok(())
            }).await
        });
        ready_rx.await.unwrap();
        job.request_pause();
        let result = tokio::time::timeout(std::time::Duration::from_secs(2), task).await.unwrap().unwrap();
        assert_eq!(result.unwrap_err(), PAUSED);
        let (cursor, recovered) = Cursor::open(&root, source.clone()).unwrap();
        assert_eq!(recovered, body[..80_000]);
        drop(cursor);
        assert!(super::super::recording_transfer::release(&root, source).is_err());
    }
}
