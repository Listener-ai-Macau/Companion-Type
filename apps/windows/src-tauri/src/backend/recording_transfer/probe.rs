use super::*;
use serde_json::{json, Value};
pub(crate) fn verify(output: &Path) -> Result<Value, String> {
    fs::create_dir(output)
        .map_err(|_| "Recording transfer probe requires a fresh output folder")?;
    let root = output.canonicalize().map_err(|_| fail())?;
    let body: Vec<u8> = (0..180_000).map(|n| (n % 239) as u8).collect();
    let sha = Sha256::digest(&body);
    let mut prefix = [0u8; 8];
    prefix.copy_from_slice(&sha[..8]);
    let source = Source {
        device: "fixture-device-a".into(),
        recording_id: 77,
        codec: 3,
        source_mode: 1,
        duration_ms: 90_000,
        total_length: body.len() as u32,
        sha256_prefix: prefix,
        content_crc32: crc32fast::hash(&body),
    };
    let mut checks = Vec::new();
    macro_rules! check {
        ($name:expr, $ok:expr) => {
            if !$ok {
                return Err(format!("transfer probe failed: {}", $name));
            }
            checks.push($name);
        };
    }
    let (mut cursor, initial) = Cursor::open(&root, source.clone())?;
    check!("fresh-empty", initial.is_empty());
    check!(
        "active-writer-refused",
        Cursor::open(&root, source.clone()).is_err()
    );
    cursor.append(&body[..70_000])?;
    // Simulate process death after a later write but before its journal flush.
    // The journal is real; dropping here has nothing new to checkpoint.
    drop(cursor);
    let part = path(&root, &source)?;
    OpenOptions::new()
        .append(true)
        .open(&part)
        .map_err(|_| fail())?
        .write_all(&body[70_000..80_000])
        .map_err(|_| fail())?;
    let (mut cursor, recovered) = Cursor::open(&root, source.clone())?;
    check!("recover-only-committed-prefix", recovered == body[..70_000]);
    check!(
        "discard-owned-uncommitted-tail",
        fs::metadata(&part).map_err(|_| fail())?.len() == 70_000
    );
    let mut other = source.clone();
    other.device = "fixture-device-b".into();
    let (other_cursor, other_initial) = Cursor::open(&root, other.clone())?;
    check!(
        "same-id-different-device-isolated",
        other_initial.is_empty() && path(&root, &other)? != part
    );
    drop(other_cursor);
    check!(
        "incomplete-cannot-consume",
        release(&root, other.clone()).is_err()
    );
    cursor.append(&body[70_000..])?;
    cursor.finish(&body)?;
    drop(cursor);
    let (complete, recovered) = Cursor::open(&root, source.clone())?;
    check!("complete-restart-reuses-verified-body", recovered == body);
    drop(complete);
    let mut changed = body.clone();
    changed[17] ^= 1;
    fs::write(&part, &changed).map_err(|_| fail())?;
    check!(
        "changed-prefix-refused",
        Cursor::open(&root, source.clone()).is_err()
    );
    check!(
        "changed-prefix-preserved",
        fs::read(&part).map_err(|_| fail())? == changed
    );
    check!(
        "changed-body-cannot-consume",
        release(&root, source.clone()).is_err()
    );
    fs::write(&part, &body).map_err(|_| fail())?;
    release(&root, source.clone())?;
    check!("verified-consume-removes-body", !part.exists());
    check!(
        "verified-consume-removes-private-receipt",
        !root
            .join(format!(".device-recording-{}.json", source.key()?))
            .exists()
    );
    release(&root, source.clone())?;
    checks.push("consume-idempotent");
    // Real durable release intent, interrupted before body or sidecar removal.
    let (mut cursor, _) = Cursor::open(&root, source.clone())?;
    cursor.append(&body)?;
    cursor.finish(&body)?;
    let mut releasing = cursor.receipt.clone();
    releasing.releasing = true;
    save(&cursor.receipt_path, &releasing)?;
    drop(cursor);
    release(&root, source.clone())?;
    check!("retry-durable-release-intent", !part.exists());
    fs::write(&part, b"unowned").map_err(|_| fail())?;
    check!(
        "unknown-cursor-not-adopted",
        Cursor::open(&root, source.clone()).is_err()
    );
    check!(
        "unknown-cursor-kept",
        fs::read(&part).map_err(|_| fail())? == b"unowned"
    );
    let receipt = root.join(format!(".device-recording-{}.json", other.key()?));
    fs::write(&receipt, b"{invalid}").map_err(|_| fail())?;
    check!(
        "corrupt-receipt-refused",
        Cursor::open(&root, other.clone()).is_err()
    );
    check!(
        "corrupt-receipt-kept",
        fs::read(&receipt).map_err(|_| fail())? == b"{invalid}"
    );
    let mut invalid = source.clone();
    invalid.total_length = u32::MAX;
    check!("oversize-refused", Cursor::open(&root, invalid).is_err());
    // Same in-process production attribution APIs; arbitrary fixture bytes only.
    struct Env(Option<std::ffi::OsString>);
    impl Drop for Env {
        fn drop(&mut self) {
            if let Some(v) = self.0.take() {
                std::env::set_var("COMPANION_TYPE_RECORDING_DIR", v);
            } else {
                std::env::remove_var("COMPANION_TYPE_RECORDING_DIR");
            }
        }
    }
    let _env = Env(std::env::var_os("COMPANION_TYPE_RECORDING_DIR"));
    std::env::set_var("COMPANION_TYPE_RECORDING_DIR", &root);
    let anchor = root.join("board-live-fixture.wav");
    let raw = root.join("board-live-fixture.cop1");
    let final_path = root.join("complete-fixture.wav");
    super::super::audio_artifacts::generated(
        &anchor,
        &raw,
        super::super::audio_artifacts::Purpose::LivePrefix,
        || fs::write(&raw, &body[..10_000]).map_err(|_| fail()),
    )?;
    groups::remember(&root, "fixture-device-a", 77, &anchor, &body[..10_000])?;
    groups::attach(&root, "fixture-device-b", 77, &body, &final_path)?;
    let groups_path = root.join(".board-live-groups.json");
    check!(
        "prefix-other-device-kept",
        serde_json::from_slice::<Value>(&fs::read(&groups_path).map_err(|_| fail())?)
            .map_err(|_| fail())?["prefixes"]
            .as_array()
            .unwrap()
            .len()
            == 1
    );
    groups::attach(&root, "fixture-device-a", 77, &changed, &final_path)?;
    check!(
        "reused-id-wrong-prefix-kept",
        serde_json::from_slice::<Value>(&fs::read(&groups_path).map_err(|_| fail())?)
            .map_err(|_| fail())?["prefixes"]
            .as_array()
            .unwrap()
            .len()
            == 1
    );
    groups::attach(&root, "fixture-device-a", 77, &body, &final_path)?;
    let references = super::super::audio_artifacts::source_references(&raw)?;
    check!(
        "verified-prefix-rebound-after-journal-reload",
        references.contains(&super::super::audio_artifacts::reference_key(&final_path)?)
    );
    check!(
        "bound-prefix-intent-retired",
        serde_json::from_slice::<Value>(&fs::read(&groups_path).map_err(|_| fail())?)
            .map_err(|_| fail())?["prefixes"]
            .as_array()
            .unwrap()
            .is_empty()
    );
    let report = json!({"schema":"companion.recording-transfer.probe.v1", "result":"PASS_LOCAL_TRANSFER_ONLY",
        "checks":checks,"checkCount":checks.len(),"hardware":"NOT_RUN","actualProcessDeath":"NOT_RUN",
        "powerLoss":"NOT_RUN","gattResume":"NOT_RUN","fullChain":"NOT_RUN"});
    super::super::export::write_atomic(
        &root.join("result.json"),
        &serde_json::to_vec_pretty(&report).map_err(|_| fail())?,
    )?;
    Ok(report)
}
#[cfg(test)]
mod tests {
    #[test]
    fn durable_device_bound_cursor_contract() {
        let root = std::env::temp_dir().join(format!(
            "companion-transfer-{}",
            uuid::Uuid::new_v4().simple()
        ));
        let report = super::verify(&root).unwrap();
        assert_eq!(report["result"], "PASS_LOCAL_TRANSFER_ONLY");
        assert!(super::verify(&root).is_err());
    }
}
