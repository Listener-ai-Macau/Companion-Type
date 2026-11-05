//! Native product binding for the durable V2 receiver. No seed, new cloud
//! service or file-name-only consume. V1 keeps its original transfer path.
use super::*;
use crate::backend::recording_wire::{Descriptor, SessionKey, receiver::{Receiver,SyncRepair,PendingScan},
    transport::{Directory, Peer, receipt_matches}};
use crate::backend::recording_wire::tail::{Tail,Prefix};
use std::collections::BTreeMap;
use std::sync::atomic::AtomicU32;
use std::sync::OnceLock;
use super::pull_session::{NativeSubscriptions, SubscriptionLease};

const STALE: &str = "录音目录正在更新，请重新取得同一快照。";
static NONCE: OnceLock<AtomicU32> = OnceLock::new();
pub(super) fn nonce() -> u32 {
    let counter = NONCE.get_or_init(|| AtomicU32::new(
        u32::from_le_bytes(*uuid::Uuid::new_v4().as_bytes().first_chunk::<4>().unwrap()).max(1)));
    loop { let n = counter.fetch_add(1, Ordering::Relaxed); if n != 0 { return n; } }
}
fn entry(d: Descriptor) -> RecordingEntry {
    RecordingEntry { capture_incomplete: d.flags & 4 != 0, recording_id: d.recording_id,
        started_unix_s: 0, duration_ms: (d.sample_count / 16) as u32,
        codec: d.codec, sync_state: RECORDING_SYNC_UNSYNCED, source_mode: d.source_mode,
        total_length: d.encoded_length, sha256_prefix: d.sha256[..8].try_into().unwrap(),
        content_crc32: d.content_crc32, segment: Some(d), tail: None }
}

pub(super) async fn read_catalog(device: &NativeDevice,
    chars: &std::collections::BTreeSet<Characteristic>, peer: Peer) -> Result<RecordingCatalog, String> {
    let profile=std::env::var("COMPANION_TYPE_RECORDING_VALUE_BYTES")
        .ok().map(|s|s.parse::<u16>().map_err(|_|"录音包长必须为219、244、495或509。".to_string()))
        .transpose()?.unwrap_or(509);
    read_catalog_with_profile(device, chars, peer, profile).await
}

// The standalone benchmark can change capacity inside one encrypted link.
// Product callers retain the existing maximum/default policy above.
pub(super) async fn read_catalog_with_profile(device: &NativeDevice,
    chars: &std::collections::BTreeSet<Characteristic>, peer: Peer,
    profile: u16) -> Result<RecordingCatalog, String> {
    let peripheral = &device.peripheral;
    let control = find_characteristic(chars, RECORDING_CONTROL_UUID)?;
    let list = find_characteristic(chars, RECORDING_LIST_UUID)?;
    if !control.properties.contains(CharPropFlags::WRITE | CharPropFlags::NOTIFY)
        || !list.properties.contains(CharPropFlags::NOTIFY) {
        return Err("连续录音需要加密控制写入及目录/确认通知。".into());
    }
    let budget = env_timeout("COMPANION_TYPE_BLE_READ_TIMEOUT_MS", 8_000);
    let deadline = StdInstant::now() + budget;
    let settings=find_characteristic(chars,SETTINGS_UUID)?;
    let clock=bounded_ble_result("read calendar capability",budget,peripheral.read(&settings)).await?;
    let calendar=clock.len()>=17 && clock[0]==1;
    #[cfg(windows)]
    let actual_mtu=device.connection_session.as_ref()
        .ok_or("V2 recording has no owned GATT session; no protocol write was sent")?
        .wait_recording_mtu(remaining_deadline_budget(deadline, budget)).await?;
    #[cfg(not(windows))]
    let actual_mtu=251u16;
    let mut notifications = bounded_ble_result("open V2 control notifications", budget,
        peripheral.notifications()).await?;
    let mut lease = SubscriptionLease::open(NativeSubscriptions::new(
        peripheral.clone(),vec![control.clone(), list.clone()]), 2, budget).await?;
    let result = timeout(remaining_deadline_budget(deadline, budget), async {
        let request = peer.negotiate_capacity(nonce(),actual_mtu,profile)?;
        eprintln!("BLE recording_packet_profile actual_att_mtu={actual_mtu} peer_value_max={} requested={profile} selected={}",
            peer.max_value_bytes,u16::from_le_bytes(request[2..4].try_into().unwrap()));
        bounded_ble_result("negotiate exact V2 recorder", remaining_deadline_budget(deadline, budget),
            peripheral.write(&control, &request, WriteType::WithResponse)).await?;
        loop {
            let n = notifications.next().await.ok_or("连续录音确认流已断开。")?;
            if n.uuid != RECORDING_CONTROL_UUID { continue; }
            if n.value == request { break; }
            if n.value.len() >= 8 && n.value[0] == 2 && n.value[1] == 0x22
                && n.value[4..8] == request[4..8] {
                return Err("设备拒绝了当前连续录音协商，尚未开始收取。".into());
            }
        }
        for _ in 0..3 {
            let mut directory = Directory::new(&peer, nonce())?;
            directory.calendar(calendar);
            let mut stale = false;
            while !directory.finished() {
                let request = directory.request();
                bounded_ble_result("request V2 directory page", remaining_deadline_budget(deadline, budget),
                    peripheral.write(&control, &request, WriteType::WithResponse)).await?;
                loop {
                    let n = notifications.next().await.ok_or("连续录音目录流已断开。")?;
                    if n.uuid != RECORDING_LIST_UUID { continue; }
                    match directory.accept(&n.value) {
                        Ok(true) => break,
                        Ok(false) => continue,
                        Err(e) if e == STALE => { stale = true; break; }
                        Err(e) => return Err(e),
                    }
                }
                if stale { break; }
            }
            if !stale {
                let generation = directory.generation();
                let dates=directory.dates();
                return Ok(RecordingCatalog { entries: directory.entries().into_iter().map(|d| {
                    let date=dates.get(&d.recording_id).copied().unwrap_or(0);
                    let mut e=entry(d);e.started_unix_s=date;e
                }).collect(),
                    peer: Some(peer.clone()), generation });
            }
        }
        Err("录音目录持续变化，这次没有混合快照或消费数据；请稍后继续同步。".into())
    }).await.map_err(|_| "连续录音目录确认超时，未消费设备数据。".to_string())
        .and_then(|r| r);
    // Every exit, including write failure, malformed response and cancellation,
    // releases subscriptions. Never retire another capture or reset a board.
    combine_operation_and_cleanup(result, lease.quiesce_for_control().await)
}

/// Only used after legacy contiguous-space admission rejects. Unsupported old
/// firmware never changes its normal path; timeout returns None and keeps the
/// original conservative rejection. All subscriptions are owned and retired.
pub(super) async fn fragmented_slots(device:&NativeDevice,
    chars:&std::collections::BTreeSet<Characteristic>,peer:&Peer,start_request:u32,
    generation:u32)->Result<Option<u8>,String> {
    if start_request==0 {return Err("录音请求身份无效。".into());}
    let control=find_characteristic(chars,RECORDING_CONTROL_UUID)?;
    if !control.properties.contains(CharPropFlags::WRITE|CharPropFlags::NOTIFY) {return Ok(None);}
    let budget=env_timeout("COMPANION_TYPE_BLE_READ_TIMEOUT_MS",8_000);
    #[cfg(windows)]
    let actual_mtu=device.connection_session.as_ref().ok_or("V2 recording has no owned GATT session")?
        .wait_recording_mtu(budget).await?;
    #[cfg(not(windows))]
    let actual_mtu=251u16;
    let mut notifications=bounded_ble_result("open capacity notifications",budget,
        device.peripheral.notifications()).await?;
    let mut lease=SubscriptionLease::open(NativeSubscriptions::new(
        device.peripheral.clone(),vec![control.clone()]),1,budget).await?;
    let result=async {
        let negotiation=peer.negotiate_capacity(nonce(),actual_mtu,509)?;
        bounded_ble_result("negotiate capacity snapshot",budget,
            device.peripheral.write(&control,&negotiation,WriteType::WithResponse)).await?;
        timeout(budget,async {
            loop {let n=notifications.next().await.ok_or("录音容量连接已断开。")?;
                if n.uuid==RECORDING_CONTROL_UUID&&n.value==negotiation {break;}}
            Ok::<(),String>(())
        }).await.map_err(|_|"设备录音容量协商超时。".to_string())??;
        let mut request=[0u8;32];request[0]=2;request[1]=0x26;
        request[4..8].copy_from_slice(&start_request.to_le_bytes());
        request[8..20].copy_from_slice(&peer.uid);request[20..28].copy_from_slice(&peer.epoch.to_le_bytes());
        let crc=crc32fast::hash(&request[..28]);request[28..32].copy_from_slice(&crc.to_le_bytes());
        // An older firmware does not recognize this optional request. No
        // start/stop/consume is sent; absent reply retains the original gate.
        if bounded_ble_result("request capacity snapshot",budget,
            device.peripheral.write(&control,&request,WriteType::WithResponse)).await.is_err() {return Ok(None);}
        let observed=timeout(StdDuration::from_secs(2),async {
            loop {
                let n=notifications.next().await.ok_or("录音容量连接已断开。")?;
                if n.uuid!=RECORDING_CONTROL_UUID||n.value.len()!=32||&n.value[..4]!=b"CSN1" {continue;}
                if let Some(count)=super::super::recording_capacity::parse_slots_reply(
                    &n.value,&peer.uid,start_request,generation)? {return Ok(Some(count));}
            }
        }).await;
        match observed {Ok(v)=>v,Err(_)=>Ok(None)}
    }.await;
    combine_operation_and_cleanup(result,lease.quiesce_for_control().await)
}

pub(super) async fn check_fragmented_start(device:&NativeDevice,
    chars:&std::collections::BTreeSet<Characteristic>,peer:&Peer,
    capacity:&crate::companion_v1::CompanionV1RecordingCapacity,seconds:u16,follow:bool,
    start_request:u32)->Result<(),String> {
    let original=match super::super::recording_capacity::check_start(capacity,seconds,follow) {
        Ok(())=>return Ok(()),Err(e)=>e,
    };
    let possible=match(capacity.segment_frames,capacity.segment_extent_bytes) {
        (Some(frames),Some(extent)) if frames>0&&extent>0=>{
            let count=if seconds==0 {1} else {(u64::from(seconds)*50).div_ceil(u64::from(frames))};
            let count=if follow{count.min(2)}else{count};
            count>0 && count<=u64::from(capacity.free_bytes/extent) &&
                count<=u64::from(capacity.max_entries.saturating_sub(capacity.used_entries))
        },_=>false,
    };
    if !possible{return Err(original);}
    let Some(count)=fragmented_slots(device,chars,peer,start_request,capacity.catalog_generation).await?
        else{return Err(original);};
    let fresh=read_recording_protocol_identity(&device.peripheral,chars).await?;
    let fresh_peer=Peer::from_status(&fresh)?.ok_or("设备录音能力已改变，未开始录音。")?;
    let fresh_capacity=super::super::recording_capacity::parse(&fresh)
        .ok_or("设备容量状态已改变，未开始录音。")?;
    if fresh_peer!=*peer||fresh_capacity!=*capacity {
        return Err("设备录音目录或容量已改变，请重试。".into());
    }
    super::super::recording_capacity::check_start_with_slots(&fresh_capacity,seconds,follow,count)
}

async fn consume(device: &NativeDevice, chars: &std::collections::BTreeSet<Characteristic>,
    peer: &Peer, request: &[u8]) -> Result<(), String> {
    // ACK candidates come only from Receiver's revalidated raw+library commit.
    receipt_matches(request, request, peer)?;
    let control = find_characteristic(chars, DELETE_PRIVACY_UUID)?;
    if !control.properties.contains(CharPropFlags::WRITE | CharPropFlags::NOTIFY) {
        return Err("设备缺少精确消费确认接口，原音已保存且未主动删除。".into());
    }
    let budget = env_timeout("COMPANION_TYPE_BLE_WRITE_TIMEOUT_MS", 8_000);
    let mut notifications = bounded_ble_result("open V2 physical receipt", budget,
        device.peripheral.notifications()).await?;
    let mut lease = SubscriptionLease::open(NativeSubscriptions::new(
        device.peripheral.clone(),vec![control.clone()]), 1, budget).await?;
    let length = u32::from_le_bytes(request[44..48].try_into().unwrap());
    let wait = StdDuration::from_millis(device_reclaim_timeout_ms(DELETE_PRIVACY_OP_DELETE_RECORDING, length));
    let result = async {
        bounded_ble_result("send exact V2 durable consume", budget,
            device.peripheral.write(&control, request, WriteType::WithResponse)).await?;
        timeout(wait, async {
            loop {
                let n = notifications.next().await.ok_or("物理消费确认流已断开，原音已保存。")?;
                if n.uuid != DELETE_PRIVACY_UUID { continue; }
                if receipt_matches(request, &n.value, peer)? { return Ok(()); }
                // Error frame cannot authorize anything; only its exact ID
                // selects the failed request. Never interpret absence as ACK.
                if n.value.len() == 16 && &n.value[..8] == b"CAE2\x02\x00\x10\x00"
                    && n.value[8..12] == request[40..44] {
                    let reason = u32::from_le_bytes(n.value[12..16].try_into().unwrap());
                    return Err(format!("设备未确认精确消费（原因{reason}），原音已保存，回执保持待确认。"));
                }
            }
        }).await.map_err(|_| "物理消费回复超时，原音已保存；下次重试相同完整身份。".to_string())?
    }.await;
    combine_operation_and_cleanup(result, lease.quiesce_for_control().await)
}

pub(super) async fn follow_tail(device:&NativeDevice,
    chars:&std::collections::BTreeSet<Characteristic>,peer:&Peer,key:&SessionKey,job:&RecordingSyncJob,
    live:Option<&mut super::super::recording_wire::receiver::LiveCursor>)->Result<(),String> {
    if job.is_paused() {return Err(recording_sync::PAUSED.into());}
    let control=find_characteristic(chars,RECORDING_CONTROL_UUID)?;
    let list=find_characteristic(chars,RECORDING_LIST_UUID)?;
    let budget=env_timeout("COMPANION_TYPE_BLE_READ_TIMEOUT_MS",8_000);
    let n=nonce();let request=Tail::request(peer,key,n)?;
    let mut notifications=bounded_ble_result("open committed tail snapshot",budget,device.peripheral.notifications()).await?;
    let mut lease=SubscriptionLease::open(NativeSubscriptions::new(device.peripheral.clone(),
        vec![control.clone(),list]),2,budget).await?;
    let result=timeout(budget,async {
        bounded_ble_result("request committed tail",budget,
            device.peripheral.write(&control,&request,WriteType::WithResponse)).await?;
        loop {
            let notice=notifications.next().await.ok_or("录中前缀确认流已断开，板端继续采音。")?;
            if notice.uuid!=RECORDING_LIST_UUID {continue;}
            let p=&notice.value;
            if p.len()==16&&&p[..8]==b"CRE2\x02\x00\x10\x00"
                &&u32::from_le_bytes(p[8..12].try_into().unwrap())==n {
                let reason=u32::from_le_bytes(p[12..16].try_into().unwrap());
                if reason==1 {return Ok(None);} // capture owns slice / no complete page yet
                return Err(format!("设备拒绝录中前缀（原因{reason}），未消费数据。"));
            }
            if p.len()<72||&p[..4]!=b"CLP2"||u32::from_le_bytes(p[68..72].try_into().unwrap())!=n {continue;}
            return Tail::decode(p,peer,key,n).map(Some);
        }
    }).await.map_err(|_|"录中前缀确认超时，板端继续采音；已有耐久前缀保留。".to_string()).and_then(|r|r);
    let tail=combine_operation_and_cleanup(result,lease.quiesce_for_control().await)?;
    let Some(tail)=tail else{return Ok(())};
    let root=native_recording_root()?;
    let (cursor,bytes)=Prefix::load(&root,&tail,peer)?;
    if bytes.len()==tail.encoded_length as usize {
        if let Some(live)=live {live.tail(&tail,&bytes);}return Ok(());
    }
    job.recording(tail.recording_id,tail.encoded_length);
    let e=RecordingEntry{capture_incomplete:false,recording_id:tail.recording_id,
        started_unix_s:tail.started_unix_s,duration_ms:(tail.sample_count/16) as u32,
        codec:3,source_mode:RECORDING_SOURCE_MIC_SAI,sync_state:RECORDING_SYNC_TRANSFER_ACTIVE,
        total_length:tail.encoded_length,sha256_prefix:[0;8],content_crc32:0,segment:None,tail:Some(tail.clone())};
    let mut session=None;
    let received=pull_recording_bytes(device,chars,&mut session,&e,&device.address,
        device.address_type,Some(bytes),Some(job),None).await;
    let cleanup=PullSession::quiesce_for_control(&mut session).await;
    if cleanup.is_err() {
        let cause=super::pull_session::finish_receive::<Vec<u8>>(received,cleanup).unwrap_err();
        retire_native_device(device,&cause).await;
        return Err(cause);
    }
    let received=super::pull_session::finish_receive(received,cleanup)?;
    job.saving();cursor.save(&tail,&received,peer)?;
    if let Some(live)=live {live.tail(&tail,&received);}
    eprintln!("recording_tail durable uid={} epoch={:016x} session={:016x} segment={} id={} bytes={} consume=0",
        hex_lower(&key.device_uid),key.format_epoch,key.session_id,tail.segment_index,tail.recording_id,received.len());
    Ok(())
}

pub(super) async fn sync_catalog(device: &NativeDevice,
    chars: &std::collections::BTreeSet<Characteristic>, peer: Peer, entries: Vec<RecordingEntry>,
    job: &RecordingSyncJob, link_policy: &mut SealedLinkPolicy, scope: Option<&SessionKey>) -> Result<NativeRecordingBatch, String> {
    sync_catalog_limited(device, chars, peer, entries, job, link_policy, None, scope).await.map(|(batch, _)| batch)
}

fn admit_segment(admitted: &mut std::collections::BTreeSet<(SessionKey, u32)>,
    key: &SessionKey, id: u32, limit: Option<usize>) -> bool {
    let identity = (key.clone(), id);
    if admitted.contains(&identity) { return true; }
    if limit.is_some_and(|limit| admitted.len() >= limit) { return false; }
    admitted.insert(identity); true
}

type SessionGroups = BTreeMap<SessionKey, (Vec<u8>, Vec<RecordingEntry>)>;

fn microphone_groups(peer: &Peer, pending: Vec<Vec<u8>>, entries: Vec<RecordingEntry>,
    scope: Option<&SessionKey>) -> Result<SessionGroups, String> {
    if scope.is_some_and(|key| key.device_uid != peer.uid || key.format_epoch != peer.epoch) {
        return Err("同步目标与当前芯片或格式代次不一致，未消费。".into());
    }
    let mut groups = SessionGroups::new();
    for wire in pending {
        let d = Descriptor::decode(&wire)?;
        peer.validate(&d)?;
        groups.entry(d.key).or_insert((wire, Vec::new()));
    }
    for e in entries {
        let d = e.segment.as_ref().ok_or("连续目录混入了旧录音身份。")?;
        peer.validate(d)?;
        let wire = d.encode()?;
        groups.entry(d.key.clone()).or_insert((wire, Vec::new())).1.push(e);
    }
    // The directory also contains retained diagnostic recordings. An unrelated
    // session must not prevent following the actual microphone's growing tail.
    // All wire identities above remain validated; no skipped group is opened,
    // published, pulled or acknowledged. Explicit non-microphone targets fail.
    if let Some(scope) = scope { groups.retain(|key, _| key == scope); }
    let mut microphones = SessionGroups::new();
    for (key, (wire, entries)) in groups {
        let initial = Descriptor::decode(&wire)?;
        if entries.iter().any(|e| e.source_mode != initial.source_mode) {
            return Err("同一连续录音的采集来源不一致，未消费。".into());
        }
        if initial.source_mode != RECORDING_SOURCE_MIC_SAI {
            if scope.is_some() {
                return Err("连续录音不是实板麦克风来源，未消费。".into());
            }
            continue;
        }
        microphones.insert(key, (wire, entries));
    }
    Ok(microphones)
}

// Do not act on any device segment belonging to a local receipt that could
// not be read or validated; keep other complete session identities independent.
fn isolate_blocked_groups(scan: &PendingScan, all: SessionGroups) -> Result<(SessionGroups, Vec<String>), String> {
    let mut groups = SessionGroups::new();
    for (key, value) in all { if !scan.blocks(&key)? { groups.insert(key, value); } }
    let failures = if scan.blocked_count() == 0 { Vec::new() } else {
        vec![format!("{}条本地录音恢复记录损坏或被占用，已保留对应设备原件", scan.blocked_count())]
    };
    Ok((groups, failures))
}

pub(super) async fn sync_catalog_limited(device: &NativeDevice,
    chars: &std::collections::BTreeSet<Characteristic>, peer: Peer, entries: Vec<RecordingEntry>,
    job: &RecordingSyncJob, link_policy: &mut SealedLinkPolicy,
    limit: Option<usize>, scope: Option<&SessionKey>) -> Result<(NativeRecordingBatch, bool), String> {
    if device.verified_uid.as_ref().is_some_and(|uid| *uid != hex_lower(&peer.uid)) {
        return Err("连接后的实际MCU与已核实设备不同，未收取或消费。".into());
    }
    let root = native_recording_root()?;
    let index = crate::backend::persistence::state_file_path();
    // Lost final replies can leave NO device entry. Only exact local manifests
    // for this UID+epoch+receiver reopen that durable session, no blind scan.
    let scan = Receiver::pending_initials(&root, &peer, &device.device_id(), scope)?;
    let mut dates=BTreeMap::new();
    for e in &entries {
        if let Some(d)=e.segment.as_ref().filter(|_|e.started_unix_s!=0) {
            if dates.insert(d.key.clone(),e.started_unix_s).is_some_and(|old|old!=e.started_unix_s) {
                return Err("同一场录音的开录日期不一致，原音保留。".into());
            }
        }
    }
    let all_groups = microphone_groups(&peer, scan.initials.clone(), entries, scope)?;
    let (groups, failures) = isolate_blocked_groups(&scan, all_groups)?;
    let mut batch = NativeRecordingBatch { device_id: device.device_id(), recordings: Vec::new(),
        failures, paused: false, connection_reusable: true, segmented: Some(Vec::new()) };
    let mut pull_session = None;
    let mut admitted = std::collections::BTreeSet::new();
    let mut deferred = false;
    let interval=if groups.values().any(|(_,entries)| !entries.is_empty()) {
        link_policy.initialize(device).await;
        let interval=super::batch_interval::BatchInterval::open(device,chars,&peer,nonce()).await?;
        if interval.is_some(){link_policy.verified_batch_interval();}
        interval
    } else {None};
    let delete = std::env::var("COMPANION_TYPE_DELETE_AFTER_SYNC")
        .map(|s| !matches!(s.trim().to_ascii_lowercase().as_str(), "0" | "false" | "off")).unwrap_or(true);
    for (key, (initial, mut entries)) in groups {
        let recorded_date=dates.get(&key).copied();
        if limit.is_some_and(|limit| admitted.len() >= limit) { deferred = true; break; }
        entries.sort_by_key(|e| e.segment.as_ref().unwrap().segment_index);
        let work = async {
            let available=entries.iter().map(|e|e.segment.as_ref().unwrap().clone()).collect::<Vec<_>>();
            let mut repair=SyncRepair::begin(&root,&initial,&peer,&device.device_id(),&available)?;
            // Previously received originals can disappear independently of
            // their durable receipt. Repair only exact current catalogue
            // identities before obtaining a publish/consume-capable receiver.
            for d in repair.missing().to_vec() {
                if job.is_paused() {return Err(recording_sync::PAUSED.into());}
                if !admit_segment(&mut admitted,&key,d.recording_id,limit) {deferred=true;return Ok(());}
                let e=entries.iter().find(|e|e.segment.as_ref().is_some_and(|current|current.same_content(&d)))
                    .ok_or("缺失原音不在当前设备目录，未消费。")?;
                job.recording(e.recording_id,e.total_length);link_policy.initialize(device).await;
                let prefix=if peer.growing_tail {Prefix::sealed(&root,&d,&peer)?}else{None};
                let bytes=pull_recording_bytes(device,chars,&mut pull_session,e,&device.address,
                    device.address_type,prefix,Some(job),Some(link_policy)).await?;
                job.saving();repair.restore(&d.encode()?,&bytes)?;
            }
            let mut receiver=repair.finish()?;
            for e in &entries { receiver.accept_metadata(&e.segment.as_ref().unwrap().encode()?)?; }
            // Keep the data CCCDs/receiver across a complete stopped recording.
            // Each raw segment and index still commits before the next pull;
            // exact ACKs follow one stream release below. Open recordings and
            // limited live slices retain their immediate per-segment consume.
            let batch_reclaim = receiver.plan()?.may_batch_reclaim(limit);
            for e in &entries {
                if job.is_paused() { return Err(recording_sync::PAUSED.into()); }
                job.recording(e.recording_id, e.total_length);
                let d = e.segment.as_ref().unwrap();
                let wire = d.encode()?;
                let mut raw_checkpoint_us = 0;
                let mut local_started = None;
                if !receiver.has_segment(&wire)? {
                    if !admit_segment(&mut admitted, &key, e.recording_id, limit) { deferred = true; return Ok(()); }
                    link_policy.initialize(device).await;
                    let prefix=if peer.growing_tail { Prefix::sealed(&root,d,&peer)? } else {None};
                    let bytes = pull_recording_bytes(device, chars, &mut pull_session, e,
                        &device.address, device.address_type, prefix, Some(job), Some(link_policy)).await?;
                    job.saving();
                    // Full SHA/CRC/frame axis are mandatory even with legacy
                    // diagnostic skip variables. COP1 originals stay unchanged.
                    let checkpoint_started = StdInstant::now();
                    local_started = Some(checkpoint_started);
                    receiver.accept_segment(&wire, &bytes)?;
                    raw_checkpoint_us = checkpoint_started.elapsed().as_micros();
                }
                let local_started = local_started.unwrap_or_else(StdInstant::now);
                let publish_started = StdInstant::now();
                let published_id = receiver.publish_with_date(&index, &device.device_id(),recorded_date)?;
                let publish_us = publish_started.elapsed().as_micros();
                let prefix_started = StdInstant::now();
                if peer.growing_tail { Prefix::release(&root,d,&peer)?; }
                let prefix_release_us = prefix_started.elapsed().as_micros();
                let ids = batch.segmented.as_mut().unwrap();
                if !ids.contains(&published_id) { ids.push(published_id); }
                let reclaim_started = StdInstant::now();
                if delete && !batch_reclaim {
                    PullSession::quiesce_for_control(&mut pull_session).await?;
                    for ack in receiver.ack_candidates(&index)? {
                        if job.is_paused() { return Err(recording_sync::PAUSED.into()); }
                        let id = u32::from_le_bytes(ack[40..44].try_into().unwrap());
                        if !admit_segment(&mut admitted, &key, id, limit) { deferred = true; return Ok(()); }
                        // Once sent, finish this bounded irreversible operation
                        // and commit its exact reply before honoring a pause.
                        job.reclaiming();
                        consume(device, chars, &peer, &ack).await?;
                        receiver.confirm_acked(&ack)?;
                    }
                    receiver.publish_with_date(&index, &device.device_id(),recorded_date)?;
                }
                let reclaim_us = reclaim_started.elapsed().as_micros();
                let cursor_started = StdInstant::now();
                super::super::recording_transfer::release(&root, recording_transfer_source(&device.address, e))?;
                // One line per sealed segment, never per packet or an extra
                // GATT read. The payload timer excludes these commits, whereas
                // the whole-original HCI window includes the gap before the
                // next segment. Keep those two measurements distinguishable.
                eprintln!("recording_segment_commit id={} raw_checkpoint_us={} publish_us={} prefix_release_us={} reclaim_us={} cursor_release_us={} local_total_us={} batch_reclaim={} delete_enabled={} end_host_unix_us={} scope=local_after_payload_not_radio_cause",
                    e.recording_id, raw_checkpoint_us, publish_us, prefix_release_us,
                    reclaim_us, cursor_started.elapsed().as_micros(), local_started.elapsed().as_micros(),
                    batch_reclaim, delete, chrono::Utc::now().timestamp_micros());
            }
            // Also cover interrupted host work with no matching live directory
            // entry. Reverification and publish precede the replay command.
            if job.is_paused() { return Err(recording_sync::PAUSED.into()); }
            receiver.publish_with_date(&index, &device.device_id(),recorded_date)?;
            if delete {
                PullSession::quiesce_for_control(&mut pull_session).await?;
                for ack in receiver.ack_candidates(&index)? {
                    if job.is_paused() { return Err(recording_sync::PAUSED.into()); }
                    let id = u32::from_le_bytes(ack[40..44].try_into().unwrap());
                    if !admit_segment(&mut admitted, &key, id, limit) { deferred = true; return Ok(()); }
                    job.reclaiming();
                    consume(device, chars, &peer, &ack).await?;
                    receiver.confirm_acked(&ack)?;
                }
            }
            if receiver.plan()?.payloads_complete { receiver.assemble_session()?; }
            let published_id = receiver.publish_with_date(&index, &device.device_id(),recorded_date)?;
            let ids = batch.segmented.as_mut().unwrap();
            if !ids.contains(&published_id) { ids.push(published_id); }
            Ok::<(), String>(())
        }.await;
        match work {
            Ok(()) => (),
            Err(e) if e == recording_sync::PAUSED => { batch.paused = true; break; }
            Err(e) => {
                batch.failures.push(e);
                // An uncertain control stream is never reused for a later ACK.
                // Preserve the exact durable receiver intent for next connect.
                batch.connection_reusable = false;
                break;
            }
        }
    }
    if let Err(error)=PullSession::quiesce_for_control(&mut pull_session).await {
        batch.failures.push(error);batch.connection_reusable=false;
    }
    if let Some(interval)=interval {
        if let Err(error)=interval.close().await {
            batch.failures.push(error);batch.connection_reusable=false;
        }
    }
    Ok((batch, deferred))
}

#[cfg(test)]
mod follow_tests {
    use super::*;
    fn directory_entry(peer: &Peer, session: u64, source: u8, id: u32) -> RecordingEntry {
        entry(Descriptor { key: SessionKey { device_uid: peer.uid, format_epoch: peer.epoch, session_id: session },
            recording_id: id, segment_index: 0, sample_offset: 0, sample_count: 320,
            encoded_length: 17, content_crc32: 1, sha256: [1;32], total_segments: 1,
            flags: 3, codec: 3, source_mode: source, sync_state: 0 })
    }
    fn peer() -> Peer {
        Peer { uid: [0x35;12], epoch: 2, capacity: 64, max_value_bytes: 509,
            logical_control: true, growing_tail: true, batch_interval: true, pause_control: true }
    }
    #[test]
    fn batch_corrupt_receipt_blocks_only_its_exact_session_and_ota() {
        use sha2::{Digest, Sha256};
        let p=peer();let good=directory_entry(&p,14,1,91);let bad=directory_entry(&p,15,1,92);
        let good_key=good.segment.as_ref().unwrap().key.clone();let bad_key=bad.segment.as_ref().unwrap().key.clone();
        let root=std::env::temp_dir().join(format!("companion-batch-isolate-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir(&root).unwrap();
        let name=format!(".board-session-{:x}.json",Sha256::digest(serde_json::to_vec(&bad_key).unwrap()));
        std::fs::write(root.join(name),b"{broken").unwrap();
        let scan=Receiver::pending_initials(&root,&p,"A1:B2:C3:D4:E5:F6",None).unwrap();
        let all=microphone_groups(&p,scan.initials.clone(),vec![good,bad],None).unwrap();
        let (groups,failures)=isolate_blocked_groups(&scan,all).unwrap();
        assert!(groups.contains_key(&good_key));assert!(!groups.contains_key(&bad_key));assert_eq!(failures.len(),1);
        let batch=NativeRecordingBatch {device_id:"A1:B2:C3:D4:E5:F6".into(),recordings:Vec::new(),
            failures,paused:false,connection_reusable:true,segmented:Some(vec!["saved-good".into()])};
        assert!(require_ota_sync_outcome(batch).is_err(),"partial batch must never authorize OTA");
        std::fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn unrelated_diagnostics_do_not_block_scoped_or_automatic_microphone_follow() {
        let p = peer();
        let mic = directory_entry(&p, 14, RECORDING_SOURCE_MIC_SAI, 65537);
        let key = mic.segment.as_ref().unwrap().key.clone();
        for source in [0,2] {
            for scope in [None, Some(&key)] {
                let groups = microphone_groups(&p, vec![], vec![directory_entry(&p, 0x7fff202610120001, source, 65536), mic.clone()], scope).unwrap();
                assert_eq!(groups.len(), 1);
                assert_eq!(groups[&key].1[0].recording_id, 65537);
            }
        }
    }
    #[test]
    fn explicitly_targeting_diagnostic_audio_remains_rejected() {
        let p=peer();
        let diagnostic=directory_entry(&p, 23, 2, 91);
        let key=diagnostic.segment.as_ref().unwrap().key.clone();
        assert!(microphone_groups(&p, vec![], vec![diagnostic], Some(&key)).unwrap_err().contains("不是实板麦克风"));
    }
    #[test]
    fn mixed_source_inside_one_session_never_becomes_microphone_evidence() {
        let p=peer();
        let mic=directory_entry(&p, 14, 1, 91);
        let key=mic.segment.as_ref().unwrap().key.clone();
        for scope in [None, Some(&key)] {
            assert!(microphone_groups(&p, vec![], vec![mic.clone(), directory_entry(&p,14,2,92)], scope).is_err());
            assert!(microphone_groups(&p, vec![mic.segment.as_ref().unwrap().encode().unwrap()], vec![directory_entry(&p,14,2,92)], scope).is_err());
        }
    }
    #[test]
    fn lost_consume_reply_keeps_exact_microphone_manifest_with_empty_directory() {
        let p=peer();let mic=directory_entry(&p,14,1,91);let d=mic.segment.as_ref().unwrap();
        let groups=microphone_groups(&p,vec![d.encode().unwrap()],vec![directory_entry(&p,23,2,92)],Some(&d.key)).unwrap();
        assert_eq!(groups.len(),1);assert!(groups[&d.key].1.is_empty());
    }
    #[test]
    fn stale_scope_and_malformed_unrelated_identity_still_fail() {
        let p=peer();let mut mic=directory_entry(&p,14,1,91);let mut key=mic.segment.as_ref().unwrap().key.clone();
        key.format_epoch+=1;assert!(microphone_groups(&p,vec![],vec![mic.clone()],Some(&key)).is_err());
        mic.segment.as_mut().unwrap().key.device_uid[0]^=1;
        assert!(microphone_groups(&p,vec![],vec![mic],None).is_err());
    }
    #[test]
    fn background_slice_counts_transfer_and_its_receipt_as_one_physical_segment() {
        let key = SessionKey { device_uid: [1;12], format_epoch: 2, session_id: 3 };
        let mut admitted = std::collections::BTreeSet::new();
        assert!(admit_segment(&mut admitted, &key, 17, Some(1)));
        assert!(admit_segment(&mut admitted, &key, 17, Some(1)), "same raw durable ACK remains in this slice");
        assert!(!admit_segment(&mut admitted, &key, 18, Some(1)));
        let mut other = key.clone(); other.session_id += 1;
        assert!(!admit_segment(&mut admitted, &other, 17, Some(1)), "physical IDs never alias another session");
    }
}
