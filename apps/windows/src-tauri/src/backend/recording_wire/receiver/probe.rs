use super::*;
use serde_json::{json, Value};
const DEVICE: &str = "A1:B2:C3:D4:E5:F6";
struct Environment(Option<std::ffi::OsString>);
impl Environment {
    fn isolate(root: &Path) -> Self {
        let old = std::env::var_os("COMPANION_TYPE_RECORDING_DIR");
        std::env::set_var("COMPANION_TYPE_RECORDING_DIR", root);
        Self(old)
    }
}
impl Drop for Environment {
    fn drop(&mut self) {
        match self.0.take() {
            Some(v) => std::env::set_var("COMPANION_TYPE_RECORDING_DIR", v),
            None => std::env::remove_var("COMPANION_TYPE_RECORDING_DIR"),
        }
    }
}
fn fixture() -> (Vec<Descriptor>, Vec<u8>) {
    let mut p = b"COP1\x01\x01\x14\x00\x80\x3e\x00\x00".to_vec();
    for _ in 0..3 {
        p.extend_from_slice(&[3, 0, 0xf8, 0xff, 0xfe]);
    }
    let key = super::super::SessionKey {
        device_uid: [0x35; 12],
        format_epoch: 0xC055AA0710123456,
        session_id: 23,
    };
    let ds = (0..3)
        .map(|n| Descriptor {
            key: key.clone(),
            recording_id: 901 + n,
            segment_index: n,
            sample_offset: u64::from(n) * 960,
            sample_count: 960,
            encoded_length: p.len() as u32,
            content_crc32: crc32fast::hash(&p),
            sha256: Sha256::digest(&p).into(),
            total_segments: if n == 2 { 3 } else { 0 },
            flags: if n == 2 { 3 } else { 1 },
            codec: 3,
            source_mode: 1,
            sync_state: 0,
        })
        .collect();
    (ds, p)
}
pub(crate) fn phase(output: &Path, phase: &str) -> Result<Value, String> {
    let root = output.canonicalize().map_err(|_| fail())?;
    let (ds, payload) = fixture();
    let wire = ds[2].encode()?;
    let _env = Environment::isolate(&root);
    if phase == "locked" {
        if Receiver::open(&root, &wire).is_ok() {
            return Err("active receiver lock was bypassed".into());
        }
        return Ok(json!({"result":"PASS_SOFTWARE_ACTIVE_WRITER_REFUSED"}));
    }
    if phase == "body-before-receipt" {
        let r = Receiver::open(&root, &wire)?;
        let first = r.payload_path(&ds[0]);
        audio_artifacts::generated_pinned(
            r._usage.as_ref(),
            &r.audio_path(),
            &first,
            audio_artifacts::Purpose::CompressedOriginal,
            || export::write_atomic(&first, &payload).map(|_| ()),
        )?;
        if !cfg!(test) {
            std::mem::forget(r);
        } // Installed CLI exits without Drop/receipt commit.
        return Ok(
            json!({"result":"PASS_SOFTWARE_BODY_BEFORE_RECEIPT","abruptChildExit":!cfg!(test)}),
        );
    }
    if phase != "partial" {
        return Err(fail());
    }
    let mut r = Receiver::open(&root, &wire)?;
    let plan = r.plan()?;
    if plan.missing_segments != vec![1]
        || plan.verified_segments != 2
        || plan.payloads_complete
        || r.audio_path().exists()
    {
        return Err(fail());
    }
    if r.ack_candidates(&root.join("sessions.json"))?.len() != 2 {
        return Err(fail());
    }
    Ok(
        json!({"result":"PASS_SOFTWARE_PROCESS_REOPEN_ONLY","missing":[1],"verifiedSegments":2,"syntheticAudio":true,"hardware":"NOT_RUN"}),
    )
}
fn child(root: &Path, phase: &str) -> Result<Value, String> {
    if cfg!(test) {
        return self::phase(root, phase);
    }
    let child = std::process::Command::new(std::env::current_exe().map_err(|_| fail())?)
        .args(["--recording-session-probe-phase"])
        .arg(root)
        .arg(phase)
        .output()
        .map_err(|_| fail())?;
    let stdout = String::from_utf8(child.stdout).map_err(|_| fail())?;
    let stderr = String::from_utf8_lossy(&child.stderr);
    if !child.status.success() {
        return Err(format!("child phase {phase} failed: {stderr}"));
    }
    let result = stdout
        .lines()
        .find_map(|s| s.strip_prefix("recording_session_phase_json="))
        .ok_or_else(fail)?;
    serde_json::from_str(result).map_err(|_| fail())
}
pub(crate) fn verify(output: &Path) -> Result<Value, String> {
    fs::create_dir(output)
        .map_err(|_| "Recording session probe requires a fresh output folder".to_string())?;
    let root = output.canonicalize().map_err(|_| fail())?;
    let _env = Environment::isolate(&root);
    let (ds, payload) = fixture();
    let wires = ds
        .iter()
        .map(Descriptor::encode)
        .collect::<Result<Vec<_>, _>>()?;
    let index = root.join("sessions.json");
    let mut checks = Vec::new();
    macro_rules! check {
        ($label:expr,$ok:expr) => {
            if !$ok {
                return Err(format!("session probe failed: {}", $label));
            }
            checks.push($label);
        };
    }
    let mut r = Receiver::open(&root, &wires[2])?;
    check!(
        "empty-directory-has-missing-first-and-middle",
        r.plan()?.missing_segments == vec![0, 1]
    );
    check!(
        "receipt-cannot-authorize-ack-before-library",
        r.ack_candidates(&index).is_err()
    );
    check!(
        "unreceived-descriptor-cannot-accept-ack",
        r.confirm_acked(&super::publish::ack(&ds[2])).is_err()
    );
    let locked = child(&root, "locked")?;
    check!(
        "exclusive-session-lease-across-processes",
        locked["result"] == "PASS_SOFTWARE_ACTIVE_WRITER_REFUSED"
    );
    r.accept_segment(&wires[2], &payload)?;
    r.accept_metadata(&wires[0])?;
    // A durable body can precede its final received bit. The declared ownership
    // and full content identity, rather than a matching filename, recover it.
    let first = r.payload_path(&ds[0]);
    check!(
        "body-after-intent-before-receipt",
        !r.receipt.segments[0].received
    );
    drop(r);
    let interrupted = child(&root, "body-before-receipt")?;
    check!(
        "child-body-flushed-without-received-checkpoint",
        interrupted["result"] == "PASS_SOFTWARE_BODY_BEFORE_RECEIPT"
    );
    let mut r = Receiver::open(&root, &wires[0])?;
    r.publish(&index, DEVICE)?;
    check!(
        "verified-body-adopted-by-exact-intent",
        r.plan()?.verified_segments == 2
    );
    let partial: Vec<crate::companion_v1::CompanionV1HostSession> =
        serde_json::from_slice(&fs::read(&index).map_err(|_| fail())?).map_err(|_| fail())?;
    check!(
        "incomplete-library-discoverable-without-asr",
        partial.len() == 1
            && !partial[0].audio_stored
            && partial[0].pending_reason.as_deref() == Some("needs_segments")
            && partial[0].recovery.intent == "none"
    );
    check!(
        "partial-library-permits-only-received-physical-acks",
        r.ack_candidates(&index)?.len() == 2
    );
    check!("missing-segment-cannot-be-assembled", r.assemble().is_err());
    let body_hash = digest(read_locked(&first)?)?;
    check!(
        "duplicate-payload-idempotent",
        r.accept_segment(&wires[0], &payload).is_ok() && digest(read_locked(&first)?)? == body_hash
    );
    let mut conflict = ds[0].clone();
    conflict.recording_id += 100;
    check!(
        "conflicting-physical-id-refused",
        r.accept_metadata(&conflict.encode()?).is_err()
    );
    let mut foreign = ds[1].clone();
    foreign.key.format_epoch += 1;
    check!(
        "foreign-format-epoch-refused",
        r.accept_metadata(&foreign.encode()?).is_err()
    );
    foreign = ds[1].clone();
    foreign.key.device_uid[0] += 1;
    check!(
        "foreign-device-uid-refused",
        r.accept_metadata(&foreign.encode()?).is_err()
    );
    foreign = ds[1].clone();
    foreign.key.session_id += 1;
    check!(
        "foreign-session-refused",
        r.accept_metadata(&foreign.encode()?).is_err()
    );
    let mut gap = ds[1].clone();
    gap.sample_offset += 320;
    check!(
        "metadata-sample-gap-refused",
        r.accept_metadata(&gap.encode()?).is_err()
    );
    let mut bad = payload.clone();
    bad[14] ^= 1;
    check!(
        "wrong-full-payload-hash-refused",
        r.accept_segment(&wires[1], &bad).is_err()
    );
    let mut mode = ds[1].clone();
    mode.source_mode = 2;
    check!(
        "mixed-meeting-mode-refused",
        r.accept_metadata(&mode.encode()?).is_err()
    );
    drop(r);
    let reopened = child(&root, "partial")?;
    check!(
        "process-reopen-keeps-missing-segment-and-two-receipts",
        reopened["verifiedSegments"] == 2
    );
    let mut r = Receiver::open(&root, &wires[0])?;
    r.accept_segment(&wires[1], &payload)?;
    check!(
        "out-of-order-payloads-complete-only-after-middle",
        r.plan()?.payloads_complete
    );
    let audio = r.assemble()?;
    let assembled = fs::read(&audio).map_err(|_| fail())?;
    let mut joined = payload[..12].to_vec();
    for _ in 0..3 {
        joined.extend_from_slice(&payload[12..]);
    }
    let reference = root.join("reference.cop1");
    let wav = root.join("reference.wav");
    fs::write(&reference, joined).map_err(|_| fail())?;
    crate::backend::audio_decode::decode_recording(&reference, &wav, false)?;
    check!(
        "one-decoder-one-preskip-matches-unsegmented-cop1",
        assembled == fs::read(&wav).map_err(|_| fail())? && assembled.len() == 44 + 8 * 320 * 2
    );
    check!(
        "assembly-retry-is-byte-for-byte-idempotent",
        r.assemble()? == audio && fs::read(&audio).map_err(|_| fail())? == assembled
    );
    r.publish(&index, DEVICE)?;
    let library: Vec<crate::companion_v1::CompanionV1HostSession> =
        serde_json::from_slice(&fs::read(&index).map_err(|_| fail())?).map_err(|_| fail())?;
    check!(
        "complete-library-keeps-local-only-card-processing-policy",
        library.len() == 1
            && library[0].audio_stored
            && library[0].processing_policy == crate::backend::product_settings::new_card_processing_policy()
            && (library[0].processing_policy == crate::companion_v1::CompanionV1ProcessingPolicy::Manual
                || library[0].recovery.intent == "processMeeting")
            && library[0].chunks.len() == 4
    );
    check!(
        "v2-row-cannot-authorize-legacy-id-only-delete",
        library[0].device_recording_id.is_none() && library[0].device_sha256.is_none()
    );
    let acks = r.ack_candidates(&index)?;
    check!(
        "exact-84-byte-ack-for-each-sealed-segment",
        acks.len() == 3 && acks.iter().all(|a| a.len() == ACK_BYTES)
    );
    let mut wrong = acks[0].clone();
    wrong[48] ^= 1;
    let crc = crc32fast::hash(&wrong[..80]);
    wrong[80..].copy_from_slice(&crc.to_le_bytes());
    check!(
        "valid-crc-wrong-sha-ack-refused",
        r.confirm_acked(&wrong).is_err()
    );
    wrong = acks[0].clone();
    wrong[8] ^= 1;
    let crc = crc32fast::hash(&wrong[..80]);
    wrong[80..].copy_from_slice(&crc.to_le_bytes());
    check!(
        "valid-crc-wrong-uid-ack-refused",
        r.confirm_acked(&wrong).is_err()
    );
    r.confirm_acked(&acks[0])?;
    r.confirm_acked(&acks[0])?;
    check!(
        "ack-confirmation-idempotent-with-remaining-retries",
        r.ack_candidates(&index)?.len() == 2
    );
    let expected_path = audio.clone();
    drop(r);
    let mut r = Receiver::open(&root, &wires[2])?;
    check!(
        "confirmed-ack-survives-reopen",
        r.ack_candidates(&index)?.len() == 2 && r.assemble()? == expected_path
    );
    let mut changed = fs::read(&first).map_err(|_| fail())?;
    changed[14] ^= 1;
    fs::write(&first, &changed).map_err(|_| fail())?;
    check!(
        "changed-received-body-cannot-produce-ack",
        r.ack_candidates(&index).is_err()
    );
    fs::write(&first, &payload).map_err(|_| fail())?;
    check!(
        "restoring-exact-original-allows-resume",
        r.plan()?.payloads_complete
    );
    let before = fs::read(&index).map_err(|_| fail())?;
    check!(
        "different-native-device-rejected-before-index-write",
        r.publish(&index, "11:22:33:44:55:66").is_err()
            && fs::read(&index).map_err(|_| fail())? == before
    );
    let mut conflicting = library.clone();
    conflicting[0].audio_path = Some(root.join("foreign.wav").to_string_lossy().into_owned());
    let collision = serde_json::to_vec_pretty(&conflicting).map_err(|_| fail())?;
    fs::write(&index, &collision).map_err(|_| fail())?;
    fs::write(index.with_file_name("sessions.json.bak"), &collision).map_err(|_| fail())?;
    check!(
        "rejected-library-merge-preserves-both-copies",
        r.publish(&index, DEVICE).is_err()
            && fs::read(&index).map_err(|_| fail())? == collision
            && fs::read(index.with_file_name("sessions.json.bak")).map_err(|_| fail())?
                == collision
    );
    fs::write(&index, &before).map_err(|_| fail())?;
    fs::write(index.with_file_name("sessions.json.bak"), &before).map_err(|_| fail())?;
    // Both copies can be temporarily unavailable; owned bytes stay intact.
    fs::write(&index, b"invalid-json").map_err(|_| fail())?;
    fs::write(index.with_file_name("sessions.json.bak"), b"invalid-json").map_err(|_| fail())?;
    check!(
        "corrupt-library-refuses-ack",
        r.ack_candidates(&index).is_err()
    );
    fs::write(&index, &before).map_err(|_| fail())?;
    fs::write(index.with_file_name("sessions.json.bak"), &before).map_err(|_| fail())?;
    check!(
        "library-restored-without-losing-wav",
        fs::read(&audio).map_err(|_| fail())? == assembled && r.ack_candidates(&index)?.len() == 2
    );
    let receipt_path = r.receipt_path();
    drop(r);
    let receipt = fs::read(&receipt_path).map_err(|_| fail())?;
    fs::write(&receipt_path, b"broken-receipt").map_err(|_| fail())?;
    check!(
        "corrupt-receipt-protected-no-audio-rewrite",
        Receiver::open(&root, &wires[0]).is_err()
            && fs::read(&audio).map_err(|_| fail())? == assembled
    );
    let mut duplicated: Receipt = serde_json::from_slice(&receipt).map_err(|_| fail())?;
    duplicated.segments.push(duplicated.segments[0].clone());
    fs::write(
        &receipt_path,
        serde_json::to_vec(&duplicated).map_err(|_| fail())?,
    )
    .map_err(|_| fail())?;
    check!(
        "duplicate-persisted-segment-refused",
        Receiver::open(&root, &wires[0]).is_err()
    );
    fs::write(&receipt_path, &receipt).map_err(|_| fail())?;
    let mut r = Receiver::open(&root, &wires[0])?;
    let original = digest(read_locked(&first)?)?;
    check!("reading-body-handle-denies-write-and-delete", {
        let guard = read_locked(&first)?;
        #[cfg(windows)]
        let denied = OpenOptions::new().write(true).open(&first).is_err()
            && fs::remove_file(&first).is_err();
        #[cfg(not(windows))]
        let denied = true;
        drop(guard);
        denied
    });
    check!(
        "body-unchanged-after-lock-negative",
        digest(read_locked(&first)?)? == original
    );
    for ack in r.ack_candidates(&index)? {
        r.confirm_acked(&ack)?;
    }
    r.publish(&index, DEVICE)?;
    check!(
        "all-device-receipts-durable-with-host-originals-retained",
        r.ack_candidates(&index)?.is_empty()
            && r.receipt.segments.iter().all(|s| s.acked)
            && first.exists()
            && audio.exists()
    );
    let selected = vec![audio.to_string_lossy().into_owned()];
    check!(
        "privacy-cannot-delete-active-session-or-sidecars",
        audio_artifacts::erase(&root, &selected, &[]).is_err()
            && first.exists()
            && audio.exists()
            && receipt_path.exists()
    );
    drop(r);
    let deleted = audio_artifacts::erase(&root, &selected, &[])?;
    check!(
        "explicit-session-erase-includes-segments-and-receipt",
        deleted.deleted >= 5
            && !first.exists()
            && !audio.exists()
            && !receipt_path.exists()
            && reference.exists()
            && wav.exists()
    );
    session_store::update(&index, |rows| rows.clear())?;
    check!(
        "privacy-index-backup-cannot-resurrect-session",
        fs::read(&index).map_err(|_| fail())?
            == fs::read(index.with_file_name("sessions.json.bak")).map_err(|_| fail())?
    );
    let report = json!({"result":"PASS_LOCAL_SESSION_RECEIVER_SOFTWARE_ONLY","checks":checks,"syntheticAudio":true,
        "actualChildProcessReopen":!cfg!(test),"actualChildProcessWriterExclusion":!cfg!(test),"actualChildAbruptExitBeforeReceipt":!cfg!(test),"radioV2Enabled":false,
        "deviceContact":false,"captureContinuity":"NOT_RUN","physicalPowerLoss":"NOT_RUN","nativeGui":"NOT_RUN","trueAsr":"NOT_RUN","fullChain":"NOT_RUN"});
    fs::write(
        root.join("result.json"),
        serde_json::to_vec_pretty(&report).map_err(|_| fail())?,
    )
    .map_err(|_| fail())?;
    Ok(report)
}
#[cfg(test)]
mod tests {
    // Both diagnostics change one process-wide directory. Serialize the outer
    // tests, not nested verify()/phase() calls or unrelated receiver tests.
    static RECORDING_ENV:std::sync::Mutex<()>=std::sync::Mutex::new(());
    #[test]
    fn sealed_segment_acks_do_not_claim_the_whole_growing_session_is_reclaimed() {
        let _environment=RECORDING_ENV.lock().unwrap_or_else(|e|e.into_inner());
        use super::*;
        let root = std::env::temp_dir().join(format!("companion-open-reclaim-{}", uuid::Uuid::new_v4()));
        fs::create_dir_all(&root).unwrap();
        let root = root.canonicalize().unwrap();
        let _env = Environment::isolate(&root);
        let (ds, payload) = fixture();
        let index = root.join("sessions.json");
        let row = || serde_json::from_slice::<Vec<crate::companion_v1::CompanionV1HostSession>>(&fs::read(&index).unwrap()).unwrap().remove(0);
        let mut r = Receiver::open(&root, &ds[0].encode().unwrap()).unwrap();
        r.accept_segment(&ds[0].encode().unwrap(), &payload).unwrap();
        r.publish(&index, DEVICE).unwrap();
        for ack in r.ack_candidates(&index).unwrap() { r.confirm_acked(&ack).unwrap(); }
        r.publish(&index, DEVICE).unwrap();
        assert!(!row().device_reclaimed, "first sealed segment is consumed, but the session has no LAST");
        assert!(!row().audio_stored);
        drop(r);
        let mut r = Receiver::open(&root, &ds[0].encode().unwrap()).unwrap();
        r.publish(&index, DEVICE).unwrap();
        assert!(!row().device_reclaimed, "reopening does not restore the premature whole-session flag");
        r.accept_segment(&ds[2].encode().unwrap(), &payload).unwrap();
        r.publish(&index, DEVICE).unwrap();
        for ack in r.ack_candidates(&index).unwrap() { r.confirm_acked(&ack).unwrap(); }
        r.publish(&index, DEVICE).unwrap();
        assert!(!row().device_reclaimed, "known LAST and all known ACKs cannot hide a missing middle segment");
        r.accept_metadata(&ds[1].encode().unwrap()).unwrap();
        r.publish(&index, DEVICE).unwrap();
        assert!(!row().device_reclaimed, "complete metadata is insufficient without durable payload and physical ACK");
        r.accept_segment(&ds[1].encode().unwrap(), &payload).unwrap();
        r.assemble().unwrap();
        session_store::update_checked(&index, |rows| {
            rows[0].capture_incomplete=true;Ok(())
        }).unwrap();
        r.publish(&index, DEVICE).unwrap();
        assert!(row().audio_stored);
        assert!(row().capture_incomplete, "complete received payload cannot erase an earlier interruption warning");
        assert_eq!(row().recovery.stage,"paused");
        assert_eq!(row().pending_reason.as_deref(),Some("capture_interrupted"));
        assert!(!row().device_reclaimed, "complete local audio still needs the last physical receipt");
        for ack in r.ack_candidates(&index).unwrap() { r.confirm_acked(&ack).unwrap(); }
        r.publish(&index, DEVICE).unwrap();
        assert!(row().device_reclaimed && row().audio_stored);
        let completed = row();
        drop(r);
        Receiver::verify_completed_row(&completed).unwrap();
        let temp = std::env::temp_dir().canonicalize().unwrap();
        assert!(root.starts_with(temp) && root.file_name().unwrap().to_string_lossy().starts_with("companion-open-reclaim-"));
        fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn durable_receiver_missing_reordered_restart_and_exact_ack() {
        let _environment=RECORDING_ENV.lock().unwrap_or_else(|e|e.into_inner());
        let root = std::env::temp_dir().join(format!(
            "companion-session-receiver-{}",
            uuid::Uuid::new_v4()
        ));
        let r = super::verify(&root).unwrap();
        assert_eq!(r["result"], "PASS_LOCAL_SESSION_RECEIVER_SOFTWARE_ONLY");
        assert!(super::verify(&root).is_err());
        std::fs::remove_dir_all(root).unwrap();
    }
}
