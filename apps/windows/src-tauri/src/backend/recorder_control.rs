//! A durable, exact CMC3 intent. A timeout preserves the same command bytes.
//! The device's CRC-checked CMS3, rather than the requested UI state, confirms it.
use std::{fs::{self, File, OpenOptions}, io::ErrorKind, path::{Path, PathBuf}};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use super::recording_wire::{SessionKey, control::{PausePeer, PauseStatus}};
use crate::companion_v1::CompanionV1RecordingKey;

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all="camelCase", deny_unknown_fields)]
pub(crate) struct Command {
    pub(crate) command: u8,
    pub(crate) request: u32,
    pub(crate) sequence: u32,
    /// Exact bytes are committed before a protected GATT write is allowed.
    pub(crate) wire: Vec<u8>,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all="camelCase", deny_unknown_fields)]
pub(crate) struct Confirmed {
    pub(crate) command: u8,
    pub(crate) request: u32,
    pub(crate) sequence: u32,
    pub(crate) state: u8,
    pub(crate) duration_ms: u32,
    /// The device sealed this same capture locally (capacity/button/time).
    /// Keep its actual last command; never manufacture a STOP acknowledgement.
    #[serde(default)]
    pub(crate) finished_locally: bool,
    #[serde(default)]
    pub(crate) local_control: bool,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all="camelCase", deny_unknown_fields)]
pub struct Journal {
    schema: u8,
    pub(crate) host_session: String,
    pub(crate) device_id: String,
    uid: [u8;12],
    epoch: u64,
    pub(crate) start_request: u32,
    pub(crate) max_seconds: u16,
    pub(crate) key: Option<CompanionV1RecordingKey>,
    pub(crate) anchor: Option<u32>,
    pub(crate) confirmed: Option<Confirmed>,
    pub(crate) pending: Option<Command>,
    /// Most recent outstanding host command displaced by a newer, verified
    /// physical control. Keep its exact bytes; it was not acknowledged.
    #[serde(default, skip_serializing_if="Option::is_none")]
    pub(crate) superseded: Option<Command>,
    /// A later protected, complete sealed catalogue can prove an old capture
    /// ended after its live CMS3 identity was replaced. This is NOT a STOP ACK.
    #[serde(default, skip_serializing_if="Option::is_none")]
    pub(crate) sealed_catalogue_end: Option<SealedCatalogueEnd>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Observation {
    /// The protected device still names the last confirmed command. A pending
    /// command may be written, but no different sequence may replace it.
    Previous,
    /// The device accepted this sequence and is draining/starting. Do not resend.
    Accepted,
    /// The requested stable state was actually reached.
    Confirmed,
}

fn failure(reason: &str) -> String { format!("录音控制尚未核对，原会话与命令保留：{reason}") }
fn same_device(left: &str, right: &str) -> bool {
    super::device_connection::stable_device_id(left)
        && super::device_connection::stable_device_id(right)
        && super::device_connection::same_device_id(left,right)
}
fn stable_state(command: u8) -> Option<u8> {
    match command {1|5=>Some(1),2|3=>Some(2),4=>Some(3),_=>None}
}

impl Journal {
    pub(crate) fn unconfirmed_start_retry(&self)->bool {
        self.confirmed.is_none() && self.key.is_none() && self.anchor.is_none()
            && self.pending.as_ref().is_some_and(|pending|pending.command==1
                && pending.request==self.start_request && pending.sequence==0)
    }
    pub(crate) fn start(peer: &PausePeer, host_session: &str, device_id: &str,
        request: u32, max_seconds: u16) -> Result<Self,String> {
        if host_session.trim().is_empty() || host_session.len()>256 || !same_device(device_id,device_id) {
            return Err(failure("开始请求缺少稳定的主机／设备身份"));
        }
        let (uid,epoch)=peer.identity();
        let wire=peer.request(None,1,request,request,max_seconds,0,true)?.to_vec();
        Ok(Self{schema:1,host_session:host_session.into(),device_id:device_id.into(),uid,epoch,
            start_request:request,max_seconds,key:None,anchor:None,confirmed:None,
            pending:Some(Command{command:1,request,sequence:0,wire}),superseded:None,sealed_catalogue_end:None})
    }

    pub(crate) fn matches(&self, peer: &PausePeer, host: &str, device: &str) -> Result<(),String> {
        if self.schema!=1 || self.host_session!=host || !same_device(&self.device_id,device)
            || (self.uid,self.epoch)!=peer.identity() || self.start_request==0 {
            return Err(failure("主机、蓝牙地址、芯片或格式代次与原命令不同"));
        }
        let key=self.key.as_ref().map(SessionKey::from_public).transpose()?;
        if key.as_ref().is_some_and(|key| (key.device_uid,key.format_epoch)!=(self.uid,self.epoch))
            || self.anchor.is_some_and(|id| id==0) || self.anchor.is_some()!=key.is_some()
            || self.confirmed.is_some()!=key.is_some() || (self.pending.is_none() && self.confirmed.is_none()) {
            return Err(failure("耐久会话身份或确认记录不完整"));
        }
        if let Some(confirmed)=self.confirmed.as_ref() {
            if confirmed.request==0 || (!confirmed.finished_locally && stable_state(confirmed.command)!=Some(confirmed.state))
                || (confirmed.finished_locally && (confirmed.state!=2 || !matches!(confirmed.command,1|4|5)))
                || (confirmed.sequence==0)!=(confirmed.command==1)
                || (confirmed.command==1 && confirmed.request!=self.start_request) {
                return Err(failure("耐久确认的命令／序号／状态不一致"));
            }
            if confirmed.local_control && !matches!(confirmed.command,1|4|5) {
                return Err(failure("本地操作不能冒充电脑停止确认"));
            }
        }
        if let Some(previous)=self.superseded.as_ref() {
            let expected=peer.request(key.as_ref(),previous.command,previous.request,self.start_request,
                0,previous.sequence,false)?;
            if previous.command==1 || previous.wire!=expected || self.confirmed.as_ref()
                .is_none_or(|c|previous.sequence>c.sequence && !(c.finished_locally &&
                    matches!(previous.command,2|3) && c.sequence.checked_add(1)==Some(previous.sequence))) {
                return Err(failure("被本地操作取代的原命令记录不一致"));
            }
        }
        if let Some(pending)=self.pending.as_ref() {
            let expected_sequence=self.confirmed.as_ref().map_or(Some(0),|c|c.sequence.checked_add(1));
            if expected_sequence!=Some(pending.sequence) || (pending.command==1)!=self.confirmed.is_none() {
                return Err(failure("待发命令没有紧随已确认序号"));
            }
            let expected=peer.request(key.as_ref(),pending.command,pending.request,self.start_request,
                if pending.command==1 {self.max_seconds}else{0},pending.sequence,pending.command==1)?;
            if pending.wire!=expected {return Err(failure("待发字节与耐久会话／序号不一致"));}
        }
        self.validate_sealed_end()?;
        Ok(())
    }

    /// Repeated clicks/restart retries preserve an unresolved intent. They may
    /// not turn a lost PAUSE response into a fresh RESUME or a new recording.
    pub(crate) fn prepare(&mut self, peer: &PausePeer, command: u8) -> Result<bool,String> {
        self.matches(peer,&self.host_session,&self.device_id)?;
        if self.sealed_catalogue_end.is_some() {return Err(failure("原录音已由封口目录确认结束，未重发旧控制或重开"));}
        if let Some(pending)=self.pending.as_ref() {
            if pending.command!=command {return Err(failure("请先核对上一次控制结果，再发送下一项操作"));}
            return Ok(true);
        }
        let prior=self.confirmed.as_ref().ok_or_else(||failure("尚无设备开始确认"))?;
        if command==1 {
            if prior.command==1 && prior.sequence==0 && prior.state==1 {return Ok(false);}
            return Err(failure("这场录音已经开始，不能重开"));
        }
        let wanted=stable_state(command).ok_or_else(||failure("未知控制命令"))?;
        if prior.state==wanted {return Ok(false);}
        if prior.state==2 || (command==4 && prior.state!=1) || (command==5 && prior.state!=3) {
            return Err(failure("这场录音已经结束或不处于可执行的状态"));
        }
        let sequence=prior.sequence.checked_add(1).ok_or_else(||failure("控制序号已耗尽"))?;
        // Reserve the final sequence for STOP even after very many pauses.
        if matches!(command,4|5) && sequence==u32::MAX {return Err(failure("请先结束录音，暂停序号已耗尽"));}
        let mut hash=Sha256::new();hash.update(b"Companion-CMC3-command-v1\0");
        hash.update(self.host_session.as_bytes());hash.update(self.uid);hash.update(self.epoch.to_le_bytes());
        hash.update(self.start_request.to_le_bytes());hash.update(sequence.to_le_bytes());hash.update([command]);
        let request=u32::from_le_bytes(hash.finalize()[..4].try_into().unwrap()).max(1);
        let key=SessionKey::from_public(self.key.as_ref().ok_or_else(||failure("原逻辑会话缺失"))?)?;
        let wire=peer.request(Some(&key),command,request,self.start_request,0,sequence,false)?.to_vec();
        self.pending=Some(Command{command,request,sequence,wire});Ok(true)
    }

    pub(crate) fn observe(&mut self, status: &PauseStatus, anchor: u32, duration: u32)
        -> Result<Observation,String> {
        if status.local_start.is_some() {
            return Err(failure("本地操作需要按原设备和原开始请求核对"));
        }
        if self.sealed_catalogue_end.is_some() {return Err(failure("原录音已封口，不能用后来的实时控制替换目录证据"));}
        if (status.device_uid,status.format_epoch)!=(self.uid,self.epoch) {
            return Err(failure("控制确认的芯片或格式代次不同"));
        }
        let key=status.key.as_ref();
        let key_matches=key.is_some_and(|key| key.device_uid==self.uid && key.format_epoch==self.epoch)
            && self.key.as_ref().is_none_or(|saved| key.map(SessionKey::public_key).as_ref()==Some(saved));
        let anchor_matches=anchor!=0 && self.anchor.is_none_or(|saved|anchor==saved);
        // A physical button/capacity/time limit can seal a capture without a
        // new host command. Only the exact pending/confirmed identity may end
        // the row. Idle, a later session or a fabricated STOP cannot do so.
        let local_finish = status.state==2 && status.timeline && status.last_error==0
            && key_matches && anchor_matches && matches!(status.command,1|4|5)
            && self.confirmed.as_ref().is_none_or(|c| duration>=c.duration_ms)
            && (self.pending.as_ref().is_some_and(|p| p.command==status.command
                && p.request==status.request && p.sequence==status.sequence)
                || (self.pending.as_ref().is_none_or(|p|p.command!=1) && self.confirmed.as_ref().is_some_and(|c|
                    c.command==status.command && c.request==status.request && c.sequence==status.sequence)));
        if local_finish {
            self.key=key.map(SessionKey::public_key);self.anchor=Some(anchor);
            self.confirmed=Some(Confirmed{command:status.command,request:status.request,sequence:status.sequence,
                state:2,duration_ms:duration,finished_locally:true,local_control:false});
            self.pending=None;return Ok(Observation::Confirmed);
        }
        if let Some(pending)=self.pending.as_ref() {
            if status.request==pending.request && status.sequence==pending.sequence && status.command==pending.command {
                // The real firmware first acknowledges START preparation,
                // before NOR allocation assigns the logical key and anchor.
                // This exact CRC-checked command is accepted, never confirmed
                // or resent; retain its durable intent until actual capture.
                if pending.command==1 && pending.sequence==0 && self.confirmed.is_none()
                    && self.key.is_none() && self.anchor.is_none() && status.state==0
                    && status.key.is_none() && anchor==0 && duration==0
                    && status.timeline && status.last_error==0 {
                    return Ok(Observation::Accepted);
                }
                if !key_matches || !anchor_matches || !status.timeline || status.last_error!=0
                    || self.confirmed.as_ref().is_some_and(|c| duration<c.duration_ms) {
                    return Err(failure("设备拒绝或返回了不同的会话／时间轴"));
                }
                let key=key.unwrap();
                if status.confirms(key,pending.command,pending.request,pending.sequence) {
                    let confirmed=Confirmed{command:pending.command,request:pending.request,sequence:pending.sequence,
                        state:status.state,duration_ms:duration,finished_locally:false,local_control:false};
                    self.key=Some(key.public_key());self.anchor=Some(anchor);self.confirmed=Some(confirmed);
                    self.pending=None;return Ok(Observation::Confirmed);
                }
                let transitional=match pending.command {1|5=>5,2|3=>6,4=>4,_=>255};
                // A local cancellation/capacity stop can drain the accepted
                // START before its first PCM block. Wait for this exact
                // command's final state; never resend START or claim capture.
                if pending.command==1 && status.state==6 {return Ok(Observation::Accepted);}
                if status.state==transitional {return Ok(Observation::Accepted);}
                return Err(failure("设备尚未到达请求的稳定状态"));
            }
        }
        if let Some(confirmed)=self.confirmed.as_mut() {
            if key_matches && anchor_matches && status.timeline && status.last_error==0
                && status.request==confirmed.request && status.sequence==confirmed.sequence
                && status.command==confirmed.command && status.state==confirmed.state
                && duration>=confirmed.duration_ms {
                confirmed.duration_ms=duration;
                return Ok(Observation::Previous);
            }
        } else if self.pending.as_ref().is_some_and(|p|p.command==1) && status.last_error==0
            && matches!(status.state,0|2) {
            // Protected idle/finalized is not a START confirmation. It merely
            // permits writing the already-durable new START to this known peer.
            return Ok(Observation::Previous);
        }
        // Keep the actual rejected observation once, outside the capture path.
        // A user-facing error alone cannot distinguish a locally ended
        // capture, device error, stale ACK, or another recording identity.
        eprintln!("recorder_control observation_mismatch state={} command={} request={} sequence={} error={} timeline={} anchor={} duration_ms={} key_matches={} anchor_matches={} confirmed={:?} pending={:?}",
            status.state,status.command,status.request,status.sequence,status.last_error,status.timeline,
            anchor,duration,key_matches,anchor_matches,self.confirmed,
            self.pending.as_ref().map(|p|(p.command,p.request,p.sequence)));
        Err(failure("设备状态既不属于待确认命令，也不属于上次确认"))
    }

    /// A physical action can race an outstanding host write. Its protected
    /// origin, original START, full key, anchor and monotonic sequence must all
    /// match. Preserve a displaced intent; STOP is rebased, never dropped.
    pub(crate) fn observe_with_peer(&mut self, peer:&PausePeer, status:&PauseStatus,
        anchor:u32, duration:u32)->Result<Observation,String> {
        if status.local_start.is_none() {return self.observe(status,anchor,duration);}
        self.matches(peer,&self.host_session,&self.device_id)?;
        let previous=self.confirmed.as_ref().ok_or_else(||failure("原开始尚未确认，不能由本地状态替代"))?;
        if self.sealed_catalogue_end.is_some() || status.local_start!=Some(self.start_request)
            || (status.device_uid,status.format_epoch)!=(self.uid,self.epoch)
            || status.key.as_ref().map(SessionKey::public_key).as_ref()!=self.key.as_ref()
            || self.anchor!=Some(anchor) || anchor==0 || !status.timeline || status.last_error!=0
            || duration<previous.duration_ms || status.sequence<previous.sequence
            || (status.sequence==previous.sequence && (!previous.local_control ||
                previous.command!=status.command || previous.request!=status.request)) {
            return Err(failure("本地控制不属于同一原录音或序号已过期"));
        }
        let stable=stable_state(status.command).ok_or_else(||failure("未知本地操作"))?;
        let transition=match status.command {4=>4,5=>5,_=>255};
        if status.state==transition {return Ok(Observation::Accepted);}
        if status.state!=stable && status.state!=2 {return Err(failure("本地操作尚未到达稳定状态"));}
        if status.sequence==previous.sequence && status.state==previous.state {
            self.confirmed.as_mut().unwrap().duration_ms=duration;
            return Ok(Observation::Previous);
        }
        let mut next=self.clone();
        let displaced=next.pending.take();
        if let Some(pending)=displaced.as_ref() {
            if pending.command==1 || (pending.sequence>status.sequence &&
                !(status.state==2 && matches!(pending.command,2|3) &&
                  status.sequence.checked_add(1)==Some(pending.sequence))) {
                return Err(failure("本地状态未覆盖原待确认命令"));
            }
            next.superseded=Some(pending.clone());
        }
        next.confirmed=Some(Confirmed{command:status.command,request:status.request,
            sequence:status.sequence,state:status.state,duration_ms:duration,
            finished_locally:status.state==2,local_control:true});
        let stop=displaced.as_ref().filter(|p|matches!(p.command,2|3)).map(|p|p.command);
        let observation=if let Some(stop)=stop.filter(|_|status.state!=2) {
            next.prepare(peer,stop)?;Observation::Previous
        } else {Observation::Confirmed};
        next.matches(peer,&next.host_session,&next.device_id)?;
        *self=next;Ok(observation)
    }
}

/// The cross-process lock spans the complete command/status operation. A
/// corrupt/unknown journal is not an empty journal and cannot authorize START.
pub(crate) struct Store { path:PathBuf, state_path:PathBuf, _lock:File, pub(crate) journal:Option<Journal> }
impl Store {
    pub(crate) fn open(state_path:&Path, host_session:&str)->Result<Self,String> {
        if host_session.trim().is_empty() || host_session.len()>256 {return Err(failure("主机会话编号无效"));}
        let parent=state_path.parent().filter(|p|!p.as_os_str().is_empty()).ok_or_else(||failure("会议库路径无效"))?;
        let root=parent.join("recorder-controls");fs::create_dir_all(&root).map_err(|e|failure(&format!("创建命令目录：{e}")))?;
        let name=format!("{:x}",Sha256::digest(host_session.as_bytes()));let path=root.join(format!("{name}.json"));
        let lock=OpenOptions::new().read(true).write(true).create(true).truncate(false)
            .open(root.join(format!("{name}.lock"))).map_err(|e|failure(&format!("打开命令锁：{e}")))?;
        lock.try_lock().map_err(|e|failure(&format!("另一进程正在控制这场录音：{e}")))?;
        let journal=match fs::read(&path) {
            Ok(bytes) if bytes.len()<=8192=>Some(serde_json::from_slice::<Journal>(&bytes)
                .map_err(|e|failure(&format!("原命令记录损坏：{e}")))?),
            Ok(_)=>return Err(failure("原命令记录过大")),
            Err(e) if e.kind()==ErrorKind::NotFound=>None,
            Err(e)=>return Err(failure(&format!("读取原命令：{e}"))),
        };
        if journal.as_ref().is_some_and(|j|j.host_session!=host_session || j.schema!=1) {
            return Err(failure("原命令记录的主机身份／版本不一致"));
        }
        Ok(Self{path,state_path:state_path.to_owned(),_lock:lock,journal})
    }
    pub(crate) fn commit(&mut self, journal:Journal)->Result<(),String> {
        let bytes=serde_json::to_vec(&journal).map_err(|e|failure(&format!("保存原命令：{e}")))?;
        super::export::write_atomic(&self.path,&bytes)?;
        self.journal=Some(journal);Ok(())
    }

    /// Both the exact command and the discoverable original row must be
    /// durable before any GATT write. A failed index commit leaves the intent
    /// available for recovery, but never authorizes a write or a new START.
    pub(crate) fn commit_bound(&mut self, journal:Journal)->Result<(),String> {
        self.commit(journal.clone())?;
        super::session_store::update_checked(&self.state_path, |rows| {
            let row=rows.iter_mut().find(|row|row.id==journal.host_session)
                .ok_or_else(||failure("原录音尚未保存在会议库，未发送控制"))?;
            journal.checkpoint_row(row)?;Ok(())
        })
    }
}

mod application;
pub(crate) use application::{apply,restart_recovery_request,unconfirmed_start_retry_request};
mod catalogue;
pub(crate) use catalogue::SealedCatalogueEnd;
mod retirement;
pub(crate) use retirement::prepare_privacy_retirement;

#[cfg(test)]
mod tests;
