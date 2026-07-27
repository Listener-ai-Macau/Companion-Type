//! Companion-Type owned transcription boundary.
//!
//! This module intentionally does not shell out to Listener-Type. The first
//! production adapters can plug in here without changing the app IPC surface.
//! The OpenAI-compatible HTTP client itself lives in the platform
//! `denzic-host-audio-v1-core` crate; this module keeps provider selection,
//! env-var plumbing, and the Companion-specific guardrails.

use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::Duration;

use super::volcengine::{VolcengineCredentials, VolcengineSaucAsr};
use denzic_host_audio_v1_core::asr::{normalize_transcript, BatchAsrProvider};
use denzic_host_audio_v1_core::asr_openai::{OpenAiAsrConfig, OpenAiCompatibleAsr};
use denzic_host_audio_v1_core::{
    ASR_DEFAULT_MAX_UPLOAD_BYTES, ASR_DEFAULT_MODEL, ASR_OPENAI_TRANSCRIPTION_ENDPOINT,
    ASR_REQUEST_TIMEOUT_SECONDS,
};

#[derive(Clone, Debug)]
pub struct CompanionTranscript {
    pub text: String,
    pub provider_id: String,
    pub mode: String,
    pub evidence_path: Option<PathBuf>,
}

#[derive(Clone, Debug)]
pub struct CompanionTranscriptionManager;

impl CompanionTranscriptionManager {
    pub fn new() -> Self {
        Self
    }

    pub fn transcribe_audio(&self, audio_path: &str) -> Result<CompanionTranscript, String> {
        let audio = PathBuf::from(audio_path);
        if !audio.exists() {
            return Err(format!("audio path does not exist: {}", audio.display()));
        }
        self.transcribe_existing_path(&audio)
    }

    /// Transcribe one primary path and optionally merge per-chunk files (long meetings).
    pub fn transcribe_session(
        &self,
        primary_audio: Option<&str>,
        chunk_paths: &[String],
    ) -> Result<CompanionTranscript, String> {
        if let Ok(text) = std::env::var("COMPANION_TYPE_TRANSCRIPT_TEXT") {
            let text = normalize_transcript(&text);
            if !text.is_empty() {
                return Ok(CompanionTranscript {
                    text,
                    provider_id: "companion-type-env-transcript".to_string(),
                    mode: "env-text".to_string(),
                    evidence_path: None,
                });
            }
        }

        let mut real_paths = Vec::new();
        for path in chunk_paths {
            let p = PathBuf::from(path);
            if p.exists() {
                real_paths.push(p);
            }
        }
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
        if real_paths.len() == 1 {
            return self.transcribe_existing_path(&real_paths[0]);
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
        })
    }

    fn transcribe_existing_path(&self, audio: &Path) -> Result<CompanionTranscript, String> {
        if let Ok(text) = std::env::var("COMPANION_TYPE_TRANSCRIPT_TEXT") {
            let text = normalize_transcript(&text);
            if !text.is_empty() {
                return Ok(CompanionTranscript {
                    text,
                    provider_id: "companion-type-env-transcript".to_string(),
                    mode: "env-text".to_string(),
                    evidence_path: None,
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

    let mut process = Command::new(&command);
    let args = std::env::var("COMPANION_TYPE_ASR_ARGS").unwrap_or_else(|_| "{audio}".to_string());
    for arg in split_command_args(&args) {
        process.arg(arg.replace("{audio}", &audio.to_string_lossy()));
    }

    let output = process
        .output()
        .map_err(|err| format!("run Companion-Type ASR command {command}: {err}"))?;
    if !output.status.success() {
        return Err(format!(
            "Companion-Type ASR command failed with {}: {}",
            output.status,
            String::from_utf8_lossy(&output.stderr).trim()
        ));
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    let text = normalize_transcript(&extract_transcript_from_stdout(&stdout));
    if text.is_empty() {
        return Err("Companion-Type ASR command did not print a transcript".to_string());
    }
    Ok(CompanionTranscript {
        text,
        provider_id: "companion-type-command-asr".to_string(),
        mode: "external-command".to_string(),
        evidence_path: None,
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

fn volcengine_transcript(audio: &Path) -> Result<CompanionTranscript, String> {
    let app_id = std::env::var("COMPANION_TYPE_VOLC_APP_KEY")
        .map_err(|_| "COMPANION_TYPE_VOLC_APP_KEY is not set".to_string())?;
    let access_token = std::env::var("COMPANION_TYPE_VOLC_ACCESS_KEY")
        .map_err(|_| "COMPANION_TYPE_VOLC_ACCESS_KEY is not set".to_string())?;
    let resource_id = std::env::var("COMPANION_TYPE_VOLC_RESOURCE_ID")
        .unwrap_or_else(|_| VolcengineCredentials::default_resource_id().to_string());
    let asr = VolcengineSaucAsr::new(VolcengineCredentials {
        app_id,
        access_token,
        resource_id,
    });
    let text = asr.transcribe_file(audio)?;
    Ok(CompanionTranscript {
        text: normalize_transcript(&text),
        provider_id: "companion-type-volcengine-asr".to_string(),
        mode: "ws-sauc:bigmodel".to_string(),
        evidence_path: None,
    })
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
    })
}

fn extract_transcript_from_stdout(stdout: &str) -> String {
    for line in stdout.lines() {
        let trimmed = line.trim();
        if let Some(value) = trimmed.strip_prefix("transcript=") {
            return value.trim().to_string();
        }
        if let Some(value) = trimmed.strip_prefix("text=") {
            return value.trim().to_string();
        }
    }
    stdout.trim().to_string()
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
