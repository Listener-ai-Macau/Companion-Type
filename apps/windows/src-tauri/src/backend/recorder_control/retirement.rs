//! Explicit meeting deletion also retires its completed control sidecar.
//! Hold the original cross-process locks until the sanitized index is saved.
use super::*;
use crate::companion_v1::{CompanionV1ControlAction as Action,CompanionV1ControlRequest,
    CompanionV1HostSession,CompanionV1Snapshot};

pub(crate) struct PrivacyRetirement { stores:Vec<Store> }
impl PrivacyRetirement {
    pub(crate) fn erase(&mut self)->Result<usize,String> {
        let mut count=0;
        for store in &self.stores {
            match fs::remove_file(&store.path) {
                Ok(())=>count+=1,
                Err(e) if e.kind()==ErrorKind::NotFound=>{},
                Err(e)=>return Err(failure(&format!("清除已结束录音控制记录失败，会议尚未清除：{e}"))),
            }
        }
        Ok(count)
    }
}

fn journal_path(state:&Path,host:&str)->Result<PathBuf,String> {
    let parent=state.parent().filter(|p|!p.as_os_str().is_empty()).ok_or("会议库路径无效")?;
    Ok(parent.join("recorder-controls").join(format!("{:x}.json",Sha256::digest(host.as_bytes()))))
}
fn retain_store(state:&Path,host:&str,row:Option<&CompanionV1HostSession>)->Result<Option<Store>,String> {
    let path=journal_path(state,host)?;
    match fs::symlink_metadata(&path) {
        Err(e) if e.kind()==ErrorKind::NotFound=>return Ok(None),
        Err(e)=>return Err(failure(&format!("读取控制记录身份：{e}"))),
        Ok(meta) if !meta.is_file() || meta.file_type().is_symlink()=>return Err(failure("控制记录不是原有普通文件，未清除")),
        Ok(_)=>{},
    }
    let store=Store::open(state,host)?;
    let j=store.journal.as_ref().ok_or("原录音控制记录在核对期间改变，未清除")?;
    j.validate_sealed_end()?;
    if (!j.ended() && j.pending.is_some()) || !j.confirmed.as_ref().is_some_and(|c|matches!(c.state,1|2|3))
        || j.key.is_none() || !j.anchor.is_some_and(|id|id>0) {
        return Err("原录音命令尚未核对为结束，未清除恢复记录；请先核对原录音。".into());
    }
    let ended=j.ended();
    if let Some(row)=row {
        if row.status=="recording" || row.recorder_control_uncertain {
            return Err("原录音仍在进行或待核对，未删除恢复记录。".into());
        }
        j.checkpoint_row(&mut row.clone())?;
        if !ended {
            crate::backend::recording_wire::receiver::Receiver::verify_closed_original(row,j.anchor.unwrap())
                .map_err(|_|"原录音的封口原件尚未完整核对，未清除恢复记录；请先同步原录音。".to_string())?;
        }
    } else if !ended {
        // Without its bound library row an old START has no closed-original
        // proof. Erase-all still cannot guess that a pending capture ended.
        return Err("旧录音没有已核对的结束状态或完整原音，恢复记录保留。".into());
    }
    Ok(Some(store))
}

pub(crate) fn prepare_privacy_retirement(snapshot:&CompanionV1Snapshot,request:&CompanionV1ControlRequest,
    state:&Path)->Result<Option<PrivacyRetirement>,String> {
    let all=request.action==Action::PrivacyEraseAll;
    if !all && request.action!=Action::PrivacyDeleteSession {return Ok(None);}
    let selected=request.session_id.as_deref();
    let mut hosts=std::collections::BTreeSet::new();
    for row in &snapshot.host.sessions {
        if all || selected==Some(row.id.as_str()) {hosts.insert(row.id.clone());}
    }
    // An earlier deleted meeting can leave a finished orphan after an old app
    // or a failed cleanup. Erase-all explicitly includes these private records;
    // unknown or pending controls never become guessed completed captures.
    if all {
        let root=state.parent().ok_or("会议库路径无效")?.join("recorder-controls");
        match fs::read_dir(&root) {
            Err(e) if e.kind()==ErrorKind::NotFound=>{},
            Err(e)=>return Err(failure(&format!("读取旧控制记录：{e}"))),
            Ok(entries)=>for entry in entries {
                let entry=entry.map_err(|e|failure(&format!("读取旧控制记录：{e}")))?;
                if entry.path().extension().is_none_or(|x|x!="json") {continue;}
                let meta=entry.path().symlink_metadata().map_err(|e|failure(&e.to_string()))?;
                if !meta.is_file() || meta.file_type().is_symlink() || meta.len()>8192 {
                    return Err(failure("旧控制记录无法核对，未清除恢复资料"));
                }
                let bytes=fs::read(entry.path()).map_err(|e|failure(&e.to_string()))?;
                let j:Journal=serde_json::from_slice(&bytes).map_err(|_|failure("旧控制记录损坏，未清除恢复资料"))?;
                if journal_path(state,&j.host_session)?!=entry.path() {
                    return Err(failure("旧控制记录文件与会话身份不同，未清除"));
                }
                hosts.insert(j.host_session);
            },
        }
    }
    let mut stores=Vec::new();
    for host in hosts {
        let row=snapshot.host.sessions.iter().find(|row|row.id==host);
        if let Some(store)=retain_store(state,&host,row)? {stores.push(store);}
    }
    Ok(Some(PrivacyRetirement{stores}))
}
