//! Companion-Type owned transcription boundary.
//!
//! This module intentionally does not shell out to Listener-Type. The first
//! production adapters can plug in here without changing the app IPC surface.
//! The OpenAI-compatible HTTP client itself lives in the platform
//! `denzic-host-audio-v1-core` crate; this module keeps provider selection,
//! env-var plumbing, and the Companion-specific guardrails.

use std::fs;
use std::path::{Path, PathBuf};
use std::time::Duration;


mod chunk_cache;
#[cfg(windows)]
mod local_paraformer;

use super::diarization::{self, EmbeddingSegment};
use super::volcengine::{Utterance, VolcengineCredentials, VolcengineSaucAsr};
use crate::companion_v1::CompanionV1UtteranceSegment;
use denzic_host_audio_v1_core::asr::{
    normalize_transcript as platform_normalize_transcript, BatchAsrProvider,
};
use denzic_host_audio_v1_core::asr_openai::{OpenAiAsrConfig, OpenAiCompatibleAsr};
use denzic_host_audio_v1_core::{
    ASR_DEFAULT_MAX_UPLOAD_BYTES, ASR_DEFAULT_MODEL, ASR_OPENAI_TRANSCRIPTION_ENDPOINT,
    ASR_REQUEST_TIMEOUT_SECONDS,
};

/// Preserve the provider's words. A fixed list of engineering homophones can
/// silently change legitimate meeting content; only whitespace is normalized.
fn normalize_transcript(text: &str) -> String {
    platform_normalize_transcript(text)
}

#[derive(Clone, Debug)]
pub struct CompanionTranscript {
    pub text: String,
    pub provider_id: String,
    pub mode: String,
    pub evidence_path: Option<PathBuf>,
    /// Timed, speaker-attributed utterances (when the provider returns them).
    /// Empty for env-text / sidecar / command / openai paths and when the
    /// volcengine response carried no utterance timing.
    pub utterances: Vec<CompanionV1UtteranceSegment>,
}

#[derive(Clone, Debug)]
pub struct CompanionTranscriptionManager;

impl CompanionTranscriptionManager {
    pub fn new() -> Self {
        Self
    }

    /// Explicit pet utterance, using the configured real provider only. Meeting
    /// correction rules, sidecars, env-text fixtures and speaker clustering do
    /// not rewrite or substitute this microphone utterance.
    pub(crate) fn transcribe_pet_audio(&self,path:&Path)->Result<String,String> {
        let _usage=super::audio_artifacts::usage(path)?;
        let provider=std::env::var("COMPANION_TYPE_ASR_PROVIDER").unwrap_or_default();
        let text=if provider.eq_ignore_ascii_case("volcengine") && volcengine_provider_configured() {
            volcengine_client()?.transcribe_file(path)?.0
        } else if matches!(provider.to_ascii_lowercase().as_str(),"openai"|"openai-compatible") && openai_provider_configured() {
            openai_compatible_transcript(path)?.text
        } else {return Err("请先在现有设置中配置语音转写，聊天不会另选服务。".into());};
        let text=platform_normalize_transcript(&text);
        if text.trim().is_empty() {return Err("这次没有听清，轻点开聊后再说一次。".into());}
        if text.chars().count()>400 {return Err("这句话太长，请分成短句再聊。".into());}
        Ok(text)
    }

    pub fn transcribe_session_owned(&self, session: &str, primary: Option<&str>, chunks: &[String]) -> Result<CompanionTranscript, String> {
        let _diagnostic_scope=super::diagnostics::RecordingScope::enter(session);
        let result = self.transcribe_session(primary, chunks);
        let paths: Vec<String> = primary.iter().map(|p| p.to_string()).chain(chunks.iter().cloned()).collect();
        // Bind successful chunks even when a later request failed. Recovery and
        // transcript deletion must find them after scratch cleanup or restart.
        if bind_cache_session(session, &paths).is_err() {
            eprintln!("[transcription] cache session binding pending; final result preserved");
        }
        result
    }

    pub fn transcribe_audio_owned(&self, session: &str, path: &str) -> Result<CompanionTranscript, String> {
        self.transcribe_session_owned(session, Some(path), &[])
    }

    pub fn transcribe_audio(&self, audio_path: &str) -> Result<CompanionTranscript, String> {
        super::diagnostics::Span::start(super::diagnostics::Operation::Transcription).result(self.transcribe_audio_inner(audio_path))
    }

    fn transcribe_audio_inner(&self, audio_path: &str) -> Result<CompanionTranscript, String> {
        let audio = PathBuf::from(audio_path);
        if !audio.exists() {
            return Err(format!("audio path does not exist: {}", audio.display()));
        }
        let _usage = super::audio_artifacts::usage(&audio)?;
        self.transcribe_single_path(&audio)
    }

    /// Transcribe one primary path and optionally merge per-chunk files (long meetings).
    pub fn transcribe_session(
        &self,
        primary_audio: Option<&str>,
        chunk_paths: &[String],
    ) -> Result<CompanionTranscript, String> {
        super::diagnostics::Span::start(super::diagnostics::Operation::Transcription).result(self.transcribe_session_inner(primary_audio, chunk_paths))
    }

    fn transcribe_session_inner(&self, primary_audio: Option<&str>, chunk_paths: &[String]) -> Result<CompanionTranscript, String> {
        // Validate the declared sequence before a provider, cache or test source
        // can consume it. Missing segments must never become a shorter meeting.
        let mut declared_paths = Vec::with_capacity(chunk_paths.len());
        let mut identities = std::collections::HashSet::new();
        for (index, path) in chunk_paths.iter().enumerate() {
            let p = PathBuf::from(path);
            let metadata = fs::metadata(&p).map_err(|_| format!("录音缺段：第 {} / {} 段不可读取。已有录音保留，请重新同步或恢复原文件后重试。", index + 1, chunk_paths.len()))?;
            if !metadata.is_file() || metadata.len() == 0 {
                return Err(format!("录音缺段：第 {} / {} 段为空或不是文件，未提交转写。", index + 1, chunk_paths.len()));
            }
            let identity = fs::canonicalize(&p).map_err(|_| "无法确认录音分段，请恢复文件后重试。")?;
            if !identities.insert(identity) { return Err(format!("录音分段重复：第 {} 段，未提交转写。", index + 1)); }
            declared_paths.push(p);
        }
        if !local_provider_selected() {
            if let Ok(text) = std::env::var("COMPANION_TYPE_TRANSCRIPT_TEXT") {
                let text = normalize_transcript(&text);
                if !text.is_empty() {
                    return Ok(CompanionTranscript {
                        text,
                        provider_id: "companion-type-env-transcript".to_string(),
                        mode: "env-text".to_string(),
                        evidence_path: None,
                        utterances: Vec::new(),
                    });
                }
            }
        }

        let mut real_paths = declared_paths;
        if let Some(primary) = primary_audio {
            let p = PathBuf::from(primary);
            if p.exists() && !real_paths.iter().any(|existing| existing == &p) {
                // Prefer chunks when present; otherwise single primary.
                if real_paths.is_empty() {
                    real_paths.push(p);
                }
            }
        }
        if real_paths.is_empty() {
            return Err(
                "No transcribable audio path (missing host WAV / chunks). Import transcript or record first."
                    .to_string(),
            );
        }
        let _usage = real_paths.iter().map(|p| super::audio_artifacts::usage(p)).collect::<Result<Vec<_>, _>>()?;
        if real_paths.len() == 1 {
            return self.transcribe_single_path(&real_paths[0]);
        }

        // Long meeting (multiple chunks): when Volcengine is the provider,
        // diarize GLOBALLY across all chunks so speaker ids stay consistent —
        // per-chunk diarization would renumber the same person in each chunk.
        if volcengine_provider_configured() {
            return volcengine_multi_chunk_transcript(&real_paths, None);
        }

        let mut parts = Vec::new();
        let mut providers = Vec::new();
        for path in &real_paths {
            let transcript = self.transcribe_existing_path(path)?;
            providers.push(transcript.provider_id.clone());
            parts.push(transcript.text);
        }
        Ok(CompanionTranscript {
            text: normalize_transcript(&parts.join("\n")),
            provider_id: "companion-type-chunk-merge".to_string(),
            mode: format!(
                "merged-{}-chunks:{}",
                real_paths.len(),
                providers
                    .into_iter()
                    .collect::<std::collections::BTreeSet<_>>()
                    .into_iter()
                    .collect::<Vec<_>>()
                    .join("+")
            ),
            evidence_path: None,
            utterances: Vec::new(),
        })
    }

    /// Transcribe one audio path. If it is a single long WAV and Volcengine is
    /// configured, split it into N concurrent SAUC sessions so ASR wall-clock ≈
    /// duration/N; otherwise fall back to the normal single-path transcribe
    /// (which also handles env-text and sidecar transcripts). Shared by both the
    /// session flow and the CLI `transcribe_audio` entry so the long-meeting
    /// speedup cannot be bypassed by entering through a different API.
    fn transcribe_single_path(&self, path: &Path) -> Result<CompanionTranscript, String> {
        if volcengine_provider_configured() && is_long_wav(path) {
            let chunk_seconds = asr_safe_chunk_seconds();
            {
                let chunks = split_long_wav_into_chunks(path, chunk_seconds)
                    .map_err(|error| format!("长录音分段未完成，原音已保留，未提交转写：{error}"))?;
                if chunks.len() > 1 {
                    eprintln!(
                        "[transcription] long_wav safe_chunks={} chunk_seconds={} workers={} retries={}",
                        chunks.len(),
                        chunk_seconds,
                        asr_parallel_worker_count(),
                        asr_chunk_retry_count()
                    );
                    // Keep the unsplit source available for the final speaker
                    // pass.  ASR still uses provider-safe chunks, but speaker
                    // VAD must see turn boundaries across chunk seams.
                    let result = volcengine_multi_chunk_transcript(&chunks, Some(path));
                    // Best-effort cleanup of the temp chunk WAVs (never the
                    // source recording, which is `path`).
                    for chunk in &chunks {
                        if chunk.as_path() != path {
                            if super::audio_artifacts::remove_temporary(chunk).is_err() {
                                eprintln!("ASR temporary cleanup pending; recording ownership retained for retry");
                            }
                        }
                    }
                    return result;
                }
            }
        }
        self.transcribe_existing_path(path)
    }

    fn transcribe_existing_path(&self, audio: &Path) -> Result<CompanionTranscript, String> {
        if local_provider_selected() {
            #[cfg(windows)]
            { return local_paraformer::transcribe(audio); }
            #[cfg(not(windows))]
            { return Err("此平台暂不支持本地转写；原录音保留。".into()); }
        }
        if let Ok(text) = std::env::var("COMPANION_TYPE_TRANSCRIPT_TEXT") {
            let text = normalize_transcript(&text);
            if !text.is_empty() {
                return Ok(CompanionTranscript {
                    text,
                    provider_id: "companion-type-env-transcript".to_string(),
                    mode: "env-text".to_string(),
                    evidence_path: None,
                    utterances: Vec::new(),
                });
            }
        }

        if let Some(path) = transcript_sidecar(audio) {
            let text = fs::read_to_string(&path)
                .map_err(|err| format!("read transcript sidecar {}: {err}", path.display()))?;
            let text = normalize_transcript(&text);
            if text.is_empty() {
                return Err(format!("transcript sidecar is empty: {}", path.display()));
            }
            return Ok(CompanionTranscript {
                text,
                provider_id: "companion-type-sidecar-transcript".to_string(),
                mode: "audio-sidecar".to_string(),
                evidence_path: Some(path),
                utterances: Vec::new(),
            });
        }

        if std::env::var("COMPANION_TYPE_ASR_COMMAND").is_ok() {
            reject_listener_type_command()?;
        }

        if volcengine_provider_configured() {
            return volcengine_transcript(audio);
        }

        if openai_provider_configured() {
            return openai_compatible_transcript(audio);
        }

        if std::env::var("COMPANION_TYPE_ASR_COMMAND").is_ok() {
            return command_transcript(audio);
        }

        Err(
            "No Companion-Type transcription provider is configured. Set COMPANION_TYPE_TRANSCRIPT_TEXT, add an audio .transcript.txt sidecar, configure COMPANION_TYPE_ASR_ENDPOINT/API_KEY, or set COMPANION_TYPE_ASR_COMMAND.".to_string(),
        )
    }
}

fn local_provider_selected() -> bool {
    std::env::var("COMPANION_TYPE_ASR_PROVIDER").unwrap_or_default().eq_ignore_ascii_case("local-paraformer")
}

impl Default for CompanionTranscriptionManager {
    fn default() -> Self {
        Self::new()
    }
}

fn transcript_sidecar(audio: &Path) -> Option<PathBuf> {
    let mut candidates = Vec::new();
    if let Some(stem) = audio.file_stem().and_then(|value| value.to_str()) {
        candidates.push(audio.with_file_name(format!("{stem}.transcript.txt")));
    }
    candidates.push(audio.with_extension("txt"));
    candidates.push(PathBuf::from(format!("{}.txt", audio.display())));
    candidates.into_iter().find(|candidate| candidate.exists())
}

fn command_transcript(audio: &Path) -> Result<CompanionTranscript, String> {
    let command = std::env::var("COMPANION_TYPE_ASR_COMMAND")
        .map_err(|_| "COMPANION_TYPE_ASR_COMMAND is not set".to_string())?;
    reject_listener_type_command()?;

    let args = std::env::var("COMPANION_TYPE_ASR_ARGS").unwrap_or_else(|_| "{audio}".to_string());
    let args = split_command_args(&args).into_iter()
        .map(|arg| arg.replace("{audio}", &audio.to_string_lossy())).collect::<Vec<_>>();
    run_command_transcript(&command, &args, super::external_command::Limits::for_timeout(super::external_command::ASR_TIMEOUT))
}

pub(super) fn run_command_transcript(command: &str, args: &[String], limits: super::external_command::Limits) -> Result<CompanionTranscript, String> {
    if command.to_ascii_lowercase().contains("listener-type") { return Err("Companion-Type ASR command must not call listener-type".into()); }
    let stdout = super::external_command::run(command, args, limits, None)
        .map_err(|error| format!("Companion-Type ASR {error}; existing audio retained"))?;
    let text = normalize_transcript(&extract_transcript_from_stdout(&stdout)?);
    if text.is_empty() {
        return Err("Companion-Type ASR command did not print a transcript".to_string());
    }
    Ok(CompanionTranscript {
        text,
        provider_id: "companion-type-command-asr".to_string(),
        mode: "external-command".to_string(),
        evidence_path: None,
        utterances: Vec::new(),
    })
}

fn reject_listener_type_command() -> Result<(), String> {
    let command = std::env::var("COMPANION_TYPE_ASR_COMMAND")
        .map_err(|_| "COMPANION_TYPE_ASR_COMMAND is not set".to_string())?;
    if command.to_ascii_lowercase().contains("listener-type") {
        return Err("Companion-Type ASR command must not call listener-type".to_string());
    }
    Ok(())
}

fn volcengine_provider_configured() -> bool {
    // Explicit opt-in only: COMPANION_TYPE_ASR_PROVIDER=volcengine gates this
    // branch so it is never shadowed by a stray OPENAI_API_KEY (the OpenAI
    // check below is greedy and matches on any of four env vars).
    std::env::var("COMPANION_TYPE_ASR_PROVIDER")
        .unwrap_or_default()
        .eq_ignore_ascii_case("volcengine")
        && std::env::var("COMPANION_TYPE_VOLC_APP_KEY").is_ok()
        && std::env::var("COMPANION_TYPE_VOLC_ACCESS_KEY").is_ok()
}

/// Low-level: transcribe one WAV via Volcengine SAUC, returning the clean
/// merged text and the timed utterances (no diarization yet).
fn volcengine_client() -> Result<VolcengineSaucAsr, String> {
    let app_id = std::env::var("COMPANION_TYPE_VOLC_APP_KEY")
        .map_err(|_| "COMPANION_TYPE_VOLC_APP_KEY is not set".to_string())?;
    let access_token = std::env::var("COMPANION_TYPE_VOLC_ACCESS_KEY")
        .map_err(|_| "COMPANION_TYPE_VOLC_ACCESS_KEY is not set".to_string())?;
    let resource_id = std::env::var("COMPANION_TYPE_VOLC_RESOURCE_ID")
        .unwrap_or_else(|_| VolcengineCredentials::default_resource_id().to_string());
    Ok(VolcengineSaucAsr::new(VolcengineCredentials {
        app_id,
        access_token,
        resource_id,
    }))
}

/// For each utterance, find the index of the speaker-embedding segment with the
/// greatest positive temporal overlap. A gap is not evidence of a speaker:
/// leave it unknown instead of borrowing an unrelated neighbouring voice.
/// The caller lifts the overlapping segment for GLOBAL clustering across chunks.
fn embedding_index_for_range(
    start_ms: u64,
    end_ms: u64,
    segs: &[EmbeddingSegment],
) -> Option<usize> {
    if end_ms <= start_ms {
        return None;
    }
    let mut best: Option<(u64, usize)> = None;
    for (i, seg) in segs.iter().enumerate() {
        let overlap = end_ms.min(seg.end_ms).saturating_sub(start_ms.max(seg.start_ms));
        if overlap > 0 && best.map_or(true, |(b, _)| overlap > b) {
            best = Some((overlap, i));
        }
    }
    best.map(|(_, index)| index)
}

fn utterance_embedding_index(utt: &Utterance, segs: &[EmbeddingSegment]) -> Option<usize> {
    embedding_index_for_range(utt.start_ms, utt.end_ms, segs)
}

/// Working utterance carrying its lifted speaker embedding (for global
/// clustering) and ASR timing (for SRT / export).
#[derive(Clone, Debug, serde::Deserialize, serde::Serialize)]
struct CollectedUtterance {
    text: String,
    start_ms: u64,
    end_ms: u64,
    provider_speaker: Option<String>,
    #[serde(default)]
    provider_request: Option<u64>,
    embedding: Option<Vec<f32>>,
}

/// An utterance with its globally-assigned speaker id (0-based) + timing.
#[derive(Debug)]
struct TaggedUtterance {
    text: String,
    start_ms: u64,
    end_ms: u64,
    speaker: Option<usize>,
}

/// Collect per-utterance timing + embedding for one audio chunk: align each ASR
/// utterance to its dominant VAD/embedding segment and lift that segment's
/// embedding. Utterances VAD missed get no embedding (speaker later falls back
/// to "说话人?"); timing always comes from the ASR utterance.
fn collect_utterance_embeddings(audio: &Path, utterances: &[Utterance]) -> Vec<CollectedUtterance> {
    let segs = diarization::segment_embeddings(audio).unwrap_or_default();
    utterances
        .iter()
        .map(|utt| {
            let embedding = utterance_embedding_index(utt, &segs)
                .map(|segment_index| segs[segment_index].embedding.clone());
            CollectedUtterance {
                text: utt.text.clone(),
                start_ms: utt.start_ms,
                end_ms: utt.end_ms,
                provider_speaker: utt.speaker.clone(),
                provider_request: None,
                embedding,
            }
        })
        .collect()
}

/// Re-align already-transcribed, globally-timed utterances against one
/// continuous source WAV.  Long ASR requests are intentionally split into
/// provider-safe chunks; extracting speaker embeddings from those same chunks
/// changes the VAD noise floor at every seam. Use the continuous recording for
/// consistent segment alignment; this alone does not establish correct speaker
/// identities and does not require another ASR request or another recording.
fn recollect_embeddings_from_full_audio(
    audio: &Path,
    utterances: &mut [CollectedUtterance],
) {
    let Ok(segs) = diarization::segment_embeddings(audio) else {
        return;
    };
    for utterance in utterances {
        utterance.embedding = embedding_index_for_range(
            utterance.start_ms,
            utterance.end_ms,
            &segs,
        )
        .map(|segment_index| segs[segment_index].embedding.clone());
    }
}

pub(super) fn refine_saved_speakers(audio:&Path,utterances:&[crate::companion_v1::CompanionV1UtteranceSegment])
    ->Result<CompanionTranscript,String> {
    let _usage=super::audio_artifacts::usage(audio)?;
    let segments=diarization::segment_embeddings(audio)?;
    if segments.is_empty() {return Err("原音没有足够的可用声纹，保留原分组。".into());}
    let collected=utterances.iter().map(|u|CollectedUtterance {text:u.text.clone(),start_ms:u.start_ms,end_ms:u.end_ms,
        provider_speaker:None,provider_request:None,embedding:embedding_index_for_range(u.start_ms,u.end_ms,&segments)
            .map(|i|segments[i].embedding.clone())}).collect::<Vec<_>>();
    let mut result=volcengine_transcript_from("",&collected);
    result.provider_id="companion-local-speaker-refinement".into();result.mode="saved-timing-local-only".into();
    Ok(result)
}

/// Cluster per-utterance embeddings GLOBALLY and assign each utterance a
/// speaker id. Because clustering runs once over every utterance (across all
/// chunks), a speaker keeps the same id throughout a chunked long meeting —
/// the fix for per-chunk 1/2/1/2 renumbering. Pure: no audio access, testable.
fn cluster_utterances_by_speaker(per_utterance: &[CollectedUtterance]) -> Vec<TaggedUtterance> {
    let mut provider_labels = std::collections::BTreeMap::<String, usize>::new();
    let mut request_labels = std::collections::BTreeMap::<u64, std::collections::BTreeSet<&str>>::new();
    for utterance in per_utterance {
        if let Some(label) = utterance.provider_speaker.as_ref() {
            let next = provider_labels.len();
            provider_labels.entry(label.clone()).or_insert(next);
            if let Some(request) = utterance.provider_request {
                request_labels.entry(request).or_default().insert(label);
            }
        }
    }
    let mut embeddings: Vec<Vec<f32>> = Vec::new();
    let mut constraints = Vec::new();
    let mut emb_indices: Vec<Option<usize>> = Vec::with_capacity(per_utterance.len());
    for u in per_utterance {
        match &u.embedding {
            Some(e) => {
                emb_indices.push(Some(embeddings.len()));
                embeddings.push(e.clone());
                // A provider returning a single constant label has not
                // established separation. Do not let it erase distinct local
                // voices. Preserve evidence from requests with real labels.
                constraints.push(u.provider_request.and_then(|request| {
                    if request_labels.get(&request).is_some_and(|labels| labels.len() >= 2) {
                        u.provider_speaker.as_ref().map(|label| diarization::SpeakerConstraint {
                            request, label: label.clone(),
                        })
                    } else { None }
                }));
            }
            None => emb_indices.push(None),
        }
    }
    let speakers = if embeddings.is_empty() {
        Vec::new()
    } else if constraints.iter().all(Option::is_none) {
        diarization::cluster_speakers(&embeddings)
    } else {
        diarization::cluster_speakers_constrained(&embeddings, &constraints)
    };
    let local_speaker_count = speakers
        .iter()
        .copied()
        .collect::<std::collections::BTreeSet<_>>()
        .len();
    // Provider labels remain authoritative when they cover at least as many
    // identities as the local embedding pass.  SAUC can legitimately return
    // only two labels for a three-person synthetic/native-voice meeting; in
    // that under-count case, discarding a clear third local cluster loses a
    // real speaker.  Never mix the two id spaces: select one complete source.
    if per_utterance.iter().all(|u| u.provider_request.is_none())
        && provider_labels.len() >= 2
        && (local_speaker_count == 0 || provider_labels.len() >= local_speaker_count)
    {
        return per_utterance
            .iter()
            .map(|utterance| TaggedUtterance {
                text: utterance.text.clone(),
                start_ms: utterance.start_ms,
                end_ms: utterance.end_ms,
                speaker: utterance
                    .provider_speaker
                    .as_ref()
                    .and_then(|label| provider_labels.get(label).copied()),
            })
            .collect();
    }
    per_utterance
        .iter()
        .enumerate()
        .map(|(i, u)| TaggedUtterance {
            text: u.text.clone(),
            start_ms: u.start_ms,
            end_ms: u.end_ms,
            speaker: emb_indices[i].and_then(|gi| speakers.get(gi).copied()),
        })
        .collect()
}

/// Render utterances as a speaker-tagged transcript: "说话人N: <text>", merging
/// consecutive utterances from the same speaker onto one line. Speaker ids are
/// 0-based internally, shown 1-based to humans. None -> "说话人?".
fn render_tagged(utterances: &[TaggedUtterance]) -> String {
    let mut groups: Vec<(Option<usize>, String)> = Vec::new();
    for u in utterances {
        if let Some(last) = groups.last_mut() {
            if last.0 == u.speaker {
                last.1.push_str(&u.text);
                continue;
            }
        }
        groups.push((u.speaker, u.text.clone()));
    }
    groups
        .into_iter()
        .map(|(speaker, text)| {
            let label = match speaker {
                Some(id) => format!("说话人{}", id + 1),
                None => "说话人?".to_string(),
            };
            format!("{}: {}", label, text)
        })
        .collect::<Vec<_>>()
        .join("\n")
}

/// Build a CompanionTranscript from clean text + globally-clustered speaker
/// pairs. If at least one utterance got a real speaker, the transcript text is
/// the speaker-tagged form; otherwise it falls back to the clean merged text
/// (single-speaker / no-models behavior unchanged).
fn volcengine_transcript_from(
    clean_text: &str,
    per_utterance: &[CollectedUtterance],
) -> CompanionTranscript {
    // Timed segments can be incomplete when the provider omits a timestamp.
    // Never let a partial segmentation replace or later reconstruct the full text.
    if !clean_text.is_empty() && !per_utterance.is_empty() {
        let full: String = clean_text.chars().filter(|c| !c.is_whitespace()).collect();
        let timed: String = per_utterance.iter().flat_map(|u| u.text.chars())
            .filter(|c| !c.is_whitespace()).collect();
        if full != timed {
            return CompanionTranscript {
                text: normalize_transcript(clean_text),
                provider_id: "companion-type-volcengine-asr".to_string(),
                mode: "ws-sauc:bigmodel:incomplete-timed-segments".to_string(),
                evidence_path: None,
                utterances: Vec::new(),
            };
        }
    }
    let tagged = cluster_utterances_by_speaker(per_utterance);
    let any_speaker = tagged.iter().any(|u| u.speaker.is_some());
    let (text, mode) = if any_speaker {
        (
            normalize_transcript(&render_tagged(&tagged)),
            "ws-sauc:bigmodel+diarized".to_string(),
        )
    } else {
        (
            normalize_transcript(clean_text),
            "ws-sauc:bigmodel".to_string(),
        )
    };
    // Utterance segments (timing + speaker) are emitted whenever the provider
    // returned them, even without diarized speakers — SRT/subtitle export and
    // playback sync only need the timing.
    let utterances = tagged
        .iter()
        .map(|u| CompanionV1UtteranceSegment {
            text: u.text.clone(),
            start_ms: u.start_ms,
            end_ms: u.end_ms,
            speaker: u.speaker,
        })
        .collect();
    CompanionTranscript {
        text,
        provider_id: "companion-type-volcengine-asr".to_string(),
        mode,
        evidence_path: None,
        utterances,
    }
}

fn volcengine_transcript(audio: &Path) -> Result<CompanionTranscript, String> {
    let (clean_text, per_utterance) = volcengine_transcribe_cached(audio)?;
    Ok(volcengine_transcript_from(&clean_text, &per_utterance))
}

/// Shared durable consumer boundary for direct, online-partial and long-meeting
/// chunk transcription. Reuse only a final result for identical PCM and
/// effective provider configuration; local speaker features are always fresh.
fn volcengine_transcribe_cached(path: &Path) -> Result<(String, Vec<CollectedUtterance>), String> {
    let cache_root = asr_chunk_cache_root();
    let asr = volcengine_client()?;
    let pcm = diarization::read_pcm16k_mono_wav(path)?;
    let key = chunk_cache::Key::new(&pcm, chunk_cache::Profile::from_configuration(&asr.cache_configuration())?)?;
    let (text, utterances) = chunk_cache::ownership::resolve(&cache_root, &key, path, || asr.transcribe_pcm_bytes(&pcm))?;
    let collected = collect_utterance_embeddings(path, &utterances);
    Ok((text, collected))
}

pub(crate) fn verify_asr_cache(output: &Path) -> Result<serde_json::Value, String> {
    chunk_cache::verify(output)
}

/// Max concurrent Volcengine SAUC sessions. The Seed ASR trial instance used by
/// Companion has a small concurrency quota, so correctness defaults to one
/// session. Paid instances can opt in to more workers without changing the
/// chunk layout or transcript ordering.
fn asr_parallel_worker_count() -> usize {
    let raw = std::env::var("COMPANION_TYPE_ASR_PARALLEL_CHUNKS")
        .ok()
        .and_then(|v| v.parse::<usize>().ok())
        .unwrap_or(1);
    raw.clamp(1, 4)
}

/// Seed SAUC connections on the current product instance have been observed to
/// close between 68 and 98 seconds. Keep every product request comfortably
/// below that boundary. This also makes retries local instead of restarting a
/// ten-minute transcription.
fn asr_safe_chunk_seconds() -> usize {
    std::env::var("COMPANION_TYPE_ASR_CHUNK_SECONDS")
        .ok()
        .and_then(|v| v.parse::<usize>().ok())
        .unwrap_or(30)
        .clamp(10, 60)
}

/// Short recordings stay on the direct path. Longer recordings are split into
/// provider-safe requests; 45 seconds leaves ordinary 30-second live windows
/// untouched while protecting meetings from the connection-duration ceiling.
const LONG_WAV_SPLIT_THRESHOLD_BYTES: usize = 45 * 16_000 * 2;

const PCM_BYTES_PER_SECOND: usize = 16_000 * 2;

pub(super) fn asr_chunk_cache_root() -> PathBuf {
    if let Some(root) = std::env::var_os("COMPANION_TYPE_ASR_CACHE_DIR") { return PathBuf::from(root); }
    if let Some(root) = std::env::var_os("COMPANION_TYPE_RECORDING_DIR") { return PathBuf::from(root).join(".asr-chunk-cache"); }
    std::env::var_os("LOCALAPPDATA")
        .map(PathBuf::from)
        .unwrap_or_else(std::env::temp_dir)
        .join("Companion Type")
        .join("asr-chunk-cache")
}

fn bind_cache_session(session: &str, paths: &[String]) -> Result<(), String> {
    let mut sources = std::collections::BTreeSet::new();
    for path in paths { sources.extend(super::audio_artifacts::source_references(Path::new(path))?); }
    chunk_cache::ownership::bind_session(&asr_chunk_cache_root(), session, &sources)
}
pub(super) fn attach_cache_sources(sources: &std::collections::BTreeSet<String>, owner: &str) -> Result<(), String> {
    chunk_cache::ownership::attach(&asr_chunk_cache_root(), sources, owner)
}
pub(super) use chunk_cache::ownership::erase as erase_cache;
pub(crate) use chunk_cache::ownership::verify as verify_cache_privacy;

/// Cheap size check: is this single WAV worth splitting into parallel sessions?
fn is_long_wav(path: &Path) -> bool {
    let is_wav = path
        .extension()
        .and_then(|e| e.to_str())
        .map(|e| e.eq_ignore_ascii_case("wav"))
        .unwrap_or(false);
    if !is_wav {
        return false;
    }
    fs::metadata(path)
        .map(|m| (m.len() as usize) >= LONG_WAV_SPLIT_THRESHOLD_BYTES)
        .unwrap_or(false)
}

/// Write a minimal 44-byte-header 16 kHz / mono / s16 PCM WAV. The chunk WAVs
/// produced here must be readable back by `diarization::read_pcm16k_mono_wav`
/// (RIFF/WAVE + a `data` chunk), which they are.
fn write_pcm16k_mono_wav(path: &Path, pcm: &[u8]) -> Result<(), String> {
    let data_size = pcm.len() as u32;
    let sample_rate: u32 = 16_000;
    let channels: u16 = 1;
    let bits: u16 = 16;
    let byte_rate = sample_rate * (channels as u32) * (bits as u32) / 8;
    let block_align = channels * (bits / 8);
    let mut out = Vec::with_capacity(44 + pcm.len());
    out.extend_from_slice(b"RIFF");
    out.extend_from_slice(&(36 + data_size).to_le_bytes());
    out.extend_from_slice(b"WAVE");
    out.extend_from_slice(b"fmt ");
    out.extend_from_slice(&16u32.to_le_bytes());
    out.extend_from_slice(&1u16.to_le_bytes()); // PCM
    out.extend_from_slice(&channels.to_le_bytes());
    out.extend_from_slice(&sample_rate.to_le_bytes());
    out.extend_from_slice(&byte_rate.to_le_bytes());
    out.extend_from_slice(&block_align.to_le_bytes());
    out.extend_from_slice(&bits.to_le_bytes());
    out.extend_from_slice(b"data");
    out.extend_from_slice(&data_size.to_le_bytes());
    out.extend_from_slice(pcm);
    fs::write(path, out).map_err(|e| format!("write chunk wav {}: {e}", path.display()))
}

/// Split one long 16 kHz / mono / s16 WAV into fixed-duration, 100 ms aligned
/// chunks in original order. The final chunk may be shorter; coverage is exact
/// with no overlap, gap, or duplicated PCM.
pub(super) fn split_long_wav_into_chunks(src: &Path, chunk_seconds: usize) -> Result<Vec<PathBuf>, String> {
    let pcm = diarization::read_pcm16k_mono_wav(src)?;
    if pcm.is_empty() {
        return Err("cannot split empty PCM".to_string());
    }
    let frame = 3_200usize; // 100 ms at 16 kHz / s16 / mono
    let chunk_bytes = ((chunk_seconds.max(1) * PCM_BYTES_PER_SECOND) / frame) * frame;
    if pcm.len() <= chunk_bytes {
        return Ok(vec![src.to_path_buf()]);
    }
    let temp_dir = super::audio_storage::recording_root()?;
    let split_id = uuid::Uuid::new_v4().simple().to_string();
    let mut paths: Vec<PathBuf> = Vec::with_capacity(pcm.len().div_ceil(chunk_bytes));
    let mut start = 0usize;
    let mut i = 0usize;
    while start < pcm.len() {
        let end = (start + chunk_bytes).min(pcm.len());
        let path = temp_dir.join(format!(
            ".companion-asr-{split_id}-{i}.wav"
        ));
        if let Err(error) = super::audio_artifacts::generated(src, &path, super::audio_artifacts::Purpose::AsrTemporary,
            || write_pcm16k_mono_wav(&path, &pcm[start..end])) {
            let _ = super::audio_artifacts::remove_temporary(&path);
            for created in &paths { let _ = super::audio_artifacts::remove_temporary(created); }
            return Err(error);
        }
        paths.push(path);
        start = end;
        i += 1;
    }
    Ok(paths)
}

/// Multi-chunk long-meeting path: transcribe each chunk, collect per-utterance
/// embeddings from every chunk, then cluster GLOBALLY once so speaker ids stay
/// consistent across chunks (instead of per-chunk renumbering). The tagged
/// transcript follows chunk order, utterance order within each chunk.
///
/// Chunks are consumed by a bounded worker pool and retried locally. Results are
/// still merged by source index, never completion order. The conservative
/// default is one worker because the current Seed ASR instance rejects larger
/// bursts; deployments with a larger quota can opt in through the environment.
fn volcengine_multi_chunk_transcript(
    paths: &[PathBuf],
    continuous_source: Option<&Path>,
) -> Result<CompanionTranscript, String> {
    volcengine_multi_chunk_transcript_with(paths, continuous_source, &transcribe_long_meeting_chunk)
}

fn volcengine_multi_chunk_transcript_with<F>(
    paths: &[PathBuf],
    continuous_source: Option<&Path>,
    transcribe: &F,
) -> Result<CompanionTranscript, String>
where F: Fn(&Path, u64) -> Result<ChunkTranscription, String> + Sync {
    let n = paths.len();
    let retry_count = asr_chunk_retry_count();
    // Each per-chunk task does BOTH the SAUC transcription AND its diarization
    // embedding extraction, so the whole per-chunk pipeline (not just ASR) runs
    // concurrently. Embeddings are best-effort (segment_embeddings failures map
    // to empty vecs inside collect_utterance_embeddings) and never sink a chunk's
    // transcript. Slot: Some(Ok((text, embeds))) on success, Some(Err) on ASR
    // failure, None if the worker panicked.
    let mut results: Vec<Option<Result<(String, Vec<CollectedUtterance>), String>>> =
        (0..n).map(|_| None).collect();
    let workers = asr_parallel_worker_count().min(n.max(1));
    for batch_start in (0..n).step_by(workers) {
        let batch_end = (batch_start + workers).min(n);
        std::thread::scope(|scope| {
            let handles: Vec<_> = (batch_start..batch_end)
                .map(|i| {
                    let path = &paths[i];
                    scope.spawn(move || {
                        let mut last_error = String::new();
                        let chunk_retry_count = retry_count;
                        for attempt in 1..=chunk_retry_count {
                            match transcribe(path, i as u64) {
                                Ok(chunk) => return (i, Ok(chunk)),
                                Err(error) => {
                                    last_error =
                                        format!("attempt {attempt}/{chunk_retry_count}: {error}");
                                    eprintln!(
                                        "[transcription] chunk={}/{} {}",
                                        i + 1,
                                        n,
                                        last_error
                                    );
                                    if !asr_error_is_retryable(&error) {
                                        break;
                                    }
                                    if attempt < chunk_retry_count {
                                        std::thread::sleep(Duration::from_secs(2));
                                    }
                                }
                            }
                        }
                        (i, Err(last_error))
                    })
                })
                .collect();
            for handle in handles {
                if let Ok((i, res)) = handle.join() {
                    results[i] = Some(res);
                }
            }
        });
        // All chunks use the same saved credentials. Once a completed batch
        // has an explicit authentication rejection, more batches cannot fix
        // it; preserve the error and let the user correct the configuration.
        if let Some((index, error)) = first_auth_failure(&results) {
            return Err(format!("chunk {} of {}: {error}", index + 1, n));
        }
    }

    // An explicit, valid empty final after EOS is a completed recognition with
    // no words, not a transport failure. Quiet intervals in a continuous
    // recording must not discard the real transcript from the other chunks.
    // This classification is emitted only by the strict receive loop; a close
    // without a valid final, timeout or malformed response stays a failure.
    accept_completed_no_speech_chunks(continuous_source, &mut results);
    // Every remaining failed leading or middle window remains a failure, even
    // if later requests succeed. A close does not establish silent pre-roll.
    // Seed SAUC occasionally closes one session without a final result while
    // accepting the following sessions. Retrying that failed chunk five times
    // immediately merely spends every attempt inside the same transient
    // rejection window. Once all other chunks have run, retry only the failed
    // chunks again: the intervening real work is a natural cooldown, and no
    // middle chunk is ever silently treated as empty.
    let deferred_retry_count = asr_deferred_retry_count();
    let failed_indices = results
        .iter()
        .enumerate()
        .filter_map(|(i, result)| match result {
            Some(Err(error)) if asr_error_is_retryable(error) => Some(i),
            _ => None,
        })
        .collect::<Vec<_>>();
    for i in failed_indices {
        let path = &paths[i];
        let mut last_error = match results[i].as_ref() {
            Some(Err(error)) => error.clone(),
            _ => String::new(),
        };
        eprintln!(
            "[transcription] chunk={}/{} deferred_recovery=1 retries={}",
            i + 1,
            n,
            deferred_retry_count
        );
        for attempt in 1..=deferred_retry_count {
            if attempt > 1 {
                // Increasing cooldown prevents a temporary provider-side
                // session throttle from consuming the whole recovery budget.
                std::thread::sleep(Duration::from_secs(5 * attempt as u64));
            }
            match transcribe(path, i as u64) {
                Ok(chunk) => {
                    eprintln!(
                        "[transcription] chunk={}/{} deferred_recovery_pass attempt={}/{}",
                        i + 1,
                        n,
                        attempt,
                        deferred_retry_count
                    );
                    results[i] = Some(Ok(chunk));
                    break;
                }
                Err(error) => {
                    last_error =
                        format!("deferred attempt {attempt}/{deferred_retry_count}: {error}");
                    eprintln!("[transcription] chunk={}/{} {}", i + 1, n, last_error);
                    if !asr_error_is_retryable(&error) {
                        break;
                    }
                }
            }
        }
        if !matches!(results[i], Some(Ok(_))) {
            results[i] = Some(Err(last_error));
        }
    }
    // Only an explicit completed no-speech result may finish an empty tail.
    // A closed connection without a final is unknown, even for quiet audio.
    // Independent files have no proven post-roll boundary and must all succeed.
    if n > 1 {
        let final_index = n - 1;
        let earlier_chunks_complete = results[..final_index].iter().all(|result| matches!(result, Some(Ok(_))));
        let earlier_chunks_have_text = results[..final_index].iter().any(|result| {
            matches!(result, Some(Ok((text, _))) if !text.trim().is_empty())
        });
        let final_error = match results[final_index].as_ref() {
            Some(Err(error)) => Some(error.as_str()),
            _ => None,
        };
        if earlier_chunks_complete && earlier_chunks_have_text && final_error.is_some_and(|error| {
            continuous_tail_may_be_empty(continuous_source, &paths[final_index], error)
        }) {
            eprintln!("[transcription] chunk={}/{} completed_no_speech_tail=1", n, n);
            results[final_index] = Some(Ok((String::new(), Vec::new())));
        }
    }
    let completed = complete_chunk_results(results)?;
    let (clean_text, mut per_utterance) = merge_chunk_transcriptions(paths, completed);
    if let Some(source) = continuous_source {
        recollect_embeddings_from_full_audio(source, &mut per_utterance);
    }
    Ok(volcengine_transcript_from(&clean_text, &per_utterance))
}

fn merge_chunk_transcriptions(
    paths: &[PathBuf],
    completed: Vec<ChunkTranscription>,
) -> (String, Vec<CollectedUtterance>) {
    let mut per_utterance: Vec<CollectedUtterance> = Vec::new();
    let mut clean_parts: Vec<String> = Vec::new();
    let mut timeline_offset_ms = 0u64;
    for (path, (text, mut embeds)) in paths.iter().zip(completed) {
        for utterance in &mut embeds {
            utterance.start_ms = utterance.start_ms.saturating_add(timeline_offset_ms);
            utterance.end_ms = utterance.end_ms.saturating_add(timeline_offset_ms);
        }
        clean_parts.push(text);
        per_utterance.extend(embeds);
        timeline_offset_ms = timeline_offset_ms.saturating_add(wav_duration_ms(path));
    }
    (clean_parts.join("\n"), per_utterance)
}

type ChunkTranscription = (String, Vec<CollectedUtterance>);

fn accept_completed_no_speech_chunks(
    continuous_source: Option<&Path>,
    results: &mut [Option<Result<ChunkTranscription, String>>],
) {
    if continuous_source.is_none() { return; }
    let total = results.len();
    for (index, result) in results.iter_mut().enumerate() {
        if matches!(result, Some(Err(error)) if super::volcengine::is_no_speech_error(error)) {
            eprintln!("[transcription] chunk={}/{} completed_no_speech=1 original_audio_retained=1", index + 1, total);
            *result = Some(Ok((String::new(), Vec::new())));
        }
    }
}

fn complete_chunk_results(
    results: Vec<Option<Result<ChunkTranscription, String>>>,
) -> Result<Vec<ChunkTranscription>, String> {
    let total = results.len();
    let completed = results.into_iter().enumerate().map(|(index, result)| {
        result.ok_or_else(|| format!("ASR worker thread panicked on chunk {}", index + 1))?
            .map_err(|error| format!("chunk {} of {}: {error}", index + 1, total))
    }).collect::<Result<Vec<_>, _>>()?;
    if completed.iter().all(|(text, _)| text.trim().is_empty()) {
        return Err(super::volcengine::NO_SPEECH_ERROR.into());
    }
    Ok(completed)
}

fn continuous_tail_may_be_empty(source: Option<&Path>, _tail: &Path, error: &str) -> bool {
    // A provider's explicit final empty result is evidence of no recognized
    // speech. Energy alone cannot establish this: a real voice may be quiet.
    source.is_some() && super::volcengine::is_no_speech_error(error)
}

fn transcribe_long_meeting_chunk(path: &Path, request: u64) -> Result<(String, Vec<CollectedUtterance>), String> {
    let _usage = super::audio_artifacts::usage(path)?;
    let (text, mut embeds) = volcengine_transcribe_cached(path)?;
    // Provider speaker ids restart at zero for each independent SAUC
    // websocket. They are authoritative for a single request but cannot be
    // compared across long-meeting chunks. Preserve the labels with their
    // request namespace so global reconciliation retains within-request
    // distinctions without equating unrelated reused labels across chunks.
    for utterance in &mut embeds {
        utterance.provider_request = Some(request);
    }
    Ok((text, embeds))
}

fn wav_duration_ms(path: &Path) -> u64 {
    diarization::read_pcm16k_mono_wav(path)
        .map(|pcm| (pcm.len() as u64).saturating_mul(1_000) / PCM_BYTES_PER_SECOND as u64)
        .unwrap_or(0)
}

fn asr_chunk_retry_count() -> usize {
    std::env::var("COMPANION_TYPE_ASR_CHUNK_RETRIES")
        .ok()
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(5)
        .clamp(3, 8)
}

fn asr_deferred_retry_count() -> usize {
    std::env::var("COMPANION_TYPE_ASR_DEFERRED_RETRIES")
        .ok()
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(3)
        .clamp(1, 5)
}

fn asr_auth_rejected(error: &str) -> bool {
    error.contains("Volcengine auth rejected (HTTP 401)")
        || error.contains("Volcengine auth rejected (HTTP 403)")
}

fn first_auth_failure(results: &[Option<Result<ChunkTranscription, String>>]) -> Option<(usize, &str)> {
    results.iter().enumerate().find_map(|(index, result)| match result {
        Some(Err(error)) if asr_auth_rejected(error) => Some((index, error.as_str())),
        _ => None,
    })
}

fn asr_error_is_retryable(error: &str) -> bool {
    !super::volcengine::is_no_speech_error(error) && !asr_auth_rejected(error)
}

fn openai_provider_configured() -> bool {
    matches!(
        std::env::var("COMPANION_TYPE_ASR_PROVIDER")
            .unwrap_or_default()
            .to_ascii_lowercase()
            .as_str(),
        "openai" | "openai-compatible"
    ) || std::env::var("COMPANION_TYPE_ASR_ENDPOINT").is_ok()
        || std::env::var("COMPANION_TYPE_ASR_API_KEY").is_ok()
        || std::env::var("OPENAI_API_KEY").is_ok()
}

fn openai_compatible_transcript(audio: &Path) -> Result<CompanionTranscript, String> {
    let endpoint = std::env::var("COMPANION_TYPE_ASR_ENDPOINT")
        .unwrap_or_else(|_| ASR_OPENAI_TRANSCRIPTION_ENDPOINT.to_string());
    if endpoint.to_ascii_lowercase().contains("listener-type") {
        return Err("Companion-Type ASR endpoint must not reference listener-type".to_string());
    }
    let api_key = std::env::var("COMPANION_TYPE_ASR_API_KEY")
        .or_else(|_| std::env::var("OPENAI_API_KEY"))
        .map_err(|_| {
            "OpenAI-compatible ASR requires COMPANION_TYPE_ASR_API_KEY or OPENAI_API_KEY"
                .to_string()
        })?;
    let model =
        std::env::var("COMPANION_TYPE_ASR_MODEL").unwrap_or_else(|_| ASR_DEFAULT_MODEL.to_string());
    let max_upload = std::env::var("COMPANION_TYPE_ASR_MAX_UPLOAD_BYTES")
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(ASR_DEFAULT_MAX_UPLOAD_BYTES);

    let mut config = OpenAiAsrConfig::new(endpoint, api_key);
    config.model = model.clone();
    config.max_upload_bytes = max_upload;
    config.timeout = Duration::from_secs(ASR_REQUEST_TIMEOUT_SECONDS);
    let provider = OpenAiCompatibleAsr::new(config);

    let transcript = provider
        .transcribe_file(audio)
        .map_err(|err| err.to_string())?;
    Ok(CompanionTranscript {
        text: transcript.text,
        provider_id: "companion-type-openai-compatible-asr".to_string(),
        mode: format!("http-multipart:{model}"),
        evidence_path: None,
        utterances: Vec::new(),
    })
}

fn extract_transcript_from_stdout(stdout: &str) -> Result<String, String> {
    let trimmed = stdout.trim();
    if trimmed.starts_with(['{', '[']) {
        let invalid = || "ASR command output is invalid or incomplete; existing audio retained".to_string();
        let value: serde_json::Value = serde_json::from_str(trimmed).map_err(|_| invalid())?;
        if value.get("error").is_some() || value.get("is_final").or_else(|| value.get("isFinal"))
            .is_some_and(|flag| flag.as_bool() != Some(true)) { return Err(invalid()); }
        let text = value.get("text").or_else(|| value.get("transcript")).and_then(serde_json::Value::as_str)
            .or_else(|| value.pointer("/transcript/text").and_then(serde_json::Value::as_str)).ok_or_else(invalid)?;
        return Ok(text.to_string());
    }
    for line in stdout.lines() {
        let trimmed = line.trim();
        if let Some(value) = trimmed.strip_prefix("transcript=") {
            return Ok(value.trim().to_string());
        }
        if let Some(value) = trimmed.strip_prefix("text=") {
            return Ok(value.trim().to_string());
        }
    }
    Ok(trimmed.to_string())
}

fn split_command_args(value: &str) -> Vec<String> {
    let mut args = Vec::new();
    let mut current = String::new();
    let mut quote: Option<char> = None;
    for ch in value.chars() {
        match (quote, ch) {
            (Some(active), next) if next == active => quote = None,
            (None, '"' | '\'') => quote = Some(ch),
            (None, ch) if ch.is_whitespace() => {
                if !current.is_empty() {
                    args.push(current.clone());
                    current.clear();
                }
            }
            _ => current.push(ch),
        }
    }
    if !current.is_empty() {
        args.push(current);
    }
    args
}

#[cfg(test)]
mod tests {
    use super::*;
    struct RecordingOverride(Option<std::ffi::OsString>);
    impl RecordingOverride {
        fn new(path: &Path) -> Self { let old = std::env::var_os("COMPANION_TYPE_RECORDING_DIR"); std::env::set_var("COMPANION_TYPE_RECORDING_DIR", path); Self(old) }
    }
    impl Drop for RecordingOverride {
        fn drop(&mut self) { if let Some(value) = &self.0 { std::env::set_var("COMPANION_TYPE_RECORDING_DIR", value); } else { std::env::remove_var("COMPANION_TYPE_RECORDING_DIR"); } }
    }

    #[test]
    fn declared_missing_and_duplicate_segments_are_rejected_before_provider() {
        let root = std::env::temp_dir().join(format!("companion-chunk-preservation-{}", uuid::Uuid::new_v4()));
        fs::create_dir_all(&root).unwrap();
        let first = root.join("first.wav");
        write_pcm16k_mono_wav(&first, &[0; 3200]).unwrap();
        let original = fs::read(&first).unwrap();
        let manager = CompanionTranscriptionManager::new();
        let paths = vec![first.to_string_lossy().into_owned(), root.join("missing.wav").to_string_lossy().into_owned()];
        assert!(manager.transcribe_session(Some(&paths[0]), &paths).unwrap_err().contains("第 2 / 2 段"));
        assert!(manager.transcribe_session(None, &[paths[0].clone(),paths[0].clone()]).unwrap_err().contains("重复"));
        assert_eq!(fs::read(&first).unwrap(), original);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn truncated_wav_is_not_silently_shortened_and_split_runs_are_isolated() {
        let root = std::env::temp_dir().join(format!("companion-split-preservation-{}", uuid::Uuid::new_v4()));
        fs::create_dir_all(&root).unwrap(); let source = root.join("recording.wav");
        let _recordings = RecordingOverride::new(&root);
        let pcm = (0..70_000).map(|index| (index % 251) as u8).collect::<Vec<_>>();
        write_pcm16k_mono_wav(&source, &pcm).unwrap();
        let first = split_long_wav_into_chunks(&source, 1).unwrap();
        let second = split_long_wav_into_chunks(&source, 1).unwrap();
        assert!(first.iter().all(|path| !second.contains(path)));
        let recovered = first.iter().flat_map(|path| diarization::read_pcm16k_mono_wav(path).unwrap()).collect::<Vec<_>>();
        assert_eq!(recovered, pcm);
        let mut bytes = fs::read(&source).unwrap(); bytes.pop(); fs::write(&source, &bytes).unwrap();
        assert!(split_long_wav_into_chunks(&source, 1).unwrap_err().contains("truncated"));
        assert_eq!(fs::read(&source).unwrap(), bytes);
        for path in first.iter().chain(&second) { super::super::audio_artifacts::remove_temporary(path).unwrap(); }
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn full_provider_text_survives_incomplete_timed_utterances() {
        let parts = vec![
            CollectedUtterance { text:"第一句。".into(), start_ms:0, end_ms:1000,
                provider_speaker:Some("A".into()), provider_request:None, embedding:None },
            CollectedUtterance { text:"第二句。".into(), start_ms:2000, end_ms:3000,
                provider_speaker:Some("B".into()), provider_request:None, embedding:None },
        ];
        let full="第一句。第二句。被漏掉的第三句。";
        let result=volcengine_transcript_from(full,&parts);
        assert_eq!(result.text,full,"never replace full provider text by partial timed utterances");
        assert!(result.utterances.is_empty(),"incomplete timing must not be exposed as complete editable text");
        let no_speakers=parts.into_iter().map(|mut u|{u.provider_speaker=None;u}).collect::<Vec<_>>();
        let result=volcengine_transcript_from(full,&no_speakers);
        assert_eq!(result.text,full);assert!(result.utterances.is_empty());
    }

    #[test]
    fn complete_provider_text_keeps_speakers_and_timing() {
        let parts = vec![
            CollectedUtterance { text:"第一句。".into(), start_ms:0, end_ms:1000,
                provider_speaker:Some("A".into()), provider_request:None, embedding:None },
            CollectedUtterance { text:"第二句。".into(), start_ms:2000, end_ms:3000,
                provider_speaker:Some("B".into()), provider_request:None, embedding:None },
        ];
        let result = volcengine_transcript_from("第一句。\n 第二句。", &parts);
        assert_eq!(result.text, "说话人1: 第一句。\n说话人2: 第二句。");
        assert_eq!(result.utterances.len(), 2);
        assert_eq!((result.utterances[1].start_ms, result.utterances[1].end_ms), (2000, 3000));
    }

    #[test]
    fn preserve_user_words_transcription() {
        let input = "使用 Office 16；open 14兆；feel close；文件职位；Opus 16。";
        assert_eq!(normalize_transcript(input), input);
    }
    use std::io::{Read, Write};
    use std::net::TcpListener;
    use std::thread;

    #[test]
    fn sidecar_transcript_is_loaded_without_listener_type() {
        std::env::remove_var("COMPANION_TYPE_TRANSCRIPT_TEXT");
        std::env::remove_var("COMPANION_TYPE_ASR_COMMAND");
        let root = std::env::temp_dir().join("companion-type-transcription-sidecar-test");
        let _ = fs::create_dir_all(&root);
        let audio = root.join("meeting.wav");
        let sidecar = root.join("meeting.transcript.txt");
        fs::write(&audio, b"RIFF----WAVEfmt ").unwrap();
        fs::write(
            &sidecar,
            "Decision: Companion-Type owns ASR.\nAction: Maya validates minutes.",
        )
        .unwrap();

        let transcript = CompanionTranscriptionManager::new()
            .transcribe_audio(&audio.to_string_lossy())
            .unwrap();
        assert_eq!(transcript.provider_id, "companion-type-sidecar-transcript");
        assert!(transcript.text.contains("Companion-Type owns ASR"));
        assert_eq!(transcript.evidence_path, Some(sidecar));
    }

    #[test]
    fn wav_writer_reader_roundtrip() {
        let dir = std::env::temp_dir().join("companion-type-asr-wav-roundtrip-test");
        let _ = fs::create_dir_all(&dir);
        // 4 x 3200 B (100 ms each) non-zero ramp so header/data byte errors surface.
        let pcm: Vec<u8> = (0..4 * 3_200).map(|i| (i & 0xff) as u8).collect();
        let path = dir.join("rt.wav");
        write_pcm16k_mono_wav(&path, &pcm).unwrap();
        let back = diarization::read_pcm16k_mono_wav(&path).unwrap();
        assert_eq!(
            back, pcm,
            "written chunk WAV must roundtrip to identical PCM"
        );
    }

    #[test]
    fn split_long_wav_into_aligned_readable_chunks() {
        let dir = std::env::temp_dir().join(format!("companion-type-asr-split-test-{}", uuid::Uuid::new_v4()));
        let _ = fs::create_dir_all(&dir);
        let _recordings = RecordingOverride::new(&dir);
        // 65.1 seconds split at 30 seconds => 30s + 30s + 5.1s.
        let total = 65 * PCM_BYTES_PER_SECOND + 3_200;
        let pcm = vec![0x11u8; total];
        let src = dir.join("long.wav");
        write_pcm16k_mono_wav(&src, &pcm).unwrap();

        let chunks = split_long_wav_into_chunks(&src, 30).unwrap();
        assert_eq!(chunks.len(), 3);
        let mut collected = 0usize;
        for (i, chunk) in chunks.iter().enumerate() {
            let data = diarization::read_pcm16k_mono_wav(chunk)
                .unwrap_or_else(|e| panic!("chunk {i} must be readable: {e}"));
            if i + 1 < chunks.len() {
                assert_eq!(data.len(), 30 * PCM_BYTES_PER_SECOND);
                assert_eq!(
                    data.len() % 3_200,
                    0,
                    "non-final chunk must be 100 ms aligned"
                );
            }
            collected += data.len();
        }
        assert_eq!(
            collected, total,
            "chunks must cover all PCM with no loss or dup"
        );
    }

    #[test]
    fn successful_asr_chunk_cache_roundtrips_by_pcm_identity() {
        let unique = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let dir = std::env::temp_dir().join(format!(
            "companion-type-asr-chunk-cache-test-{}-{unique}",
            std::process::id()
        ));
        let cache = dir.join("cache");
        fs::create_dir_all(&dir).unwrap();
        let wav = dir.join("chunk.wav");
        write_pcm16k_mono_wav(&wav, &vec![0x31u8; PCM_BYTES_PER_SECOND]).unwrap();
        let utterances = vec![Utterance {
            text: "十分钟约一点二兆".into(),
            start_ms: 100,
            end_ms: 900,
            speaker: Some("speaker-a".into()),
        }];
        let profile = chunk_cache::Profile::from_configuration(&serde_json::json!({
            "provider": "test", "model": "test", "language": "auto",
        })).unwrap();
        let key = chunk_cache::Key::new(&diarization::read_pcm16k_mono_wav(&wav).unwrap(), profile.clone()).unwrap();
        assert!(chunk_cache::load(&cache, &key).is_none());
        chunk_cache::store(&cache, &key, "十分钟约一点二兆", &utterances).unwrap();
        let (text, restored) = chunk_cache::load(&cache, &key).unwrap();
        assert_eq!(text, "十分钟约一点二兆");
        assert_eq!(restored.len(), 1);
        assert_eq!(restored[0].start_ms, 100);
        assert_eq!(restored[0].speaker.as_deref(), Some("speaker-a"));

        // Same file name with different PCM must miss: identity is content,
        // never a process-local chunk index or temporary path.
        write_pcm16k_mono_wav(&wav, &vec![0x32u8; PCM_BYTES_PER_SECOND]).unwrap();
        let key = chunk_cache::Key::new(&diarization::read_pcm16k_mono_wav(&wav).unwrap(), profile).unwrap();
        assert!(chunk_cache::load(&cache, &key).is_none());
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn unconfirmed_quiet_tail_never_becomes_a_complete_transcript() {
        let dir = std::env::temp_dir().join(format!("companion-unconfirmed-tail-{}", uuid::Uuid::new_v4()));
        fs::create_dir_all(&dir).unwrap();
        let path = dir.join("tail.wav");
        // Low-level, varying voice-like signal: amplitude cannot prove speech
        // or silence. A closed connection without a final is still unknown.
        let mut pcm = Vec::new();
        for index in 0..(6 * 16_000) {
            let level: i16 = if (index / 1600) % 4 == 0 { 35 } else { 120 };
            let sample = if index % 2 == 0 { level } else { -level };
            pcm.extend_from_slice(&sample.to_le_bytes());
        }
        write_pcm16k_mono_wav(&path, &pcm).unwrap();
        let no_result = "Volcengine connection closed without a final result";
        assert!(!continuous_tail_may_be_empty(Some(Path::new("source.wav")), &path, no_result),
            "quiet audio and a missing final do not establish silence");
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn independent_or_speechful_tail_never_uses_continuous_noise_exception() {
        let dir = std::env::temp_dir().join(format!("companion-type-tail-{}", uuid::Uuid::new_v4()));
        fs::create_dir_all(&dir).unwrap();
        let short = dir.join("short.wav");
        write_pcm16k_mono_wav(&short, &vec![0u8; 9 * PCM_BYTES_PER_SECOND]).unwrap();
        let no_result = "attempt 5/5: Volcengine connection closed without a final result";
        assert!(!continuous_tail_may_be_empty(None, &short, no_result));
        assert!(!continuous_tail_may_be_empty(Some(Path::new("source.wav")), &short, no_result));
        assert!(continuous_tail_may_be_empty(Some(Path::new("source.wav")), &short,
            super::super::volcengine::NO_SPEECH_ERROR));
        assert!(!continuous_tail_may_be_empty(Some(Path::new("source.wav")), &short, "transport timeout"));
        assert!(!continuous_tail_may_be_empty(Some(Path::new("source.wav")), &short,
            "Volcengine connection closed without a final result; malformed response"));
        let mut pcm = vec![0u8; 9 * PCM_BYTES_PER_SECOND];
        for sample in pcm[2 * PCM_BYTES_PER_SECOND..4 * PCM_BYTES_PER_SECOND].chunks_exact_mut(2) {
            sample.copy_from_slice(&4_000i16.to_le_bytes());
        }
        write_pcm16k_mono_wav(&short, &pcm).unwrap();
        assert!(!continuous_tail_may_be_empty(Some(Path::new("source.wav")), &short, no_result));
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn failed_leading_middle_or_final_chunk_cannot_become_a_complete_transcript() {
        let no_result = "Volcengine connection closed without a final result";
        for failed_index in 0..3 {
            let results = (0..3).map(|index| Some(if index == failed_index {
                Err(no_result.to_string())
            } else { Ok((format!("real provider text {index}"), Vec::new())) })).collect();
            let error = complete_chunk_results(results).unwrap_err();
            assert!(error.contains(&format!("chunk {} of 3", failed_index + 1)));
            assert!(error.contains(no_result));
        }
        let complete = complete_chunk_results(vec![Some(Ok(("first".into(), Vec::new()))),
            Some(Ok(("second".into(), Vec::new())))]).unwrap();
        assert_eq!(complete[0].0, "first"); assert_eq!(complete[1].0, "second");
    }

    #[test]
    fn long_recording_does_not_retry_rejected_authentication() {
        for status in [401, 403] {
            let error = format!("Volcengine auth rejected (HTTP {status}). Check credentials");
            assert!(!asr_error_is_retryable(&error));
            assert!(!asr_error_is_retryable(&format!("attempt 1/5: {error}")));
        }
        assert!(asr_error_is_retryable("Volcengine ws connect failed: HTTP 429"));
        assert!(asr_error_is_retryable("Volcengine ws connect failed: HTTP 503"));
        assert!(asr_error_is_retryable("Volcengine network connection failed"));
        let error = "attempt 1/5: Volcengine auth rejected (HTTP 403). Check credentials";
        let results = vec![Some(Ok(("already recognized".into(), Vec::new()))), Some(Err(error.into())), None];
        assert_eq!(first_auth_failure(&results), Some((1, error)));
        let transient = vec![Some(Err("Volcengine ws connect failed: HTTP 503".into())), None];
        assert_eq!(first_auth_failure(&transient), None);
        let calls = std::sync::atomic::AtomicUsize::new(0);
        let paths: Vec<PathBuf> = (0..6).map(|i| PathBuf::from(format!("fictional-{i}.wav"))).collect();
        let error = volcengine_multi_chunk_transcript_with(&paths, None, &|_, _| {
            calls.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
            Err("Volcengine auth rejected (HTTP 401). Check credentials".into())
        }).unwrap_err();
        assert_eq!(calls.load(std::sync::atomic::Ordering::SeqCst), asr_parallel_worker_count());
        assert!(error.contains("auth rejected") && error.contains("chunk"));
    }

    #[test]
    fn explicit_no_speech_is_not_retried_or_accepted_as_a_complete_meeting() {
        let error = "attempt 1/5: Volcengine ASR completed without recognized speech";
        assert!(!asr_error_is_retryable(error));
        assert!(super::super::volcengine::is_no_speech_error(error));
        assert!(asr_error_is_retryable("Volcengine connection closed without a final result"));
        let results = vec![Some(Err(error.to_string())), Some(Ok(("later real words".into(), Vec::new())))];
        assert!(complete_chunk_results(results).unwrap_err().contains("chunk 1 of 2"));
    }

    #[test]
    fn continuous_recording_quiet_chunks_preserve_real_text_and_original_offsets() {
        let dir = std::env::temp_dir().join(format!("companion-quiet-chunks-{}", uuid::Uuid::new_v4()));
        fs::create_dir_all(&dir).unwrap();
        let paths = (0..3).map(|index| {
            let path = dir.join(format!("{index}.wav"));
            write_pcm16k_mono_wav(&path, &vec![0u8; 5 * PCM_BYTES_PER_SECOND]).unwrap();
            path
        }).collect::<Vec<_>>();
        let completed_empty = format!("attempt 1/5: {}", super::super::volcengine::NO_SPEECH_ERROR);
        // A real board clip ended with 8.9 s without recognized words. Also
        // cover quiet pre-roll and a pause between speakers without inventing
        // text, flattening the source clock, or accepting an unknown failure.
        for quiet_index in 0..3 {
            let mut results = (0..3).map(|index| Some(if index == quiet_index {
                Err(completed_empty.clone())
            } else { Ok((format!("recognized words {index}"), vec![CollectedUtterance {
                text: format!("recognized words {index}"), start_ms: 100, end_ms: 600,
                provider_speaker: None, provider_request: None, embedding: None,
            }])) })).collect::<Vec<_>>();
            accept_completed_no_speech_chunks(Some(Path::new("continuous-board.wav")), &mut results);
            let completed = complete_chunk_results(results).unwrap();
            assert_eq!(completed.len(), 3);
            assert!(completed[quiet_index].0.is_empty());
            assert!(completed[quiet_index].1.is_empty());
            for (index, (text, _)) in completed.iter().enumerate() {
                if index != quiet_index { assert_eq!(text, &format!("recognized words {index}")); }
            }
            let (text, timed) = merge_chunk_transcriptions(&paths, completed);
            assert_eq!(timed.len(), 2);
            let spoken_indices = (0..3).filter(|index| *index != quiet_index).collect::<Vec<_>>();
            for (utterance, index) in timed.iter().zip(spoken_indices) {
                assert!(text.contains(&format!("recognized words {index}")));
                assert_eq!(utterance.start_ms, index as u64 * 5_000 + 100);
                assert_eq!(utterance.end_ms, index as u64 * 5_000 + 600);
            }
        }
        for path in paths { fs::remove_file(path).unwrap(); }
        fs::remove_dir(dir).unwrap();
    }

    #[test]
    fn continuous_quiet_chunk_rule_keeps_unknown_errors_and_all_empty_failure() {
        let empty = super::super::volcengine::NO_SPEECH_ERROR.to_string();
        let mut all_empty = vec![Some(Err(empty.clone())), Some(Err(empty.clone()))];
        accept_completed_no_speech_chunks(Some(Path::new("continuous-board.wav")), &mut all_empty);
        assert!(super::super::volcengine::is_no_speech_error(&complete_chunk_results(all_empty).unwrap_err()));
        let mut independent = vec![Some(Err(empty)), Some(Ok(("actual words".into(), Vec::new())))];
        accept_completed_no_speech_chunks(None, &mut independent);
        assert!(complete_chunk_results(independent).unwrap_err().contains("chunk 1 of 2"));
        for failed_index in 0..3 {
            for error in ["Volcengine connection closed without a final result", "transport timeout",
                          "Volcengine response protocol invalid", "Volcengine request rejected (code=45000081)"] {
                let mut results = (0..3).map(|index| Some(if index == failed_index {
                    Err(error.to_string())
                } else { Ok(("actual words".into(), Vec::new())) })).collect::<Vec<_>>();
                accept_completed_no_speech_chunks(Some(Path::new("continuous-board.wav")), &mut results);
                let failure = complete_chunk_results(results).unwrap_err();
                assert!(failure.contains(&format!("chunk {} of 3", failed_index + 1)) && failure.contains(error));
            }
        }
    }

    #[test]
    fn listener_type_command_is_rejected() {
        std::env::remove_var("COMPANION_TYPE_TRANSCRIPT_TEXT");
        let root = std::env::temp_dir().join("companion-type-transcription-command-test");
        let _ = fs::create_dir_all(&root);
        let audio = root.join("meeting.wav");
        fs::write(&audio, b"RIFF----WAVEfmt ").unwrap();
        std::env::set_var("COMPANION_TYPE_ASR_COMMAND", "listener-type.exe");
        let error = CompanionTranscriptionManager::new()
            .transcribe_audio(&audio.to_string_lossy())
            .unwrap_err();
        assert!(error.contains("must not call listener-type"));
        std::env::remove_var("COMPANION_TYPE_ASR_COMMAND");
    }

    #[test]
    fn openai_compatible_provider_posts_audio_multipart() {
        std::env::remove_var("COMPANION_TYPE_TRANSCRIPT_TEXT");
        std::env::remove_var("COMPANION_TYPE_ASR_COMMAND");
        let root = std::env::temp_dir().join("companion-type-transcription-openai-compatible-test");
        let _ = fs::create_dir_all(&root);
        let audio = root.join("meeting.wav");
        fs::write(&audio, b"RIFF----WAVEfmt test audio").unwrap();

        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let endpoint = format!(
            "http://{}/v1/audio/transcriptions",
            listener.local_addr().unwrap()
        );
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            stream
                .set_read_timeout(Some(Duration::from_secs(5)))
                .unwrap();
            let mut request = Vec::new();
            let mut chunk = [0_u8; 4096];
            loop {
                let read = stream.read(&mut chunk).unwrap_or(0);
                if read == 0 {
                    break;
                }
                request.extend_from_slice(&chunk[..read]);
                if request_is_complete(&request) {
                    break;
                }
            }
            let request_text = String::from_utf8_lossy(&request).to_string();
            let body = "{\"text\":\"Decision: Companion-Type uses real ASR. Action: Validate provider chain.\"}";
            let response = format!(
                "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{}",
                body.len(),
                body
            );
            stream.write_all(response.as_bytes()).unwrap();
            request_text
        });

        std::env::set_var("COMPANION_TYPE_ASR_PROVIDER", "openai-compatible");
        std::env::set_var("COMPANION_TYPE_ASR_ENDPOINT", endpoint);
        std::env::set_var("COMPANION_TYPE_ASR_API_KEY", "test-key");
        std::env::set_var("COMPANION_TYPE_ASR_MODEL", "gpt-4o-transcribe");
        let transcript = CompanionTranscriptionManager::new()
            .transcribe_audio(&audio.to_string_lossy())
            .unwrap();
        assert_eq!(
            transcript.provider_id,
            "companion-type-openai-compatible-asr"
        );
        assert!(transcript.text.contains("real ASR"));
        let captured = server.join().unwrap();
        let captured_lower = captured.to_ascii_lowercase();
        assert!(captured.contains("POST /v1/audio/transcriptions"));
        assert!(captured_lower.contains("authorization: bearer test-key"));
        assert!(captured.contains("name=\"model\""));
        assert!(captured.contains("gpt-4o-transcribe"));
        assert!(captured.contains("name=\"file\""));
        assert!(captured.contains("multipart/form-data"));
        std::env::remove_var("COMPANION_TYPE_ASR_PROVIDER");
        std::env::remove_var("COMPANION_TYPE_ASR_ENDPOINT");
        std::env::remove_var("COMPANION_TYPE_ASR_API_KEY");
        std::env::remove_var("COMPANION_TYPE_ASR_MODEL");
    }

    #[test]
    fn utterance_embedding_index_picks_max_overlap() {
        let segs = vec![
            EmbeddingSegment {
                start_ms: 0,
                end_ms: 1000,
                embedding: vec![1.0],
            },
            EmbeddingSegment {
                start_ms: 2000,
                end_ms: 3000,
                embedding: vec![2.0],
            },
        ];
        let u = Utterance {
            text: "x".into(),
            start_ms: 2500,
            end_ms: 2800,
            speaker: None,
        };
        assert_eq!(utterance_embedding_index(&u, &segs), Some(1));
    }

    #[test]
    fn utterance_embedding_index_keeps_uncovered_audio_unknown() {
        let segs = vec![
            EmbeddingSegment {
                start_ms: 0,
                end_ms: 1000,
                embedding: vec![1.0],
            },
            EmbeddingSegment {
                start_ms: 2000,
                end_ms: 3000,
                embedding: vec![2.0],
            },
        ];
        // A VAD miss cannot establish that the preceding person spoke.
        let u = Utterance {
            text: "x".into(),
            start_ms: 1100,
            end_ms: 1200,
            speaker: None,
        };
        assert_eq!(utterance_embedding_index(&u, &segs), None);
        for (start, end) in [(1000, 2000), (3000, 3200), (800, 800), (2800, 2500),
                             (u64::MAX - 10, u64::MAX)] {
            assert_eq!(embedding_index_for_range(start, end, &segs), None);
        }
        let per = [CollectedUtterance {
            text: u.text, start_ms: u.start_ms, end_ms: u.end_ms,
            provider_speaker: None, provider_request: None, embedding: None,
        }];
        assert_eq!(cluster_utterances_by_speaker(&per)[0].speaker, None);
    }

    #[test]
    fn cluster_utterances_keeps_speakers_consistent_across_chunks() {
        // Two chunks, three utterances, two real speakers. A1 (chunk 1) and A2
        // (chunk 2) are the SAME speaker (near-identical embedding); B1 is a
        // different speaker. Global clustering must give A1 and A2 the SAME id
        // even though they are fed as separate "chunks" — this is the fix for
        // per-chunk speaker renumbering in long meetings.
        let per: Vec<CollectedUtterance> = vec![
            CollectedUtterance {
                text: "A1".into(),
                start_ms: 0,
                end_ms: 1000,
                provider_speaker: None,
                provider_request: None,
                embedding: Some(vec![1.0_f32, 0.0]),
            },
            CollectedUtterance {
                text: "B1".into(),
                start_ms: 1100,
                end_ms: 2000,
                provider_speaker: None,
                provider_request: None,
                embedding: Some(vec![0.0, 1.0]),
            },
            CollectedUtterance {
                text: "A2".into(),
                start_ms: 2100,
                end_ms: 3000,
                provider_speaker: None,
                provider_request: None,
                embedding: Some(vec![0.98, 0.19]),
            },
        ];
        let tagged = cluster_utterances_by_speaker(&per);
        assert_eq!(
            tagged[0].speaker, tagged[2].speaker,
            "A1 and A2 same speaker: {:?}",
            tagged
        );
        assert_ne!(
            tagged[0].speaker, tagged[1].speaker,
            "A1 and B1 different speakers"
        );
        assert!(
            tagged.iter().all(|u| u.speaker.is_some()),
            "all assigned a speaker"
        );
    }

    #[test]
    fn cluster_utterances_retains_request_scoped_labels_without_assuming_a_speaker_count() {
        let utterance = |request, label: &str, embedding: Vec<f32>| CollectedUtterance {
            text: "actual provider words".into(), start_ms: 0, end_ms: 1000,
            provider_speaker: Some(label.into()), provider_request: Some(request), embedding: Some(embedding),
        };
        // Local room-noise features alone would collapse all three entries.
        // The service distinguished the first two inside its actual request.
        let per = [utterance(0,"0",vec![1.0,0.0]), utterance(0,"1",vec![1.0,0.0]),
                   utterance(1,"0",vec![1.0,0.0])];
        let tagged = cluster_utterances_by_speaker(&per);
        assert_ne!(tagged[0].speaker, tagged[1].speaker);
        // A single constant label in a request cannot erase acoustic voices.
        let per = [utterance(0,"0",vec![1.0,0.0]), utterance(0,"0",vec![0.0,1.0])];
        let tagged = cluster_utterances_by_speaker(&per);
        assert_ne!(tagged[0].speaker, tagged[1].speaker);
        // Equal integer labels from independent requests do not mean the same
        // person. The embeddings, rather than either request's numbering, match.
        let per = [utterance(0,"0",vec![1.0,0.0]), utterance(0,"1",vec![0.0,1.0]),
                   utterance(1,"0",vec![0.0,1.0]), utterance(1,"1",vec![1.0,0.0])];
        let tagged = cluster_utterances_by_speaker(&per);
        assert_eq!(tagged[0].speaker, tagged[3].speaker);
        assert_eq!(tagged[1].speaker, tagged[2].speaker);
        assert_ne!(tagged[0].speaker, tagged[1].speaker);
    }

    #[test]
    fn provider_speaker_labels_override_local_clusters_and_are_normalized() {
        let per = vec![
            CollectedUtterance {
                text: "甲".into(),
                start_ms: 0,
                end_ms: 900,
                provider_speaker: Some("7".into()),
                provider_request: None,
                embedding: Some(vec![1.0, 0.0]),
            },
            CollectedUtterance {
                text: "乙".into(),
                start_ms: 1000,
                end_ms: 1900,
                provider_speaker: Some("9".into()),
                provider_request: None,
                // Deliberately identical: provider labels must win.
                embedding: Some(vec![1.0, 0.0]),
            },
            CollectedUtterance {
                text: "丙".into(),
                start_ms: 2000,
                end_ms: 2900,
                provider_speaker: Some("7".into()),
                provider_request: None,
                embedding: Some(vec![0.0, 1.0]),
            },
        ];
        let tagged = cluster_utterances_by_speaker(&per);
        assert_eq!(tagged[0].speaker, tagged[2].speaker);
        assert_ne!(tagged[0].speaker, tagged[1].speaker);
        assert_eq!(
            tagged
                .iter()
                .filter_map(|utterance| utterance.speaker)
                .collect::<std::collections::BTreeSet<_>>()
                .len(),
            2
        );
    }

    #[test]
    fn local_third_speaker_survives_provider_undercount() {
        let per = vec![
            CollectedUtterance {
                text: "甲".into(),
                start_ms: 0,
                end_ms: 900,
                provider_speaker: Some("p1".into()),
                provider_request: None,
                embedding: Some(vec![1.0, 0.0, 0.0]),
            },
            CollectedUtterance {
                text: "乙".into(),
                start_ms: 1000,
                end_ms: 1900,
                provider_speaker: Some("p2".into()),
                provider_request: None,
                embedding: Some(vec![0.0, 1.0, 0.0]),
            },
            CollectedUtterance {
                text: "丙".into(),
                start_ms: 2000,
                end_ms: 2900,
                // Provider merged this real third identity into p1.
                provider_speaker: Some("p1".into()),
                provider_request: None,
                embedding: Some(vec![0.0, 0.0, 1.0]),
            },
        ];
        let tagged = cluster_utterances_by_speaker(&per);
        assert_eq!(
            tagged
                .iter()
                .filter_map(|utterance| utterance.speaker)
                .collect::<std::collections::BTreeSet<_>>()
                .len(),
            3
        );
    }

    #[test]
    fn render_tagged_merges_consecutive_same_speaker() {
        let utts = vec![
            TaggedUtterance {
                text: "甲".into(),
                start_ms: 0,
                end_ms: 500,
                speaker: Some(0),
            },
            TaggedUtterance {
                text: "乙".into(),
                start_ms: 600,
                end_ms: 900,
                speaker: Some(0),
            },
            TaggedUtterance {
                text: "丙".into(),
                start_ms: 1000,
                end_ms: 1500,
                speaker: Some(1),
            },
        ];
        let out = render_tagged(&utts);
        assert!(out.contains("说话人1: 甲乙"), "out={out}");
        assert!(out.contains("说话人2: 丙"), "out={out}");
    }

    #[test]
    fn render_tagged_handles_empty_and_unknown_speaker() {
        assert_eq!(render_tagged(&[]), "");
        let out = render_tagged(&[TaggedUtterance {
            text: "x".into(),
            start_ms: 0,
            end_ms: 100,
            speaker: None,
        }]);
        assert!(out.contains("说话人?"), "out={out}");
    }

    /// End-to-end: volcengine transcription + sherpa-onnx diarization of the
    /// 4-speaker zh meeting clip. The transcript text should be speaker-tagged
    /// ("说话人1: ... / 说话人2: ..."). Requires real Volcengine credentials,
    /// Listener's speaker-verification models, and the probe WAV.
    #[test]
    #[ignore = "requires volcengine creds + Listener speaker models + the 4-speaker probe WAV"]
    fn volcengine_diarized_transcript_four_speaker() {
        std::env::var("COMPANION_TYPE_VOLC_APP_KEY").expect("COMPANION_TYPE_VOLC_APP_KEY");
        std::env::var("COMPANION_TYPE_VOLC_ACCESS_KEY").expect("COMPANION_TYPE_VOLC_ACCESS_KEY");
        let wav = std::env::var("COMPANION_TYPE_DIARIZE_PROBE_WAV")
            .unwrap_or_else(|_| "docs/validation/four-speakers-zh.wav".to_string());
        let audio = PathBuf::from(&wav);
        let transcript = CompanionTranscriptionManager::new()
            .transcribe_audio(&audio.to_string_lossy())
            .expect("transcript");
        eprintln!("diarized_transcript:\n{}", transcript.text);
        eprintln!("mode={}", transcript.mode);
        assert!(
            transcript.text.contains("说话人"),
            "expected speaker tags: {}",
            transcript.text
        );
        assert!(
            transcript.text.contains("说话人1"),
            "expected 说话人1: {}",
            transcript.text
        );
        assert!(
            transcript.text.contains("说话人2"),
            "expected 说话人2: {}",
            transcript.text
        );
    }

    fn request_is_complete(request: &[u8]) -> bool {
        let text = String::from_utf8_lossy(request);
        let Some(header_end) = text.find("\r\n\r\n") else {
            return false;
        };
        let content_length = text
            .lines()
            .find_map(|line| {
                let (name, value) = line.split_once(':')?;
                if name.eq_ignore_ascii_case("content-length") {
                    value.trim().parse::<usize>().ok()
                } else {
                    None
                }
            })
            .unwrap_or(0);
        request.len() >= header_end + 4 + content_length
    }
}
