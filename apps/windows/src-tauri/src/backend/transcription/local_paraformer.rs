//! Windows local ASR provider; model assets are supplied separately.
use std::{
    fs::File,
    io::{Read, Seek, SeekFrom},
    path::Path,
};
#[path = "paraformer_shared.rs"]
mod shared;
use shared::{cut_samples, wav_data, Runtime, MODEL_SHA, RATE};
pub(super) fn transcribe(audio: &Path) -> Result<super::CompanionTranscript, String> {
    let root = std::env::var_os("COMPANION_TYPE_LOCAL_ASR_DIR")
        .ok_or("请先准备本地转写模型；原录音保留。")?;
    let runtime = Runtime::load(Path::new(&root), Path::new(&root))?;
    let mut file = File::open(audio).map_err(|e| e.to_string())?;
    let (start, len) = wav_data(&mut file)?;
    let mut offset = 0u64;
    let mut parts = Vec::new();
    let profile = super::chunk_cache::Profile::from_configuration(
        &serde_json::json!({"provider":"local-paraformer","model":MODEL_SHA,"language":"zh-en","runtime":"sherpa-onnx-1.13.1","segmentation":"quiet-16s-v1"}),
    )?;
    while offset < len {
        let n = (len - offset).min((20 * RATE * 2 + 2) as u64) as usize;
        let mut buf = vec![0; n];
        file.seek(SeekFrom::Start(start + offset))
            .map_err(|e| e.to_string())?;
        file.read_exact(&mut buf).map_err(|e| e.to_string())?;
        let count = cut_samples(&buf);
        buf.truncate(count * 2);
        if buf.is_empty() {
            return Err("本地转写分段失败，原录音保留。".into());
        }
        let key = super::chunk_cache::Key::new(&buf, profile.clone())?;
        let result = super::chunk_cache::ownership::resolve(
            &super::asr_chunk_cache_root(),
            &key,
            audio,
            || runtime.transcribe(&buf).map(|text| (text, Vec::new())),
        );
        match result {
            Ok((text, _)) => parts.push(text),
            Err(e) if e == "ASR final result is empty or has invalid timing" => {}
            Err(e) => return Err(format!("本地转写中断，原录音保留，可重试：{e}")),
        }
        offset += buf.len() as u64;
    }
    let text = super::normalize_transcript(&parts.join("\n"));
    if text.is_empty() {
        return Err("没有识别到语音，原录音保留。".into());
    }
    Ok(super::CompanionTranscript {
        text,
        provider_id: "companion-type-local-paraformer".into(),
        mode: "offline:paraformer".into(),
        evidence_path: None,
        utterances: Vec::new(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn two_hours_are_fully_covered_with_bounded_chunks() {
        let total = 2 * 60 * 60 * RATE;
        let mut done = 0usize;
        let mut chunks = 0;
        while done < total {
            let samples = (total - done).min(20 * RATE + 1);
            let pcm = vec![0u8; samples * 2];
            let cut = cut_samples(&pcm);
            assert!(cut > 0 && cut <= 20 * RATE && cut <= samples);
            done += cut;
            chunks += 1;
        }
        assert_eq!(done, total);
        assert!(chunks > 360);
    }

    #[test]
    #[ignore = "requires locally installed pinned runtime, model and synthetic fixture"]
    fn listener_runtime_transcribes_synthetic_meeting() {
        let root = std::env::var_os("COMPANION_LOCAL_ASR_TEST_ROOT").expect("test model root");
        let fixture = std::env::var_os("COMPANION_LOCAL_ASR_TEST_WAV").expect("synthetic WAV");
        let runtime =
            Runtime::load(Path::new(&root), Path::new(&root)).expect("load pinned runtime");
        let mut file = File::open(Path::new(&fixture)).unwrap();
        let (start, len) = wav_data(&mut file).unwrap();
        file.seek(SeekFrom::Start(start)).unwrap();
        let mut pcm = vec![0; len as usize];
        file.read_exact(&mut pcm).unwrap();
        let text = runtime.transcribe(&pcm).unwrap();
        assert!(text.contains("蓝色文件夹"), "{text}");
    }
}
