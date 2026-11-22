//! Preserve the scope of spoken judgments and assignments in the published document.
use serde_json::Value;

use super::{commitments, factual_audit, line, Action, Document, Kind, Unit, SOURCE_ITEMS_FACT_LIMIT};

pub(super) struct ReportedCondition {
    text: String,
    sources: Vec<String>,
    speaker: String,
}

pub(super) fn conditional_speakers(brief: &factual_audit::VerifiedBrief, units: &[Unit]) -> Vec<ReportedCondition> {
    let turns = commitments::with_turn_labels(&factual_audit::evidence_sentences(units));
    let mut reported = Vec::new();
    for (i, topic) in brief.document.topics.iter().enumerate() {
        for (j, point) in topic.points.iter().enumerate() {
            if !matches!(point.kind, Kind::Status | Kind::Opinion)
                || !["如果", "假如", "倘若"].iter().any(|cue| point.text.starts_with(cue))
            {
                continue;
            }
            let Some([id]) = brief.evidence.get(&format!("topics[{i}].points[{j}]")).map(Vec::as_slice) else { continue };
            let Some(turn) = turns.iter().find(|row| row["id"] == id.as_str()
                && point.sources.iter().any(|unit| row["source"] == unit.as_str()))
            else { continue };
            let Some(speaker) = turn["turnSpeaker"].as_str() else { continue };
            reported.push(ReportedCondition {text:point.text.clone(),sources:point.sources.clone(),speaker:speaker.to_owned()});
        }
    }
    reported
}

pub(super) struct UnresolvedTiming {
    action: String,
    sources: Vec<String>,
    phrase: String,
    quote: String,
}

fn timing_phrase(text: &str) -> Option<(&str, &str)> {
    static TIMING: std::sync::LazyLock<regex::Regex> = std::sync::LazyLock::new(|| {
        regex::Regex::new(r"^(?P<object>[\p{Han}]{2,18}?)(?P<event>出品|出来|到位|到货|发货|交付|上线|完工|发布)(?:的)?时间$")
            .expect("timing field pattern")
    });
    let featured = |text: &str| TIMING.is_match(text);
    let mut matches = text.split(['、','，','。','；','：',',',';']).map(str::trim).filter(|part| featured(part));
    let phrase = matches.next()?;
    if matches.next().is_some() { return None; }
    let event = TIMING.captures(phrase)?.name("event")?.as_str();
    Some((phrase, event))
}

fn opaque_timing(source: &str) -> impl Iterator<Item = (&str, &str)> {
    static OPAQUE: std::sync::LazyLock<regex::Regex> = std::sync::LazyLock::new(|| {
        regex::Regex::new(r"(?P<quote>(?:咱们的|我们的|他们的|这批|那批|这件|那件|这个|那个|那些)?东西(?P<event>出来|到位|到货|发货|交付|上线|完工|发布)(?:的)?时间)")
            .expect("opaque timing pattern")
    });
    OPAQUE.captures_iter(source).map(|capture| {
        (capture.name("quote").unwrap().as_str(), capture.name("event").unwrap().as_str())
    })
}

fn same_event(first: &str, second: &str) -> bool {
    first == second || ["出品", "出来"].contains(&first) && ["出品", "出来"].contains(&second)
}

fn anchored_opaque_time(action: &str, turns: &[&str]) -> Option<(String, String)> {
    let (phrase, event) = timing_phrase(action)?;
    let field = phrase.replace("的时间", "时间");
    if turns.iter().any(|text| text.replace("的时间", "时间").contains(&field)) {
        return None;
    }
    let mut opaque = turns.iter().flat_map(|text| opaque_timing(text))
        .filter(|(_, candidate)| same_event(event, candidate)).map(|(quote, _)| quote);
    let quote = opaque.next()?;
    if !opaque.all(|other| other == quote) { return None; }
    Some((phrase.to_owned(), quote.to_owned()))
}

pub(super) fn unresolved_timings(brief: &factual_audit::VerifiedBrief, units: &[Unit]) -> Vec<UnresolvedTiming> {
    let turns = factual_audit::evidence_sentences(units);
    brief.document.action_items.iter().enumerate().filter_map(|(index, action)| {
        let ids = brief.evidence.get(&format!("actionItems[{index}]"))?;
        let mut evidence = Vec::new();
        for row in turns.iter().filter(|row| ids.iter().any(|id| row["id"] == id.as_str())
            && action.sources.iter().any(|unit| row["source"] == unit.as_str()))
        {
            evidence.push(content(row));
        }
        let (phrase, quote) = anchored_opaque_time(&action.text, &evidence)?;
        Some(UnresolvedTiming {action:action.text.clone(),sources:action.sources.clone(),phrase,quote})
    }).collect()
}

// The draft may be the only result when the next request times out.
pub(super) fn retain_source_timing(text: &str, turns: &[&str]) -> Option<String> {
    let (phrase, quote) = anchored_opaque_time(text, turns)?;
    let revised = text.replacen(&phrase, &format!("「{quote}」（具体对象待核实）"), 1);
    line(&revised, 90).then_some(revised)
}

fn same_timing_list(before: &str, after: &str, field: &str) -> bool {
    fn rest(text: &str, field: &str) -> Option<(String, String)> {
        let (prefix, suffix) = text.split_once(field)?;
        let suffix = suffix.trim_start_matches(['，', ',', '、', ' ']);
        let suffix = ["以及", "及"].iter().find_map(|join| suffix.strip_prefix(join)).unwrap_or(suffix);
        Some((super::normalized(prefix), super::normalized(suffix)))
    }
    rest(before, field).is_some_and(|left| rest(after, field).as_ref() == Some(&left))
}

pub(super) fn preserve_unresolved_timings(doc: &mut Document, unresolved: &[UnresolvedTiming]) -> usize {
    let mut retained = 0;
    for action in &mut doc.action_items {
        let Some(entry) = unresolved.iter().find(|item| action.sources == item.sources
            && (action.text == item.action || same_timing_list(&item.action, &action.text, &item.phrase)))
        else { continue; };
        let body = action.text.replacen(&entry.phrase, &format!("「{}」（具体对象待核实）", entry.quote), 1);
        let body = if body.starts_with("待核对：") { body } else { format!("待核对：{body}") };
        if line(&body, 180) {
            action.text = body;
            retained += 1;
        }
    }
    retained
}

fn content(turn: &Value) -> &str {
    let text = turn["text"].as_str().unwrap_or("");
    super::super::source_resolution::split_turn_label(text).map_or(text, |(_, speech)| speech)
}

fn retrospective_report<'a>(action: &Action, reviewed: &[String], turns: &'a [Value]) -> Option<Vec<&'a str>> {
    const PERIODS: &[&str] = &["上周", "上个月", "上月", "上一季度", "上季度", "上半年", "上年度", "去年"];
    const DEFERRED: &[&str] = &["会后", "散会后", "结束后", "回去后", "下次", "下周", "明天", "截止",
        "提交", "发给", "交付", "书面", "整理", "材料", "另行", "如果", "假如", "例如", "比如"];
    let future_or_conditional = |text: &str| DEFERRED.iter().any(|cue| text.contains(cue));
    if action.due.is_some() || !action.text.contains("汇报") || future_or_conditional(&action.text) {
        return None;
    }
    let cited: Vec<_> = turns.iter().enumerate().filter(|(_, line)| {
        reviewed.iter().any(|id| line["id"] == id.as_str())
            && action.sources.iter().any(|unit| line["source"] == unit.as_str())
    }).collect();
    if cited.len() != reviewed.len() || cited.iter().any(|(_, line)| future_or_conditional(content(line))) {
        return None;
    }
    let period = *PERIODS.iter().find(|&&period| action.text.contains(period))?;
    let (_, scope) = cited.iter().find(|(_, line)| {
        let spoken = content(line);
        spoken.contains(period) && spoken.contains("汇报")
    })?;
    let (_, request) = cited.iter().find(|(index, line)| {
        let words = content(line);
        if !words.contains("汇报一下") { return false; }
        if ["在会上", "会上请", "当场", "现在就", "已经汇报", "第一就是", "第二就是", "第三就是"]
            .iter().any(|cue| words.contains(cue))
        {
            return true;
        }
        let handoff = turns[index.saturating_sub(2)..*index].iter().any(|line| {
            let spoken = content(line);
            !future_or_conditional(spoken) && ["下面", "接下来"].iter().any(|cue| spoken.contains(cue))
                && ["请", "问", "听"].iter().any(|cue| spoken.contains(cue))
        });
        handoff && cited.iter().any(|(after, response)| {
            *after > *index && *after - *index <= 2 && ["我们", "我来", "我先"].iter().any(|cue|
                content(response).trim_start().starts_with(cue))
        })
    })?;
    let scope = content(scope).trim();
    let request = content(request).trim();
    Some(if scope == request { vec![request] } else { vec![scope, request] })
}

/// Exact evidence of an in-meeting report can support its content without assigning a future task.
pub(super) fn take_live_report_quotes(brief: &mut factual_audit::VerifiedBrief, units: &[Unit]) -> Vec<String> {
    if brief.document.action_items.is_empty() { return Vec::new(); }
    let turns = factual_audit::evidence_sentences(units);
    let mut quotes = Vec::new();
    brief.document.action_items = std::mem::take(&mut brief.document.action_items)
        .into_iter().enumerate().filter_map(|(index, action)| {
            let source = brief.evidence.get(&format!("actionItems[{index}]"))
                .and_then(|ids| retrospective_report(&action, ids, &turns));
            if let Some(source) = source {
                for quote in source {
                    let quote = quote.to_owned();
                    if !quotes.contains(&quote) { quotes.push(quote); }
                }
                None
            } else {
                Some(action)
            }
        }).collect();
    quotes
}

#[cfg(test)]
#[test]
fn distinguishes_a_live_handoff_from_an_actual_future_report() {
    let action = Action {text:"汇报上月的交接情况。".into(),owner:Some("调度组".into()),due:None,
        sources:vec!["u000".into()]};
    let source = vec![
        serde_json::json!({"id":"e0","source":"u000","text":"下面请调度组。"}),
        serde_json::json!({"id":"e1","source":"u000","text":"把上月的交接情况汇报一下吧。"}),
        serde_json::json!({"id":"e2","source":"u000","text":"我们上月做了两次交接。"}),
        serde_json::json!({"id":"e3","source":"u000","text":"会后再向负责人汇报上月的交接情况。"}),
    ];
    let live = ["e1".into(), "e2".into()];
    assert_eq!(retrospective_report(&action, &live, &source), Some(vec!["把上月的交接情况汇报一下吧。"]));
    assert!(retrospective_report(&action, &["e1".into(), "e2".into(), "e3".into()], &source).is_none());
    assert!(retrospective_report(&action, &["e1".into()], &source).is_none());
    let with_deadline = Action { due: Some("周五前".into()), ..action };
    assert!(retrospective_report(&with_deadline, &live, &source).is_none());
}

fn bound_scope(action: &Action, turns: &[Value]) -> Option<[Action; 2]> {
    let owner = action.owner.as_deref()?;
    let (joint, rest) = action.text.split_once(['，', '；', ',', ';'])?;
    let personal = rest.trim().strip_prefix('由')?.strip_prefix(owner)?.trim();
    let joint_key: String = joint.chars().take(5).collect();
    let verb: String = personal.chars().take(2).collect();
    if action.due.is_some() || !joint.starts_with('把') || joint_key.chars().count() < 5
        || verb.chars().count() != 2 || !line(personal, 176) || rest.matches(owner).count() != 1
        || personal.contains(['，', '；', ',', ';'])
    {
        return None;
    }
    let request = [format!("你来{verb}"), format!("你负责{verb}"), format!("请你{verb}")];
    let cited = |row: &Value| action.sources.iter().any(|id| row["source"] == id.as_str());
    let witnesses = turns.windows(2).enumerate().find_map(|(index, adjacent)| {
        let [speaking, acknowledgement] = adjacent else { return None };
        let ask = content(speaking);
        let assent = content(acknowledgement).trim().trim_end_matches(['。', '！', '，', '、']).trim();
        let directing = speaking["turnSpeaker"].as_str()?;
        if directing == owner || acknowledgement["turnSpeaker"] != owner
            || !matches!(assent, "行" | "好" | "好的" | "可以" | "嗯好")
            || !cited(speaking) || !cited(acknowledgement) || !request.iter().any(|form| ask.contains(form))
        {
            return None;
        }
        let mention = turns[index.saturating_sub(3)..index].iter().rev().find(|row| {
            let spoken = content(row);
            let Some((before, _)) = spoken.split_once(&joint_key) else { return false };
            cited(row) && row["turnSpeaker"] == directing
                && ["我们", "咱们", "大家", "共同"].iter().any(|group| before.contains(group))
                && !["不用", "不要", "先不", "取消", "暂停"].iter().any(|stop| before.contains(stop))
        })?;
        Some([mention, speaking, acknowledgement])
    })?;
    let [joint_quote, directed_quote, confirmation] = witnesses;
    let source = |row: &Value| row["source"].as_str().unwrap().to_owned();
    let mut personal_sources = vec![source(directed_quote)];
    let accepted_unit = source(confirmation);
    if personal_sources[0] != accepted_unit { personal_sources.push(accepted_unit); }
    Some([
        Action{text:format!("{}。",joint.trim_end_matches('。')),owner:None,due:None,sources:vec![source(joint_quote)]},
        Action{text:personal.to_owned(),owner:Some(owner.to_owned()),due:None,sources:personal_sources},
    ])
}

pub(super) fn apply(doc: &mut Document, units: &[Unit], reported: Vec<ReportedCondition>) -> (usize, usize) {
    let mut attributed = 0;
    for point in doc.topics.iter_mut().flat_map(|topic| &mut topic.points) {
        if !matches!(point.kind, Kind::Status | Kind::Opinion) { continue; }
        if let Some(claim) = reported.iter().find(|claim| claim.text == point.text && claim.sources == point.sources) {
            let text = format!("{}：{}", claim.speaker, point.text);
            if line(&text, 90) {
                point.text = text;
                point.kind = Kind::Opinion;
                attributed += 1;
            }
        }
    }
    let total_facts = doc.topics.iter().map(|topic| topic.points.len()+topic.details.len()).sum::<usize>()
        + doc.action_items.len() + doc.decisions.len() + doc.questions.len();
    let mut room = SOURCE_ITEMS_FACT_LIMIT.saturating_sub(total_facts);
    if room == 0 { return (attributed, 0); }
    let turns = commitments::with_turn_labels(&factual_audit::evidence_sentences(units));
    let mut split = 0;
    let original = doc.action_items.clone();
    doc.action_items = std::mem::take(&mut doc.action_items).into_iter().flat_map(|action| {
        if room > 0 {
            if let Some(scoped) = bound_scope(&action, &turns) {
                if !scoped.iter().any(|row| original.iter().any(|existing| row.text == existing.text)) {
                    room -= 1;
                    split += 1;
                    return Vec::from(scoped);
                }
            }
        }
        vec![action]
    }).collect();
    (attributed, split)
}

#[cfg(test)]
#[test]
fn bound_timing_keeps_exact_unresolved_words_and_other_task_fields() {
    let action = Action{text:"列出折扣、设备交付时间、出厂参数。".into(), owner:Some("采购组".into()),
        due:Some("周五之前".into()), sources:vec!["u002".into()]};
    let evidence = ["同时写折扣，再看这批东西交付的时间。"];
    let (phrase, quote) = anchored_opaque_time(&action.text, &evidence).unwrap();
    assert_eq!(phrase, "设备交付时间");
    assert_eq!(quote, "这批东西交付的时间");
    assert!(anchored_opaque_time(&action.text, &[evidence[0], "就是设备交付的时间。"]).is_none());
    assert!(anchored_opaque_time(&action.text, &["等待这批东西上线的时间。"]).is_none());
    let mut doc = Document{purpose:"讨论交付安排。".into(),topics:Vec::new(),decisions:Vec::new(),
        action_items:vec![action.clone()],questions:Vec::new()};
    let retained = preserve_unresolved_timings(&mut doc, &[UnresolvedTiming{
        action:action.text.clone(),sources:action.sources.clone(),phrase,quote}]);
    assert_eq!(retained, 1);
    assert_eq!(doc.action_items[0].text,"待核对：列出折扣、「这批东西交付的时间」（具体对象待核实）、出厂参数。");
    assert_eq!(doc.action_items[0].owner, action.owner);
    assert_eq!(doc.action_items[0].due, action.due);
}

#[cfg(test)]
#[test]
fn same_source_timing_survives_a_list_punctuation_change() {
    let earlier = "在方案中列出最低折扣、产品出品时间，以及各平台促销力度或可达效益。";
    let revised = "在方案中列出最低折扣、产品出品时间及各平台促销力度或可达效益。";
    let evidence = UnresolvedTiming{action:earlier.into(),sources:vec!["u014".into()],
        phrase:"产品出品时间".into(),quote:"咱们的东西出来的时间".into()};
    let mut doc = Document{purpose:"讨论交付安排。".into(),topics:Vec::new(),decisions:Vec::new(),questions:Vec::new(),
        action_items:vec![
            Action{text:revised.into(),owner:None,due:None,sources:vec!["u014".into()]},
            Action{text:revised.into(),owner:None,due:None,sources:vec!["u015".into()]},
            Action{text:revised.replace("最低","最高"),owner:None,due:None,sources:vec!["u014".into()]},
        ]};
    assert_eq!(preserve_unresolved_timings(&mut doc,&[evidence]),1);
    assert!(doc.action_items[0].text.contains("「咱们的东西出来的时间」（具体对象待核实）"));
    assert!(doc.action_items[1..].iter().all(|action| action.text.contains("产品出品时间")));
}

#[cfg(test)]
#[test]
fn splits_accepted_personal_step_from_the_cited_collective_task() {
    let text = concat!("说话人1：咱们把设备清点过来，然后开个会。\n",
                       "说话人1：接下来你来主持一下下次。\n",
                       "说话人2：行。\n");
    let units = vec![Unit{id:"u001".into(),text:text.into()}];
    let turns = commitments::with_turn_labels(&factual_audit::evidence_sentences(&units));
    let task = Action{text:"把设备清点好再开会，由说话人2主持下次会议。".into(),
        owner:Some("说话人2".into()),due:None,sources:vec!["u001".into()]};
    let [joint, personal] = bound_scope(&task, &turns).unwrap();
    assert!(joint.owner.is_none() && joint.text.contains("把设备清点"));
    assert_eq!(personal.owner.as_deref(), Some("说话人2"));
    assert_eq!(personal.text, "主持下次会议。");
    assert!(bound_scope(&task, &turns[..2]).is_none());
    let mut dated = task;
    dated.due = Some("周三".into());
    assert!(bound_scope(&dated, &turns).is_none());
}

#[cfg(test)]
#[test]
fn retains_the_speaker_for_an_opinion_on_the_same_turn() {
    use serde_json::json;
    let units = vec![Unit{id:"u000".into(),text:"说话人2：这是我的看法。如果货架太低，就不适合存放这些货。\n".into()}];
    let doc: Document = serde_json::from_value(json!({
        "purpose":"讨论货架",
        "topics":[{"title":"货架高度","points":[{"kind":"opinion","text":"如果货架太低，就不适合存放这些货。","sources":["u000"]}]}],
        "actionItems":[],"decisions":[],"questions":[]
    })).unwrap();
    let brief = factual_audit::VerifiedBrief{document:doc.clone(),
        evidence:std::collections::HashMap::from([("topics[0].points[0]".into(),vec!["e0001".into()])]),
        pending_quotes:Vec::new()};
    let mut published = doc;
    let speakers = conditional_speakers(&brief, &units);
    assert_eq!(apply(&mut published, &units, speakers), (1,0));
    assert_eq!(published.topics[0].points[0].text, "说话人2：如果货架太低，就不适合存放这些货。");
}
