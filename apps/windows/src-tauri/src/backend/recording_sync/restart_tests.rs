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

#[test]
fn damaged_sync_choice_allows_only_an_explicit_one_device_job_across_restart() {
    const DEVICE: &str = "AA:BB:CC:DD:EE:01";
    const OTHER: &str = "AA:BB:CC:DD:EE:02";
    if let Ok(phase) = std::env::var("COMPANION_DAMAGED_SYNC_TEST_PHASE") {
        assert_eq!(status().unwrap().phase, "blocked");
        assert!(!automatic_allowed(DEVICE));
        assert!(!automatic_allowed(OTHER));
        assert!(Job::begin(DEVICE).is_err());
        if phase == "manual" {
            resume_explicit(Some(DEVICE)).unwrap();
            assert!(!automatic_allowed(DEVICE));
            assert!(Job::begin_background(DEVICE).is_err());
            assert!(Job::begin(OTHER).is_err());
            let job = Job::begin(DEVICE).unwrap();
            // Exercise the actual durable prefix under the admitted job, not
            // just the status switch; an interrupted transfer can resume it.
            use super::super::recording_transfer::{Cursor, Source};
            use sha2::{Digest, Sha256};
            let body:Vec<u8>=(0..100_000).map(|n|(n%239) as u8).collect();
            let digest=Sha256::digest(&body);let mut prefix=[0;8];prefix.copy_from_slice(&digest[..8]);
            let source=Source {device:DEVICE.into(),recording_id:7,codec:3,source_mode:1,
                duration_ms:90_000,total_length:body.len() as u32,sha256_prefix:prefix,content_crc32:crc32fast::hash(&body)};
            let root=std::path::PathBuf::from(std::env::var_os("COMPANION_TYPE_STATE_PATH").unwrap());
            let data=root.parent().unwrap().join("manual-cursor");std::fs::create_dir(&data).unwrap();
            let (mut cursor,_)=Cursor::open(&data,source.clone()).unwrap();
            cursor.append(&body[..65_536]).unwrap();job.recording(7,body.len() as u32);job.received(65_536);
            drop(cursor);let (cursor,recovered)=Cursor::open(&data,source).unwrap();
            assert_eq!(recovered,body[..65_536]);drop(cursor);
            assert_eq!(status().unwrap().received_bytes,65_536);
            drop(job);
            assert!(Job::begin(DEVICE).is_err(), "one explicit action admits one manual job");
            assert_eq!(status().unwrap().phase, "blocked");
        } else { assert_eq!(phase, "restart"); }
        return;
    }
    let root = std::env::temp_dir().join(format!("companion-sync-damaged-{}", uuid::Uuid::new_v4()));
    std::fs::create_dir(&root).unwrap();
    let preference = root.join("recording-sync.json");
    let damaged = b"{incomplete choice";
    std::fs::write(&preference, damaged).unwrap();
    for phase in ["manual", "restart"] {
        let result = std::process::Command::new(std::env::current_exe().unwrap())
            .args(["--exact", "backend::recording_sync::restart_tests::damaged_sync_choice_allows_only_an_explicit_one_device_job_across_restart", "--nocapture"])
            .env("COMPANION_TYPE_STATE_PATH", root.join("sessions.json"))
            .env("COMPANION_DAMAGED_SYNC_TEST_PHASE", phase)
            .env_remove("COMPANION_TYPE_DISABLE_AUTO_RECOVERY")
            .output().unwrap();
        assert!(result.status.success(), "phase {phase}: {} {}", String::from_utf8_lossy(&result.stdout), String::from_utf8_lossy(&result.stderr));
        assert_eq!(std::fs::read(&preference).unwrap(), damaged);
    }
    std::fs::remove_dir_all(root).unwrap();
}
