//! Explicit synthetic transport diagnostics. The product's microphone-only
//! sync/consume path remains separate and unchanged. Uses its native encrypted
//! connection, negotiated directory, batch interval, queues and packet parser.
use super::*;
use crate::backend::recording_wire::{Descriptor, SessionKey};

#[derive(serde::Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Sample {
    synthetic: bool,
    device_uid: String,
    format_epoch: String,
    session_id: String,
    recording_id: u32,
    bytes: u32,
    sha256: String,
}

impl Sample {
    fn identity(&self) -> Result<(SessionKey, [u8; 32]), String> {
        if !self.synthetic || self.recording_id == 0 || !(524288..=64*1024*1024).contains(&self.bytes) {
            return Err("upload benchmark requires an explicit synthetic sealed sample >=512KiB".into());
        }
        let key = SessionKey::from_public(&crate::companion_v1::CompanionV1RecordingKey {
            device_uid: self.device_uid.clone(), format_epoch: self.format_epoch.clone(),
            session_id: self.session_id.clone(),
        })?;
        Ok((key, parse_sha256_hex(&self.sha256)?))
    }

    fn matches(&self, d: &Descriptor) -> Result<(), String> {
        let (key, sha) = self.identity()?;
        if d.key != key || d.recording_id != self.recording_id || d.sha256 != sha
            || d.encoded_length != self.bytes || d.source_mode != 2 || d.codec != 3
            || d.flags != 3 || d.segment_index != 0 || d.total_segments != 1 || d.sample_offset != 0 {
            return Err("upload benchmark identity/length/SHA/source/sealed boundary differs; no payload or consume".into());
        }
        Ok(())
    }
}

fn validate_profiles(profiles: Option<&[u16]>) -> Result<(), String> {
    if let Some(profiles) = profiles {
        if !(2..=3).contains(&profiles.len()) || profiles.iter().any(|p|!matches!(p,219|244|495|509)) {
            return Err("same-link benchmark requires two or three profiles from 219,244,495,509".into());
        }
    }
    Ok(())
}

#[derive(Clone,Copy,PartialEq)]
enum FixtureConnectionPath { Sealed, NormalThenSealed }
impl FixtureConnectionPath {
    fn parse(value: Option<&str>) -> Result<Self,String> {
        match value.map(str::trim) {
            None | Some("") | Some("sealed") => Ok(Self::Sealed),
            Some("normal_then_sealed") => Ok(Self::NormalThenSealed),
            _ => Err("invalid explicit synthetic benchmark connection path; no BLE operation".into()),
        }
    }
    fn name(self) -> &'static str {
        match self { Self::Sealed=>"sealed",Self::NormalThenSealed=>"normal_then_sealed" }
    }
    fn from_env() -> Result<Self,String> {
        match std::env::var("COMPANION_TYPE_BLE_BENCHMARK_CONNECTION_PATH") {
            Ok(value)=>Self::parse(Some(&value)),
            Err(std::env::VarError::NotPresent)=>Self::parse(None),
            Err(_)=>Err("non-Unicode synthetic benchmark connection path; no BLE operation".into()),
        }
    }
}

async fn connect_fixture(device_id:&str,path:FixtureConnectionPath) -> Result<NativeConnectionSetup,String> {
    if path==FixtureConnectionPath::Sealed {
        return connect_native_device_setup_with_intent(Some(device_id),false,ConnectionIntent::SealedSync).await;
    }
    // Exercise the real normal preference/discovery path, then the real sealed
    // path on its retained session. Clock writes and recording START are not
    // part of this explicit synthetic experiment. No second physical connect.
    let normal=connect_native_device_setup_with_intent(Some(device_id),false,ConnectionIntent::Normal).await?;
    #[cfg(windows)]
    drop(normal.preference);
    let retained=normal.device;
    eprintln!("recording_benchmark_connection_path stage=normal_setup_complete path={} retained_session=1 clock_sync=0 reconnect_allowed=0",path.name());
    let warm=connect_known_native_device_setup_guarded(retained.clone(),false,ConnectionIntent::SealedSync,true).await;
    match warm {
        Ok(setup)=>Ok(setup),
        Err(error)=>combine_operation_and_cleanup(Err(error),disconnect_native_device(&retained).await),
    }
}

// Diagnostic-only pause before any batch/payload, so the harness can take one
// admitted UART setup snapshot. It cannot change the production sync path or
// exclude backpressure from an already-started payload speed window.
async fn capture_setup_barrier(output: &Path) -> Result<u128, String> {
    let token = segmented::nonce();
    let ready = serde_json::json!({"schema":"companion.setup-snapshot.v1",
        "token":token,"payloadStarted":false,"maximumWaitMs":15000});
    let mut file = OpenOptions::new().write(true).create_new(true)
        .open(output.join("setup-ready.json")).map_err(|e|format!("setup ready: {e}"))?;
    file.write_all(&serde_json::to_vec(&ready).map_err(|e|e.to_string())?)
        .and_then(|_|file.sync_all()).map_err(|e|e.to_string())?;
    drop(file);
    let started = StdInstant::now();
    loop {
        if started.elapsed() >= StdDuration::from_secs(15) {
            return Err("one diagnostic setup snapshot timed out; no payload or retry".into());
        }
        match std::fs::read(output.join("setup-release.json")) {
            Ok(bytes) => {
                if bytes.len()>512 {return Err("setup release exceeds diagnostic bound".into());}
                let value: serde_json::Value = serde_json::from_slice(&bytes)
                    .map_err(|e|format!("setup release: {e}"))?;
                if value.get("token").and_then(|v|v.as_u64()) != Some(u64::from(token)) {
                    return Err("setup snapshot release token differs; no payload".into());
                }
                return Ok(started.elapsed().as_millis());
            }
            Err(e) if e.kind()==std::io::ErrorKind::NotFound => {},
            Err(e) => return Err(format!("setup release: {e}")),
        }
        tokio::time::sleep(StdDuration::from_millis(50)).await;
    }
}

pub(crate) fn receive_fixture(device_id: &str, manifest: &Path, output: &Path,
    profiles: Option<&[u16]>, capture_setup: bool) -> Result<serde_json::Value, String> {
    let connection_path=FixtureConnectionPath::from_env()?;
    validate_profiles(profiles)?; // Reject before any output or BLE connection.
    if device_id.trim().is_empty() || std::fs::metadata(manifest).map_err(|e|e.to_string())?.len() > 16384 {
        return Err("explicit benchmark device and bounded manifest required".into());
    }
    let sample: Sample = serde_json::from_slice(&std::fs::read(manifest).map_err(|e|e.to_string())?)
        .map_err(|e|format!("benchmark manifest: {e}"))?;
    let (key, _) = sample.identity()?;
    // No default product-library root or reused checkpoints. The dedicated
    // command owns this process's isolated receive root from before connect.
    std::fs::create_dir(output).map_err(|e|format!("benchmark output must be a new directory: {e}"))?;
    let output = std::fs::canonicalize(output).map_err(|e|e.to_string())?;
    std::env::set_var("COMPANION_TYPE_RECORDING_DIR", &output);
    run_native_blocking(async {
        eprintln!("recording_benchmark_connection_path stage=begin path={} explicit_synthetic_only=1",connection_path.name());
        let setup = connect_fixture(device_id,connection_path).await?;
        let device = setup.device;
        #[cfg(windows)]
        let mut preference = setup.preference;
        #[cfg(windows)]
        if let Some(p) = preference.as_mut() { p.handoff_to_sealed_sync(); }
        let mut policy = SealedLinkPolicy {
            #[cfg(windows)] preference,
            #[cfg(windows)] initialized: true,
        };
        let result = async {
            let chars = device.peripheral.characteristics();
            let explicit_peer = if profiles.is_some() {
                let status = read_optional_status(&device.peripheral, &chars, DEVICE_STATUS_UUID, 20)
                    .await.ok_or("same-link benchmark requires current authenticated V2 status")?;
                Some(crate::backend::recording_wire::transport::Peer::from_status(&status)?
                    .ok_or("same-link benchmark cannot fall back to legacy protocol")?)
            } else { None };
            let requested: Vec<Option<u16>> = match profiles {
                Some(values) => values.iter().copied().map(Some).collect(),
                None => vec![None],
            };
            let mut reports = Vec::new();
            let mut setup_pause_ms = None;
            for (index, profile) in requested.into_iter().enumerate() {
                let folder = if let Some(profile) = profile {
                    let folder = output.join(format!("{:02}-{profile}",index+1));
                    std::fs::create_dir(&folder).map_err(|e|format!("fresh profile directory: {e}"))?;
                    folder
                } else { output.clone() };
                // This command has an isolated process and no GUI/background
                // sync. Each receive opens its own empty durable cursor root;
                // changing the root never changes a product library setting.
                std::env::set_var("COMPANION_TYPE_RECORDING_DIR", &folder);
                let catalog = if let Some(profile) = profile {
                    segmented::read_catalog_with_profile(&device, &chars,
                        explicit_peer.as_ref().unwrap().clone(), profile).await?
                } else { read_recording_catalog(&device, &chars).await? };
                let peer = catalog.peer.ok_or("synthetic benchmark requires negotiated V2 peer")?;
                if peer.uid != key.device_uid || peer.epoch != key.format_epoch {
                    return Err("benchmark MCU/format epoch mismatch; no payload or consume".into());
                }
                let selected: Vec<_> = catalog.entries.iter().filter(|e|e.recording_id == sample.recording_id).collect();
                if selected.len() != 1 { return Err("benchmark sample missing or ambiguous; no payload or consume".into()); }
                let entry = selected[0];
                let descriptor = entry.segment.as_ref().ok_or("benchmark requires full sealed descriptor")?;
                peer.validate(descriptor)?;
                sample.matches(descriptor)?;
                if capture_setup && index==0 {
                    setup_pause_ms = Some(capture_setup_barrier(&output).await?);
                }
                let job = RecordingSyncJob::begin(&device.device_id())?;
                job.recording(entry.recording_id, entry.total_length);
                policy.initialize(&device).await;
                let interval = batch_interval::BatchInterval::open(&device, &chars, &peer, segmented::nonce()).await?;
                if interval.is_some() { policy.verified_batch_interval(); }
                let mut session = None;
                let start_epoch_ms = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH)
                    .map_err(|e|e.to_string())?.as_millis();
                eprintln!("recording_benchmark_window index={} requested={profile:?} start_epoch_ms={start_epoch_ms} one_native_connect=1",index+1);
                let started = StdInstant::now();
                // A failed comparison stops, preserving that failure. No
                // reconnect, recovery retry or new pairing can qualify it.
                let payload = pull_recording_bytes_once(&device.peripheral, &chars, &mut session, entry,
                    &device.address, device.address_type, None, Some(&job), Some(&mut policy)).await;
                let payload_wall = started.elapsed().as_secs_f64();
                let end_epoch_ms = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH)
                    .map_err(|e|e.to_string())?.as_millis();
                let cleanup = PullSession::quiesce_for_control(&mut session).await;
                PullSession::close(&mut session).await;
                let interval_cleanup = match interval { Some(i) => i.close().await, None => Ok(()) };
                let payload = combine_operation_and_cleanup(payload,
                    combine_operation_and_cleanup(cleanup, interval_cleanup))?;
                descriptor.verify_payload(&payload)?;
                let raw = folder.join("synthetic-upload-received.cop1");
                let mut file = OpenOptions::new().write(true).create_new(true).open(&raw).map_err(|e|e.to_string())?;
                file.write_all(&payload).and_then(|_|file.sync_all()).map_err(|e|e.to_string())?;
                drop(file);
                descriptor.verify_payload(&std::fs::read(&raw).map_err(|e|e.to_string())?)?;
                let report = serde_json::json!({
                "result":"SYNTHETIC_UPLOAD_COMPLETE", "synthetic":true, "boardMic":false,
                "recordingKey":key.public_key(), "recordingId":entry.recording_id,
                "rawPath":raw, "bytes":payload.len(), "sha256":hex_lower(&descriptor.sha256),
                "caseIndex":index+1, "requestedValueBytes":profile,
                "connectionPath":connection_path.name(),
                "payloadStartEpochMs":start_epoch_ms, "payloadEndEpochMs":end_epoch_ms,
                "payloadWallSeconds":payload_wall,
                "payloadKiBPerSecond":payload.len() as f64 / 1024.0 / payload_wall.max(0.001),
                "diagnosticSetupSnapshotPauseMs":setup_pause_ms,
                "diagnosticSetupPauseBeforeBatchAndPayload":capture_setup,
                "timerScope":"before native payload open through verified receive, includes subscription/request/waits/checkpoints; excludes connect/catalog/local raw commit",
                "cachedBytes":0, "consumeCommands":0, "captureCommands":0,
                "cloudCalls":0, "playback":false, "productLibraryWrites":0,
                "scope":"synthetic storage/native encrypted BLE diagnostic only; no microphone/meeting/QM11/OTA qualification"
                });
                std::fs::write(folder.join("benchmark-result.json"),
                    serde_json::to_vec_pretty(&report).map_err(|e|e.to_string())?).map_err(|e|e.to_string())?;
                eprintln!("recording_benchmark_window index={} end_epoch_ms={end_epoch_ms} payload_kib_s={} sha_verified=1",index+1,report["payloadKiBPerSecond"]);
                println!("recording_upload_benchmark_case_json={report}");
                reports.push(report);
            }
            if profiles.is_none() { return Ok(reports.remove(0)); }
            Ok(serde_json::json!({
                "result":"SYNTHETIC_SAME_CONNECTION_COMPARISON_COMPLETE",
                "cases":reports,"nativeConnectCalls":1,"reconnectAttempts":0,
                "connectionPath":connection_path.name(),
                "normalSetupCalls":u8::from(connection_path==FixtureConnectionPath::NormalThenSealed),
                "warmSealedSetupCalls":u8::from(connection_path==FixtureConnectionPath::NormalThenSealed),
                "sameEncryptedConnection":true,"actualLinkParametersQualified":false,
                "cachedBytes":0,"consumeCommands":0,"captureCommands":0,"cloudCalls":0,
                "synthetic":true,"boardMic":false,"productLibraryWrites":0,
                "scope":"Same native encrypted connection only; actual DLE/PHY/CI stability requires passive evidence; no microphone/meeting/QM11/OTA qualification"
            }))
        }.await;
        drop(policy);
        combine_operation_and_cleanup(result, disconnect_native_device(&device).await)
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn fixture_connection_path_requires_an_explicit_valid_choice() {
        assert!(FixtureConnectionPath::parse(None).unwrap()==FixtureConnectionPath::Sealed);
        assert!(FixtureConnectionPath::parse(Some("normal_then_sealed")).unwrap()==FixtureConnectionPath::NormalThenSealed);
        assert!(FixtureConnectionPath::parse(Some("normal")).is_err());
    }
    #[test]
    fn explicit_fixture_contract_rejects_real_source_and_identity_changes() {
        // Construct valid metadata directly; runtime also independently decodes
        // and verifies its directory CRC and full payload/frame axis.
        let sample = Sample { synthetic:true, device_uid:"010101010101010101010101".into(),
            format_epoch:"0000000000000002".into(), session_id:"0000000000000003".into(),
            recording_id:65536, bytes:2097152, sha256:"01".repeat(32) };
        let (key, sha) = sample.identity().unwrap();
        let mut d = Descriptor {key, recording_id:65536, segment_index:0, sample_offset:0,
            sample_count:15977920, encoded_length:2097152, content_crc32:1, sha256:sha,
            total_segments:1, flags:3, codec:3, source_mode:2, sync_state:1};
        assert!(sample.matches(&d).is_ok());
        d.source_mode = RECORDING_SOURCE_MIC_SAI;
        assert!(sample.matches(&d).is_err(), "diagnostic cannot accept real microphone source");
        d.source_mode = 2; d.key.session_id += 1;
        assert!(sample.matches(&d).is_err());
        d.key.session_id -= 1; d.sha256[0] ^= 1;
        assert!(sample.matches(&d).is_err());
    }

    #[test]
    fn profile_comparison_is_bounded_and_allows_aba_without_product_default_change() {
        assert!(validate_profiles(None).is_ok());
        assert!(validate_profiles(Some(&[509,219,509])).is_ok());
        assert!(validate_profiles(Some(&[495,244])).is_ok());
        for values in [&[][..], &[509][..], &[509,218][..], &[509,219,509,219][..]] {
            assert!(validate_profiles(Some(values)).is_err());
        }
    }
}
