use super::*;

#[test]
fn user_sync_pause_survives_fresh_process_until_explicit_resume() {
    const DEVICE: &str = "AA:BB:CC:DD:EE:01";
    if let Ok(phase) = std::env::var("COMPANION_SYNC_PAUSE_TEST_PHASE") {
        match phase.as_str() {
            "pause" => {
                let job = Job::begin(DEVICE).unwrap();
                assert!(pause(&job.id).unwrap());
                assert!(job.is_paused());
                drop(job);
            }
            "paused" => {
                assert!(!automatic_allowed("aabbccddee01"), "restart must retain the user's Pause Sync choice");
                assert!(!owned_follow_allowed(DEVICE));
                assert!(automatic_allowed("AA:BB:CC:DD:EE:02"), "pause is per device");
                assert!(Job::begin(DEVICE).is_err());
                assert_eq!(status().unwrap().phase, "paused");
            }
            "resume" => {
                resume_explicit(Some(DEVICE)).unwrap();
                assert!(automatic_allowed(DEVICE));
            }
            "resumed" => {
                assert!(owned_follow_allowed(DEVICE));
                assert!(Job::begin(DEVICE).is_ok());
                assert_eq!(status().unwrap().phase, "idle");
            }
            _ => panic!("unexpected phase"),
        }
        return;
    }
    let root = std::env::temp_dir().join(format!("companion-sync-restart-{}", uuid::Uuid::new_v4()));
    std::fs::create_dir(&root).unwrap();
    for phase in ["pause", "paused", "resume", "resumed"] {
        let result = std::process::Command::new(std::env::current_exe().unwrap())
            .args(["--exact", "backend::recording_sync::restart_tests::user_sync_pause_survives_fresh_process_until_explicit_resume", "--nocapture"])
            .env("COMPANION_TYPE_STATE_PATH", root.join("sessions.json"))
            .env("COMPANION_SYNC_PAUSE_TEST_PHASE", phase)
            .env_remove("COMPANION_TYPE_DISABLE_AUTO_RECOVERY")
            .output().unwrap();
        assert!(result.status.success(), "phase {phase}: {} {}", String::from_utf8_lossy(&result.stdout), String::from_utf8_lossy(&result.stderr));
    }
    std::fs::remove_dir_all(root).unwrap();
}
