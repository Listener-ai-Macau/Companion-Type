//! Candidate offline ASR; runtime and model are supplied separately.
use libloading::Library;
use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::{
    ffi::{c_char, c_void, CStr, CString},
    fs::File,
    io::{Read, Seek, SeekFrom},
    path::Path,
};
pub(super) const RATE: usize = 16_000;
pub(super) const MODEL_SHA: &str =
    "3ef6c19369b912f7caf3cef8e545c5ccd1a33d9d7ec792a46668dc41c4b229ec";
pub(super) const TOKENS_SHA: &str =
    "4b2d964e18b9cf139b473003b6698fb2ed9a2a5ec55b93daa677b28f578897aa";
#[repr(C)]
struct FeatureConfig {
    sample_rate: i32,
    feature_dim: i32,
}

#[repr(C)]
struct TransducerConfig {
    encoder: *const c_char,
    decoder: *const c_char,
    joiner: *const c_char,
}

#[repr(C)]
struct ParaformerConfig {
    model: *const c_char,
}

#[repr(C)]
struct SingleModelConfig {
    model: *const c_char,
}

#[repr(C)]
struct WhisperConfig {
    encoder: *const c_char,
    decoder: *const c_char,
    language: *const c_char,
    task: *const c_char,
    tail_paddings: i32,
    enable_token_timestamps: i32,
    enable_segment_timestamps: i32,
}

#[repr(C)]
struct SenseVoiceConfig {
    model: *const c_char,
    language: *const c_char,
    use_itn: i32,
}

#[repr(C)]
struct MoonshineConfig {
    preprocessor: *const c_char,
    encoder: *const c_char,
    uncached_decoder: *const c_char,
    cached_decoder: *const c_char,
    merged_decoder: *const c_char,
}

#[repr(C)]
struct TwoModelConfig {
    encoder: *const c_char,
    decoder: *const c_char,
}

#[repr(C)]
struct CanaryConfig {
    encoder: *const c_char,
    decoder: *const c_char,
    src_lang: *const c_char,
    tgt_lang: *const c_char,
    use_pnc: i32,
}

#[repr(C)]
struct FunAsrNanoConfig {
    encoder_adaptor: *const c_char,
    llm: *const c_char,
    embedding: *const c_char,
    tokenizer: *const c_char,
    system_prompt: *const c_char,
    user_prompt: *const c_char,
    max_new_tokens: i32,
    temperature: f32,
    top_p: f32,
    seed: i32,
    language: *const c_char,
    itn: i32,
    hotwords: *const c_char,
}

#[repr(C)]
struct Qwen3AsrConfig {
    conv_frontend: *const c_char,
    encoder: *const c_char,
    decoder: *const c_char,
    tokenizer: *const c_char,
    max_total_len: i32,
    max_new_tokens: i32,
    temperature: f32,
    top_p: f32,
    seed: i32,
    hotwords: *const c_char,
}

#[repr(C)]
struct CohereConfig {
    encoder: *const c_char,
    decoder: *const c_char,
    language: *const c_char,
    use_punct: i32,
    use_itn: i32,
}

#[repr(C)]
struct OfflineModelConfig {
    transducer: TransducerConfig,
    paraformer: ParaformerConfig,
    nemo_ctc: SingleModelConfig,
    whisper: WhisperConfig,
    tdnn: SingleModelConfig,
    tokens: *const c_char,
    num_threads: i32,
    debug: i32,
    provider: *const c_char,
    model_type: *const c_char,
    modeling_unit: *const c_char,
    bpe_vocab: *const c_char,
    telespeech_ctc: *const c_char,
    sense_voice: SenseVoiceConfig,
    moonshine: MoonshineConfig,
    fire_red_asr: TwoModelConfig,
    dolphin: SingleModelConfig,
    zipformer_ctc: SingleModelConfig,
    canary: CanaryConfig,
    wenet_ctc: SingleModelConfig,
    omnilingual: SingleModelConfig,
    medasr: SingleModelConfig,
    funasr_nano: FunAsrNanoConfig,
    fire_red_asr_ctc: SingleModelConfig,
    qwen3_asr: Qwen3AsrConfig,
    cohere_transcribe: CohereConfig,
}

#[repr(C)]
struct LanguageModelConfig {
    model: *const c_char,
    scale: f32,
}

#[repr(C)]
struct HomophoneReplacerConfig {
    dict_dir: *const c_char,
    lexicon: *const c_char,
    rule_fsts: *const c_char,
}

#[repr(C)]
struct OfflineRecognizerConfig {
    feat_config: FeatureConfig,
    model_config: OfflineModelConfig,
    lm_config: LanguageModelConfig,
    decoding_method: *const c_char,
    max_active_paths: i32,
    hotwords_file: *const c_char,
    hotwords_score: f32,
    rule_fsts: *const c_char,
    rule_fars: *const c_char,
    blank_penalty: f32,
    hr: HomophoneReplacerConfig,
}

type CreateRecognizer = unsafe extern "C" fn(*const OfflineRecognizerConfig) -> *const c_void;
type DestroyRecognizer = unsafe extern "C" fn(*const c_void);
type CreateStream = unsafe extern "C" fn(*const c_void) -> *const c_void;
type DestroyStream = unsafe extern "C" fn(*const c_void);
type AcceptWaveform = unsafe extern "C" fn(*const c_void, i32, *const f32, i32);
type DecodeStream = unsafe extern "C" fn(*const c_void, *const c_void);
type GetResultJson = unsafe extern "C" fn(*const c_void) -> *const c_char;
type DestroyResultJson = unsafe extern "C" fn(*const c_char);

#[derive(Deserialize)]
struct RecognitionResult {
    text: String,
}

pub(super) fn verified(path: &Path, expected: &str) -> Result<(), String> {
    let mut f =
        File::open(path).map_err(|e| format!("本地转写组件不可用 {}: {e}", path.display()))?;
    let mut hash = Sha256::new();
    let mut buf = [0u8; 65536];
    loop {
        let n = f.read(&mut buf).map_err(|e| e.to_string())?;
        if n == 0 {
            break;
        }
        hash.update(&buf[..n]);
    }
    if format!("{:x}", hash.finalize()) != expected {
        return Err("本地语音模型校验失败；原录音保留。".into());
    }
    Ok(())
}
fn cpath(path: &Path) -> Result<CString, String> {
    CString::new(path.to_string_lossy().as_bytes()).map_err(|_| "本地模型路径无效".into())
}
pub(super) struct Runtime {
    _onnx: Library,
    #[cfg(windows)]
    _providers: Library,
    _sherpa: Library,
    recognizer: *const c_void,
    create_stream: CreateStream,
    destroy_stream: DestroyStream,
    accept: AcceptWaveform,
    decode: DecodeStream,
    result: GetResultJson,
    destroy_result: DestroyResultJson,
    destroy: DestroyRecognizer,
}
impl Drop for Runtime {
    fn drop(&mut self) {
        unsafe { (self.destroy)(self.recognizer) }
    }
}
impl Runtime {
    pub(super) fn load(root: &Path, runtime_root: &Path) -> Result<Self, String> {
        let model = root.join("sherpa-onnx-paraformer-zh-small-2024-03-09/model.int8.onnx");
        let tokens = root.join("sherpa-onnx-paraformer-zh-small-2024-03-09/tokens.txt");
        verified(&model, MODEL_SHA)?;
        verified(&tokens, TOKENS_SHA)?;
        #[cfg(windows)]
        for (name, hash) in [
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
        ] {
            verified(&runtime_root.join(name), hash)?;
        }
        #[cfg(target_os = "android")]
        if !runtime_root.as_os_str().is_empty() {
            for (name, hash) in [
                (
                    "libonnxruntime.so",
                    "4d2318b3849abb8862133d3068fc7e807ed8b2671cc6d83657fff2fcb9e1caad",
                ),
                (
                    "libsherpa-onnx-c-api.so",
                    "c9d2277b02366fd467ca6f0cde2fc16f8efb69b2fb80cf51e8e3fee0c9f12278",
                ),
            ] {
                verified(&runtime_root.join(name), hash)?;
            }
        }
        let model = cpath(&model)?;
        let tokens = cpath(&tokens)?;
        let cpu = CString::new("cpu").unwrap();
        let greedy = CString::new("greedy_search").unwrap();
        unsafe {
            #[cfg(windows)]
            let onnx =
                Library::new(runtime_root.join("onnxruntime.dll")).map_err(|e| e.to_string())?;
            #[cfg(windows)]
            let providers = Library::new(runtime_root.join("onnxruntime_providers_shared.dll"))
                .map_err(|e| e.to_string())?;
            #[cfg(windows)]
            let lib = Library::new(runtime_root.join("sherpa-onnx-c-api.dll"))
                .map_err(|e| e.to_string())?;
            #[cfg(target_os = "android")]
            let onnx = Library::new(if runtime_root.as_os_str().is_empty() {
                std::path::PathBuf::from("libonnxruntime.so")
            } else {
                runtime_root.join("libonnxruntime.so")
            })
            .map_err(|e| e.to_string())?;
            #[cfg(target_os = "android")]
            let lib = Library::new(if runtime_root.as_os_str().is_empty() {
                std::path::PathBuf::from("libsherpa-onnx-c-api.so")
            } else {
                runtime_root.join("libsherpa-onnx-c-api.so")
            })
            .map_err(|e| e.to_string())?;
            let create: CreateRecognizer = *lib
                .get(b"SherpaOnnxCreateOfflineRecognizer\0")
                .map_err(|e| e.to_string())?;
            let destroy: DestroyRecognizer = *lib
                .get(b"SherpaOnnxDestroyOfflineRecognizer\0")
                .map_err(|e| e.to_string())?;
            let create_stream: CreateStream = *lib
                .get(b"SherpaOnnxCreateOfflineStream\0")
                .map_err(|e| e.to_string())?;
            let destroy_stream: DestroyStream = *lib
                .get(b"SherpaOnnxDestroyOfflineStream\0")
                .map_err(|e| e.to_string())?;
            let accept: AcceptWaveform = *lib
                .get(b"SherpaOnnxAcceptWaveformOffline\0")
                .map_err(|e| e.to_string())?;
            let decode: DecodeStream = *lib
                .get(b"SherpaOnnxDecodeOfflineStream\0")
                .map_err(|e| e.to_string())?;
            let result: GetResultJson = *lib
                .get(b"SherpaOnnxGetOfflineStreamResultAsJson\0")
                .map_err(|e| e.to_string())?;
            let destroy_result: DestroyResultJson = *lib
                .get(b"SherpaOnnxDestroyOfflineStreamResultJson\0")
                .map_err(|e| e.to_string())?;
            let mut config: OfflineRecognizerConfig = std::mem::zeroed();
            config.feat_config.sample_rate = RATE as i32;
            config.feat_config.feature_dim = 80;
            config.model_config.paraformer.model = model.as_ptr();
            config.model_config.tokens = tokens.as_ptr();
            config.model_config.num_threads = 2;
            config.model_config.provider = cpu.as_ptr();
            config.decoding_method = greedy.as_ptr();
            let recognizer = create(&config);
            if recognizer.is_null() {
                return Err("本地语音模型无法启动，原录音保留。".into());
            }
            Ok(Self {
                _onnx: onnx,
                #[cfg(windows)]
                _providers: providers,
                _sherpa: lib,
                recognizer,
                create_stream,
                destroy_stream,
                accept,
                decode,
                result,
                destroy_result,
                destroy,
            })
        }
    }
    pub(super) fn transcribe(&self, pcm: &[u8]) -> Result<String, String> {
        let samples: Vec<f32> = pcm
            .chunks_exact(2)
            .map(|x| i16::from_le_bytes([x[0], x[1]]) as f32 / 32768.0)
            .collect();
        unsafe {
            let stream = (self.create_stream)(self.recognizer);
            if stream.is_null() {
                return Err("无法创建本地转写任务".into());
            }
            let result = (|| {
                (self.accept)(stream, RATE as i32, samples.as_ptr(), samples.len() as i32);
                (self.decode)(self.recognizer, stream);
                let p = (self.result)(stream);
                if p.is_null() {
                    return Err("本地转写没有返回结果".into());
                }
                let json = CStr::from_ptr(p).to_string_lossy().into_owned();
                (self.destroy_result)(p);
                let value: RecognitionResult =
                    serde_json::from_str(&json).map_err(|e| e.to_string())?;
                Ok(value.text)
            })();
            (self.destroy_stream)(stream);
            result
        }
    }
}

// Validate RIFF before inference, then read small bounded windows, including for two-hour recordings.
pub(super) fn wav_data(file: &mut File) -> Result<(u64, u64), String> {
    let size = file.metadata().map_err(|e| e.to_string())?.len();
    let mut h = [0u8; 12];
    file.read_exact(&mut h).map_err(|e| e.to_string())?;
    if &h[..4] != b"RIFF"
        || &h[8..] != b"WAVE"
        || u32::from_le_bytes(h[4..8].try_into().unwrap()) as u64 + 8 != size
    {
        return Err("录音WAV长度或格式无效，原录音保留。".into());
    }
    let mut pos = 12u64;
    let mut fmt = false;
    let mut data = None;
    while pos + 8 <= size {
        file.seek(SeekFrom::Start(pos)).map_err(|e| e.to_string())?;
        let mut head = [0u8; 8];
        file.read_exact(&mut head).map_err(|e| e.to_string())?;
        let len = u32::from_le_bytes(head[4..].try_into().unwrap()) as u64;
        let start = pos + 8;
        let end = start
            .checked_add(len)
            .filter(|x| *x <= size)
            .ok_or("录音WAV分段不完整")?;
        if &head[..4] == b"fmt " {
            if fmt || len < 16 {
                return Err("录音WAV格式无效".into());
            }
            let mut f = [0u8; 16];
            file.read_exact(&mut f).map_err(|e| e.to_string())?;
            if u16::from_le_bytes(f[0..2].try_into().unwrap()) != 1
                || u16::from_le_bytes(f[2..4].try_into().unwrap()) != 1
                || u32::from_le_bytes(f[4..8].try_into().unwrap()) != 16000
                || u32::from_le_bytes(f[8..12].try_into().unwrap()) != 32000
                || u16::from_le_bytes(f[12..14].try_into().unwrap()) != 2
                || u16::from_le_bytes(f[14..16].try_into().unwrap()) != 16
            {
                return Err("本地转写需要16kHz单声道PCM录音".into());
            }
            fmt = true;
        } else if &head[..4] == b"data" {
            if data.is_some() || len % 2 != 0 {
                return Err("录音WAV数据无效".into());
            }
            data = Some((start, len));
        }
        pos = end + len % 2;
        if pos > size {
            return Err("录音WAV不完整".into());
        }
    }
    if !fmt || pos != size {
        return Err("录音WAV缺少有效格式".into());
    }
    let (start, len) = data.ok_or("录音WAV缺少声音")?;
    if len == 0 {
        return Err("录音为空".into());
    }
    Ok((start, len))
}

// Cut near a quiet region, covering the original samples exactly once. This
// model provides no word timestamps; it cannot promise seam-perfect text.
pub(super) fn cut_samples(pcm: &[u8]) -> usize {
    let count = pcm.len() / 2;
    if count <= 20 * RATE {
        return count;
    }
    let mut best = (u64::MAX, 16 * RATE);
    for i in (14 * RATE..=18 * RATE).step_by(RATE / 5) {
        let mut energy = 0u64;
        for s in (i - RATE / 20)..(i + RATE / 20) {
            let j = s * 2;
            energy += i16::from_le_bytes([pcm[j], pcm[j + 1]]).unsigned_abs() as u64;
        }
        let score = energy + (i.abs_diff(16 * RATE) as u64) / 20;
        if score < best.0 {
            best = (score, i);
        }
    }
    best.1
}
