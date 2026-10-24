//! Device-authored schema3 marks arrive only through verified sealed payloads.
//! No GATT, clock estimate, cloud request or synthetic START is used here.
use super::Bookmark;
use crate::{backend::{cop1::Event,recording_wire::{Descriptor,SessionKey}},
    companion_v1::CompanionV1HostSession};
use sha2::{Digest,Sha256};
use std::collections::BTreeSet;

#[derive(Clone)]
pub(crate) struct DeviceMark { pub descriptor:Descriptor,pub event:Event }
impl DeviceMark {
    fn id(&self)->String {
        let mut hash=Sha256::new();hash.update(b"Companion-offline-bookmark-v1\0");
        hash.update(self.descriptor.key.device_uid);hash.update(self.descriptor.key.format_epoch.to_le_bytes());
        hash.update(self.descriptor.key.session_id.to_le_bytes());hash.update(self.event.sequence.to_le_bytes());
        let digest=hash.finalize();let mut bytes=[0;16];bytes.copy_from_slice(&digest[..16]);
        bytes[6]=(bytes[6]&15)|0x80;bytes[8]=(bytes[8]&63)|0x80;
        uuid::Uuid::from_bytes(bytes).to_string()
    }
    fn validate(&self,key:&SessionKey)->Result<(),String> {
        let _=self.descriptor.encode()?; // Same descriptor validation, no new trust bypass.
        let end=self.descriptor.sample_offset.checked_add(self.descriptor.sample_count).ok_or("重点源范围溢出。")?;
        if &self.descriptor.key!=key || self.event.kind!=4 || self.event.sequence==0
            || self.event.sample_offset%320!=0 || self.event.sample_offset<self.descriptor.sample_offset
            || self.event.sample_offset>end {
            return Err("设备重点不属于同一原音范围，原件已保留。".into());
        }
        Ok(())
    }
}

/// Called inside the original library transaction before consumption. The
/// import ledger also records deliberate deletions; source replay never
/// overwrites a user label or creates a deleted bookmark a second time.
pub(crate) fn merge(row:&mut CompanionV1HostSession,marks:&[DeviceMark],key:&SessionKey,
    captured_samples:Option<u64>)->Result<bool,String> {
    merge_with_origin(row,marks,key,captured_samples,320)
}
pub(crate) fn merge_with_origin(row:&mut CompanionV1HostSession,marks:&[DeviceMark],key:&SessionKey,
    captured_samples:Option<u64>,origin:u64)->Result<bool,String> {
    if ![0,320].contains(&origin){return Err("设备重点的源样本起点无效。".into());}
    if marks.is_empty() {return Ok(false);}
    if row.source!="boardDevice" || row.device_recording_key.as_ref()!=Some(&key.public_key())
        || row.source_device_id.as_deref().is_none_or(|s|!crate::backend::device_connection::stable_device_id(s))
        || marks.len()>1024 || row.device_bookmark_imports.len()>1024 || row.bookmarks.len()>1024 {
        return Err("设备重点的原录音归属或数量异常，未回收设备原音。".into());
    }
    let mut ids=row.device_bookmark_imports.iter().cloned().collect::<BTreeSet<_>>();
    if ids.len()!=row.device_bookmark_imports.len() || ids.iter().any(|id|uuid::Uuid::parse_str(id).is_err()) {
        return Err("设备重点接收记录异常，原件保留。".into());
    }
    let mut points=row.bookmarks.clone();let mut imported=row.device_bookmark_imports.clone();
    let mut last:Option<Event>=None;
    for mark in marks {
        mark.validate(key)?;
        if last.is_some_and(|e|mark.event.sequence<=e.sequence || mark.event.sample_offset<e.sample_offset
            || mark.event.elapsed_ms<e.elapsed_ms) {return Err("设备重点序号或时间倒退，未回收设备原音。".into());}
        last=Some(mark.event);
        let id=mark.id();let position_ms=mark.event.sample_offset/16;
        let audio_position_ms=if let Some(samples)=captured_samples {
            if mark.event.sample_offset>samples || samples<origin {return Err("设备重点超过已保存原音范围。".into());}
            Some(mark.event.sample_offset.saturating_sub(origin)/16)
        } else {None};
        let hash=mark.descriptor.sha256.iter().map(|v|format!("{v:02x}")).collect::<String>();
        let existing=points.iter_mut().filter(|p|p.id==id).collect::<Vec<_>>();
        if existing.len()>1 {return Err("设备重点在资料库中重复，原件保留。".into());}
        if ids.contains(&id) {
            if let Some(point)=existing.into_iter().next() {
                if point.origin!="boardOffline" || point.position_ms!=position_ms
                    || point.source_recording_key.as_ref()!=Some(&key.public_key())
                    || point.recording_id!=Some(mark.descriptor.recording_id)
                    || point.source_sha256.as_deref()!=Some(hash.as_str())
                    || point.source_device_id.as_deref()!=row.source_device_id.as_deref() {
                    return Err("已接收重点的原音身份发生变化，未覆盖用户资料。".into());
                }
                // Labels and deliberate deletion remain user-owned. Mapping
                // becomes available only with the verified complete original.
                if audio_position_ms.is_some() {point.audio_position_ms=audio_position_ms;}
            }
            continue;
        }
        if !existing.is_empty() || ids.len()>=1024 || points.len()>=1024 {
            return Err("重点已满或标识冲突，原音保留，尚未确认消费。".into());
        }
        points.push(Bookmark{id:id.clone(),label:"重点".into(),position_ms,audio_position_ms,
            created_at:format!("device-elapsed:{}ms",mark.event.elapsed_ms),origin:"boardOffline".into(),
            source_device_id:row.source_device_id.clone(),recording_id:Some(mark.descriptor.recording_id),
            source_sha256:Some(hash),source_recording_key:Some(key.public_key())});
        ids.insert(id.clone());imported.push(id);
    }
    points.sort_by_key(|p|p.position_ms);
    if points==row.bookmarks && imported==row.device_bookmark_imports {return Ok(false);}
    let revision=row.bookmark_revision.checked_add(1).ok_or("重点版本耗尽，原件保留。")?;
    row.bookmarks=points;row.device_bookmark_imports=imported;row.bookmark_revision=revision;row.exported_at=None;
    Ok(true)
}

pub(crate) fn require_saved(row:&CompanionV1HostSession,marks:&[DeviceMark],key:&SessionKey,
    captured_samples:Option<u64>)->Result<(),String> {
    require_saved_with_origin(row,marks,key,captured_samples,320)
}
pub(crate) fn require_saved_with_origin(row:&CompanionV1HostSession,marks:&[DeviceMark],key:&SessionKey,
    captured_samples:Option<u64>,origin:u64)->Result<(),String> {
    let mut copy=row.clone();
    if merge_with_origin(&mut copy,marks,key,captured_samples,origin)? {
        return Err("设备重点尚未耐久保存，原音未确认回收。".into());
    }
    Ok(())
}
