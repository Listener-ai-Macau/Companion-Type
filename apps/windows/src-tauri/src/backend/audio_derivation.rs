//! Sample-accurate edits over explicitly resolved, complete canonical PCM.
//! Wire fields match packages/audio-derivation. Native inputs never deserialize
//! paths from UI requests. The caller retains source usage leases and publishes
//! the resulting audio and its independent provenance through existing storage.
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs::{self, File, OpenOptions},
    io::{Read, Seek, SeekFrom, Write},
    path::{Path, PathBuf},
};

const SAFE: u64 = 9_007_199_254_740_991;
const BUFFER: usize = 65_536;
const MAX_ORIGINAL: u64 = 2 * 1024 * 1024 * 1024;
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct SourceIdentity {
    pub key: String,
    pub identity: String,
    pub frames: u64,
    pub sample_rate: u32,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Slice {
    pub source_key: String,
    pub source_identity: String,
    pub start_frame: u64,
    pub end_frame: u64,
    pub output_start_frame: u64,
    pub output_end_frame: u64,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Plan {
    pub schema: u8,
    pub sample_rate: u32,
    pub frames: u64,
    pub slices: Vec<Slice>,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Provenance {
    pub schema: u8,
    pub sources: Vec<SourceIdentity>,
    pub plan: Plan,
}
fn sha(text: &str) -> bool {
    text.len() == 64
        && text
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}
impl Plan {
    pub fn validate(&self, sources: &[SourceIdentity]) -> Result<(), String> {
        if self.schema != 1
            || self.sample_rate != 16000
            || self.frames == 0
            || self.frames > SAFE
            || sources.is_empty()
            || sources.len() > 128
            || self.slices.is_empty()
            || self.slices.len() > 512
        {
            return Err("请选择有效的完整本机音频片段。".into());
        }
        let mut known = BTreeMap::new();
        for source in sources {
            if source.key.is_empty()
                || source.key.len() > 1200
                || source.key.chars().any(char::is_control)
                || !sha(&source.identity)
                || source.frames == 0
                || source.frames > SAFE
                || source.sample_rate != 16000
                || known.insert(source.key.as_str(), source).is_some()
            {
                return Err("原音身份或完整长度尚未确认，请重新读取。".into());
            }
        }
        let mut output = 0u64;
        for slice in &self.slices {
            let source = known
                .get(slice.source_key.as_str())
                .ok_or("找不到所选原音，请重新打开编辑。")?;
            if slice.source_identity != source.identity {
                return Err("原音已变化，请重新选择编辑范围。".into());
            }
            if slice.end_frame <= slice.start_frame || slice.end_frame > source.frames {
                return Err("编辑区间超出原音范围。".into());
            }
            let end = output
                .checked_add(slice.end_frame - slice.start_frame)
                .filter(|n| *n <= SAFE)
                .ok_or("派生音频长度超出处理范围。")?;
            if slice.output_start_frame != output || slice.output_end_frame != end {
                return Err("派生音频时间对应已损坏，请重新生成。".into());
            }
            output = end;
        }
        if output != self.frames {
            return Err("派生音频长度与来源不符。".into());
        }
        Ok(())
    }
    pub fn provenance(&self, sources: &[SourceIdentity]) -> Result<Provenance, String> {
        self.validate(sources)?;
        let used: BTreeSet<&str> = self.slices.iter().map(|s| s.source_key.as_str()).collect();
        Ok(Provenance {
            schema: 1,
            sources: sources
                .iter()
                .filter(|s| used.contains(s.key.as_str()))
                .cloned()
                .collect(),
            plan: self.clone(),
        })
    }
}
impl Provenance {
    pub fn validate(&self) -> Result<(), String> {
        if self.schema != 1 {
            return Err("派生音频来源版本无效。".into());
        }
        self.plan.validate(&self.sources)
    }
}
pub(super) struct InputPart {
    pub path: PathBuf,
    pub sha256: String,
}
pub(super) struct Input {
    pub source: SourceIdentity,
    pub parts: Vec<InputPart>,
    pub meeting: Option<crate::companion_v1::CompanionV1MeetingTracks>,
}
pub(super) struct Rendered {
    pub temporary: PathBuf,
    pub frames: u64,
    pub bytes: u64,
    pub sha256: String,
}
struct Part {
    path: PathBuf,
    offset: u64,
    frames: u64,
    sha256: String,
}
fn io(error: std::io::Error) -> String {
    format!("本机音频读写未完成，原录音保留：{error}")
}
fn hash(
    path: &Path,
    done: u64,
    total: u64,
    check: &mut impl FnMut(u64, u64) -> Result<(), String>,
) -> Result<String, String> {
    let mut input = File::open(path).map_err(io)?;
    let mut hash = Sha256::new();
    let mut bytes = [0u8; BUFFER];
    loop {
        check(done, total)?;
        let n = input.read(&mut bytes).map_err(io)?;
        if n == 0 {
            break;
        }
        hash.update(&bytes[..n]);
    }
    Ok(format!("{:x}", hash.finalize()))
}
fn inspect(
    input: &InputPart,
    check: &mut impl FnMut(u64, u64) -> Result<(), String>,
) -> Result<Part, String> {
    if !sha(&input.sha256) {
        return Err("原音校验身份无效。".into());
    }
    let metadata = fs::symlink_metadata(&input.path).map_err(io)?;
    if !metadata.is_file() || metadata.file_type().is_symlink() || metadata.len() < 44 {
        return Err("本机原音不是完整普通文件。".into());
    }
    let size = metadata.len();
    let mut file = File::open(&input.path).map_err(io)?;
    let mut head = [0u8; 12];
    file.read_exact(&mut head).map_err(io)?;
    if &head[..4] != b"RIFF"
        || &head[8..] != b"WAVE"
        || u64::from(u32::from_le_bytes(head[4..8].try_into().unwrap())) + 8 != size
    {
        return Err("本机回听音频不是完整WAV。".into());
    }
    let (mut offset, mut format, mut data) = (12u64, false, None);
    while offset < size {
        check(0, 0)?;
        if size - offset < 8 {
            return Err("本机音频区块不完整。".into());
        }
        file.seek(SeekFrom::Start(offset)).map_err(io)?;
        let mut chunk = [0u8; 8];
        file.read_exact(&mut chunk).map_err(io)?;
        let length = u64::from(u32::from_le_bytes(chunk[4..].try_into().unwrap()));
        let body = offset + 8;
        let next = body
            .checked_add(length)
            .and_then(|n| n.checked_add(length & 1))
            .filter(|n| *n <= size)
            .ok_or("本机音频区块越界。")?;
        if &chunk[..4] == b"fmt " {
            if format || length < 16 {
                return Err("本机音频格式不明确。".into());
            }
            let mut fmt = [0u8; 16];
            file.read_exact(&mut fmt).map_err(io)?;
            if u16::from_le_bytes(fmt[0..2].try_into().unwrap()) != 1
                || u16::from_le_bytes(fmt[2..4].try_into().unwrap()) != 1
                || u32::from_le_bytes(fmt[4..8].try_into().unwrap()) != 16000
                || u32::from_le_bytes(fmt[8..12].try_into().unwrap()) != 32000
                || u16::from_le_bytes(fmt[12..14].try_into().unwrap()) != 2
                || u16::from_le_bytes(fmt[14..16].try_into().unwrap()) != 16
            {
                return Err("请先准备16kHz单声道本机回听音频，再进行编辑。".into());
            }
            format = true;
        } else if &chunk[..4] == b"data" {
            if data.is_some() || length == 0 || length & 1 != 0 {
                return Err("本机音频采样区间无效。".into());
            }
            data = Some((body, length / 2));
        }
        offset = next;
    }
    let (data_offset, frames) = data.filter(|_| format).ok_or("本机音频没有完整采样。")?;
    if hash(&input.path, 0, 0, check)? != input.sha256 {
        return Err("原音已变化，请重新选择编辑范围。".into());
    }
    Ok(Part {
        path: input.path.clone(),
        offset: data_offset,
        frames,
        sha256: input.sha256.clone(),
    })
}

pub(super) fn probe(path: &Path) -> Result<(u64, String), String> {
    let (_, sha256) = super::audio_storage::fingerprint(path)?;
    let part = inspect(
        &InputPart {
            path: path.into(),
            sha256: sha256.clone(),
        },
        &mut |_, _| Ok(()),
    )?;
    Ok((part.frames, sha256))
}

/// Only creates one unique private temporary. No library row or source file is
/// changed, including on cancellation. Publication is a separate native step.
pub(super) fn render(
    stage: &Path,
    inputs: &[Input],
    plan: &Plan,
    mut check: impl FnMut(u64, u64) -> Result<(), String>,
) -> Result<Rendered, String> {
    let sources: Vec<_> = inputs.iter().map(|i| i.source.clone()).collect();
    plan.validate(&sources)?;
    let bytes = plan
        .frames
        .checked_mul(2)
        .and_then(|n| n.checked_add(44))
        .filter(|n| *n <= MAX_ORIGINAL)
        .ok_or("本次派生音频超过2GB，请分批保存。")?;
    let directory = fs::symlink_metadata(stage).map_err(io)?;
    if !directory.is_dir() || directory.file_type().is_symlink() {
        return Err("编辑临时目录尚未就绪。".into());
    }
    let used: BTreeSet<_> = plan.slices.iter().map(|s| s.source_key.as_str()).collect();
    let mut prepared = BTreeMap::new();
    for input in inputs
        .iter()
        .filter(|i| used.contains(i.source.key.as_str()))
    {
        if input.parts.is_empty() || input.parts.len() > 4096 {
            return Err("本机原音分段尚未完整准备。".into());
        }
        let mut total = 0u64;
        let mut parts = Vec::new();
        for part in &input.parts {
            let part = inspect(part, &mut check)?;
            total = total.checked_add(part.frames).ok_or("原音时长无效。")?;
            parts.push(part);
        }
        if input.meeting.is_none() && total != input.source.frames {
            return Err("原音长度在编辑前发生变化。".into());
        }
        prepared.insert(input.source.key.as_str(), parts);
    }
    check(0, plan.frames)?;
    let output = stage.join(format!(
        "derived-{}.wav.part",
        uuid::Uuid::new_v4().simple()
    ));
    let mut out = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&output)
        .map_err(io)?;
    let result = (|| {
        out.write_all(&denzic_host_audio_v1_core::wav::wav_header(
            (bytes - 44) as u32,
        ))
        .map_err(io)?;
        let mut buffer = [0u8; BUFFER];
        let mut copied = 0u64;
        for slice in &plan.slices {
            let source = inputs
                .iter()
                .find(|i| i.source.key == slice.source_key)
                .ok_or("找不到原音。")?;
            if let Some(tracks) = &source.meeting {
                super::meeting_audio_mix::mix_range(
                    &tracks.microphone,
                    &tracks.system,
                    slice.start_frame,
                    slice.end_frame,
                    |samples| {
                        check(copied, plan.frames)?;
                        for sample in samples {
                            out.write_all(&sample.to_le_bytes()).map_err(io)?;
                        }
                        copied += samples.len() as u64;
                        Ok(())
                    },
                )?;
                continue;
            }
            let parts = prepared
                .get(slice.source_key.as_str())
                .ok_or("所选原音分段缺失。")?;
            let mut base = 0u64;
            for part in parts {
                let start = slice.start_frame.max(base);
                let end = slice.end_frame.min(base + part.frames);
                if start < end {
                    let mut source = File::open(&part.path).map_err(io)?;
                    source
                        .seek(SeekFrom::Start(part.offset + (start - base) * 2))
                        .map_err(io)?;
                    let mut remaining = (end - start) * 2;
                    while remaining > 0 {
                        check(copied, plan.frames)?;
                        let length = remaining.min(BUFFER as u64) as usize;
                        source.read_exact(&mut buffer[..length]).map_err(io)?;
                        out.write_all(&buffer[..length]).map_err(io)?;
                        remaining -= length as u64;
                        copied += length as u64 / 2;
                    }
                }
                base += part.frames;
            }
        }
        if copied != plan.frames || out.metadata().map_err(io)?.len() != bytes {
            return Err("派生音频尚未完整生成，原音保留。".into());
        }
        out.sync_all().map_err(io)?;
        for parts in prepared.values() {
            for part in parts {
                if hash(&part.path, copied, plan.frames, &mut check)? != part.sha256 {
                    return Err("原音在编辑期间变化，已停止提交。".into());
                }
            }
        }
        let sha256 = hash(&output, copied, plan.frames, &mut check)?;
        Ok(Rendered {
            temporary: output.clone(),
            frames: copied,
            bytes,
            sha256,
        })
    })();
    drop(out);
    if result.is_err() {
        let _ = fs::remove_file(&output);
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;
    fn wav(path: &Path, start: i16, frames: usize) {
        let mut bytes = denzic_host_audio_v1_core::wav::wav_header((frames * 2) as u32).to_vec();
        for i in 0..frames {
            bytes.extend_from_slice(&(start + i as i16).to_le_bytes());
        }
        fs::write(path, bytes).unwrap();
    }
    fn source(key: &str, identity: char, frames: u64) -> SourceIdentity {
        SourceIdentity {
            key: key.into(),
            identity: identity.to_string().repeat(64),
            frames,
            sample_rate: 16000,
        }
    }
    fn part(path: PathBuf) -> InputPart {
        let sha256 = hash(&path, 0, 0, &mut |_, _| Ok(())).unwrap();
        InputPart { path, sha256 }
    }
    #[test]
    fn exact_multi_source_pcm_and_cancel_preserve_originals() {
        let root =
            std::env::temp_dir().join(format!("companion-edit-pcm-{}", uuid::Uuid::new_v4()));
        fs::create_dir(&root).unwrap();
        let a = root.join("a1.wav");
        let a2 = root.join("a2.wav");
        let b = root.join("b.wav");
        wav(&a, 100, 8);
        wav(&a2, 108, 8);
        wav(&b, 200, 17);
        let sa = source("source-a", 'a', 16);
        let sb = source("source-b", 'b', 17);
        let inputs = vec![
            Input {
                source: sa.clone(),
                meeting: None,
                parts: vec![part(a.clone()), part(a2.clone())],
            },
            Input {
                source: sb.clone(),
                meeting: None,
                parts: vec![part(b.clone())],
            },
        ];
        let ranges = [(&sa, 4, 10), (&sb, 2, 6), (&sa, 0, 3)];
        let mut output = 0;
        let mut slices = Vec::new();
        for (s, start, end) in ranges {
            let next = output + end - start;
            slices.push(Slice {
                source_key: s.key.clone(),
                source_identity: s.identity.clone(),
                start_frame: start,
                end_frame: end,
                output_start_frame: output,
                output_end_frame: next,
            });
            output = next;
        }
        let plan = Plan {
            schema: 1,
            sample_rate: 16000,
            frames: 13,
            slices,
        };
        let saved = render(&root, &inputs, &plan, |_, _| Ok(())).unwrap();
        let raw = fs::read(&saved.temporary).unwrap();
        let actual: Vec<_> = raw[44..]
            .chunks_exact(2)
            .map(|b| i16::from_le_bytes([b[0], b[1]]))
            .collect();
        assert_eq!(
            actual,
            vec![104, 105, 106, 107, 108, 109, 202, 203, 204, 205, 100, 101, 102]
        );
        assert_eq!(saved.bytes, 70);
        assert_eq!(saved.frames, 13);
        assert_eq!(
            hash(&saved.temporary, 0, 0, &mut |_, _| Ok(())).unwrap(),
            saved.sha256
        );
        let before = fs::read_dir(&root).unwrap().count();
        assert!(render(&root, &inputs, &plan, |done, _| if done > 0 {
            Err("cancelled".into())
        } else {
            Ok(())
        })
        .is_err());
        assert_eq!(fs::read_dir(&root).unwrap().count(), before);
        for input in &inputs {
            for p in &input.parts {
                assert_eq!(hash(&p.path, 0, 0, &mut |_, _| Ok(())).unwrap(), p.sha256);
            }
        }
        let mut stale = plan.clone();
        stale.slices[0].source_identity = "f".repeat(64);
        assert!(stale.validate(&[sa.clone(), sb.clone()]).is_err());
        let mut damaged = plan.clone();
        damaged.slices[1].output_start_frame += 1;
        assert!(damaged.validate(&[sa.clone(), sb.clone()]).is_err());
        let wire = serde_json::to_value(plan.provenance(&[sa, sb]).unwrap()).unwrap();
        assert!(serde_json::from_value::<Provenance>(wire)
            .unwrap()
            .validate()
            .is_ok());
        // Deliberately keep this tiny generated fixture directory for failed-run
        // diagnosis; no user paths or recordings are used by this test.
    }
}
