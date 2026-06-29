use serde::{Deserialize, Serialize};

pub const COMPANION_V1_SCHEMA: &str = "companion.host.v1";
pub const COMPANION_V1_DEFAULT_BLE_NAME: &str = "companion";
pub const COMPANION_V1_BLE_NAME_MAX_BYTES: usize = 29;

#[derive(Clone, Copy, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1GattBoundary {
    pub settings_service_uuid: &'static str,
    pub ble_name_config_uuid: &'static str,
    pub meeting_service_uuid: &'static str,
    pub meeting_control_uuid: &'static str,
    pub meeting_status_uuid: &'static str,
    pub sensors_service_uuid: &'static str,
    pub imu_status_uuid: &'static str,
    pub audio_output_service_uuid: &'static str,
    pub speaker_control_uuid: &'static str,
    pub speaker_status_uuid: &'static str,
    pub wake_word_control_uuid: &'static str,
    pub wake_word_status_uuid: &'static str,
}

pub const COMPANION_V1_GATT_BOUNDARY: CompanionV1GattBoundary = CompanionV1GattBoundary {
    settings_service_uuid: "8f7a0004-7b7d-4f3d-9d6f-6c2d1b7c0000",
    ble_name_config_uuid: "8f7a4002-7b7d-4f3d-9d6f-6c2d1b7c0000",
    meeting_service_uuid: "8f7a0008-7b7d-4f3d-9d6f-6c2d1b7c0000",
    meeting_control_uuid: "8f7a8001-7b7d-4f3d-9d6f-6c2d1b7c0000",
    meeting_status_uuid: "8f7a8002-7b7d-4f3d-9d6f-6c2d1b7c0000",
    sensors_service_uuid: "8f7a0009-7b7d-4f3d-9d6f-6c2d1b7c0000",
    imu_status_uuid: "8f7a9001-7b7d-4f3d-9d6f-6c2d1b7c0000",
    audio_output_service_uuid: "8f7a000a-7b7d-4f3d-9d6f-6c2d1b7c0000",
    speaker_control_uuid: "8f7aa001-7b7d-4f3d-9d6f-6c2d1b7c0000",
    speaker_status_uuid: "8f7aa002-7b7d-4f3d-9d6f-6c2d1b7c0000",
    wake_word_control_uuid: "8f7aa003-7b7d-4f3d-9d6f-6c2d1b7c0000",
    wake_word_status_uuid: "8f7aa004-7b7d-4f3d-9d6f-6c2d1b7c0000",
};

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1Snapshot {
    pub schema: &'static str,
    pub source: &'static str,
    pub device_id: Option<String>,
    pub connected: bool,
    pub updated_at: String,
    pub gatt: CompanionV1GattBoundary,
    pub meeting: CompanionV1MeetingState,
    pub imu: CompanionV1ImuState,
    pub speaker: CompanionV1SpeakerState,
    pub wake_word: CompanionV1WakeWordState,
    pub ble_name: CompanionV1BleNameState,
    pub last_control: Option<CompanionV1ControlEcho>,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1MeetingState {
    pub supported: bool,
    pub active: bool,
    pub status: String,
    pub started_at: Option<String>,
    pub duration_ms: u64,
    pub transcript_count: u32,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1ImuState {
    pub supported: bool,
    pub online: bool,
    pub sample_hz: u16,
    pub motion: String,
    pub accel: CompanionV1Vector3,
    pub gyro: CompanionV1Vector3,
}

#[derive(Clone, Debug, Serialize)]
pub struct CompanionV1Vector3 {
    pub x: f32,
    pub y: f32,
    pub z: f32,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1SpeakerState {
    pub supported: bool,
    pub online: bool,
    pub muted: bool,
    pub volume: u8,
    pub status: String,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1WakeWordState {
    pub supported: bool,
    pub armed: bool,
    pub engine: String,
    pub keyword: String,
    pub last_detected_at: Option<String>,
    pub confidence: f32,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1BleNameState {
    pub active_name: String,
    pub staged_name: String,
    pub max_len: u8,
    pub status: String,
    pub pending_restart: bool,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1ControlEcho {
    pub action: CompanionV1ControlAction,
    pub characteristic_uuid: &'static str,
    pub payload_hex: String,
    pub accepted: bool,
    pub message: String,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub enum CompanionV1ControlAction {
    StageBleName,
    ApplyBleName,
    ResetBleName,
    MeetingStart,
    MeetingStop,
    MeetingFinalize,
    SpeakerPrompt,
    SpeakerStop,
    WakeArm,
    WakeDisable,
    WakeTestDetect,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1ControlRequest {
    pub action: CompanionV1ControlAction,
    pub ble_name: Option<String>,
    pub session_id: Option<String>,
    pub prompt_id: Option<String>,
}

pub fn companion_ble_name_is_valid(name: &str) -> bool {
    let bytes = name.as_bytes();
    if bytes.is_empty() || bytes.len() > COMPANION_V1_BLE_NAME_MAX_BYTES {
        return false;
    }
    bytes
        .iter()
        .all(|byte| (0x20..=0x7e).contains(byte) && !matches!(byte, b'"' | b'\'' | b';' | b'=' | b'\\'))
}

pub fn fixture_snapshot() -> CompanionV1Snapshot {
    CompanionV1Snapshot {
        schema: COMPANION_V1_SCHEMA,
        source: "fixture",
        device_id: Some("fixture-companion-v1".to_string()),
        connected: false,
        updated_at: "fixture".to_string(),
        gatt: COMPANION_V1_GATT_BOUNDARY,
        meeting: CompanionV1MeetingState {
            supported: true,
            active: false,
            status: "idle".to_string(),
            started_at: None,
            duration_ms: 0,
            transcript_count: 0,
        },
        imu: CompanionV1ImuState {
            supported: true,
            online: false,
            sample_hz: 0,
            motion: "unknown".to_string(),
            accel: CompanionV1Vector3 { x: 0.0, y: 0.0, z: 1.0 },
            gyro: CompanionV1Vector3 { x: 0.0, y: 0.0, z: 0.0 },
        },
        speaker: CompanionV1SpeakerState {
            supported: true,
            online: false,
            muted: false,
            volume: 65,
            status: "idle".to_string(),
        },
        wake_word: CompanionV1WakeWordState {
            supported: true,
            armed: false,
            engine: "fixture".to_string(),
            keyword: "hey companion".to_string(),
            last_detected_at: None,
            confidence: 0.0,
        },
        ble_name: CompanionV1BleNameState {
            active_name: COMPANION_V1_DEFAULT_BLE_NAME.to_string(),
            staged_name: COMPANION_V1_DEFAULT_BLE_NAME.to_string(),
            max_len: COMPANION_V1_BLE_NAME_MAX_BYTES as u8,
            status: "clean".to_string(),
            pending_restart: false,
        },
        last_control: None,
    }
}

pub fn apply_fixture_control(
    request: CompanionV1ControlRequest,
) -> Result<CompanionV1Snapshot, String> {
    let mut snapshot = fixture_snapshot();

    match request.action {
        CompanionV1ControlAction::StageBleName => {
            let name = request
                .ble_name
                .clone()
                .ok_or_else(|| "bleName is required".to_string())?;
            if !companion_ble_name_is_valid(&name) {
                return Err("invalid Companion BLE name".to_string());
            }
            snapshot.ble_name.staged_name = name;
            snapshot.ble_name.status = "staged".to_string();
            snapshot.ble_name.pending_restart = true;
        }
        CompanionV1ControlAction::ApplyBleName => {
            snapshot.ble_name.status = "pendingRestart".to_string();
            snapshot.ble_name.pending_restart = true;
        }
        CompanionV1ControlAction::ResetBleName => {
            snapshot.ble_name.staged_name = COMPANION_V1_DEFAULT_BLE_NAME.to_string();
            snapshot.ble_name.status = "staged".to_string();
            snapshot.ble_name.pending_restart = true;
        }
        CompanionV1ControlAction::MeetingStart => {
            snapshot.meeting.active = true;
            snapshot.meeting.status = "recording".to_string();
            snapshot.meeting.started_at = Some("fixture".to_string());
        }
        CompanionV1ControlAction::MeetingStop => {
            snapshot.meeting.active = false;
            snapshot.meeting.status = "idle".to_string();
            snapshot.meeting.duration_ms = 1;
        }
        CompanionV1ControlAction::MeetingFinalize => {
            snapshot.meeting.active = false;
            snapshot.meeting.status = "finalized".to_string();
            snapshot.meeting.transcript_count = 1;
        }
        CompanionV1ControlAction::SpeakerPrompt => {
            snapshot.speaker.online = true;
            snapshot.speaker.status = "prompting".to_string();
        }
        CompanionV1ControlAction::SpeakerStop => {
            snapshot.speaker.status = "idle".to_string();
        }
        CompanionV1ControlAction::WakeArm => {
            snapshot.wake_word.armed = true;
        }
        CompanionV1ControlAction::WakeDisable => {
            snapshot.wake_word.armed = false;
            snapshot.wake_word.confidence = 0.0;
        }
        CompanionV1ControlAction::WakeTestDetect => {
            snapshot.wake_word.armed = true;
            snapshot.wake_word.last_detected_at = Some("fixture".to_string());
            snapshot.wake_word.confidence = 0.92;
        }
    }

    let message = request
        .session_id
        .as_deref()
        .or(request.prompt_id.as_deref())
        .map(|id| format!("fixture accepted ({id})"))
        .unwrap_or_else(|| "fixture accepted".to_string());

    snapshot.last_control = Some(CompanionV1ControlEcho {
        action: request.action,
        characteristic_uuid: characteristic_for_action(request.action),
        payload_hex: payload_hex(&request),
        accepted: true,
        message,
    });
    Ok(snapshot)
}

fn characteristic_for_action(action: CompanionV1ControlAction) -> &'static str {
    match action {
        CompanionV1ControlAction::StageBleName
        | CompanionV1ControlAction::ApplyBleName
        | CompanionV1ControlAction::ResetBleName => COMPANION_V1_GATT_BOUNDARY.ble_name_config_uuid,
        CompanionV1ControlAction::MeetingStart
        | CompanionV1ControlAction::MeetingStop
        | CompanionV1ControlAction::MeetingFinalize => COMPANION_V1_GATT_BOUNDARY.meeting_control_uuid,
        CompanionV1ControlAction::SpeakerPrompt | CompanionV1ControlAction::SpeakerStop => {
            COMPANION_V1_GATT_BOUNDARY.speaker_control_uuid
        }
        CompanionV1ControlAction::WakeArm
        | CompanionV1ControlAction::WakeDisable
        | CompanionV1ControlAction::WakeTestDetect => COMPANION_V1_GATT_BOUNDARY.wake_word_control_uuid,
    }
}

fn payload_hex(request: &CompanionV1ControlRequest) -> String {
    let mut bytes = vec![action_command(request.action)];
    if matches!(
        request.action,
        CompanionV1ControlAction::StageBleName
            | CompanionV1ControlAction::ApplyBleName
            | CompanionV1ControlAction::ResetBleName
    ) {
        bytes.push(COMPANION_V1_BLE_NAME_MAX_BYTES as u8);
        bytes.extend(
            request
                .ble_name
                .as_deref()
                .unwrap_or("")
                .as_bytes()
                .iter()
                .take(COMPANION_V1_BLE_NAME_MAX_BYTES),
        );
    }
    bytes.iter().map(|byte| format!("{byte:02x}")).collect()
}

fn action_command(action: CompanionV1ControlAction) -> u8 {
    match action {
        CompanionV1ControlAction::StageBleName
        | CompanionV1ControlAction::MeetingStart
        | CompanionV1ControlAction::SpeakerPrompt
        | CompanionV1ControlAction::WakeArm => 1,
        CompanionV1ControlAction::ApplyBleName
        | CompanionV1ControlAction::MeetingStop
        | CompanionV1ControlAction::SpeakerStop
        | CompanionV1ControlAction::WakeDisable => 2,
        CompanionV1ControlAction::ResetBleName
        | CompanionV1ControlAction::MeetingFinalize
        | CompanionV1ControlAction::WakeTestDetect => 3,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ble_name_policy_matches_firmware_contract() {
        assert!(companion_ble_name_is_valid("companion-v1"));
        assert!(companion_ble_name_is_valid("companion lab"));
        assert!(!companion_ble_name_is_valid(""));
        assert!(!companion_ble_name_is_valid("companion=lab"));
        assert!(!companion_ble_name_is_valid("companion-123456789012345678901"));
    }

    #[test]
    fn stage_ble_name_uses_settings_characteristic() {
        let snapshot = apply_fixture_control(CompanionV1ControlRequest {
            action: CompanionV1ControlAction::StageBleName,
            ble_name: Some("companion-v1".to_string()),
            session_id: None,
            prompt_id: None,
        })
        .unwrap();
        let echo = snapshot.last_control.unwrap();
        assert_eq!(echo.characteristic_uuid, COMPANION_V1_GATT_BOUNDARY.ble_name_config_uuid);
        assert!(echo.payload_hex.starts_with("011d"));
    }

    #[test]
    fn meeting_finalize_is_separate_state() {
        let snapshot = apply_fixture_control(CompanionV1ControlRequest {
            action: CompanionV1ControlAction::MeetingFinalize,
            ble_name: None,
            session_id: Some("meeting-1".to_string()),
            prompt_id: None,
        })
        .unwrap();
        assert_eq!(snapshot.meeting.status, "finalized");
        assert_eq!(snapshot.meeting.transcript_count, 1);
    }
}
