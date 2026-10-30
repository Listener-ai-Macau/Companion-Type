//! Portable CMC3 driver. The transport supplies only the already selected link.
use super::{device_connection,export,recorder_control::{self,Journal,Observation,SettlementAction},
    recording_capacity as capacity,recording_wire::{control::{self,PausePeer,PauseStatus},transport::Peer}};
use sha2::{Digest,Sha256};
use std::{fs::{self,OpenOptions},path::{Path,PathBuf},time::{Duration,Instant}};

pub(crate) trait Transport {
    fn identity(&mut self)->Result<Vec<u8>,String>;
    fn status(&mut self)->Result<Vec<u8>,String>;
    fn write_control(&mut self,wire:&[u8])->Result<(),String>;
    /// The existing negotiated recording link sends this request and waits for CSN1.
    fn capacity_slots(&mut self,wire:&[u8])->Result<Option<Vec<u8>>,String>;
}

#[derive(serde::Serialize)]
#[serde(rename_all="camelCase")]
pub(crate) struct Report {
    pub host_session:String,pub state:&'static str,pub recording_key:Option<crate::companion_v1::CompanionV1RecordingKey>,
    pub anchor:Option<u32>,pub duration_ms:u32,pub finished_locally:bool,
}
#[derive(serde::Serialize)]
#[serde(rename_all="camelCase")]
pub(crate) struct Inventory {pub sessions:Vec<InventoryItem>,pub unreadable_count:usize}
#[derive(serde::Serialize)]
#[serde(rename_all="camelCase")]
pub(crate) struct InventoryItem {
    host_session:String,state:&'static str,recording_key:Option<crate::companion_v1::CompanionV1RecordingKey>,
    anchor:Option<u32>,duration_ms:u32,pending_command:Option<u8>,max_seconds:u16,
}

fn journal_name(host:&str)->String {format!("{:x}.json",Sha256::digest(host.as_bytes()))}
fn device_dir(root:&Path,device:&str)->Result<PathBuf,String> {
    if !root.is_absolute()||!device_connection::stable_device_id(device){return Err("录音控制目录或设备身份无效。".into());}
    let id=device.chars().filter(|c|c.is_ascii_hexdigit()).flat_map(char::to_uppercase).collect::<String>();
    Ok(root.join("recorder-control").join(id))
}
fn read_journal(path:&Path)->Result<Option<Journal>,String> {
    let metadata=match fs::symlink_metadata(path) {Ok(m)=>m,Err(e) if e.kind()==std::io::ErrorKind::NotFound=>return Ok(None),Err(_)=>return Err("无法读取原录音控制记录。".into())};
    if !metadata.is_file()||metadata.file_type().is_symlink()||metadata.len()>8192{return Err("原录音控制记录不可读取；原音保留。".into());}
    let bytes=fs::read(path).map_err(|_|"无法读取原录音控制记录。")?;
    serde_json::from_slice(&bytes).map(Some).map_err(|_|"原录音控制记录损坏；原音保留。".into())
}
fn save(path:&Path,journal:&Journal)->Result<(),String> {
    let bytes=serde_json::to_vec(journal).map_err(|_|"无法保存录音控制记录。")?;
    if bytes.len()>8192{return Err("录音控制记录过大；原音保留。".into());}
    export::write_atomic(path,&bytes).map(|_|()).map_err(|_|"无法保存录音控制记录，未发送新命令。".into())
}
/// Find persisted sessions for the selected device without sending control commands.
pub(crate) fn inventory(root:&Path,device:&str,identity:&[u8])->Result<Inventory,String> {
    let dir=device_dir(root,device)?;let peer=PausePeer::from_status(identity)?.ok_or("设备不支持当前录音控制。")?;
    if !dir.exists(){return Ok(Inventory{sessions:vec![],unreadable_count:0});}
    let lock=OpenOptions::new().read(true).write(true).create(true).truncate(false).open(dir.join("control.lock")).map_err(|_|"录音控制记录暂不可用。")?;
    lock.try_lock().map_err(|_|"该设备正在处理另一项录音操作。")?;
    let mut sessions=Vec::new();let mut unreadable=0;
    for item in fs::read_dir(&dir).map_err(|_|"无法检查录音控制记录。")? {
        let path=item.map_err(|_|"无法检查录音控制记录。")?.path();if path.extension().is_none_or(|e|e!="json"){continue;}
        let record=read_journal(&path).and_then(|j|j.ok_or("控制记录已消失。".into()));
        let journal=match record {Ok(j) if path.file_name().is_some_and(|n|n==journal_name(&j.host_session).as_str()) && j.matches(&peer,&j.host_session,device).is_ok()=>j,
            _=>{unreadable+=1;continue;}};
        let state=if journal.pending.is_some(){"pending"}else{match journal.confirmed.as_ref().map(|c|c.state){Some(1)=>"recording",Some(2)=>"stopped",Some(3)=>"paused",_=>"unknown"}};
        sessions.push(InventoryItem{host_session:journal.host_session.clone(),state,recording_key:journal.key.clone(),anchor:journal.anchor,
            duration_ms:journal.confirmed.as_ref().map_or(0,|c|c.duration_ms),pending_command:journal.pending.as_ref().map(|p|p.command),max_seconds:journal.max_seconds});
    }
    sessions.sort_by(|a,b|a.host_session.cmp(&b.host_session));Ok(Inventory{sessions,unreadable_count:unreadable})
}
fn validate_idle(raw:&[u8],peer:&PausePeer)->Result<(),String> {
    if raw.len()==80 {
        let s=PauseStatus::decode(raw)?;
        if (s.device_uid,s.format_epoch)!=peer.identity()||s.last_error!=0||!matches!(s.state,0|2) {
            return Err("设备正在录音或状态尚未确认；没有开始新录音。".into());
        }
    } else if raw.len()==64 {
        control::status(raw)?;
        let(uid,epoch)=peer.identity();
        if raw[32..44]!=uid||u64::from_le_bytes(raw[44..52].try_into().unwrap())!=epoch||raw[2]!=0||!matches!(raw[1],0|2) {
            return Err("设备状态与选中的录音卡不一致或正在录音。".into());
        }
    } else {return Err("设备录音状态暂不可确认；没有开始新录音。".into());}
    Ok(())
}
fn observation(journal:&mut Journal,peer:&PausePeer,raw:&[u8])->Result<Observation,String> {
    if raw.len()!=80 {
        if journal.unconfirmed_start_retry(){validate_idle(raw,peer)?;return Ok(Observation::Previous);}
        return Err("设备当前状态无法确认原录音，请重新连接后核对；原音保留。".into());
    }
    let s=PauseStatus::decode(raw)?;
    let anchor=u32::from_le_bytes(raw[12..16].try_into().unwrap());
    let duration=u32::from_le_bytes(raw[20..24].try_into().unwrap());
    journal.observe_with_peer(peer,&s,anchor,duration)
}

fn preflight<T:Transport>(transport:&mut T,identity:&[u8],peer:&Peer,seconds:u16,token:u32)->Result<(),String> {
    let Some(c)=capacity::parse(identity) else {
        if identity.get(36..40)==Some(b"CCQ2") {return Err("设备录音容量尚未准备好；没有开始录音。".into());}
        return Ok(());
    };
    let original=match capacity::check_start(&c,seconds,false){Ok(())=>return Ok(()),Err(e)=>e};
    let possible=match(c.segment_frames,c.segment_extent_bytes){(Some(frames),Some(extent)) if frames>0&&extent>0=>{
        let count=(u64::from(seconds)*50).div_ceil(u64::from(frames));
        count>0&&count<=u64::from(c.free_bytes/extent)&&count<=u64::from(c.max_entries.saturating_sub(c.used_entries))},_=>false};
    if !possible{return Err(original);}
    let mut request=[0u8;32];request[0]=2;request[1]=0x26;request[4..8].copy_from_slice(&token.to_le_bytes());
    request[8..20].copy_from_slice(&peer.uid);request[20..28].copy_from_slice(&peer.epoch.to_le_bytes());
    let crc=crc32fast::hash(&request[..28]);request[28..32].copy_from_slice(&crc.to_le_bytes());
    let Some(raw)=transport.capacity_slots(&request)? else{return Err(original);};
    let Some(count)=capacity::parse_slots_reply(&raw,&peer.uid,token,c.catalog_generation)? else{return Err(original);};
    let fresh=transport.identity()?;
    if Peer::from_status(&fresh)?.as_ref()!=Some(peer)||capacity::parse(&fresh).as_ref()!=Some(&c) {
        return Err("设备容量已变化，请重新开始；没有覆盖原音。".into());
    }
    capacity::check_start_with_slots(&c,seconds,false,count)
}

fn settle<T:Transport>(transport:&mut T,peer:&PausePeer,path:&Path,journal:&mut Journal,
    disposition:Observation,fresh_start:bool)->Result<(),String> {
    save(path,journal)?;
    let mut floor=None;
    let mut action=recorder_control::settlement_action(journal,disposition,true,fresh_start,&mut floor)?;
    let deadline=Instant::now()+Duration::from_secs(60);
    loop {
        match &action {SettlementAction::Complete=>return Ok(()),SettlementAction::Write(cmd)=>transport.write_control(&cmd.wire)?,SettlementAction::Wait=>{}}
        action=SettlementAction::Wait;
        if Instant::now()>=deadline{return Err("录音控制确认超时；原请求和录音保留，请重连核对。".into());}
        let wire=transport.status()?;
        if wire.len()==64&&journal.unconfirmed_start_retry(){validate_idle(&wire,peer)?;std::thread::sleep(Duration::from_millis(100));continue;}
        let disposition=observation(journal,peer,&wire)?;save(path,journal)?;
        action=recorder_control::settlement_action(journal,disposition,false,false,&mut floor)?;
        if matches!(action,SettlementAction::Wait){std::thread::sleep(Duration::from_millis(100));}
    }
}

/// Execute/query one original session. The OS lock covers journal and link operations.
pub(crate) fn execute<T:Transport>(root:&Path,host:&str,device:&str,command:u8,seconds:u16,transport:&mut T)->Result<Report,String> {
    if host.trim().is_empty()||host.len()>256||command>5||(command==1&&seconds==0)||(command!=1&&seconds!=0){return Err("录音操作参数不完整。".into());}
    let dir=device_dir(root,device)?;fs::create_dir_all(&dir).map_err(|_|"无法保存录音控制记录。")?;
    let lock=OpenOptions::new().read(true).write(true).create(true).truncate(false).open(dir.join("control.lock")).map_err(|_|"录音控制暂不可用。")?;
    lock.try_lock().map_err(|_|"该设备正在处理另一项录音操作。")?;
    let identity=transport.identity()?;let peer=PausePeer::from_status(&identity)?.ok_or("设备不支持当前录音控制。")?;
    let actual=Peer::from_status(&identity)?.ok_or("设备录音身份不可用。")?;
    let raw=transport.status()?;let path=dir.join(journal_name(host));
    let mut journal=match read_journal(&path)? {
        Some(j)=>{j.matches(&peer,host,device)?;if command==1&&j.max_seconds!=seconds{return Err("这次录音的原始时长与请求不同，请先核对原录音。".into());}j},
        None if command==1=>{
            for item in fs::read_dir(&dir).map_err(|_|"无法检查已有录音控制记录。")? {
                let path=item.map_err(|_|"无法检查已有录音控制记录。")?.path();
                if path.extension().is_none_or(|e|e!="json"){continue;}
                let old=read_journal(&path)?.ok_or("已有录音控制记录不可读取。")?;
                if path.file_name().is_none_or(|n|n!=journal_name(&old.host_session).as_str())||!device_connection::same_device_id(&old.device_id,device)||!old.ended(){
                    return Err("设备上有尚未确认的录音操作，请先恢复原录音。".into());
                }
            }
            validate_idle(&raw,&peer)?;
            let token=u32::from_le_bytes(uuid::Uuid::new_v4().as_bytes()[..4].try_into().unwrap()).max(1);
            preflight(transport,&identity,&actual,seconds,token)?;
            let j=Journal::start(&peer,host,device,token,seconds)?;save(&path,&j)?;j
        },
        None=>return Err("没有找到这次录音的控制记录。".into()),
    };
    let mut disposition=observation(&mut journal,&peer,&raw)?;save(&path,&journal)?;
    if disposition==Observation::Accepted || (matches!(command,0|2|3)&&journal.pending.is_some()) {
        settle(transport,&peer,&path,&mut journal,disposition,command==1)?;
        disposition=Observation::Previous;
    }
    if command!=0&&journal.prepare(&peer,command)? {
        save(&path,&journal)?;settle(transport,&peer,&path,&mut journal,disposition,command==1)?;
    }
    let confirmed=journal.confirmed.as_ref().ok_or("设备尚未确认录音状态；原请求保留。")?;
    let state=match confirmed.state {1=>"recording",2=>"stopped",3=>"paused",_=>return Err("设备录音状态尚未稳定。".into())};
    Ok(Report{host_session:host.into(),state,recording_key:journal.key.clone(),anchor:journal.anchor,duration_ms:confirmed.duration_ms,finished_locally:confirmed.finished_locally})
}

#[cfg(test)]
mod tests {
    use super::*;
    const DEVICE:&str="C8:92:FF:DD:3B:CA";
    fn vector(index:usize)->&'static [u8] {
        let golden=include_bytes!("../../../../windows/src-tauri/src/backend/cop1/tests/engine-pause-control.cpc3");
        &golden[8+index*137..8+(index+1)*137]
    }
    fn capability()->Vec<u8> {
        let mut s=vec![0;116];s[0]=1;s[12..16].copy_from_slice(&0x5742_4155u32.to_le_bytes());
        for(i,b)in s[20..32].iter_mut().enumerate(){*b=(i+1) as u8;}
        s[36..40].copy_from_slice(b"CCP1");s[40]=1;s[41]=1;s[43]=7;
        for(at,n)in [(48,8u32*1024*1024-8192),(52,8*1024*1024-8192),(56,8*1024*1024-8192),(68,2100),(72,4096),(76,1800)]{s[at..at+4].copy_from_slice(&n.to_le_bytes());}
        let p=&mut s[84..];p[..4].copy_from_slice(b"CRV2");p[4..6].copy_from_slice(&2u16.to_le_bytes());
        p[6..8].copy_from_slice(&32u16.to_le_bytes());p[8..12].copy_from_slice(&127u32.to_le_bytes());p[12..20].copy_from_slice(&7u64.to_le_bytes());
        p[20..22].copy_from_slice(&64u16.to_le_bytes());p[22..24].copy_from_slice(&1024u16.to_le_bytes());p[24..26].copy_from_slice(&248u16.to_le_bytes());
        let crc=crc32fast::hash(&p[..28]);p[28..32].copy_from_slice(&crc.to_le_bytes());s
    }
    fn crc_status(raw:&mut [u8]){let crc=crc32fast::hash(&raw[..76]);raw[76..80].copy_from_slice(&crc.to_le_bytes());}
    struct Fake {identity:Vec<u8>,status:Vec<u8>,writes:Vec<Vec<u8>>,fail_after_write:bool,fail_before_write:bool,slots:Option<u8>}
    impl Fake {
        fn new()->Self {let mut status=vector(0)[56..136].to_vec();status[1]=2;crc_status(&mut status);
            Self{identity:capability(),status,writes:vec![],fail_after_write:false,fail_before_write:false,slots:None}}
        fn fragmented(&mut self) {
            let s=&mut self.identity;s[36..40].copy_from_slice(b"CCQ2");s[40]=3;s[41]=1;s[42]=1;s[43]=64;
            for(at,n)in [(44,4u32),(48,0x100000),(52,0xf0000),(56,0x50000),(60,0x10000),(64,0),(68,6400),(72,0x50000),(76,1800)]{s[at..at+4].copy_from_slice(&n.to_le_bytes());}
            s[80]=1;s[81]=0;s[82]=0;self.slots=Some(3);
        }
    }
    impl Transport for Fake {
        fn identity(&mut self)->Result<Vec<u8>,String>{Ok(self.identity.clone())}
        fn status(&mut self)->Result<Vec<u8>,String>{Ok(self.status.clone())}
        fn write_control(&mut self,wire:&[u8])->Result<(),String> {
            if self.fail_before_write{self.fail_before_write=false;return Err("synthetic write failure".into());}
            self.writes.push(wire.to_vec());let index=match wire[5]{1=>0,4=>2,5=>5,2=>8,_=>return Err("unexpected command".into())};
            let mut status=vector(index)[56..136].to_vec();status[8..12].copy_from_slice(&wire[36..40]);status[60..64].copy_from_slice(&wire[48..52]);crc_status(&mut status);self.status=status;
            if self.fail_after_write{self.fail_after_write=false;return Err("synthetic lost write confirmation".into());}Ok(())
        }
        fn capacity_slots(&mut self,wire:&[u8])->Result<Option<Vec<u8>>,String> {
            let Some(count)=self.slots else{return Ok(None)};
            let mut out=vec![0;32];out[..4].copy_from_slice(b"CSN1");out[4..8].copy_from_slice(&wire[4..8]);out[8..12].copy_from_slice(&self.identity[44..48]);
            out[12]=count;out[16..28].copy_from_slice(&wire[8..20]);let crc=crc32fast::hash(&out[..28]);out[28..32].copy_from_slice(&crc.to_le_bytes());Ok(Some(out))
        }
    }
    fn root()->PathBuf {std::env::temp_dir().join(format!("companion-control-test-{}",uuid::Uuid::new_v4()))}
    fn cleanup(root:&Path) {
        let r=root.canonicalize().unwrap();let temp=std::env::temp_dir().canonicalize().unwrap();
        assert!(r.parent()==Some(temp.as_path())&&r.file_name().unwrap().to_string_lossy().starts_with("companion-control-test-"));
        fs::remove_dir_all(r).unwrap();
    }
    #[test]
    fn start_pause_resume_stop_are_persisted_and_bound_to_same_original() {
        let root=root();let mut fake=Fake::new();
        for (cmd,seconds,wanted) in [(1,120,"recording"),(4,0,"paused"),(5,0,"recording"),(2,0,"stopped")] {
            let report=execute(&root,"synthetic-session",DEVICE,cmd,seconds,&mut fake).unwrap();
            assert_eq!(report.state,wanted);assert!(report.recording_key.is_some());assert_eq!(report.anchor,Some(1));
        }
        assert_eq!(fake.writes.iter().map(|w|w[5]).collect::<Vec<_>>(),[1,4,5,2]);
        let path=device_dir(&root,DEVICE).unwrap().join(journal_name("synthetic-session"));assert!(read_journal(&path).unwrap().unwrap().ended());
        cleanup(&root);
    }
    #[test]
    fn lost_write_confirmation_queries_same_session_without_second_start() {
        let root=root();let mut fake=Fake::new();fake.fail_after_write=true;
        assert!(execute(&root,"synthetic-session",DEVICE,1,120,&mut fake).is_err());
        let inventory=inventory(&root,DEVICE,&fake.identity).unwrap();assert_eq!(inventory.sessions.len(),1);
        assert_eq!(inventory.sessions[0].host_session,"synthetic-session");assert_eq!(inventory.sessions[0].state,"pending");
        let report=execute(&root,"synthetic-session",DEVICE,0,0,&mut fake).unwrap();
        assert_eq!(report.state,"recording");assert_eq!(fake.writes.len(),1);cleanup(&root);
    }
    #[test]
    fn unsent_start_is_never_automatically_restarted_and_explicit_retry_is_identical() {
        let root=root();let mut fake=Fake::new();fake.fail_before_write=true;
        assert!(execute(&root,"synthetic-session",DEVICE,1,120,&mut fake).is_err());
        let file=device_dir(&root,DEVICE).unwrap().join(journal_name("synthetic-session"));let original=read_journal(&file).unwrap().unwrap().pending.unwrap().wire;
        assert!(execute(&root,"synthetic-session",DEVICE,0,0,&mut fake).is_err());assert!(fake.writes.is_empty());
        assert!(execute(&root,"synthetic-session",DEVICE,1,121,&mut fake).is_err());assert!(fake.writes.is_empty());
        assert_eq!(execute(&root,"synthetic-session",DEVICE,1,120,&mut fake).unwrap().state,"recording");
        assert_eq!(fake.writes,[original]);cleanup(&root);
    }
    #[test]
    fn another_session_or_unreadable_original_cannot_silently_start() {
        let root=root();let mut fake=Fake::new();execute(&root,"session-a",DEVICE,1,120,&mut fake).unwrap();
        assert!(execute(&root,"session-b",DEVICE,1,120,&mut fake).is_err());assert_eq!(fake.writes.len(),1);
        let file=device_dir(&root,DEVICE).unwrap().join(journal_name("session-a"));fs::write(file,b"damaged").unwrap();
        assert!(execute(&root,"session-b",DEVICE,1,120,&mut fake).is_err());assert_eq!(fake.writes.len(),1);cleanup(&root);
    }
    #[test]
    fn fragmented_free_space_uses_matching_capacity_snapshot() {
        let root=root();let mut fake=Fake::new();fake.fragmented();
        assert_eq!(execute(&root,"synthetic-session",DEVICE,1,200,&mut fake).unwrap().state,"recording");
        assert_eq!(fake.writes.len(),1);cleanup(&root);
    }
}
