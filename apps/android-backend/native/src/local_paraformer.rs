//! Candidate local mobile recognition. Call only on a worker; no network is used.
use std::{
    fs::File,
    io::{Read, Seek, SeekFrom},
    path::Path,
};
#[path = "../../../windows/src-tauri/src/backend/transcription/paraformer_shared.rs"]
mod shared;
use shared::{cut_samples, wav_data, ModelKind, Runtime, RATE};

pub(super) fn transcribe(
    wav: &Path,
    model_dir: &Path,
    runtime_dir: &Path,
    cache_dir: &Path,
) -> Result<String, String> {
    if !wav.is_absolute()
        || !model_dir.is_absolute()
        || (!runtime_dir.as_os_str().is_empty() && !runtime_dir.is_absolute())
        || !cache_dir.is_absolute()
    {
        return Err("录音、本地模型及缓存需要使用应用内的完整路径。".into());
    }
    let kind = ModelKind::available(model_dir);
    let runtime = Runtime::load_model(model_dir, runtime_dir, kind)?;
    let mut file = File::open(wav).map_err(|e| e.to_string())?;
    let (start, len) = wav_data(&mut file)?;
    let cache = super::asr_cache::Cache::new(
        cache_dir,
        &serde_json::json!({
            "provider":kind.provider(), "model":kind.model_hash(), "runtime":"sherpa-onnx-1.13.1", "segmentation":"quiet-16s-v1"
        }),
    )?;
    let mut offset = 0u64;
    let mut parts = Vec::new();
    while offset < len {
        let count = (len - offset).min((20 * RATE * 2 + 2) as u64) as usize;
        let mut pcm = vec![0u8; count];
        file.seek(SeekFrom::Start(start + offset))
            .map_err(|e| e.to_string())?;
        file.read_exact(&mut pcm)
            .map_err(|_| "录音读取中断，原录音保留。")?;
        let cut = cut_samples(&pcm);
        pcm.truncate(cut * 2);
        if pcm.is_empty() {
            return Err("本地转写分段失败，原录音保留。".into());
        }
        let completed = match cache.lookup(&pcm) {
            Some(done) => done,
            None => {
                let text = runtime.transcribe(&pcm)?;
                let done = if text.trim().is_empty() {
                    super::asr_cache::Completed::Silence
                } else {
                    super::asr_cache::Completed::Text(text)
                };
                cache.save(&pcm, &done);
                done
            }
        };
        if let super::asr_cache::Completed::Text(text) = completed {
            parts.push(text);
        }
        offset += pcm.len() as u64;
    }
    if parts.is_empty() {
        return Err("没有识别到语音，原录音保留。".into());
    }
    Ok(parts.join("\n"))
}

#[cfg(test)]
mod tests {
    use super::*;
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
