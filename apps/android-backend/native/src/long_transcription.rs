//! Sequential, provider-safe transcription of a local 16 kHz mono WAV.
use std::{fs::File,io::{Read,Seek,SeekFrom},path::Path};

const BYTES_PER_SECOND:u64=32_000;
const SPLIT_THRESHOLD:u64=45*BYTES_PER_SECOND;
const SEGMENT_BYTES:u64=30*BYTES_PER_SECOND;

// These explicit WebSocket handshake rejections happen before any audio is
// uploaded. Do not retry ambiguous connection failures after a possible upload.
fn transient_handshake(error:&str)->bool {
    [429,500,502,503,504].iter().any(|status|error==format!("Volcengine ws connect failed: HTTP {status}"))
}

/// A failure returns no complete transcript; the caller retains the original WAV.
pub(super) fn transcribe_cached<F>(path:&Path,cache:Option<&super::asr_cache::Cache>,send:F)->Result<String,String>
where F:FnMut(&[u8])->Result<String,String> {
    transcribe_file(path,cache,send,|_|Ok(()))
}

pub(super) const CANCELLED:&str="云端转写已停止；原录音保留，已保存的片段可复用。";

fn transcribe_file<F,P>(path:&Path,cache:Option<&super::asr_cache::Cache>,mut send:F,mut progress:P)->Result<String,String>
where F:FnMut(&[u8])->Result<String,String>,P:FnMut(u64)->Result<(),String> {
    let mut file=File::open(path).map_err(|e|format!("open recording: {e}"))?;
    let (start,length)=pcm_range(&mut file)?;
    let step=if length>SPLIT_THRESHOLD {SEGMENT_BYTES}else{length};
    let mut remaining=length;let mut text=Vec::new();file.seek(SeekFrom::Start(start)).map_err(|e|e.to_string())?;
    while remaining>0 {
        let count=remaining.min(step) as usize;let mut pcm=vec![0;count];
        file.read_exact(&mut pcm).map_err(|_|"recording was truncated during transcription".to_string())?;
        let completed=if let Some(value)=cache.and_then(|store|store.lookup(&pcm)) {value} else {
            let first=send(&pcm);
            let attempt=match first {
                // An explicit pre-upload failure can be retried; first let the
                // user cancel so a stopped job cannot start another request.
                Err(ref error) if transient_handshake(error)=>{progress(length-remaining)?;send(&pcm)},
                other=>other,
            };
            let value=match attempt {
                Ok(value) if !value.trim().is_empty()=>super::asr_cache::Completed::Text(value),
                Ok(_)=>return Err("speech recognition returned an empty result".into()),
                Err(error) if super::volcengine::is_no_speech_error(&error)=>super::asr_cache::Completed::Silence,
                Err(error)=>return Err(error),
            };
            if let Some(store)=cache {store.save(&pcm,&value);}
            value
        };
        match completed {super::asr_cache::Completed::Text(value)=>text.push(value),super::asr_cache::Completed::Silence=>{}}
        remaining-=count as u64;
        progress(length-remaining)?;
    }
    if text.is_empty(){return Err(super::volcengine::NO_SPEECH_ERROR.into());}
    Ok(text.join("\n"))
}

/// Submit every verified part in order. Preflight the whole set before any upload.
pub(super) fn transcribe_cached_files<F>(paths:&[std::path::PathBuf],cache:Option<&super::asr_cache::Cache>,send:F)->Result<String,String>
where F:FnMut(&[u8])->Result<String,String> {
    transcribe_cached_files_observed(paths,cache,send,|_,_|Ok(()))
}

/// Report processed audio duration. Cancellation is honored before upload and
/// after each saved window; already-sent requests cannot be recalled.
pub(super) fn transcribe_cached_files_observed<F,P>(paths:&[std::path::PathBuf],cache:Option<&super::asr_cache::Cache>,mut send:F,mut progress:P)->Result<String,String>
where F:FnMut(&[u8])->Result<String,String>,P:FnMut(u64,u64)->Result<(),String> {
    if paths.is_empty() || paths.iter().any(|p|!p.is_absolute()) {return Err("invalid recording parts".into());}
    let mut lengths=Vec::with_capacity(paths.len());let mut total=0u64;
    for path in paths {
        let mut file=File::open(path).map_err(|e|format!("open recording: {e}"))?;
        let (_,len)=pcm_range(&mut file)?;total=total.checked_add(len).ok_or("recording duration is too large")?;lengths.push(len);
    }
    let total_ms=u64::try_from((total as u128+31)/32).map_err(|_|"recording duration is too large")?;
    if total_ms>i64::MAX as u64{return Err("recording duration is too large".into());}
    progress(0,total_ms)?;
    let mut text=Vec::new();let mut base=0u64;
    for (path,length) in paths.iter().zip(lengths) {
        let result=transcribe_file(path,cache,&mut send,|done| {
            let bytes=base.checked_add(done).ok_or("recording duration is too large")?;
            let ms=if bytes==total {total_ms}else{bytes/32};
            progress(ms,total_ms)
        });
        match result {Ok(value)=>text.push(value),Err(error) if error==super::volcengine::NO_SPEECH_ERROR=>{},Err(error)=>return Err(error)}
        base=base.checked_add(length).ok_or("recording duration is too large")?;
    }
    if text.is_empty(){return Err(super::volcengine::NO_SPEECH_ERROR.into());}
    Ok(text.join("\n"))
}

fn pcm_range(file:&mut File)->Result<(u64,u64),String> {
    let length=file.metadata().map_err(|e|e.to_string())?.len();let mut header=[0u8;12];
    file.read_exact(&mut header).map_err(|_|"incomplete WAV header")?;
    if &header[..4]!=b"RIFF"||&header[8..]!=b"WAVE" {return Err("invalid WAV recording".into());}
    let declared=u64::from(u32::from_le_bytes(header[4..8].try_into().unwrap()))+8;
    if declared>length||declared<12{return Err("WAV recording is truncated".into());}
    let mut at=12u64;let mut format_valid=false;let mut data=None;
    while at.checked_add(8).is_some_and(|end|end<=declared) {
        file.seek(SeekFrom::Start(at)).map_err(|e|e.to_string())?;let mut chunk=[0u8;8];
        file.read_exact(&mut chunk).map_err(|_|"incomplete WAV chunk")?;
        let size=u64::from(u32::from_le_bytes(chunk[4..8].try_into().unwrap()));let start=at+8;
        let end=start.checked_add(size).ok_or("invalid WAV chunk size")?;
        if end>declared{return Err("WAV recording is truncated".into());}
        if &chunk[..4]==b"fmt " {
            if size<16||format_valid{return Err("invalid or duplicate WAV format".into());}
            let mut format=[0u8;16];file.read_exact(&mut format).map_err(|_|"incomplete WAV format")?;
            let u16at=|i|u16::from_le_bytes([format[i],format[i+1]]);
            let u32at=|i|u32::from_le_bytes(format[i..i+4].try_into().unwrap());
            format_valid=u16at(0)==1&&u16at(2)==1&&u32at(4)==16000&&u32at(8)==32000&&u16at(12)==2&&u16at(14)==16;
            if !format_valid{return Err("recording must be 16 kHz mono PCM WAV".into());}
        } else if &chunk[..4]==b"data" {
            if data.is_some()||size==0||size%2!=0{return Err("invalid or duplicate WAV audio data".into());}
            data=Some((start,size));
        }
        at=end.checked_add(size&1).ok_or("invalid WAV padding")?;
        if at>declared{return Err("WAV recording is truncated".into());}
    }
    if !format_valid||at!=declared{return Err("invalid WAV format or trailing chunk".into());}
    data.ok_or_else(||"WAV recording has no audio data".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{fs,io::Write,sync::atomic::Ordering};
    fn transcribe<F>(path:&Path,send:F)->Result<String,String> where F:FnMut(&[u8])->Result<String,String> {super::transcribe_cached(path,None,send)}
    fn fixture(seconds:usize)->(std::path::PathBuf,Vec<u8>) {
        let path=std::env::temp_dir().join(format!("companion-asr-fixture-{}-{}.wav",std::process::id(),super::super::TEMP_COUNTER.fetch_add(1,Ordering::Relaxed)));
        let pcm=(0..seconds*BYTES_PER_SECOND as usize).map(|i|(i%251) as u8).collect::<Vec<_>>();
        let mut f=File::create(&path).unwrap();f.write_all(&super::super::wav_header(pcm.len() as u32)).unwrap();f.write_all(&pcm).unwrap();(path,pcm)
    }
    #[test] fn progress_cancel_and_resume_preserve_cached_windows_and_all_parts() {
        let (first,first_pcm)=fixture(70);let (last,last_pcm)=fixture(2);
        let dir=first.with_extension("observed-cache");
        let cache=super::super::asr_cache::Cache::new(&dir,&serde_json::json!({"account":"fake"})).unwrap();
        let paths=[first.clone(),last.clone()];let mut calls=0;let mut progress=Vec::new();
        let result=transcribe_cached_files_observed(&paths,Some(&cache),|_|{calls+=1;Ok("done".into())},|done,total|{
            progress.push((done,total));if done>=30_000 {Err(CANCELLED.into())}else{Ok(())}
        });
        assert_eq!(result.unwrap_err(),CANCELLED);assert_eq!(calls,1);assert_eq!(progress,vec![(0,72_000),(30_000,72_000)]);
        calls=0;progress.clear();let result=transcribe_cached_files_observed(&paths,Some(&cache),|_|{calls+=1;Ok("done".into())},|done,total|{progress.push((done,total));Ok(())}).unwrap();
        assert_eq!(calls,3,"only unfinished windows are submitted again");assert_eq!(result,"done\ndone\ndone\ndone");
        assert_eq!(progress,vec![(0,72_000),(30_000,72_000),(60_000,72_000),(70_000,72_000),(72_000,72_000)]);
        assert_eq!(&fs::read(&first).unwrap()[44..],&first_pcm);assert_eq!(&fs::read(&last).unwrap()[44..],&last_pcm);
        for entry in fs::read_dir(&dir).unwrap(){fs::remove_file(entry.unwrap().path()).unwrap();}fs::remove_dir(dir).unwrap();fs::remove_file(first).unwrap();fs::remove_file(last).unwrap();
    }
    #[test] fn cancellation_before_transient_retry_stops_another_request() {
        let (path,_)=fixture(2);let mut calls=0;let mut observations=0;
        let result=transcribe_cached_files_observed(&[path.clone()],None,|_|{calls+=1;Err("Volcengine ws connect failed: HTTP 503".into())},|_,_|{
            observations+=1;if observations==2 {Err(CANCELLED.into())}else{Ok(())}
        });
        assert_eq!(result.unwrap_err(),CANCELLED);assert_eq!(calls,1);fs::remove_file(path).unwrap();
    }
    #[test] fn ordered_files_check_all_before_upload_and_do_not_hide_failures() {
        let (first,_)=fixture(2);let (last,_)=fixture(3);let missing=first.with_extension("missing");
        let mut calls=0;
        assert!(transcribe_cached_files(&[first.clone(),missing],None,|_|{calls+=1;Ok("unexpected".into())}).is_err());assert_eq!(calls,0);
        let text=transcribe_cached_files(&[first.clone(),last.clone()],None,|pcm|{calls+=1;Ok(format!("{}",pcm.len()))}).unwrap();
        assert_eq!(text,"64000\n96000");assert_eq!(calls,2);
        calls=0;assert!(transcribe_cached_files(&[first.clone(),last.clone()],None,|_|{calls+=1;if calls==2{Err("network error".into())}else{Ok("first".into())}}).is_err());assert_eq!(calls,2);
        calls=0;let text=transcribe_cached_files(&[first.clone(),last.clone()],None,|_|{calls+=1;if calls==1{Err(super::super::volcengine::NO_SPEECH_ERROR.into())}else{Ok("second".into())}}).unwrap();
        assert_eq!(text,"second");assert_eq!(calls,2);
        fs::remove_file(first).unwrap();fs::remove_file(last).unwrap();
    }
    #[test] fn duplicate_data_or_damaged_tail_never_submits_partial_recording() {
        let (path,_) = fixture(2);let valid=fs::read(&path).unwrap();
        let mut duplicate=valid.clone();duplicate.extend_from_slice(b"data\x02\0\0\0\x01\x02");
        let size=(duplicate.len() as u32-8).to_le_bytes();duplicate[4..8].copy_from_slice(&size);fs::write(&path,&duplicate).unwrap();
        let mut calls=0;assert!(transcribe(&path,|_|{calls+=1;Ok("partial".into())}).is_err());assert_eq!(calls,0);
        let mut bad_tail=valid.clone();bad_tail.extend_from_slice(b"LIST\x10\0\0\0x");
        let size=(bad_tail.len() as u32-8).to_le_bytes();bad_tail[4..8].copy_from_slice(&size);fs::write(&path,&bad_tail).unwrap();
        calls=0;assert!(transcribe(&path,|_|{calls+=1;Ok("partial".into())}).is_err());assert_eq!(calls,0);
        let mut valid_metadata=valid.clone();valid_metadata.extend_from_slice(b"LIST\x03\0\0\0abc\0");
        let size=(valid_metadata.len() as u32-8).to_le_bytes();valid_metadata[4..8].copy_from_slice(&size);fs::write(&path,&valid_metadata).unwrap();
        calls=0;assert_eq!(transcribe(&path,|_|{calls+=1;Ok("ok".into())}).unwrap(),"ok");assert_eq!(calls,1);
        // Preserve tolerated extra bytes outside RIFF, and accept valid chunks
        // in either order after the complete declared structure is checked.
        let mut outside=valid.clone();outside.extend_from_slice(b"external trailing tag");fs::write(&path,&outside).unwrap();
        calls=0;assert_eq!(transcribe(&path,|_|{calls+=1;Ok("ok".into())}).unwrap(),"ok");assert_eq!(calls,1);
        let mut reordered=valid[..12].to_vec();reordered.extend_from_slice(&valid[36..]);reordered.extend_from_slice(&valid[12..36]);
        fs::write(&path,&reordered).unwrap();calls=0;assert_eq!(transcribe(&path,|_|{calls+=1;Ok("ok".into())}).unwrap(),"ok");assert_eq!(calls,1);
        fs::remove_file(path).unwrap();
    }
    #[test] fn chunks_preserve_every_byte_and_transcript_order() {
        let (path,pcm)=fixture(70);let mut received=Vec::new();let mut lengths=Vec::new();
        let result=transcribe(&path,|chunk|{lengths.push(chunk.len());received.extend_from_slice(chunk);Ok(format!("part{}",lengths.len()))}).unwrap();
        assert_eq!(lengths,[960_000,960_000,320_000]);assert_eq!(received,pcm);assert_eq!(result,"part1\npart2\npart3");fs::remove_file(path).unwrap();
    }
    #[test] fn short_audio_one_request_and_truncated_audio_no_request() {
        let (path,_)=fixture(2);let mut calls=0;assert_eq!(transcribe(&path,|_|{calls+=1;Ok("ok".into())}).unwrap(),"ok");assert_eq!(calls,1);
        let f=std::fs::OpenOptions::new().write(true).open(&path).unwrap();let len=f.metadata().unwrap().len();f.set_len(len-1).unwrap();drop(f);
        calls=0;assert!(transcribe(&path,|_|{calls+=1;Ok("should not send".into())}).is_err());assert_eq!(calls,0);fs::remove_file(path).unwrap();
    }
    #[test] fn failure_stops_future_requests_and_explicit_silence_is_not_failure() {
        let (path,_)=fixture(70);let mut calls=0;
        assert!(transcribe(&path,|_|{calls+=1;if calls==2 {Err("Volcengine auth rejected (HTTP 401)".into())}else{Ok("first".into())}}).is_err());assert_eq!(calls,2);
        calls=0;let result=transcribe(&path,|_|{calls+=1;if calls==2{Err(super::super::volcengine::NO_SPEECH_ERROR.into())}else{Ok(format!("part{calls}"))}}).unwrap();
        assert_eq!(result,"part1\npart3");fs::remove_file(path).unwrap();
    }
    #[test] fn threshold_stays_single_and_unconfirmed_empty_is_an_error() {
        let (path,_)=fixture(45);let mut calls=0;
        assert!(transcribe(&path,|pcm|{calls+=1;assert_eq!(pcm.len(),45*32000);Ok(String::new())}).is_err());
        assert_eq!(calls,1);fs::remove_file(path).unwrap();
    }
    #[test] fn transient_handshake_failure_gets_one_retry_without_repeating_auth_or_silence() {
        let (path,_)=fixture(2);let mut calls=0;
        let text=transcribe(&path,|_|{calls+=1;if calls==1{Err("Volcengine ws connect failed: HTTP 503".into())}else{Ok("成功".into())}}).unwrap();
        assert_eq!(text,"成功");assert_eq!(calls,2);
        for error in ["Volcengine auth rejected (HTTP 401). Check credentials", "Volcengine ASR completed without recognized speech", "Volcengine network connection failed"] {
            calls=0;assert!(transcribe(&path,|_|{calls+=1;Err(error.into())}).is_err());assert_eq!(calls,1,"{error}");
        }
        calls=0;assert!(transcribe(&path,|_|{calls+=1;Err("Volcengine ws connect failed: HTTP 503".into())}).is_err());assert_eq!(calls,2);
        fs::remove_file(path).unwrap();
    }
    #[test] fn long_recording_retries_only_rejected_chunk_and_reuses_completed_cache() {
        let (path,_)=fixture(70);let cache_dir=path.with_extension("cache");
        let cache=super::super::asr_cache::Cache::new(&cache_dir,&serde_json::json!({"account":"synthetic"})).unwrap();
        let mut lengths=Vec::new();let mut second=Vec::new();
        let result=transcribe_cached(&path,Some(&cache),|pcm|{lengths.push(pcm.len());
            if lengths.len()==2 {second=pcm.to_vec();return Err("Volcengine ws connect failed: HTTP 503".into());}
            if lengths.len()==3 {assert_eq!(pcm,second);}
            Ok(format!("part{}",if lengths.len()==4{3}else{lengths.len().min(2)}))
        }).unwrap();
        assert_eq!(result,"part1\npart2\npart3");assert_eq!(lengths,[960_000,960_000,960_000,320_000]);
        let mut calls=0;assert_eq!(transcribe_cached(&path,Some(&cache),|_|{calls+=1;Err("unexpected request".into())}).unwrap(),result);assert_eq!(calls,0);
        for entry in fs::read_dir(&cache_dir).unwrap(){fs::remove_file(entry.unwrap().path()).unwrap();}fs::remove_dir(cache_dir).unwrap();fs::remove_file(path).unwrap();
    }
    #[test] fn interrupted_requests_reuse_only_completed_chunks_for_same_profile() {
        let (path,_)=fixture(70);let cache_dir=path.with_extension("cache");
        let cache=super::super::asr_cache::Cache::new(&cache_dir,&serde_json::json!({"account":"fake-a","model":"fake"})).unwrap();
        let mut calls=0;
        assert!(super::transcribe_cached(&path,Some(&cache),|_|{calls+=1;if calls==2{Err("connection failed".into())}else{Ok("first".into())}}).is_err());assert_eq!(calls,2);
        drop(cache);let cache=super::super::asr_cache::Cache::new(&cache_dir,&serde_json::json!({"account":"fake-a","model":"fake"})).unwrap();
        calls=0;let text=super::transcribe_cached(&path,Some(&cache),|_|{calls+=1;Ok(format!("resumed{calls}"))}).unwrap();
        assert_eq!(calls,2);assert_eq!(text,"first\nresumed1\nresumed2");
        for entry in fs::read_dir(&cache_dir).unwrap(){let bytes=fs::read(entry.unwrap().path()).unwrap();assert!(!String::from_utf8(bytes).unwrap().contains("fake-a"));}
        calls=0;assert_eq!(super::transcribe_cached(&path,Some(&cache),|_|{calls+=1;Err("unexpected request".into())}).unwrap(),text);assert_eq!(calls,0);
        let other=super::super::asr_cache::Cache::new(&cache_dir,&serde_json::json!({"account":"fake-b","model":"fake"})).unwrap();
        calls=0;super::transcribe_cached(&path,Some(&other),|_|{calls+=1;Ok("new profile".into())}).unwrap();assert_eq!(calls,3);
        for entry in fs::read_dir(&cache_dir).unwrap(){fs::remove_file(entry.unwrap().path()).unwrap();}fs::remove_dir(cache_dir).unwrap();fs::remove_file(path).unwrap();
    }
    #[test] fn damaged_cache_is_repaired_by_the_next_successful_recognition() {
        let (path,_)=fixture(2);let cache_dir=path.with_extension("cache");
        let cache=super::super::asr_cache::Cache::new(&cache_dir,&serde_json::json!({"account":"fake"})).unwrap();
        let mut calls=0;
        super::transcribe_cached(&path,Some(&cache),|_|{calls+=1;Ok("original".into())}).unwrap();
        let entry=fs::read_dir(&cache_dir).unwrap().next().unwrap().unwrap().path();
        fs::write(entry,b"damaged").unwrap();
        assert_eq!(super::transcribe_cached(&path,Some(&cache),|_|{calls+=1;Ok("recovered".into())}).unwrap(),"recovered");
        assert_eq!(super::transcribe_cached(&path,Some(&cache),|_|{calls+=1;Ok("unexpected".into())}).unwrap(),"recovered");
        assert_eq!(calls,2);
        for entry in fs::read_dir(&cache_dir).unwrap(){fs::remove_file(entry.unwrap().path()).unwrap();}fs::remove_dir(cache_dir).unwrap();fs::remove_file(path).unwrap();
    }
}
