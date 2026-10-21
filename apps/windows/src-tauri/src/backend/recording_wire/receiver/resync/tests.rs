use super::*;
const DEVICE:&str="A1:B2:C3:D4:E5:F6";
struct Environment(Option<std::ffi::OsString>);
impl Environment {
    fn managed(root:&Path)->Self {
        let old=std::env::var_os("COMPANION_TYPE_RECORDING_DIR");
        std::env::set_var("COMPANION_TYPE_RECORDING_DIR",root);Self(old)
    }
}
impl Drop for Environment {
    fn drop(&mut self) {match &self.0 {
        Some(value)=>std::env::set_var("COMPANION_TYPE_RECORDING_DIR",value),
        None=>std::env::remove_var("COMPANION_TYPE_RECORDING_DIR"),
    }}
}
fn root()->PathBuf {
    let path=std::env::temp_dir().join(format!("companion-resync-r63-{}",uuid::Uuid::new_v4()));
    fs::create_dir(&path).unwrap();path
}
fn remove(root:PathBuf) {
    assert_eq!(root.parent(),Some(std::env::temp_dir().as_path()));
    fs::remove_dir_all(root).unwrap();
}
fn fixture(root:&Path)->(Peer,Vec<Descriptor>,Vec<u8>,PathBuf,PathBuf,Vec<u8>) {
    // Software silence fixture only: no microphone, board, BLE, cloud or speed.
    let mut raw=b"COP1\x01\x01\x14\x00\x80\x3e\x00\x00".to_vec();
    for _ in 0..3 {raw.extend_from_slice(&[3,0,0xf8,0xff,0xfe]);}
    let peer=Peer{uid:[0x35;12],epoch:9,capacity:64,max_value_bytes:509,
        logical_control:true,growing_tail:true,batch_interval:true,pause_control:true};
    let key=SessionKey{device_uid:peer.uid,format_epoch:peer.epoch,session_id:37};
    let ds=(0..3).map(|n|Descriptor{key:key.clone(),recording_id:91+n,segment_index:n,
        sample_offset:u64::from(n)*960,sample_count:960,encoded_length:raw.len() as u32,
        content_crc32:crc32fast::hash(&raw),sha256:Sha256::digest(&raw).into(),
        total_segments:if n==2{3}else{0},flags:if n==2{3}else{1},codec:3,source_mode:1,sync_state:0}).collect::<Vec<_>>();
    let index=root.join("sessions.json");let mut r=Receiver::open(root,&ds[0].encode().unwrap()).unwrap();
    for d in &ds {r.accept_segment(&d.encode().unwrap(),&raw).unwrap();}
    let wav=r.assemble().unwrap();r.publish(&index,DEVICE).unwrap();
    let first=r.ack_candidates(&index).unwrap().remove(0);r.confirm_acked(&first).unwrap();
    r.publish(&index,DEVICE).unwrap();
    session_store::update_checked(&index,|rows|{rows[0].title="My untouched title".into();Ok(())}).unwrap();
    let receipt=r.receipt_path();let audio=fs::read(&wav).unwrap();drop(r);
    (peer,ds,raw,index,receipt,audio)
}
fn json(path:&Path)->serde_json::Value {serde_json::from_slice(&fs::read(path).unwrap()).unwrap()}
fn payload(root:&Path,d:&Descriptor)->PathBuf {
    let r=Receiver::open_inner(root,&d.encode().unwrap(),OpenMode::PrepareSync).unwrap();r.payload_path(d)
}
#[test]
fn r63_managed_missing_original_refetch_preserves_receipt_and_rebuilds_wav_after_restart() {
    let root=root();let _environment=Environment::managed(&root);
    let(peer,ds,raw,index,receipt,wav)=fixture(&root);
    let before=json(&receipt);let row_before=json(&index)[0].clone();let missing=payload(&root,&ds[1]);
    let audio=PathBuf::from(row_before["audioPath"].as_str().unwrap());
    fs::remove_file(&missing).unwrap();fs::remove_file(&audio).unwrap();
    assert!(Receiver::open(&root,&ds[0].encode().unwrap()).is_err());
    let mut repair=SyncRepair::begin(&root,&ds[0].encode().unwrap(),&peer,DEVICE,&ds).unwrap();
    assert_eq!(repair.missing().len(),1);assert_eq!(repair.missing()[0].recording_id,ds[1].recording_id);
    assert!(repair.restore(&ds[1].encode().unwrap(),b"wrong payload").is_err());assert!(!missing.exists());
    repair.restore(&ds[1].encode().unwrap(),&raw).unwrap();
    drop(repair); // Crash boundary after raw commit, before WAV/publish/consume.
    assert_eq!(json(&receipt),before,"never clear received or acknowledged history");
    let repair=SyncRepair::begin(&root,&ds[0].encode().unwrap(),&peer,DEVICE,&ds).unwrap();
    assert!(repair.missing().is_empty(),"already restored bytes are not pulled again");
    let mut r=repair.finish().unwrap();assert_eq!(fs::read(&audio).unwrap(),wav);
    assert_eq!(fs::read(&missing).unwrap(),raw);assert_eq!(json(&receipt),before);
    let id=r.publish(&index,DEVICE).unwrap();let after=json(&index)[0].clone();
    assert_eq!(id,row_before["id"].as_str().unwrap());assert_eq!(after["title"],row_before["title"]);
    assert_eq!(after["deviceReclaimed"],row_before["deviceReclaimed"]);
    let acks=r.ack_candidates(&index).unwrap();assert_eq!(acks.len(),2);
    assert_eq!(super::super::super::u32le(&acks[0],40),ds[1].recording_id);
    drop(r);drop(_environment);remove(root);
}
#[test]
fn r63_directory_identity_and_absent_reclaimed_original_refuse_without_changing_evidence() {
    let root=root();let _environment=Environment::managed(&root);
    let(peer,ds,_raw,index,receipt,_wav)=fixture(&root);let before=json(&receipt);let library=fs::read(&index).unwrap();
    fs::remove_file(payload(&root,&ds[1])).unwrap();
    assert!(Receiver::open(&root,&ds[0].encode().unwrap()).err().unwrap().contains("请连接原设备补收"));
    for mut available in [vec![],vec![ds[1].clone()]] {
        if let Some(d)=available.first_mut() {d.sha256[0]^=1;}
        assert!(SyncRepair::begin(&root,&ds[0].encode().unwrap(),&peer,DEVICE,&available).is_err());
    }
    let mut foreign=peer.clone();foreign.uid[0]^=1;
    assert!(SyncRepair::begin(&root,&ds[0].encode().unwrap(),&foreign,DEVICE,&ds).is_err());
    assert!(SyncRepair::begin(&root,&ds[0].encode().unwrap(),&peer,"11:22:33:44:55:66",&ds).is_err());
    assert_eq!(json(&receipt),before);assert_eq!(fs::read(&index).unwrap(),library);
    fs::remove_file(payload(&root,&ds[0])).unwrap();
    let error=SyncRepair::begin(&root,&ds[0].encode().unwrap(),&peer,DEVICE,&[]).err().unwrap();
    assert!(error.contains("已确认回收"));assert_eq!(json(&receipt),before);
    drop(_environment);remove(root);
}
#[test]
fn r63_missing_original_cannot_reset_tombstone_or_overwrite_corrupt_existing_file() {
    for kind in ["gone","badIdentity","corruptPresent"] {
        let root=root();let _environment=Environment::managed(&root);
        let(peer,ds,raw,index,receipt,_wav)=fixture(&root);let before=json(&receipt);let library=fs::read(&index).unwrap();
        let missing=payload(&root,&ds[1]);
        if kind=="corruptPresent" {fs::write(&missing,b"preserve corrupt evidence").unwrap();}
        else {
            fs::remove_file(&missing).unwrap();let manifest=root.join(".audio-artifacts.json");let mut data=json(&manifest);
            let artifact=data["files"].as_array_mut().unwrap().iter_mut()
                .find(|f|f["file"].as_str()==missing.file_name().unwrap().to_str()).unwrap();
            if kind=="gone" {artifact["phase"]="gone".into();artifact["identity"]=serde_json::Value::Null;}
            else {artifact["identity"]["sha256"]="0".repeat(64).into();}
            fs::write(&manifest,serde_json::to_vec(&data).unwrap()).unwrap();
        }
        let mut repair=SyncRepair::begin(&root,&ds[0].encode().unwrap(),&peer,DEVICE,&ds).unwrap();
        if kind=="corruptPresent" {
            assert!(repair.missing().is_empty());assert!(repair.finish().is_err());
            assert_eq!(fs::read(&missing).unwrap(),b"preserve corrupt evidence");
        } else {
            assert!(repair.restore(&ds[1].encode().unwrap(),&raw).is_err());assert!(!missing.exists());drop(repair);
        }
        assert_eq!(json(&receipt),before);assert_eq!(fs::read(&index).unwrap(),library);
        drop(_environment);remove(root);
    }
}
