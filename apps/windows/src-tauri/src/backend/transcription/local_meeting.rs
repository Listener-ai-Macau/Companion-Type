//! Explicitly installed local meeting package. It never chooses a network
//! provider or falls back after an incomplete local result.
use super::CompanionTranscript;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    fs,
    io::Read,
    path::{Path, PathBuf},
};

const CONFIG_ENV: &str = "COMPANION_TYPE_LOCAL_MEETING_CONFIG";
const MISSING: &str = "本机会议识别尚未准备好，请检查模型包；原录音保留。";

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Package {
    schema: String,
    program: PathBuf,
    program_sha256: String,
    entry_script: PathBuf,
    entry_script_sha256: String,
    args: Vec<String>,
    work_root: PathBuf,
    assets: Vec<Asset>,
    #[serde(skip)]
    identity: String,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Asset {
    path: PathBuf,
    bytes: u64,
}

fn file_sha(path: &Path) -> Result<String, String> {
    let mut file = fs::File::open(path).map_err(|_| MISSING.to_string())?;
    let mut hash = Sha256::new();
    let mut buffer = [0u8; 65536];
    loop {
        let n = file.read(&mut buffer).map_err(|_| MISSING.to_string())?;
        if n == 0 {
            break;
        }
        hash.update(&buffer[..n]);
    }
    Ok(format!("{:x}", hash.finalize()))
}

fn package() -> Result<Package, String> {
    let path = PathBuf::from(std::env::var_os(CONFIG_ENV).ok_or(MISSING)?);
    if !path.is_absolute() {
        return Err(MISSING.into());
    }
    let bytes = fs::read(path).map_err(|_| MISSING.to_string())?;
    if bytes.len() > 65536 {
        return Err(MISSING.into());
    }
    let mut p: Package = serde_json::from_slice(&bytes).map_err(|_| MISSING.to_string())?;
    if p.schema != "companion.local-meeting-package.v1"
        || !p.program.is_absolute()
        || !p.entry_script.is_absolute()
        || !p.work_root.is_absolute()
        || p.args.len() > 32
        || !p.args.iter().any(|a| a == "{manifest}")
        || !p.args.iter().any(|a| a == "{entry}")
        || p.program
            .to_string_lossy()
            .to_ascii_lowercase()
            .contains("listener-type")
        || p.assets.is_empty()
        || p.assets.iter().any(|a| {
            !a.path.is_absolute()
                || a.bytes == 0
                || !fs::metadata(&a.path).is_ok_and(|m| m.is_file() && m.len() == a.bytes)
        })
        || file_sha(&p.program)? != p.program_sha256
        || file_sha(&p.entry_script)? != p.entry_script_sha256
    {
        return Err(MISSING.into());
    }
    p.identity = format!("{:x}", Sha256::digest(&bytes));
    Ok(p)
}

pub(super) fn check() -> Result<(), String> {
    package().map(|_| ())
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct InputFile {
    path: PathBuf,
    sha256: String,
    pcm_bytes: u64,
}

pub(super) fn transcribe(
    paths: &[PathBuf],
    owner: Option<&str>,
) -> Result<CompanionTranscript, String> {
    let p = package()?;
    let owner = owner.ok_or("会议归属尚未准备好，未启动本机识别，原音保留。")?;
    if paths.is_empty() {
        return Err("没有可转写的原音。".into());
    }
    let mut files = Vec::new();
    let mut bytes = 0u64;
    for path in paths {
        super::super::meeting_processing_job::check_current()?;
        let path = fs::canonicalize(path).map_err(|_| "原音暂不可读取，已有资料保留。")?;
        let pcm = super::wav_pcm_bytes(&path)?;
        bytes = bytes.checked_add(pcm).ok_or("原音时间范围过大。")?;
        files.push(InputFile {
            sha256: file_sha(&path)?,
            path,
            pcm_bytes: pcm,
        });
    }
    let identity = serde_json::to_vec(&serde_json::json!({"files":files,"package":p.identity}))
        .map_err(|_| MISSING)?;
    let key = format!("complete-{:x}", Sha256::digest(&identity));
    let cache = super::local_meeting_cache::reserve(&super::asr_chunk_cache_root(), owner, &key)?;
    let request = cache.root.join("input.json");
    let payload = serde_json::json!({"schema":"companion.local-meeting-input.v1","files":files,
        "language":"auto","localOnly":true,"finalize":true,"artifactRoot":cache.root,
        "ownedStreamRoots":[]});
    // Keep the immutable request as a recoverable source binding on failure.
    let payload = serde_json::to_vec(&payload).map_err(|_| MISSING)?;
    if request.exists() && fs::read(&request).map_err(|_| MISSING)? != payload {
        return Err("本机识别续作归属变化，原音和已保存进度保留。".into());
    }
    if !request.exists() {
        super::super::export::write_atomic(&request, &payload)
            .map_err(|_| "无法保存本机处理请求，原音保留。")?;
    }
    let args = p
        .args
        .iter()
        .map(|a| match a.as_str() {
            "{manifest}" => request.to_string_lossy().into_owned(),
            "{entry}" => p.entry_script.to_string_lossy().into_owned(),
            _ => a.clone(),
        })
        .collect::<Vec<_>>();
    let seconds = bytes.div_ceil(super::PCM_BYTES_PER_SECOND as u64);
    let stdout = super::super::external_command::run_local_meeting(
        &p.program.to_string_lossy(),
        &args,
        seconds,
    )
    .map_err(|e| format!("本机会议识别未完成：{e}；原音和已保存的处理进度保留。"))?;
    super::super::meeting_processing_job::check_current()?;
    let document = super::super::meeting_transcript::parse_command_output(&stdout)?;
    let duration =
        u64::try_from((bytes as u128 * 1000).div_ceil(super::PCM_BYTES_PER_SECOND as u128))
            .map_err(|_| "原音时间范围过大。")?;
    document.validate(Some(duration))?;
    let envelope: serde_json::Value =
        serde_json::from_str(&stdout).map_err(|_| "本机转写复核范围无法读取，原音保留。")?;
    let mut unrecognized: Vec<crate::companion_v1::CompanionV1UnrecognizedAudio> =
        match envelope.get("unrecognizedAudio") {
            Some(value) => serde_json::from_value(value.clone())
                .map_err(|_| "本机转写复核范围无效，原音保留。")?,
            None => Vec::new(),
        };
    if envelope
        .get("reviewRequired")
        .and_then(|v| v.as_bool())
        .unwrap_or(false)
        != !unrecognized.is_empty()
        || unrecognized
            .iter()
            .any(|r| r.start_ms >= r.end_ms || r.end_ms > duration)
    {
        return Err("本机转写复核状态与原音范围不一致，原音保留。".into());
    }
    unrecognized.sort_by_key(|r| (r.start_ms, r.end_ms));
    let text = if document.utterances.is_empty() {
        document.text
    } else {
        super::super::meeting_transcript::source_text(&document.utterances)
    };
    Ok(CompanionTranscript {
        text,
        provider_id: "companion-local-meeting".into(),
        mode: "local-bilingual-complete-meeting".into(),
        evidence_path: Some(request),
        utterances: document.utterances,
        unrecognized,
    })
}
