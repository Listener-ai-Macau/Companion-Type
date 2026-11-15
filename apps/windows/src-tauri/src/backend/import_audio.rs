//! Decode imported files incrementally for the existing 16 kHz speech pipeline.
//! The selected original is never modified; the caller owns its preserved copy.
use std::{fs::{self,File,OpenOptions}, io::{ErrorKind,Read,Seek,SeekFrom,Write}, path::{Path,PathBuf}, sync::atomic::{AtomicBool,Ordering}};
use sha2::{Digest,Sha256};
use symphonia::core::{audio::{AudioBufferRef,Signal,SampleBuffer}, codecs::DecoderOptions, errors::Error,
    formats::FormatOptions, io::MediaSourceStream, meta::MetadataOptions, probe::Hint};
use super::{audio_artifacts::{self, Purpose, WriteLease}, host_recording::RatioResampler,
    host_segmented_capture::{HostAudioPart, RollingHostWav}};

static ACTIVE:AtomicBool=AtomicBool::new(false);
static CANCEL:AtomicBool=AtomicBool::new(false);
struct ImportGuard;
impl ImportGuard {
    fn begin()->Result<Self,String> {
        ACTIVE.compare_exchange(false,true,Ordering::AcqRel,Ordering::Acquire)
            .map_err(|_|"已有音频正在导入，请等待完成或取消。")?;
        Ok(Self)
    }
}
impl Drop for ImportGuard {
    fn drop(&mut self) {CANCEL.store(false,Ordering::Release);ACTIVE.store(false,Ordering::Release);}
}
pub(crate) fn cancel()->bool {
    if ACTIVE.load(Ordering::Acquire) {CANCEL.store(true,Ordering::Release);true}else{false}
}
fn check_cancel()->Result<(),String> {
    if CANCEL.load(Ordering::Acquire) {Err("已取消导入，所选原文件未改变。".into())} else {Ok(())}
}

// Two cascaded Butterworth sections suppress high-frequency aliases before
// downsampling. State is continuous across codec packets.
struct LowPass { b0:f64,b1:f64,b2:f64,a1:f64,a2:f64,x1:f64,x2:f64,y1:f64,y2:f64 }
impl LowPass {
    fn new(rate:u32,q:f64)->Self {
        let frequency=7000.0_f64.min(rate as f64*0.45);
        let w=2.0*std::f64::consts::PI*frequency/rate as f64;
        let (sin,cos)=w.sin_cos();let alpha=sin/(2.0*q);let a0=1.0+alpha;
        Self {b0:(1.0-cos)/(2.0*a0),b1:(1.0-cos)/a0,b2:(1.0-cos)/(2.0*a0),
            a1:-2.0*cos/a0,a2:(1.0-alpha)/a0,x1:0.0,x2:0.0,y1:0.0,y2:0.0}
    }
    fn process(&mut self,x:f64)->f64 {
        let y=self.b0*x+self.b1*self.x1+self.b2*self.x2-self.a1*self.y1-self.a2*self.y2;
        self.x2=self.x1;self.x1=x;self.y2=self.y1;self.y1=y;y
    }
}
struct SpeechConverter {rate:u32, channels:usize,resampler:RatioResampler,filters:Option<[LowPass;2]>,invert_right:bool}
impl SpeechConverter {
    fn new(rate:u32,channels:usize)->Result<Self,String> {
        if rate==0 || channels==0 {return Err("音频采样格式不完整。".into());}
        Ok(Self {rate,channels,resampler:RatioResampler::new(rate,16000),
            filters:(rate>16000).then(||[LowPass::new(rate,0.5411961),LowPass::new(rate,1.306563)]),invert_right:false})
    }
    fn process(&mut self,samples:&[f32])->Vec<i16> {
        let mut mono=Vec::with_capacity(samples.len()/self.channels);
        if self.channels==2 {
            let (mut left,mut right,mut dot)=(0.0_f64,0.0_f64,0.0_f64);
            for frame in samples.chunks_exact(2) {
                let l=if frame[0].is_finite(){f64::from(frame[0])}else{0.0};
                let r=if frame[1].is_finite(){f64::from(frame[1])}else{0.0};
                left+=l*l;right+=r*r;dot+=l*r;
            }
            // Only reverse a channel when both carry a clear signal and their
            // waveforms are nearly opposite. A hysteresis band avoids changing
            // the choice on quiet or borderline packets.
            if left>1e-8 && right>1e-8 {
                let correlation=dot/(left*right).sqrt();
                if correlation< -0.90 {self.invert_right=true;}
                else if correlation> -0.70 {self.invert_right=false;}
            }
        }
        for frame in samples.chunks_exact(self.channels) {
            let mut sample=frame.iter().enumerate().map(|(index,v)|{
                let value=if v.is_finite(){*v as f64}else{0.0};
                if self.channels==2 && index==1 && self.invert_right {-value}else{value}
            }).sum::<f64>()/self.channels as f64;
            if let Some(filters)=&mut self.filters { for filter in filters { sample=filter.process(sample); } }
            mono.push(sample.clamp(-1.0,1.0) as f32);
        }
        self.resampler.process(&mono)
    }
}

pub(super) fn decode_to_speech_wav(input:&Path,anchor:&Path)->Result<Vec<HostAudioPart>,String> {
    check_cancel()?;
    let mut file=File::open(input).map_err(|e|format!("无法读取所选音频：{e}"))?;
    // An incomplete RIFF may otherwise appear to end normally to a decoder.
    // Reject a file whose own declared length extends beyond the source.
    let actual=file.metadata().map_err(|e|format!("无法读取音频信息：{e}"))?.len();
    let mut header=[0u8;12];
    if file.read_exact(&mut header).is_ok() && &header[..4]==b"RIFF" && &header[8..]==b"WAVE"
        && u64::from(u32::from_le_bytes(header[4..8].try_into().unwrap()))+8>actual {
        return Err("音频文件不完整，无法导入；原文件未改变。".into());
    }
    file.seek(SeekFrom::Start(0)).map_err(|e|format!("无法读取所选音频：{e}"))?;
    let stream=MediaSourceStream::new(Box::new(file),Default::default());
    let mut hint=Hint::new();if let Some(ext)=input.extension().and_then(|x|x.to_str()){hint.with_extension(ext);}
    let mut format=symphonia::default::get_probe().format(&hint,stream,&FormatOptions::default(),&MetadataOptions::default())
        .map_err(|e|format!("无法读取音频格式：{e}"))?.format;
    let track=format.default_track().ok_or("文件中没有可用音轨。")?;
    let track_id=track.id;
    let mut decoder=symphonia::default::get_codecs().make(&track.codec_params,&DecoderOptions::default())
        .map_err(|e|format!("暂不支持这个音频编码：{e}"))?;
    let mut leases:Vec<WriteLease>=Vec::new();
    audio_artifacts::generated(anchor,anchor,Purpose::Recording,|| {
        let mut writer=RollingHostWav::create(anchor).map_err(|e|format!("无法保存导入录音：{e}"))?;
        let mut converter:Option<SpeechConverter>=None;
        let mut samples_written=0u64;
        loop {
            check_cancel()?;
            let packet=match format.next_packet() {
                Ok(packet)=>packet,
                Err(Error::IoError(e)) if e.kind()==ErrorKind::UnexpectedEof=>break,
                Err(e)=>return Err(format!("读取音频未完成，原文件未改变：{e}")),
            };
            if packet.track_id()!=track_id {continue;}
            let audio=decoder.decode(&packet).map_err(|e|format!("音频解码未完成，原文件未改变：{e}"))?;
            let spec=*audio.spec();let channels=spec.channels.count();
            if converter.is_none() { converter=Some(SpeechConverter::new(spec.rate,channels)?); }
            let c=converter.as_mut().expect("converter initialized");
            if c.rate!=spec.rate||c.channels!=channels {return Err("音频中途改变采样格式，暂无法完整导入。原文件未改变。".into());}
            // The speech format already matches. Keep every PCM16 value,
            // including -32768, instead of quantizing it through f32 again.
            let pcm=if spec.rate==16000&&channels==1 {
                if let AudioBufferRef::S16(ref pcm)=audio {pcm.chan(0).to_vec()}
                else {let mut buf=SampleBuffer::<f32>::new(audio.capacity() as u64,spec);buf.copy_interleaved_ref(audio);c.process(buf.samples())}
            } else {let mut buf=SampleBuffer::<f32>::new(audio.capacity() as u64,spec);buf.copy_interleaved_ref(audio);c.process(buf.samples())};
            samples_written=samples_written.checked_add(pcm.len() as u64).ok_or("音频时长无效。")?;
            writer.append_bulk(&pcm,|next| {
                let lease=WriteLease::begin(next,next,Purpose::Recording).map_err(std::io::Error::other)?;
                audio_artifacts::attach_group(next,anchor).map_err(std::io::Error::other)?;
                if let Some(lease)=lease {leases.push(lease);} Ok(())
            }).map_err(|e|format!("保存导入录音失败，原文件未改变：{e}"))?;
        }
        if samples_written==0 {return Err("音频没有可用的声音数据，原文件未改变。".into());}
        let parts=writer.finish().map_err(|e|format!("完成导入录音失败，原文件未改变：{e}"))?;
        for lease in leases.drain(..) {lease.finish()?;}
        Ok(parts)
    })
}

pub(super) struct ImportedAudio {pub id:String,pub title:String,pub anchor:PathBuf,pub original:PathBuf,pub original_bytes:u64,pub original_sha256:String,pub parts:Vec<HostAudioPart>}

/// Record the selected file as a separate chunk in the existing session schema.
/// Unlike a new global artifact type, older versions can still read the library.
pub(super) fn import(input:&Path)->Result<ImportedAudio,String> {import_with_id(input,None)}
pub(super) fn import_with_id(input:&Path,incoming_id:Option<&str>)->Result<ImportedAudio,String> {
    let _guard=ImportGuard::begin()?;
    let ext=input.extension().and_then(|v|v.to_str()).unwrap_or("").to_ascii_lowercase();
    if !["wav","mp3","m4a","mp4","aac","flac","ogg"].contains(&ext.as_str()) {
        return Err("请选择 WAV、MP3、M4A、AAC、FLAC 或 OGG（Vorbis）音频文件。".into());
    }
    let title=input.file_stem().and_then(|v|v.to_str()).unwrap_or("导入录音")
        .chars().filter(|c|!c.is_control()).take(120).collect::<String>();
    let title=if title.trim().is_empty(){"导入录音".into()}else{title};
    let root=super::audio_storage::recording_root()?;
    let id=format!("import-{}",match incoming_id {Some(value)=>uuid::Uuid::parse_str(value).map_err(|_|"接收标识无效。")?,None=>uuid::Uuid::new_v4()}.simple());
    let anchor=root.join(format!("{id}.wav"));let original=root.join(format!("{id}.original.{ext}"));
    for path in [&anchor,&original]{match fs::symlink_metadata(path){
        Err(e) if e.kind()==std::io::ErrorKind::NotFound=>(),
        Err(_)=>return Err("无法核对上次接收文件，请保留原件后检查。".into()),
        Ok(_)=>return Err("上次接收的文件仍保留，但会议保存尚未确认；请先在资料库核对，未找到时移除此待接收项并重新分享。原文件未改变。".into()),
    }}
    let mut original_created=false;
    let result=(|| {
        let mut src=File::open(input).map_err(|e|format!("无法读取所选音频：{e}"))?;
        let before=src.metadata().map_err(|e|format!("无法读取音频信息：{e}"))?;
        if before.len()>2*1024*1024*1024 {return Err("单个原文件最多2GB，请先分成较短文件。".into());}
        if !before.is_file() || before.len()==0 {return Err("所选音频为空或不是文件。".into());}
        let mut out=OpenOptions::new().write(true).create_new(true).open(&original).map_err(|e|format!("无法保存音频副本：{e}"))?;
        original_created=true;let mut copied=0u64;let mut block=[0u8;65536];let mut hash=Sha256::new();
        loop { check_cancel()?; let n=src.read(&mut block).map_err(|e|format!("读取音频未完成：{e}"))?;if n==0 {break;}
            if copied.saturating_add(n as u64)>2*1024*1024*1024{return Err("原文件超过2GB，已停止导入；来源文件未改变。".into());}
            out.write_all(&block[..n]).map_err(|e|format!("复制音频未完成，原文件未改变：{e}"))?;hash.update(&block[..n]);
            copied=copied.checked_add(n as u64).ok_or("音频容量无效。")?; }
        out.flush().and_then(|_|out.sync_all()).map_err(|e|format!("保存音频副本未完成：{e}"))?;drop(out);
        let after=src.metadata().map_err(|e|format!("无法核对所选音频：{e}"))?;
        if copied!=before.len() || after.len()!=before.len() || after.modified().ok()!=before.modified().ok() {
            return Err("所选音频在复制时发生变化，请重试；原文件未改变。".into());
        }
        let original_sha256=format!("{:x}",hash.finalize());
        let parts=decode_to_speech_wav(&original,&anchor)?;check_cancel()?;
        Ok(ImportedAudio{id,title,anchor:anchor.clone(),original:original.clone(),original_bytes:copied,original_sha256,parts})
    })();
    if result.is_err() {
        // These exact names were created exclusively by this import; the
        // user-selected original is outside the cleanup operation.
        let _=audio_artifacts::erase(&root,&[anchor.to_string_lossy().into_owned()],&[]);
        if original_created {let _=fs::remove_file(&original);}
    }
    result
}

pub(super) fn original_chunk(row:&crate::companion_v1::CompanionV1HostSession)->Result<&crate::companion_v1::CompanionV1AudioChunk,String> {
    if !matches!(row.source.as_str(),"importedAudio"|"derivedAudio") {return Err("不是导入的音频。".into());}
    let mut matches=row.chunks.iter().filter(|chunk|chunk.status=="importedOriginal");
    let original=matches.next().ok_or("导入原文件记录缺失。")?;
    if matches.next().is_some(){return Err("导入原文件记录无效。".into());}
    let prefix=format!("{}-imported-original-",row.id);
    let hash=original.id.strip_prefix(&prefix).ok_or("导入原文件记录无效。")?;
    if hash.len()!=64 || !hash.bytes().all(|b|b.is_ascii_hexdigit()) || original.bytes==0 || original.path.is_none() {
        return Err("导入原文件记录无效。".into());
    }
    Ok(original)
}
pub(super) fn verify_original(row:&crate::companion_v1::CompanionV1HostSession,root:&Path)->Result<PathBuf,String> {
    let chunk=original_chunk(row)?;let path=PathBuf::from(chunk.path.as_deref().unwrap());
    if !super::audio_storage::owned_recording_reference(&path,root) {return Err("导入原文件位置无效。".into());}
    let meta=fs::symlink_metadata(&path).map_err(|_|"导入原文件缺失；回听副本仍保留。")?;
    if !meta.is_file() || meta.file_type().is_symlink() {return Err("导入原文件位置无效。".into());}
    let hash=chunk.id.rsplit('-').next().ok_or("导入原文件记录无效。")?;
    if super::audio_storage::fingerprint(&path)?!=(chunk.bytes,hash.to_owned()) {
        return Err("导入原文件缺失或已变化；回听副本仍保留。".into());
    }
    Ok(path)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn conversion_is_streaming_and_reduces_aliasing() {
        let mut converter=SpeechConverter::new(48000,2).unwrap();
        let input=(0..48000).flat_map(|n| {let x=(2.0*std::f32::consts::PI*12000.0*n as f32/48000.0).sin();[x,x]}).collect::<Vec<_>>();
        let pcm=input.chunks(2048).flat_map(|chunk|converter.process(chunk)).collect::<Vec<_>>();
        assert_eq!(pcm.len(),16000);
        let energy=pcm.iter().skip(100).map(|&x|f64::from(x).powi(2)).sum::<f64>()/15900.0;
        assert!(energy.sqrt()<4000.0,"high frequency energy should be filtered before downsampling");
    }
    #[test]
    fn opposite_phase_stereo_does_not_cancel_speech() {
        let mut converter=SpeechConverter::new(16000,2).unwrap();
        let source=(0..1600).flat_map(|i|{let value=((i as f32)*0.08).sin()*0.4;[value,-value]}).collect::<Vec<_>>();
        let output=converter.process(&source);assert_eq!(output.len(),1600);
        let peak=output.iter().map(|&v|i32::from(v).abs()).max().unwrap();
        assert!(peak>12000,"opposite-phase channels must not cancel to silence");
        let quiet=vec![0.0;200];assert!(converter.process(&quiet).iter().all(|&v|v==0));
        let normal=(0..1600).flat_map(|i|{let value=((i as f32)*0.08).sin()*0.4;[value,value]}).collect::<Vec<_>>();
        assert!(converter.process(&normal).iter().any(|v|i32::from(*v).abs()>12000),"normal stereo must remain audible");
    }
    #[test]
    fn imported_recording_survives_reopen_and_backs_up_original() {
        use crate::backend::CompanionBackend;
        let dir=std::env::temp_dir().join(format!("companion-import-library-{}",uuid::Uuid::new_v4()));
        let recordings=dir.join("recordings");std::fs::create_dir_all(&recordings).unwrap();
        let old_recordings=std::env::var_os("COMPANION_TYPE_RECORDING_DIR");let old_state=std::env::var_os("COMPANION_TYPE_STATE_PATH");
        std::env::set_var("COMPANION_TYPE_RECORDING_DIR",&recordings);std::env::set_var("COMPANION_TYPE_STATE_PATH",dir.join("sessions.json"));
        let input=dir.join("会议录音.wav");let mut w=denzic_host_audio_v1_core::wav::WavWriter::create(&input).unwrap();
        w.append_samples(&vec![500;32000]).unwrap();w.finalize().unwrap();drop(w);
        let original=std::fs::read(&input).unwrap();let backend=super::super::FixtureCompanionBackend::new();
        {let mut snapshot=backend.snapshot.lock().unwrap();snapshot.host.sessions.clear();snapshot.host.selected_session_id=None;}
        let snapshot=backend.import_audio_file(&input).unwrap();let row=&snapshot.host.sessions[0];
        assert_eq!(row.source,"importedAudio");assert_eq!(row.status,"captured");assert_eq!(row.duration_ms,2000);
        assert_eq!(snapshot.privacy.audio_cache_bytes,row.audio_bytes+original.len() as u64);
        let anchor=row.audio_path.as_ref().unwrap();
        let saved_original=verify_original(row,&recordings.canonicalize().unwrap()).unwrap();assert_eq!(std::fs::read(saved_original).unwrap(),original);
        let managed=super::super::audio_artifacts::backup_files_at(&recordings.canonicalize().unwrap(),&[anchor.clone()]).unwrap();
        assert_eq!(managed.len(),1,"the shared manifest must remain compatible with older versions");
        let exported=dir.join("exported-original.wav");super::super::audio_export::export(&snapshot,&row.id,&exported).unwrap();
        assert_eq!(std::fs::read(exported).unwrap(),original,"export must return the exact original, not the speech conversion");
        let backups=dir.join("backups");let target=dir.join("restored");
        std::fs::create_dir(&backups).unwrap();std::fs::create_dir(&target).unwrap();
        let report=super::super::library_backup::save(&snapshot,&recordings,&backups).unwrap();assert_eq!(report.files,2);
        std::env::set_var("COMPANION_TYPE_RECORDING_DIR",&target);
        let conflict=target.join(original_chunk(row).unwrap().path.as_ref().and_then(|p|Path::new(p).file_name()).unwrap());
        std::fs::write(&conflict,b"different existing file").unwrap();
        assert!(super::super::library_backup::restore_files(Path::new(&report.path),&target).is_err());
        assert_eq!(std::fs::read(&conflict).unwrap(),b"different existing file");
        assert!(!target.join(Path::new(anchor).file_name().unwrap()).exists(),"conflicts must be found before publishing any files");
        std::fs::remove_file(&conflict).unwrap();
        let restored_rows=super::super::library_backup::restore_files(Path::new(&report.path),&target).unwrap();
        let restored_anchor=restored_rows[0].audio_path.clone().unwrap();
        let restored_files=super::super::audio_artifacts::backup_files_at(&target.canonicalize().unwrap(),&[restored_anchor]).unwrap();
        assert_eq!(restored_files.len(),1);
        let restored_original=verify_original(&restored_rows[0],&target.canonicalize().unwrap()).unwrap();
        assert_eq!(std::fs::read(restored_original).unwrap(),original);
        let mut restored_snapshot=snapshot.clone();restored_snapshot.host.sessions=restored_rows;
        let restored_export=dir.join("restored-original.wav");
        super::super::audio_export::export(&restored_snapshot,&row.id,&restored_export).unwrap();
        assert_eq!(std::fs::read(restored_export).unwrap(),original);
        std::env::set_var("COMPANION_TYPE_RECORDING_DIR",&recordings);
        assert_eq!(std::fs::read(&input).unwrap(),original);let moved=dir.join("moved-user-original.wav");std::fs::rename(&input,&moved).unwrap();
        let mut reopened=super::super::FixtureCompanionBackend::new().snapshot().unwrap();
        reopened.host.selected_session_id=Some(row.id.clone());
        let restored=reopened.host.sessions.iter().find(|s|s.id==row.id).unwrap();assert_eq!(restored.source,"importedAudio");
        assert!(super::super::meeting_workspace::local_audio_path(&reopened,&row.id).unwrap().is_file());
        assert_eq!(super::super::transcription_chunk_paths(restored).unwrap(),vec![anchor.clone()]);
        let owned=verify_original(restored,&recordings.canonicalize().unwrap()).unwrap();
        let manager=super::super::privacy::PrivacyManager::for_handoff_test(recordings.canonicalize().unwrap(),dir.join("legacy"));
        let removed=manager.erase_selected_audio(&reopened);assert_eq!(removed.failed_files,0);
        assert!(!owned.exists() && !Path::new(anchor).exists());assert_eq!(std::fs::read(moved).unwrap(),original);
        if let Some(value)=old_recordings {std::env::set_var("COMPANION_TYPE_RECORDING_DIR",value);} else {std::env::remove_var("COMPANION_TYPE_RECORDING_DIR");}
        if let Some(value)=old_state {std::env::set_var("COMPANION_TYPE_STATE_PATH",value);} else {std::env::remove_var("COMPANION_TYPE_STATE_PATH");}
        std::fs::remove_dir_all(dir).unwrap();
    }
    #[test]
    #[ignore = "uses caller supplied synthetic media file"]
    fn decode_synthetic_format_fixture() {
        let src=std::path::PathBuf::from(std::env::var_os("COMPANION_IMPORT_TEST_INPUT").unwrap());
        let dst=std::path::PathBuf::from(std::env::var_os("COMPANION_IMPORT_TEST_OUTPUT").unwrap());
        let parts=decode_to_speech_wav(&src,&dst).unwrap();assert_eq!(parts.len(),1);
        let ms=super::super::meeting_workspace::wav_duration_ms(&dst).unwrap();
        let expected=std::env::var("COMPANION_IMPORT_EXPECT_MS").ok().and_then(|v|v.parse::<u64>().ok()).unwrap_or(2000);
        assert!(ms.abs_diff(expected)<=150,"decoded duration {ms}, expected {expected}");
    }
    #[test]
    fn cancelling_stops_conversion_without_touching_source() {
        let dir=std::env::temp_dir().join(format!("companion-import-cancel-{}",uuid::Uuid::new_v4()));std::fs::create_dir(&dir).unwrap();
        let src=dir.join("source.wav");let dst=dir.join("result.wav");std::fs::write(&src,b"unchanged source").unwrap();
        let guard=ImportGuard::begin().unwrap();assert!(cancel());assert!(decode_to_speech_wav(&src,&dst).is_err());drop(guard);
        assert!(!cancel());assert!(!dst.exists());assert_eq!(std::fs::read(&src).unwrap(),b"unchanged source");std::fs::remove_dir_all(dir).unwrap();
    }
    #[test]
    #[ignore = "imports an explicitly supplied public long meeting to an isolated directory"]
    fn public_long_meeting_reopens_with_original_and_full_duration() {
        use crate::backend::CompanionBackend;
        let input=PathBuf::from(std::env::var_os("COMPANION_IMPORT_TEST_INPUT").unwrap());
        let dir=PathBuf::from(std::env::var_os("COMPANION_IMPORT_TEST_DIRECTORY").unwrap());
        let expected=std::env::var("COMPANION_IMPORT_EXPECT_MS").unwrap().parse::<u64>().unwrap();
        std::fs::create_dir(&dir).unwrap();let root=dir.join("recordings");std::fs::create_dir(&root).unwrap();
        std::env::set_var("COMPANION_TYPE_RECORDING_DIR",&root);std::env::set_var("COMPANION_TYPE_STATE_PATH",dir.join("sessions.json"));
        let source_identity=super::super::audio_storage::fingerprint(&input).unwrap();
        let backend=super::super::FixtureCompanionBackend::new();
        {let mut snapshot=backend.snapshot.lock().unwrap();snapshot.host.sessions.clear();snapshot.host.selected_session_id=None;}
        let snapshot=backend.import_audio_file(&input).unwrap();let row=&snapshot.host.sessions[0];
        assert_eq!(row.source,"importedAudio");assert!(row.duration_ms.abs_diff(expected)<=150,"duration {} expected {expected}",row.duration_ms);
        let copied=verify_original(row,&root.canonicalize().unwrap()).unwrap();
        assert_eq!(super::super::audio_storage::fingerprint(&copied).unwrap(),source_identity);
        assert_eq!(super::super::audio_storage::fingerprint(&input).unwrap(),source_identity);
        let reopened=super::super::FixtureCompanionBackend::new().snapshot().unwrap();
        assert!(super::super::meeting_workspace::local_audio_path(&reopened,&row.id).unwrap().is_file());
        let paths=super::super::transcription_chunk_paths(&reopened.host.sessions[0]).unwrap();assert!(!paths.is_empty());
        std::fs::write(dir.join("result.json"),serde_json::to_vec_pretty(&serde_json::json!({"sourceUnchanged":true,"durationMs":row.duration_ms,"originalCopied":true,"reopened":true,"transcriptionPaths":paths.len(),"inputBytes":source_identity.0})).unwrap()).unwrap();
    }
    #[test]
    fn truncated_wav_is_not_presented_as_complete() {
        let dir=std::env::temp_dir().join(format!("companion-import-truncated-{}",uuid::Uuid::new_v4()));std::fs::create_dir(&dir).unwrap();
        let src=dir.join("truncated.wav");let dst=dir.join("decoded.wav");
        let mut w=denzic_host_audio_v1_core::wav::WavWriter::create(&src).unwrap();
        w.append_samples(&vec![500;16000]).unwrap();w.finalize().unwrap();drop(w);
        let file=std::fs::OpenOptions::new().write(true).open(&src).unwrap();file.set_len(16044).unwrap();drop(file);
        let original=std::fs::read(&src).unwrap();assert!(decode_to_speech_wav(&src,&dst).is_err());
        assert!(!dst.exists());assert_eq!(std::fs::read(&src).unwrap(),original);std::fs::remove_dir_all(dir).unwrap();
    }
    #[test]
    fn valid_wav_decodes_and_source_remains_unchanged() {
        let dir=std::env::temp_dir().join(format!("companion-import-{}",uuid::Uuid::new_v4()));std::fs::create_dir(&dir).unwrap();
        let src=dir.join("chosen.wav");let dst=dir.join("decoded.wav");
        let mut w=denzic_host_audio_v1_core::wav::WavWriter::create(&src).unwrap();
        let input=(0..16000).map(|i|(((i as f32)*0.1).sin()*8000.0) as i16).collect::<Vec<_>>();
        w.append_samples(&input).unwrap();w.finalize().unwrap();drop(w);
        let before=std::fs::read(&src).unwrap();let parts=decode_to_speech_wav(&src,&dst).unwrap();
        assert_eq!(parts.len(),1);assert_eq!(parts[0].samples,16000);assert_eq!(std::fs::read(&src).unwrap(),before);
        assert_eq!(super::super::meeting_workspace::wav_duration_ms(&dst).unwrap(),1000);
        std::fs::remove_dir_all(dir).unwrap();
    }
}
