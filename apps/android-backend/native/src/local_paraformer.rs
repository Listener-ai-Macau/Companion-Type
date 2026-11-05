//! Candidate local mobile recognition. Call only on a worker; no network is used.
use std::{
    fs::File,
    io::{Read, Seek, SeekFrom},
    path::{Path, PathBuf},
};
// Mobile's independently delivered model contract is pinned to the desktop
// 0.1.7 runtime; the mobile source tree retains its earlier Windows app.
#[path = "paraformer_shared.rs"]
mod shared;
use shared::{cut_samples, is_digital_silence, wav_data, ModelKind, Runtime, RATE};

#[derive(serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub(super) struct TimedTranscript {
    pub schema: u32,
    pub text: String,
    pub provider: String,
    pub duration_ms: u64,
    pub segments: Vec<TimedSegment>,
    pub unrecognized: Vec<UnrecognizedRange>,
}

#[derive(serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub(super) struct UnrecognizedRange {
    pub start_ms: u64,
    pub end_ms: u64,
}

#[derive(serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub(super) struct TimedSegment {
    pub text: String,
    pub start_ms: u64,
    pub end_ms: u64,
    // The range is the recognition input window, not word-level timing.
    pub approximate_timing: bool,
}

fn timed_segment(text: String, start: u64, end: u64) -> Result<TimedSegment, String> {
    if start % 2 != 0 || end % 2 != 0 || end <= start || text.trim().is_empty() {
        return Err("本地转写时间范围无效，原录音保留。".into());
    }
    let start_ms = u64::try_from((start as u128 / 2) * 1000 / RATE as u128)
        .map_err(|_| "录音时间范围过大。")?;
    let end_ms = u64::try_from(((end as u128 / 2) * 1000 + RATE as u128 - 1) / RATE as u128)
        .map_err(|_| "录音时间范围过大。")?;
    Ok(TimedSegment { text, start_ms, end_ms, approximate_timing: true })
}

pub(super) fn transcribe(
    wav: &Path,
    model_dir: &Path,
    runtime_dir: &Path,
    cache_dir: &Path,
) -> Result<String, String> {
    Ok(transcribe_detailed(wav, model_dir, runtime_dir, cache_dir)?.text)
}

pub(super) fn transcribe_detailed(
    wav: &Path,
    model_dir: &Path,
    runtime_dir: &Path,
    cache_dir: &Path,
) -> Result<TimedTranscript, String> {
    transcribe_detailed_files(&[wav.to_path_buf()], model_dir, runtime_dir, cache_dir)
}

// Validate the complete ordered input before loading a model or returning any result.
fn inspect_files(wavs: &[PathBuf]) -> Result<Vec<(u64, u64)>, String> {
    if wavs.is_empty() || wavs.iter().any(|p| !p.is_absolute()) {
        return Err("录音需要使用应用内的完整路径。".into());
    }
    wavs.iter().map(|path| {
        let mut file = File::open(path).map_err(|e| e.to_string())?;
        wav_data(&mut file)
    }).collect()
}

fn process_files<F, P>(wavs: &[PathBuf], metadata: &[(u64, u64)], mut recognize: F, mut progress: P)
    -> Result<(String, u64, Vec<TimedSegment>, Vec<UnrecognizedRange>), String>
where F: FnMut(&[u8]) -> Result<Option<String>, String>,
      P: FnMut(u64) -> Result<(), String> {
    let mut base = 0u64;
    let mut parts = Vec::new();
    let mut segments = Vec::new();
    let mut unrecognized: Vec<UnrecognizedRange> = Vec::new();
    for (wav, &(start, len)) in wavs.iter().zip(metadata) {
        let mut file = File::open(wav).map_err(|e| e.to_string())?;
        if wav_data(&mut file)? != (start, len) { return Err("录音已变化，原录音保留。".into()); }
        let mut offset = 0u64;
        while offset < len {
            let count = (len - offset).min((20 * RATE * 2 + 2) as u64) as usize;
            let mut pcm = vec![0u8; count];
            file.seek(SeekFrom::Start(start + offset)).map_err(|e| e.to_string())?;
            file.read_exact(&mut pcm).map_err(|_| "录音读取中断，原录音保留。")?;
            let cut = cut_samples(&pcm);
            pcm.truncate(cut * 2);
            if pcm.is_empty() { return Err("本地转写分段失败，原录音保留。".into()); }
            let end = offset.checked_add(pcm.len() as u64).ok_or("录音时间范围过大。")?;
            if !is_digital_silence(&pcm) {
                let global_start = base.checked_add(offset).ok_or("录音时间范围过大。")?;
                let global_end = base.checked_add(end).ok_or("录音时间范围过大。")?;
                if let Some(text) = recognize(&pcm)? {
                    segments.push(timed_segment(text.clone(), global_start, global_end)?);
                    parts.push(text);
                } else {
                    // An empty recognition result may be silence or missed speech.
                    // Keep the original timeline so the caller can offer playback.
                    let start_ms = u64::try_from((global_start as u128 / 2) * 1000 / RATE as u128)
                        .map_err(|_| "录音时间范围过大。")?;
                    let end_ms = ((global_end as u128 / 2) * 1000 + RATE as u128 - 1) / RATE as u128;
                    let end_ms = u64::try_from(end_ms).map_err(|_| "录音时间范围过大。")?;
                    if let Some(last) = unrecognized.last_mut().filter(|r| r.end_ms >= start_ms) {
                        last.end_ms = end_ms;
                    } else {
                        unrecognized.push(UnrecognizedRange { start_ms, end_ms });
                    }
                }
            }
            offset = end;
            progress(base.checked_add(end).ok_or("录音时间范围过大。")?)?;
        }
        base = base.checked_add(len).ok_or("录音时间范围过大。")?;
    }
    if parts.is_empty() { return Err("没有识别到语音，原录音保留。".into()); }
    let duration_ms = u64::try_from(((base as u128 / 2) * 1000 + RATE as u128 - 1) / RATE as u128)
        .map_err(|_| "录音时间范围过大。")?;
    Ok((parts.join("\n"), duration_ms, segments, unrecognized))
}

pub(super) const CANCELLED: &str = "本地转写已取消；原录音保留，已保存的片段可复用。";

pub(super) fn transcribe_detailed_files(
    wavs: &[PathBuf], model_dir: &Path, runtime_dir: &Path, cache_dir: &Path,
) -> Result<TimedTranscript, String> {
    transcribe_detailed_files_observed(wavs, model_dir, runtime_dir, cache_dir, |_, _| Ok(()))
}

pub(super) fn transcribe_detailed_files_observed<F>(
    wavs: &[PathBuf], model_dir: &Path, runtime_dir: &Path, cache_dir: &Path, mut progress: F,
) -> Result<TimedTranscript, String>
where F: FnMut(u64, u64) -> Result<(), String> {
    if !model_dir.is_absolute()
        || (!runtime_dir.as_os_str().is_empty() && !runtime_dir.is_absolute())
        || !cache_dir.is_absolute()
    { return Err("本地模型及缓存需要使用应用内的完整路径。".into()); }
    let metadata = inspect_files(wavs)?;
    let total_bytes = metadata.iter().try_fold(0u64, |sum, &(_, len)|
        sum.checked_add(len).ok_or("录音时间范围过大。"))?;
    let total_ms = u64::try_from(((total_bytes as u128 / 2) * 1000 + RATE as u128 - 1) / RATE as u128)
        .map_err(|_| "录音时间范围过大。")?;
    if total_ms > i64::MAX as u64 { return Err("录音时间范围过大。".into()); }
    progress(0, total_ms)?;
    let preferred = ModelKind::available(model_dir);
    let mut first_error=None;
    let mut selected=None;
    for (index,kind) in [preferred,ModelKind::SenseVoice,ModelKind::Paraformer].into_iter().enumerate() {
        if index>0 && kind==preferred {continue;}
        match Runtime::load_model(model_dir,runtime_dir,kind) {
            Ok(runtime)=>{selected=Some((runtime,kind));break;},
            Err(error)=>if first_error.is_none(){first_error=Some(error);},
        }
    }
    let (runtime,kind)=selected.ok_or_else(||first_error.unwrap_or_else(||"本地转写模型不可用。".into()))?;
    let cache = super::asr_cache::Cache::optional(cache_dir, &serde_json::json!({
        "provider":kind.provider(), "model":kind.model_hash(), "runtime":"sherpa-onnx-1.13.1", "segmentation":"quiet-16s-v1"
    }));
    let (text, duration_ms, segments, unrecognized) = process_files(wavs, &metadata, |pcm| {
        let completed = match cache.as_ref().and_then(|cache|cache.lookup(pcm)) {
            Some(done) => done,
            None => {
                let text = runtime.transcribe(pcm)?;
                let done = if text.trim().is_empty() { super::asr_cache::Completed::Silence }
                    else { super::asr_cache::Completed::Text(text) };
                if let Some(cache)=&cache {cache.save(pcm, &done);}
                done
            }
        };
        Ok(match completed { super::asr_cache::Completed::Text(text) => Some(text), _ => None })
    }, |done_bytes| {
        let done_ms = if done_bytes == total_bytes { total_ms } else {
            u64::try_from((done_bytes as u128 / 2) * 1000 / RATE as u128)
                .map_err(|_| "录音时间范围过大。")?
        };
        progress(done_ms, total_ms)
    })?;
    Ok(TimedTranscript { schema: 1, text, provider: kind.provider().to_string(), duration_ms, segments, unrecognized })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn multipart_timing_silence_and_missing_files() {
        use std::io::Write;
        let dir = std::env::temp_dir().join(format!("mobile-parts-asr-{}-{:?}", std::process::id(), std::thread::current().id()));
        std::fs::create_dir(&dir).unwrap();
        let make_wav = |name: &str, samples: u32, value: i16| {
            let path = dir.join(name); let mut f = File::create(&path).unwrap();
            let bytes = samples * 2;
            f.write_all(b"RIFF").unwrap(); f.write_all(&(bytes + 36).to_le_bytes()).unwrap();
            f.write_all(b"WAVEfmt ").unwrap(); f.write_all(&16u32.to_le_bytes()).unwrap();
            f.write_all(&1u16.to_le_bytes()).unwrap(); f.write_all(&1u16.to_le_bytes()).unwrap();
            f.write_all(&16000u32.to_le_bytes()).unwrap(); f.write_all(&32000u32.to_le_bytes()).unwrap();
            f.write_all(&2u16.to_le_bytes()).unwrap(); f.write_all(&16u16.to_le_bytes()).unwrap();
            f.write_all(b"data").unwrap(); f.write_all(&bytes.to_le_bytes()).unwrap();
            for _ in 0..samples { f.write_all(&value.to_le_bytes()).unwrap(); } path
        };
        let files = vec![make_wav("first.wav",16000,1), make_wav("silent.wav",32000,0), make_wav("last.wav",16000,2)];
        let metadata = inspect_files(&files).unwrap();
        let (text,duration,segments,unrecognized) = process_files(&files,&metadata,|pcm| Ok(Some(format!("{}",pcm[0]))), |_| Ok(())).unwrap();
        assert_eq!(text,"1\n2"); assert_eq!(duration,4000);
        assert!(unrecognized.is_empty());
        assert_eq!(segments.iter().map(|s|(s.start_ms,s.end_ms)).collect::<Vec<_>>(),vec![(0,1000),(3000,4000)]);
        let (partial,_,_,gaps) = process_files(&files,&metadata,
            |pcm| if pcm[0]==1 {Ok(None)} else {Ok(Some("后面的文字".into()))}, |_| Ok(())).unwrap();
        assert_eq!(partial,"后面的文字");
        assert_eq!(gaps.iter().map(|r|(r.start_ms,r.end_ms)).collect::<Vec<_>>(),vec![(0,1000)]);
        let original:Vec<_>=files.iter().map(|p|std::fs::read(p).unwrap()).collect();
        let mut seen=Vec::new();let mut recognized=0;
        let cancelled=process_files(&files,&metadata,|_| {recognized+=1;Ok(Some("speech".into()))}, |done| {
            seen.push(done);if done>=96000 {Err(CANCELLED.into())}else{Ok(())}
        });
        assert!(matches!(cancelled,Err(error) if error==CANCELLED));assert_eq!(seen,vec![32000,96000]);assert_eq!(recognized,1);
        assert_eq!(files.iter().map(|p|std::fs::read(p).unwrap()).collect::<Vec<_>>(),original);
        let mut missing=files.clone(); missing.push(dir.join("missing.wav"));
        assert!(inspect_files(&missing).is_err());
        std::fs::write(dir.join("bad.wav"),b"broken").unwrap(); missing.pop();missing.push(dir.join("bad.wav"));
        assert!(inspect_files(&missing).is_err());
        std::fs::remove_file(&files[2]).unwrap();
        assert!(process_files(&files,&metadata,|_| Ok(Some("speech".into())), |_| Ok(())).is_err());
        std::fs::remove_dir_all(dir).unwrap();
    }
    #[test]
    #[ignore = "requires public speech and pinned local model/runtime"]
    fn real_multipart_public_speech_uses_original_timeline() {
        let base=PathBuf::from(std::env::var_os("COMPANION_MULTI_PUBLIC_BASE").unwrap());
        let root=PathBuf::from(std::env::var_os("COMPANION_MULTI_MODEL_ROOT").unwrap());
        let cache=PathBuf::from(std::env::var_os("COMPANION_MULTI_CACHE").unwrap());
        let files=[base.join("first.wav"),base.join("silence.wav"),base.join("last.wav")];
        let result=transcribe_detailed_files(&files,&root,&root,&cache).unwrap();
        assert_eq!(result.duration_ms,42000);
        assert!(result.segments.iter().any(|s|s.start_ms<20000));
        assert!(result.segments.iter().any(|s|s.start_ms>=22000 && s.end_ms<=42000));
        assert!(result.segments.iter().all(|s|s.end_ms<=20000 || s.start_ms>=22000));
        assert!(result.text.chars().count()>30);
    }
    #[test]
    #[ignore = "requires public speech, the existing real-card weak sample and pinned local model/runtime"]
    fn real_weak_middle_retains_other_speech_and_range() {
        let base=PathBuf::from(std::env::var_os("COMPANION_MULTI_PUBLIC_BASE").unwrap());
        let weak=PathBuf::from(std::env::var_os("COMPANION_WEAK_SAMPLE").unwrap());
        let root=PathBuf::from(std::env::var_os("COMPANION_MULTI_MODEL_ROOT").unwrap());
        let cache=PathBuf::from(std::env::var_os("COMPANION_MULTI_CACHE").unwrap());
        let files=[base.join("first.wav"),weak,base.join("last.wav")];
        let result=transcribe_detailed_files(&files,&root,&root,&cache).unwrap();
        assert_eq!(result.duration_ms,55000);
        assert!(result.segments.iter().any(|s|s.start_ms<20000));
        assert!(result.segments.iter().any(|s|s.start_ms>=35000));
        assert!(result.unrecognized.iter().any(|r|r.start_ms==20000 && r.end_ms==35000));
    }
    #[test]
    fn local_segments_use_original_sample_axis_and_mark_approximate() {
        let segment=timed_segment("第二段".into(), 22*RATE as u64*2, 42*RATE as u64*2).unwrap();
        assert_eq!((segment.start_ms,segment.end_ms),(22000,42000));
        assert!(segment.approximate_timing);
        let one=timed_segment("一".into(),2,4).unwrap();
        assert_eq!((one.start_ms,one.end_ms),(0,1));
        assert!(timed_segment("".into(),0,2).is_err());
        assert!(timed_segment("一".into(),1,2).is_err());
        assert!(timed_segment("一".into(),2,2).is_err());
    }
    #[test]
    #[ignore = "requires verified legacy model, damaged preferred model, and public speech"]
    fn corrupted_preferred_mobile_model_uses_verified_fallback() {
        let root=std::path::PathBuf::from(std::env::var_os("COMPANION_MOBILE_FALLBACK_ROOT").unwrap());
        let wav=std::path::PathBuf::from(std::env::var_os("COMPANION_MOBILE_FALLBACK_WAV").unwrap());
        let cache=std::path::PathBuf::from(std::env::var_os("COMPANION_MOBILE_FALLBACK_CACHE").unwrap());
        assert_eq!(ModelKind::available(&root),ModelKind::SenseVoice);
        let text=transcribe(&wav,&root,&root,&cache).expect("verified fallback should transcribe when preferred model is damaged");
        assert!(text.contains("主持人"));
        let healthy=std::path::PathBuf::from(std::env::var_os("COMPANION_MOBILE_HEALTHY_ROOT").unwrap());
        assert_eq!(ModelKind::available(&healthy),ModelKind::SenseVoice);
        let newer=transcribe(&wav,&healthy,&healthy,&cache).expect("healthy preferred model should remain usable");
        assert!(newer.contains("主持人"));
        assert_ne!(text,newer,"switching models must not reuse the other model's cached transcript");
    }

    #[test]
    #[ignore = "requires pinned local Windows runtime and synthetic audio"]
    fn local_transcription_reuses_private_chunk_cache() {
        let root = std::env::var_os("COMPANION_LOCAL_ASR_TEST_ROOT").unwrap();
        let wav = std::env::var_os("COMPANION_LOCAL_ASR_TEST_WAV").unwrap();
        let cache = std::env::var_os("COMPANION_LOCAL_ASR_TEST_CACHE").unwrap();
        let root = Path::new(&root);
        let wav = Path::new(&wav);
        let cache = Path::new(&cache);
        let first = transcribe(wav, root, root, cache).unwrap();
        assert!(first.contains("蓝色文件夹"));
        let entries = std::fs::read_dir(cache).unwrap().count();
        assert!(entries > 0);
        let second = transcribe(wav, root, root, cache).unwrap();
        assert_eq!(second, first);
        assert_eq!(std::fs::read_dir(cache).unwrap().count(), entries);
    }
}
