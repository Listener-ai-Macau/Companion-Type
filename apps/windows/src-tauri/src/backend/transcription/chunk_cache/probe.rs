//! Offline probe uses only a newly created caller-supplied folder and
//! controlled provider closures. It does not perform ASR or touch user data.
use super::{digest, load, resolve, store, Key, Profile, Utterance, MAX_ENTRY_BYTES};
use serde_json::{json, Value};
use std::{cell::Cell, fs, path::Path};

pub(in super::super) fn verify(output: &Path) -> Result<Value, String> {
    // Refuse existing paths before any reads/writes, including symlinks.
    fs::create_dir(output)
        .map_err(|_| "ASR cache probe requires a fresh, creatable output folder")?;
    let root = output.join("cache");
    let pcm = vec![0x31u8; 32_000];
    let configuration = json!({"provider": "controlled-offline-provider", "endpoint": "offline:test",
        "model": "model-a", "language": "auto", "account": "probe-account-no-secret",
        "resource": "resource-a", "payload": {"hotwords": ["probe-private-lexicon"]}});
    let profile = Profile::from_configuration(&configuration)?;
    let key = Key::new(&pcm, profile.clone())?;
    let path = key.path(&root)?;
    let calls = Cell::new(0);
    let provider = || {
        calls.set(calls.get() + 1);
        Ok((
            "Controlled final transcript".into(),
            vec![Utterance {
                text: "Controlled final transcript".into(),
                start_ms: 100,
                end_ms: 900,
                speaker: Some("speaker-7".into()),
            }],
        ))
    };
    let mut checks = Vec::new();
    let mut check = |name: &str, pass: bool| -> Result<(), String> {
        checks.push(json!({"name": name, "passed": pass}));
        if pass {
            Ok(())
        } else {
            Err(format!("ASR cache probe failed: {name}"))
        }
    };
    let first = resolve(&root, &key, provider)?;
    let second = resolve(&root, &key, provider)?;
    check(
        "same_pcm_and_configuration_reuses_final_result",
        first == second && calls.get() == 1,
    )?;
    check(
        "provider_timing_and_speaker_labels_roundtrip",
        second.1[0].start_ms == 100 && second.1[0].speaker.as_deref() == Some("speaker-7"),
    )?;
    for field in [
        "provider", "endpoint", "model", "language", "account", "resource", "payload",
    ] {
        let mut changed = configuration.clone();
        changed[field] = json!(format!("changed-{field}"));
        let changed_key = Key::new(&pcm, Profile::from_configuration(&changed)?)?;
        check(
            &format!("changed_{field}_misses"),
            load(&root, &changed_key).is_none(),
        )?;
    }
    let mut changed = profile;
    changed.processing_version = "future-processing".into();
    check(
        "processing_version_misses",
        load(&root, &Key::new(&pcm, changed)?).is_none(),
    )?;
    check(
        "changed_pcm_misses",
        load(
            &root,
            &Key::new(&vec![0x32u8; 32_000], key.profile.clone())?,
        )
        .is_none(),
    )?;
    let serialized = fs::read_to_string(&path).map_err(|_| "Cannot read probe cache entry")?;
    check(
        "no_account_hotwords_or_local_embeddings_persisted",
        !serialized.contains("probe-account-no-secret")
            && !serialized.contains("probe-private-lexicon")
            && !serialized.contains("embedding"),
    )?;
    let mut tampered: Value =
        serde_json::from_str(&serialized).map_err(|_| "Probe entry is not JSON")?;
    tampered["text"] = json!("Tampered but valid JSON");
    fs::write(&path, serde_json::to_vec(&tampered).unwrap())
        .map_err(|_| "Cannot write probe corruption")?;
    check("tampered_valid_json_misses", load(&root, &key).is_none())?;
    fs::write(&path, b"{interrupted").map_err(|_| "Cannot write probe truncation")?;
    let recovered = resolve(&root, &key, provider)?;
    check(
        "truncated_entry_retranscribes_and_repairs",
        calls.get() == 2 && recovered == first && load(&root, &key) == Some(first.clone()),
    )?;
    let oversized = fs::File::create(&path).map_err(|_| "Cannot create oversized probe entry")?;
    oversized
        .set_len(MAX_ENTRY_BYTES + 1)
        .map_err(|_| "Cannot size probe entry")?;
    drop(oversized);
    check("oversized_entry_misses", load(&root, &key).is_none())?;
    fs::remove_file(&path).map_err(|_| "Cannot reset probe entry")?;
    fs::write(
        root.join(format!("{}.json", digest(&pcm))),
        b"{\"schema\":\"companion-type.asr-chunk-cache.v1\",\"text\":\"legacy\"}",
    )
    .map_err(|_| "Cannot write probe legacy entry")?;
    check(
        "legacy_pcm_only_entry_is_not_reused",
        load(&root, &key).is_none(),
    )?;
    let legacy_root = output.join("previous-processing-cache");
    let mut legacy_profile = key.profile.clone();
    legacy_profile.processing_version = "pcm16k-mono-s16le-volc-final-v2".into();
    let legacy_key = Key::new(&pcm, legacy_profile)?;
    store(&legacy_root, &legacy_key, "Old partial wrongly accepted as final", &[])?;
    let before = calls.get();
    check("old_final_processing_cannot_reuse_partial_cache",
        resolve(&legacy_root, &key, provider)? == first && calls.get() == before + 1)?;
    let failed = resolve(&root, &key, || Err("Controlled provider failure".into()));
    check(
        "provider_failure_is_never_cached",
        failed.is_err() && !path.exists(),
    )?;
    let empty = resolve(&root, &key, || Ok((" \n ".into(), vec![])));
    check(
        "empty_success_is_never_cached",
        empty.is_err() && !path.exists(),
    )?;
    let invalid = vec![Utterance {
        text: "invalid timing".into(),
        start_ms: 4000,
        end_ms: 3000,
        speaker: None,
    }];
    check(
        "invalid_timing_is_never_cached",
        store(&root, &key, "invalid timing", &invalid).is_err() && !path.exists(),
    )?;
    let invalid = vec![Utterance {
        text: "outside audio".into(),
        start_ms: 100,
        end_ms: 3000,
        speaker: None,
    }];
    check(
        "outside_audio_timing_is_never_cached",
        store(&root, &key, "outside audio", &invalid).is_err() && !path.exists(),
    )?;
    let blocked = output.join("cache-root-is-a-file");
    fs::write(&blocked, b"file").map_err(|_| "Cannot create probe blocked root")?;
    check(
        "cache_write_failure_keeps_valid_provider_result",
        resolve(&blocked, &key, provider)? == first,
    )?;
    check(
        "failed_requests_are_retryable",
        resolve(&root, &key, provider)? == first && load(&root, &key) == Some(first),
    )?;
    let report = json!({"schema": "companion.type.local_asr_cache_probe.v1", "result": "PASS_LOCAL_ASR_CACHE_ONLY", "checks": checks,
        "realUserProfileAccess": false, "networkAccess": false, "deviceAccess": false,
        "trueAsrAcceptance": "NOT_RUN", "guiAcceptance": "NOT_RUN", "fullChainAcceptance": "NOT_RUN"});
    fs::write(
        output.join("result.json"),
        serde_json::to_vec_pretty(&report).unwrap(),
    )
    .map_err(|_| "Cannot save probe result")?;
    Ok(report)
}
