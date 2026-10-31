//! Windows local ASR provider; model assets are supplied separately.
use std::{
    fs::File,
    io::{Read, Seek, SeekFrom, Write},
    path::Path,
};
#[path = "paraformer_shared.rs"]
mod shared;
use shared::{cut_samples, is_digital_silence, wav_data, ModelKind, Runtime, MODEL_SHA, RATE, TOKENS_SHA};
use std::{fs, path::PathBuf, sync::Mutex};

const MODEL_BASE: &str = "https://huggingface.co/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/resolve/2365baeacb507f821a0c8120fcee3d484dba7a07/";
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
        let runtime = ASSETS[2..].iter().all(|(name, _)| {
            dir.join(name)
                .metadata()
                .is_ok_and(|m| m.is_file() && m.len() > 0)
        });
        let old_model = ASSETS[..2].iter().all(|(name, _)| dir.join(name).metadata().is_ok_and(|m|m.is_file() && m.len() > 0));
        let sense = dir.join(shared::SENSE_DIR);
        let present = |name: &str| sense.join(name).metadata().is_ok_and(|m|m.is_file() && m.len() > 0);
        runtime && (old_model || (sense.join("ready").is_file() && present("model.int8.onnx") && present("tokens.txt")))
    })
}

fn download_model(name: &str, size: u64, hash: &str, dest: &Path) -> Result<(), String> {
    let client = reqwest::blocking::Client::builder()
        .connect_timeout(std::time::Duration::from_secs(15))
        .timeout(std::time::Duration::from_secs(600)).build().map_err(|_| "无法创建模型下载连接。")?;
    let response = client.get(format!("{MODEL_BASE}{name}?download=true"))
        .send().and_then(|r| r.error_for_status()).map_err(|_| "本地模型下载失败，请检查网络后重试。")?;
    let mut file = File::create(dest).map_err(|_| "无法保存本地模型。")?;
    let count = std::io::copy(&mut response.take(size + 1), &mut file).map_err(|_| "本地模型下载未完成。")?;
    file.flush().and_then(|_| file.sync_all()).map_err(|_| "本地模型保存失败。")?;
    drop(file);
    if count != size { return Err("本地模型下载未完成，请重试。".into()); }
    shared::verified(dest, hash)
}

// Preserve the existing offline setup path when Listener's verified model is
// already installed and a fresh network setup is unavailable.
fn prepare_legacy(dest: &Path, stage: &Path) -> Result<(), String> {
    let appdata = std::env::var_os("APPDATA").ok_or("无法找到本机模型目录。")?;
    let source = PathBuf::from(appdata).join("Listener Type/models/speaker-verification");
    for (name, hash) in ASSETS { shared::verified(&source.join(name), hash)?; }
    for (name, hash) in ASSETS {
        let target=stage.join(name);
        fs::create_dir_all(target.parent().ok_or("无法准备模型目录。")?).map_err(|e|e.to_string())?;
        fs::copy(source.join(name), &target).map_err(|_| "复制本地模型失败。")?;
        fs::OpenOptions::new().write(true).open(&target).and_then(|f|f.sync_all()).map_err(|e|e.to_string())?;
        shared::verified(&target, hash)?;
    }
    for (name, hash) in ASSETS {
        let target=dest.join(name);
        fs::create_dir_all(target.parent().ok_or("无法准备模型目录。")?).map_err(|e|e.to_string())?;
        if shared::verified(&target, hash).is_err() {
            let parent=target.parent().unwrap().canonicalize().map_err(|e|e.to_string())?;
            let destination=parent.join(target.file_name().ok_or("模型路径无效。")?);
            super::super::export::replace_file(&stage.join(name).canonicalize().map_err(|e|e.to_string())?, &destination)?;
        }
    }
    Ok(())
}

/// User-initiated setup. Model files are downloaded separately and never include recordings.
pub(super) fn prepare() -> Result<(), String> {
    let _guard = PREPARING
        .try_lock()
        .map_err(|_| "本地转写模型正在准备，请稍候。")?;
    let dest = root()?;
    let sense = dest.join(shared::SENSE_DIR);
    if ModelKind::available(&dest) == ModelKind::SenseVoice
        && shared::verified(&sense.join("model.int8.onnx"), shared::SENSE_MODEL_SHA).is_ok()
        && shared::verified(&sense.join("tokens.txt"), shared::SENSE_TOKENS_SHA).is_ok()
        && ASSETS[2..].iter().all(|(name, hash)| shared::verified(&dest.join(name), hash).is_ok()) {
        return Ok(());
    }
    let parent = dest.parent().ok_or("无法准备本地模型目录。")?;
    fs::create_dir_all(parent).map_err(|e| format!("无法创建本地模型目录：{e}"))?;
    let stage = parent.join(format!("local-asr-{}", uuid::Uuid::new_v4()));
    fs::create_dir(&stage).map_err(|e| format!("无法准备本地模型：{e}"))?;
    let mut result = (|| {
        super::super::audio_components::prepare_runtime(&stage, &dest)?;
        for (name, size, hash) in [("model.int8.onnx",239_233_841,shared::SENSE_MODEL_SHA), ("tokens.txt",315_894,shared::SENSE_TOKENS_SHA)] {
            let target = stage.join(name);
            if shared::verified(&sense.join(name), hash).is_ok() {
                fs::copy(sense.join(name), &target).map_err(|_| "复制本地模型失败。")?;
            } else { download_model(name, size, hash, &target)?; }
            shared::verified(&target, hash)?;
        }
        fs::create_dir_all(&sense).map_err(|e| e.to_string())?;
        let dest = dest.canonicalize().map_err(|e| e.to_string())?;
        for (name, hash) in &ASSETS[2..] {
            if shared::verified(&dest.join(name), hash).is_err() {
                let file = stage.join(name).canonicalize().map_err(|e| e.to_string())?;
                super::super::export::replace_file(&file, &dest.join(name))?;
            }
        }
        let model_dir = dest.join(shared::SENSE_DIR);
        for (name, hash) in [("model.int8.onnx",shared::SENSE_MODEL_SHA), ("tokens.txt",shared::SENSE_TOKENS_SHA)] {
            if shared::verified(&model_dir.join(name), hash).is_err() {
                let file=stage.join(name).canonicalize().map_err(|e|e.to_string())?;
                super::super::export::replace_file(&file, &model_dir.join(name))?;
            }
            shared::verified(&model_dir.join(name), hash)?;
        }
        let ready = stage.join("ready");
        let mut marker=File::create(&ready).map_err(|e|e.to_string())?;
        marker.write_all(shared::SENSE_MODEL_SHA.as_bytes()).and_then(|_|marker.sync_all()).map_err(|e|e.to_string())?;
        drop(marker);
        super::super::export::replace_file(&ready.canonicalize().map_err(|e|e.to_string())?, &model_dir.join("ready"))?;
        Ok(())
    })();
    if result.is_err() && !assets_present() && ModelKind::available(&dest) == ModelKind::Paraformer {
        if prepare_legacy(&dest, &stage).is_ok() { result = Ok(()); }
    }
    if let (Ok(actual), Ok(expected)) = (stage.canonicalize(), parent.canonicalize()) {
        if actual.parent() == Some(expected.as_path()) && actual.file_name() == stage.file_name() {
            let _ = fs::remove_dir_all(actual);
        }
    }
    result
}
pub(super) fn check() -> Result<(), String> {
    let root = root()?;
    let _runtime = Runtime::load_model(&root, &root, ModelKind::available(&root))?;
    Ok(())
}

// This is the input window, not a word/speaker timestamp. Keep a clear marker
// so review can seek near the original audio without presenting it as exact.
fn chunk_anchor(text: &str, start_byte: u64, end_byte: u64) -> Option<crate::companion_v1::CompanionV1UtteranceSegment> {
    let text=super::normalize_transcript(text);
    if text.is_empty() || end_byte <= start_byte || start_byte % 2 != 0 || end_byte % 2 != 0 {return None;}
    let start_samples=(start_byte/2) as u128;let end_samples=(end_byte/2) as u128;
    let start_ms=u64::try_from(start_samples*1000/RATE as u128).ok()?;
    let end_ms=u64::try_from((end_samples*1000+RATE as u128-1)/RATE as u128).ok()?;
    Some(crate::companion_v1::CompanionV1UtteranceSegment{text,start_ms,end_ms,speaker:None,approximate_timing:true})
}

pub(super) fn transcribe(audio: &Path) -> Result<super::CompanionTranscript, String> {
    let root = root()?;
    let kind = ModelKind::available(&root);
    let runtime = Runtime::load_model(&root, &root, kind)?;
    let mut file = File::open(audio).map_err(|e| e.to_string())?;
    let (start, len) = wav_data(&mut file)?;
    let mut offset = 0u64;
    let mut parts = Vec::new();
    let mut anchors = Vec::new();
    let profile = super::chunk_cache::Profile::from_configuration(
        &serde_json::json!({"provider":kind.provider(),"model":kind.model_hash(),"language":"zh-en","runtime":"sherpa-onnx-1.13.1","segmentation":"quiet-16s-v1"}),
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
        if is_digital_silence(&buf) {
            offset += buf.len() as u64;
            continue;
        }
        let key = super::chunk_cache::Key::new(&buf, profile.clone())?;
        let result = super::chunk_cache::ownership::resolve(
            &super::asr_chunk_cache_root(),
            &key,
            audio,
            || runtime.transcribe(&buf).map(|text| (text, Vec::new())),
        );
        match result {
            Ok((text, _)) => {
                let normalized=super::normalize_transcript(&text);
                if !normalized.is_empty() {
                    let anchor=chunk_anchor(&normalized,offset,offset+buf.len() as u64)
                        .ok_or("无法保存本地转写时间范围，原录音保留。")?;
                    parts.push(normalized);anchors.push(anchor);
                }
            },
            Err(e) if e == "ASR final result is empty or has invalid timing" => {}
            Err(e) => return Err(format!("本地转写中断，原录音保留，可重试：{e}")),
        }
        offset += buf.len() as u64;
    }
    let text = super::normalize_transcript(&parts.join("\n"));
    if text.is_empty() {
        return Err(super::LOCAL_NO_SPEECH.into());
    }
    Ok(super::CompanionTranscript {
        text,
        provider_id: format!("companion-type-{}", kind.provider()),
        mode: match kind { ModelKind::Paraformer => "offline:paraformer", ModelKind::SenseVoice => "offline:sensevoice" }.into(),
        evidence_path: None,
        utterances: anchors,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn incomplete_new_model_does_not_override_existing_model() {
        let dir=std::env::temp_dir().join(format!("companion-model-selection-{}", uuid::Uuid::new_v4()));
        let sense=dir.join(shared::SENSE_DIR);
        fs::create_dir_all(&sense).unwrap();
        fs::write(sense.join("model.int8.onnx"), b"partial").unwrap();
        fs::write(sense.join("tokens.txt"), b"partial").unwrap();
        assert_eq!(ModelKind::available(&dir), ModelKind::Paraformer);
        fs::write(sense.join("ready"), b"ready").unwrap();
        assert_eq!(ModelKind::available(&dir), ModelKind::SenseVoice);
        assert!(Runtime::load_model(&dir, &dir, ModelKind::SenseVoice).is_err());
        assert_ne!(ModelKind::Paraformer.model_hash(), ModelKind::SenseVoice.model_hash());
        fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn cached_local_text_has_explicit_approximate_chunk_positions() {
        let first=chunk_anchor(" 第一段。\r\n",0,32_000*16).unwrap();
        let last=chunk_anchor("第二段。",32_000*20,32_000*25+16).unwrap();
        assert_eq!((first.start_ms,first.end_ms),(0,16_000));
        assert_eq!((last.start_ms,last.end_ms),(20_000,25_001));
        assert!(first.approximate_timing && last.approximate_timing);
        assert_eq!(first.speaker,None);
        assert_eq!(super::super::normalize_transcript(&[first.text,last.text].join("\n")),"第一段。\n第二段。");
        assert!(chunk_anchor("  ",0,10).is_none());
        assert!(chunk_anchor("x",0,0).is_none());
    }

    #[test]
    #[ignore = "downloads the pinned model; requires isolated test model directory and WAV"]
    fn fresh_install_downloads_and_transcribes_real_board_voice() {
        let fixture=std::env::var_os("COMPANION_LOCAL_ASR_TEST_WAV").unwrap();
        assert!(std::env::var_os("COMPANION_TYPE_LOCAL_ASR_DIR").is_some());
        prepare().unwrap();
        check().unwrap();
        let result=transcribe(Path::new(&fixture)).unwrap();
        assert_eq!(result.provider_id, "companion-type-local-sensevoice");
        assert!(result.text.contains("蓝色文件夹"));
    }

    #[test]
    #[ignore = "requires isolated destination and already installed Listener model"]
    fn legacy_listener_model_still_prepares_offline() {
        let dest=root().unwrap();
        let stage=dest.parent().unwrap().join(format!("legacy-test-{}", uuid::Uuid::new_v4()));
        fs::create_dir_all(&stage).unwrap();
        prepare_legacy(&dest, &stage).unwrap();
        assert!(assets_present());
        assert_eq!(ModelKind::available(&dest), ModelKind::Paraformer);
        check().unwrap();
        fs::remove_dir_all(stage).unwrap();
    }

    #[test]
    #[ignore = "requires isolated pinned model, real-meeting WAV and output paths"]
    fn real_two_hour_meeting_uses_production_cache() {
        let fixture=std::env::var_os("COMPANION_LOCAL_ASR_TEST_WAV").unwrap();
        let output=std::env::var_os("COMPANION_LOCAL_ASR_TEST_OUTPUT").unwrap();
        assert!(std::env::var_os("COMPANION_TYPE_LOCAL_ASR_DIR").is_some());
        assert!(std::env::var_os("COMPANION_TYPE_ASR_CACHE_DIR").is_some());
        let result=transcribe(Path::new(&fixture)).unwrap();
        assert_eq!(result.provider_id, "companion-type-local-sensevoice");
        assert!(!result.text.is_empty());
        assert!(!result.utterances.is_empty());
        assert!(result.utterances.iter().all(|u|u.approximate_timing && u.speaker.is_none() && u.end_ms>u.start_ms));
        assert!(result.utterances.windows(2).all(|u|u[0].end_ms<=u[1].start_ms+1));
        assert_eq!(super::super::normalize_transcript(&result.utterances.iter().map(|u|u.text.as_str()).collect::<Vec<_>>().join("\n")),result.text);
        if let Some(path)=std::env::var_os("COMPANION_LOCAL_ASR_TEST_ANCHORS_OUTPUT") {
            fs::write(path,serde_json::to_vec_pretty(&result.utterances).unwrap()).unwrap();
        }
        fs::write(output, result.text).unwrap();
    }

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
