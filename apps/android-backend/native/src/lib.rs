//! Shared decoder candidate for the mobile backend. Platform bindings are separate.
#[path = "../../../windows/src-tauri/src/backend/cop1.rs"]
mod cop1;
#[path = "../../../../third_party/denzic-platform/host_audio/host/rust/src/opus_decoder.rs"]
mod opus_decoder;
#[cfg(feature="mobile-asr")]
mod volcengine { include!(concat!(env!("OUT_DIR"),"/volcengine_shared.rs")); }
#[cfg(feature="mobile-asr")]
mod long_transcription;
#[cfg(feature="mobile-asr")]
mod asr_cache;
#[cfg(feature="mobile-local-asr")]
mod local_paraformer;
#[cfg(feature="mobile-calendar")]
mod calendar_copy {
    // The shared calendar exporter references this existing desktop handoff type;
    // the phone export itself uses the shared ICS functions, not this helper.
    pub struct Entry {pub uid:String,pub title:String,pub deadline:String,pub reminder_minutes:Option<u16>,pub reminder_at:Option<String>}
}
#[cfg(feature="mobile-calendar")]
#[path = "../../../windows/src-tauri/src/backend/action_export.rs"]
mod action_export;
#[cfg(feature="mobile-calendar")]
mod mobile_calendar;
#[cfg(feature="mobile-memo")]
mod companion_v1 {
    #[derive(Clone,Debug,serde::Serialize,serde::Deserialize)]
    pub struct CompanionV1ActionItem {pub text:String,pub owner:Option<String>,pub due:Option<String>}
    #[derive(Clone)] pub struct Note {pub text:String}
    #[derive(Clone,serde::Serialize)] pub struct SpeakerName {pub name:String}
    #[derive(Clone,serde::Serialize)] pub struct UtteranceEdit {pub speaker_name:Option<String>}
    #[derive(Clone,serde::Serialize)] pub struct TranscriptReview {pub speaker_names:Vec<SpeakerName>,pub utterance_edits:Vec<UtteranceEdit>}
    #[derive(Clone,Default)] pub struct CompanionV1HostSession {pub id:String,pub title:String,pub source:String,pub transcript_text:String,pub duration_ms:u64,pub meeting_notes:Vec<Note>,pub meeting_mode:String,pub audio_path:Option<String>,pub transcript_review:Option<TranscriptReview>,pub utterances:Vec<()>,pub minutes:Option<CompanionV1MeetingMinutes>,pub minutes_by_mode:()}
    #[derive(Clone,Debug,serde::Serialize,serde::Deserialize)]
    #[serde(rename_all="camelCase")]
    pub struct CompanionV1MeetingMinutes {pub processing:Option<CompanionV1MinutesProcessing>,pub source_note_context:Option<()>,pub source_review_revision:Option<u64>,pub generated_at:String,pub source:String,pub quality:String,pub summary:Vec<String>,pub decisions:Vec<String>,pub action_items:Vec<CompanionV1ActionItem>,pub questions:Vec<String>,pub keywords:Vec<String>,pub markdown:String,pub llm_note:Option<String>}
    #[derive(Clone,Debug,serde::Serialize,serde::Deserialize)]
    #[serde(rename_all="camelCase")]
    pub struct CompanionV1MinutesProcessing {pub strategy:String,pub source_bytes:usize,pub processed_source_bytes:usize,pub total_chunks:usize,pub completed_chunks:usize,pub resumed_chunks:usize,pub complete:bool}
    impl CompanionV1MinutesProcessing {pub fn is_complete(&self)->bool{self.strategy=="chunkedSourceBacked"&&self.complete&&self.total_chunks!=0&&self.completed_chunks==self.total_chunks&&self.resumed_chunks<=self.completed_chunks&&self.source_bytes!=0&&self.processed_source_bytes==self.source_bytes}}
    #[cfg(feature="mobile-control")]
    #[derive(Clone,Debug,serde::Serialize,serde::Deserialize,PartialEq,Eq)]
    #[serde(rename_all="camelCase")]
    pub struct CompanionV1RecordingKey {pub device_uid:String,pub format_epoch:String,pub session_id:String}
    #[cfg(feature="mobile-control")]
    #[derive(Clone,Copy,Debug,serde::Serialize,serde::Deserialize,PartialEq,Eq)]
    #[serde(rename_all="camelCase")]
    pub enum CompanionV1RecordingEndReason {User,StorageFull,DurationLimit,LowBattery,Silence}
    #[cfg(feature="mobile-control")]
    impl CompanionV1RecordingEndReason {pub(crate) fn from_code(code:u8)->Result<Option<Self>,String>{Ok(match code{0=>None,1=>Some(Self::User),2=>Some(Self::StorageFull),3=>Some(Self::DurationLimit),4=>Some(Self::LowBattery),5=>Some(Self::Silence),_=>return Err("unsupported recording end reason".into())})}}
    #[cfg(feature="mobile-control")]
    #[derive(Clone,Debug,PartialEq,Eq)]
    pub struct CompanionV1RecordingCapacity {pub layout_version:u8,pub busy:bool,pub confirmed_discard_supported:bool,pub used_entries:u8,pub max_entries:u8,pub catalog_generation:u32,pub data_bytes:u32,pub free_bytes:u32,pub largest_free_extent:u32,pub protected_bytes:u32,pub consumed_bytes:u32,pub bytes_per_second:u32,pub reserve_headroom:u32,pub segment_frames:Option<u32>,pub segment_extent_bytes:Option<u32>,pub local_limit_seconds:u32,pub unsynced_entries:u8,pub writing_entries:u8,pub consumed_entries:u8}
}
#[cfg(feature="mobile-memo")]
use companion_v1::CompanionV1MeetingMinutes;
#[cfg(feature="mobile-memo")]
mod fact_match { include!(concat!(env!("OUT_DIR"),"/minutes_fact_match.rs")); }
#[cfg(feature="mobile-memo")]
use fact_match::source_fact_covered;
#[cfg(feature="mobile-memo")]
#[path = "../../../windows/src-tauri/src/backend/minutes/short_memo.rs"]
mod short_memo;
#[cfg(feature="mobile-memo")]
mod mobile_memo;
#[cfg(feature="mobile-minutes")]
extern crate self as denzic_host_audio_v1_core;
#[cfg(feature="mobile-minutes")]
#[path = "../../../../third_party/denzic-platform/host_audio/host/rust/src/http_policy.rs"]
pub mod http_policy;
#[cfg(feature="mobile-minutes")]
mod backend;
#[cfg(feature="mobile-minutes")]
mod mobile_minutes;
#[cfg(feature="mobile-control")]
mod mobile_control_jni;

use sha2::{Digest,Sha256};
use std::{fs::{self,File,OpenOptions},io::{Read,Seek,SeekFrom,Write},path::{Path,PathBuf},sync::atomic::{AtomicU64,Ordering}};

/// A previously saved segment and its unmodified device descriptor.
pub struct Segment { pub path:PathBuf, pub descriptor:[u8;112] }
pub struct Decoded { pub path:PathBuf, pub samples:u64, pub capture_complete:bool }

struct Description {uid:[u8;12],epoch:u64,session:u64,index:u32,recording:u32,offset:u64,samples:u64,
    length:u32,crc:u32,sha:[u8;32],total:u32,flags:u8,source:u8}
fn u32le(p:&[u8])->u32 {u32::from_le_bytes(p.try_into().unwrap())}
fn u64le(p:&[u8])->u64 {u64::from_le_bytes(p.try_into().unwrap())}
impl Description {
    fn parse(p:&[u8;112])->Result<Self,String> {
        if &p[..8]!=b"CRS2\x02\x00\x70\x00" || crc32fast::hash(&p[..108])!=u32le(&p[108..]) {return Err("invalid recording descriptor".into());}
        let d=Self {recording:u32le(&p[8..12]),epoch:u64le(&p[12..20]),session:u64le(&p[20..28]),index:u32le(&p[28..32]),offset:u64le(&p[32..40]),samples:u64le(&p[40..48]),length:u32le(&p[48..52]),crc:u32le(&p[52..56]),sha:p[56..88].try_into().unwrap(),total:u32le(&p[88..92]),flags:p[92],source:p[94],uid:p[96..108].try_into().unwrap()};
        if d.recording==0||d.epoch==0||d.session==0||d.index>=1024||p[93]!=3||d.source>2||p[95]>2||d.flags&!63!=0||d.flags>>3>5||
            (d.flags&56!=0&&d.flags&2==0)||d.flags&1==0||d.length<15||d.length>64*1024*1024||d.samples==0||d.samples%320!=0||d.offset%320!=0||
            d.offset.checked_add(d.samples).is_none()||d.samples/320>u64::from((d.length-12)/3)||
            d.uid.iter().all(|b|*b==0)||d.uid.iter().all(|b|*b==255)||d.sha.iter().all(|b|*b==0)||
            (if d.flags&2!=0 {d.total!=d.index+1} else {d.total!=0}) {return Err("invalid sealed recording descriptor".into());}
        Ok(d)
    }
}

static TEMP_COUNTER:AtomicU64=AtomicU64::new(0);
fn wav_header(size:u32)->[u8;44] {
    let mut h=[0u8;44];h[..4].copy_from_slice(b"RIFF");h[4..8].copy_from_slice(&(size+36).to_le_bytes());h[8..16].copy_from_slice(b"WAVEfmt ");h[16..20].copy_from_slice(&16u32.to_le_bytes());h[20..22].copy_from_slice(&1u16.to_le_bytes());h[22..24].copy_from_slice(&1u16.to_le_bytes());h[24..28].copy_from_slice(&16000u32.to_le_bytes());h[28..32].copy_from_slice(&32000u32.to_le_bytes());h[32..34].copy_from_slice(&2u16.to_le_bytes());h[34..36].copy_from_slice(&16u16.to_le_bytes());h[36..40].copy_from_slice(b"data");h[40..44].copy_from_slice(&size.to_le_bytes());h
}

/// Decode a complete set of verified sealed segments. An existing output is never overwritten.
/// Call on a worker thread. The device and original segment files are not modified.
pub fn decode_session(segments:&[Segment],output:&Path)->Result<Decoded,String> {
    if segments.is_empty()||segments.len()>1024{return Err("recording segments are missing".into());}
    let descriptions=segments.iter().map(|s|Description::parse(&s.descriptor)).collect::<Result<Vec<_>,_>>()?;
    let first=&descriptions[0];let mut offset=0u64;let mut ids=std::collections::HashSet::new();
    for (i,d) in descriptions.iter().enumerate() {
        if d.uid!=first.uid||d.epoch!=first.epoch||d.session!=first.session||d.source!=first.source||d.index!=i as u32||d.offset!=offset||!ids.insert(d.recording)||
            ((d.flags&2!=0)!=(i+1==descriptions.len())) {return Err("recording session is missing or has conflicting segments".into());}
        offset=offset.checked_add(d.samples).ok_or("recording is too long")?;
    }
    let parent=output.parent().ok_or("output directory is missing")?;
    let counter=TEMP_COUNTER.fetch_add(1,Ordering::Relaxed);
    let temporary=parent.join(format!(".companion-decode-{}-{}.tmp",std::process::id(),counter));
    let mut file=OpenOptions::new().write(true).read(true).create_new(true).open(&temporary).map_err(|e|format!("create temporary audio: {e}"))?;
    let result=(|| -> Result<Decoded,String> {
        file.write_all(&wav_header(0)).map_err(|e|e.to_string())?;
        let mut decoder=opus_decoder::MonoDecoder::new(16000)?;let mut window=None;let mut schema=None;let mut timeline=None;let mut written=0u64;
        for (s,d) in segments.iter().zip(&descriptions) {
            let input=File::open(&s.path).map_err(|e|format!("open recording: {e}"))?;
            if input.metadata().map_err(|e|e.to_string())?.len()!=u64::from(d.length) {return Err("recording segment length changed".into());}
            let mut bytes=Vec::with_capacity(d.length as usize);input.take(u64::from(d.length)+1).read_to_end(&mut bytes).map_err(|e|e.to_string())?;
            if bytes.len()!=d.length as usize || crc32fast::hash(&bytes)!=d.crc || Sha256::digest(&bytes).as_slice()!=d.sha {return Err("recording segment checksum changed".into());}
            let mut reader=cop1::Reader::new(bytes.as_slice(),d.offset,false)?;
            if reader.frame_ms!=20||reader.source_rate!=16000||schema.is_some_and(|v|v!=reader.schema) {return Err("recording audio format changed".into());}
            if schema.is_none(){schema=Some(reader.schema);window=Some(cop1::SampleWindow::new(reader.schema,320)?);if reader.schema>=2{timeline=Some(cop1::Timeline::default());}}
            while let Some(record)=reader.next()? {
                let packet=match record {
                    cop1::Record::Audio(p)=>p,
                    cop1::Record::Boundary(b)=>{window.as_mut().unwrap().observe(b)?;continue;},
                    cop1::Record::Event(e)=>{if !window.as_ref().unwrap().event_allowed(){return Err("event after audio end".into());}timeline.as_mut().ok_or("unexpected event")?.push(e)?;continue;},
                };
                let pcm=decoder.decode(&packet)?;if pcm.len()!=320{return Err("unexpected audio packet duration".into());}
                let range=window.as_mut().unwrap().packet(pcm.len())?;
                let pcm=&pcm[range];let mut encoded=Vec::with_capacity(pcm.len()*2);
                for sample in pcm {encoded.extend_from_slice(&sample.to_le_bytes());}
                file.write_all(&encoded).map_err(|e|e.to_string())?;written+=pcm.len() as u64;
                if written>512*1024*1024{return Err("decoded recording exceeds supported size".into());}
            }
            let summary=reader.finish(d.flags&4!=0)?;
            if summary.frames.checked_mul(320)!=Some(d.samples)||summary.encoded_bytes!=u64::from(d.length) {return Err("recording segment sample count changed".into());}
            if summary.ended_paused && d.flags&2==0 && !(reader.schema>=4&&summary.codec_end.is_some()) {return Err("recording ended before its final segment".into());}
            if let Some(t)=timeline.as_mut(){t.add_segment(&summary)?;}
        }
        let recovered=descriptions.iter().any(|d|d.flags&4!=0);
        let boundary=window.unwrap().finish(descriptions.last().unwrap().flags&4!=0)?;
        if boundary.written_samples!=written||written==0{return Err("recording contains no complete audio".into());}
        let data=(written*2) as u32;file.seek(SeekFrom::Start(0)).map_err(|e|e.to_string())?;file.write_all(&wav_header(data)).map_err(|e|e.to_string())?;file.sync_all().map_err(|e|e.to_string())?;
        // Publish without replacing a previous recording, even if another writer races us.
        fs::hard_link(&temporary,output).map_err(|e|format!("save decoded recording: {e}"))?;
        Ok(Decoded{path:output.to_path_buf(),samples:written,capture_complete:!recovered})
    })();
    drop(file);let _=fs::remove_file(&temporary);result
}

#[no_mangle]
pub extern "system" fn Java_com_denzic_companion_mobile_NativeAudio_decodeFiles(
    mut env:jni::JNIEnv,_class:jni::objects::JClass,paths:jni::objects::JObjectArray,
    descriptors:jni::objects::JObjectArray,output:jni::objects::JString) -> jni::sys::jlong {
    let run=std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| -> Result<i64,String> {
        let count=env.get_array_length(&paths).map_err(|e|e.to_string())?;
        if count<=0||count>1024||env.get_array_length(&descriptors).map_err(|e|e.to_string())?!=count {return Err("invalid recording segment list".into());}
        let output:String=env.get_string(&output).map_err(|e|e.to_string())?.into();
        let mut segments=Vec::with_capacity(count as usize);
        for i in 0..count {
            let path=jni::objects::JString::from(env.get_object_array_element(&paths,i).map_err(|e|e.to_string())?);
            let path_value:String=env.get_string(&path).map_err(|e|e.to_string())?.into();
            env.delete_local_ref(path).map_err(|e|e.to_string())?;
            let descriptor=jni::objects::JByteArray::from(env.get_object_array_element(&descriptors,i).map_err(|e|e.to_string())?);
            let bytes=env.convert_byte_array(&descriptor).map_err(|e|e.to_string())?;
            env.delete_local_ref(descriptor).map_err(|e|e.to_string())?;
            segments.push(Segment{path:PathBuf::from(path_value),descriptor:bytes.try_into().map_err(|_|"invalid recording descriptor length")?});
        }
        Ok(decode_session(&segments,Path::new(&output))?.samples as i64)
    }));
    match run {
        Ok(Ok(samples))=>samples,
        Ok(Err(error))=>{let _=env.throw_new("java/io/IOException",error);0},
        Err(_)=>{let _=env.throw_new("java/io/IOException","audio decoding failed; original recordings were retained");0},
    }
}

/// The existing Companion/Listener network fixture uses only local synthetic audio and a local server.
#[cfg(feature="mobile-asr")]
pub fn local_asr_probe()->Result<usize,String> {Ok(volcengine::verify_network()?.len())}

/// Performs one explicitly requested recognition; credentials are supplied by the caller.
#[cfg(feature="mobile-local-asr")]
#[no_mangle]
pub extern "system" fn Java_com_denzic_companion_mobile_NativeLocalTranscription_transcribeFile(
    mut env: jni::JNIEnv, _class: jni::objects::JClass, wav: jni::objects::JString,
    model_dir: jni::objects::JString, runtime_dir: jni::objects::JString, cache_dir: jni::objects::JString,
) -> jni::sys::jstring {
    let run = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| -> Result<String, String> {
        let wav: String = env.get_string(&wav).map_err(|e| e.to_string())?.into();
        let model: String = env.get_string(&model_dir).map_err(|e| e.to_string())?.into();
        let runtime: String = env.get_string(&runtime_dir).map_err(|e| e.to_string())?.into();
        let cache: String = env.get_string(&cache_dir).map_err(|e| e.to_string())?.into();
        local_paraformer::transcribe(Path::new(&wav), Path::new(&model), Path::new(&runtime), Path::new(&cache))
    }));
    match run {
        Ok(Ok(text)) => match env.new_string(text) { Ok(s) => s.into_raw(), Err(e) => { let _ = env.throw_new("java/io/IOException", e.to_string()); std::ptr::null_mut() } },
        Ok(Err(error)) => { let _ = env.throw_new("java/io/IOException", error); std::ptr::null_mut() },
        Err(_) => { let _ = env.throw_new("java/io/IOException", "本地转写未完成，原录音保留。"); std::ptr::null_mut() },
    }
}

/// Performs one explicitly requested recognition; credentials are supplied by the caller.
#[cfg(feature="mobile-asr")]
#[no_mangle]
pub extern "system" fn Java_com_denzic_companion_mobile_NativeTranscription_transcribeFileWithCache(
    mut env:jni::JNIEnv,_class:jni::objects::JClass,wav:jni::objects::JString,
    app_id:jni::objects::JString,access_token:jni::objects::JString,resource:jni::objects::JString,cache_dir:jni::objects::JString
) -> jni::sys::jstring {
    let run=std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| -> Result<String,String> {
        let wav:String=env.get_string(&wav).map_err(|e|e.to_string())?.into();
        let app_id:String=env.get_string(&app_id).map_err(|e|e.to_string())?.into();
        let access_token:String=env.get_string(&access_token).map_err(|e|e.to_string())?.into();
        let resource_id:String=env.get_string(&resource).map_err(|e|e.to_string())?.into();
        let cache_dir:String=env.get_string(&cache_dir).map_err(|e|e.to_string())?.into();
        if app_id.trim().is_empty()||access_token.trim().is_empty()||resource_id.trim().is_empty(){return Err("recognition service configuration is incomplete".into());}
        let provider=volcengine::VolcengineSaucAsr::new(volcengine::VolcengineCredentials{app_id,access_token,resource_id});
        let cache=if cache_dir.is_empty(){None}else{Some(asr_cache::Cache::new(Path::new(&cache_dir),&provider.cache_configuration())?)};
        long_transcription::transcribe_cached(Path::new(&wav),cache.as_ref(),|pcm|provider.transcribe_pcm_bytes(pcm).map(|(text,_)|text))
    }));
    match run {
        Ok(Ok(text))=>match env.new_string(text){Ok(s)=>s.into_raw(),Err(e)=>{let _=env.throw_new("java/io/IOException",e.to_string());std::ptr::null_mut()}},
        Ok(Err(error))=>{let _=env.throw_new("java/io/IOException",error);std::ptr::null_mut()},
        Err(_)=>{let _=env.throw_new("java/io/IOException","speech recognition failed; original audio was retained");std::ptr::null_mut()},
    }
}

#[cfg(feature="mobile-calendar")]
#[no_mangle]
pub extern "system" fn Java_com_denzic_companion_mobile_NativeCalendar_exportJson(
    mut env:jni::JNIEnv,_class:jni::objects::JClass,request:jni::objects::JString
) -> jni::sys::jstring {
    let run=std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| -> Result<String,String> {
        let request:String=env.get_string(&request).map_err(|e|e.to_string())?.into();
        mobile_calendar::export_json(&request)
    }));
    match run {
        Ok(Ok(json))=>match env.new_string(json){Ok(s)=>s.into_raw(),Err(e)=>{let _=env.throw_new("java/io/IOException",e.to_string());std::ptr::null_mut()}},
        Ok(Err(error))=>{let _=env.throw_new("java/io/IOException",error);std::ptr::null_mut()},
        Err(_)=>{let _=env.throw_new("java/io/IOException","calendar export failed; saved content was retained");std::ptr::null_mut()},
    }
}

#[cfg(feature="mobile-memo")]
#[no_mangle]
pub extern "system" fn Java_com_denzic_companion_mobile_NativeMemo_extractJson(
    mut env:jni::JNIEnv,_class:jni::objects::JClass,input:jni::objects::JString,duration_ms:jni::sys::jlong
) -> jni::sys::jstring {
    let run=std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| -> Result<String,String> {
        if duration_ms<0{return Err("录音时长无效。".into());}
        let input:String=env.get_string(&input).map_err(|e|e.to_string())?.into();
        mobile_memo::extract(&input,duration_ms as u64)
    }));
    match run {
        Ok(Ok(json))=>match env.new_string(json){Ok(s)=>s.into_raw(),Err(e)=>{let _=env.throw_new("java/io/IOException",e.to_string());std::ptr::null_mut()}},
        Ok(Err(error))=>{let _=env.throw_new("java/io/IOException",error);std::ptr::null_mut()},
        Err(_)=>{let _=env.throw_new("java/io/IOException","待办草稿未生成；原转写保留。");std::ptr::null_mut()},
    }
}

#[cfg(feature="mobile-minutes")]
#[no_mangle]
pub extern "system" fn Java_com_denzic_companion_mobile_NativeMinutes_generateJson(
    mut env:jni::JNIEnv,_class:jni::objects::JClass,request:jni::objects::JString,
    key:jni::objects::JString,cache:jni::objects::JString
) -> jni::sys::jstring {
    let run=std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| -> Result<String,String> {
        let request:String=env.get_string(&request).map_err(|e|e.to_string())?.into();
        let key:String=env.get_string(&key).map_err(|e|e.to_string())?.into();
        let cache:String=env.get_string(&cache).map_err(|e|e.to_string())?.into();
        mobile_minutes::generate_json(&request,&key,Path::new(&cache))
    }));
    match run {
        Ok(Ok(json))=>match env.new_string(json){Ok(s)=>s.into_raw(),Err(e)=>{let _=env.throw_new("java/io/IOException",e.to_string());std::ptr::null_mut()}},
        Ok(Err(error))=>{let _=env.throw_new("java/io/IOException",error);std::ptr::null_mut()},
        Err(_)=>{let _=env.throw_new("java/io/IOException","纪要未生成；原转写保持不变。");std::ptr::null_mut()},
    }
}

#[cfg(test)]
mod mobile_tests {
    use super::*;
    fn segment(dir:&Path,index:u32,count:u32,last:bool,raw:Vec<u8>)->Segment {
        let path=dir.join(format!("segment-{index}.cop1"));fs::write(&path,&raw).unwrap();
        let mut d=[0u8;112];d[..8].copy_from_slice(b"CRS2\x02\x00\x70\x00");
        d[8..12].copy_from_slice(&(41+index).to_le_bytes());d[12]=1;d[20]=1;d[28..32].copy_from_slice(&index.to_le_bytes());
        d[32..40].copy_from_slice(&(u64::from(index)*640).to_le_bytes());d[40..48].copy_from_slice(&(u64::from(count)*320).to_le_bytes());
        d[48..52].copy_from_slice(&(raw.len() as u32).to_le_bytes());d[52..56].copy_from_slice(&crc32fast::hash(&raw).to_le_bytes());
        d[56..88].copy_from_slice(&Sha256::digest(&raw));if last{d[88..92].copy_from_slice(&(index+1).to_le_bytes());}
        d[92]=if last{3}else{1};d[93]=3;d[96]=1;let crc=crc32fast::hash(&d[..108]);d[108..].copy_from_slice(&crc.to_le_bytes());
        Segment{path,descriptor:d}
    }
    fn create_segment(dir:&Path,index:u32,count:u32,last:bool)->Segment {
        let mut raw=b"COP1\x01\x01\x14\x00\x80\x3e\x00\x00".to_vec();
        for _ in 0..count {raw.extend_from_slice(&[3,0,0xf8,0xff,0xfe]);}
        segment(dir,index,count,last,raw)
    }
    fn boundary(kind:u8,encoded:u64,valid:u64)->[u8;32] {
        let mut w=[0u8;32];w[2..6].copy_from_slice(b"CDB1");w[6]=kind;w[8..12].copy_from_slice(&40u32.to_le_bytes());
        w[12..20].copy_from_slice(&encoded.to_le_bytes());w[20..28].copy_from_slice(&valid.to_le_bytes());let crc=crc32fast::hash(&w[..28]);w[28..].copy_from_slice(&crc.to_le_bytes());w
    }
    fn silent_packets()->Vec<Vec<u8>> {
        use std::ffi::c_void;
        extern "C" {fn opus_encoder_create(rate:i32,channels:i32,application:i32,error:*mut i32)->*mut c_void;
            fn opus_encoder_ctl(encoder:*mut c_void,request:i32,...)->i32;
            fn opus_encode(encoder:*mut c_void,pcm:*const i16,frame:i32,out:*mut u8,max:i32)->i32;
            fn opus_encoder_destroy(encoder:*mut c_void);}
        unsafe {
            let mut error=0;let e=opus_encoder_create(16000,1,2048,&mut error);assert!(!e.is_null()&&error==0);
            assert_eq!(opus_encoder_ctl(e,4002,16000i32),0);assert_eq!(opus_encoder_ctl(e,4006,0i32),0);
            let pcm=[0i16;320];let mut packets=Vec::new();
            for _ in 0..3{let mut packet=vec![0;40];assert_eq!(opus_encode(e,pcm.as_ptr(),320,packet.as_mut_ptr(),40),40);packets.push(packet);}
            opus_encoder_destroy(e);packets
        }
    }
    #[test]
    fn silent_two_segment_session_decodes_and_preserves_existing_output() {
        let dir=std::env::temp_dir().join(format!("companion-mobile-decode-{}-{}",std::process::id(),TEMP_COUNTER.fetch_add(1,Ordering::Relaxed)));
        fs::create_dir(&dir).unwrap();let first=create_segment(&dir,0,2,false);let second=create_segment(&dir,1,1,true);let out=dir.join("audio.wav");
        let inputs=[first,second];let decoded=decode_session(&inputs,&out).unwrap();assert_eq!(decoded.samples,640);assert!(decoded.capture_complete);
        let wav=fs::read(&out).unwrap();assert_eq!(&wav[..4],b"RIFF");assert_eq!(wav.len(),44+640*2);
        assert!(decode_session(&inputs,&out).is_err());assert_eq!(fs::read(&out).unwrap(),wav);
        let mut broken=fs::read(&inputs[1].path).unwrap();broken[15]^=1;fs::write(&inputs[1].path,broken).unwrap();
        assert!(decode_session(&inputs,&dir.join("damaged.wav")).is_err());assert!(!dir.join("damaged.wav").exists());assert_eq!(fs::read(&out).unwrap(),wav);
        fs::remove_file(&inputs[0].path).unwrap();fs::remove_file(&inputs[1].path).unwrap();fs::remove_file(out).unwrap();fs::remove_dir(dir).unwrap();
    }
    #[test]
    fn schema4_and_schema5_segments_keep_explicit_source_start_and_end() {
        let dir=std::env::temp_dir().join(format!("companion-mobile-boundary-{}-{}",std::process::id(),TEMP_COUNTER.fetch_add(1,Ordering::Relaxed)));
        fs::create_dir(&dir).unwrap();let packets=silent_packets();
        for schema in [4u8,5] {
            let mut header=b"COP1\x04\x01\x14\x07\x80\x3e\x00\x00".to_vec();if schema==5 {header[4]=5;header[7]=15;}
            let profile=include_bytes!("../../../windows/src-tauri/src/backend/fixtures/audio-profile-v1.bin");
            let mut first=header.clone();first.extend_from_slice(&boundary(1,0,u64::MAX));if schema==5{first.extend_from_slice(profile);}
            for p in &packets[..2]{first.extend_from_slice(&40u16.to_le_bytes());first.extend_from_slice(p);}
            let mut last=header;last.extend_from_slice(&boundary(1,640,u64::MAX));if schema==5{last.extend_from_slice(profile);}
            while last.len()%248!=0{last.push(255);}last.extend_from_slice(&boundary(2,960,640));
            last.extend_from_slice(&40u16.to_le_bytes());last.extend_from_slice(&packets[2]);
            let segments=[segment(&dir,0,2,false,first),segment(&dir,1,1,true,last)];let out=dir.join("audio.wav");
            let result=decode_session(&segments,&out).unwrap();assert_eq!(result.samples,640);assert_eq!(fs::metadata(&out).unwrap().len(),44+1280);
            fs::remove_file(&segments[0].path).unwrap();fs::remove_file(&segments[1].path).unwrap();fs::remove_file(out).unwrap();
        }
        fs::remove_dir(dir).unwrap();
    }
}
