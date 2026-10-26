//! Export only action items explicitly present in the selected saved document.
//! RFC 5545: https://www.rfc-editor.org/rfc/rfc5545.html (3.1, 3.6.2, 3.8.2.3).
use chrono::{DateTime, NaiveDate, Utc};
use sha2::{Digest, Sha256};
use std::sync::LazyLock;

// Aligned with UI savedActions::emptyActionNotice. Exclude only anchored
// no-task statements, never a task merely containing a negative quotation.
fn empty_action_notice(text:&str)->bool {
    let value=text.trim().trim_end_matches(['.','。']);
    // Same matched, whole absence wrapper as UI emptyActionNotice. Only a
    // complete already supported absence explanation is excluded; original
    // saved prose is never changed and negative words in a real task stay.
    static WRAPPED:LazyLock<regex::Regex>=LazyLock::new(||regex::Regex::new(
        r"(?i)^(?:无|暂无|none(?: captured)?)\s*(?:（([^（）()\r\n]+)）|\(([^（）()\r\n]+)\))$"
    ).expect("constant wrapped empty action notice"));
    if let Some(captures)=WRAPPED.captures(value) {
        let explanation=captures.get(1).or_else(||captures.get(2)).unwrap().as_str().trim().trim_end_matches(['.','。']);
        // Do not reuse top-level free explanatory tails inside a new wrapper:
        // they could contain another real instruction. Preserve unknown text.
        static ATOMIC_CHINESE:LazyLock<regex::Regex>=LazyLock::new(||regex::Regex::new(
            r"^(?:(?:转写|原文|录音|本次|当前|会议|文中|内容)(?:中|里)?[，,：:\s]*)?(?:未(?:明确)?(?:给出|提及|记录|识别|提取)(?:明确的?|具体的?)?|没有(?:明确的?|具体的?)?|暂无|无)(?:行动项|待办(?:事项)?|跟进任务|可执行任务|任务)(?:[、或和及](?:负责人|责任人|截止时间|截止日期|截止日|日期|时间))*$"
        ).expect("constant atomic Chinese absence explanation"));
        static ATOMIC_ENGLISH:LazyLock<regex::Regex>=LazyLock::new(||regex::Regex::new(
            r"(?i)^no (?:action items?|tasks?|to-dos?)(?:\s+(?:were |was |are |is )?(?:identified|captured|recorded|found|specified|available|mentioned))?$"
        ).expect("constant atomic English absence explanation"));
        if matches!(explanation.to_lowercase().as_str(),"none captured"|"none"|"无"|"暂无"|"无行动项"|"暂无行动项"|"待确认")
            || ATOMIC_CHINESE.is_match(explanation) || ATOMIC_ENGLISH.is_match(explanation) { return true; }
    }
    if matches!(value.to_lowercase().as_str(),"none captured"|"none"|"无"|"暂无"|"无行动项"|"暂无行动项"|"待确认") { return true; }
    static NOTICE:LazyLock<regex::Regex>=LazyLock::new(||regex::Regex::new(
        r"^(?:(?:转写|原文|录音|本次|当前|会议|文中|内容)(?:中|里)?[，,：:\s]*)?(?:未(?:明确)?(?:给出|提及|记录|识别|提取)(?:明确的?|具体的?)?|没有(?:明确的?|具体的?)?|暂无|无)(?:行动项|待办(?:事项)?|跟进任务|可执行任务|任务)(?:[、，,。；;：:\s].*)?$"
    ).expect("constant empty action notice"));
    static ENGLISH:LazyLock<regex::Regex>=LazyLock::new(||regex::Regex::new(
        r"(?i)^no (?:action items?|tasks?|to-dos?)(?:\s+(?:were |was |are |is )?(?:identified|captured|recorded|found|specified|available|mentioned).*)?$"
    ).expect("constant English empty action notice"));
    NOTICE.is_match(value)||ENGLISH.is_match(value)
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Action {
    pub text: String,
    pub completed: bool,
    pub due: Option<String>,
}

/// Deliberately conservative: prose/decisions are never turned into tasks.
pub fn parse_saved_actions(markdown: &str) -> Vec<Action> {
    let mut actions: Vec<Action> = Vec::new();
    let mut in_actions = false;
    let mut section_level = 0;
    let mut fence: Option<char> = None;
    for raw in markdown.lines() {
        let line = raw.trim();
        if line.starts_with("```") || line.starts_with("~~~") {
            let marker = line.chars().next().unwrap();
            if fence == Some(marker) { fence = None; } else if fence.is_none() { fence = Some(marker); }
            continue;
        }
        if fence.is_some() { continue; }
        let level = line.chars().take_while(|c| *c == '#').count();
        if level > 0 && line.as_bytes().get(level) == Some(&b' ') {
            let heading = line[level..].trim().trim_end_matches('#').trim().to_lowercase();
            let heading = heading.trim_matches('*').trim_end_matches([':', '：']);
            if matches!(heading, "action items" | "actions" | "todo" | "to-do" | "行动项" | "待办" | "待办事项" | "行动计划") {
                in_actions = true; section_level = level;
            } else if level <= section_level { in_actions = false; }
            continue;
        }
        if !in_actions { continue; }
        let body = line.strip_prefix("- ").or_else(|| line.strip_prefix("* "))
            .or_else(|| line.strip_prefix("+ ")).or_else(|| {
                let end = line.find(|c: char| !c.is_ascii_digit())?;
                if end == 0 { return None; }
                line[end..].strip_prefix(". ").or_else(|| line[end..].strip_prefix(") "))
            });
        let Some(body) = body else { continue; };
        let completed = body.starts_with("[x] ") || body.starts_with("[X] ");
        let text = body.strip_prefix("[ ] ").or_else(|| body.strip_prefix("[x] "))
            .or_else(|| body.strip_prefix("[X] ")).unwrap_or(body).trim();
        if text.is_empty() || empty_action_notice(text) { continue; }
        // A named metadata field is required. Never infer a deadline from an
        // arbitrary date in the task sentence, or resolve "Friday" by guessing.
        let due = ["due:", "due：", "截止日期：", "截止日期:", "截止：", "截止:"]
            .iter().find_map(|label| {
                let start = text.to_ascii_lowercase().find(label)? + label.len();
                let value = text[start..].split([',', '，', ')', '）', ';', '；', '|']).next()?.trim();
                if value.is_empty() { None } else { Some(value.to_string()) }
            });
        actions.push(Action { text: text.into(), completed, due });
    }
    actions
}

// Same literal fold as UI commonActionSupplement; no interpretation, removal
// of conditions or changes to independently exported calendar tasks.
struct CommonSupplement { text:String, display_texts:Vec<String> }
fn common_supplement(actions: &[Action]) -> Option<CommonSupplement> {
    if actions.len()<2 {return None;}
    let text=&actions.first()?.text;
    let start=text.rfind("（补充：")?;
    if start==0 || !text.ends_with('）') {return None;}
    let suffix=&text[start..];
    let words=suffix.strip_prefix("（补充：")?.strip_suffix('）')?;
    if words.trim().is_empty() || words.contains(['\r','\n']) {return None;}
    if actions.iter().all(|item|item.text.ends_with(suffix) && item.text.len()>suffix.len()) {
        return Some(CommonSupplement{text:words.into(),display_texts:actions.iter().map(|item|item.text[..item.text.len()-suffix.len()].into()).collect()});
    }
    // Same conservative whole-clause fold as UI. Unknown/quoted/nested
    // wrappers remain intact; saved actions/calendar identities do not change.
    let parts:Option<Vec<(&str,Vec<&str>)>>=actions.iter().map(|item|{
        let start=item.text.find("（补充：")?;
        if start==0 || !item.text.ends_with('）') || item.text[start+"（补充：".len()..].contains("（补充："){return None;}
        let context=&item.text[start+"（补充：".len()..item.text.len()-'）'.len_utf8()];
        if context.contains(['\r','\n','（','）','(',')','“','”','‘','’','「','」','『','』','"','\'']){return None;}
        let clauses:Vec<_>=context.split('；').collect();
        if clauses.iter().any(|part|part.trim().is_empty()){return None;}
        Some((&item.text[..start],clauses))
    }).collect();
    let parts=parts?;
    if parts.iter().any(|(_,clauses)|clauses.iter().collect::<std::collections::HashSet<_>>().len()!=clauses.len()){return None;}
    let common=parts[0].1.iter().copied().filter(|clause|parts.iter().all(|(_,clauses)|clauses.contains(clause))).collect::<Vec<_>>();
    if common.is_empty(){return None;}
    let shared_set=common.iter().copied().collect::<std::collections::HashSet<_>>();
    if parts.iter().any(|(_,clauses)|clauses.iter().copied().filter(|clause|shared_set.contains(clause)).collect::<Vec<_>>()!=common){return None;}
    let shared=common.join("；");
    let display_texts=parts.iter().map(|(title,clauses)|{
        let remaining=clauses.iter().copied().filter(|clause|!shared_set.contains(clause)).collect::<Vec<_>>().join("；");
        if remaining.is_empty(){(*title).into()}else{format!("{title}（补充：{remaining}）")}
    }).collect();
    Some(CommonSupplement{text:shared,display_texts})
}

pub fn todo(title: &str, actions: &[Action], draft: bool) -> String {
    let mut out = format!("# {} — 待办事项\n\n", title.replace(['\r', '\n'], " "));
    if draft { out.push_str("> 草稿：请核对负责人、任务和截止日期。\n\n"); }
    let common=common_supplement(actions);
    if let Some(shared)=&common {
        let words=&shared.text;
        if words.starts_with("共同适用规则："){out.push_str(&format!("> {words}\n\n"));}
        else{out.push_str(&format!("> 以下事项的共同补充：{words}\n\n"));}
    }
    let mut has_supplements=false;
    for (index,item) in actions.iter().enumerate() {
        let text=common.as_ref().map_or(item.text.as_str(),|shared|shared.display_texts[index].as_str());
        let supplement=text.strip_prefix("用户补充：");
        has_supplements|=supplement.is_some();
        out.push_str(&format!("- [{}] {}{}\n",if item.completed {"x"}else{" "},
            supplement.unwrap_or(text),if supplement.is_some(){" ＊"}else{""}));
    }
    if has_supplements {out.push_str("\n> ＊ 来自用户补充；原话与补充仍分别保留。\n");}
    out
}

fn due_property(value: &str) -> Option<String> {
    if value.len() == 10 && value.as_bytes().get(4) == Some(&b'-') && value.as_bytes().get(7) == Some(&b'-') {
        let date = NaiveDate::parse_from_str(value, "%Y-%m-%d").ok()?;
        return Some(format!("DUE;VALUE=DATE:{}\r\n", date.format("%Y%m%d")));
    }
    // A time requires an explicit timezone, otherwise preserve the original text.
    let timestamp = DateTime::parse_from_rfc3339(value).ok()?;
    Some(format!("DUE:{}\r\n", timestamp.with_timezone(&Utc).format("%Y%m%dT%H%M%SZ")))
}

/// The actual native calendar parser is authoritative for this notice.
pub(crate) fn calendar_time_notice(actions: &[Action]) -> Option<String> {
    let count=actions.iter().filter(|action| action.due.as_deref().is_some_and(|value|due_property(value).is_none())).count();
    (count>0).then(||format!("有{count}项时间只保留为文字，没有日历截止时间。请在编辑清单中确认日历时间后重新导出；其它内容已保留。"))
}

pub(crate) fn property(name: &str, value: &str) -> String {
    let escaped = value.replace('\\', "\\\\").replace(';', "\\;").replace(',', "\\,")
        .replace("\r\n", "\n").replace('\r', "\n").replace('\n', "\\n")
        .chars().filter(|c| !c.is_control() || *c == '\t').collect::<String>();
    let line = format!("{name}:{escaped}");
    let mut out = String::new(); let mut used = 0;
    for c in line.chars() {
        if used + c.len_utf8() > 75 { out.push_str("\r\n "); used = 1; }
        out.push(c); used += c.len_utf8();
    }
    out.push_str("\r\n"); out
}

pub fn calendar(session_id: &str, mode: &str, title: &str, actions: &[Action], draft: bool, stamp: &str) -> String {
    let mut out = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Companion Type//Action Items//ZH\r\nCALSCALE:GREGORIAN\r\n".to_string();
    for (index, item) in actions.iter().enumerate() {
        // Include mode and text so unrelated sessions/tasks cannot collide.
        let mut hash = Sha256::new();
        for field in [session_id, mode, &index.to_string(), &item.text] { hash.update(field.as_bytes()); hash.update([0]); }
        let id = format!("{:x}", hash.finalize());
        out.push_str("BEGIN:VTODO\r\n");
        out.push_str(&property("UID", &format!("{}@companion-type", &id[..40])));
        out.push_str(&property("DTSTAMP", stamp));
        out.push_str(&property("SUMMARY", &item.text));
        let description = format!("会议：{title}\n模式：{mode}{}\n原始任务：{}", if draft { "\n草稿：请先核对" } else { "" }, item.text);
        out.push_str(&property("DESCRIPTION", &description));
        if let Some(due) = item.due.as_deref().and_then(due_property) { out.push_str(&due); }
        out.push_str(if item.completed { "STATUS:COMPLETED\r\n" } else { "STATUS:NEEDS-ACTION\r\n" });
        out.push_str("END:VTODO\r\n");
    }
    out.push_str("END:VCALENDAR\r\n"); out
}

pub fn stamp_now() -> String { Utc::now().format("%Y%m%dT%H%M%SZ").to_string() }

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn saved_actions_ignore_decisions_code_and_empty_placeholders() {
        let actions = parse_saved_actions("## 决定\n- 发版\n## 行动项\n- [ ] 核对 (due: 周五)\n- [x] 完成测试\n```\n- 假任务\n```\n## 问题\n- 待解决");
        assert_eq!(actions.len(), 2); assert_eq!(actions[0].due.as_deref(), Some("周五")); assert!(actions[1].completed);
        assert!(parse_saved_actions("## Action Items\n- None captured").is_empty());
    }
    #[test]
    fn calendar_validates_dates_folds_utf8_and_does_not_inject_properties() {
        assert_eq!(due_property("2028-02-29").unwrap(), "DUE;VALUE=DATE:20280229\r\n");
        for invalid in ["周五", "2026-02-29", "2026-10-04T12:00:00", "2026-10-04\r\nBEGIN:VEVENT"] { assert!(due_property(invalid).is_none()); }
        assert_eq!(due_property("2026-10-04T12:00:00+08:00").unwrap(), "DUE:20261004T040000Z\r\n");
        let tasks = vec![Action { text: format!("{}\r\nBEGIN:VEVENT", "长任务".repeat(40)), completed: false, due: Some("周五".into()) }];
        let result = calendar("会议1", "offlineStore", "Title", &tasks, false, "20261004T010203Z");
        assert!(result.lines().all(|line| line.len() <= 75)); assert!(!result.contains("\r\nBEGIN:VEVENT"));
        assert!(!result.contains("DUE:")); assert!(result.contains("DTSTAMP:20261004T010203Z"));
        assert_ne!(result, calendar("会议1", "onlineLive", "Title", &tasks, false, "20261004T010203Z"));
    }
    #[test]
    fn p612_calendar_notice_uses_native_acceptance_without_guessing_relative_times() {
        let tasks=|due:&str|vec![Action{text:format!("核对 (due: {due})"),completed:false,due:Some(due.into())}];
        for value in ["2026-10-26 15:00", "明天下午三点", "2026-02-29", "2026-10-26T15:00:00"] {
            let items=tasks(value);let notice=calendar_time_notice(&items).unwrap();
            assert!(notice.contains("1项时间只保留为文字"));assert!(!notice.contains(value));
            let ics=calendar("s","offlineStore","备忘",&items,false,"20261026T010000Z");
            assert!(!ics.contains("\r\nDUE"));assert!(ics.contains(value));
        }
        for value in ["2028-02-29","2026-10-26T15:00:00+08:00","2026-10-26T07:00:00Z"] {
            assert!(calendar_time_notice(&tasks(value)).is_none());
        }
        assert!(calendar_time_notice(&[Action{text:"未注明时间".into(),completed:false,due:None}]).is_none());
    }

}
