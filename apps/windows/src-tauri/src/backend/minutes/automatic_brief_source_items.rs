//! Extract independent matters before applying a reading budget to the brief.
use std::{
    collections::{HashMap, HashSet},
    ops::Range,
    time::Instant,
};

use serde::Deserialize;
use serde_json::{Value, json};

use super::{
    Document, Kind, Unit,
    answer_layout::{self, Fact, Placement},
    factual_audit, line, normalized,
};

const EXTRACT: &str = include_str!("automatic_brief_source_items.txt");
const ORGANIZE: &str = include_str!("automatic_brief_source_item_layout.txt");
const WINDOW_BYTES: usize = 13 * 1024;
const WINDOW_WORKERS: usize = 3;
const FACT_LIMIT: usize = 128;
const DETAILS_LIMIT: usize = 8;

pub(super) fn enabled() -> bool {
    std::env::var("COMPANION_TYPE_MINUTES_SOURCE_ITEMS").as_deref() == Ok("1")
}

#[derive(Deserialize)]
#[serde(rename_all = "lowercase")]
enum Role {
    Status,
    Opinion,
    Recommendation,
    Forecast,
    Decision,
    Action,
    Question,
}

impl Role {
    fn category(self) -> (Kind, Placement) {
        match self {
            Self::Status => (Kind::Status, Placement::Topic),
            Self::Opinion => (Kind::Opinion, Placement::Topic),
            Self::Recommendation => (Kind::Recommendation, Placement::Topic),
            Self::Forecast => (Kind::Forecast, Placement::Topic),
            Self::Decision => (Kind::Decision, Placement::Decision),
            Self::Action => (Kind::Decision, Placement::Action),
            Self::Question => (Kind::Status, Placement::Question),
        }
    }
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct SourceItem {
    role: Role,
    text: String,
    evidence: Vec<String>,
    owner: Option<String>,
    due: Option<String>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct SourceAnswer {
    id: String,
    items: Vec<SourceItem>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Extraction {
    units: Vec<SourceAnswer>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct TopicIds {
    title: String,
    points: Vec<String>,
    details: Vec<String>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Layout {
    purpose: String,
    topics: Vec<TopicIds>,
}

fn parse<T: serde::de::DeserializeOwned>(raw: &str) -> Result<T, String> {
    serde_json::from_str(super::super::strip_code_fences(raw).trim())
        .map_err(|error| format!("纪要事项回包结构不完整：{error}"))
}

fn windows(units: &[Unit]) -> Vec<Range<usize>> {
    let mut windows = Vec::new();
    let mut start = 0;
    let mut bytes = 0;
    for (index, unit) in units.iter().enumerate() {
        if index > start && bytes + unit.text.len() > WINDOW_BYTES {
            windows.push(start..index);
            bytes = 0;
            start = index;
        }
        bytes += unit.text.len();
    }
    if start < units.len() {
        windows.push(start..units.len());
    }
    windows
}

struct Window<'a> {
    core: &'a [Unit],
    offered: &'a [Unit],
    evidence: &'a [Value],
}

impl Window<'_> {
    fn input(&self) -> Value {
        let units = self.offered.iter().map(|unit| {
            let sentences = self.evidence.iter().filter(|row| row["source"] == unit.id)
                .map(|row| json!({"id":row["id"],"text":row["text"]})).collect::<Vec<_>>();
            json!({"id":unit.id,"primary":self.core.iter().any(|core| core.id == unit.id),
                "sentences":sentences})
        }).collect::<Vec<_>>();
        json!({"sourceUnits":units})
    }

    fn decode(&self, raw: &str) -> Result<Vec<Fact>, String> {
        let extraction: Extraction = parse(raw)?;
        if !extraction.units.iter().map(|answer| answer.id.as_str())
            .eq(self.core.iter().map(|unit| unit.id.as_str()))
        {
            return Err("原话分段的核对记录不完整，已有纪要和原文保留。".into());
        }
        let unit_ids: HashSet<_> = self.offered.iter().map(|unit| unit.id.as_str()).collect();
        let known: HashMap<_, _> = self.evidence.iter()
            .filter(|row| unit_ids.contains(row["source"].as_str().unwrap()))
            .map(|row| (row["id"].as_str().unwrap(), row)).collect();
        let known_ids = known.keys().copied().collect();
        let mut facts = Vec::new();
        for answer in extraction.units {
            for item in answer.items {
                let (kind, placement) = item.role.category();
                if !line(&item.text, 90) || item.evidence.is_empty() || item.evidence.len() > 8
                    || placement != Placement::Action && (item.owner.is_some() || item.due.is_some())
                {
                    return Err("纪要事项格式不完整，已有纪要和原文保留。".into());
                }
                let evidence = item.evidence.iter().map(|id| {
                    factual_audit::canonical_sentence_reference(id, &known_ids)
                        .ok_or_else(|| "纪要事项引用了未提供的原话。".to_string())
                }).collect::<Result<Vec<_>, _>>()?;
                if !evidence.iter().any(|id| known[id.as_str()]["source"] == answer.id) {
                    return Err("纪要事项缺少本段主要依据，已有纪要和原文保留。".into());
                }
                let snippets: Vec<_> = evidence.iter().map(|id| known[id.as_str()]["text"].as_str().unwrap()).collect();
                let owner = item.owner.filter(|owner| line(owner, 80) && snippets.iter()
                    .any(|text| normalized(text).contains(&normalized(owner))));
                let due = item.due.filter(|due| line(due, 80) && snippets.iter()
                    .any(|text| due_is_bound(text, due)));
                facts.push(Fact {id: String::new(), kind, placement, text: item.text, owner, due, evidence});
                if facts.len() > FACT_LIMIT {
                    return Err("纪要分段返回的事项超过整理容量，完整原文保留。".into());
                }
            }
        }
        Ok(facts)
    }
}

fn due_is_bound(sentence: &str, due: &str) -> bool {
    const BEFORE: &[&str] = &["截止到", "截止", "最迟", "不晚于", "必须在", "务必在", "须在", "截至"];
    const AFTER: &[&str] = &["之前", "以前", "前", "以内", "之内", "为止", "截止"];
    const ACTION: &[&str] = &["提交", "交付", "完成", "交稿", "报给", "发给", "交给"];
    let due = normalized(due);
    let sentence = normalized(sentence);
    sentence.match_indices(&due).any(|(start, _)| {
        let left = sentence[..start].rsplit(['，', ',', '：', ':', '。', '；']).next().unwrap_or("");
        let right = &sentence[start + due.len()..];
        BEFORE.iter().any(|marker| left.ends_with(marker) || due.starts_with(marker))
            || AFTER.iter().any(|marker| right.starts_with(marker) || due.ends_with(marker))
            || ACTION.iter().any(|verb| right.starts_with(verb))
                && ["必须", "请", "需要", "我会", "负责", "要在"].iter().any(|cue| left.contains(cue))
    })
}

fn seal_items(mut facts: Vec<Fact>, units: &[Unit]) -> Result<Vec<Fact>, String> {
    let mut seen = HashSet::new();
    facts.retain(|fact| seen.insert((
        fact.kind.label(), fact.placement,
        normalized(&fact.text), fact.owner.clone(), fact.due.clone(),
    )));
    for (index, fact) in facts.iter_mut().enumerate() {
        fact.id = format!("a{index:03}");
    }
    answer_layout::validate_facts(&facts, units, FACT_LIMIT)?;
    Ok(facts)
}

fn organize(raw: &str, facts: &[Fact], units: &[Unit]) -> Result<Document, String> {
    let layout: Layout = parse(raw)?;
    let topics = layout.topics.iter().map(|topic| json!({"title":topic.title,
        "points":topic.points.iter().map(|id| [id]).collect::<Vec<_>>(),
        "details":topic.details.iter().map(|id| [id]).collect::<Vec<_>>()})).collect::<Vec<_>>();
    let placed = |placement| facts.iter().filter(|fact| fact.placement == placement)
        .map(|fact| [&fact.id]).collect::<Vec<_>>();
    let mapped = json!({"purpose":layout.purpose,"topics":topics,"decisions":placed(Placement::Decision),
        "actionItems":placed(Placement::Action),"questions":placed(Placement::Question),"excluded":[]});
    answer_layout::assemble_with_details_limit(&mapped.to_string(), facts, units, DETAILS_LIMIT, FACT_LIMIT)
        .map(|assembled| assembled.document)
}

pub(super) fn generate(endpoint: &str, model: &str, key: &str, client: &reqwest::blocking::Client,
    units: &[Unit], start: Instant, trace: &mut Vec<Value>) -> Result<Document, String>
{
    let evidence = factual_audit::evidence_sentences(units);
    let mut facts = Vec::new();
    let ranges = windows(units);
    let cancellation = super::current_cancellation();
    for batch in ranges.chunks(WINDOW_WORKERS) {
        super::check_current()?;
        let replies = std::thread::scope(|scope| {
            let jobs = batch.iter().map(|range| {
                let window = Window {core: &units[range.clone()],
                    offered: &units[range.start.saturating_sub(1)..(range.end + 1).min(units.len())],
                    evidence: &evidence};
                let cancellation = cancellation.clone();
                scope.spawn(move || {
                    let stage = format!("source-items-{}", window.core[0].id);
                    let mut calls = Vec::new();
                    let result = super::with_parent_job(cancellation, || {
                        let raw = super::request(endpoint, model, key, client, EXTRACT, window.input(),
                            false, start, &mut calls, &stage)?;
                        window.decode(&raw)
                    });
                    (result, calls)
                })
            }).collect::<Vec<_>>();
            while jobs.iter().any(|job| !job.is_finished()) {
                let _ = super::check_current();
                std::thread::sleep(std::time::Duration::from_millis(100));
            }
            jobs.into_iter().map(|job| job.join().unwrap_or_else(|_| {
                (Err("原话分段核对未完成，已有纪要和原文保留。".into()), Vec::new())
            })).collect::<Vec<_>>()
        });
        let mut batch_items = Vec::new();
        for (result, calls) in replies {
            trace.extend(calls);
            batch_items.push(result);
        }
        for items in batch_items {
            facts.extend(items?);
        }
    }
    let facts = seal_items(facts, units)?;
    let topics = facts.iter().filter(|fact| fact.placement == Placement::Topic)
        .map(|fact| json!({"id":fact.id,"text":fact.text,"kind":fact.kind})).collect::<Vec<_>>();
    let constraints = facts.iter().filter(|fact| fact.placement != Placement::Topic)
        .map(|fact| json!({"text":fact.text,"placement":fact.placement})).collect::<Vec<_>>();
    let raw = super::request(endpoint, model, key, client, ORGANIZE, json!({"topicItems":topics,
        "meetingActionsAndDecisions":constraints}), false, start, trace, "source-items-layout")?;
    if let Some(last) = trace.last_mut() {
        last["items"] = json!(facts);
    }
    organize(&raw, &facts, units)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn source_item_keeps_supported_deadline_and_does_not_import_target_month() {
        assert!(due_is_bound("请销售周五前完成报价。", "周五"));
        assert!(due_is_bound("请销售周五前完成报价。", "周五前"));
        assert!(due_is_bound("截止到下周二，保留正确的数据。", "下周二"));
        assert!(due_is_bound("我会明天下午提交手册。", "明天下午"));
        assert!(!due_is_bound("下个月可以安排现场活动，所以请运营准备一份方案。", "下个月"));
        assert!(!due_is_bound("负责人说下个月销售，提交时间还没定。", "下个月"));
    }

    #[test]
    fn source_item_assembly_retains_independent_commitments_and_refuses_missing_ids() {
        let units = vec![Unit { id:"u000".into(), text: "讨论校服。\n请采购组周五前提交材料清单。\n请质检组周五前提交检验清单。".into() }];
        let evidence = factual_audit::evidence_sentences(&units);
        let window = Window { core: &units, offered: &units, evidence: &evidence };
        let raw = json!({"units":[{"id":"u000","items":[
            {"role":"status","text":"讨论校服。","evidence":["e0000"]},
            {"role":"action","text":"提交材料清单。","owner":"采购组","due":"周五前","evidence":["e0001"]},
            {"role":"action","text":"提交检验清单。","owner":"质检组","due":"周五前","evidence":["e0002"]}
        ]}]}).to_string();
        let facts = seal_items(window.decode(&raw).unwrap(), &units).unwrap();
        let layout = json!({"purpose":"讨论校服","topics":[{"title":"校服筹备","points":["a000"],"details":[]}]});
        let document = organize(&layout.to_string(), &facts, &units).unwrap();
        assert_eq!(document.action_items.len(), 2);
        assert_eq!(document.action_items[0].owner.as_deref(), Some("采购组"));
        assert_eq!(document.action_items[1].owner.as_deref(), Some("质检组"));
        assert!(organize(&layout.to_string().replace("a000","a001"), &facts, &units).is_err());
        assert!(window.decode(&raw.replace("e0002","e9999")).is_err());
        assert!(window.decode(r#"{"units":[]}"#).is_err());
    }

    #[test]
    #[ignore = "isolated windowed source-item replay, explicitly invoked with a loopback service"]
    fn replay_source_items_windows_application_entry() {
        use crate::backend::minutes::{CompanionMinutesManager, tests::session_with_text};
        let setting = |name| std::env::var(name).expect(name);
        assert!(enabled());
        assert_eq!(setting("DEEPSEEK_API_KEY"), "qm06-unified-relay");
        assert!(setting("DEEPSEEK_BASE_URL").starts_with("http://127.0.0.1:"));
        let fixture: Value = serde_json::from_slice(&std::fs::read(setting("QM06_INPUT")).unwrap()).unwrap();
        let mut session = session_with_text(fixture["text"].as_str().unwrap());
        session.id = fixture["id"].as_str().unwrap().into();
        session.title = fixture["title"].as_str().unwrap().into();
        session.duration_ms = fixture["durationMs"].as_u64().unwrap();
        let start = Instant::now();
        let minutes = CompanionMinutesManager::new().generate(&session, "2026-11-20T00:00:00Z");
        let output = json!({"minutes":minutes,"elapsedSeconds":start.elapsed().as_secs_f64()});
        std::fs::write(setting("QM06_RESULT"), serde_json::to_vec_pretty(&output).unwrap()).unwrap();
    }
}
