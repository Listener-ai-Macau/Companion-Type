//! Windows local ASR provider; model assets are supplied separately.
use std::{
    fs::File,
    io::{Read, Seek, SeekFrom},
    path::Path,
};
#[path = "paraformer_shared.rs"]
mod shared;
use shared::{cut_samples, wav_data, Runtime, MODEL_SHA, RATE, TOKENS_SHA};
use std::{fs, path::PathBuf, sync::Mutex};

const MODEL_DIR: &str = "sherpa-onnx-paraformer-zh-small-2024-03-09";
const ASSETS: [(&str, &str); 5] = [
    (
        "sherpa-onnx-paraformer-zh-small-2024-03-09/model.int8.onnx",
        MODEL_SHA,
    ),
    (
        "sherpa-onnx-paraformer-zh-small-2024-03-09/tokens.txt",
        TOKENS_SHA,
    ),
    (
        "onnxruntime.dll",
        "8b695444d1a35ed0c8338b8c14438b3be5e0a3b222b88b1e7b4ce8753f135b50",
    ),
    (
        "onnxruntime_providers_shared.dll",
        "ebc55b0f28e8a79cbf78e810a7f510ba70e75a2dfbcfcc6aca31ab2b8710a59a",
    ),
    (
        "sherpa-onnx-c-api.dll",
        "94f23cb935c57fb2581c66d65f6602ab5b509d6fc269404296af0336871daba5",
    ),
];
static PREPARING: Mutex<()> = Mutex::new(());

fn root() -> Result<PathBuf, String> {
    if let Some(path) = std::env::var_os("COMPANION_TYPE_LOCAL_ASR_DIR") {
        return Ok(path.into());
    }
    let base = std::env::var_os("APPDATA").ok_or("无法找到本机模型目录。")?;
    Ok(PathBuf::from(base).join("Companion Type/models/local-asr"))
}

/// This is a lightweight availability hint. Runtime::load verifies every hash
/// before loading a model, so a later missing or changed file cannot be used.
pub(super) fn assets_present() -> bool {
    root().ok().is_some_and(|dir| {
        ASSETS.iter().all(|(name, _)| {
            dir.join(name)
                .metadata()
                .is_ok_and(|m| m.is_file() && m.len() > 0)
        })
    })
}

/// Copy verified already-installed Listener assets into Companion-owned storage.
/// This makes no network request and never modifies the original assets.
pub(super) fn prepare() -> Result<(), String> {
    let _guard = PREPARING
        .try_lock()
        .map_err(|_| "本地转写模型正在准备，请稍候。")?;
    let dest = root()?;
    if ASSETS
        .iter()
        .all(|(name, hash)| shared::verified(&dest.join(name), hash).is_ok())
    {
        return Ok(());
    }
    let appdata = std::env::var_os("APPDATA").ok_or("无法找到本机模型目录。")?;
    let source = PathBuf::from(appdata).join("Listener Type/models/speaker-verification");
    for (name, hash) in ASSETS {
        shared::verified(&source.join(name), hash).map_err(|_| {
            "本机没有可复用的 Listener 中文转写模型，暂时无法自动准备；可以继续使用云端转写。"
        })?;
    }
    let parent = dest.parent().ok_or("无法准备本地模型目录。")?;
    fs::create_dir_all(parent).map_err(|e| format!("无法创建本地模型目录：{e}"))?;
    let stage = parent.join(format!("local-asr-{}", uuid::Uuid::new_v4()));
    fs::create_dir(&stage).map_err(|e| format!("无法准备本地模型：{e}"))?;
    let result = (|| {
        fs::create_dir(stage.join(MODEL_DIR)).map_err(|e| e.to_string())?;
        for (name, hash) in ASSETS {
            let copy = stage.join(name);
            fs::copy(source.join(name), &copy).map_err(|e| format!("复制本地模型失败：{e}"))?;
            fs::OpenOptions::new()
                .write(true)
                .open(&copy)
                .and_then(|f| f.sync_all())
                .map_err(|e| format!("保存本地模型失败：{e}"))?;
            shared::verified(&copy, hash)?;
        }
        fs::create_dir_all(dest.join(MODEL_DIR)).map_err(|e| e.to_string())?;
        let dest = dest.canonicalize().map_err(|e| e.to_string())?;
        for (name, hash) in ASSETS {
            if shared::verified(&dest.join(name), hash).is_err() {
                let file = stage.join(name).canonicalize().map_err(|e| e.to_string())?;
                super::super::export::replace_file(&file, &dest.join(name))?;
            }
        }
        for (name, hash) in ASSETS {
            shared::verified(&dest.join(name), hash)?;
        }
        Ok(())
    })();
    if let (Ok(actual), Ok(expected)) = (stage.canonicalize(), parent.canonicalize()) {
        if actual.parent() == Some(expected.as_path()) && actual.file_name() == stage.file_name() {
            let _ = fs::remove_dir_all(actual);
        }
    }
    result
}
pub(super) fn check() -> Result<(), String> {
    let root = root()?;
    let _runtime = Runtime::load(&root, &root)?;
    Ok(())
}
pub(super) fn transcribe(audio: &Path) -> Result<super::CompanionTranscript, String> {
    let root = root()?;
    let runtime = Runtime::load(&root, &root)?;
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
