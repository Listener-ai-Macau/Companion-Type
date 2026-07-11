//! Companion coordinator.
//!
//! Single owner of the Companion host workflow. The current backend is a
//! deterministic fixture, but the public methods are the same surface the real
//! BLE/audio/ASR backend will implement.

use std::sync::Arc;

use crate::backend::{
    CompanionBackend, CompanionBackendCapabilities, CompanionBleBridgeStatus,
    CompanionFirmwareOtaReport, CompanionFirmwareOtaRequest, FixtureCompanionBackend,
};
use crate::companion_v1::{CompanionV1ControlRequest, CompanionV1Snapshot};

pub struct CompanionCoordinator {
    backend: Arc<dyn CompanionBackend>,
}

impl CompanionCoordinator {
    pub fn new_fixture() -> Self {
        Self {
            backend: Arc::new(FixtureCompanionBackend::new()),
        }
    }

    pub fn snapshot(&self) -> Result<CompanionV1Snapshot, String> {
        self.backend.snapshot()
    }

    pub fn apply_control(
        &self,
        request: CompanionV1ControlRequest,
    ) -> Result<CompanionV1Snapshot, String> {
        self.backend.apply_control(request)
    }

    pub fn backend_capabilities(&self) -> CompanionBackendCapabilities {
        self.backend.capabilities()
    }

    pub fn ble_bridge_status(&self) -> CompanionBleBridgeStatus {
        self.backend.ble_bridge_status()
    }

    pub fn transfer_firmware_ota(
        &self,
        request: CompanionFirmwareOtaRequest,
    ) -> Result<CompanionFirmwareOtaReport, String> {
        self.backend.transfer_firmware_ota(request)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::companion_v1::CompanionV1ControlAction;

    #[test]
    fn coordinator_owns_backend_state() {
        let coordinator = CompanionCoordinator::new_fixture();
        let initial = coordinator.snapshot().unwrap();
        assert_eq!(initial.host.sessions.len(), 0);

        coordinator
            .apply_control(CompanionV1ControlRequest {
                action: CompanionV1ControlAction::MeetingStart,
                ble_name: None,
                session_id: None,
                prompt_id: None,
                title: Some("Coordinator chain".to_string()),
                transcript_text: None,
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            })
            .unwrap();

        let next = coordinator.snapshot().unwrap();
        assert_eq!(next.host.sessions.len(), 1);
        assert_eq!(next.host.sessions[0].title, "Coordinator chain");
    }
}
