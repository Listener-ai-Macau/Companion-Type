//! Companion-Type offline speaker diarization.
//!
//! Reuses Listener's sherpa-onnx speaker-embedding runtime (3dspeaker model +
//! sherpa-onnx-c-api.dll under `%APPDATA%\Listener Type\models\speaker-verification`)
//! to extract per-segment embeddings, then clusters them with agglomerative
//! hierarchical clustering (cosine similarity) to assign speaker ids. VAD is a
//! simple adaptive energy gate (no silero dependency).
//!
//! FFI pattern ported from Listener-Type `src-tauri/src/speaker_verification.rs`.

use std::ffi::{c_char, c_void, CString};
use std::path::{Path, PathBuf};
use std::sync::{OnceLock, Mutex, Arc};

use libloading::Library;

const SAMPLE_RATE: i32 = 16_000;
// Use a window materially shorter than ordinary turn-taking pauses. The
// previous 500 ms window plus 500 ms merge bridged the product stimulus' 350 ms
// inter-speaker gaps and handed several speakers to the embedding model as one
// segment. 100 ms windows with a 300 ms merge retain within-sentence pauses but
// preserve real turn boundaries.
const VAD_WINDOW_MS: usize = 100;
const VAD_MERGE_GAP_MS: usize = 300;
const MIN_SEGMENT_MS: usize = 1_500;
/// Merge clusters only when their average cosine is at least this value.
/// Keep this conservative: increasing it can split codec/noise variation from
/// one person into fake speakers. Provider-supplied speaker labels take
/// precedence when the configured ASR service supports them.
const DEFAULT_CLUSTER_COSINE_THRESHOLD: f32 = 0.68;

fn cluster_cosine_threshold() -> f32 {
    std::env::var("COMPANION_TYPE_DIARIZATION_COSINE_THRESHOLD")
        .ok()
        .and_then(|value| value.parse::<f32>().ok())
        .filter(|value| (0.50..=0.85).contains(value))
        .unwrap_or(DEFAULT_CLUSTER_COSINE_THRESHOLD)
}

#[derive(Debug, Clone)]
pub struct DiarizationSegment {
    pub start_ms: u64,
    pub end_ms: u64,
    pub speaker: usize,
}

/// A VAD speech segment with its extracted (normalized) speaker embedding.
/// Exposed so the transcription layer can collect embeddings across MANY audio
/// chunks and cluster them once globally — keeping speaker ids consistent
/// across a chunked long meeting instead of re-clustering (and renumbering
/// speakers) per chunk.
#[derive(Debug, Clone)]
pub struct EmbeddingSegment {
    pub start_ms: u64,
    pub end_ms: u64,
    pub embedding: Vec<f32>,
}

// ===================== sherpa-onnx speaker-embedding FFI =====================

#[repr(C)]
struct ExtractorConfig {
    model: *const c_char,
    num_threads: i32,
    debug: i32,
    provider: *const c_char,
}
type FnCreateExtractor = unsafe extern "C" fn(*const ExtractorConfig) -> *const c_void;
type FnDestroyExtractor = unsafe extern "C" fn(*const c_void);
type FnExtractorDim = unsafe extern "C" fn(*const c_void) -> i32;
type FnCreateStream = unsafe extern "C" fn(*const c_void) -> *const c_void;
type FnAcceptWaveform = unsafe extern "C" fn(*const c_void, i32, *const f32, i32);
type FnInputFinished = unsafe extern "C" fn(*const c_void);
type FnIsReady = unsafe extern "C" fn(*const c_void, *const c_void) -> i32;
type FnComputeEmbedding = unsafe extern "C" fn(*const c_void, *const c_void) -> *const f32;
type FnDestroyEmbedding = unsafe extern "C" fn(*const f32);
type FnDestroyStream = unsafe extern "C" fn(*const c_void);

struct SpeakerRuntime {
    _libs: Vec<Library>,
    extractor: *const c_void,
    dimension: usize,
    create_stream: FnCreateStream,
    accept_waveform: FnAcceptWaveform,
    input_finished: FnInputFinished,
    is_ready: FnIsReady,
    compute_embedding: FnComputeEmbedding,
    destroy_embedding: FnDestroyEmbedding,
    destroy_stream: FnDestroyStream,
    destroy_extractor: FnDestroyExtractor,
}

unsafe impl Send for SpeakerRuntime {}
unsafe impl Sync for SpeakerRuntime {}

impl Drop for SpeakerRuntime {
    fn drop(&mut self) {
        unsafe { (self.destroy_extractor)(self.extractor) };
    }
}

impl SpeakerRuntime {
    fn load(model_dir: &Path) -> Result<Self, String> {
        super::audio_components::verify(model_dir)?;
        let model_path = model_dir.join("3dspeaker_speech_campplus_sv_zh-cn_16k-common.onnx");
        if !model_path.exists() {
            return Err(format!(
                "3dspeaker model not found at {}. Install Listener Type (ships the model + sherpa-onnx runtime) or set COMPANION_TYPE_SPEAKER_MODEL_DIR.",
                model_path.display()
            ));
        }
        let model = CString::new(model_path.to_string_lossy().as_bytes())
            .map_err(|_| "model path has NUL".to_string())?;
        let provider = CString::new("cpu").unwrap();
        unsafe {
            let onnx = Library::new(model_dir.join("onnxruntime.dll"))
                .map_err(|e| format!("onnxruntime.dll: {e}"))?;
            let providers = Library::new(model_dir.join("onnxruntime_providers_shared.dll"))
                .map_err(|e| format!("providers_shared: {e}"))?;
            let sherpa = Library::new(model_dir.join("sherpa-onnx-c-api.dll"))
                .map_err(|e| format!("sherpa-onnx-c-api.dll: {e}"))?;
            let create_extractor: FnCreateExtractor = *sherpa
                .get(b"SherpaOnnxCreateSpeakerEmbeddingExtractor\0")
                .map_err(|e| format!("symbol CreateExtractor: {e}"))?;
            let destroy_extractor: FnDestroyExtractor = *sherpa
                .get(b"SherpaOnnxDestroySpeakerEmbeddingExtractor\0")
                .map_err(|e| format!("symbol DestroyExtractor: {e}"))?;
            let extractor_dim: FnExtractorDim = *sherpa
                .get(b"SherpaOnnxSpeakerEmbeddingExtractorDim\0")
                .map_err(|e| format!("symbol ExtractorDim: {e}"))?;
            let create_stream: FnCreateStream = *sherpa
                .get(b"SherpaOnnxSpeakerEmbeddingExtractorCreateStream\0")
                .map_err(|e| format!("symbol CreateStream: {e}"))?;
            let accept_waveform: FnAcceptWaveform = *sherpa
                .get(b"SherpaOnnxOnlineStreamAcceptWaveform\0")
                .map_err(|e| format!("symbol AcceptWaveform: {e}"))?;
            let input_finished: FnInputFinished = *sherpa
                .get(b"SherpaOnnxOnlineStreamInputFinished\0")
                .map_err(|e| format!("symbol InputFinished: {e}"))?;
            let is_ready: FnIsReady = *sherpa
                .get(b"SherpaOnnxSpeakerEmbeddingExtractorIsReady\0")
                .map_err(|e| format!("symbol IsReady: {e}"))?;
            let compute_embedding: FnComputeEmbedding = *sherpa
                .get(b"SherpaOnnxSpeakerEmbeddingExtractorComputeEmbedding\0")
                .map_err(|e| format!("symbol ComputeEmbedding: {e}"))?;
            let destroy_embedding: FnDestroyEmbedding = *sherpa
                .get(b"SherpaOnnxSpeakerEmbeddingExtractorDestroyEmbedding\0")
                .map_err(|e| format!("symbol DestroyEmbedding: {e}"))?;
            let destroy_stream: FnDestroyStream =
                *sherpa
                    .get(b"SherpaOnnxDestroyOnlineStream\0")
                    .map_err(|e| format!("symbol DestroyStream: {e}"))?;
            let config = ExtractorConfig {
                model: model.as_ptr(),
                num_threads: 1,
                debug: 0,
                provider: provider.as_ptr(),
            };
            let extractor = create_extractor(&config);
            if extractor.is_null() {
                return Err("speaker embedding extractor init failed".to_string());
            }
            let dimension = extractor_dim(extractor);
            if dimension <= 0 || dimension > 4096 {
                destroy_extractor(extractor);
                return Err(format!("invalid embedding dimension: {dimension}"));
            }
            Ok(Self {
                _libs: vec![onnx, providers, sherpa],
                extractor,
                dimension: dimension as usize,
                create_stream,
                accept_waveform,
                input_finished,
                is_ready,
                compute_embedding,
                destroy_embedding,
                destroy_stream,
                destroy_extractor,
            })
        }
    }

    fn embedding(&self, samples: &[f32]) -> Result<Vec<f32>, String> {
        let n = i32::try_from(samples.len()).map_err(|_| "audio too long")?;
        unsafe {
            let stream = (self.create_stream)(self.extractor);
            if stream.is_null() {
                return Err("create stream failed".to_string());
            }
            (self.accept_waveform)(stream, SAMPLE_RATE, samples.as_ptr(), n);
            (self.input_finished)(stream);
            if (self.is_ready)(self.extractor, stream) == 0 {
                (self.destroy_stream)(stream);
                return Err("insufficient speech for embedding".to_string());
            }
            let raw = (self.compute_embedding)(self.extractor, stream);
            if raw.is_null() {
                (self.destroy_stream)(stream);
                return Err("embedding compute failed".to_string());
            }
            let mut emb = std::slice::from_raw_parts(raw, self.dimension).to_vec();
            (self.destroy_embedding)(raw);
            (self.destroy_stream)(stream);
            normalize(&mut emb);
            Ok(emb)
        }
    }
}

fn normalize(v: &mut [f32]) {
    let norm = v.iter().map(|x| x * x).sum::<f32>().sqrt();
    if norm > f32::EPSILON {
        for x in v.iter_mut() {
            *x /= norm;
        }
    }
}

fn speaker_model_dir() -> PathBuf {
    if let Ok(dir) = std::env::var("COMPANION_TYPE_SPEAKER_MODEL_DIR") {
        return PathBuf::from(dir);
    }
    let appdata = std::env::var("APPDATA").unwrap_or_default();
    let own = PathBuf::from(&appdata).join("Companion Type").join("models").join("speaker-verification");
    if own.is_dir() { return own; }
    // Explicit compatibility fallback for existing installations only.
    PathBuf::from(appdata)
        .join("Listener Type")
        .join("models")
        .join("speaker-verification")
}

pub(crate) fn model_files_present() -> bool {
    let dir = speaker_model_dir();
    ["3dspeaker_speech_campplus_sv_zh-cn_16k-common.onnx", "onnxruntime.dll", "onnxruntime_providers_shared.dll", "sherpa-onnx-c-api.dll"].iter().all(|name| dir.join(name).metadata().is_ok_and(|m| m.is_file() && m.len()>0))
}

static RUNTIME: OnceLock<Mutex<Option<Arc<SpeakerRuntime>>>> = OnceLock::new();

fn runtime() -> Result<Arc<SpeakerRuntime>, String> {
    let mut state = RUNTIME.get_or_init(|| Mutex::new(None)).lock().map_err(|_| "说话人组件状态不可用")?;
    if let Some(runtime)=state.as_ref() {return Ok(Arc::clone(runtime));}
    let loaded=Arc::new(SpeakerRuntime::load(&speaker_model_dir())?);
    *state=Some(Arc::clone(&loaded));
    Ok(loaded)
}

pub(crate) fn prepare_runtime()->Result<(),String> { super::audio_components::prepare()?; runtime().map(|_|()) }
pub(crate) fn runtime_loaded()->bool { RUNTIME.get().and_then(|state|state.try_lock().ok()).is_some_and(|state|state.is_some()) }

// ===================== energy VAD =====================

fn rms(w: &[f32]) -> f32 {
    if w.is_empty() {
        return 0.0;
    }
    let sum: f32 = w.iter().map(|s| s * s).sum();
    (sum / w.len() as f32).sqrt()
}

/// Adaptive energy VAD: split into VAD_WINDOW_MS windows and estimate a robust
/// noise floor (p10) plus speech reference (p95). A max-relative threshold was
/// dominated by isolated Opus/microphone peaks on the WB55 path and retained
/// fewer than 10% of windows, fragmenting every utterance. The percentile
/// threshold remains stable in the presence of those peaks.
fn energy_vad(samples: &[f32]) -> Vec<(usize, usize)> {
    let win = SAMPLE_RATE as usize * VAD_WINDOW_MS / 1000;
    if samples.len() < win {
        return Vec::new();
    }
    let energies: Vec<f32> = samples.chunks(win).map(rms).collect();
    let mut sorted = energies.clone();
    sorted.sort_by(f32::total_cmp);
    let quantile = |percent: usize| sorted[percent * (sorted.len() - 1) / 100];
    let noise_floor = quantile(10);
    let speech_reference = quantile(95);
    if speech_reference <= f32::EPSILON {
        return Vec::new();
    }
    let thr = noise_floor + (speech_reference - noise_floor).max(0.0) * 0.15;
    let speech: Vec<bool> = energies.iter().map(|e| *e > thr).collect();
    let gap_windows = (VAD_MERGE_GAP_MS + VAD_WINDOW_MS - 1) / VAD_WINDOW_MS;
    // Merge speech windows, bridging gaps shorter than gap_windows.
    let mut segments: Vec<(usize, usize)> = Vec::new();
    let mut i = 0;
    while i < speech.len() {
        if !speech[i] {
            i += 1;
            continue;
        }
        let start = i;
        let mut end = i;
        let mut j = i + 1;
        while j < speech.len() {
            if speech[j] {
                end = j;
                j += 1;
            } else {
                // count gap
                let mut g = 0;
                while j + g < speech.len() && !speech[j + g] {
                    g += 1;
                }
                if g <= gap_windows && j + g < speech.len() {
                    j += g;
                    end = j; // bridge gap, continue
                } else {
                    break;
                }
            }
        }
        let _ = start;
        segments.push((i * win, ((end + 1) * win).min(samples.len())));
        i = end + 1;
    }
    segments
}

// ===================== AHC clustering (cosine) =====================

fn cosine(a: &[f32], b: &[f32]) -> f32 {
    a.iter().zip(b).map(|(x, y)| x * y).sum()
}

/// Cluster a set of speaker embeddings with the canonical Companion threshold
/// (see [`cluster_cosine_threshold`]). Public so callers that collect embeddings
/// across many audio chunks can cluster them ONCE globally — this is what
/// keeps speaker ids consistent across a chunked long meeting. Returns a
/// speaker id (0-based) per embedding, in input order.
pub fn cluster_speakers(embeddings: &[Vec<f32>]) -> Vec<usize> {
    ahc_cluster(embeddings, cluster_cosine_threshold())
}

/// A provider identity is comparable only inside one recognition request.
/// Different labels there must not collapse merely because room noise makes
/// local embeddings similar. Labels reused by another request are unrelated.
#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct SpeakerConstraint {
    pub request: u64,
    pub label: String,
}

pub(crate) fn cluster_speakers_constrained(
    embeddings: &[Vec<f32>], constraints: &[Option<SpeakerConstraint>],
) -> Vec<usize> {
    ahc_cluster_constrained(embeddings, cluster_cosine_threshold(), constraints)
}

/// Agglomerative hierarchical clustering: start with each embedding as its own
/// cluster, repeatedly merge the two clusters whose average-link cosine
/// similarity is highest, as long as it is >= threshold. Returns a speaker id
/// (0-based, arbitrary) per input embedding.
fn ahc_cluster(embeddings: &[Vec<f32>], threshold: f32) -> Vec<usize> {
    ahc_cluster_constrained(embeddings, threshold, &[])
}

fn ahc_cluster_constrained(
    embeddings: &[Vec<f32>], threshold: f32, constraints: &[Option<SpeakerConstraint>],
) -> Vec<usize> {
    let n = embeddings.len();
    if n == 0 {
        return Vec::new();
    }
    // Same-request equal labels are one provider identity. Start them together;
    // across requests, the unchanged acoustic threshold decides association.
    let mut clusters: Vec<Vec<usize>> = Vec::new();
    let mut identities = std::collections::BTreeMap::new();
    for i in 0..n {
        if let Some(identity) = constraints.get(i).and_then(Option::as_ref) {
            let key = (identity.request, identity.label.as_str());
            let next = clusters.len();
            let cluster = *identities.entry(key).or_insert(next);
            if cluster == next { clusters.push(Vec::new()); }
            clusters[cluster].push(i);
        } else {
            clusters.push(vec![i]);
        }
    }
    while clusters.len() > 1 {
        // find the pair with max average-link cosine similarity
        let mut best = (0usize, 1usize, f32::NEG_INFINITY);
        for a in 0..clusters.len() {
            for b in (a + 1)..clusters.len() {
                let conflicts = clusters[a].iter().any(|&i| clusters[b].iter().any(|&j| {
                    match (constraints.get(i).and_then(Option::as_ref),
                           constraints.get(j).and_then(Option::as_ref)) {
                        (Some(left), Some(right)) => left.request == right.request && left.label != right.label,
                        _ => false,
                    }
                }));
                if conflicts { continue; }
                let sim = avg_link(&embeddings, &clusters[a], &clusters[b]);
                if sim > best.2 {
                    best = (a, b, sim);
                }
            }
        }
        if best.2 < threshold {
            break;
        }
        // merge b into a
        let mut merged = std::mem::take(&mut clusters[best.1]);
        clusters[best.0].append(&mut merged);
        clusters.remove(best.1);
    }
    // assign speaker ids
    let mut ids = vec![0usize; n];
    for (sid, members) in clusters.iter().enumerate() {
        for &m in members {
            ids[m] = sid;
        }
    }
    ids
}

fn avg_link(embeddings: &[Vec<f32>], a: &[usize], b: &[usize]) -> f32 {
    let mut sum = 0.0f32;
    let mut count = 0;
    for &i in a {
        for &j in b {
            sum += cosine(&embeddings[i], &embeddings[j]);
            count += 1;
        }
    }
    if count == 0 {
        0.0
    } else {
        sum / count as f32
    }
}

// ===================== diarize =====================

/// Read a 16k/mono/16-bit WAV, slice it into speech segments via energy VAD,
/// and return each segment with its start/end ms and extracted speaker
/// embedding. No clustering happens here — callers can collect these across
/// many chunks and cluster once with [`cluster_speakers`] so speaker ids stay
/// consistent across a chunked long meeting. Segments whose embedding
/// extraction fails (too short / noisy) are dropped.
pub fn segment_embeddings(wav_path: &Path) -> Result<Vec<EmbeddingSegment>, String> {
    super::diagnostics::Span::start(super::diagnostics::Operation::SpeakerEmbedding).result(segment_embeddings_inner(wav_path))
}

fn segment_embeddings_inner(wav_path: &Path) -> Result<Vec<EmbeddingSegment>, String> {
    let pcm = read_pcm16k_mono_wav(wav_path)?;
    let samples: Vec<f32> = pcm
        .chunks_exact(2)
        .map(|c| i16::from_le_bytes([c[0], c[1]]) as f32 / 32768.0)
        .collect();
    let raw_segments = energy_vad(&samples);
    let min_samples = SAMPLE_RATE as usize * MIN_SEGMENT_MS / 1000;
    let to_ms = |sample: usize| -> u64 { (sample as f32 / SAMPLE_RATE as f32 * 1000.0) as u64 };
    let rt = runtime()?;
    let mut out = Vec::new();
    for (s, e) in raw_segments
        .into_iter()
        .filter(|(s, e)| e - s >= min_samples)
    {
        if let Ok(emb) = rt.embedding(&samples[s..e]) {
            out.push(EmbeddingSegment {
                start_ms: to_ms(s),
                end_ms: to_ms(e),
                embedding: emb,
            });
        }
    }
    Ok(out)
}

/// Convenience for a single file: segment + cluster locally. For multi-chunk
/// meetings, collect [`segment_embeddings`] across all chunks and cluster once
/// with [`cluster_speakers`] so speaker ids stay consistent across chunks.
pub fn diarize(wav_path: &Path) -> Result<Vec<DiarizationSegment>, String> {
    let segs = segment_embeddings(wav_path)?;
    if segs.is_empty() {
        return Ok(Vec::new());
    }
    let embeddings: Vec<Vec<f32>> = segs.iter().map(|s| s.embedding.clone()).collect();
    let speakers = ahc_cluster(&embeddings, cluster_cosine_threshold());
    Ok(segs
        .iter()
        .enumerate()
        .map(|(i, s)| DiarizationSegment {
            start_ms: s.start_ms,
            end_ms: s.end_ms,
            speaker: speakers[i],
        })
        .collect())
}

pub(crate) fn read_pcm16k_mono_wav(path: &Path) -> Result<Vec<u8>, String> {
    let bytes = std::fs::read(path).map_err(|e| format!("read wav {}: {e}", path.display()))?;
    if bytes.len() < 44 || &bytes[0..4] != b"RIFF" || &bytes[8..12] != b"WAVE" {
        return Err(format!("not a RIFF/WAVE: {}", path.display()));
    }
    let riff_end = u32::from_le_bytes(bytes[4..8].try_into().unwrap()) as usize + 8;
    if riff_end != bytes.len() { return Err("WAV length does not match RIFF header; recording may be truncated".into()); }
    let mut offset = 12;
    let mut data: Option<(usize, usize)> = None;
    let mut format_valid = false;
    while offset + 8 <= bytes.len() {
        let id = &bytes[offset..offset + 4];
        let size = u32::from_le_bytes([
            bytes[offset + 4],
            bytes[offset + 5],
            bytes[offset + 6],
            bytes[offset + 7],
        ]) as usize;
        let body = offset + 8;
        let end = body.checked_add(size).filter(|end| *end <= riff_end)
            .ok_or("truncated WAV chunk; original recording preserved")?;
        if id == b"fmt " {
            if size < 16 || format_valid { return Err("invalid or duplicate WAV format".into()); }
            let u16_at = |n: usize| u16::from_le_bytes(bytes[body+n..body+n+2].try_into().unwrap());
            let u32_at = |n: usize| u32::from_le_bytes(bytes[body+n..body+n+4].try_into().unwrap());
            if u16_at(0) != 1 || u16_at(2) != 1 || u32_at(4) != 16_000 || u32_at(8) != 32_000 || u16_at(12) != 2 || u16_at(14) != 16 {
                return Err("unsupported WAV; expected 16 kHz mono PCM16".into());
            }
            format_valid = true;
        }
        if id == b"data" {
            if data.is_some() || size == 0 || size % 2 != 0 { return Err("invalid WAV PCM data chunk".into()); }
            data = Some((body, size));
        }
        offset = end + (size & 1);
    }
    if !format_valid || offset != riff_end { return Err("invalid WAV format or trailing chunk".into()); }
    let (start, size) = data.ok_or_else(|| "WAV has no data chunk".to_string())?;
    Ok(bytes[start..start + size].to_vec())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ahc_two_speakers_split() {
        // Two tight clusters of 2D unit vectors: {0,1} and {2,3}.
        let emb = vec![
            vec![1.0, 0.0],
            vec![0.98, 0.19], // close to 0
            vec![0.0, 1.0],
            vec![0.19, 0.98], // close to 2
        ];
        let mut e = emb.clone();
        for v in &mut e {
            normalize(v);
        }
        let ids = ahc_cluster(&e, 0.5);
        assert_eq!(ids[0], ids[1], "emb 0 and 1 same speaker");
        assert_eq!(ids[2], ids[3], "emb 2 and 3 same speaker");
        assert_ne!(ids[0], ids[2], "two distinct speakers");
    }

    #[test]
    fn ahc_single_speaker() {
        let mut emb = vec![vec![1.0, 0.0], vec![0.98, 0.19], vec![0.95, 0.31]];
        for v in &mut emb {
            normalize(v);
        }
        let ids = ahc_cluster(&emb, 0.5);
        assert!(ids.iter().all(|&id| id == ids[0]), "all same speaker");
    }

    #[test]
    fn constrained_speaker_identity_preserves_provider_distinctions_through_a_bridge() {
        let embeddings = vec![vec![1.0, 0.0]; 4];
        let constraint = |label: &str| Some(SpeakerConstraint { request: 0, label: label.into() });
        let groups = vec![constraint("a"), constraint("b"), None, constraint("a")];
        let ids = ahc_cluster_constrained(&embeddings, 0.68, &groups);
        assert_eq!(ids[0], ids[3]);
        assert_ne!(ids[0], ids[1], "a bridge cannot erase two provider identities");
        assert_eq!(ids[0], ids[2]);
        assert_eq!(ahc_cluster(&embeddings, 0.68), vec![0; 4]);
    }

    #[test]
    fn constrained_speaker_identity_matches_acoustics_across_reused_provider_labels() {
        let embeddings = vec![vec![1.0,0.0], vec![0.0,1.0], vec![0.0,1.0], vec![1.0,0.0]];
        let groups = [(0,"0"),(0,"1"),(1,"0"),(1,"1")].map(|(request,label)| {
            Some(SpeakerConstraint { request, label:label.into() })
        });
        let ids = ahc_cluster_constrained(&embeddings, 0.68, &groups);
        assert_eq!(ids[0], ids[3]);
        assert_eq!(ids[1], ids[2]);
        assert_ne!(ids[0], ids[1]);
        let embeddings = vec![vec![1.0,0.0,0.0,0.0],vec![0.0,1.0,0.0,0.0],
                              vec![0.0,0.0,1.0,0.0],vec![0.0,0.0,0.0,1.0]];
        let ids = ahc_cluster_constrained(&embeddings, 0.68, &groups);
        assert_eq!(ids.iter().copied().collect::<std::collections::BTreeSet<_>>().len(), 4,
            "labels reused by another request do not establish one identity");
    }

    #[test]
    fn energy_vad_silence_filtered() {
        // 3 seconds: 1s silence (zeros) + 1s tone + 1s silence.
        let n = SAMPLE_RATE as usize * 3;
        let mut samples = vec![0.0f32; n];
        let sr = SAMPLE_RATE as usize;
        for i in 0..sr {
            samples[sr + i] = (2.0 * std::f32::consts::PI * 220.0 * i as f32 / sr as f32).sin();
        }
        let segs = energy_vad(&samples);
        assert!(!segs.is_empty(), "tone window detected");
        // Windowing/merge may span slightly
        // beyond the strict [1s, 2s] tone region; assert it overlaps it.
        let tone_start = sr;
        let tone_end = 2 * sr;
        let any_overlap = segs.iter().any(|(s, e)| *e > tone_start && *s < tone_end);
        assert!(
            any_overlap,
            "a segment overlaps the tone region [1s,2s]: {:?}",
            segs
        );
    }

    /// Real diarization on the 4-speaker zh meeting clip. Disabled by default;
    /// requires Listener's speaker-verification models installed.
    ///
    /// `COMPANION_TYPE_SPEAKER_MODEL_DIR` defaults to
    /// `%APPDATA%\Listener Type\models\speaker-verification`.
    #[test]
    #[ignore = "requires Listener speaker-verification models (3dspeaker + sherpa-onnx runtime)"]
    fn diarize_four_speaker_meeting() {
        let wav = std::env::var("COMPANION_TYPE_DIARIZE_PROBE_WAV")
            .unwrap_or_else(|_| "docs/validation/four-speakers-zh.wav".to_string());
        let segments = diarize(Path::new(&wav)).expect("diarize");
        assert!(!segments.is_empty(), "expected speech segments");
        let speakers: std::collections::BTreeSet<usize> =
            segments.iter().map(|s| s.speaker).collect();
        eprintln!(
            "diarize_four_speaker: {} segments, {} distinct speakers detected",
            segments.len(),
            speakers.len()
        );
        for s in &segments {
            eprintln!(
                "  [{:>5}->{:>5}ms] speaker={}",
                s.start_ms, s.end_ms, s.speaker
            );
        }
        // The sample is a 4-speaker clip; we expect at least 2 distinct
        // speakers. (Exact count depends on VAD granularity + threshold.)
        assert!(
            speakers.len() >= 2,
            "expected at least 2 speakers, got {}: {:?}",
            speakers.len(),
            segments
        );
    }
}
