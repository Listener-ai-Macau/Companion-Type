//! Multi-format transcript / minutes export.
//!
//! Markdown is rendered by `minutes::render_minutes_markdown`. This module
//! renders the other formats the dashboard can request via the
//! `MeetingExport{Txt,Json,Srt}` actions:
//!  - **txt**  : the plain (speaker-tagged) transcript text.
//!  - **json** : a structured dump (title, transcript, timed utterances, minutes).
//!  - **srt**  : subtitles from the diarization-aware utterance segments
//!               (requires per-utterance timing from the volcengine path).

use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};

use crate::companion_v1::{
    CompanionV1HostSession, CompanionV1MeetingMinutes, CompanionV1MinutesVariant,
    CompanionV1UtteranceSegment,
};
use super::transcript_review;

fn minutes_source_notice(session: &CompanionV1HostSession, revision: Option<u64>, context: &Option<super::minutes_context::Source>, manual: bool, body: String) -> String {
    if !transcript_review::minutes_current(session, revision) || !super::minutes_context::current(session, context) {
        format!("> 整理来源已变化：以下为之前保留的结果，转写或补充已更新，请重新整理后使用。\n\n{body}")
    } else if manual {
        format!("> 用户手写清单，仅本机保存；不是自动整理或录音识别。\n\n{body}")
    } else if revision.is_some() {
        format!("> 基于人工修订的转写生成；原始识别结果另行保留。\n\n{body}")
    } else { body }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum MeetingExportFormat {
    Markdown,
    Txt,
    Json,
    Srt,
    Todo,
    TodoText,
    Ics,
    Calendar,
    CalendarReminder,
    CalendarReminder30,
    CalendarReminder60,
}

impl MeetingExportFormat {
    pub fn extension(self) -> &'static str {
        match self {
            Self::Markdown => "md",
            Self::Txt => "txt",
            Self::Json => "json",
            Self::Srt => "srt",
            Self::Todo => "md",
            Self::TodoText => "txt",
            Self::Ics | Self::Calendar | Self::CalendarReminder | Self::CalendarReminder30 | Self::CalendarReminder60 => "ics",
        }
    }

    pub fn dialog_label(self) -> &'static str {
        match self {
            Self::Markdown => "Markdown",
            Self::Txt => "Plain text",
            Self::Json => "JSON",
            Self::Srt => "SubRip subtitles",
            Self::Todo => "待办清单 Markdown",
            Self::TodoText => "待办清单普通文本",
            Self::Ics => "iCalendar 待办事项",
            Self::Calendar => "日历日程 (.ics)",
            Self::CalendarReminder | Self::CalendarReminder30 | Self::CalendarReminder60 => "日历日程与提醒 (.ics)",
        }
    }
}

#[derive(Clone, Debug)]
pub struct PreparedMeetingExport {
    pub bytes: Vec<u8>,
    pub suggested_name: String,
    pub format: MeetingExportFormat,
    pub warning: Option<String>,
}

/// Plain checklist body from the same validated native TODO renderer. No file,
/// exported marker, inferred date, clipboard or provider operation occurs here.
pub fn checklist_copy_text(prepared: &PreparedMeetingExport) -> Result<String,String> {
    let text=std::str::from_utf8(&prepared.bytes).map_err(|_|"清单文字无法读取，请保留已保存内容。")?;
    let body=text.split_once('\n').map(|(_,body)|body.trim()).unwrap_or("");
    if body.is_empty(){return Err("没有可复制的已保存清单。".into());}
    Ok(body.to_owned())
}

pub fn content_hash(prepared: &PreparedMeetingExport) -> String {
    use sha2::Digest;
    let mut hash=sha2::Sha256::new();
    hash.update(prepared.suggested_name.as_bytes());hash.update([0]);
    if matches!(prepared.format,MeetingExportFormat::Ics|MeetingExportFormat::Calendar|MeetingExportFormat::CalendarReminder|MeetingExportFormat::CalendarReminder30|MeetingExportFormat::CalendarReminder60) {
        // The generated DTSTAMP is the export instant, not saved content.
        // Every other byte (including UID, title, mode, literal time and DUE)
        // remains bound to the user's reviewed saved result.
        let text=String::from_utf8_lossy(&prepared.bytes);
        for line in text.split_inclusive("\r\n") {
            if !line.starts_with("DTSTAMP:"){hash.update(line.as_bytes());}
        }
    } else {hash.update(&prepared.bytes);}
    format!("{:x}",hash.finalize())
}

pub fn require_unchanged(prepared: &PreparedMeetingExport, expected: Option<&str>) -> Result<(),String> {
    if expected.is_some_and(|value|value!=content_hash(prepared)) {
        return Err("导出内容已变化，请重新查看当前记录后再导出；本次未写入文件。".into());
    }
    Ok(())
}

fn minutes_variant_for_mode<'a>(
    session: &'a CompanionV1HostSession,
    meeting_mode: &str,
) -> Option<&'a CompanionV1MinutesVariant> {
    match meeting_mode {
        "offlineStore" => session.minutes_by_mode.offline_store.as_ref(),
        "onlineLive" => session.minutes_by_mode.online_live.as_ref(),
        _ => None,
    }
}

fn saved_minutes_markdown_for_mode(
    session: &CompanionV1HostSession,
    meeting_mode: &str,
) -> Result<String, String> {
    if let Some(variant) = minutes_variant_for_mode(session, meeting_mode) {
        if variant.markdown.trim().is_empty() {
            return Err(format!("{meeting_mode} minutes have no saved content"));
        }
        return Ok(minutes_source_notice(session, variant.source_review_revision, &variant.source_note_context, variant.source == "userAuthored", if variant.status == "minutesReady" && variant.quality != "draft"
            && variant.processing.as_ref().is_none_or(|p| p.is_complete()) {
            variant.markdown.clone()
        } else {
            format!(
                "> 草稿：纪要服务尚未完成；以下为已保存在本机的内容。\n\n{}",
                variant.markdown
            )
        }));
    }
    let has_any_variant = session.minutes_by_mode.offline_store.is_some()
        || session.minutes_by_mode.online_live.is_some();
    if !has_any_variant && session.meeting_mode == meeting_mode {
        if let Some(minutes) = session
            .minutes
            .as_ref()
            .filter(|minutes| !minutes.markdown.trim().is_empty())
        {
            return Ok(minutes_source_notice(session, minutes.source_review_revision, &minutes.source_note_context, minutes.source == "userAuthored", if minutes.llm_note.is_some() || minutes.quality == "draft"
                || minutes.processing.as_ref().is_some_and(|p| !p.is_complete()) {
                format!(
                    "> 草稿：纪要服务尚未完成；以下为已保存在本机的内容。\n\n{}",
                    minutes.markdown
                )
            } else {
                minutes.markdown.clone()
            }));
        }
    }
    Err(format!("{meeting_mode} minutes have not been generated"))
}

fn session_has_final_transcript(session: &CompanionV1HostSession) -> bool {
    transcript_review::final_transcript_available(session)
}

fn require_final_transcript(session: &CompanionV1HostSession) -> Result<(), String> {
    if !session_has_final_transcript(session) {
        return Err("会议文字尚未整理完成，暂时不能导出".to_string());
    }
    Ok(())
}

pub(super) fn safe_file_stem(title: &str, session_id: &str) -> String {
    let source = if title.trim().is_empty() {
        session_id.trim()
    } else {
        title.trim()
    };
    let mut stem = source
        .chars()
        .map(|character| match character {
            '<' | '>' | ':' | '"' | '/' | '\\' | '|' | '?' | '*' => '_',
            character if character.is_control() => '_',
            character => character,
        })
        .take(80)
        .collect::<String>();
    stem = stem.trim().trim_end_matches(['.', ' ']).to_string();
    if stem.is_empty() {
        "Companion-meeting".to_string()
    } else {
        stem
    }
}

pub fn prepare_meeting_export(
    session: &CompanionV1HostSession,
    meeting_mode: &str,
    format: MeetingExportFormat,
) -> Result<PreparedMeetingExport, String> {
    super::library_lifecycle::require_available(session)?;
    if !matches!(meeting_mode, "offlineStore" | "onlineLive") {
        return Err(format!("不支持的会议模式：{meeting_mode}"));
    }
    let has_requested_variant = minutes_variant_for_mode(session, meeting_mode).is_some();
    if session.meeting_mode != meeting_mode && !has_requested_variant {
        return Err(format!(
            "这场会议还没有保存 {meeting_mode} 模式的结果"
        ));
    }

    let mut warning=None;
    let content = match format {
        MeetingExportFormat::Todo | MeetingExportFormat::TodoText | MeetingExportFormat::Ics | MeetingExportFormat::Calendar | MeetingExportFormat::CalendarReminder | MeetingExportFormat::CalendarReminder30 | MeetingExportFormat::CalendarReminder60 => {
            let processing = minutes_variant_for_mode(session, meeting_mode).and_then(|v| v.processing.as_ref())
                .or_else(|| if minutes_variant_for_mode(session, meeting_mode).is_none() {
                    session.minutes.as_ref().and_then(|m| m.processing.as_ref())
                } else { None });
            if processing.is_some_and(|p| !p.is_complete()) {
                return Err("长会议仍有未整理片段，请先继续整理完成，再导出整场待办；部分纪要和原文可以保存。".into());
            }
            let revision = minutes_variant_for_mode(session, meeting_mode).map(|v| v.source_review_revision)
                .or_else(|| session.minutes.as_ref().map(|m| m.source_review_revision)).flatten();
            let context = match minutes_variant_for_mode(session,meeting_mode) {
                Some(v)=>v.source_note_context.clone(),
                None=>session.minutes.as_ref().and_then(|m|m.source_note_context.clone()),
            };
            if !transcript_review::minutes_current(session, revision) || !super::minutes_context::current(session,&context) {
                return Err("转写已经修订，请先重新生成或核对这版纪要，再导出待办，避免使用旧的任务归属。".into());
            }
            let saved = saved_minutes_markdown_for_mode(session, meeting_mode)?;
            let mut actions = super::action_export::parse_saved_actions(&saved);
            if processing.is_some() {
                let mut seen = std::collections::HashSet::new();
                actions.retain(|a| seen.insert((a.text.clone(), a.completed, a.due.clone())));
            }
            if actions.is_empty() {
                return Err("这版已保存纪要中没有可导出的待办。请在“行动项”或“Action Items”标题下用列表填写任务并保存。".into());
            }
            if format==MeetingExportFormat::Ics { warning=super::action_export::calendar_time_notice(&actions); }
            if format==MeetingExportFormat::Calendar { warning=super::action_export::calendar_event_notice(&actions); }
            if matches!(format,MeetingExportFormat::CalendarReminder|MeetingExportFormat::CalendarReminder30|MeetingExportFormat::CalendarReminder60) { warning=super::action_export::calendar_event_reminder_notice(&actions); }
            let draft = saved.lines().any(|line| line.starts_with("> 草稿："));
            if matches!(format, MeetingExportFormat::Todo | MeetingExportFormat::TodoText) {
                let body=super::action_export::todo(&session.title, &actions, draft);
                // The same validated checklist, in a universally readable text
                // file. Keep checkboxes, conditions and source notices intact.
                if format==MeetingExportFormat::TodoText {
                    body.strip_prefix("# ").unwrap_or(&body).to_owned()
                }else{body}
            } else if matches!(format,MeetingExportFormat::Calendar|MeetingExportFormat::CalendarReminder|MeetingExportFormat::CalendarReminder30|MeetingExportFormat::CalendarReminder60) {
                super::action_export::calendar_events_with_reminder_lead(&session.id,meeting_mode,&session.title,&actions,draft,&super::action_export::stamp_now(),match format{MeetingExportFormat::CalendarReminder=>Some(0),MeetingExportFormat::CalendarReminder30=>Some(30),MeetingExportFormat::CalendarReminder60=>Some(60),_=>None})?
            } else {
                super::action_export::calendar(&session.id, meeting_mode, &session.title, &actions, draft, &super::action_export::stamp_now())
            }
        }
        MeetingExportFormat::Markdown => format!("{}{}{}",saved_minutes_markdown_for_mode(session, meeting_mode)?,render_bookmarks(session),super::meeting_notes::render(session)),
        MeetingExportFormat::Txt => {
            if session.bookmarks.is_empty() && session.meeting_notes.is_empty() { require_final_transcript(session)?; }
            render_txt(session)
        }
        MeetingExportFormat::Json => {
            if session.bookmarks.is_empty() && session.meeting_notes.is_empty() { require_final_transcript(session)?; }
            render_json_for_mode(session, meeting_mode)?
        }
        MeetingExportFormat::Srt => {
            require_final_transcript(session)?;
            if session.utterances.is_empty()
                || session.utterances.iter().any(|utterance| {
                    utterance.text.trim().is_empty() || utterance.end_ms <= utterance.start_ms
                })
            {
                return Err(
                    "无法导出 SRT：这份转写没有可用的真实时间轴"
                        .to_string(),
                );
            }
            render_srt(session)
        }
    };
    let file_stem = safe_file_stem(&session.title, &session.id);
    let purpose = match format {
        MeetingExportFormat::Markdown => "整理结果",
        MeetingExportFormat::Txt => "文字与补充",
        MeetingExportFormat::Json => "完整资料",
        MeetingExportFormat::Srt => "字幕",
        MeetingExportFormat::Todo => "待办清单",
        MeetingExportFormat::TodoText => "待办清单",
        MeetingExportFormat::Ics => "待办日历",
        MeetingExportFormat::Calendar => "日历日程",
        MeetingExportFormat::CalendarReminder | MeetingExportFormat::CalendarReminder30 | MeetingExportFormat::CalendarReminder60 => "日历提醒",
    };
    let both_modes = session.minutes_by_mode.offline_store.is_some() && session.minutes_by_mode.online_live.is_some();
    let mode_label = if both_modes && !matches!(format, MeetingExportFormat::Txt | MeetingExportFormat::Srt) {
        if meeting_mode == "onlineLive" { "在线速记-" } else { "先录后整理-" }
    } else { "" };
    Ok(PreparedMeetingExport {
        bytes: content.into_bytes(),
        suggested_name: format!(
            "{file_stem}-{mode_label}{purpose}.{}",
            format.extension()
        ),
        format,
        warning,
    })
}

fn render_json_for_mode(
    session: &CompanionV1HostSession,
    meeting_mode: &str,
) -> Result<String, String> {
    #[derive(serde::Serialize)]
    #[serde(rename_all = "camelCase")]
    struct Export<'a> {
        session_id: &'a str,
        title: &'a str,
        meeting_mode: &'a str,
        duration_ms: u64,
        started_at: &'a Option<String>,
        stopped_at: &'a Option<String>,
        transcript_text: String,
        transcript_final: bool,
        bookmark_revision: u64,
        bookmarks: &'a [super::recording_bookmarks::Bookmark],
        organization: &'a super::library_organization::Metadata,
        note_revision: u64,
        user_notes: &'a [super::meeting_notes::Note],
        utterances: Vec<CompanionV1UtteranceSegment>,
        original_transcript_text: &'a str,
        original_utterances: &'a [CompanionV1UtteranceSegment],
        transcript_review: &'a Option<transcript_review::TranscriptReview>,
        speaker_labels: Vec<Option<String>>,
        review_stale: bool,
        minutes_current: bool,
        minutes: Option<&'a CompanionV1MinutesVariant>,
        legacy_minutes: Option<&'a CompanionV1MeetingMinutes>,
    }
    let selected_variant = minutes_variant_for_mode(session, meeting_mode);
    let legacy_minutes = if selected_variant.is_none()
        && session.minutes_by_mode.offline_store.is_none()
        && session.minutes_by_mode.online_live.is_none()
        && session.meeting_mode == meeting_mode
    {
        session.minutes.as_ref()
    } else {
        None
    };
    serde_json::to_string_pretty(&Export {
        session_id: &session.id,
        title: &session.title,
        meeting_mode,
        duration_ms: session.duration_ms,
        started_at: &session.started_at,
        stopped_at: &session.stopped_at,
        transcript_text: transcript_review::effective_text(session),
        transcript_final: session.transcript_final,
        bookmark_revision: session.bookmark_revision,
        note_revision: session.note_revision,
        user_notes: &session.meeting_notes,
        bookmarks: &session.bookmarks,
        organization: &session.organization,
        utterances: transcript_review::effective_utterances(session),
        original_transcript_text: &session.transcript_text,
        original_utterances: &session.utterances,
        transcript_review: &session.transcript_review,
        speaker_labels: (0..session.utterances.len()).map(|i| transcript_review::speaker_label(session,i)).collect(),
        review_stale: transcript_review::review_is_stale(session),
        minutes_current: (selected_variant.is_some() || legacy_minutes.is_some()) && transcript_review::minutes_current(session, selected_variant.map(|v| v.source_review_revision)
            .or_else(|| legacy_minutes.map(|m| m.source_review_revision)).flatten())
            && super::minutes_context::current(session,&selected_variant.and_then(|v|v.source_note_context.clone())
                .or_else(||legacy_minutes.and_then(|m|m.source_note_context.clone()))),
        minutes: selected_variant,
        legacy_minutes,
    })
    .map_err(|error| format!("serialize export json: {error}"))
}

pub(crate) fn local_write_error(action:&str,error:&std::io::Error)->String {
    use std::io::ErrorKind;
    #[cfg(windows)]
    let occupied=error.raw_os_error().is_some_and(|code|{
        use windows::Win32::Foundation::{ERROR_SHARING_VIOLATION,ERROR_LOCK_VIOLATION};
        code==ERROR_SHARING_VIOLATION.0 as i32||code==ERROR_LOCK_VIOLATION.0 as i32
    });
    #[cfg(not(windows))]
    let occupied=false;
    let remedy=if occupied {"保存文件正在使用中，请解除文件占用后重试"} else {match error.kind() {
        ErrorKind::StorageFull=>"本机磁盘空间不足，请释放保存位置所在磁盘的空间",
        ErrorKind::PermissionDenied|ErrorKind::ReadOnlyFilesystem=>"无法写入保存位置，请检查目录权限或解除文件占用",
        _=>"请检查保存位置和磁盘是否可用",
    }};
    format!("{action}失败：{remedy}。已有文件保留，本次保存未完成；处理后可重试。原因：{error}")
}
#[cfg(windows)]
fn windows_commit_error(error:windows::core::Error)->String {
    // Decode only HRESULT_FROM_WIN32 values. Other facilities retain their
    // original diagnostic; truncating arbitrary HRESULTs invents OS causes.
    // https://learn.microsoft.com/windows/win32/api/winerror/nf-winerror-hresult_from_win32
    let code=error.code().0 as u32;
    if code&0xffff0000==0x80070000 {
        local_write_error("提交保存文件",&std::io::Error::from_raw_os_error((code&0xffff) as i32))
    } else {format!("提交保存文件失败，已有文件保留；请处理后重试。原因：{error}")}
}

pub fn write_atomic(path: &Path, bytes: &[u8]) -> Result<u64, String> {
    let file_name = path.file_name().ok_or("export destination has no file name")?;
    let parent = path.parent().filter(|parent| !parent.as_os_str().is_empty())
        .unwrap_or_else(|| Path::new("."));
    fs::create_dir_all(parent)
        .map_err(|error| local_write_error("创建保存目录",&error))?;
    // Resolve the parent once. Rust supplies the Win32 verbatim form for long
    // paths; preserve the final component rather than following a file symlink.
    let parent = parent.canonicalize()
        .map_err(|error| local_write_error("打开保存目录",&error))?;
    let destination = parent.join(file_name);
    // Do not append the destination's name: a valid 255-character filename
    // must not become an invalid temporary filename after adding a UUID.
    let temp_path: PathBuf = parent.join(format!(".companion-{}.tmp", uuid::Uuid::new_v4().simple()));
    let result = (|| {
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&temp_path)
            .map_err(|error| local_write_error("创建保存文件",&error))?;
        file.write_all(bytes)
            .map_err(|error| local_write_error("写入保存文件",&error))?;
        file.sync_all()
            .map_err(|error| local_write_error("提交保存文件",&error))?;
        drop(file);
        replace_file(&temp_path, &destination)?;
        Ok(bytes.len() as u64)
    })();
    if result.is_err() {
        let _ = fs::remove_file(&temp_path);
    }
    result
}

#[cfg(windows)]
pub(crate) fn replace_file(source: &Path, destination: &Path) -> Result<(), String> {
    use std::os::windows::ffi::OsStrExt;
    use windows::core::PCWSTR;
    use windows::Win32::Storage::FileSystem::{
        MoveFileExW, MOVEFILE_REPLACE_EXISTING, MOVEFILE_WRITE_THROUGH,
    };

    let resolve = |path: &Path| -> Result<PathBuf, String> {
        let name = path.file_name().ok_or("atomic replacement path has no file name")?;
        let parent = path.parent().filter(|parent| !parent.as_os_str().is_empty())
            .unwrap_or_else(|| Path::new("."));
        parent.canonicalize().map(|parent| parent.join(name))
            .map_err(|error| format!("resolve atomic replacement directory {}: {error}", parent.display()))
    };
    let source_resolved = resolve(source)?;
    let destination_resolved = resolve(destination)?;
    let source_wide = source_resolved
        .as_os_str()
        .encode_wide()
        .chain(std::iter::once(0))
        .collect::<Vec<_>>();
    let destination_wide = destination_resolved
        .as_os_str()
        .encode_wide()
        .chain(std::iter::once(0))
        .collect::<Vec<_>>();
    unsafe {
        MoveFileExW(
            PCWSTR(source_wide.as_ptr()),
            PCWSTR(destination_wide.as_ptr()),
            MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH,
        )
        .map_err(windows_commit_error)
    }
}

#[cfg(not(windows))]
pub(crate) fn replace_file(source: &Path, destination: &Path) -> Result<(), String> {
    fs::rename(source, destination).map_err(|error| {
        format!(
            "commit export {} -> {}: {error}",
            source.display(),
            destination.display()
        )
    })?;
    if let Some(parent) = destination.parent() {
        fs::File::open(parent).and_then(|file| file.sync_all())
            .map_err(|error| format!("flush export directory: {error}"))?;
    }
    Ok(())
}

/// Plain-text export: the session title + transcript text (already carries
/// "说话人N:" speaker attribution when diarization ran).
pub fn render_txt(session: &CompanionV1HostSession) -> String {
    let title = if session.title.trim().is_empty() {
        "Companion meeting"
    } else {
        session.title.trim()
    };
    let notice = if transcript_review::active_revision(session).is_some() {
        "人工修订转写；原始识别结果另行保留。\n\n"
    } else if transcript_review::review_is_stale(session) {
        "原始转写已更新；旧修订未套用，请核对保留的草稿。\n\n"
    } else { "" };
    let pending=if session.transcript_final {""} else {"尚无最终转写；重点和备注为用户补充，不代表识别结果或已完成的纪要。\n\n"};
    format!("# {title}\n\n{pending}{notice}{}{}{}", transcript_review::effective_text(session),render_bookmarks(session),super::meeting_notes::render(session))
}

fn render_bookmarks(session:&CompanionV1HostSession)->String {
    if session.bookmarks.is_empty() { return String::new(); }
    let mut text="\n\n## 用户重点\n\n".to_string();
    for point in &session.bookmarks {
        let valid=point.source_sha256.as_deref().is_none_or(|s|Some(s)==session.device_sha256.as_deref())
            && (point.origin!="boardRecording" || (point.recording_id==session.device_recording_id
                && point.source_device_id.as_deref().zip(session.source_device_id.as_deref())
                    .is_some_and(|(a,b)|super::device_connection::same_device_id(a,b))));
        if let Some(ms)=point.audio_position_ms.filter(|_|valid) {
            text.push_str(&format!("- {:02}:{:02}.{:03} {}\n",ms/60000,(ms/1000)%60,ms%1000,point.label));
        } else {
            text.push_str(&format!("- {}（设备录音时间 {} ms，回听映射尚未确认）\n",point.label,point.position_ms));
        }
    }
    text
}

/// Structured JSON export of the session. Minutes are included when present.
pub fn render_json(session: &CompanionV1HostSession) -> Result<String, String> {
    render_json_for_mode(session, &session.meeting_mode)
}

/// SRT subtitle export from the timed utterance segments. Returns an empty
/// string when the session has no utterance timing (e.g. env-text / sidecar /
/// pre-diarization sessions); the caller falls back to markdown in that case.
pub fn render_srt(session: &CompanionV1HostSession) -> String {
    if session.utterances.is_empty() {
        return String::new();
    }
    let mut out = String::new();
    for (index, utt) in transcript_review::effective_utterances(session).iter().enumerate() {
        let label = transcript_review::speaker_label(session, index)
            .map(|name| format!("{name}: "))
            .unwrap_or_default();
        out.push_str(&format!("{}\n", index + 1));
        out.push_str(&format!(
            "{} --> {}\n",
            srt_timestamp(utt.start_ms),
            srt_timestamp(utt.end_ms)
        ));
        let subtitle_text = utt.text.lines().filter(|line| !line.trim().is_empty()).collect::<Vec<_>>().join("\n");
        out.push_str(&format!("{}{}\n\n", label, subtitle_text));
    }
    out
}

/// Format milliseconds as an SRT timestamp: `HH:MM:SS,mmm`.
fn srt_timestamp(ms: u64) -> String {
    let millis = ms % 1000;
    let total_seconds = ms / 1000;
    let seconds = total_seconds % 60;
    let total_minutes = total_seconds / 60;
    let minutes = total_minutes % 60;
    let hours = total_minutes / 60;
    format!("{hours:02}:{minutes:02}:{seconds:02},{millis:03}")
}

/// Markdown checklist of the meeting's action items (the highest-leverage
/// output of a meeting). `- [ ] task (owner: X, due: Y)`.
pub fn render_action_items_todo(session: &CompanionV1HostSession) -> String {
    let title = if session.title.trim().is_empty() {
        "Companion meeting"
    } else {
        session.title.trim()
    };
    let mut out = format!("# {title} — Action Items\n\n");
    let items = session
        .minutes
        .as_ref()
        .map(|m| m.action_items.as_slice())
        .unwrap_or(&[]);
    if items.is_empty() {
        out.push_str("_(no action items captured)_\n");
    } else {
        for item in items {
            let mut line = format!("- [ ] {}", item.text);
            let mut meta = Vec::new();
            if let Some(owner) = item.owner.as_deref() {
                if !owner.trim().is_empty() {
                    meta.push(format!("owner: {owner}"));
                }
            }
            if let Some(due) = item.due.as_deref() {
                if !due.trim().is_empty() {
                    meta.push(format!("due: {due}"));
                }
            }
            if !meta.is_empty() {
                line.push_str(&format!(" ({})", meta.join(", ")));
            }
            out.push_str(&line);
            out.push('\n');
        }
    }
    out
}

/// Legacy structured export uses the same valid iCalendar writer as the UI.
pub fn render_action_items_ical(session: &CompanionV1HostSession) -> String {
    let actions = session.minutes.as_ref().map(|minutes| minutes.action_items.iter().map(|item| {
        super::action_export::Action {
            text: format!("{}{}{}", item.text,
                item.owner.as_deref().map(|owner| format!(" (owner: {owner})")).unwrap_or_default(),
                item.due.as_deref().map(|due| format!(" (due: {due})")).unwrap_or_default()),
            completed: false, due: item.due.clone(),
        }
    }).collect::<Vec<_>>()).unwrap_or_default();
    super::action_export::calendar(&session.id, &session.meeting_mode, &session.title, &actions, false, &super::action_export::stamp_now())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::companion_v1::{CompanionV1ActionItem, CompanionV1SessionRetention};

    fn session(
        transcript: &str,
        utterances: Vec<CompanionV1UtteranceSegment>,
        minutes: Option<CompanionV1MeetingMinutes>,
    ) -> CompanionV1HostSession {
        CompanionV1HostSession { device_recording_end_reason: None, processing_policy: Default::default(), recorder_control: None, recorder_control_uncertain: false, device_recording_key: None, 
            transcript_review: None,
            bookmark_revision: 0, bookmarks: vec![], organization: Default::default(), device_bookmark_imports: vec![],
            note_revision: 0, meeting_notes: vec![],
            id: "s1".into(),
            title: "Q3 Review".into(),
            source: "hostMicrophone".into(),
            meeting_mode: "offlineStore".into(),
            status: "minutesReady".into(),
            pending_reason: None,
            started_at: Some("2026-07-28T10:00:00Z".into()),
            stopped_at: None,
            duration_ms: 5000,
            audio_path: None,
            audio_bytes: 0,
            audio_stored: false,
            device_recording_id: None,
            device_total_length: None,
            device_sha256: None,
            device_reclaimed: false, capture_incomplete: false,
            source_device_id: None,
            chunks: vec![],
            transcript_text: transcript.into(),
            transcript_final: true,
            live_transcript_text: String::new(),
            transcript_preview: transcript.into(),
            transcript_segments: 0,
            utterances,
            minutes,
            minutes_by_mode: Default::default(),
            recovery: Default::default(),
            export_markdown: String::new(),
            calendar_copy_revision: 0, calendar_copy_epoch: 0, calendar_copies: Vec::new(),
            exported_at: None,
            retention: CompanionV1SessionRetention {
                audio_cached: true,
                transcript_cached: true,
                minutes_cached: true,
                consent_required: true,
                retention_label: "7 days local".into(),
                expires_at: None,
            },
        }
    }

    fn minutes() -> CompanionV1MeetingMinutes {
        CompanionV1MeetingMinutes {
            processing: None,
            source_note_context: None, source_review_revision: None,
            generated_at: "2026-07-28T10:05:00Z".into(),
            source: "rules_l0".into(),
            quality: "draft".into(),
            summary: vec!["讨论了持久化".into()],
            decisions: vec!["决定：上线持久化".into()],
            action_items: vec![CompanionV1ActionItem {
                text: "陈明周五前验证".into(),
                owner: Some("陈明".into()),
                due: Some("周五".into()),
            }],
            questions: vec![],
            keywords: vec!["持久化".into()],
            markdown: "# Q3 Review".into(),
            llm_note: None,
        }
    }

    #[test]
    fn calendar_reminder_format_binds_choice_source_and_stale_saved_content() {
        let mut s=session("原话",vec![],Some(minutes()));
        s.minutes.as_mut().unwrap().markdown="## Action Items\n- [ ] 只买非深烘咖啡豆 (due: 2026-10-31T09:00:00+08:00)".into();
        let original=s.clone();
        let plain=prepare_meeting_export(&s,"offlineStore",MeetingExportFormat::Calendar).unwrap();
        let reminder=prepare_meeting_export(&s,"offlineStore",MeetingExportFormat::CalendarReminder).unwrap();
        assert_ne!(content_hash(&plain),content_hash(&reminder));
        assert!(require_unchanged(&reminder,Some(&content_hash(&plain))).is_err());
        let mut later=reminder.clone();
        later.bytes=String::from_utf8(later.bytes).unwrap().lines().map(|line|if line.starts_with("DTSTAMP:"){"DTSTAMP:20271028T010000Z"}else{line}).collect::<Vec<_>>().join("\r\n").into_bytes();
        later.bytes.extend_from_slice(b"\r\n");
        assert_eq!(content_hash(&reminder),content_hash(&later));
        s.minutes.as_mut().unwrap().markdown="## Action Items\n- [ ] 只买非深烘咖啡豆 (due: 2026-11-01T10:00:00+08:00)".into();
        let changed=prepare_meeting_export(&s,"offlineStore",MeetingExportFormat::CalendarReminder).unwrap();
        assert!(require_unchanged(&changed,Some(&content_hash(&reminder))).is_err());
        assert_eq!(original.title,s.title);assert_eq!(original.transcript_text,s.transcript_text);
    }

    #[test]
    fn render_txt_includes_title_and_speaker_tagged_transcript() {
        let s = session("说话人1: 你好\n说话人2: 谢谢", vec![], None);
        let out = render_txt(&s);
        assert!(out.contains("# Q3 Review"));
        assert!(out.contains("说话人1: 你好"));
    }

    #[test]
    fn render_json_includes_utterances_and_minutes() {
        let utts = vec![
            CompanionV1UtteranceSegment {
                text: "你好".into(),
                start_ms: 0,
                end_ms: 1500,
                speaker: Some(0),
            },
            CompanionV1UtteranceSegment {
                text: "谢谢".into(),
                start_ms: 1600,
                end_ms: 3000,
                speaker: Some(1),
            },
        ];
        let s = session("说话人1: 你好\n说话人2: 谢谢", utts, Some(minutes()));
        let out = render_json(&s).expect("json");
        assert!(out.contains("\"transcriptText\""));
        assert!(out.contains("\"utterances\""));
        assert!(out.contains("\"startMs\": 0"));
        assert!(out.contains("\"speaker\": 1"));
        assert!(out.contains("\"actionItems\""));
        assert!(out.contains("陈明周五前验证"));
    }

    #[test]
    fn render_srt_emits_timed_subtitles_with_speaker() {
        let utts = vec![
            CompanionV1UtteranceSegment {
                text: "你好".into(),
                start_ms: 0,
                end_ms: 1500,
                speaker: Some(0),
            },
            CompanionV1UtteranceSegment {
                text: "谢谢".into(),
                start_ms: 1_842_500,
                end_ms: 1_843_999,
                speaker: Some(1),
            },
        ];
        let s = session("irrelevant", utts, None);
        let out = render_srt(&s);
        assert!(out.contains("1\n00:00:00,000 --> 00:00:01,500\n说话人1: 你好\n\n"));
        // 1842500ms = 00:30:42,500 ; 1843999ms = 00:30:43,999
        assert!(out.contains("2\n00:30:42,500 --> 00:30:43,999\n说话人2: 谢谢"));
    }

    #[test]
    fn render_srt_empty_when_no_timing() {
        let s = session("plain text, no utterances", vec![], None);
        assert_eq!(render_srt(&s), "");
    }

    #[test]
    fn srt_timestamp_format() {
        assert_eq!(srt_timestamp(0), "00:00:00,000");
        assert_eq!(srt_timestamp(1500), "00:00:01,500");
        assert_eq!(srt_timestamp(3_661_001), "01:01:01,001");
    }

    #[test]
    fn action_items_todo_renders_checklist_with_meta() {
        let s = session("irrelevant", vec![], Some(minutes()));
        let out = render_action_items_todo(&s);
        assert!(out.contains("# Q3 Review — Action Items"));
        assert!(out.contains("- [ ] 陈明周五前验证 (owner: 陈明, due: 周五)"));
    }

    #[test]
    fn action_items_todo_handles_empty() {
        let m = CompanionV1MeetingMinutes {
            processing: None,
            action_items: vec![],
            ..minutes()
        };
        let s = session("x", vec![], Some(m));
        let out = render_action_items_todo(&s);
        assert!(out.contains("no action items captured"));
    }

    #[test]
    fn action_items_ical_emits_vtodo_with_due() {
        let s = session("irrelevant", vec![], Some(minutes()));
        let out = render_action_items_ical(&s);
        assert!(out.starts_with("BEGIN:VCALENDAR\r\n"));
        assert!(out.contains("BEGIN:VTODO\r\n"));
        assert!(out.contains("SUMMARY:陈明周五前验证"));
        assert!(!out.contains("DUE:"));
        assert!(out.contains("注明时间：周五"));
        assert!(out.contains("STATUS:NEEDS-ACTION\r\n"));
        assert!(out.ends_with("END:VCALENDAR\r\n"));
    }

    #[test]
    fn ical_escape_folds_long_lines_and_escapes_specials() {
        let folded = super::super::action_export::property("SUMMARY", "a;b,c\nd");
        assert!(folded.contains("SUMMARY:a\\;b\\,c\\nd\r\n"));
        let long = super::super::action_export::property("SUMMARY", &"x".repeat(200));
        // 75-octet first line, continuation lines start with a space.
        assert!(long.contains("\r\n "));
    }

    #[test]
    fn formal_export_is_bound_to_the_requested_mode_and_saved_variant() {
        let mut s = session("final transcript", vec![], Some(minutes()));
        s.minutes_by_mode.offline_store = Some(CompanionV1MinutesVariant {
            processing: None,
            source_note_context: None, source_review_revision: None,
            status: "minutesReady".to_string(),
            markdown: "# offline product".to_string(),
            source: "saved".to_string(),
            quality: "final".to_string(),
            generated_at: Some("2026-10-04T00:00:00Z".to_string()),
            partial_count: 0,
        });
        s.minutes_by_mode.online_live = Some(CompanionV1MinutesVariant {
            processing: None,
            source_note_context: None, source_review_revision: None,
            status: "minutesReady".to_string(),
            markdown: "# online product".to_string(),
            source: "saved".to_string(),
            quality: "final".to_string(),
            generated_at: Some("2026-10-04T00:00:01Z".to_string()),
            partial_count: 3,
        });

        let export = prepare_meeting_export(
            &s,
            "offlineStore",
            MeetingExportFormat::Markdown,
        )
        .expect("offline export");
        assert_eq!(String::from_utf8(export.bytes).unwrap(), "# offline product");
        let online = prepare_meeting_export(
            &s,
            "onlineLive",
            MeetingExportFormat::Markdown
        )
        .expect("independently saved online product");
        assert_eq!(String::from_utf8(online.bytes).unwrap(), "# online product");

        s.minutes_by_mode.online_live = None;
        assert!(prepare_meeting_export(&s, "onlineLive", MeetingExportFormat::Markdown)
            .unwrap_err()
            .contains("还没有保存"));
    }

    #[test]
    fn action_exports_use_selected_saved_edits_never_stale_structured_items() {
        let mut s = session("final transcript", vec![], Some(minutes()));
        s.minutes_by_mode.offline_store = Some(CompanionV1MinutesVariant {
            processing: None,
            source_note_context: None, source_review_revision: None,
            status: "minutesReady".into(), markdown: "## 行动项\n- [ ] 新任务 (due: 2026-10-09)".into(),
            source: "userEdited".into(), quality: "final".into(), generated_at: None, partial_count: 0,
        });
        s.minutes_by_mode.online_live = Some(CompanionV1MinutesVariant {
            processing: None,
            source_note_context: None, source_review_revision: None,
            status: "minutesReady".into(), markdown: "## Action Items\n- 第二模式任务".into(),
            source: "saved".into(), quality: "final".into(), generated_at: None, partial_count: 1,
        });
        let todo = prepare_meeting_export(&s, "offlineStore", MeetingExportFormat::Todo).unwrap();
        let content = String::from_utf8(todo.bytes).unwrap();
        assert!(content.contains("新任务")); assert!(!content.contains("陈明"));
        assert!(todo.suggested_name.ends_with("-待办清单.md"));
        let ics = String::from_utf8(prepare_meeting_export(&s, "offlineStore", MeetingExportFormat::Ics).unwrap().bytes).unwrap();
        assert!(ics.contains("DUE;VALUE=DATE:20261009"));
        let online = String::from_utf8(prepare_meeting_export(&s, "onlineLive", MeetingExportFormat::Todo).unwrap().bytes).unwrap();
        assert!(online.contains("第二模式任务")); assert!(!online.contains("新任务"));
        s.minutes_by_mode.offline_store.as_mut().unwrap().markdown = "## 行动项\n- 无".into();
        assert!(prepare_meeting_export(&s, "offlineStore", MeetingExportFormat::Ics).unwrap_err().contains("没有可导出"));
    }

    #[test]
    fn plain_checklist_keeps_saved_conditions_and_original_data() {
        let mut s=session("这是原话，不是本次要带走的清单",vec![],Some(minutes()));
        s.minutes_by_mode.offline_store=Some(CompanionV1MinutesVariant {
            processing:None,source_note_context:None,source_review_revision:None,
            status:"minutesReady".into(),source:"userAuthored".into(),quality:"final".into(),
            markdown:"## 行动项\n- [ ] 预算未确认先不买礼物 (due: 2026-10-29T20:00:00+08:00, owner: 我)\n- [x] 找到非深烘咖啡豆".into(),
            generated_at:Some("2026-10-27T06:00:00Z".into()),partial_count:0,
        });
        let before=serde_json::to_value(&s).unwrap();
        let plain=prepare_meeting_export(&s,"offlineStore",MeetingExportFormat::TodoText).unwrap();
        let text=std::str::from_utf8(&plain.bytes).unwrap();
        assert!(plain.suggested_name.ends_with("-待办清单.txt"));
        assert!(text.contains("预算未确认先不买礼物"));
        assert!(text.contains("20:00")&&text.contains("我"));
        assert!(text.contains("[x] 找到非深烘咖啡豆"));
        assert!(!text.contains("这是原话")&&!text.contains("陈明")&&!text.starts_with("# "));
        assert_eq!(serde_json::to_value(&s).unwrap(),before);
        s.minutes_by_mode.offline_store.as_mut().unwrap().source_review_revision=Some(99);
        assert!(prepare_meeting_export(&s,"offlineStore",MeetingExportFormat::TodoText).is_err());
    }

    #[test]
    fn draft_markdown_is_exportable_but_visibly_labeled() {
        let mut s = session("final transcript", vec![], Some(minutes()));
        s.minutes_by_mode.offline_store = Some(CompanionV1MinutesVariant {
            processing: None,
            source_note_context: None, source_review_revision: None,
            status: "retryPending".to_string(),
            markdown: "# 本机草稿".to_string(),
            source: "rules_l0".to_string(),
            quality: "draft".to_string(),
            generated_at: Some("2026-10-04T00:00:00Z".to_string()),
            partial_count: 0,
        });
        let export = prepare_meeting_export(
            &s,
            "offlineStore",
            MeetingExportFormat::Markdown,
        )
        .unwrap();
        let content = String::from_utf8(export.bytes).unwrap();
        assert!(content.starts_with("> 草稿："));
        assert!(content.contains("# 本机草稿"));
    }

    #[test]
    fn legacy_completed_transcript_remains_exportable_but_partial_does_not() {
        let mut legacy = session("legacy final", vec![], None);
        legacy.transcript_final = false;
        legacy.recovery = Default::default();
        legacy.status = "transcribed".to_string();
        assert!(prepare_meeting_export(&legacy, "offlineStore", MeetingExportFormat::Txt).is_ok());

        legacy.status = "recording".to_string();
        assert!(prepare_meeting_export(&legacy, "offlineStore", MeetingExportFormat::Txt)
            .unwrap_err()
            .contains("尚未整理完成"));
    }

    #[test]
    fn formal_srt_export_rejects_missing_or_fabricated_timing() {
        let s = session("final transcript", vec![], None);
        assert!(prepare_meeting_export(&s, "offlineStore", MeetingExportFormat::Srt)
            .unwrap_err()
            .contains("真实时间轴"));

        let s = session(
            "final transcript",
            vec![CompanionV1UtteranceSegment {
                text: "text".to_string(),
                start_ms: 1_000,
                end_ms: 1_000,
                speaker: None,
            }],
            None,
        );
        assert!(prepare_meeting_export(&s, "offlineStore", MeetingExportFormat::Srt)
            .unwrap_err()
            .contains("真实时间轴"));
    }

    #[test]
    fn atomic_export_replaces_destination_with_exact_bytes() {
        let directory = std::env::temp_dir().join(format!(
            "companion-export-{}",
            uuid::Uuid::new_v4().simple()
        ));
        std::fs::create_dir_all(&directory).unwrap();
        let destination = directory.join("minutes.md");
        std::fs::write(&destination, b"old").unwrap();
        let bytes = "# 已保存纪要\n".as_bytes();
        assert_eq!(write_atomic(&destination, bytes).unwrap(), bytes.len() as u64);
        assert_eq!(std::fs::read(&destination).unwrap(), bytes);
        assert_eq!(
            std::fs::read_dir(&directory).unwrap().count(),
            1,
            "temporary file must not remain after commit"
        );
        std::fs::remove_dir_all(directory).unwrap();
    }
    #[test]
    fn r64_storage_full_and_permission_errors_offer_the_matching_recovery_action() {
        use std::io::{Error,ErrorKind};
        // OS error classification only, not physical-disk-full qualification.
        let full=local_write_error("提交接收文件",&Error::new(ErrorKind::StorageFull,"storage-full-model"));
        assert!(full.contains("磁盘空间不足")&&full.contains("保存未完成")&&full.contains("storage-full-model"));
        for kind in [ErrorKind::PermissionDenied,ErrorKind::ReadOnlyFilesystem] {
            let denied=local_write_error("提交接收文件",&Error::new(kind,"permission-model"));
            assert!(denied.contains("目录权限或解除文件占用")&&!denied.contains("磁盘空间不足"));
        }
    }
    #[cfg(windows)]
    #[test]
    fn r64_commit_preserves_win32_storage_class_without_truncating_other_hresult_facilities() {
        use windows::core::{Error,HRESULT};
        let full=windows_commit_error(Error::from_hresult(HRESULT(0x80070070u32 as i32)));
        assert!(full.contains("磁盘空间不足")&&full.contains("os error 112"));
        let occupied=windows_commit_error(Error::from_hresult(HRESULT(0x80070020u32 as i32)));
        assert!(occupied.contains("文件占用")&&occupied.contains("os error 32"),"{occupied}");
        let other=windows_commit_error(Error::from_hresult(HRESULT(0x80040070u32 as i32)));
        assert!(!other.contains("磁盘空间不足"),"another facility is not Windows disk-full error 112");
    }
    #[test]
    fn p636_calendar_export_follows_saved_mode_source_hash_and_unchanged_state() {
        let mut s=session("原话保留，不用重录",vec![],None);
        let variant=|text:&str|CompanionV1MinutesVariant {
            processing:None,source_note_context:None,source_review_revision:None,
            status:"minutesReady".into(),quality:"final".into(),source:"userEdited".into(),
            markdown:text.into(),generated_at:None,partial_count:0,
        };
        s.minutes_by_mode.offline_store=Some(variant("## 行动项\n- [ ] 带证件 (due: 2026-11-05T16:30:00+08:00)\n- [ ] 待确认 (due: 周五)"));
        s.minutes_by_mode.online_live=Some(variant("## 行动项\n- [ ] 线上安排 (due: 2026-11-06)"));
        let before=serde_json::to_value(&s).unwrap();
        let prepared=prepare_meeting_export(&s,"offlineStore",MeetingExportFormat::Calendar).unwrap();
        let text=String::from_utf8(prepared.bytes.clone()).unwrap();
        assert!(prepared.suggested_name.ends_with("日历日程.ics"));
        assert!(text.contains("DTSTART:20261105T083000Z"));assert!(!text.contains("线上安排"));
        assert!(prepared.warning.as_ref().unwrap().contains("1项尚无"));
        let mut restamped=prepared.clone();
        restamped.bytes=text.split_inclusive("\r\n").map(|line|if line.starts_with("DTSTAMP:"){"DTSTAMP:20261101T000000Z\r\n"}else{line}).collect::<String>().into_bytes();
        assert_eq!(content_hash(&prepared),content_hash(&restamped));
        require_unchanged(&restamped,Some(&content_hash(&prepared))).unwrap();
        s.minutes_by_mode.offline_store.as_mut().unwrap().markdown.push_str("\n- [ ] 改后的任务 (due: 2026-11-07)");
        let changed=prepare_meeting_export(&s,"offlineStore",MeetingExportFormat::Calendar).unwrap();
        assert!(require_unchanged(&changed,Some(&content_hash(&prepared))).is_err());
        assert_ne!(content_hash(&prepared),content_hash(&prepare_meeting_export(&s,"offlineStore",MeetingExportFormat::Ics).unwrap()));
        s.minutes_by_mode.offline_store.as_mut().unwrap().markdown="## 行动项\n- [ ] 待确认 (due: 周五)".into();
        assert!(prepare_meeting_export(&s,"offlineStore",MeetingExportFormat::Calendar).unwrap_err().contains("没有可导出的日历日程"));
        assert_eq!(s.transcript_text,before["transcriptText"].as_str().unwrap());
    }
    #[test]
    fn p612_calendar_handoff_follows_saved_mode_and_preserves_unparsed_time_as_text() {
        let mut s=session("原话：明天下午三点检查样品",vec![],None);
        let variant=|due:&str|CompanionV1MinutesVariant {
            processing:None,source_note_context:None,source_review_revision:None,
            status:"minutesReady".into(),quality:"final".into(),source:"userEdited".into(),
            markdown:format!("## Action Items\n- [ ] 检查样品 (due: {due})"),
            generated_at:None,partial_count:0,
        };
        s.minutes_by_mode.offline_store=Some(variant("2026-10-26 15:00"));
        s.minutes_by_mode.online_live=Some(variant("2026-10-26T15:00:00+08:00"));
        let before=serde_json::to_value(&s).unwrap();
        let unconfirmed=prepare_meeting_export(&s,"offlineStore",MeetingExportFormat::Ics).unwrap();
        assert!(unconfirmed.warning.unwrap().contains("1项时间"));
        let plain=String::from_utf8(unconfirmed.bytes).unwrap();
        assert!(!plain.contains("\r\nDUE"));assert!(plain.contains("2026-10-26 15:00"));
        let confirmed=prepare_meeting_export(&s,"onlineLive",MeetingExportFormat::Ics).unwrap();
        assert!(confirmed.warning.is_none());assert!(String::from_utf8(confirmed.bytes).unwrap().contains("DUE:20261026T070000Z\r\n"));
        assert!(prepare_meeting_export(&s,"offlineStore",MeetingExportFormat::Todo).unwrap().warning.is_none());
        assert_eq!(serde_json::to_value(&s).unwrap(),before,"export must not rewrite speech, notes, saved time or another mode");
        s.minutes_by_mode.offline_store=Some(variant("2028-02-29"));
        let date=prepare_meeting_export(&s,"offlineStore",MeetingExportFormat::Ics).unwrap();
        assert!(date.warning.is_none());assert!(String::from_utf8(date.bytes).unwrap().contains("DUE;VALUE=DATE:20280229\r\n"));
    }

    #[test]
    fn p622_preview_binds_saved_content_not_export_clock() {
        let s=session("原话保留",vec![],None);
        let prepared=|stamp:&str,title:&str,due:&str|PreparedMeetingExport{
            bytes:format!("BEGIN:VCALENDAR\r\nDTSTAMP:{stamp}\r\nSUMMARY:{title}\r\nDUE:{due}\r\nEND:VCALENDAR\r\n").into_bytes(),
            suggested_name:"测试.ics".into(),format:MeetingExportFormat::Ics,warning:None};
        let a=prepared("20261027T010000Z","带身份证","20261028T120000Z");
        let later=prepared("20261027T020000Z","带身份证","20261028T120000Z");
        let digest=content_hash(&a);assert_eq!(digest,content_hash(&later));
        assert!(require_unchanged(&later,Some(&digest)).is_ok());
        for changed in [prepared("20261027T020000Z","带充电线","20261028T120000Z"),
            prepared("20261027T020000Z","带身份证","20261029T120000Z")] {
            assert!(require_unchanged(&changed,Some(&digest)).unwrap_err().contains("未写入文件"));
        }
        assert!(require_unchanged(&a,Some("wrong")).is_err());
        assert!(require_unchanged(&a,None).is_ok());
        assert_eq!(s.transcript_text,"原话保留");
    }

    #[test]
    fn copy_checklist_keeps_checks_unicode_and_literal_time_without_title_task() {
        let prepared=PreparedMeetingExport{
            suggested_name:"清单.md".into(),
            format:MeetingExportFormat::Todo,
            bytes:"# 出差准备 — 待办事项\n- [ ] 带身份证（注明时间：明天上午）\n- [x] 已确认回程\n".as_bytes().to_vec(),
            warning:None,
        };
        let copied=checklist_copy_text(&prepared).unwrap();
        assert_eq!(copied,"- [ ] 带身份证（注明时间：明天上午）\n- [x] 已确认回程");
        assert!(String::from_utf8(prepared.bytes).unwrap().starts_with("# 出差准备"));
    }

    #[test]
    fn calendar_advance_reminder_hashes_bind_each_choice_without_moving_deadline() {
        let mut s=session("原话",vec![],Some(minutes()));
        s.minutes.as_mut().unwrap().markdown="## 行动项\n- [ ] 未测完不要写通过 (due: 2026-11-06T15:00:00+08:00前)".into();
        let plain=prepare_meeting_export(&s,"offlineStore",MeetingExportFormat::Calendar).unwrap();
        let at=prepare_meeting_export(&s,"offlineStore",MeetingExportFormat::CalendarReminder).unwrap();
        let half=prepare_meeting_export(&s,"offlineStore",MeetingExportFormat::CalendarReminder30).unwrap();
        let hour=prepare_meeting_export(&s,"offlineStore",MeetingExportFormat::CalendarReminder60).unwrap();
        let hashes=[content_hash(&plain),content_hash(&at),content_hash(&half),content_hash(&hour)];
        assert_eq!(hashes.iter().collect::<std::collections::HashSet<_>>().len(),4);
        assert!(require_unchanged(&hour,Some(&hashes[2])).is_err());
        assert!(require_unchanged(&half,Some(&hashes[2])).is_ok());
        for value in [&plain,&at,&half,&hour] {assert!(String::from_utf8_lossy(&value.bytes).contains("DTSTART:20261106T070000Z\r\n"));}
    }

}
