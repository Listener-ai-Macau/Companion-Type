//! Bounded product diagnostics. Only typed metadata enters the journal: never
//! transcripts, credentials, URLs, raw errors, device addresses or audio paths.
//! The platform envelope is shared; Companion's 20+28-byte device log remains
//! a separate product protocol and is not decoded as the platform 10+24 format.
use std::{fs, io::{Read, Write}, path::{Path, PathBuf}, sync::{Mutex, OnceLock}, time::{Instant, SystemTime, UNIX_EPOCH}};
use denzic_observability_v1_core::{new_host_correlation_id, EventEnvelope, EventSource, Capability, CommandResult, ErrorCategory};
use serde::{Deserialize, Serialize};

const MAX_LOG_BYTES: u64 = 512 * 1024;
static JOURNAL: Mutex<()> = Mutex::new(());
static START: OnceLock<Instant> = OnceLock::new();
static WRITE_FAILED: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);

#[derive(Clone, Copy, Debug, Serialize, Deserialize)]
#[serde(rename_all="camelCase")]
pub enum Operation { DeviceControl, Reconnect, RecordingSync, BoardRecording, HostRecordingStart, HostRecordingStop, Transcription, Minutes, AudioDecode, SpeakerEmbedding, OtaValidate, OtaTransfer, DeviceLogPull }
impl Operation {
    fn capability(self) -> Capability {
        match self {
            Self::DeviceControl | Self::Reconnect | Self::DeviceLogPull => Capability::Ble,
            Self::OtaValidate | Self::OtaTransfer => Capability::Ota,
            _ => Capability::Audio,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all="camelCase")]
pub struct Record { pub operation: Operation, pub unix_ms: u64, pub event: EventEnvelope }

fn log_path() -> PathBuf { super::persistence::state_file_path().with_file_name("diagnostics.jsonl") }
fn previous(path: &Path) -> PathBuf { path.with_extension("previous.jsonl") }
fn append(path: &Path, record: &Record) -> Result<(), String> {
    let bytes = serde_json::to_vec(record).map_err(|_| "encode diagnostics")?;
    if let Some(parent) = path.parent() { fs::create_dir_all(parent).map_err(|_| "create diagnostics directory")?; }
    if fs::metadata(path).map(|m| m.len()).unwrap_or(0) + bytes.len() as u64 + 1 > MAX_LOG_BYTES {
        let old = previous(path);
        if old.exists() { fs::remove_file(&old).map_err(|_| "rotate diagnostics")?; }
        fs::rename(path, old).map_err(|_| "rotate diagnostics")?;
    }
    let mut file = fs::OpenOptions::new().create(true).append(true).open(path).map_err(|_| "open diagnostics")?;
    file.write_all(&bytes).and_then(|_| file.write_all(b"\n")).and_then(|_| file.flush()).map_err(|_| "write diagnostics".into())
}
fn record(operation: Operation, correlation: u64, sequence: u32, result: CommandResult, category: ErrorCategory, elapsed: u32) {
    let mut event = EventEnvelope::new(correlation, sequence, START.get_or_init(Instant::now).elapsed().as_millis().min(u32::MAX as u128) as u32, EventSource::Type, operation.capability());
    event.command_result=result; event.error_category=category;
    event.timing_value_ms=elapsed;
    event.timing_metric=match operation { Operation::OtaTransfer => denzic_observability_v1_core::TimingMetric::OtaTransferMs, Operation::Reconnect => denzic_observability_v1_core::TimingMetric::BleRecoveryMs, Operation::Transcription => denzic_observability_v1_core::TimingMetric::FinalTranscriptionMs, _ => denzic_observability_v1_core::TimingMetric::None };
    if cfg!(test) { return; } // Unit tests never touch the owner's journal.
    let value=Record { operation, unix_ms:SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_millis().min(u64::MAX as u128) as u64, event };
    if let Ok(_guard)=JOURNAL.lock() {
        if append(&log_path(), &value).is_err() { WRITE_FAILED.store(true, std::sync::atomic::Ordering::Relaxed); }
    }
}

pub struct Span { operation: Operation, id: u64, start: Instant, finished: bool }
impl Span {
    pub fn start(operation: Operation) -> Self {
        let value=Self { operation, id:new_host_correlation_id(), start:Instant::now(), finished:false };
        record(operation,value.id,1,CommandResult::Started,ErrorCategory::None,0); value
    }
    pub fn finish(mut self, error: Option<&str>) {
        let (result, category)=error.map(classify_error).unwrap_or((CommandResult::Succeeded,ErrorCategory::None));
        record(self.operation,self.id,2,result,category,self.start.elapsed().as_millis().min(u32::MAX as u128) as u32);
        self.finished=true;
    }
    pub fn result<T>(self, result: Result<T,String>) -> Result<T,String> { self.finish(result.as_ref().err().map(String::as_str)); result }
}
impl Drop for Span { fn drop(&mut self) { if !self.finished { record(self.operation,self.id,2,CommandResult::Failed,ErrorCategory::Host,self.start.elapsed().as_millis().min(u32::MAX as u128) as u32); } } }
fn classify_error(error: &str) -> (CommandResult, ErrorCategory) {
    // Classify in memory, never retain arbitrary provider/OS text.
    let e=error.to_ascii_lowercase();
    if e.contains("timeout") || e.contains("timed out") { (CommandResult::Timeout,ErrorCategory::Transport) }
    else if e.contains("credential") || e.contains("unauthorized") || e.contains("provider") || e.contains("api key") { (CommandResult::Failed,ErrorCategory::Provider) }
    else if e.contains("crc") || e.contains("schema") || e.contains("sha256") || e.contains("packet") { (CommandResult::Failed,ErrorCategory::Protocol) }
    else if e.contains("bluetooth") || e.contains("gatt") || e.contains("disconnect") { (CommandResult::Failed,ErrorCategory::Transport) }
    else if e.contains("network") || e.contains("http") { (CommandResult::Failed,ErrorCategory::Network) }
    else if e.contains("storage") || e.contains("space") || e.contains("busy") { (CommandResult::Failed,ErrorCategory::Resource) }
    else { (CommandResult::Failed,ErrorCategory::Host) }
}

#[derive(Serialize)]
#[serde(rename_all="camelCase")]
pub struct HostJournal { pub events: Vec<Record>, pub unreadable_lines: usize, pub write_failed: bool }
fn read_journal(path: &Path) -> HostJournal {
    let mut output=HostJournal { events:Vec::new(), unreadable_lines:0, write_failed:WRITE_FAILED.load(std::sync::atomic::Ordering::Relaxed) };
    for file in [previous(path),path.to_path_buf()] {
        let mut bytes=Vec::new();
        match fs::File::open(file) {
            Ok(file) => { if file.take(MAX_LOG_BYTES+1).read_to_end(&mut bytes).is_err() { output.unreadable_lines+=1; continue; } },
            Err(e) if e.kind()==std::io::ErrorKind::NotFound => continue,
            Err(_) => { output.unreadable_lines+=1; continue; }
        }
        if bytes.len() as u64 > MAX_LOG_BYTES { output.unreadable_lines+=1; continue; }
        for line in bytes.split(|b| *b==b'\n').filter(|s| !s.is_empty()) {
            match serde_json::from_slice::<Record>(line) { Ok(record)=>output.events.push(record),Err(_)=>output.unreadable_lines+=1 }
        }
    }
    output
}
pub fn host_journal() -> HostJournal { let _guard=JOURNAL.lock().ok(); read_journal(&log_path()) }

pub(crate) fn report(snapshot:&crate::companion_v1::CompanionV1Snapshot, device:Option<DeviceLogPage>, requested:bool) -> serde_json::Value {
    serde_json::json!({
        "schema":"companion.diagnostics.v1", "typeVersion":env!("CARGO_PKG_VERSION"),
        "capturedAtUnixMs":SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_millis() as u64,
        "privacy":"Metadata only; no credentials, transcript, meeting title, raw audio or service URLs.",
        "host":host_journal(),
        "deviceLogStatus":if device.is_some() {"captured_tail"} else if requested {"unavailable"} else {"not_requested"}, "deviceLog":device,
        "deviceLogScope":"Most recent up to 8 retained RAM events; reset clears device history; not a complete recording or acceptance trace.",
        "cachedDevice":{"connected":snapshot.device.connected,"recording":snapshot.device.recording,"firmwareVersion":snapshot.device.firmware_version,"uiGeneration":snapshot.device.ui_generation},
        "audio":{"codec":"Opus16/COP1","sampleRateHz":16000,"cop1Decoder":"bundled-libopus-1.5.2","speakerModelFilesPresent":super::speaker_model_files_present(),"speakerModelRuntimeLoaded":super::diarization::runtime_loaded()},
        "boardAcceptance":"NOT_RUN_BY_DIAGNOSTICS"
    })
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all="camelCase")]
pub struct DeviceEvent { pub sequence:u32, pub uptime_ms:u32, pub source:u8, pub event_id:u8, pub severity:u8, pub flags:u8, pub args:[u32;4] }
#[derive(Clone, Debug, Serialize)]
#[serde(rename_all="camelCase")]
pub struct DeviceLogPage { pub flags:u8, pub request_cursor:u32, pub next_cursor:u32, pub total_available:u16, pub events:Vec<DeviceEvent> }
pub fn decode_device_page(bytes:&[u8], cursor:u32) -> Result<DeviceLogPage,String> {
    let bad=|| "Companion diagnostic packet schema/length/cursor/CRC mismatch".to_string();
    if bytes.len()<20 || bytes[0]!=1 { return Err(bad()); }
    let u16at=|n|u16::from_le_bytes(bytes[n..n+2].try_into().unwrap());
    let u32at=|n|u32::from_le_bytes(bytes[n..n+4].try_into().unwrap());
    let count=u16at(2) as usize; let next=u32at(8);
    if bytes[1]&0x80!=0 {
        if bytes.len()!=20 || count!=0 || u16at(14)!=0 || u32at(16)!=0 || u32at(4)!=cursor || next!=cursor { return Err(bad()); }
        return Err(if bytes[1]&8!=0 { "设备忙于录音、传输或升级，请结束后再读取日志".into() } else { "设备拒绝了诊断请求；请检查固件协议版本".into() });
    }
    if bytes[1]&!0x07!=0 || count>8 || bytes.len()!=20+count*28 || u16at(14) as usize!=count*28 || u32at(4)!=cursor || crc32fast::hash(&bytes[20..])!=u32at(16) { return Err(bad()); }
    let mut events=Vec::with_capacity(count);
    let mut last=cursor;
    for item in bytes[20..].chunks_exact(28) {
        let word=|n| u32::from_le_bytes(item[n..n+4].try_into().unwrap());
        let sequence=word(0);
        if sequence==0 || (last!=0 && sequence.wrapping_sub(last) as i32<=0) { return Err(bad()); }
        last=sequence;
        events.push(DeviceEvent { sequence,uptime_ms:word(4),source:item[8],event_id:item[9],severity:item[10],flags:item[11],args:[word(12),word(16),word(20),word(24)] });
    }
    if (count>0 && next!=last) || (count==0 && (next!=cursor || bytes[1]&4==0)) { return Err(bad()); }
    Ok(DeviceLogPage {flags:bytes[1],request_cursor:cursor,next_cursor:next,total_available:u16at(12),events})
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn rejects_corruption_wrong_product_format_and_stale_cursor() {
        let mut packet=vec![0u8;48]; packet[0]=1; packet[2]=1; packet[8..12].copy_from_slice(&12u32.to_le_bytes()); packet[12]=1; packet[14]=28; packet[20..24].copy_from_slice(&12u32.to_le_bytes());
        let crc=crc32fast::hash(&packet[20..]); packet[16..20].copy_from_slice(&crc.to_le_bytes());
        assert_eq!(decode_device_page(&packet,0).unwrap().events[0].sequence,12);
        assert!(decode_device_page(&packet,11).is_err());
        packet[30]^=1; assert!(decode_device_page(&packet,0).is_err());
        assert!(decode_device_page(&[0;34],0).is_err());
    }
    #[test] fn journal_rotates_and_does_not_export_malformed_or_unknown_fields() {
        let dir=std::env::temp_dir().join(format!("companion-diagnostics-{}",uuid::Uuid::new_v4())); fs::create_dir_all(&dir).unwrap(); let path=dir.join("log.jsonl");
        fs::write(&path,vec![b'x';MAX_LOG_BYTES as usize]).unwrap();
        let record=Record { operation:Operation::OtaTransfer,unix_ms:1,event:EventEnvelope::new(5,1,0,EventSource::Type,Capability::Ota) };
        append(&path,&record).unwrap();
        let out=read_journal(&path); assert_eq!(out.events.len(),1); assert_eq!(out.unreadable_lines,1);
        let text=serde_json::to_string(&out).unwrap(); assert!(!text.contains("xxxx"));
        assert_eq!(classify_error("unauthorized secret=PRIVATE_TOKEN").1,ErrorCategory::Provider);
        fs::remove_dir_all(dir).unwrap();
    }
}
