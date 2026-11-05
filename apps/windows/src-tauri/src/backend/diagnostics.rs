//! Bounded product diagnostics. Only typed metadata enters the journal: never
//! transcripts, credentials, URLs, raw errors, device addresses or audio paths.
//! The platform envelope is shared; Companion's 20+28-byte device log remains
//! a separate product protocol and is not decoded as the platform 10+24 format.
use std::{fs, io::{Read, Write}, path::{Path, PathBuf}, sync::{Mutex, OnceLock}, time::{Instant, SystemTime, UNIX_EPOCH}};
use denzic_observability_v1_core::{new_host_correlation_id, EventEnvelope, EventSource, Capability, CommandResult, ErrorCategory};
use serde::{Deserialize, Serialize};

mod identity;
pub use identity::RecordingScope;
use identity::{Trace,BuildIdentity};

const MAX_LOG_BYTES: u64 = 512 * 1024;
static JOURNAL: Mutex<()> = Mutex::new(());
static START: OnceLock<Instant> = OnceLock::new();
static WRITE_FAILED: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);

#[derive(Clone, Copy, Debug, Serialize, Deserialize)]
#[serde(rename_all="camelCase")]
pub enum Operation { DeviceControl, Reconnect, RecordingSync, BoardRecording, HostRecordingStart, HostRecordingStop, Transcription, Minutes, AudioDecode, SpeakerEmbedding, OtaValidate, OtaTransfer, DeviceLogPull, RecordingSaved, RecordingFragmentSaved, RecordingRestored }
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
pub struct Record {
    pub operation:Operation,pub unix_ms:u64,pub event:EventEnvelope,
    #[serde(default,skip_serializing_if="zero")]pub process_instance:u64,
    #[serde(default,skip_serializing_if="Option::is_none")]pub recording_trace:Option<u64>,
    #[serde(default,skip_serializing_if="false_value")]pub trace_unavailable:bool,
}
fn zero(value:&u64)->bool{*value==0}
fn false_value(value:&bool)->bool{!*value}
fn unix_ms()->u64{SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_millis().min(u64::MAX as u128)as u64}
#[cfg(test)]
thread_local!{static TEST_EVENTS:std::cell::RefCell<Option<Vec<Record>>>=const{std::cell::RefCell::new(None)};}
#[cfg(test)]
pub(super) fn capture_test_events<T>(work:impl FnOnce()->T)->(T,Vec<Record>){
    struct Restore(Option<Vec<Record>>);impl Drop for Restore{fn drop(&mut self){TEST_EVENTS.with(|s|{s.replace(self.0.take());});}}
    let _restore=Restore(TEST_EVENTS.with(|s|s.replace(Some(Vec::new()))));
    let result=work();let events=TEST_EVENTS.with(|s|s.replace(None)).unwrap_or_default();(result,events)
}
#[cfg(test)]
pub(crate) fn capture_with_test_trace<T>(work:impl FnOnce()->T)->(T,Vec<Record>){identity::with_test_seed([17;32],||capture_test_events(work))}

fn log_path() -> PathBuf { super::persistence::state_file_path().with_file_name("diagnostics.jsonl") }
fn previous(path: &Path) -> PathBuf { path.with_extension("previous.jsonl") }
fn append(path: &Path, record: &Record) -> Result<(), String> {
    let bytes = serde_json::to_vec(record).map_err(|_| "encode diagnostics")?;
    append_line(path,&bytes)
}
fn append_line(path:&Path,bytes:&[u8])->Result<(),String>{
    if let Some(parent) = path.parent() { fs::create_dir_all(parent).map_err(|_| "create diagnostics directory")?; }
    if fs::metadata(path).map(|m| m.len()).unwrap_or(0) + bytes.len() as u64 + 1 > MAX_LOG_BYTES {
        let old = previous(path);
        if old.exists() { fs::remove_file(&old).map_err(|_| "rotate diagnostics")?; }
        fs::rename(path, old).map_err(|_| "rotate diagnostics")?;
        if let Some(image)=identity::cached_build(){
            let line=serde_json::to_vec(image).map_err(|_|"encode image identity")?;
            let mut file=fs::OpenOptions::new().create(true).append(true).open(path).map_err(|_|"open diagnostics")?;
            file.write_all(&line).and_then(|_|file.write_all(b"\n")).and_then(|_|file.flush()).map_err(|_|"write diagnostics")?;
        }
    }
    let mut file = fs::OpenOptions::new().create(true).append(true).open(path).map_err(|_| "open diagnostics")?;
    file.write_all(&bytes).and_then(|_| file.write_all(b"\n")).and_then(|_| file.flush()).map_err(|_| "write diagnostics".into())
}
fn record(operation: Operation, correlation: u64, sequence: u32, result: CommandResult, category: ErrorCategory, elapsed: u32,trace:Trace) {
    let mut event = EventEnvelope::new(correlation, sequence, START.get_or_init(Instant::now).elapsed().as_millis().min(u32::MAX as u128) as u32, EventSource::Type, operation.capability());
    event.command_result=result; event.error_category=category;
    event.timing_value_ms=elapsed;
    event.timing_metric=match operation { Operation::OtaTransfer => denzic_observability_v1_core::TimingMetric::OtaTransferMs, Operation::Reconnect => denzic_observability_v1_core::TimingMetric::BleRecoveryMs, Operation::Transcription => denzic_observability_v1_core::TimingMetric::FinalTranscriptionMs, _ => denzic_observability_v1_core::TimingMetric::None };
    let value=Record {operation,unix_ms:unix_ms(),event,process_instance:identity::process_instance(),recording_trace:trace.recording,trace_unavailable:trace.unavailable};
    #[cfg(test)]
    {TEST_EVENTS.with(|s|{if let Some(events)=s.borrow_mut().as_mut(){events.push(value.clone());}});return;}
    #[cfg(not(test))]
    {
        identity::warm_build();
        if let Ok(_guard)=JOURNAL.lock() {
            if append(&log_path(), &value).is_err() { WRITE_FAILED.store(true, std::sync::atomic::Ordering::Relaxed); }
        }
    }
}

fn publish_build_identity(image:&BuildIdentity){
    if let Ok(_guard)=JOURNAL.lock(){
        if serde_json::to_vec(image).map_err(|_|()).and_then(|line|append_line(&log_path(),&line).map_err(|_|())).is_err(){WRITE_FAILED.store(true,std::sync::atomic::Ordering::Relaxed);}
    }
}
pub struct Span { operation: Operation, id: u64, start: Instant, finished: bool,trace:Trace }
impl Span {
    pub fn start(operation: Operation) -> Self {
        let value=Self { operation, id:new_host_correlation_id(), start:Instant::now(), finished:false,trace:identity::current_trace() };
        record(operation,value.id,1,CommandResult::Started,ErrorCategory::None,0,value.trace); value
    }
    pub fn bind_recording(&mut self,session:&str){let _scope=RecordingScope::enter(session);self.trace=identity::current_trace();}
    pub fn finish(mut self, error: Option<&str>) {
        let (result, category)=error.map(classify_error).unwrap_or((CommandResult::Succeeded,ErrorCategory::None));
        record(self.operation,self.id,2,result,category,self.start.elapsed().as_millis().min(u32::MAX as u128) as u32,self.trace);
        self.finished=true;
    }
    pub fn result<T>(self, result: Result<T,String>) -> Result<T,String> { self.finish(result.as_ref().err().map(String::as_str)); result }
}
impl Drop for Span { fn drop(&mut self) { if !self.finished { record(self.operation,self.id,2,CommandResult::Failed,ErrorCategory::Host,self.start.elapsed().as_millis().min(u32::MAX as u128) as u32,self.trace); } } }
pub(crate) fn recording_saved(session:&str,fragment:bool){
    let _scope=RecordingScope::enter(session);
    Span::start(if fragment{Operation::RecordingFragmentSaved}else{Operation::RecordingSaved}).finish(None);
}
pub(crate) fn recording_restored(session:&str){let _scope=RecordingScope::enter(session);Span::start(Operation::RecordingRestored).finish(None);}
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
pub struct HostJournal { pub events: Vec<Record>, pub unreadable_lines: usize, pub write_failed: bool, pub build_identities:Vec<BuildIdentity>,pub build_conflicts:usize }
fn read_journal(path: &Path) -> HostJournal {
    let mut output=HostJournal { events:Vec::new(), unreadable_lines:0, write_failed:WRITE_FAILED.load(std::sync::atomic::Ordering::Relaxed),build_identities:Vec::new(),build_conflicts:0 };
    let mut conflicted=std::collections::HashSet::new();
    for file in [previous(path),path.to_path_buf()] {
        let mut bytes=Vec::new();
        match fs::File::open(file) {
            Ok(file) => { if file.take(MAX_LOG_BYTES+1).read_to_end(&mut bytes).is_err() { output.unreadable_lines+=1; continue; } },
            Err(e) if e.kind()==std::io::ErrorKind::NotFound => continue,
            Err(_) => { output.unreadable_lines+=1; continue; }
        }
        if bytes.len() as u64 > MAX_LOG_BYTES { output.unreadable_lines+=1; continue; }
        for line in bytes.split(|b| *b==b'\n').filter(|s| !s.is_empty()) {
            if let Ok(record)=serde_json::from_slice::<Record>(line){
                if record.recording_trace==Some(0)||(record.trace_unavailable&&record.recording_trace.is_some()){output.unreadable_lines+=1;}else{output.events.push(record);}continue;
            }
            match serde_json::from_slice::<BuildIdentity>(line){
                Ok(image)if image.valid()=>{
                    if conflicted.contains(&image.process_instance){continue}
                    if let Some(old)=output.build_identities.iter().find(|old|old.process_instance==image.process_instance){
                        if old!=&image {let id=image.process_instance;output.build_identities.retain(|old|old.process_instance!=id);conflicted.insert(id);output.build_conflicts+=1;}
                    }else{output.build_identities.push(image);}
                },_=>output.unreadable_lines+=1,
            }
        }
    }
    output
}
pub fn host_journal() -> HostJournal { let _guard=JOURNAL.lock().ok(); read_journal(&log_path()) }

fn preview_value(snapshot:&crate::companion_v1::CompanionV1Snapshot,host:&HostJournal,current:Option<&BuildIdentity>)->serde_json::Value{
    let hex=|value:u64|format!("{value:016x}");
    let digest=|image:&identity::Image|image.sha256.map(|bytes|bytes.iter().map(|b|format!("{b:02x}")).collect::<String>());
    let mut recent:Vec<_>=host.events.iter().rev().take(24).map(|record|serde_json::json!({
        "operation":record.operation,"unixMs":record.unix_ms,"operationId":hex(record.event.correlation_id),
        "recordingTrace":record.recording_trace.map(hex),"traceUnavailable":record.trace_unavailable,
        "processInstance":(record.process_instance!=0).then(||hex(record.process_instance)),
        "result":record.event.command_result,"category":record.event.error_category,"elapsedMs":record.event.timing_value_ms,
    })).collect();recent.reverse();
    serde_json::json!({"schema":"companion.diagnostics.preview.v1","typeVersion":env!("CARGO_PKG_VERSION"),
        "currentProcessInstance":hex(identity::process_instance()),"executableSha256":current.and_then(|v|digest(&v.executable)),
        "librarySha256":current.and_then(|v|digest(&v.companion_library)),"hostEventCount":host.events.len(),
        "unreadableLines":host.unreadable_lines,"writeFailed":host.write_failed,"buildConflicts":host.build_conflicts,
        "unlinkedEvents":host.events.iter().filter(|v|v.recording_trace.is_none()).count(),
        "unknownBuildEvents":host.events.iter().filter(|v|v.process_instance==0||!host.build_identities.iter().any(|b|b.process_instance==v.process_instance)).count(),
        "cachedFirmwareVersion":snapshot.device.firmware_version,"cachedUiGeneration":snapshot.device.ui_generation,
        "recentEvents":recent,"deviceLogIncluded":false})
}
pub(crate) fn preview(snapshot:&crate::companion_v1::CompanionV1Snapshot)->serde_json::Value{
    let image=identity::current_build_for_report();let host=host_journal();preview_value(snapshot,&host,image.as_ref())
}
pub(crate) fn report(snapshot:&crate::companion_v1::CompanionV1Snapshot, device:Option<DeviceLogPage>, requested:bool) -> serde_json::Value {
    let current_build=identity::current_build_for_report();
    let host=host_journal();let preview=preview_value(snapshot,&host,current_build.as_ref());
    serde_json::json!({
        "schema":"companion.diagnostics.v1", "typeVersion":env!("CARGO_PKG_VERSION"),
        "diagnosticMetadataVersion":2,"currentProcessInstance":identity::process_instance(),"currentProcessImage":current_build,
        "buildIdentityScope":"Observed on-disk process executable and Companion library; not an in-memory attestation. Unknown legacy/conflicted process identities are not inferred from the current build.",
        "recordingTraceScope":"Local salted pseudonymous recording linkage, not a firmware event correlation ID. No raw session ID or salt is exported; missing linkage stays unavailable. Save checkpoints are not capture/transfer duration measurements.",
        "capturedAtUnixMs":SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_millis() as u64,
        "privacy":"Metadata only; no credentials, transcript, meeting title, raw audio or service URLs.",
        "host":host,"preview":preview,
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
        let record=Record { operation:Operation::OtaTransfer,unix_ms:1,event:EventEnvelope::new(5,1,0,EventSource::Type,Capability::Ota),process_instance:0,recording_trace:None,trace_unavailable:false };
        append(&path,&record).unwrap();
        let out=read_journal(&path); assert_eq!(out.events.len(),1); assert_eq!(out.unreadable_lines,1);
        let text=serde_json::to_string(&out).unwrap(); assert!(!text.contains("xxxx"));
        assert_eq!(classify_error("unauthorized secret=PRIVATE_TOKEN").1,ErrorCategory::Provider);
        fs::remove_dir_all(dir).unwrap();
    }
}

#[cfg(test)]
mod trace_tests;
