//! Optional source references for the ordinary single-request AI minutes path.
//! These are reading aids, not proof that an AI paraphrase is semantically true.
use serde_json::Value;
use crate::companion_v1::{CompanionV1ActionItem,CompanionV1MeetingMinutes};

pub(super) const PROMPT:&str="\n可额外返回 evidence 数组，格式为 {field: summary|decisions|actionItems|questions, index: 对应数组的零起始下标, quote: 转写中的连续原话}。为能对应原话的条目提供引用；只复制原文，不要拼接、改写或虚构。没有把握就省略引用；不影响其余纪要和任务。";
const MARKER:&str="\n\n## 原话核对\n\n> 以下原话由 AI 关联，仅供核对；关联和转写可能有误。\n\n";
#[derive(Clone,Debug)]
enum Item { Summary(String),Decision(String),Question(String),Action(CompanionV1ActionItem) }
#[derive(Clone,Debug)]
pub(super) struct Entry {item:Item, quote:String}

// A provider may omit or mangle this optional field. Only retain bounded,
// verbatim single-line source excerpts and a valid source-item index.
pub(super) fn capture(object:&Value, minutes:&CompanionV1MeetingMinutes, transcript:&str)->Vec<Entry> {
    let Some(values)=object.get("evidence").and_then(Value::as_array) else{return Vec::new()};
    let mut out=Vec::new();
    for value in values.iter().take(256) {
        let (Some(field),Some(index),Some(quote))=(value.get("field").and_then(Value::as_str),
            value.get("index").and_then(Value::as_u64).and_then(|v|usize::try_from(v).ok()),
            value.get("quote").and_then(Value::as_str)) else{continue};
        if quote.trim()!=quote || quote.is_empty() || quote.len()>1024 || quote.contains(['\r','\n']) || !transcript.contains(quote) {continue;}
        let item=match field {
            "summary"=>minutes.summary.get(index).cloned().map(Item::Summary),
            "decisions"=>minutes.decisions.get(index).cloned().map(Item::Decision),
            "questions"=>minutes.questions.get(index).cloned().map(Item::Question),
            "actionItems"=>minutes.action_items.get(index).cloned().map(Item::Action),
            _=>None,
        };
        let Some(item)=item else{continue};
        let text=match &item{Item::Summary(t)|Item::Decision(t)|Item::Question(t)=>t,Item::Action(a)=>&a.text};
        if text.trim().is_empty() || text.len()>1024 || text.contains(['\r','\n']) {continue;}
        out.push(Entry{item,quote:quote.to_owned()});
    }
    out
}

// The finalizer may remove or rewrite items, so associate only items that
// still exist in the saved result; no unsupported item blocks generation.
pub(super) fn append(minutes:&mut CompanionV1MeetingMinutes, entries:&[Entry]) {
    if minutes.processing.is_some() || minutes.source!="llm_deepseek" || minutes.markdown.contains(MARKER) {return;}
    let mut lines=String::new();let mut seen=std::collections::HashSet::new();
    for entry in entries {
        let (label,text,present)=match &entry.item {
            Item::Summary(t)=>("摘要",t,minutes.summary.contains(t)),
            Item::Decision(t)=>("决定",t,minutes.decisions.contains(t)),
            Item::Question(t)=>("问题",t,minutes.questions.contains(t)),
            Item::Action(a)=>("事项",&a.text,minutes.action_items.iter().any(|v|v.text==a.text&&v.owner==a.owner&&v.due==a.due)),
        };
        if !present || !seen.insert((label,text.as_str(),entry.quote.as_str())) {continue;}
        lines.push_str(&format!("- {label}：{text}\n- 原话：“{}”\n\n",entry.quote));
    }
    if !lines.is_empty(){minutes.markdown.push_str(MARKER);minutes.markdown.push_str(lines.trim_end());minutes.markdown.push('\n');}
}

#[cfg(test)]
mod tests {
    use super::*;
    fn minutes()->CompanionV1MeetingMinutes {
        CompanionV1MeetingMinutes{processing:None,source_note_context:None,source_review_revision:None,
            generated_at:"now".into(),source:"llm_deepseek".into(),quality:"final".into(),
            summary:vec!["讨论产品包装".into()],decisions:vec![],questions:vec![],
            action_items:vec![CompanionV1ActionItem{text:"整理报价".into(),owner:Some("小王".into()),due:Some("周五".into())}],
            keywords:vec![],markdown:"# 会议\n\n## 待办\n\n- 整理报价".into(),llm_note:None}
    }
    #[test]
    fn source_quotes_are_optional_verbatim_and_still_bound_to_final_items() {
        let source="明天下午讨论产品包装。小王负责整理报价，周五之前发给大家。";
        let object=serde_json::json!({"evidence":[
            {"field":"summary","index":0,"quote":"明天下午讨论产品包装。"},
            {"field":"actionItems","index":0,"quote":"小王负责整理报价，周五之前发给大家。"},
            {"field":"actionItems","index":0,"quote":"小王周一发送报价"},
            {"field":"summary","index":3,"quote":"明天下午讨论产品包装。"},
            {"field":"unknown","index":0,"quote":"明天下午讨论产品包装。"}
        ]});
        let mut result=minutes();let entries=capture(&object,&result,source);assert_eq!(entries.len(),2);
        // If later source checks remove or revise an action, do not attach
        // its old quote to the revised action or suggest the metadata is exact.
        result.action_items[0].due=Some("周一".into());append(&mut result,&entries);
        assert!(result.markdown.contains("## 原话核对"));assert!(result.markdown.contains("明天下午讨论产品包装。"));
        assert!(!result.markdown.contains("小王负责整理报价"));assert!(!result.markdown.contains("小王周一发送报价"));
        let before=result.markdown.clone();append(&mut result,&entries);assert_eq!(result.markdown,before);
    }
    #[test]
    fn missing_or_invalid_evidence_never_blocks_minutes() {
        let mut result=minutes();let before=result.markdown.clone();
        for object in [serde_json::json!({}),serde_json::json!({"evidence":"bad"}),
          serde_json::json!({"evidence":[{"field":"summary","index":0,"quote":"不存在"}]})] {
            let entries=capture(&object,&result,"原文");append(&mut result,&entries);
        }
        assert_eq!(result.markdown,before);assert_eq!(result.quality,"final");
    }
}
