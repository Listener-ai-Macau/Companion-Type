//! Exact successful calendar-file snapshots live with their original session.
//! They prove local file save only, never external import or synchronization.
use serde::{Deserialize,Serialize};
use sha2::{Digest,Sha256};
use crate::companion_v1::CompanionV1HostSession;

#[derive(Clone,Debug,Deserialize,Serialize,PartialEq,Eq)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
pub struct Entry {
    pub uid:String,
    pub title:String,
    pub deadline:String,
    pub reminder_minutes:Option<u16>,
    #[serde(default,skip_serializing_if="Option::is_none")]
    pub reminder_at:Option<String>,
}

#[derive(Clone,Debug,Deserialize,Serialize,PartialEq,Eq)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
pub struct Copy {
    pub schema:u8,
    pub privacy_epoch:u64,
    pub meeting_mode:String,
    pub saved_at:String,
    pub file_name:String,
    pub file_sha256:String,
    pub content_hash:String,
    pub source_title:String,
    pub source_markdown:String,
    pub entries:Vec<Entry>,
    /// Passed only between preparation and commit; the v1/v2 receipt format
    /// stays byte-compatible for older installations.
    #[serde(skip)]
    pub(crate) transient_slots:Vec<super::action_export::CalendarSlotSelection>,
}

/// Slot settings are kept beside receipts, never embedded into the legacy
/// receipt schema. They carry the exact receipt hash and privacy epoch.
#[derive(Clone,Debug,Deserialize,Serialize,PartialEq,Eq)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
pub struct SlotCopy {
    pub privacy_epoch:u64,
    pub meeting_mode:String,
    pub content_hash:String,
    pub selections:Vec<super::action_export::CalendarSlotSelection>,
}

impl SlotCopy {
    fn validate_against(&self,copy:&Copy)->Result<(),String> {
        if self.privacy_epoch!=copy.privacy_epoch||self.meeting_mode!=copy.meeting_mode||self.content_hash!=copy.content_hash
            ||self.selections.is_empty()||self.selections.len()>copy.entries.len() {return Err("执行时段与日历副本不一致；原文件保留，请重新核对。".into());}
        let mut seen=std::collections::HashSet::new();
        for selection in &self.selections {
            if !seen.insert(&selection.uid)||copy.entries.iter().filter(|e|e.uid==selection.uid).count()!=1
                ||super::action_export::slot_in_utc(&selection.slot).is_none() {
                return Err("执行时段与日历事项不一致；原文件保留，请重新核对。".into());
            }
        }
        Ok(())
    }
}

impl Copy {
    fn validate(&self)->Result<(),String> {
        let hash=|s:&str|s.len()==64&&s.bytes().all(|b|b.is_ascii_digit()||(b'a'..=b'f').contains(&b));
        if !matches!(self.schema,1|2)||!matches!(self.meeting_mode.as_str(),"offlineStore"|"onlineLive")
            ||self.saved_at.is_empty()||!hash(&self.file_sha256)||!hash(&self.content_hash)
            ||self.file_name.is_empty()||self.file_name.len()>1024||self.file_name.chars().any(|c|c.is_control()||matches!(c,'/'|'\\'))
            ||self.entries.is_empty()||self.entries.len()>4096
            ||self.entries.iter().any(|e|e.uid.is_empty()||e.title.is_empty()||e.deadline.is_empty()
                ||e.reminder_minutes.is_some_and(|n|!matches!(n,0|30|60|1440))
                ||(e.reminder_at.is_some()&&e.reminder_minutes.is_some())
                ||e.reminder_at.as_deref().is_some_and(|at|super::action_export::absolute_alarm_utc(at).is_none())
                ||(self.schema==1&&(e.reminder_at.is_some()||e.reminder_minutes==Some(1440)))) {
            return Err("日历副本来源不完整；文件保存结果不变，请保留原文件。".into());
        }
        if serde_json::to_vec(self).map_err(|e|e.to_string())?.len()>1_048_576 {
            return Err("这份日历副本说明超过本机记录上限；文件仍保留，请自行核对接收日历。".into());
        }
        Ok(())
    }
}

pub(crate) fn prepare(session:&CompanionV1HostSession,mode:&str,
    prepared:&super::export::PreparedMeetingExport,destination:&std::path::Path)->Result<Option<Copy>,String> {
    use super::export::MeetingExportFormat as F;
    if !matches!(prepared.format,F::Calendar|F::CalendarReminder|F::CalendarReminder30|F::CalendarReminder60){return Ok(None);}
    let variant=match mode {"offlineStore"=>session.minutes_by_mode.offline_store.as_ref(),"onlineLive"=>session.minutes_by_mode.online_live.as_ref(),_=>return Err("不支持的日历整理方式。".into())};
    let markdown=variant.map(|v|v.markdown.clone()).or_else(|| {
        (session.meeting_mode==mode&&session.minutes_by_mode.offline_store.is_none()&&session.minutes_by_mode.online_live.is_none())
            .then(||session.minutes.as_ref().map(|v|v.markdown.clone())).flatten()
    }).ok_or("找不到这份日历对应的已保存清单。")?;
    // The export may have deduplicated chunked minutes. Re-reading raw lines
    // here would invent extra saved events and shift their UID indices.
    use super::action_export::CalendarAlarm;
    let entries=prepared.calendar_items.as_ref().ok_or("日历文件缺少对应的事项预览，未记录副本。")?.iter()
        .filter(|item|matches!(item.status,"timed"|"allDay"))
        .map(|item|Entry{uid:item.uid.clone(),title:item.title.clone(),deadline:item.deadline.clone().unwrap_or_default(),
            reminder_minutes:match &item.reminder {CalendarAlarm::Before{minutes}=>Some(*minutes),_=>None},
            reminder_at:match &item.reminder {CalendarAlarm::At{at}=>Some(at.clone()),_=>None}}).collect::<Vec<_>>();
    let schema=if entries.iter().any(|e|e.reminder_at.is_some()||e.reminder_minutes==Some(1440)){2}else{1};
    let transient_slots=prepared.calendar_items.as_ref().into_iter().flatten().filter_map(|item|item.execution_slot.as_ref().map(|slot|super::action_export::CalendarSlotSelection{uid:item.uid.clone(),slot:slot.clone()})).collect();
    let copy=Copy{schema,privacy_epoch:session.calendar_copy_epoch,meeting_mode:mode.into(),saved_at:chrono::Utc::now().to_rfc3339(),
        file_name:destination.file_name().ok_or("日历文件名无法读取。")?.to_string_lossy().into(),
        file_sha256:format!("{:x}",Sha256::digest(&prepared.bytes)),content_hash:super::export::content_hash(prepared),
        source_title:session.title.clone(),source_markdown:markdown,entries,transient_slots};
    copy.validate()?;
    if !copy.transient_slots.is_empty(){SlotCopy{privacy_epoch:copy.privacy_epoch,meeting_mode:copy.meeting_mode.clone(),content_hash:copy.content_hash.clone(),selections:copy.transient_slots.clone()}.validate_against(&copy)?;}
    Ok(Some(copy))
}

/// Attach the exact prepared snapshot, even if the current text changed during
/// file I/O. Never replace the current row with the older prepared session.
pub(crate) fn apply(rows:&mut [CompanionV1HostSession],id:&str,mut copy:Copy)->Result<(),String> {
    copy.saved_at=chrono::Utc::now().to_rfc3339();copy.validate()?;
    let row=rows.iter_mut().find(|r|r.id==id).ok_or("原记录已移除，文件已保存，但没有新建或恢复该记录。")?;
    super::library_lifecycle::require_available(row)?;
    if row.calendar_copy_epoch!=copy.privacy_epoch {return Err("文字已在其它窗口清除；文件已保存，没有将旧文字重新附回记录。".into());}
    for old in &row.calendar_copies {old.validate()?;}
    let mut slot_keys=std::collections::HashSet::new();
    for slots in &row.calendar_slot_copies {
        if !slot_keys.insert((slots.privacy_epoch,&slots.meeting_mode,&slots.content_hash)) {return Err("保存的执行时段重复；原文件保留，请先核对。".into());}
        let old=row.calendar_copies.iter().find(|old|old.privacy_epoch==slots.privacy_epoch&&old.meeting_mode==slots.meeting_mode&&old.content_hash==slots.content_hash)
            .ok_or("保存的执行时段缺少对应副本；原文件保留，请先核对。")?;
        slots.validate_against(old)?;
    }
    let new_slots=if copy.transient_slots.is_empty(){None}else{
        let slots=SlotCopy{privacy_epoch:copy.privacy_epoch,meeting_mode:copy.meeting_mode.clone(),content_hash:copy.content_hash.clone(),selections:std::mem::take(&mut copy.transient_slots)};
        slots.validate_against(&copy)?;Some(slots)
    };
    let revision=row.calendar_copy_revision.checked_add(1).ok_or("日历副本版本已超出范围。")?;
    // Keep current/previous semantic file snapshots per mode. Re-saving the
    // same content updates its filename/time without evicting a different copy.
    let mut next=vec![copy.clone()];let mut mode_count=1;
    for old in &row.calendar_copies {
        if old.meeting_mode==copy.meeting_mode {
            if old.content_hash!=copy.content_hash&&mode_count<2 {next.push(old.clone());mode_count+=1;}
        }else if next.iter().filter(|c|c.meeting_mode==old.meeting_mode).count()<2 {next.push(old.clone());}
    }
    let mut next_slots=Vec::new();if let Some(slots)=new_slots {next_slots.push(slots);}
    for slots in &row.calendar_slot_copies {
        // The newest receipt is replaced even when its content matches.
        if slots.privacy_epoch==copy.privacy_epoch&&slots.meeting_mode==copy.meeting_mode&&slots.content_hash==copy.content_hash {continue;}
        if next.iter().any(|old|old.privacy_epoch==slots.privacy_epoch&&old.meeting_mode==slots.meeting_mode&&old.content_hash==slots.content_hash){next_slots.push(slots.clone());}
    }
    row.calendar_copies=next;row.calendar_slot_copies=next_slots;row.calendar_copy_revision=revision;row.exported_at=Some(copy.saved_at);
    Ok(())
}

pub(crate) fn commit(path:&std::path::Path,id:&str,copy:Copy)->Result<(u64,Vec<Copy>,Vec<SlotCopy>,Option<String>),String> {
    super::session_store::update_checked(path,|rows|apply(rows,id,copy))?;
    let loaded=super::session_store::load(path);
    if loaded.state.status!="ready" {return Err("日历文件已保存，副本说明暂时无法重读；请刷新后核对。".into());}
    let rows:Vec<CompanionV1HostSession>=serde_json::from_slice(&loaded.bytes.ok_or("副本说明保存后找不到原记录。")?).map_err(|e|e.to_string())?;
    let row=rows.iter().find(|r|r.id==id).ok_or("副本说明保存后原记录已变化，请刷新核对。")?;
    Ok((row.calendar_copy_revision,row.calendar_copies.clone(),row.calendar_slot_copies.clone(),row.exported_at.clone()))
}

#[cfg(test)]
mod tests;
