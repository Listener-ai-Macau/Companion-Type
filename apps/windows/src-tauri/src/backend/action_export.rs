//! Export only action items explicitly present in the selected saved document.
//! RFC 5545: https://www.rfc-editor.org/rfc/rfc5545.html (3.1, 3.6.2, 3.8.2.3).
use chrono::{DateTime, Datelike, NaiveDate, Timelike, Utc};
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

// Presentation only. Saved markdown, provenance, calendar identity and the
// conservative DUE parser remain based on the original values.
fn readable_time(value: &str) -> String {
    if let Some(base)=value.strip_suffix('前') {
        let readable=readable_time(base);
        return if readable!=base {if readable.contains("（UTC"){readable.replacen("（UTC","前（UTC",1)}else{format!("{readable}前")}}else{value.into()};
    }
    static DATE:LazyLock<regex::Regex>=LazyLock::new(||regex::Regex::new(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$").unwrap());
    static STAMP:LazyLock<regex::Regex>=LazyLock::new(||regex::Regex::new(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-5][0-9](?:\.[0-9]+)?(?:[Zz]|[+-][0-9]{2}:[0-9]{2})$").unwrap());
    if value.starts_with("0000"){return value.into()}
    if DATE.is_match(value) {
        if let Ok(date)=NaiveDate::parse_from_str(value,"%Y-%m-%d") {
            return date.format("%Y年%-m月%-d日").to_string();
        }
    }
    if STAMP.is_match(value)&&!value.ends_with("-00:00") {
        if let Ok(time)=DateTime::parse_from_rfc3339(value) {
            if time.nanosecond()<1_000_000_000 {
                let clock=if time.second()==0&&time.nanosecond()==0 {time.format("%H:%M").to_string()}else{time.format("%H:%M:%S%.f").to_string()};
                return format!("{} {clock}（UTC{}）",time.format("%Y年%-m月%-d日"),time.format("%:z"));
            }
        }
    }
    value.into()
}

fn readable_action(text: &str) -> String {
    // Same complete, known suffix contract as UI nativeActionParts. Unknown,
    // duplicate or empty fields stay literal, including all task conditions.
    static SUFFIX:LazyLock<regex::Regex>=LazyLock::new(||regex::Regex::new(r"\s+\(([^()\r\n]+)\)$").unwrap());
    static SEPARATOR:LazyLock<regex::Regex>=LazyLock::new(||regex::Regex::new(r",\s*[A-Za-z_][A-Za-z_ -]*:\s*").unwrap());
    static FIELD:LazyLock<regex::Regex>=LazyLock::new(||regex::Regex::new(r"^(owner|due):\s*(\S[\s\S]*)$").unwrap());
    let Some(suffix)=SUFFIX.captures(text) else{return text.into()};
    let inner=suffix.get(1).unwrap().as_str();
    let mut starts=vec![0];
    starts.extend(SEPARATOR.find_iter(inner).map(|separator|separator.start()+1));
    let mut seen=std::collections::HashSet::new();let mut labels=Vec::new();
    for (index,start) in starts.iter().copied().enumerate() {
        let end=starts.get(index+1).map_or(inner.len(),|next|next-1);
        let Some(field)=FIELD.captures(inner[start..end].trim_start()) else{return text.into()};
        let key=field.get(1).unwrap().as_str();let value=field.get(2).unwrap().as_str();
        if !seen.insert(key){return text.into()}
        labels.push(if key=="due" {format!("{}：{}",if value.ends_with('前')||readable_time(value)!=value{"截止"}else{"注明时间"},readable_time(value))}else{format!("负责人：{value}")});
    }
    format!("{}（{}）",&text[..suffix.get(0).unwrap().start()],labels.join("；"))
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
            readable_action(supplement.unwrap_or(text)),if supplement.is_some(){" ＊"}else{""}));
    }
    if has_supplements {out.push_str("\n> ＊ 来自用户补充；原话与补充仍分别保留。\n");}
    out
}

fn due_property(value: &str) -> Option<String> {
    let value=value.strip_suffix('前').unwrap_or(value);
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
        let readable=readable_action(&item.text);
        out.push_str(&property("SUMMARY", &readable));
        let mode_label=match mode {"offlineStore"=>"先录后整理","onlineLive"=>"在线速记",other=>other};
        let description = format!("记录：{title}\n整理方式：{mode_label}{}\n事项：{readable}", if draft { "\n草稿：请先核对" } else { "" });
        out.push_str(&property("DESCRIPTION", &description));
        if let Some(due) = item.due.as_deref().and_then(due_property) { out.push_str(&due); }
        out.push_str(if item.completed { "STATUS:COMPLETED\r\n" } else { "STATUS:NEEDS-ACTION\r\n" });
        out.push_str("END:VTODO\r\n");
    }
    out.push_str("END:VCALENDAR\r\n"); out
}


// Calendar applications commonly import VEVENT rather than VTODO. Keep the
// original task export intact; create deadline markers only for an unfinished
// action with a confirmed absolute date or timestamp. No relative-date guess,
// invitation, invented duration or automatic account/calendar write.
fn event_start(value: &str) -> Option<String> {
    let value=value.strip_suffix('前').unwrap_or(value);
    if value.len()==10 && value.as_bytes().get(4)==Some(&b'-') && value.as_bytes().get(7)==Some(&b'-') {
        let date=NaiveDate::parse_from_str(value,"%Y-%m-%d").ok()?;
        if !(1..=9999).contains(&date.year()) || date.format("%Y-%m-%d").to_string()!=value {return None;}
        return Some(format!("DTSTART;VALUE=DATE:{}\r\n",date.format("%Y%m%d")));
    }
    static STAMP:LazyLock<regex::Regex>=LazyLock::new(||regex::Regex::new(
        r"^[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-5][0-9](?:\.[0-9]+)?(?:[Zz]|[+-][0-9]{2}:[0-9]{2})$"
    ).unwrap());
    if !STAMP.is_match(value) || value.ends_with("-00:00") {return None;}
    let time=DateTime::parse_from_rfc3339(value).ok()?;
    let utc=time.with_timezone(&Utc);
    // iCalendar has whole-second precision. Do not silently round an authored
    // fractional instant, accept a leap-second normalization or year zero.
    if time.nanosecond()!=0 || !(1..=9999).contains(&time.year()) || !(1..=9999).contains(&utc.year()) {return None;}
    Some(format!("DTSTART:{}\r\n",utc.format("%Y%m%dT%H%M%SZ")))
}

pub(crate) fn calendar_event_notice(actions:&[Action])->Option<String> {
    let completed=actions.iter().filter(|a|a.completed).count();
    let ready=actions.iter().filter(|a|!a.completed && a.due.as_deref().and_then(event_start).is_some()).count();
    let missing=actions.len()-ready-completed;
    if missing==0 && completed==0 {return None;}
    let mut excluded=Vec::new();
    if missing>0 {excluded.push(format!("{missing}项尚无明确的日历时间"));}
    if completed>0 {excluded.push(format!("{completed}项已完成"));}
    Some(format!("可导出{ready}项日历日程。{}，仍保留在清单中，不包含在本次日历文件。",excluded.join("，")))
}

pub fn calendar_events(session_id:&str,mode:&str,title:&str,actions:&[Action],draft:bool,stamp:&str)->Result<String,String> {
    calendar_events_with_reminder(session_id,mode,title,actions,draft,stamp,false)
}

pub(crate) fn calendar_event_reminder_notice(actions:&[Action])->Option<String> {
    let mut notes=Vec::new();
    if let Some(base)=calendar_event_notice(actions){notes.push(base);}
    let days=actions.iter().filter(|a|!a.completed && a.due.as_deref().and_then(event_start).is_some_and(|s|s.starts_with("DTSTART;VALUE=DATE:"))).count();
    if days>0{notes.push(format!("{days}项只有日期，会保留为全天日程，不添加提醒；确认具体时刻后才能提醒。"));}
    if notes.is_empty(){None}else{Some(notes.join(" "))}
}

/// Explicit DISPLAY alarm only. No date-only midnight, guessed duration,
/// recipient/invitation, online calendar mutation or automatic synchronization.
pub fn calendar_events_with_reminder(session_id:&str,mode:&str,title:&str,actions:&[Action],draft:bool,stamp:&str,remind_at_time:bool)->Result<String,String> {
    calendar_events_with_reminder_lead(session_id,mode,title,actions,draft,stamp,if remind_at_time{Some(0)}else{None})
}

fn calendar_event_uid(session_id:&str,mode:&str,index:usize,text:&str)->String {
    let mut hash=Sha256::new();
    for field in ["calendar-deadline-event",session_id,mode,&index.to_string(),text] {hash.update(field.as_bytes());hash.update([0]);}
    format!("{}@companion-type",&format!("{:x}",hash.finalize())[..40])
}

pub(crate) fn calendar_copy_entries(session_id:&str,mode:&str,actions:&[Action],lead:Option<u16>)->Vec<super::calendar_copy::Entry> {
    actions.iter().enumerate().filter_map(|(index,item)|{
        if item.completed{return None;}
        let start=item.due.as_deref().and_then(event_start)?;
        Some(super::calendar_copy::Entry{uid:calendar_event_uid(session_id,mode,index,&item.text),
            title:readable_action(&item.text),deadline:item.due.clone()?,
            reminder_minutes:lead.filter(|_|start.starts_with("DTSTART:"))})
    }).collect()
}

pub(crate) fn calendar_events_with_reminder_lead(session_id:&str,mode:&str,title:&str,actions:&[Action],draft:bool,stamp:&str,lead_minutes:Option<u16>)->Result<String,String> {
    if lead_minutes.is_some_and(|m|!matches!(m,0|30|60)){return Err("不支持的提前提醒时间；请重新选择，截止时间保持不变。".into());}
    let mut out="BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Companion Type//Checklist Calendar Events//ZH\r\nCALSCALE:GREGORIAN\r\n".to_string();
    let mut count=0;
    let mut reminder_count=0;
    for(index,item)in actions.iter().enumerate() {
        if item.completed {continue;}
        let Some(start)=item.due.as_deref().and_then(event_start)else{continue;};
        let id=calendar_event_uid(session_id,mode,index,&item.text);
        let readable=readable_action(&item.text);
        let mode_label=match mode {"offlineStore"=>"先录后整理","onlineLive"=>"在线速记",other=>other};
        out.push_str("BEGIN:VEVENT\r\n");
        out.push_str(&property("UID",&id));
        out.push_str(&property("DTSTAMP",stamp));out.push_str(&start);
        out.push_str(&property("SUMMARY",&readable));
        out.push_str(&property("DESCRIPTION",&format!("记录：{title}\n整理方式：{mode_label}{}\n事项：{readable}\n清单时间点；导入后请核对日期、时区和提醒。",if draft{"\n草稿：请先核对"}else{""})));
        // RFC5545: a date without DTEND is one day; a timed event without
        // DTEND ends at DTSTART. A deadline does not reserve invented work time.
        out.push_str("CLASS:PRIVATE\r\nTRANSP:TRANSPARENT\r\nSTATUS:CONFIRMED\r\n");
        if let Some(lead)=lead_minutes.filter(|_|start.starts_with("DTSTART:")) {
            out.push_str("BEGIN:VALARM\r\nACTION:DISPLAY\r\n");
            out.push_str(&format!("TRIGGER;RELATED=START:{}\r\n",if lead==0{"PT0S".into()}else{format!("-PT{lead}M")}));
            out.push_str(&property("DESCRIPTION",&format!("清单提醒：{readable}")));
            out.push_str("END:VALARM\r\n");reminder_count+=1;
        }
        out.push_str("END:VEVENT\r\n");count+=1;
    }
    if count==0 {
        if actions.iter().all(|item|item.completed) {
            return Err("CALENDAR_NO_PENDING_ACTIONS:清单事项均已完成，没有需要放入日历的未完成事项；原清单保持不变。".into());
        }
        return Err("CALENDAR_TIME_REQUIRED:没有可导出的日历日程。请在编辑清单中确认未完成事项的日期或时刻，再导出；原清单保持不变。".into());
    }
    if lead_minutes.is_some() && reminder_count==0 {
        return Err("CALENDAR_TIME_REQUIRED:提醒需要具体时刻。请确认未完成事项的时刻；只有日期的事项仍可作为全天日程导出，原清单保持不变。".into());
    }
    out.push_str("END:VCALENDAR\r\n");Ok(out)
}

pub fn stamp_now() -> String { Utc::now().format("%Y%m%dT%H%M%SZ").to_string() }

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn calendar_reminder_is_explicit_preserves_conditions_and_never_guesses_midnight() {
        let markdown="## 行动项\n- [ ] 咖啡豆不要深烘，确认灯座后买灯泡 (due: 2026-10-31T09:00:00+08:00)\n- [ ] 只确定星期六 (due: 2026-10-31)\n- [x] 已完成 (due: 2026-10-31T08:00:00+08:00)\n- [ ] 尚待商量 (due: 周末)";
        let actions=parse_saved_actions(markdown);
        let plain=calendar_events("same","offlineStore","采购",&actions,false,"20261028T010000Z").unwrap();
        let alarm=calendar_events_with_reminder("same","offlineStore","采购",&actions,false,"20261028T010000Z",true).unwrap();
        assert!(!plain.contains("VALARM"));
        assert_eq!(alarm.matches("BEGIN:VEVENT").count(),2);
        assert_eq!(alarm.matches("BEGIN:VALARM").count(),1);
        assert!(alarm.contains("DTSTART:20261031T010000Z\r\n"));
        assert!(alarm.contains("DTSTART;VALUE=DATE:20261031\r\n"));
        assert!(alarm.contains("ACTION:DISPLAY\r\nTRIGGER;RELATED=START:PT0S\r\nDESCRIPTION:"));
        assert!(alarm.contains("不要深烘"));assert!(alarm.replace("\r\n ","").contains("确认灯座后买灯泡"));
        assert!(!alarm.contains("ATTENDEE:"));assert!(!alarm.contains("DTEND:"));
        assert!(!alarm.contains("T000000Z"));
        assert!(calendar_event_reminder_notice(&actions).unwrap().contains("1项只有日期"));
        assert_eq!(actions,parse_saved_actions(markdown));
    }

    #[test]
    fn calendar_reminder_requires_confirmed_instant_and_escapes_alarm_description() {
        for due in ["2026-10-31","周末","2026-10-31T09:00:00-00:00","2026-10-31T09:00:00.001Z"] {
            let actions=parse_saved_actions(&format!("## 行动项\n- [ ] 确认后再买 (due: {due})"));
            assert!(calendar_events_with_reminder("id","offlineStore","记录",&actions,false,"20261028T010000Z",true).unwrap_err().starts_with("CALENDAR_TIME_REQUIRED:"));
        }
        let actions=[Action{text:"要保留,条件;以及\nEND:VALARM\nBEGIN:VEVENT".into(),completed:false,due:Some("2026-10-31T09:00:00Z".into())}];
        let value=calendar_events_with_reminder("id","onlineLive","原记录",&actions,true,"20261028T010000Z",true).unwrap();
        assert_eq!(value.lines().filter(|line|*line=="BEGIN:VEVENT").count(),1);
        assert_eq!(value.lines().filter(|line|*line=="END:VALARM").count(),1);
        assert!(value.replace("\r\n ","").contains("\\nEND:VALARM\\nBEGIN:VEVENT"));
    }

    #[test]
    fn p613_readable_exports_preserve_calendar_identity_and_saved_values() {
        let text="核对结果 (owner: 小林, due: 2026-10-26T15:00:00+08:00)";
        let actions=parse_saved_actions(&format!("## 行动项\n- [ ] {text}"));
        let markdown=todo("备忘",&actions,false);
        assert!(markdown.contains("核对结果（负责人：小林；截止：2026年10月26日 15:00（UTC+08:00））"));
        assert!(!markdown.contains("owner:")&&!markdown.contains("due:"));
        let ics=calendar("p613","offlineStore","备忘",&actions,false,"20261026T010000Z");
        let unfolded=ics.replace("\r\n ","");
        assert!(unfolded.contains("UID:2d9e5c77cc6901851e74cda50745d65ae0a256ec@companion-type\r\n"));
        assert!(unfolded.contains("DUE:20261026T070000Z\r\n"));
        assert!(unfolded.contains("整理方式：先录后整理"));
        assert!(!unfolded.contains("offlineStore")&&!unfolded.contains("due:")&&!unfolded.contains("owner:"));
        assert_eq!(actions[0].text,text);assert_eq!(actions[0].due.as_deref(),Some("2026-10-26T15:00:00+08:00"));
        assert!(ics.lines().all(|line|line.len()<=75));
    }
    #[test]
    fn p613_export_reading_never_guesses_or_drops_unknown_task_prose() {
        for text in ["核对 (due: 周五, note: 尚未确认)","核对 (due: 周五, due: 周六)","核对 (due: )","核对 (owner: 小林 (代班), due: 周五)","先讨论 due: 周五 的含义"] {
            assert_eq!(readable_action(text),text);
        }
        assert_eq!(readable_action("周五前核对 (due: 周五)"),"周五前核对（注明时间：周五）");
        assert_eq!(readable_action("核对 (owner: A,B, due: 未定)"),"核对（负责人：A,B；注明时间：未定）");
        for value in ["明天下午3点","2026-02-29","0000-01-01","2026-10-26 15:00","2026-10-26T15:00:00-00:00"] {assert_eq!(readable_time(value),value);}
        assert_eq!(readable_time("2028-02-29"),"2028年2月29日");
        assert_eq!(readable_time("2026-10-26T07:00:12.125Z"),"2026年10月26日 07:00:12.125（UTC+00:00）");
        let tasks=parse_saved_actions("## 行动项\n- [x] 周五前核对 (due: 周五)");
        let ics=calendar("relative","onlineLive","备忘",&tasks,false,"20261026T010000Z").replace("\r\n ","");
        assert!(ics.contains("周五前核对")&&ics.contains("注明时间：周五")&&ics.contains("整理方式：在线速记"));
        assert!(!ics.contains("\r\nDUE"));assert!(ics.contains("STATUS:COMPLETED"));assert!(calendar_time_notice(&tasks).is_some());
    }
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


#[cfg(test)]
mod p636_calendar_events_tests {
    use super::*;
    #[test]
    fn p636_calendar_events_preserve_confirmed_dates_skip_unsupported_and_keep_original_tasks() {
        let saved="## 行动项\n- [ ] 带身份证 (due: 2026-11-05)\n- [ ] 拿票 (due: 2026-11-05T16:30:00+08:00)\n- [ ] 核对安排 (due: 周五)\n- [x] 已完成 (due: 2026-11-04)";
        let actions=parse_saved_actions(saved);let original=actions.clone();
        let body=calendar_events("p636","offlineStore","出差安排",&actions,false,"20261027T010000Z").unwrap();
        assert_eq!(body.matches("BEGIN:VEVENT\r\n").count(),2);
        assert!(body.contains("DTSTART;VALUE=DATE:20261105\r\n"));
        assert!(body.contains("DTSTART:20261105T083000Z\r\n"));
        assert!(body.contains("CLASS:PRIVATE\r\nTRANSP:TRANSPARENT\r\n"));
        assert!(!body.contains("BEGIN:VTODO")&&!body.contains("BEGIN:VALARM")&&!body.contains("DTEND")&&!body.contains("ATTENDEE"));
        assert_eq!(actions,original);
        let notice=calendar_event_notice(&actions).unwrap();assert!(notice.contains("2项日历")&&notice.contains("1项尚无")&&notice.contains("1项已完成"));
        let old=calendar("p636","offlineStore","出差安排",&actions,false,"20261027T010000Z");
        assert_eq!(old.matches("BEGIN:VTODO\r\n").count(),4);assert!(old.contains("周五"));
        let uid=|text:&str|text.lines().find(|line|line.starts_with("UID:")).unwrap().to_owned();
        assert_ne!(uid(&old),uid(&body));
        assert_ne!(body,calendar_events("p636","onlineLive","出差安排",&actions,false,"20261027T010000Z").unwrap());
    }
    #[test]
    fn p636_calendar_events_do_not_guess_or_round_times() {
        for value in ["周五","2026年11月5日16:30","2026-11-05 16:30","0000-01-01","2026-02-29",
            "2026-11-05T16:30:00-00:00","2026-11-05T16:30:60Z","2026-11-05T16:30:00.001Z","0001-01-01T00:00:00+08:00"] {
            let task=Action{text:format!("任务 (due: {value})"),completed:false,due:Some(value.into())};
            assert!(calendar_events("s","offlineStore","t",&[task],false,"20261027T010000Z").is_err(),"{value}");
        }
        for value in ["2026-11-05","2026-11-05T16:30:00+08:00","2026-11-05T16:30:00.000Z"] {
            let task=Action{text:"任务".into(),completed:false,due:Some(value.into())};
            assert!(calendar_events("s","offlineStore","t",&[task],false,"20261027T010000Z").is_ok(),"{value}");
        }
    }
    #[test]
    fn p636_calendar_events_escape_author_content_and_fold_complete_utf8() {
        let task=Action{text:format!("核对资料,不可删除;{}\nBEGIN:VEVENT", "保留条件".repeat(70)),completed:false,due:Some("2026-11-05".into())};
        let body=calendar_events("s","offlineStore","标题\nBEGIN:VALARM",&[task],true,"20261027T010000Z").unwrap();
        assert_eq!(body.lines().filter(|line|*line=="BEGIN:VEVENT").count(),1);assert!(!body.contains("\r\nBEGIN:VALARM"));
        assert!(body.lines().all(|line|line.len()<=75));assert!(body.contains("\\,不可删除\\;"));
        assert!(body.replace("\r\n ","").contains("草稿：请先核对"));
    }
}


#[cfg(test)]
mod p637_calendar_capability_tests {
    use super::*;
    #[test]
    fn p637_calendar_requires_time_is_distinct_from_completed_and_file_io() {
        let pending=Action{text:"先确认再买".into(),completed:false,due:Some("本周六上午出门前".into())};
        let error=calendar_events("s","offlineStore","采购",&[pending.clone()],false,"20261027T010000Z").unwrap_err();
        assert!(error.starts_with("CALENDAR_TIME_REQUIRED:"));assert!(error.contains("原清单保持不变"));
        let mut done=pending.clone();done.completed=true;
        let completed=calendar_events("s","offlineStore","采购",&[done],false,"20261027T010000Z").unwrap_err();
        assert!(completed.starts_with("CALENDAR_NO_PENDING_ACTIONS:"));assert!(!completed.starts_with("CALENDAR_TIME_REQUIRED:"));
        assert_eq!(pending.due.as_deref(),Some("本周六上午出门前"));
        let mut confirmed=pending;confirmed.due=Some("2026-10-31T09:00:00+08:00".into());
        let body=calendar_events("s","offlineStore","采购",&[confirmed],false,"20261027T010000Z").unwrap();
        assert!(body.contains("DTSTART:20261031T010000Z"));
    }
    #[test]
    fn calendar_deadline_leads_preserve_the_deadline_and_all_conditions() {
        let raw="## 行动项\n- [ ] 把样品结果发给小林；未测完不要写通过 (due: 2026-11-06T15:00:00+08:00前)\n- [ ] 只有日期 (due: 2026-11-07)";
        let actions=parse_saved_actions(raw);let original=actions.clone();
        let text=todo("样品",&actions,false);
        assert!(text.contains("截止：2026年11月6日 15:00前（UTC+08:00）"));
        for(lead,trigger)in[(0,"PT0S"),(30,"-PT30M"),(60,"-PT60M")] {
            let value=calendar_events_with_reminder_lead("sample","offlineStore","样品",&actions,false,"20261028T010000Z",Some(lead)).unwrap();
            assert!(value.contains("DTSTART:20261106T070000Z\r\n"));
            assert!(value.contains(&format!("TRIGGER;RELATED=START:{trigger}\r\n")));
            assert_eq!(value.matches("BEGIN:VALARM").count(),1,"date-only never guesses midnight");
            assert!(value.contains("未测完不要写通过")&&value.contains("15:00前"));
        }
        assert_eq!(actions,original);
        assert!(calendar_events_with_reminder_lead("s","offlineStore","样品",&actions,false,"20261028T010000Z",Some(15)).is_err());
        let plain=calendar_events("s","offlineStore","样品",&actions,false,"20261028T010000Z").unwrap();
        assert!(!plain.contains("VALARM"));
        let legacy=calendar("s","offlineStore","样品",&actions,false,"20261028T010000Z");
        assert!(legacy.contains("DUE:20261106T070000Z"));
        assert!(event_start("2026年11月6日15:00前").is_none(),"unconfirmed prose is not silently converted");
    }

}
