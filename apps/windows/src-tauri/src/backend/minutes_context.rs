//! One-time, revision-bound use of saved user context. Never alters ASR or
//! persists authorization to resend supplements during background recovery.
use serde::{Deserialize, Serialize};
use crate::companion_v1::CompanionV1HostSession;

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Source {
    pub note_revision: u64,
    pub source_transcript_text: String,
    pub notes: Vec<super::meeting_notes::Note>,
}

pub(crate) fn validate(session: &CompanionV1HostSession, revision: u64) -> Result<(), String> {
    if session.note_revision != revision {
        return Err("补充已变化，请先核对，再选择是否用于这次整理；本次未提交。".into());
    }
    if session.meeting_notes.is_empty() {
        return Err("还没有已保存的补充，本次未提交。".into());
    }
    if std::env::var("COMPANION_TYPE_MINUTES_COMMAND").ok().is_some_and(|v| !v.trim().is_empty()) {
        return Err("当前自定义整理命令尚未支持补充来源，本次未提交；可先仅按原话整理。".into());
    }
    Ok(())
}

pub(crate) fn source(session: &CompanionV1HostSession) -> Source {
    Source { note_revision: session.note_revision,
        source_transcript_text: super::transcript_review::effective_text(session),
        notes: session.meeting_notes.clone() }
}

pub(crate) fn current(session: &CompanionV1HostSession, context: &Option<Source>) -> bool {
    context.as_ref().is_none_or(|context| context.note_revision == session.note_revision
        && context.notes == session.meeting_notes
        && context.source_transcript_text == super::transcript_review::effective_text(session))
}

pub(crate) fn notice(context: &Source) -> String {
    let mut result = format!("> 本次依据录音文字＋用户明确选择的补充整理（补充版本{}）。补充不是原始录音识别，原话单独保留。\n\n## 本次使用的用户补充\n",context.note_revision);
    for (i,note) in context.notes.iter().enumerate() {
        result.push_str(&format!("\n补充{}：\n",i+1));
        for line in note.text.lines() { result.push_str("> "); result.push_str(line); result.push('\n'); }
    }
    result
}
