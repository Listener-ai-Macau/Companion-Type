//! Extract independent matters before applying a reading budget to the brief.
use std::{
    collections::{HashMap, HashSet},
    ops::Range,
    sync::LazyLock,
    time::Instant,
};

use serde::Deserialize;
use serde_json::{Value, json};

use super::{
    Action, Document, Entry, Kind, Unit,
    answer_layout::{self, Fact, Placement},
    factual_audit, line, normalized,
};

const EXTRACT: &str = include_str!("automatic_brief_source_items.txt");
const ORGANIZE: &str = include_str!("automatic_brief_source_item_layout.txt");
const FIND_MISSING: &str = include_str!("automatic_brief_source_item_missing.txt");
const WINDOW_BYTES: usize = 13 * 1024;
const WINDOW_WORKERS: usize = 3;
const FACT_LIMIT: usize = 128;
pub(super) const DETAILS_LIMIT: usize = 24;

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

impl SourceItem {
    fn bind(self, known: &HashMap<&str, &Value>, known_ids: &HashSet<&str>) -> Result<Fact, String> {
        let (kind, placement) = self.role.category();
        if !line(&self.text, 90) || self.evidence.is_empty() || self.evidence.len() > 8 {
            return Err("纪要事项格式不完整，已有纪要和原文保留。".into());
        }
        let evidence = self.evidence.iter().map(|id| {
            factual_audit::canonical_sentence_reference(id, known_ids)
                .ok_or_else(|| "纪要事项引用了未提供的原话。".to_string())
        }).collect::<Result<Vec<_>, _>>()?;
        let mut seen = HashSet::new();
        let evidence: Vec<_> = evidence.into_iter().filter(|id| seen.insert(id.clone())).collect();
        let snippets: Vec<_> = evidence.iter().map(|id| known[id.as_str()]["text"].as_str().unwrap()).collect();
        let owner = self.owner.filter(|owner| line(owner, 80) && snippets.iter()
            .any(|text| normalized(text).contains(&normalized(owner))));
        let (text, owner, due) = if placement == Placement::Action {
            let due = self.due.filter(|due| line(due, 80) && snippets.iter()
                .any(|text| due_is_bound(text, due)));
            (self.text, owner, due)
        } else {
            // A speaker label is not a work assignment. Preserve an exact
            // speaking label as attribution where it is absent.
            let text = owner.as_deref().filter(|name| matches!(kind, Kind::Opinion | Kind::Recommendation | Kind::Forecast)
                && !self.text.contains(name)
                && snippets.iter().any(|source| source.split_once([':', '：'])
                    .is_some_and(|(label, _)| label.trim() == *name)))
                .map(|name| format!("{name}表示，{}", self.text));
            (text.filter(|text| line(text, 90)).unwrap_or(self.text), None, None)
        };
        Ok(Fact {id: String::new(), kind, placement, text, owner, due, evidence})
    }
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
    #[serde(default, rename = "type")]
    _format: super::ResponseFormatMarker,
    purpose: String,
    topics: Vec<TopicIds>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct MissingItems {
    #[serde(default, rename = "type")]
    _format: super::ResponseFormatMarker,
    additions: Vec<MissingItem>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct MissingItem {
    item: SourceItem,
    topic: Option<String>,
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

struct CheckedWindow {
    facts: Vec<Fact>,
    ignored_neighbors: usize,
    ignored_neighbor_only_items: usize,
    normalized_topic_metadata: usize,
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

    fn decode(&self, raw: &str) -> Result<CheckedWindow, String> {
        let extraction: Extraction = parse(raw)?;
        let unit_ids: HashSet<_> = self.offered.iter().map(|unit| unit.id.as_str()).collect();
        let primary: HashSet<_> = self.core.iter().map(|unit| unit.id.as_str()).collect();
        let missing = || "原话分段的核对记录不完整，已有纪要和原文保留。".to_string();
        let mut by_id = HashMap::new();
        let mut ignored_neighbors = 0;
        for answer in extraction.units {
            if !unit_ids.contains(answer.id.as_str()) {
                return Err(missing());
            }
            if !primary.contains(answer.id.as_str()) {
                // This unit has its own primary request. The context copy
                // cannot produce a second set of competing facts.
                ignored_neighbors += 1;
                continue;
            }
            if by_id.insert(answer.id, answer.items).is_some() {
                return Err(missing());
            }
        }
        let known: HashMap<_, _> = self.evidence.iter()
            .filter(|row| unit_ids.contains(row["source"].as_str().unwrap()))
            .map(|row| (row["id"].as_str().unwrap(), row)).collect();
        let known_ids = known.keys().copied().collect();
        let mut facts = Vec::new();
        let mut ignored_neighbor_only_items = 0;
        let mut normalized_topic_metadata = 0;
        for unit in self.core {
            for item in by_id.remove(&unit.id).ok_or_else(missing)? {
                let has_metadata = item.owner.is_some() || item.due.is_some();
                let fact = item.bind(&known, &known_ids)?;
                if !fact.evidence.iter().any(|id| primary.contains(known[id.as_str()]["source"].as_str().unwrap())) {
                    ignored_neighbor_only_items += 1;
                    continue;
                }
                if has_metadata && fact.placement != Placement::Action {
                    normalized_topic_metadata += 1;
                }
                facts.push(fact);
                if facts.len() > FACT_LIMIT {
                    return Err("纪要分段返回的事项超过整理容量，完整原文保留。".into());
                }
            }
        }
        Ok(CheckedWindow { facts, ignored_neighbors, ignored_neighbor_only_items, normalized_topic_metadata })
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

fn complete_layout(layout: &mut Layout, facts: &[Fact]) -> Result<Value, String> {
    let fail = || "纪要组稿超出可恢复的事项范围，已有纪要保留。".to_string();
    let order: HashMap<_, _> = facts.iter().enumerate().filter(|(_, fact)| fact.placement == Placement::Topic)
        .map(|(index, fact)| (fact.id.as_str(), index)).collect();
    if layout.topics.is_empty() || layout.topics.len() > 8 {
        return Err(fail());
    }
    let mut used = HashSet::new();
    let mut moved = Vec::new();
    for topic in &mut layout.topics {
        if topic.points.iter().chain(&topic.details).any(|id| !order.contains_key(id.as_str())) {
            return Err(fail());
        }
        topic.points.retain(|id| used.insert(id.clone()));
        topic.details.retain(|id| used.insert(id.clone()));
        if topic.points.len() > 3 {
            let overflow = topic.points.split_off(3);
            moved.extend(overflow.iter().cloned());
            topic.details.splice(0..0, overflow);
        }
        if topic.points.is_empty() && !topic.details.is_empty() {
            topic.points.push(topic.details.remove(0));
        }
    }
    layout.topics.retain(|topic| !topic.points.is_empty());
    let mut main_length: usize = layout.topics.iter().flat_map(|topic| &topic.points)
        .map(|id| facts[order[id.as_str()]].text.chars().count()).sum();
    for topic in layout.topics.iter_mut().rev() {
        while main_length > 1000 && topic.points.len() > 1 {
            let id = topic.points.pop().ok_or_else(fail)?;
            main_length -= facts[order[id.as_str()]].text.chars().count();
            moved.push(id.clone());
            topic.details.insert(0, id);
        }
    }
    // If an offered group is full or a known item was missed, use the closest
    // item by source order to select a group with room. Zero facts are rewritten.
    let mut pending = Vec::new();
    for topic in &mut layout.topics {
        if topic.details.len() > DETAILS_LIMIT {
            pending.extend(topic.details.split_off(DETAILS_LIMIT));
        }
    }
    let restored: Vec<_> = facts.iter().filter(|fact| fact.placement == Placement::Topic && !used.contains(&fact.id))
        .map(|fact| fact.id.clone()).collect();
    pending.extend(restored.iter().cloned());
    for id in pending {
        let index = order[id.as_str()];
        let topic = layout.topics.iter_mut().filter(|topic| topic.details.len() < DETAILS_LIMIT)
            .min_by_key(|topic| topic.points.iter().chain(&topic.details)
                .map(|item| order[item.as_str()].abs_diff(index)).min().unwrap_or(usize::MAX))
            .ok_or_else(fail)?;
        topic.details.push(id);
    }
    Ok(json!({"restoredTopicIds":restored,"movedToDetails":moved}))
}

fn organize(raw: &str, facts: &[Fact], units: &[Unit]) -> Result<(Document, Value), String> {
    let mut layout: Layout = parse(raw)?;
    let projection = complete_layout(&mut layout, facts)?;
    let topics = layout.topics.iter().map(|topic| json!({"title":topic.title,
        "points":topic.points.iter().map(|id| [id]).collect::<Vec<_>>(),
        "details":topic.details.iter().map(|id| [id]).collect::<Vec<_>>()})).collect::<Vec<_>>();
    let placed = |placement| facts.iter().filter(|fact| fact.placement == placement)
        .map(|fact| [&fact.id]).collect::<Vec<_>>();
    let mapped = json!({"purpose":layout.purpose,"topics":topics,"decisions":placed(Placement::Decision),
        "actionItems":placed(Placement::Action),"questions":placed(Placement::Question),"excluded":[]});
    answer_layout::assemble_with_details_limit(&mapped.to_string(), facts, units, DETAILS_LIMIT, FACT_LIMIT)
        .map(|assembled| (assembled.document, projection))
}

fn append_missing(raw: &str, mut doc: Document, units: &[Unit], evidence: &[Value]) -> Result<Document, String> {
    let missing: MissingItems = parse(raw)?;
    if missing.additions.len() > 4 {
        return Err("纪要本轮漏项核对超出补充范围，已有纪要保留。".into());
    }
    let known: HashMap<_, _> = evidence.iter().map(|row| (row["id"].as_str().unwrap(), row)).collect();
    let known_ids = known.keys().copied().collect();
    let mut represented: HashSet<_> = doc.topics.iter().flat_map(|topic| {
        topic.points.iter().map(|entry| normalized(&entry.text))
            .chain(topic.details.iter().map(|entry| normalized(&entry.text)))
    }).chain(doc.decisions.iter().map(|entry| normalized(&entry.text)))
        .chain(doc.questions.iter().map(|entry| normalized(&entry.text))).collect();
    for addition in missing.additions {
        let fact = addition.item.bind(&known, &known_ids)?;
        let mut selected = HashSet::new();
        let sources: Vec<_> = fact.evidence.iter().map(|id| known[id.as_str()]["source"].as_str().unwrap())
            .filter(|id| selected.insert(*id)).map(str::to_owned).collect();
        let key = normalized(&fact.text);
        if fact.placement == Placement::Action {
            if addition.topic.is_some() {
                return Err("补充交办的栏目无效，已有纪要保留。".into());
            }
            if !doc.action_items.iter().any(|action| normalized(&action.text) == key
                && action.owner == fact.owner && action.due == fact.due)
            {
                doc.action_items.push(Action { text:fact.text, owner:fact.owner, due:fact.due, sources });
            }
            continue;
        }
        if !represented.insert(key) {
            continue;
        }
        let entry = Entry {text:fact.text, sources, quantity_needs_review:false};
        match (fact.placement, addition.topic) {
            (Placement::Topic, Some(title)) => {
                let topic = doc.topics.iter_mut().find(|topic| topic.title == title)
                    .ok_or("补充事项没有对应的原议题，已有纪要保留。")?;
                topic.details.push(entry);
            }
            (Placement::Decision, None) => doc.decisions.push(entry),
            (Placement::Question, None) => doc.questions.push(entry),
            _ => return Err("补充事项的栏目无效，已有纪要保留。".into()),
        }
    }
    super::validate(&doc, units)?;
    Ok(doc)
}

fn omission_cues(doc: &Document, evidence: &[Value]) -> Vec<Value> {
    static LITERAL: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:[0-9０-９]+(?:[.．][0-9０-９]+)?|[零〇一二两三四五六七八九十百千万亿半]+)\s*(?:美元|元|块钱|个月|季度|工作日|小时|分钟|周|天|年|%|％)|(?:明天|后天|下周|本周|下个月|本月底|周[一二三四五六日])(?:之前|以前|截止|前|为止)"
    ).expect("constant omission cue expression"));
    let mut displayed: HashMap<String, String> = HashMap::new();
    let mut include = |sources: &[String], text: &str| {
        for source in sources {
            displayed.entry(source.clone()).or_default().push_str(&normalized(text));
        }
    };
    for topic in &doc.topics {
        for point in &topic.points {
            include(&point.sources, &point.text);
        }
        for detail in &topic.details {
            include(&detail.sources, &detail.text);
        }
    }
    for entry in doc.decisions.iter().chain(&doc.questions) {
        include(&entry.sources, &entry.text);
    }
    for action in &doc.action_items {
        include(&action.sources, &action.text);
        if let Some(due) = &action.due {
            include(&action.sources, due);
        }
    }
    let mut seen = HashSet::new();
    let candidates: Vec<_> = evidence.iter().filter_map(|row| {
        let unit = row["source"].as_str()?;
        let text = row["text"].as_str()?;
        let text = text.split_once([':', '：']).filter(|(head, _)| head.starts_with("说话人"))
            .map_or(text, |(_, rest)| rest);
        let span = LITERAL.find_iter(text).find(|item| {
            let value = normalized(item.as_str());
            !displayed.get(unit).is_some_and(|current| current.contains(&value))
                && seen.insert((unit, value))
        })?;
        Some(json!({"id":row["id"],"span":span.as_str()}))
    }).collect();
    let count = candidates.len().min(24);
    (0..count).map(|index| candidates[index*candidates.len()/count].clone()).collect()
}

pub(super) fn fill_omissions(endpoint: &str, model: &str, key: &str, client: &reqwest::blocking::Client,
    doc: Document, units: &[Unit], start: Instant, trace: &mut Vec<Value>) -> Result<Document, String>
{
    let evidence = factual_audit::evidence_sentences(units);
    let cues = omission_cues(&doc, &evidence);
    // This pass locates at most four source relations. The separate factual
    // audit remains responsible for judging them before publication.
    let raw = super::request(endpoint, model, key, client, FIND_MISSING,
        json!({"sourceSentences":evidence,"currentBrief":doc,"lexicalCues":cues}), false, start, trace, "source-items-omissions")?;
    if let Some(call) = trace.last_mut() {
        call["omissionCues"] = json!(cues);
    }
    append_missing(&raw, doc, units, &evidence)
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
                        let checked = window.decode(&raw)?;
                        if let Some(call) = calls.last_mut() {
                            call["sourceProjection"] = json!({
                                "acceptedItems":checked.facts.len(),
                                "ignoredContextUnits":checked.ignored_neighbors,
                                "ignoredContextOnlyItems":checked.ignored_neighbor_only_items,
                                "normalizedTopicMetadata":checked.normalized_topic_metadata
                            });
                        }
                        Ok(checked.facts)
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
    let (doc, projection) = organize(&raw, &facts, units)?;
    if let Some(last) = trace.last_mut() {
        last["layoutProjection"] = projection;
    }
    Ok(doc)
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
        let facts = seal_items(window.decode(&raw).unwrap().facts, &units).unwrap();
        let layout = json!({"purpose":"讨论校服","topics":[{"title":"校服筹备","points":["a000"],"details":[]}]});
        let (document, _) = organize(&layout.to_string(), &facts, &units).unwrap();
        assert_eq!(document.action_items.len(), 2);
        assert_eq!(document.action_items[0].owner.as_deref(), Some("采购组"));
        assert_eq!(document.action_items[1].owner.as_deref(), Some("质检组"));
        assert!(organize(&layout.to_string().replace("a000","a001"), &facts, &units).is_err());
        assert!(window.decode(&raw.replace("e0002","e9999")).is_err());
        assert!(window.decode(r#"{"units":[]}"#).is_err());
    }

    #[test]
    fn echoes_of_a_neighbor_do_not_discard_the_primary_review() {
        let units = vec![
            Unit { id:"u000".into(), text:"说话人1：讨论校服。".into() },
            Unit { id:"u001".into(), text:"说话人2：我认为面料要透气。".into() },
        ];
        let evidence = factual_audit::evidence_sentences(&units);
        let window = Window { core: &units[1..], offered: &units, evidence: &evidence };
        let raw = json!({"units":[{"id":"u000","items":[]},{"id":"u001","items":[
            {"role":"opinion","text":"面料要透气。","owner":"说话人2","evidence":["e0001"]},
            {"role":"status","text":"讨论校服。","evidence":["e0000"]}
        ]}]}).to_string();
        let result = window.decode(&raw).unwrap();
        assert_eq!(result.ignored_neighbors, 1);
        assert_eq!(result.ignored_neighbor_only_items, 1);
        assert_eq!(result.normalized_topic_metadata, 1);
        assert_eq!(result.facts.len(), 1);
        assert_eq!(result.facts[0].text, "说话人2表示，面料要透气。");
        assert!(result.facts[0].owner.is_none());
        assert!(window.decode(&raw.replace("u001","u999")).is_err());
    }

    #[test]
    fn source_omissions_preserve_prior_items_and_require_real_evidence() {
        let units = vec![Unit { id:"u000".into(),
            text:"讨论校服。\n采购组周五前提交面料清单。\n运动服预算未通过。".into() }];
        let evidence = factual_audit::evidence_sentences(&units);
        let doc: Document = serde_json::from_value(json!({"purpose":"讨论校服",
            "topics":[{"title":"校服筹备","points":[{"kind":"status","text":"讨论校服。","sources":["u000"]}],
                "details":[]}],"decisions":[],"actionItems":[],"questions":[]})).unwrap();
        let raw = json!({"additions":[
            {"topic":"校服筹备","item":{"role":"status","text":"运动服预算未通过。","evidence":["e0002"]}},
            {"topic":null,"item":{"role":"action","text":"提交面料清单。","owner":"采购组","due":"周五前","evidence":["e0001"]}},
            {"topic":"校服筹备","item":{"role":"status","text":"讨论校服。","evidence":["e0000"]}}
        ]}).to_string();
        let enriched = append_missing(&raw, doc.clone(), &units, &evidence).unwrap();
        assert_eq!(enriched.topics[0].points[0].text, doc.topics[0].points[0].text);
        assert_eq!(enriched.topics[0].details.len(), 1);
        assert_eq!(enriched.topics[0].details[0].text, "运动服预算未通过。");
        assert_eq!(enriched.action_items[0].due.as_deref(), Some("周五前"));
        assert!(append_missing(&raw.replace("e0002","e9999"), doc, &units, &evidence).is_err());
    }

    #[test]
    fn source_layout_keeps_omitted_and_overflowing_ids_without_rewriting() {
        let units = vec![Unit {id:"u000".into(),text:"讨论校服。".into()}];
        let facts: Vec<_> = (0..5).map(|index| Fact {
            id:format!("a{index:03}"), kind:Kind::Status, placement:Placement::Topic,
            text:format!("保留第{index}项。"), owner:None, due:None, evidence:vec!["e0000".into()],
        }).collect();
        let raw = json!({"purpose":"讨论校服","topics":[{"title":"校服筹备",
            "points":["a000","a001","a002","a003"],"details":[]}]}).to_string();
        let (assembled, projection) = organize(&raw, &facts, &units).unwrap();
        assert_eq!(assembled.topics[0].points.len(), 3);
        assert_eq!(projection["restoredTopicIds"], json!(["a004"]));
        assert_eq!(projection["movedToDetails"], json!(["a003"]));
        assert_eq!(assembled.topics[0].details[0].text, facts[3].text);
        assert_eq!(assembled.topics[0].details[1].text, facts[4].text);
        assert!(organize(&raw.replace("a003","a999"), &facts, &units).is_err());
    }

    #[test]
    fn omission_cue_finds_an_unwritten_duration_in_an_already_cited_sentence() {
        let units = vec![Unit{id:"u000".into(),text:"客户来自学校，学校每年有三个月的假期。".into()}];
        let evidence = factual_audit::evidence_sentences(&units);
        let doc: Document = serde_json::from_value(json!({"purpose":"餐饮讨论",
            "topics":[{"title":"客流","points":[{"kind":"status","text":"客户来自学校。","sources":["u000"]}]}],
            "decisions":[],"actionItems":[],"questions":[]})).unwrap();
        assert_eq!(omission_cues(&doc,&evidence),json!([{"id":"e0000","span":"三个月"}]).as_array().unwrap().clone());
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
