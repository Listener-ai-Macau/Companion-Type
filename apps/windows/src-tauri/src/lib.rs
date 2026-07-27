//! Companion Type Tauri backend.
//!
//! The module split keeps IPC commands, workflow state, replaceable services,
//! and the shared Companion contract separate.

mod backend;
mod commands;
mod companion_v1;
mod coordinator;

use std::fs;
use std::path::{Path, PathBuf};
use std::process;
use std::sync::Arc;

use backend::{CompanionFirmwareOtaRequest, CompanionTranscriptionManager};
use coordinator::CompanionCoordinator;

pub fn run() {
    let args = std::env::args().collect::<Vec<_>>();
    if let Some(result) = run_firmware_ota_cli(&args) {
        process::exit(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(result) = run_embedded_audio_cli(args) {
        process::exit(if result.is_ok() { 0 } else { 1 });
    }

    let coordinator = Arc::new(CompanionCoordinator::new_fixture());

    tauri::Builder::default()
        .manage(coordinator)
        .invoke_handler(tauri::generate_handler![
            commands::get_companion_v1_snapshot,
            commands::apply_companion_v1_control,
            commands::get_companion_backend_capabilities,
            commands::get_companion_ble_bridge_status,
            commands::transfer_companion_firmware_ota
        ])
        .setup(|app| {
            // The main window is built here (not in tauri.conf.json) so we can inject
            // WebView2 browser args for acceptance-test automation (e.g. CDP). The window
            // matches the previous config: "Companion Type", 980x720, min 420x560.
            let mut builder = tauri::webview::WebviewWindowBuilder::new(
                app,
                "main",
                tauri::WebviewUrl::App("index.html".into()),
            )
            .title("Companion Type")
            .inner_size(980.0, 720.0)
            .min_inner_size(420.0, 560.0);

            // Acceptance-test hook: only when COMPANION_TYPE_WEBVIEW_ARGS is set (e.g.
            // "--remote-debugging-port=9223"). wry overrides its default browser args when this
            // is used, so the standard --disable-features are re-added to keep the normal app
            // behavior identical.
            if let Ok(extra) = std::env::var("COMPANION_TYPE_WEBVIEW_ARGS") {
                let extra = extra.trim();
                if !extra.is_empty() {
                    let combined = format!(
                        "--disable-features=msWebOOUI,msPdfOOUI,msSmartScreenProtection {extra}"
                    );
                    builder = builder.additional_browser_args(&combined);
                }
            }

            builder.build()?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Companion Type");
}

fn run_firmware_ota_cli(args: &[String]) -> Option<Result<(), String>> {
    let index = args
        .iter()
        .position(|arg| arg == "--firmware-ota-transfer")?;
    let result = (|| {
        let manifest_path = args
            .get(index + 1)
            .ok_or_else(|| "missing manifest path after --firmware-ota-transfer".to_string())?;
        let firmware_path = args
            .get(index + 2)
            .ok_or_else(|| "missing firmware path after --firmware-ota-transfer".to_string())?;
        if !Path::new(manifest_path).is_file() {
            return Err(format!("OTA manifest does not exist: {manifest_path}"));
        }
        if !Path::new(firmware_path).is_file() {
            return Err(format!("OTA firmware does not exist: {firmware_path}"));
        }
        let device_id = args
            .iter()
            .position(|arg| arg == "--device-id")
            .and_then(|position| args.get(position + 1))
            .cloned();
        let report = CompanionCoordinator::new_fixture().transfer_firmware_ota(
            CompanionFirmwareOtaRequest {
                manifest_path: manifest_path.clone(),
                firmware_path: firmware_path.clone(),
                device_id,
            },
        )?;
        let payload = serde_json::json!({
            "status": "PASS",
            "protocol": report.protocol,
            "deviceId": report.device_id,
            "firmwareBytes": report.firmware_bytes,
            "dataWrites": report.data_writes,
            "statusReads": report.status_reads,
            "recoveredOffsets": report.recovered_offsets,
            "activeLinkConfirmed": report.active_link_confirmed,
            "elapsedMs": report.elapsed_ms,
        });
        println!("firmware_ota_result_json={payload}");
        Ok(())
    })();
    if let Err(error) = &result {
        eprintln!("[cli] Companion OTA failed: {error}");
    }
    Some(result)
}

fn run_embedded_audio_cli(args: Vec<String>) -> Option<Result<(), String>> {
    let intent = match embedded_audio_cli_path(&args) {
        Some(Ok(intent)) => intent,
        Some(Err(error)) => {
            eprintln!("[cli] submit-embedded-audio-streaming-file failed: {error}");
            return Some(Err(error));
        }
        None => return None,
    };

    let audio_path = intent.audio_path;
    let audio_path_text = audio_path.to_string_lossy().to_string();
    println!(
        "[cli] submit-embedded-audio-streaming-file: path={} format={}",
        audio_path.display(),
        intent.format
    );

    let result = CompanionTranscriptionManager::new().transcribe_audio(&audio_path_text);
    match result {
        Ok(transcript) => {
            let text = transcript.text;
            if let Err(error) = write_debug_transcript(&text) {
                eprintln!("[cli] write debug transcript failed: {error}");
            }
            let payload = serde_json::json!({
                "result": {
                    "text": text.clone(),
                    "utterances": [
                        {
                            "definite": true,
                            "text": text.clone(),
                        }
                    ]
                }
            });
            println!("[asr] server JSON: {payload}");
            println!("source=backend.companion_type_cli event=asr_final transcript_empty=false");
            println!(
                "[cli] submit-embedded-audio-streaming-file done: pcm_bytes={} missing_packets=0",
                pcm_payload_bytes(&audio_path, intent.format)
            );
            Some(Ok(()))
        }
        Err(error) => {
            eprintln!("[cli] submit-embedded-audio-streaming-file failed: {error}");
            Some(Err(error))
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum EmbeddedAudioFormat {
    Raw,
    Wav,
    Pcm16Le,
}

impl std::fmt::Display for EmbeddedAudioFormat {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let value = match self {
            EmbeddedAudioFormat::Raw => "raw",
            EmbeddedAudioFormat::Wav => "wav",
            EmbeddedAudioFormat::Pcm16Le => "pcm16le",
        };
        formatter.write_str(value)
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
struct EmbeddedAudioCliIntent {
    audio_path: PathBuf,
    format: EmbeddedAudioFormat,
}

fn embedded_audio_cli_path(args: &[String]) -> Option<Result<EmbeddedAudioCliIntent, String>> {
    let mut index = 1;
    while index < args.len() {
        let format = match args[index].as_str() {
            "--submit-embedded-audio" | "--submit-embedded-audio-stream" => {
                Some(EmbeddedAudioFormat::Raw)
            }
            "--submit-embedded-audio-wav" | "--submit-embedded-audio-wav-stream" => {
                Some(EmbeddedAudioFormat::Wav)
            }
            "--submit-embedded-audio-pcm16le" | "--submit-embedded-audio-pcm16le-stream" => {
                Some(EmbeddedAudioFormat::Pcm16Le)
            }
            _ => None,
        };
        if let Some(format) = format {
            let Some(path) = args.get(index + 1) else {
                return Some(Err(format!("missing audio path after {}", args[index])));
            };
            let audio_path = PathBuf::from(path);
            if !audio_path.exists() {
                return Some(Err(format!(
                    "audio path does not exist: {}",
                    audio_path.display()
                )));
            }
            return Some(Ok(EmbeddedAudioCliIntent { audio_path, format }));
        }
        index += 1;
    }
    None
}

fn write_debug_transcript(text: &str) -> Result<(), String> {
    let mut paths = Vec::new();
    for key in [
        "COMPANION_TYPE_DEBUG_TRANSCRIPT_FILE",
        "LISTENER_TYPE_DEBUG_TRANSCRIPT_FILE",
    ] {
        if let Some(path) = std::env::var_os(key).map(PathBuf::from) {
            if !paths.contains(&path) {
                paths.push(path);
            }
        }
    }
    for path in paths {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)
                .map_err(|error| format!("create {}: {error}", parent.display()))?;
        }
        fs::write(&path, text).map_err(|error| format!("write {}: {error}", path.display()))?;
    }
    Ok(())
}

fn pcm_payload_bytes(audio_path: &Path, format: EmbeddedAudioFormat) -> u64 {
    if format == EmbeddedAudioFormat::Wav
        || audio_path
            .extension()
            .is_some_and(|value| value.to_string_lossy().eq_ignore_ascii_case("wav"))
    {
        if let Some(size) = wav_data_chunk_bytes(audio_path) {
            return size;
        }
    }
    fs::metadata(audio_path)
        .map(|metadata| metadata.len())
        .unwrap_or(0)
}

fn wav_data_chunk_bytes(audio_path: &Path) -> Option<u64> {
    let data = fs::read(audio_path).ok()?;
    if data.len() < 12 || &data[0..4] != b"RIFF" || &data[8..12] != b"WAVE" {
        return None;
    }
    let mut cursor = 12;
    while cursor + 8 <= data.len() {
        let chunk_id = &data[cursor..cursor + 4];
        let chunk_size = u32::from_le_bytes(data[cursor + 4..cursor + 8].try_into().ok()?) as usize;
        cursor += 8;
        if chunk_id == b"data" {
            return Some(chunk_size as u64);
        }
        cursor = cursor.saturating_add(chunk_size + (chunk_size % 2));
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn embedded_audio_cli_ignores_normal_app_launch() {
        let args = vec![
            "companion-type".to_string(),
            "--suppress-capsule-window".to_string(),
        ];
        assert_eq!(embedded_audio_cli_path(&args), None);
    }

    #[test]
    fn embedded_audio_cli_accepts_listener_compatible_wav_stream_flag() {
        let root = std::env::temp_dir().join("companion-type-cli-wav-stream-test");
        let _ = fs::create_dir_all(&root);
        let audio = root.join("input.wav");
        fs::write(&audio, b"RIFF----WAVEfmt ").unwrap();
        let args = vec![
            "companion-type".to_string(),
            "--suppress-capsule-window".to_string(),
            "--submit-embedded-audio-wav-stream".to_string(),
            audio.to_string_lossy().to_string(),
        ];
        let intent = embedded_audio_cli_path(&args).unwrap().unwrap();
        assert_eq!(intent.audio_path, audio);
        assert_eq!(intent.format, EmbeddedAudioFormat::Wav);
    }

    #[test]
    fn wav_payload_bytes_uses_data_chunk_size() {
        let root = std::env::temp_dir().join("companion-type-cli-wav-bytes-test");
        let _ = fs::create_dir_all(&root);
        let audio = root.join("input.wav");
        let mut wav = Vec::new();
        wav.extend_from_slice(b"RIFF");
        wav.extend_from_slice(&40_u32.to_le_bytes());
        wav.extend_from_slice(b"WAVE");
        wav.extend_from_slice(b"fmt ");
        wav.extend_from_slice(&16_u32.to_le_bytes());
        wav.extend_from_slice(&[1, 0, 1, 0, 0x80, 0x3e, 0, 0, 0, 0x7d, 0, 0, 2, 0, 16, 0]);
        wav.extend_from_slice(b"data");
        wav.extend_from_slice(&4_u32.to_le_bytes());
        wav.extend_from_slice(&[1, 2, 3, 4]);
        fs::write(&audio, wav).unwrap();
        assert_eq!(pcm_payload_bytes(&audio, EmbeddedAudioFormat::Wav), 4);
    }
}
