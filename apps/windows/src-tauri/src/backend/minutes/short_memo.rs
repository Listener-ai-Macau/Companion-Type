//! Conservative source extraction for a short, explicitly planned personal list.
//! Every returned item is a literal source clause. No identity/date resolution.
use crate::companion_v1::{CompanionV1ActionItem, CompanionV1HostSession};
use std::{borrow::Cow, sync::LazyLock};

pub(super) fn actions(session: &CompanionV1HostSession) -> Option<Vec<CompanionV1ActionItem>> {
    plan_clauses(&session.transcript_text,session.duration_ms,true).map(|clauses|clauses.into_iter()
        .map(|(text,_)|CompanionV1ActionItem{text,owner:None,due:None}).collect())
}

// The key is only the literal positive verb/object after an explicit source
// time/connector. It is used for exact duplicates, never semantic/date guesses.
fn plan_clauses(source:&str,duration_ms:u64,require_intent:bool)->Option<Vec<(String,String)>> {
    let text = source.trim();
    if text.is_empty() || text.chars().count() > 280 || duration_ms > 120_000 {
        return None;
    }
    // A short discussion, question, cancelled plan or report is not a task list.
    // Unknown input falls back to the unchanged meeting extraction, not a guess.
    if ["?", "？", "吗", "呢", "是否", "要不要", "会不会", "能不能", "如果", "假如", "假设",
        "可能", "也许", "或许", "建议", "希望", "考虑", "取消", "不要", "不再", "不用", "无需",
        "没有", "尚未", "未完成", "不是", "不打算", "但是", "不过", "昨天", "前天", "上周", "上星期",
        "已经", "刚才", "刚刚", "曾经", "当时", "做完", "完成了", "买过", "取过", "碰到", "遇到",
        "的时候", "的人", "很贵", "很便宜", "很难", "真好", "取决于", "取得", "说过", "听说",
        "不到", "不了", "没能", "不能", "不会", "只是", "还是", "还会", "还有", "还要"]
        .iter().any(|marker| text.contains(marker)) {
        return None;
    }
    static PREFIX: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"^(?:(?:提醒我|记得|我要|我会|我得|我需要|待办(?:事项)?[：:]?|记一下[：:]?)\s*)?(?:(?:今天|今晚|明天|明早|明晚|后天|本周|这周|下周|周[一二三四五六日天末]|星期[一二三四五六日天]|本月|下个月|月底)(?:上午|下午|中午|晚上|早上|傍晚)?(?:[零〇一二三四五六七八九十百0-9]{1,5}(?:点|时)(?:半|[零〇一二三四五六七八九十0-9]{1,3}分?)?)?(?:之前|前|之后|后)?\s*)?"
    ).expect("constant memo intent prefix"));
    static CONNECTOR: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"^(?:然后|顺路|顺便|接着|并且|同时|再)\s*"
    ).expect("constant memo list connector"));
    const VERBS: &[&str] = &["打电话", "发邮件", "发消息", "发送", "回复", "联系", "预约", "预订", "购买",
        "领取", "归还", "寄出", "提交", "交付", "检查", "确认", "核对", "完成", "整理", "补交",
        "缴纳", "支付", "带上", "送到", "打印", "备份", "买", "取", "寄", "还", "带", "拿", "订", "缴", "付", "送", "查", "修"];
    let text=if !require_intent {
        text.split_once(['：',':']).filter(|(label,_)|label.chars().count()<=12
            && (label.ends_with("补充")||matches!(*label,"备注"|"说明"|"准备事项"|"待办")))
            .map_or(text,|(_,body)|body.trim())
    } else {text};
    static CONTEXT_CONNECTOR:LazyLock<regex::Regex>=LazyLock::new(||regex::Regex::new(
        r"^(?:然后|顺路|顺便|接着|并且|同时|再|先|并|出门前|出门|回家前|上班前|开会前)\s*"
    ).expect("constant context connector"));
    let clauses = text.split(['，', ',', '；', ';', '。', '.', '！', '!', '\n'])
        .map(str::trim).filter(|clause| !clause.is_empty()).collect::<Vec<_>>();
    if clauses.is_empty() || clauses.len() > 8 { return None; }
    let mut items: Vec<(String,String)> = Vec::new();
    for (index, clause) in clauses.iter().enumerate() {
        if clause.chars().count() > 100 || clause.ends_with('了') { return None; }
        let connected = if !require_intent {
            let mut value=(*clause).to_string();
            for _ in 0..3 {
                let next=CONTEXT_CONNECTOR.replace(&value,"").into_owned();
                if next==value {break;} value=next;
            }
            Cow::Owned(value)
        } else if index == 0 { Cow::Borrowed(*clause) } else { CONNECTOR.replace(clause, "") };
        let prefix = PREFIX.find(&connected)?;
        // The first clause must state an intention or time. Later literal
        // clauses may share the list context, never owner/deadline metadata.
        if require_intent && index == 0 && prefix.end() == 0 { return None; }
        let action = connected[prefix.end()..].trim();
        // A purpose explains the preceding literal preparation; it is not a
        // new task or a cancellation. Preserve its wording with that entry.
        if !require_intent && action.strip_prefix("避免").is_some_and(|purpose|!purpose.trim().is_empty()) {
            items.last_mut()?.0.push_str(&format!("，{clause}"));
            continue;
        }
        let starts_with_verb=|value:&str,verbs:&[&str]|verbs.iter()
            .any(|verb|value.strip_prefix(verb).is_some_and(|object|!object.trim().is_empty()));
        const PREPARATION_VERBS:&[&str]=&["找好","找齐","找到","看看","看一下","查看","询问","问一下","准备","备好","找","看","问"];
        let contextual_positive=!require_intent && (
            starts_with_verb(action,PREPARATION_VERBS)
            || action.strip_prefix("把").is_some_and(|body|
                ["找好","找齐","准备好","带好","带上","放好","整理好","收好","保存好","核对好","检查好","确认好"]
                    .iter().any(|ending|body.strip_suffix(ending).is_some_and(|object|
                        !object.trim().is_empty()&&object.chars().count()<=48)))
            || action.split_once(['先','再']).is_some_and(|(topic,verb)|
                !topic.trim().is_empty()&&topic.chars().count()<=24
                    &&(starts_with_verb(verb,VERBS)||starts_with_verb(verb,PREPARATION_VERBS))));
        if !starts_with_verb(action,VERBS) && !contextual_positive {
            return None;
        }
        items.push(((*clause).into(),action.to_string()));
    }
    Some(items)
}

pub(super) fn restore_literal_actions(minutes: &mut super::CompanionV1MeetingMinutes,
    session: &CompanionV1HostSession) -> bool {
    let Some(actions) = actions(session) else { return false; };
    let unchanged = minutes.action_items.len() == actions.len()
        && minutes.action_items.iter().zip(&actions)
            .all(|(left,right)| left.text == right.text && left.owner == right.owner && left.due == right.due);
    if unchanged { return false; }
    // A provider may omit an explicit list or add an unsupported attribution.
    // The deterministic source clauses are authoritative for this narrow path.
    minutes.action_items = actions;
    true
}

// Only a fully explicit, positive short source list plus fully explicit,
// positive supplements qualifies. Unknown/cancelled/conditional input retains
// the existing conservative provider path instead of reviving cancelled tasks.
pub(super) fn context_actions(session:&CompanionV1HostSession)->Option<Vec<CompanionV1ActionItem>> {
    if session.meeting_notes.is_empty(){return None;}
    let original=plan_clauses(&session.transcript_text,session.duration_ms,true)?;
    let mut notes=Vec::new();
    for note in &session.meeting_notes { notes.extend(plan_clauses(&note.text,0,false)?); }
    if notes.is_empty()||notes.len()+original.len()>12{return None;}
    let explicit_order=notes.iter().any(|(text,_)|text.starts_with("先")||text.starts_with("出门"));
    let mut result=Vec::new();let mut seen=std::collections::HashSet::new();
    if explicit_order {
        for (text,key) in &notes {
            if seen.insert(key.clone()){result.push(CompanionV1ActionItem{text:format!("用户补充：{text}"),owner:None,due:None});}
        }
        for (text,key) in original {
            if seen.insert(key){result.push(CompanionV1ActionItem{text,owner:None,due:None});}
        }
    } else {
        for (text,key) in original {
            if seen.insert(key.clone()) {
                let text=notes.iter().find(|(_,candidate)|candidate==&key)
                    .map_or(text,|(text,_)|format!("用户补充：{text}"));
                result.push(CompanionV1ActionItem{text,owner:None,due:None});
            }
        }
        for (text,key) in notes {
            if seen.insert(key){result.push(CompanionV1ActionItem{text:format!("用户补充：{text}"),owner:None,due:None});}
        }
    }
    Some(result)
}
