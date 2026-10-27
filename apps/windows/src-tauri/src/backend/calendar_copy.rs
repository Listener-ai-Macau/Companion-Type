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
}

impl Copy {
    fn validate(&self)->Result<(),String> {
        let hash=|s:&str|s.len()==64&&s.bytes().all(|b|b.is_ascii_digit()||(b'a'..=b'f').contains(&b));
        if self.schema!=1||!matches!(self.meeting_mode.as_str(),"offlineStore"|"onlineLive")
            ||self.saved_at.is_empty()||!hash(&self.file_sha256)||!hash(&self.content_hash)
            ||self.file_name.is_empty()||self.file_name.len()>1024||self.file_name.chars().any(|c|c.is_control()||matches!(c,'/'|'\\'))
            ||self.entries.is_empty()||self.entries.len()>4096
            ||self.entries.iter().any(|e|e.uid.is_empty()||e.title.is_empty()||e.deadline.is_empty()
                ||e.reminder_minutes.is_some_and(|n|!matches!(n,0|30|60))) {
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
    let lead=match prepared.format {F::Calendar=>None,F::CalendarReminder=>Some(0),F::CalendarReminder30=>Some(30),F::CalendarReminder60=>Some(60),_=>return Ok(None)};
    let variant=match mode {"offlineStore"=>session.minutes_by_mode.offline_store.as_ref(),"onlineLive"=>session.minutes_by_mode.online_live.as_ref(),_=>return Err("不支持的日历整理方式。".into())};
    let markdown=variant.map(|v|v.markdown.clone()).or_else(|| {
        (session.meeting_mode==mode&&session.minutes_by_mode.offline_store.is_none()&&session.minutes_by_mode.online_live.is_none())
            .then(||session.minutes.as_ref().map(|v|v.markdown.clone())).flatten()
    }).ok_or("找不到这份日历对应的已保存清单。")?;
    let actions=super::action_export::parse_saved_actions(&markdown);
    let entries=super::action_export::calendar_copy_entries(&session.id,mode,&actions,lead);
    let copy=Copy{schema:1,privacy_epoch:session.calendar_copy_epoch,meeting_mode:mode.into(),saved_at:chrono::Utc::now().to_rfc3339(),
        file_name:destination.file_name().ok_or("日历文件名无法读取。")?.to_string_lossy().into(),
        file_sha256:format!("{:x}",Sha256::digest(&prepared.bytes)),content_hash:super::export::content_hash(prepared),
        source_title:session.title.clone(),source_markdown:markdown,entries};
    copy.validate()?;
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
    let revision=row.calendar_copy_revision.checked_add(1).ok_or("日历副本版本已超出范围。")?;
    // Keep current/previous semantic file snapshots per mode. Re-saving the
    // same content updates its filename/time without evicting a different copy.
    let mut next=vec![copy.clone()];let mut mode_count=1;
    for old in &row.calendar_copies {
        if old.meeting_mode==copy.meeting_mode {
            if old.content_hash!=copy.content_hash&&mode_count<2 {next.push(old.clone());mode_count+=1;}
        }else if next.iter().filter(|c|c.meeting_mode==old.meeting_mode).count()<2 {next.push(old.clone());}
    }
    row.calendar_copies=next;row.calendar_copy_revision=revision;row.exported_at=Some(copy.saved_at);
    Ok(())
}

pub(crate) fn commit(path:&std::path::Path,id:&str,copy:Copy)->Result<(u64,Vec<Copy>,Option<String>),String> {
    super::session_store::update_checked(path,|rows|apply(rows,id,copy))?;
    let loaded=super::session_store::load(path);
    if loaded.state.status!="ready" {return Err("日历文件已保存，副本说明暂时无法重读；请刷新后核对。".into());}
    let rows:Vec<CompanionV1HostSession>=serde_json::from_slice(&loaded.bytes.ok_or("副本说明保存后找不到原记录。")?).map_err(|e|e.to_string())?;
    let row=rows.iter().find(|r|r.id==id).ok_or("副本说明保存后原记录已变化，请刷新核对。")?;
    Ok((row.calendar_copy_revision,row.calendar_copies.clone(),row.exported_at.clone()))
}

#[cfg(test)]
mod tests;
