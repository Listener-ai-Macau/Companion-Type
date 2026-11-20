//! Extract independent matters before applying a reading budget to the brief.
use std::{
    collections::{HashMap, HashSet},
    ops::Range,
    sync::LazyLock,
    time::Instant,
};

use serde::{Deserialize, Serialize};
use serde_json::{Value, json};

use super::{
    Action, Document, Entry, Kind, Unit,
    answer_layout::{self, Fact, Placement},
    factual_audit, line, normalized,
};

const EXTRACT: &str = include_str!("automatic_brief_source_items.txt");
const ORGANIZE: &str = include_str!("automatic_brief_source_item_layout.txt");
const FIND_MISSING: &str = include_str!("automatic_brief_source_item_missing.txt");
const RECHECK_MEASURES: &str = include_str!("automatic_brief_source_item_recheck.txt");
const REPAIR_COVERAGE: &str = include_str!("automatic_brief_source_coverage_repair.txt");
const WINDOW_BYTES: usize = 13 * 1024;
const WINDOW_WORKERS: usize = 3;
const FACT_LIMIT: usize = 128;
pub(super) const DETAILS_LIMIT: usize = super::SOURCE_ITEMS_DETAILS_LIMIT;

pub(super) fn enabled() -> bool {
    std::env::var("COMPANION_TYPE_MINUTES_SOURCE_ITEMS").as_deref() == Ok("1")
}

#[derive(Clone, Deserialize)]
#[serde(rename_all = "lowercase")]
enum Role {
    #[serde(alias = "condition")]
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

#[derive(Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub(super) struct SourceItem {
    role: Role,
    pub(super) text: String,
    pub(super) evidence: Vec<String>,
    pub(super) owner: Option<String>,
    pub(super) due: Option<String>,
}

impl SourceItem {
    pub(super) fn bind(self, known: &HashMap<&str, &Value>, known_ids: &HashSet<&str>) -> Result<Fact, String> {
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
    #[serde(default)]
    checks: Vec<SourceCheck>,
    #[serde(default)]
    additions: Vec<MissingItem>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub(super) struct MissingItem {
    pub(super) item: SourceItem,
    pub(super) topic: Option<String>,
    #[serde(rename = "newAspect")]
    pub(super) new_aspect: Option<String>,
}

#[derive(Serialize, Debug)]
struct SourceCue {
    id: String,
    evidence: String,
    span: String,
}

#[derive(Deserialize)]
#[serde(tag = "status", rename_all = "camelCase")]
enum SourceCheck {
    Covered { id: String, claim: String, #[serde(default)] proof: Option<CoverageProof> },
    Missing { id: String, addition: MissingItem },
    NeedsReview { id: String, addition: MissingItem },
    Conflict { id: String, claim: String },
    Background { id: String, reason: String },
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct CoverageProof {
    source_quote: String,
    statement_quote: String,
}

impl SourceCheck {
    fn id(&self) -> &str {
        match self {
            Self::Covered { id, .. } | Self::Missing { id, .. } | Self::NeedsReview { id, .. }
            | Self::Conflict { id, .. } | Self::Background { id, .. } => id,
        }
    }
}

pub(super) struct CheckedOmissions {
    pub(super) doc: Document,
    pub(super) conflicts: Vec<Value>,
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

pub(super) fn omission_topic(doc: &Document, sources: &[String], units: &[Unit]) -> Option<usize> {
    let order: HashMap<_, _> = units.iter().enumerate().map(|(index, unit)| (unit.id.as_str(), index)).collect();
    let anchors: Vec<_> = sources.iter().filter_map(|id| order.get(id.as_str())).copied().collect();
    doc.topics.iter().enumerate().filter(|(_, topic)| topic.details.len() < DETAILS_LIMIT)
        .filter_map(|(index, topic)| {
            let distance = topic.points.iter().flat_map(|point| &point.sources)
                .chain(topic.details.iter().flat_map(|entry| &entry.sources))
                .filter_map(|id| order.get(id.as_str()))
                .flat_map(|offset| anchors.iter().map(move |anchor| offset.abs_diff(*anchor)))
                .min()?;
            Some((distance, index))
        })
        .min().map(|(_, index)| index)
}

pub(super) fn append_missing(additions: Vec<MissingItem>, mut doc: Document, units: &[Unit], evidence: &[Value]) -> Result<Document, String> {
    let known: HashMap<_, _> = evidence.iter().map(|row| (row["id"].as_str().unwrap(), row)).collect();
    let known_ids = known.keys().copied().collect();
    let mut represented: HashSet<_> = doc.topics.iter().flat_map(|topic| {
        topic.points.iter().map(|entry| normalized(&entry.text))
            .chain(topic.details.iter().map(|entry| normalized(&entry.text)))
    }).chain(doc.decisions.iter().map(|entry| normalized(&entry.text)))
        .chain(doc.questions.iter().map(|entry| normalized(&entry.text))).collect();
    for addition in additions {
        let fact = addition.item.bind(&known, &known_ids)?;
        let mut selected = HashSet::new();
        let sources: Vec<_> = fact.evidence.iter().map(|id| known[id.as_str()]["source"].as_str().unwrap())
            .filter(|id| selected.insert(*id)).map(str::to_owned).collect();
        let key = normalized(&fact.text);
        if fact.placement == Placement::Action {
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
        match fact.placement {
            Placement::Topic => {
                // The fact and its evidence have already been checked for
                // shape. A missing display hint does not erase an entire reply.
                let fail = || "补充事项没有对应的原议题，已有纪要保留。".to_string();
                let requested = addition.topic.as_ref().and_then(|title| doc.topics.iter().position(|topic| &topic.title == title));
                let index = requested.filter(|index| doc.topics[*index].details.len() < DETAILS_LIMIT)
                    .or_else(|| omission_topic(&doc, &entry.sources, units)).ok_or_else(fail)?;
                doc.topics[index].details.push(entry);
            }
            Placement::Decision => doc.decisions.push(entry),
            Placement::Question => doc.questions.push(entry),
            Placement::Action => unreachable!("handled above"),
        }
    }
    super::validate(&doc, units)?;
    Ok(doc)
}

fn omission_cues(facts: &[Fact], evidence: &[Value]) -> Vec<SourceCue> {
    static LITERAL: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:[0-9０-９]+(?:[.．][0-9０-９]+)?|[零〇一二两三四五六七八九十百千万亿半]+)\s*(?:美元|元|块钱|个月|季度|工作日|小时|分钟|周|天|年|%|％)|(?:明天|后天|[本下]周[一二三四五六日]?|下个月|本月底|周[一二三四五六日])(?:之前|以前|截止|前|为止)"
    ).expect("constant omission cue expression"));
    static STATUS: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"不是主+打|不(?:再|用|需要|得|能)?(?:同时推|主推|推销|签字|放行|上线|下单|开工|发货|执行)|未(?:批准|通过|定案|决定)|暂不(?:批准|签字|执行|上线)|取消(?:原定|计划|订单|审批)|改(?:为|到|成)|以.{1,18}为准|除非|只有.{1,18}(?:才|才能)|.{1,14}为前提"
    ).expect("constant status cue expression"));
    let mut shown: HashMap<&str, HashSet<String>> = HashMap::new();
    for fact in facts {
        let measures: Vec<_> = std::iter::once(fact.text.as_str()).chain(fact.due.as_deref())
            .flat_map(|text| LITERAL.find_iter(text).map(|hit| normalized(hit.as_str())))
            .collect();
        for id in &fact.evidence {
            shown.entry(id).or_default().extend(measures.iter().cloned());
        }
    }
    let mut literals = Vec::new();
    let mut reversals = Vec::new();
    for row in evidence {
        let id = row["id"].as_str().unwrap();
        let source = row["text"].as_str().unwrap();
        let text = source.split_once([':', '：']).filter(|(head, _)| head.starts_with("说话人"))
            .map_or(source, |(_, rest)| rest);
        let mut seen = HashSet::new();
        for hit in LITERAL.find_iter(text) {
            let span = hit.as_str();
            let value = normalized(span);
            if !shown.get(id).is_some_and(|claims| claims.contains(&value))
                && seen.insert(span)
            {
                literals.push((id, span));
            }
        }
        if let Some(hit) = STATUS.find(text) {
            reversals.push((id, hit.as_str()));
        }
    }
    // Reserve places for both source numbers and final-state changes when the
    // meeting has enough candidates to fill the existing review budget.
    let total = (literals.len() + reversals.len()).min(24);
    let literal_count = literals.len().min(total - reversals.len().min(total / 2));
    let mut cues = Vec::with_capacity(total);
    for (candidates, count) in [(&literals, literal_count), (&reversals, total - literal_count)] {
        for index in 0..count {
            let (evidence, span) = candidates[index * candidates.len() / count];
            cues.push(SourceCue { id: format!("v{:03}", cues.len()), evidence: evidence.into(), span: span.into() });
        }
    }
    cues
}

fn measures(text: &str) -> impl Iterator<Item = (f64, &str)> {
    static MEASURE: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"([0-9０-９]+(?:[.．][0-9０-９]+)?[万亿]?|[零〇一二两三四五六七八九十百千万亿半]+)\s*(美元|块钱|元|个月|季度|工作日|小时|分钟|周|天|年|%|％)"
    ).expect("constant measure expression"));
    MEASURE.captures_iter(text).filter_map(|capture| {
        let unit_match = capture.get(2)?;
        let unit = unit_match.as_str();
        if unit == "年" && text[unit_match.end()..].starts_with('级') {
            return None;
        }
        let quantity = number_value(capture.get(1)?.as_str(), unit == "年")?;
        let unit = match unit { "块钱" => "元", "％" => "%", _ => unit };
        Some((quantity, unit))
    })
}

fn number_value(text: &str, year: bool) -> Option<f64> {
    let text: String = text.chars().map(|ch| match ch {
        '０'..='９' => char::from_u32(ch as u32 - '０' as u32 + '0' as u32).unwrap(),
        '．' => '.',
        _ => ch,
    }).collect();
    if let Ok(value) = text.parse::<f64>() {
        return Some(value);
    }
    let (number, factor) = match text.chars().last()? {
        '万' => (text.strip_suffix('万')?, 10_000.0),
        '亿' => (text.strip_suffix('亿')?, 100_000_000.0),
        _ => (text.as_str(), 1.0),
    };
    if let Ok(value) = number.parse::<f64>() {
        return Some(value * factor);
    }
    if text == "半" { return Some(0.5); }
    let digit = |ch| "零一二三四五六七八九".chars().position(|d| d == ch)
        .or(match ch { '〇' => Some(0), '两' => Some(2), _ => None });
    if year && text.chars().count() == 4 && text.chars().all(|ch| digit(ch).is_some()) {
        return Some(text.chars().fold(0.0, |year, ch| year * 10.0 + digit(ch).unwrap() as f64));
    }
    let (mut total, mut section, mut current) = (0.0, 0.0, None);
    for ch in text.chars() {
        if let Some(value) = digit(ch) {
            if current.replace(value).is_some_and(|previous| previous != 0) {
                return None; // Adjacent digits such as 两三 can indicate a range.
            }
            continue;
        }
        let scale = match ch {
            '十' => 10.0, '百' => 100.0, '千' => 1000.0,
            '万' => 10_000.0, '亿' => 100_000_000.0,
            _ => return None,
        };
        if scale < 10000.0 {
            section += current.take().unwrap_or(1) as f64 * scale;
        } else {
            section += current.take().unwrap_or(0) as f64;
            total = if ch == '亿' { (total + section) * scale } else { total + section * scale };
            section = 0.0;
        }
    }
    Some(total + section + current.unwrap_or(0) as f64)
}

fn measure_has_witness(span: &str, claim: &Value) -> bool {
    let Some((quantity, unit)) = measures(span).next() else { return true; };
    ["text", "due"].into_iter().filter_map(|key| claim[key].as_str()).flat_map(measures)
        .any(|(found, found_unit)| unit == found_unit && (found - quantity).abs() < 1e-8)
}

fn contextual_measure_witness(span: &str, claim: &Value, source: &str) -> bool {
    // A cited duration can be contextual rather than a second measurement.
    // Do not require a rhetorical question to repeat an already named period,
    // or treat retrospective working-year wording as a new commitment.
    let contextual_literal = |span: &str, predicate: &dyn Fn(&str, &str) -> bool| {
        let mut occurrences = source.match_indices(span).peekable();
        occurrences.peek().is_some() && occurrences.all(|(start, term)| predicate(&source[..start], &source[start + term.len()..]))
    };
    if span == "一年" && contextual_literal(span, &|_, tail| {
        ["工作的情况下", "的这个工作情况", "的工作情况"].iter().any(|cue| tail.starts_with(cue))
            || (source.contains("工作") && tail.starts_with("已经")
                && tail.chars().take(38).collect::<String>().contains("度过"))
    }) {
        return true;
    }
    if span.ends_with('天') && source.contains("为什么") && source.contains('呢')
        && contextual_literal(span, &|lead, _| lead.ends_with('这')) {
        return true;
    }
    if span == "半年" {
        let mut occurrences = source.match_indices(span).peekable();
        if occurrences.peek().is_some() && occurrences.all(|(start, _)| source[..start].ends_with(['上', '下'])) {
            // 上半年/下半年 locate a calendar period. The factual audit
            // still checks the period and does not require a duration claim.
            return true;
        }
    }
    if span == "一年" {
        let mut occurrences = source.match_indices(span).peekable();
        if occurrences.peek().is_some() && occurrences.all(|(start, term)| source[start + term.len()..].starts_with("四季")) {
            return true;
        }
    }
    if span == "半个月" && claim["kind"] != "action" && claim["kind"] != "decision"
        && (source.contains("如果") || source.contains("大约") || source.contains("大概"))
        && measure_has_witness("十五天", claim) {
        // Conversational estimates can use half a month or fifteen days.
        // A deadline or a finalized arrangement still needs its own wording.
        return true;
    }
    if measure_has_witness(span, claim) { return true; }
    let Some((value, "年")) = measures(span).next() else { return false; };
    let occurrences: Vec<_> = source.match_indices(span).map(|(start, word)| {
        (&source[..start], &source[start + word.len()..])
    }).collect();
    if !occurrences.is_empty() && occurrences.iter().all(|(_, after)| after.starts_with('级')) {
        // A grade in a school example is not a duration.
        return true;
    }
    if value != 1.0 { return false; }
    // A once-per-year denominator and a calendar year or one-year contract
    // are distinct. Compare the frequency (including its numerator) instead.
    static RATE: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"^(?:有|要|做|需|每|\s|，|,)*([0-9０-９]+|[一二两三四五六七八九十]+)(?:个)?(季|次|批|轮)"
    ).expect("constant yearly rate expression"));
    let rate = |text: &str| {
        let capture = RATE.captures(text)?;
        let value = capture.get(1)?.as_str();
        let mut chars = value.chars();
        let first = chars.next()?;
        let spoken = if !first.is_ascii() && chars.next() == Some(first) && chars.next().is_none() {
            &value[..first.len_utf8()]
        } else { value };
        Some((number_value(spoken, false)?, capture.get(2)?.as_str().to_owned()))
    };
    let spoken_rates: Vec<_> = occurrences.iter()
        .filter(|(_, after)| !after.starts_with('级')).filter_map(|(_, after)| rate(after)).collect();
    claim["text"].as_str().is_some_and(|text| {
        text.match_indices("每年").filter_map(|(start, term)| rate(&text[start + term.len()..]))
            .any(|written| spoken_rates.contains(&written))
    })
}

#[cfg(test)]
#[test]
fn period_half_year_is_distinct_from_a_stated_duration() {
    let claim = json!({"text":"奥数线上教学不够直接。"});
    assert!(contextual_measure_witness("半年", &claim, "上半年在线上授课，不够直接。"));
    assert!(contextual_measure_witness("半年", &claim, "下半年还有上半年的安排。"));
    assert!(!contextual_measure_witness("半年", &claim, "上半年讨论了半年的学习安排。"));
    assert!(!contextual_measure_witness("半年", &claim, "计划至少学习半年。"));
}

fn disputed_coverage(missing: &MissingItems, cues: &[SourceCue], doc: &Document, evidence: &[Value],
    bindings: &HashMap<String, &Vec<String>>,
) -> Vec<Value> {
    let claims = factual_audit::claims(doc);
    let by_path: HashMap<_, _> = claims.iter().map(|claim| (claim["path"].as_str().unwrap(), claim)).collect();
    let by_id: HashMap<_, _> = cues.iter().map(|cue| (cue.id.as_str(), cue)).collect();
    missing.checks.iter().filter_map(|check| {
        let SourceCheck::Covered { id, claim, .. } = check else { return None; };
        let cue = by_id.get(id.as_str())?;
        let statement = by_path.get(claim.as_str())?;
        let sentence = evidence.iter().find(|row| row["id"].as_str() == Some(cue.evidence.as_str()))?;
        let cited = bindings.get(claim);
        let wrong_measure = !contextual_measure_witness(&cue.span, statement, sentence["text"].as_str()?);
        let different_source = !cited.is_some_and(|ids| ids.contains(&cue.evidence));
        (wrong_measure || different_source).then(|| json!({
            "cue":cue, "claimedWitness":statement, "witnessEvidence":cited,
            "measureNeedsCheck":wrong_measure, "sourceNeedsCheck":different_source,
        }))
    }).collect()
}

fn coverage_quote_is_grounded(quote: &str, text: &str) -> bool {
    line(quote, 180) && quote.chars().filter(|ch| ch.is_alphanumeric()).count() >= 5
        && normalized(text).contains(&normalized(quote))
}

fn restriction() -> &'static regex::Regex {
    static RESTRICTION: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:不是(?:特别|很|太|那么的?)|不(?:够|太|能|得|允许)|没有|尚未|仍未|不得)([\p{Han}]{2,10})"
    ).unwrap());
    &RESTRICTION
}

fn related_causal_evidence(evidence: &[Value], source: &Value, phrase: &str) -> Vec<String> {
    let Some((speaker, _)) = super::super::source_resolution::split_turn_label(source["text"].as_str().unwrap()) else {
        return Vec::new();
    };
    let Some(predicate) = restriction().captures(phrase).and_then(|captures| captures.get(1)) else {
        return Vec::new();
    };
    evidence.iter().skip_while(|row| row["id"] != source["id"]).skip(1).take(12).filter_map(|row| {
        let (actual, text) = super::super::source_resolution::split_turn_label(row["text"].as_str()?)?;
        if actual != speaker || !["因为", "因此", "导致", "所以"].iter().any(|cue| text.contains(cue)) {
            return None;
        }
        restriction().captures_iter(text).any(|captures| captures.get(1).is_some_and(|m| m.as_str() == predicate.as_str()))
            .then(|| row["id"].as_str().unwrap().to_owned())
    }).collect()
}

fn rejected_coverage(checks: &[SourceCheck], disputed: &[Value], doc: &Document, evidence: &[Value],
    bindings: &HashMap<String, &Vec<String>>,
) -> Vec<Value> {
    let clauses = factual_audit::claims(doc);
    checks.iter().filter_map(|check| {
        let SourceCheck::Covered { id, claim, proof } = check else { return None; };
        let context = disputed.iter().find(|row| row["cue"]["id"] == id.as_str())?;
        let source = evidence.iter().find(|row| row["id"] == context["cue"]["evidence"])?;
        let target = clauses.iter().find(|row| row["path"] == claim.as_str());
        let source_text = source["text"].as_str()?;
        let cited = bindings.get(claim);
        let grounded = proof.as_ref().is_some_and(|proof| {
            (coverage_quote_is_grounded(&proof.source_quote, source_text) || evidence.iter().any(|row| {
                row["id"].as_str().is_some_and(|e| cited.is_some_and(|ids| ids.iter().any(|id| id == e)))
                    && coverage_quote_is_grounded(&proof.source_quote, row["text"].as_str().unwrap())
            })) && target.and_then(|row| row["text"].as_str())
                .is_some_and(|text| coverage_quote_is_grounded(&proof.statement_quote, text))
        });
        let measure_matches = target.is_some_and(|claim| {
            contextual_measure_witness(context["cue"]["span"].as_str().unwrap(), claim, source_text)
        });
        let omitted_qualification = restriction().find_iter(source_text).find(|hit| {
            !hit.as_str().ends_with(['吗', '么', '呢'])
                && !(hit.as_str().starts_with("没有") && source_text[..hit.start()].ends_with('有'))
        }).filter(|_| {
            context["sourceNeedsCheck"] == true && !target.and_then(|row| row["text"].as_str())
                .is_some_and(|text| restriction().is_match(text))
        });
        if grounded && measure_matches && omitted_qualification.is_none() { return None; }
        let mut issue = context.clone();
        issue["previousClaim"] = json!(claim);
        issue["reason"] = json!(if !measure_matches {
            "该正文未保留原话的同一数量或时长。若原话数字只是口语描述、例子或含混片段，应说明其性质；若关乎实际理解或执行，补入正确事实或写待核实。"
        } else if omitted_qualification.is_some() {
            "原话有明确的限制或不足，所指正文只写了其他内容，未表达这条限制。"
        } else { "必须分别提供原话与现有正文实际出现的同一事实短句。" });
        if let Some(qualification) = omitted_qualification {
            issue["unrepresentedSourceQuote"] = json!(qualification.as_str());
            let related = related_causal_evidence(evidence, source, qualification.as_str());
            if !related.is_empty() {
                issue["relatedCausalEvidence"] = json!(related);
            }
        }
        Some(issue)
    }).collect()
}

fn preserves_related_cause(checks: &[SourceCheck], rejected: &[Value]) -> bool {
    checks.iter().all(|check| {
        let Some(related) = rejected.iter().find(|row| row["cue"]["id"] == check.id())
            .and_then(|row| row["relatedCausalEvidence"].as_array()) else { return true; };
        match check {
            SourceCheck::Missing { addition, .. } | SourceCheck::NeedsReview { addition, .. } => related.iter()
                .all(|id| addition.item.evidence.iter().any(|evidence| id == evidence.as_str())),
            SourceCheck::Covered { .. } | SourceCheck::Conflict { .. } => true,
            SourceCheck::Background { .. } => false,
        }
    })
}

fn checked_additions(missing: MissingItems, cues: &[SourceCue], doc: &Document, facts: &[Fact], evidence: &[Value])
    -> Result<(Vec<MissingItem>, Vec<Value>), String>
{
    let fail = || "纪要关键原话核对不完整，已有结果保留。".to_string();
    if missing.checks.len() != cues.len() || missing.additions.len() > 4 {
        return Err(fail());
    }
    let claims = factual_audit::claims(doc);
    let by_path: HashMap<_, _> = claims.iter().filter(|claim| claim.get("sources").is_some())
        .map(|claim| (claim["path"].as_str().unwrap(), claim)).collect();
    let known: HashMap<_, _> = evidence.iter().map(|row| (row["id"].as_str().unwrap(), row["text"].as_str().unwrap())).collect();
    let known_ids = known.keys().copied().collect();
    let mut pending: HashMap<_, _> = cues.iter().map(|cue| (cue.id.as_str(), cue)).collect();
    let mut additions = Vec::new();
    let mut conflicts = Vec::new();
    for check in missing.checks {
        let cue = pending.remove(check.id()).ok_or_else(fail)?;
        match check {
            SourceCheck::Covered { claim, .. } => {
                let existing = by_path.get(claim.as_str()).ok_or_else(fail)?;
                if !contextual_measure_witness(&cue.span, existing, known[cue.evidence.as_str()]) { return Err(fail()); }
            }
            SourceCheck::Conflict { claim, .. } => {
                let existing = by_path.get(claim.as_str()).ok_or_else(fail)?;
                conflicts.push(json!({"claim":existing, "evidence":cue.evidence}));
            }
            check @ (SourceCheck::Missing { .. } | SourceCheck::NeedsReview { .. }) => {
                let review = matches!(check, SourceCheck::NeedsReview { .. });
                let (SourceCheck::Missing { addition, .. } | SourceCheck::NeedsReview { addition, .. }) = check else {
                    unreachable!()
                };
                if !addition.item.evidence.iter().any(|id| {
                    factual_audit::canonical_sentence_reference(id, &known_ids).as_deref() == Some(cue.evidence.as_str())
                }) || (review && (!matches!(addition.item.role, Role::Status | Role::Question)
                    || !addition.item.text.starts_with("待核实")))
                {
                    return Err(fail());
                }
                additions.push(addition);
            }
            SourceCheck::Background { reason, .. } => {
                if !line(&reason, 100) { return Err(fail()); }
            }
        }
    }
    let reused: HashSet<_> = facts.iter().flat_map(|fact| fact.evidence.iter().map(String::as_str)).collect();
    for addition in missing.additions {
        let ids: Vec<_> = addition.item.evidence.iter().map(|id| {
            factual_audit::canonical_sentence_reference(id, &known_ids).ok_or_else(fail)
        }).collect::<Result<_, _>>()?;
        let uses_new_source = ids.iter().any(|id| !reused.contains(id.as_str()));
        let has_new_aspect = addition.new_aspect.as_ref().is_some_and(|aspect| {
            line(aspect, 100) && aspect.chars().count() >= 5
                && ids.iter().any(|id| known[id.as_str()].contains(aspect))
                && !facts.iter().any(|fact| normalized(&fact.text).contains(&normalized(aspect)))
        });
        if uses_new_source || has_new_aspect {
            additions.push(addition);
        }
    }
    Ok((additions, conflicts))
}

pub(super) fn fill_omissions(endpoint: &str, model: &str, key: &str, client: &reqwest::blocking::Client,
    doc: Document, facts: &[Fact], units: &[Unit], start: Instant, trace: &mut Vec<Value>) -> Result<CheckedOmissions, String>
{
    let evidence = factual_audit::evidence_sentences(units);
    let cues = omission_cues(facts, &evidence);
    let evidence_by_claim: HashMap<_, _> = facts.iter().map(|fact| {
        ((fact.text.as_str(), fact.owner.as_deref(), fact.due.as_deref()), &fact.evidence)
    }).collect();
    let bindings: HashMap<_, _> = factual_audit::claims(&doc).into_iter().filter_map(|claim| {
        claim.get("sources")?;
        let key = (claim["text"].as_str()?, claim["owner"].as_str(), claim["due"].as_str());
        Some((claim["path"].as_str()?.to_owned(), *evidence_by_claim.get(&key)?))
    }).collect();
    let raw = super::request(endpoint, model, key, client, FIND_MISSING,
        json!({"sourceSentences":evidence,"currentBrief":doc,"lexicalCues":cues,"claimEvidence":bindings}),
        false, start, trace, "source-items-omissions")?;
    let scan_index = trace.len() - 1;
    trace[scan_index]["omissionCues"] = json!(cues);
    let mut checked: MissingItems = parse(&raw)?;
    let disputed = disputed_coverage(&checked, &cues, &doc, &evidence, &bindings);
    if !disputed.is_empty() && checked.checks.len() == cues.len() {
        let selected: HashSet<_> = disputed.iter().map(|case| case["cue"]["id"].as_str().unwrap()).collect();
        let neighborhoods: HashSet<_> = disputed.iter().flat_map(|case| {
            let id = case["cue"]["evidence"].as_str().unwrap();
            let position = evidence.iter().position(|row| row["id"].as_str() == Some(id)).unwrap();
            let after = if case["sourceNeedsCheck"] == true { 13 } else { 3 };
            position.saturating_sub(2)..(position + after).min(evidence.len())
        }).collect();
        let cited: HashSet<_> = disputed.iter().filter_map(|case| case["witnessEvidence"].as_array())
            .flatten().filter_map(Value::as_str).collect();
        let context: Vec<_> = evidence.iter().enumerate().filter_map(|(index, row)| {
            (neighborhoods.contains(&index) || cited.contains(row["id"].as_str().unwrap())).then_some(row)
        }).collect();
        let raw = super::request(endpoint,model,key,client,RECHECK_MEASURES,
            json!({"sourceSentences":context,"sourceCheckRecheck":disputed,"currentBrief":doc}),false,start,trace,"source-items-omissions-recheck")?;
        let mut fixed: MissingItems = parse(&raw)?;
        let returned: HashSet<_> = fixed.checks.iter().map(SourceCheck::id).collect();
        if returned != selected || fixed.checks.len() != selected.len() || !fixed.additions.is_empty() {
            return Err("纪要存在未完成的关键原话覆盖复核，已有结果保留。".into());
        }
        let rejected = rejected_coverage(&fixed.checks, &disputed, &doc, &evidence, &bindings);
        if !rejected.is_empty() {
            let ids: HashSet<_> = rejected.iter().filter_map(|row| row["cue"]["id"].as_str()).collect();
            let raw = super::request(endpoint,model,key,client,REPAIR_COVERAGE,
                json!({"sourceSentences":context,"sourceCoverageRepair":rejected,"currentBrief":doc}),
                false,start,trace,"source-items-coverage-repair")?;
            let repair: MissingItems = parse(&raw)?;
            let returned: HashSet<_> = repair.checks.iter().map(SourceCheck::id).collect();
            if returned != ids || repair.checks.len() != ids.len() || !repair.additions.is_empty()
                || !rejected_coverage(&repair.checks, &rejected, &doc, &evidence, &bindings).is_empty()
                || !preserves_related_cause(&repair.checks, &rejected) {
                return Err("纪要存在未完成的关键原话覆盖复核，已有结果保留。".into());
            }
            fixed.checks.retain(|row| !ids.contains(row.id()));
            fixed.checks.extend(repair.checks);
        }
        checked.checks.retain(|check| !selected.contains(check.id()));
        checked.checks.extend(fixed.checks);
    }
    let (additions, conflicts) = checked_additions(checked, &cues, &doc, facts, &evidence)?;
    trace[scan_index]["boundAdditions"] = json!(additions.len());
    trace[scan_index]["conflictingClaims"] = json!(conflicts);
    Ok(CheckedOmissions { doc: append_missing(additions, doc, units, &evidence)?, conflicts })
}

pub(super) fn generate(endpoint: &str, model: &str, key: &str, client: &reqwest::blocking::Client,
    units: &[Unit], start: Instant, trace: &mut Vec<Value>) -> Result<(Document, Vec<Fact>), String>
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
    Ok((doc, facts))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn background_recheck_accepts_explanatory_metadata_and_keeps_required_fields() {
        let raw = r#"{"checks":[{"evidence":"e0249","id":"v000","status":"background","reason":"只是说明付出的时间。"}]}"#;
        let parsed: MissingItems = parse(raw).unwrap();
        assert_eq!(parsed.checks[0].id(), "v000");
        assert!(parsed.additions.is_empty());
        assert!(parse::<MissingItems>(r#"{"checks":[{"id":"v000","status":"missing","note":"三个月。"}]}"#).is_err());
    }

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
        let additions = parse::<MissingItems>(&raw).unwrap().additions;
        let enriched = append_missing(additions, doc.clone(), &units, &evidence).unwrap();
        assert_eq!(enriched.topics[0].points[0].text, doc.topics[0].points[0].text);
        assert_eq!(enriched.topics[0].details.len(), 1);
        assert_eq!(enriched.topics[0].details[0].text, "运动服预算未通过。");
        assert_eq!(enriched.action_items[0].due.as_deref(), Some("周五前"));
        let invalid = parse::<MissingItems>(&raw.replace("e0002","e9999")).unwrap().additions;
        assert!(append_missing(invalid, doc, &units, &evidence).is_err());
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
    fn checked_cues_preserve_the_other_fact_in_an_already_cited_sentence() {
        let units = vec![Unit{id:"u000".into(),text:"客户多是附近学生，学校有三个月假期。试营安排三个月。".into()}];
        let evidence = factual_audit::evidence_sentences(&units);
        let facts = vec![
            Fact {id:"a000".into(), kind:Kind::Status, placement:Placement::Topic, text:"顾客以学生为主。".into(),
                owner:None, due:None, evidence:vec!["e0000".into()]},
            Fact {id:"a001".into(), kind:Kind::Status, placement:Placement::Topic, text:"先试营三个月。".into(),
                owner:None, due:None, evidence:vec!["e0001".into()]},
        ];
        let doc: Document = serde_json::from_value(json!({"purpose":"餐饮讨论",
            "topics":[{"title":"客流","points":[{"kind":"status","text":facts[0].text,"sources":["u000"]}],
                "details":[{"text":facts[1].text,"sources":["u000"]}]}],
            "decisions":[],"actionItems":[],"questions":[]})).unwrap();
        let cues = omission_cues(&facts, &evidence);
        assert_eq!(json!(cues), json!([{"id":"v000","evidence":"e0000","span":"三个月"}]));
        assert!(checked_additions(parse(r#"{"additions":[]}"#).unwrap(), &cues, &doc, &facts, &evidence).is_err());
        let false_coverage = parse(r#"{"checks":[{"id":"v000","status":"covered","claim":"topics[0].points[0]"}],"additions":[]}"#).unwrap();
        assert_eq!(disputed_coverage(&false_coverage, &cues, &doc, &evidence, &HashMap::new()).len(), 1);
        assert!(checked_additions(false_coverage, &cues, &doc, &facts, &evidence).is_err());
        assert!(measure_has_witness("三个月", &json!({"text":"3个月假期"})));
        assert!(!measure_has_witness("三个月", &json!({"text":"13个月假期"})));
        assert!(measure_has_witness("六万块钱", &json!({"text":"前期投入约６万元"})));
        let yearly = "对方每年一年两两季都要设计服装，不能从一年级穿到六年级。";
        assert!(contextual_measure_witness("一年", &json!({"text":"对方每年两季要设计服装。"}), yearly));
        assert!(contextual_measure_witness("六年", &json!({"text":"随学生年级变化重新设计。"}), yearly));
        assert!(!contextual_measure_witness("一年", &json!({"text":"每年做三季。"}), "一年两季要重做。"));
        assert!(!contextual_measure_witness("一年", &json!({"text":"每年两季。"}), "合同暂签一年。"));
        let reply = json!({"checks":[{"id":"v000","status":"missing","addition":{
                "topic":"客流","item":{"role":"status","text":"学校约有三个月假期。","evidence":["e0000"]}}}],
            "additions":[{"topic":"客流","item":{"role":"status","text":"附近学生是主要顾客。","evidence":["e0000"]}}]});
        let (additions, conflicts) = checked_additions(parse(&reply.to_string()).unwrap(), &cues, &doc, &facts, &evidence).unwrap();
        assert!(conflicts.is_empty());
        assert_eq!(additions.len(), 1);
        let checked = append_missing(additions, doc, &units, &evidence).unwrap();
        assert_eq!(checked.topics[0].details.last().unwrap().text, "学校约有三个月假期。");
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
