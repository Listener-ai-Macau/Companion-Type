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
const FACT_LIMIT: usize = super::SOURCE_ITEMS_FACT_LIMIT;
pub(super) const DETAILS_LIMIT: usize = super::SOURCE_ITEMS_DETAILS_LIMIT;

pub(super) fn enabled() -> bool {
    std::env::var("COMPANION_TYPE_MINUTES_SOURCE_ITEMS").as_deref() == Ok("1")
}

#[derive(Clone, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
enum Role {
    #[serde(alias = "condition")]
    Status,
    Requirement,
    Opinion,
    Example,
    #[serde(alias = "suggestion")]
    Recommendation,
    Forecast,
    Decision,
    Action,
    Question,
}

impl Role {
    fn category(self) -> (Kind, Placement) {
        match self {
            Self::Status | Self::Requirement => (Kind::Status, Placement::Topic),
            Self::Opinion | Self::Example => (Kind::Opinion, Placement::Topic),
            Self::Recommendation => (Kind::Recommendation, Placement::Topic),
            Self::Forecast => (Kind::Forecast, Placement::Topic),
            Self::Decision => (Kind::Decision, Placement::Decision),
            Self::Action => (Kind::Decision, Placement::Action),
            Self::Question => (Kind::Status, Placement::Question),
        }
    }
}

#[derive(Clone, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub(super) struct SourceItem {
    role: Role,
    pub(super) text: String,
    pub(super) evidence: Vec<String>,
    pub(super) owner: Option<String>,
    pub(super) due: Option<String>,
}

impl SourceItem {
    pub(super) fn attributed_opinion(text: String, evidence: Vec<String>) -> Self {
        Self { role: Role::Opinion, text, evidence, owner: None, due: None }
    }

    pub(super) fn is_action(&self) -> bool { matches!(self.role, Role::Action) }

    pub(super) fn bind(self, known: &HashMap<&str, &Value>, known_ids: &HashSet<&str>) -> Result<Fact, String> {
        let stated_requirement = matches!(self.role, Role::Requirement);
        let illustration = matches!(self.role, Role::Example);
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
        let owner = self.owner.as_ref().filter(|owner| line(owner, 80) && snippets.iter()
            .any(|text| normalized(text).contains(&normalized(owner)))).cloned();
        let (text, owner, due) = if placement == Placement::Action {
            let owner = owner.or_else(|| self.owner.as_deref().filter(|owner| line(owner, 80))
                .and_then(|owner| evidence.iter().find_map(|id| {
                    super::commitments::owner_as_spoken(owner, known[id.as_str()])
                })));
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
        let text = if illustration {
            let markers = ["举例", "比如", "例如", "设例", "假如", "假设", "如果"];
            if !snippets.iter().any(|quote| markers.iter().any(|marker| quote.contains(marker))) {
                return Err("纪要例子缺少原话支持，已有结果保留。".into());
            }
            let text = if markers.iter().any(|marker| text.contains(marker)) {
                text
            } else {
                format!("会上举例，{text}")
            };
            if !line(&text, 90) {
                return Err("纪要例子格式不完整，已有结果保留。".into());
            }
            text
        } else if stated_requirement && !text.starts_with("会上") {
            let reported = format!("会上提出：{text}");
            if !line(&reported, 90) {
                return Err("纪要事项格式不完整，已有纪要和原文保留。".into());
            }
            reported
        } else { text };
        Ok(Fact {id: String::new(), kind, placement, text, owner, due, evidence})
    }
}

fn completed_report(summary: &str, snippets: &[&str]) -> bool {
    static REPORTED: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:已(?:经)?|此前已|曾经)(?:专门|统一|共同|集中|正式|顺利|及时)?(?P<work>开会|召开|完成|提交|发放|交付|安装|通知|培训)"
    ).unwrap());
    static FINISHED: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:开会|召开|完成|提交|发放|交付|安装|通知|培训)了|开{1,3}了(?:一|个|场|次|专|[\s，,]){0,12}[^。！？；\n]{0,8}会"
    ).unwrap());
    let head = summary.split(['，', ',', '；', '。']).next().unwrap_or_default();
    let head = normalized(head);
    let Some(work) = REPORTED.captures(&head).and_then(|matched| matched.name("work")) else { return false; };
    if ["会后", "后续", "接下来", "下一步", "以后", "下周", "继续", "还要", "另需", "另行"]
        .iter().any(|marker| summary.contains(marker)) {
        return false;
    }
    snippets.iter().any(|text| {
        let text = normalized(text);
        REPORTED.captures_iter(&text).any(|matched| matched.name("work").is_some_and(|found| found.as_str() == work.as_str()))
            || FINISHED.find_iter(&text).any(|found| {
                let position = found.start();
                let prefix = &text[..position];
                !prefix.ends_with(['不', '没', '未'])
                    && (found.as_str().starts_with(work.as_str())
                        || (matches!(work.as_str(), "开会" | "召开") && found.as_str().starts_with('开')))
            })
    })
}

fn contingent_closing(summary: &str, snippets: &[&str]) -> bool {
    summary.contains("有机会再")
        && snippets.iter().any(|text| text.contains("有机会再")
            && ["散会", "先到这儿", "先到这里"].iter().any(|closing| text.contains(closing)))
        && !snippets.iter().any(|text| ["会后由", "明确安排", "定在", "确定在", "务必"]
            .iter().any(|cue| text.contains(cue)))
}

fn reported_context(summary: &str, evidence: &[&Value]) -> Option<String> {
    let speaker = |row: &Value| row["turnSpeaker"].as_str().map(str::to_owned)
        .or_else(|| row["text"].as_str().and_then(super::super::source_resolution::split_turn_label)
            .map(|(who, _)| who.to_owned()));
    let opening: String = summary.split(['，', '。', '；']).next()?.chars().take(32).collect();
    let attributed = ["表示", "认为", "说明", "解释", "举例", "指出", "提到", "担心", "倾向", "称"]
        .iter().any(|cue| opening.contains(cue));
    for row in evidence {
        let source = row["text"].as_str().unwrap_or_default();
        if let Some(example) = super::source_coverage::corrected_example(source, summary) {
            let who = speaker(row).unwrap_or_else(|| "发言人".into());
            let quote = format!("{who}举例时说「{example}」，该示例口径待核实。");
            if !line(&quote, 90) { continue; }
            let combined = summary.split_once('；').map(|(_, other)| format!("{quote}{other}"));
            return Some(combined.filter(|text| line(text, 90)).unwrap_or(quote));
        }
    }
    let interpreted = ["构成", "属于", "责任", "最高判", "以为", "规定", "依据", "违法", "判定"]
        .iter().any(|cue| summary.contains(cue));
    if attributed || !interpreted || !evidence.iter().any(|row| {
        ["我举个例子", "比如说", "假如说", "如果说", "我觉得", "我认为", "给大家普及", "法条上写"]
            .iter().any(|cue| row["text"].as_str().is_some_and(|text| text.contains(cue)))
    }) {
        return None;
    }
    let mut speakers = evidence.iter().filter(|row| {
        !["是不是", "对不对", "你觉得", "？", "?"].iter()
            .any(|cue| row["text"].as_str().is_some_and(|text| text.trim_end().ends_with(cue)))
    }).filter_map(|row| speaker(row));
    let who = speakers.next()?;
    if speakers.any(|other| other != who) || summary.starts_with(&who) { return None; }
    let text = format!("{who}称，{summary}");
    line(&text, 90).then_some(text)
}

fn live_request_topic(fact: &Fact, evidence: &[Value]) -> Option<String> {
    if fact.due.is_some() || fact.owner.is_some() || fact.evidence.len() != 1 {
        return None;
    }
    let index = evidence.iter().position(|row| row["id"] == fact.evidence[0].as_str())?;
    let mut nearby = evidence[index..].iter().take(3);
    let question = nearby.next().and_then(|row| row["text"].as_str()).unwrap_or_default();
    let question = super::super::source_resolution::split_turn_label(question)
        .map_or(question, |(_, words)| words).trim();
    let ask = question.replace(['嗯', '呃', '啊', ' '], "");
    if !["想让", "想请", "我想问", "能不能", "可不可以"].iter().any(|cue| ask.contains(cue))
        || ["会后", "以后", "回去", "下周", "接下来", "下一次", "另约", "到时候"]
            .iter().any(|cue| question.contains(cue))
        || question.contains(['「', '」'])
    {
        return None;
    }
    let same_explanation = [
        (["科普", "普及"], ["科普", "普及"]),
        (["解释", "讲解"], ["解释", "讲解"]),
        (["说一下", "说明"], ["说一下", "说明"]),
    ].iter().any(|(asked, answered)| {
        asked.iter().any(|cue| question.contains(cue)) && asked.iter().any(|cue| fact.text.contains(cue))
            && nearby.clone().filter_map(|row| row["text"].as_str()).any(|text|
                answered.iter().any(|cue| text.contains(cue))
                    && ["我来", "给大家", "给你", "我先", "是这样"].iter().any(|cue| text.contains(cue)))
    });
    if !same_explanation { return None; }
    let text = format!("会上有人请发言人说明，原话为「{}」。", question.trim_end_matches(['。', '？', '！']));
    line(&text, 90).then_some(text)
}

fn answered_question(summary: &str, cited: &[&Value]) -> bool {
    static EXCHANGE: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:询问|追问|质疑|问)(?P<question>[^。！？]{2,}?)\s*(?:回答|答称|答道|答因|回应|确认|认为|解释|说明|答)(?P<answer>[^。！？；]+)"
    ).unwrap());
    const STILL_OPEN: &[&str] = &[
        "待确认", "待核实", "待核对", "待决定", "待答复", "未确定", "未确认", "不确定", "没确定",
        "未回答", "尚未", "暂不能", "还不清楚", "需进一步", "仍需", "还需", "核实后", "确认后", "会后再",
    ];
    let Some(exchange) = EXCHANGE.captures(summary) else { return false; };
    if STILL_OPEN.iter().any(|word| summary.contains(word)) { return false; }
    let overlaps = |part: &str, quote: &str, width: usize| {
        let part: Vec<_> = normalized(part).chars().collect();
        let quote = normalized(quote);
        part.windows(width).any(|segment| segment.iter().all(|ch| ch.is_alphanumeric())
            && quote.contains(&segment.iter().collect::<String>()))
    };
    let turns: Vec<_> = cited.iter().filter_map(|row| {
        let text = row["text"].as_str()?;
        let (label, words) = super::super::source_resolution::split_turn_label(text)
            .or_else(|| row["turnSpeaker"].as_str().map(|speaker| (speaker, text)))?;
        Some((row["id"].as_str()?, label, words.trim()))
    }).collect();
    turns.iter().any(|(asked_id, asked_by, question)| {
        let interrogative = question.contains(['?', '？'])
            || ["为什么", "为何", "有没有", "是不是", "是否", "怎么", "有什么", "哪些"].iter().any(|word| question.contains(word));
        interrogative && overlaps(&exchange["question"], question, 2)
            && turns.iter().any(|(answered_id, answered_by, reply)| {
                asked_id < answered_id && asked_by != answered_by && !reply.ends_with(['?', '？'])
                    && !STILL_OPEN.iter().any(|word| reply.contains(word))
                    && overlaps(&exchange["answer"], reply, 4)
            })
    })
}

fn live_agenda(fact: &Fact, quotes: &[&str]) -> bool {
    static ORDER: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:咱们?|我们|现在|当前|这场会|这次会)[^。！？；，]{0,12}?先(?:先|不|集中|只)*(?:说|谈|讨论|问|汇报|听|介绍)"
    ).unwrap());
    static DEFER: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"一会儿?(?:再|在)(?:说|谈|讨论|问|汇报|听|介绍)"
    ).unwrap());
    let summary = normalized(&fact.text);
    const BINDING: &[&str] = &["会后", "散会后", "下周", "明天", "下次会议", "决定由", "董事会决定",
        "正式决定", "同意执行", "达成一致", "明确通过", "定于", "最迟", "截止"];
    if fact.due.is_some() || BINDING.iter().any(|word|
        summary.contains(word) || quotes.iter().any(|quote| normalized(quote).contains(word)))
    {
        return false;
    }
    match fact.placement {
        Placement::Decision => {
            let about_discussion = ["当前先", "现在先", "先集中讨论", "先讨论", "暂不讨论",
                "先问", "先谈", "先听", "先请"].iter().any(|marker| summary.contains(marker));
            about_discussion && quotes.iter().any(|quote| {
                let quote = normalized(quote);
                ORDER.is_match(&quote) || (DEFER.is_match(&quote)
                    && ["你就说", "刚才", "现在", "先", "接着"].iter().any(|cue| quote.contains(cue)))
            })
        }
        Placement::Action => {
            let opening = ["召开", "开一场", "举行"].iter().any(|cue| summary.starts_with(cue))
                && summary.contains('会') && ["先讨论", "先谈", "先听"].iter().any(|cue| summary.contains(cue));
            opening && quotes.iter().any(|quote| {
                let quote = normalized(quote);
                ["叫过来", "把大家叫来", "把大家聚到一起"].iter().any(|cue| quote.contains(cue))
                    && ["开一个", "开个会", "开这场"].iter().any(|cue| quote.contains(cue))
                    && ORDER.is_match(&quote)
            })
        }
        _ => false,
    }
}

fn reconcile_spoken_scope(facts: &mut [Fact], evidence: &[Value]) -> Vec<String> {
    let by_id: HashMap<_, _> = evidence.iter().filter_map(|row|
        Some((row["id"].as_str()?, row))).collect();
    let mut changed = Vec::new();
    for fact in facts {
        let rows: Vec<_> = fact.evidence.iter().filter_map(|id| by_id.get(id.as_str()).copied()).collect();
        let quotes: Vec<_> = rows.iter().filter_map(|row| row["text"].as_str()).collect();
        let result = match fact.placement {
            Placement::Decision | Placement::Action if live_agenda(fact, &quotes) => Some((Kind::Status, None)),
            Placement::Action if fact.due.is_none() && completed_report(&fact.text, &quotes) =>
                Some((Kind::Status, None)),
            Placement::Action => live_request_topic(fact, evidence).map(|text| (Kind::Opinion, Some(text))),
            Placement::Decision if contingent_closing(&fact.text, &quotes) =>
                Some((Kind::Recommendation, None)),
            Placement::Question if answered_question(&fact.text, &rows) => Some((Kind::Opinion, None)),
            Placement::Topic if matches!(fact.kind, Kind::Status | Kind::Opinion) =>
                reported_context(&fact.text, &rows).map(|text| (Kind::Opinion, Some(text))),
            _ => None,
        };
        let Some((kind, text)) = result else { continue; };
        fact.kind = kind;
        fact.placement = Placement::Topic;
        fact.owner = None;
        fact.due = None;
        if let Some(text) = text { fact.text = text; }
        changed.push(fact.id.clone());
    }
    changed
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

impl MissingItems {
    fn coalesce_identical_checks(&mut self, claim_paths: &HashSet<&str>) -> usize {
        let count = self.checks.len();
        let mut unique = Vec::with_capacity(count);
        for mut check in self.checks.drain(..) {
            check.normalize_claim_path(claim_paths);
            // Equal repeats contribute no new evidence. Unequal verdicts
            // for one ID stay separate and fail the existing scope checks.
            if !unique.contains(&check) {
                unique.push(check);
            }
        }
        self.checks = unique;
        count - self.checks.len()
    }

    fn defer_unrequested_omissions(&mut self, expected: &HashSet<&str>) -> Vec<String> {
        let mut requested = HashSet::new();
        let mut deferred = Vec::new();
        for check in &self.checks {
            if expected.contains(check.id()) {
                if !requested.insert(check.id()) { return Vec::new(); }
            } else if matches!(check, SourceCheck::Missing { .. }) {
                deferred.push(check.id().to_owned());
            } else {
                return Vec::new();
            }
        }
        if &requested != expected || deferred.is_empty() {
            return Vec::new();
        }
        // A free candidate cannot expand the coverage contract or become a
        // certified decision. Its original content stays in the scan receipt.
        self.checks.retain(|check| expected.contains(check.id()));
        deferred
    }
}

#[cfg(test)]
#[test]
fn identical_source_checks_are_idempotent_but_conflicting_verdicts_stay_separate() {
    let addition = json!({"id":"v013","status":"missing","addition":{"topic":null,
        "item":{"role":"action","text":"演练前先检查消防设备。","evidence":["e0164"],"owner":"安保部","due":null}}});
    let contrary = json!({"id":"v013","status":"background","reason":"原话没有具体行动。"});
    let raw = json!({"checks":[addition.clone(),addition,contrary]}).to_string();
    let mut results: MissingItems = parse(&raw).unwrap();
    assert_eq!(results.coalesce_identical_checks(&HashSet::new()), 1);
    assert_eq!(results.checks.len(), 2);
    assert_eq!(results.checks[0].id(), results.checks[1].id());
}

#[cfg(test)]
#[test]
fn surplus_omission_keeps_the_requested_checks_without_certifying_an_extra_decision() {
    let numbered = json!({"id":"v000","status":"background","reason":"会议开场的当场流程。"});
    let outside = json!({"id":"v001","status":"missing","addition":{"topic":null,
        "item":{"role":"decision","text":"必须延后演练。","evidence":["e0010"],"owner":null,"due":null}}});
    let expected = HashSet::from(["v000"]);
    let packet = json!({"checks":[numbered.clone(),outside.clone()],"additions":[]});
    let mut checked: MissingItems = parse(&packet.to_string()).unwrap();
    assert_eq!(checked.defer_unrequested_omissions(&expected),["v001"]);
    assert_eq!(checked.checks[0].id(),"v000");
    assert_eq!(checked.checks.len(),1);
    assert!(checked.additions.is_empty());

    let missing_expected = json!({"checks":[outside.clone()]});
    let mut checked: MissingItems = parse(&missing_expected.to_string()).unwrap();
    assert!(checked.defer_unrequested_omissions(&expected).is_empty());
    assert_eq!(checked.checks[0].id(),"v001");

    let contrary = json!({"id":"v000","status":"covered","claim":"purpose"});
    let conflict = json!({"checks":[numbered,contrary,outside]});
    let mut checked: MissingItems = parse(&conflict.to_string()).unwrap();
    assert!(checked.defer_unrequested_omissions(&expected).is_empty());
    assert_eq!(checked.checks.len(),3);
}

#[derive(Deserialize, PartialEq)]
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
    #[serde(skip_serializing_if = "Option::is_none")]
    aspect: Option<&'static str>,
}

#[derive(Deserialize, PartialEq)]
#[serde(tag = "status", rename_all = "camelCase")]
enum SourceCheck {
    Covered { id: String, #[serde(deserialize_with = "claim_path")] claim: String, #[serde(default)] proof: Option<CoverageProof> },
    Missing { id: String, addition: MissingItem },
    NeedsReview { id: String, addition: MissingItem },
    Conflict { id: String, #[serde(deserialize_with = "claim_path")] claim: String },
    Background { id: String, reason: String },
}

fn claim_path<'de, D: serde::Deserializer<'de>>(decoder: D) -> Result<String, D::Error> {
    #[derive(Deserialize)]
    #[serde(untagged)]
    enum Locator {
        Path(String),
        Claim { path: String },
    }
    Ok(match Locator::deserialize(decoder)? {
        Locator::Path(path) | Locator::Claim { path } => path,
    })
}

#[derive(Deserialize, PartialEq)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct CoverageProof {
    source_quote: String,
    statement_quote: String,
}

impl SourceCheck {
    fn normalize_claim_path(&mut self, claims: &HashSet<&str>) {
        let (Self::Covered { claim, .. } | Self::Conflict { claim, .. }) = self else { return; };
        if claims.contains(claim.as_str()) {
            return;
        }
        if let Some(base) = claim.strip_suffix(".text").filter(|base| claims.contains(base)) {
            *claim = base.to_owned();
        }
    }

    fn id(&self) -> &str {
        match self {
            Self::Covered { id, .. } | Self::Missing { id, .. } | Self::NeedsReview { id, .. }
            | Self::Conflict { id, .. } | Self::Background { id, .. } => id,
        }
    }
}

fn background_reason(span: &str, source: &str) -> Option<&'static str> {
    let occurrences: Vec<_> = source.match_indices(span).collect();
    if occurrences.is_empty() {
        return None;
    }
    let retrospective = ["一年", "一季度", "一个月"].contains(&span)
        && occurrences.iter().all(|(at, _)| {
            let lead = &source[..*at];
            let rest = &source[at + span.len()..];
            lead.ends_with(['上', '去'])
                && ["情况来讲", "情况来看", "工作情况来说", "工作情况来讲"]
                    .iter().any(|marker| rest.trim_start().starts_with(marker))
        });
    if retrospective {
        return Some("这处数字位于原话回顾情况的引子，未给出新的执行时限。");
    }
    let illustration = ["举例", "例如", "比如", "像一些", "比方说"]
        .iter().any(|marker| source.contains(marker));
    let requires_action = ["会上决定", "请你", "必须", "负责", "最晚", "截止", "务必"]
        .iter().any(|marker| source.contains(marker));
    if illustration && !requires_action && source.trim_end().ends_with(['?', '？'])
        && occurrences.iter().all(|(at, _)| {
            let lead = &source[..*at];
            ["会不会", "能不能", "可不可以"].iter().any(|marker| lead.contains(marker))
                && lead.contains("或者") && measures(span).any(|(_, unit)| matches!(unit, "个月" | "周" | "天" | "年"))
        })
    {
        return Some("原话用可选时段举例提问，没有确定这个时长。");
    }
    None
}

fn remove_surplus_check_brace(raw: &str) -> Option<String> {
    let unfenced = super::super::strip_code_fences(raw);
    let body = unfenced.trim();
    let bytes = body.as_bytes();
    let mut containers = Vec::new();
    let mut in_string = false;
    let mut escape = false;
    let mut surplus = None;
    for (at, byte) in bytes.iter().copied().enumerate() {
        if in_string {
            if escape { escape = false; }
            else if byte == b'\\' { escape = true; }
            else if byte == b'"' { in_string = false; }
            continue;
        }
        match byte {
            b'"' => in_string = true,
            b'{' | b'[' => containers.push(byte),
            b']' => { if containers.pop() != Some(b'[') { return None; } },
            b'}' if containers.last() == Some(&b'{') => { containers.pop(); },
            b'}' if containers.last() == Some(&b'[') => {
                let prior = bytes[..at].iter().rev().find(|byte| !byte.is_ascii_whitespace());
                let next = bytes[at + 1..].iter().find(|byte| !byte.is_ascii_whitespace());
                if prior != Some(&b'}') || !matches!(next, Some(b']' | b','))
                    || surplus.replace(at).is_some()
                {
                    return None;
                }
            },
            b'}' => return None,
            _ => (),
        }
    }
    let at = surplus?;
    if in_string || !containers.is_empty() { return None; }
    let repaired = format!("{}{}", &body[..at], &body[at + 1..]);
    let syntax: Value = serde_json::from_str(&repaired).ok()?;
    syntax["checks"].is_array().then_some(repaired)
}

fn move_last_check_brace(raw: &str) -> Option<String> {
    let unfenced = super::super::strip_code_fences(raw);
    let body = unfenced.trim();
    let error = serde_json::from_str::<Value>(body).err()?;
    if !error.is_syntax() { return None; }
    let line_offset = body.split_inclusive('\n').take(error.line().checked_sub(1)?)
        .map(str::len).sum::<usize>();
    let at = line_offset + error.column().checked_sub(1)?;
    // A fully present final row can have its closing brace placed just
    // outside the checks array. No text, IDs or verdicts may be synthesized.
    if !body.get(..at)?.trim_end().ends_with('}') { return None; }
    let suffix = body.get(at..)?.strip_prefix(']')?.trim_start().strip_prefix('}')?;
    let following = suffix.trim_start().strip_prefix(',')?.trim_start();
    if !following.starts_with("\"additions\"") { return None; }
    let repaired = format!("{}}}]{suffix}", &body[..at]);
    let packet: Value = serde_json::from_str(&repaired).ok()?;
    let expected_shape = packet["checks"].as_array()?.last()?;
    matches!(expected_shape["status"].as_str(), Some("missing" | "needsReview"))
        .then_some(repaired)
}

fn normalize_check_delimiter(raw: &str) -> Option<(String, &'static str)> {
    move_last_check_brace(raw).map(|value| (value, "movedLastCheckBrace"))
        .or_else(|| remove_surplus_check_brace(raw).map(|value| (value, "removedSurplusCheckBrace")))
}

fn parse_source_check_packet(
    raw: &str, expected: &HashSet<&str>, call: &mut Value,
) -> Result<MissingItems, String> {
    let error = match parse(raw) {
        Ok(items) => return Ok(items),
        Err(error) => error,
    };
    let Some((candidate, operation)) = normalize_check_delimiter(raw) else { return Err(error); };
    let items: MissingItems = parse(&candidate).map_err(|_| error.clone())?;
    let returned: HashSet<_> = items.checks.iter().map(SourceCheck::id).collect();
    if &returned != expected || items.checks.len() != expected.len() {
        return Err(error);
    }
    call[operation] = json!(true);
    Ok(items)
}

#[cfg(test)]
#[test]
fn source_scan_moves_only_the_last_present_checks_close() {
    let raw = r#"{
        "checks":[{"id":"v000","status":"missing","addition":{"topic":null,
        "item":{"role":"status","text":"消防设备已检修。","evidence":["e0018"],"owner":null,"due":null}}]},
        "additions":[]
    }"#;
    let mut trace = json!({});
    let expected = HashSet::from(["v000"]);
    let repaired = parse_source_check_packet(raw, &expected, &mut trace).unwrap();
    assert_eq!(trace["movedLastCheckBrace"], true);
    assert!(matches!(&repaired.checks[0], SourceCheck::Missing { addition, .. }
        if addition.item.text == "消防设备已检修。" && addition.item.evidence == ["e0018"]));
    assert!(parse_source_check_packet(raw, &HashSet::from(["v001"]), &mut json!({})).is_err());
    assert!(parse_source_check_packet(&raw.replace("}}]},", "}]},"),
        &expected, &mut json!({})).is_err());
}

fn parse_coverage_repair(raw: &str, expected: &[Value], evidence: &[Value]) -> Result<(MissingItems, usize), String> {
    let initial = match parse::<MissingItems>(raw) {
        Ok(items) => return Ok((items, 0)),
        Err(error) => error,
    };
    let mut packet: Value = serde_json::from_str(super::super::strip_code_fences(raw).trim())
        .map_err(|_| initial.clone())?;
    let rows = packet["checks"].as_array_mut().ok_or_else(|| initial.clone())?;
    let mut restored = 0;
    for row in rows {
        if row["status"] != "background" || !row["reason"].is_null()
            || !row["addition"].is_null() || !row["claim"].is_null()
        {
            continue;
        }
        let Some(expected) = expected.iter().find(|entry| entry["cue"]["id"] == row["id"]
            && entry["cue"]["id"].is_string() && entry["cue"]["aspect"].is_null()) else { continue; };
        let Some(span) = expected["cue"]["span"].as_str() else { continue; };
        let Some(text) = evidence.iter().find(|source| source["id"] == expected["cue"]["evidence"])
            .and_then(|source| source["text"].as_str()) else { continue; };
        if let Some(reason) = background_reason(span, text) {
            row["reason"] = json!(reason);
            restored += 1;
        }
    }
    if restored == 0 { return Err(initial); }
    parse(&packet.to_string()).map(|items| (items, restored))
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
    context: Vec<Fact>,
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
        let mut neighbors = Vec::new();
        for answer in extraction.units {
            if !unit_ids.contains(answer.id.as_str()) {
                return Err(missing());
            }
            if !primary.contains(answer.id.as_str()) {
                // This unit has its own primary request. The context copy
                // cannot produce a second set of competing facts.
                ignored_neighbors += 1;
                neighbors.push(answer);
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
        let context = neighbors.into_iter().flat_map(|SourceAnswer { id: unit, items }| {
            let (known, known_ids) = (&known, &known_ids);
            items.into_iter().filter_map(move |item| {
                let fact = item.bind(known, known_ids).ok()?;
                (fact.placement == Placement::Topic
                    && fact.evidence.iter().any(|id| known[id.as_str()]["source"] == unit)).then_some(fact)
            })
        }).take(FACT_LIMIT).collect();
        Ok(CheckedWindow { facts, context, ignored_neighbors, ignored_neighbor_only_items, normalized_topic_metadata })
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
    // Keep assigned details in their original section under the global fact
    // budget. Estimate a topic only for facts the organizer left unassigned.
    let restored: Vec<_> = facts.iter().filter(|fact| fact.placement == Placement::Topic && !used.contains(&fact.id))
        .map(|fact| fact.id.clone()).collect();
    for id in &restored {
        let index = order[id.as_str()];
        let topic = layout.topics.iter_mut().filter(|topic| topic.details.len() < DETAILS_LIMIT)
            .min_by_key(|topic| topic.points.iter().chain(&topic.details)
                .map(|item| order[item.as_str()].abs_diff(index)).min().unwrap_or(usize::MAX))
            .ok_or_else(fail)?;
        topic.details.push(id.clone());
    }
    Ok(json!({"restoredTopicIds":restored,"movedToDetails":moved}))
}

fn organize(raw: &str, facts: &[Fact], units: &[Unit], context: &[Fact]) -> Result<(Document, Value, Vec<Fact>), String> {
    let mut layout: Layout = parse(raw)?;
    let evidence = super::commitments::with_turn_labels(&factual_audit::evidence_sentences(units));
    let bindings = super::source_bindings::SourceBindings::new(&evidence);
    let mut facts = facts.to_vec();
    let renamed: Vec<_> = facts.iter_mut().filter_map(|fact| {
        bindings.correct_attribution(fact).map(|(before, after)| (fact.id.clone(), before, after))
    }).collect();
    let split = bindings.split_assignments(&mut facts);
    let roles = super::source_coverage::preserve_spoken_roles(&mut facts, &evidence);
    let bridged_assignments = super::source_coverage::bind_nearby_assignment(&mut facts, &evidence);
    let cited_details = super::source_coverage::retain_cited_details(&mut facts, &evidence);
    let assignment_dialogue = super::source_coverage::retain_assignment_dialogue(&mut facts, &evidence, &bindings);
    let contextual_schedule = super::source_coverage::retain_context_schedule(&mut facts, context, &evidence);
    let host = super::source_coverage::retain_opening_host(&mut layout.purpose, &evidence, &bindings);
    let separated = retain_requests_before_questions(&mut facts, &evidence);
    let source_by_id: HashMap<_, _> = evidence.iter().map(|row| {
        (row["id"].as_str().unwrap(), row["text"].as_str().unwrap())
    }).collect();
    let payment_ranges = facts.iter_mut().filter_map(|fact| {
        let sources = fact.evidence.iter().map(|id| source_by_id[id.as_str()]);
        let corrected = retain_payment_extent(&fact.text, sources)?;
        fact.text = corrected;
        Some(fact.id.clone())
    }).collect::<Vec<_>>();
    let tentative_dates = facts.iter_mut().filter_map(|fact| {
        let sources = fact.evidence.iter().map(|id| source_by_id[id.as_str()]);
        let corrected = super::source_coverage::preserve_tentative_date(&fact.text, sources)?;
        fact.text = corrected;
        Some(fact.id.clone())
    }).collect::<Vec<_>>();
    let limits = super::source_coverage::restore_cited_limits(&mut facts, &evidence);
    let delivery_scopes = super::source_coverage::restore_delivery_scope(&mut facts, &evidence);
    let spoken_scope = reconcile_spoken_scope(&mut facts, &evidence);
    let corrected_scope = super::source_corrections::correct(&mut facts, &evidence);
    let mut projection = complete_layout(&mut layout, &facts)?;
    let mut moved = Vec::new();
    for (id, before, after) in &renamed {
        let current = layout.topics.iter().position(|topic| {
            topic.title.starts_with(before) && topic.points.iter().chain(&topic.details).any(|item| item == id)
        });
        let correct = layout.topics.iter().position(|topic| topic.title.starts_with(after) && topic.details.len() < DETAILS_LIMIT);
        let (Some(current), Some(correct)) = (current, correct) else { continue; };
        if current == correct {
            continue;
        }
        let topic = &mut layout.topics[current];
        topic.points.retain(|item| item != id);
        topic.details.retain(|item| item != id);
        if topic.points.is_empty() && !topic.details.is_empty() {
            topic.points.push(topic.details.remove(0));
        }
        layout.topics[correct].details.push(id.clone());
        moved.push(id.clone());
    }
    layout.topics.retain(|topic| !topic.points.is_empty());
    let details: HashSet<_> = layout.topics.iter().flat_map(|topic| &topic.details).collect();
    let mut marked = Vec::new();
    for fact in &mut facts {
        if details.contains(&fact.id) && super::source_bindings::mark_proposal(fact) {
            marked.push(fact.id.clone());
        }
    }
    projection["sourceBindings"] = json!({"correctedAttributions":renamed,"movedToSpeakerTopic":moved,
        "priorProposalsMarked":marked,"splitAssignmentEvidence":split,
        "restoredSourceRoles":roles,"separateRequests":separated,"retainedLiteralLimits":limits,
        "retainedDeliveryScopes":delivery_scopes,"spokenScopeCorrections":spoken_scope});
    if !payment_ranges.is_empty() {
        projection["sourceBindings"]["retainedPaymentRanges"] = json!(payment_ranges);
    }
    if !corrected_scope.is_empty() {
        projection["sourceBindings"]["correctedExecutionAndRefundScope"] = json!(corrected_scope);
    }
    if !tentative_dates.is_empty() {
        projection["sourceBindings"]["retainedTentativeDates"] = json!(tentative_dates);
    }
    if !bridged_assignments.is_empty() {
        projection["sourceBindings"]["bridgedAssignments"] = json!(bridged_assignments);
    }
    if !cited_details.is_empty() {
        projection["sourceBindings"]["retainedCitedDetails"] = json!(cited_details);
    }
    if !assignment_dialogue.is_empty() {
        projection["sourceBindings"]["retainedAssignmentDialogue"] = json!(assignment_dialogue);
    }
    if !contextual_schedule.is_empty() {
        projection["sourceBindings"]["retainedContextSchedule"] = json!(contextual_schedule);
    }
    if let Some(host) = host {
        projection["sourceBindings"]["retainedOpeningHost"] = host;
    }
    let topics = layout.topics.iter().map(|topic| json!({"title":topic.title,
        "points":topic.points.iter().map(|id| [id]).collect::<Vec<_>>(),
        "details":topic.details.iter().map(|id| [id]).collect::<Vec<_>>()})).collect::<Vec<_>>();
    let placed = |placement| facts.iter().filter(|fact| fact.placement == placement)
        .map(|fact| [&fact.id]).collect::<Vec<_>>();
    let mapped = json!({"purpose":layout.purpose,"topics":topics,"decisions":placed(Placement::Decision),
        "actionItems":placed(Placement::Action),"questions":placed(Placement::Question),"excluded":[]});
    answer_layout::assemble_with_details_limit(&mapped.to_string(), &facts, units, DETAILS_LIMIT, FACT_LIMIT)
        .map(|assembled| (assembled.document, projection, facts))
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
        let mut fact = addition.item.bind(&known, &known_ids)?;
        if matches!(fact.placement, Placement::Decision | Placement::Action) {
            let quotes: Vec<_> = fact.evidence.iter()
                .filter_map(|id| known[id.as_str()]["text"].as_str()).collect();
            if live_agenda(&fact, &quotes) {
                fact.kind = Kind::Status;
                fact.placement = Placement::Topic;
                fact.owner = None;
                fact.due = None;
            }
        } else if fact.placement == Placement::Question {
            let rows: Vec<_> = fact.evidence.iter().map(|id| known[id.as_str()]).collect();
            if answered_question(&fact.text, &rows) {
                fact.kind = Kind::Opinion;
                fact.placement = Placement::Topic;
            }
        }
        let sources = fact.evidence.iter().map(|id| known[id.as_str()]["text"].as_str().unwrap());
        if let Some(corrected) = retain_payment_extent(&fact.text, sources.clone()) {
            fact.text = corrected;
        }
        if let Some(corrected) = super::source_coverage::preserve_tentative_date(&fact.text, sources) {
            fact.text = corrected;
        }
        if fact.placement == Placement::Topic {
            super::source_bindings::mark_proposal(&mut fact);
        }
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

pub(super) fn restore_reported_steps(
    doc: &Document, facts: &[Fact], units: &[Unit], trace: &mut Vec<Value>,
) -> Result<Option<Document>, String> {
    let retained = doc.topics.iter().map(|topic| topic.points.len() + topic.details.len()).sum::<usize>()
        + doc.decisions.len() + doc.action_items.len() + doc.questions.len();
    let limit = FACT_LIMIT.saturating_sub(retained).min(3);
    if limit == 0 { return Ok(None); }

    let evidence = factual_audit::evidence_sentences(units);
    let by_id: HashMap<_, _> = evidence.iter()
        .filter_map(|row| Some((row["id"].as_str()?, row))).collect();
    let mut seen = HashSet::new();
    let mut steps = Vec::new();
    'facts: for fact in facts.iter().filter(|fact| fact.placement == Placement::Topic && matches!(fact.kind, Kind::Status)) {
        let Some(topic) = doc.topics.iter().find(|topic| {
            topic.points.iter().any(|point| point.text == fact.text)
                || topic.details.iter().any(|entry| entry.text == fact.text)
        }) else { continue; };
        for id in &fact.evidence {
            let Some(source) = by_id.get(id.as_str()).and_then(|row| row["text"].as_str()) else { continue; };
            let Some(step) = super::source_coverage::omitted_reported_step(source, &fact.text)
                else { continue; };
            if steps.len() == limit { break 'facts; }
            let compact = normalized(step).replace("就是进行", "").replace("就是", "");
            let meaning = compact.trim_start_matches("进行").trim_start_matches("采取")
                .trim_start_matches("开展").trim_start_matches("办理");
            if !seen.insert((id, step))
                || topic.points.iter().any(|entry| normalized(&entry.text).contains(meaning))
                || topic.details.iter().any(|entry| normalized(&entry.text).contains(meaning))
            {
                continue;
            }
            steps.push(MissingItem {
                item: SourceItem { role: Role::Status, text: format!("同一流程还提到「{step}」。"),
                    evidence: vec![id.clone()], owner: None, due: None },
                topic: Some(topic.title.clone()), new_aspect: None,
            });
        }
    }
    if steps.is_empty() { return Ok(None); }
    trace.push(json!({"stage":"source-reported-procedure-recovery","added":steps.iter()
        .map(|step| (&step.item.evidence, &step.item.text)).collect::<Vec<_>>() }));
    append_missing(steps, doc.clone(), units, &evidence).map(Some)
}

pub(super) fn ordinary_source_aspect(text: &str) -> Option<(&'static str, &str)> {
    static PROGRESS: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:逐步|陆续|逐渐)(?:在|进行|开始)?(?:打开|拓展|扩充|开展|推广|恢复|推进|应用|转向|转移)"
    ).unwrap());
    static DIRECTED: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:要|须|需要)(?:进行|开展|组织|协调|安排|核实|调查|准备)[^，,。！？；;\r\n]{2,20}"
    ).unwrap());
    let question = ["你觉得", "你看哪", "你认为哪", "我问的是", "请问"]
        .iter().filter_map(|cue| text.find(cue)).min();
    if let Some(before_question) = question.map(|start| &text[..start]) {
        if let Some(directed) = DIRECTED.find_iter(before_question).last() {
            let before = &before_question[..directed.start()];
            if !before.trim_end().ends_with(['不', '没', '勿']) {
                return Some(("交办后又提问", directed.as_str().trim()));
            }
        }
    }
    let hit = PROGRESS.find(text)?;
    let lead = &text[..hit.start()];
    let clause = lead.rsplit(['。', '！', '？', '；']).next()?.trim();
    if clause.chars().count() < 6 || ["是否", "能否", "能不能"].iter().any(|cue| clause.contains(cue)) {
        return None;
    }
    Some(("实际进展", hit.as_str()))
}

const QUANTITY: &str = r"[0-9０-９]+(?:[.．][0-9０-９]+)?[万亿]?|[零〇一二两三四五六七八九十百千万亿半]+";
const QUANTITY_UNIT: &str = r"美元|块钱|元|个月|季度|工作日|小时|分钟|周岁|岁|周|天|年|%|％";

fn omission_cues(facts: &[Fact], evidence: &[Value]) -> Vec<SourceCue> {
    static LITERAL: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(&format!(
        r"(?:{QUANTITY})\s*(?:{QUANTITY_UNIT})|(?:明天|后天|[本下]周[一二三四五六日]?|下个月|本月底|周[一二三四五六日])(?:之前|以前|截止|前|为止)"
    )).expect("constant omission cue expression"));
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
    let mut ordinary = Vec::new();
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
        if let Some((aspect, span)) = ordinary_source_aspect(text) {
            if !facts.iter().any(|fact| fact.evidence.iter().any(|e| e == id)
                && fact.placement != Placement::Question
                && normalized(&fact.text).contains(&normalized(span)))
            {
                ordinary.push((id, span, aspect));
            }
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
            cues.push(SourceCue { id: format!("v{:03}", cues.len()), evidence: evidence.into(), span: span.into(), aspect: None });
        }
    }
    let ordinary_count = ordinary.len().min(6);
    for index in 0..ordinary_count {
        let (evidence, span, aspect) = ordinary[index * ordinary.len() / ordinary_count];
        cues.push(SourceCue { id: format!("v{:03}", cues.len()), evidence: evidence.into(),
            span: span.into(), aspect: Some(aspect) });
    }
    for (evidence, span, aspect) in super::source_coverage::material_cues(facts, evidence) {
        if !cues.iter().any(|cue| cue.evidence == evidence && cue.span == span) {
            cues.push(SourceCue { id: format!("v{:03}", cues.len()), evidence, span, aspect: Some(aspect) });
        }
    }
    cues
}

#[cfg(test)]
#[test]
fn an_agenda_period_can_be_kept_in_the_purpose_without_a_title_as_evidence() {
    let source = "嗯今天呢把大家叫来，咱们就是对咱们健身中心上半年咱们的经营情况做一个简单的 呃汇报和总结，然后请各部门发言。";
    let quote = "咱们健身中心上半年咱们的经营情况做一个简单的 呃汇报和总结";
    let purpose = "各部门汇报上半年工作并讨论下半年安排。";
    assert!(opening_scope_is_retained(source, quote, purpose));
    assert!(!opening_scope_is_retained(source, quote, "各部门汇报下半年工作。"));
    assert!(!opening_scope_is_retained(source, "上半年提交客户报告", purpose));
    assert!(!opening_scope_is_retained(
        &format!("{source}另有新材料必须在上半年交付。"), quote, purpose));
    let raw = json!({"checks":[{"id":"v000","status":"covered","claim":"topics[0].title",
        "proof":{"sourceQuote":quote,"statementQuote":"教练团队与服务"}}]});
    let mut supplied: MissingItems = parse(&raw.to_string()).unwrap();
    let doc: Document = serde_json::from_value(json!({"purpose":purpose,"topics":[],
        "decisions":[],"actionItems":[],"questions":[]})).unwrap();
    let evidence = [json!({"id":"e0008","text":source})];
    let expected = [json!({"cue":{"id":"v000","evidence":"e0008","span":"半年"}})];
    assert_eq!(retain_opening_scope(&mut supplied.checks,&expected,&doc,&evidence),1);
    assert!(matches!(supplied.checks[0],SourceCheck::Background{..}));
    let mut supplied: MissingItems = parse(&raw.to_string()).unwrap();
    let amount = [json!({"cue":{"id":"v000","evidence":"e0008","span":"二万元"}})];
    assert_eq!(retain_opening_scope(&mut supplied.checks,&amount,&doc,&evidence),0);

    let source = "咱们今天把各部门儿叫过来，开个咱上半年的总结会议，接下来由副院长主持。";
    let mut doc = doc;
    doc.purpose = "院长召集会议并交由副院长主持。会议回顾上半年网课与经费情况。".into();
    let raw = json!({"checks":[{"id":"v000","status":"covered","claim":"purpose",
        "proof":{"sourceQuote":source,"statementQuote":"院长召集会议并交由副院长主持"}}]});
    let mut supplied: MissingItems = parse(&raw.to_string()).unwrap();
    let evidence = [json!({"id":"e0008","text":source})];
    assert_eq!(retain_opening_scope(&mut supplied.checks,&expected,&doc,&evidence),1);
    let mut supplied: MissingItems = parse(&raw.to_string()).unwrap();
    doc.purpose = doc.purpose.replace("回顾上半年","回顾下半年");
    assert_eq!(retain_opening_scope(&mut supplied.checks,&expected,&doc,&evidence),0);
}

#[cfg(test)]
#[test]
fn missing_background_reasons_are_restored_only_for_grounded_context() {
    let raw = r#"{"checks":[{"id":"v002","status":"background","addition":null},{"id":"v006","status":"background","addition":null}],"additions":[]}"#;
    let expected = [json!({"cue":{"evidence":"e0043","id":"v002","span":"一个月"}}),
        json!({"cue":{"evidence":"e0083","id":"v006","span":"一年"}})];
    let mut quotes = [json!({"id":"e0043","text":"像一些顾客会有一些憧憬，他会不会再一个星期或者一个月之内瘦掉几斤？"}),
        json!({"id":"e0083","text":"说话人3: 保安部话这边的话就是延上半期就是上一年情况来讲的话，对于这个保安人员的话，他不是就是"})];
    assert_eq!(parse_coverage_repair(raw, &expected, &quotes).unwrap().1,2);
    quotes[0]["text"] = json!("会上决定，请你一个月内提交初稿。");
    assert!(parse_coverage_repair(raw, &expected, &quotes).is_err());
    quotes[0]["text"] = json!("像一些顾客会有一些憧憬，他会不会再一个星期或者一个月之内瘦掉几斤？");
    assert!(parse_coverage_repair(raw, &expected[..1], &quotes).is_err());
    assert!(parse_coverage_repair(&raw.replace("null", r#"{"text":"擅自设定期限"}"#),&expected,&quotes).is_err());
}

#[cfg(test)]
#[test]
fn age_and_recurring_context_do_not_become_durations() {
    let source = "说话人1：十三周岁能不能参加，十八周岁是成人组，报名限一周。";
    let evidence = [json!({"id":"e0000","text":source})];
    let cues = omission_cues(&[], &evidence);
    assert_eq!(cues.iter().filter(|cue| cue.aspect.is_none()).map(|cue| cue.span.as_str()).collect::<Vec<_>>(),
        ["十三周岁", "十八周岁", "一周"]);
    assert!(measure_has_witness("十八周岁", &json!({"text":"成人组限18岁。"})));
    assert!(!measure_has_witness("十八周岁", &json!({"text":"训练十八周。"})));
    assert!(!measure_has_witness("十八周岁", &json!({"text":"成人组限19岁。"})));
    assert!(contextual_measure_witness("一天", &json!({"text":"前台每天加强训练。"}),
        "前台每一天都在加强训练。"));
    assert!(!contextual_measure_witness("一天", &json!({"text":"前台每天加强训练。"}),
        "这个培训持续一天。"));
    assert!(!contextual_measure_witness("一天", &json!({"text":"前台每周加强训练。"}),
        "前台每一天都在加强训练。"));
    let question = json!({"kind":"unresolved", "text":"各部门对下半年有什么计划，待汇报。"});
    assert!(contextual_measure_witness("一季度", &question,
        "针对上一季度的这个工作情况，我想问一下各部门对下半年有什么计划？"));
    assert!(!contextual_measure_witness("一季度", &question,
        "针对上一季度的工作情况，我想问一下各部门下半年是否能在一季度内完成计划？"));
    assert!(!contextual_measure_witness("一季度", &question,
        "确定在一季度内改善工作情况，我想问一下各部门对下半年有什么计划？"));
}

#[cfg(test)]
#[test]
fn ordinary_coverage_separates_progress_and_a_request_before_a_question() {
    let evidence = [
        json!({"id":"e0000","text":"说话人3：网球这方面的市场还在逐步进行打开。"}),
        json!({"id":"e0001","text":"说话人1：这块儿要进行一个市场调查 你觉得哪个风险大？"}),
        json!({"id":"e0002","text":"说话人1：咱们能否逐步推进这些做法？"}),
    ];
    let cues = omission_cues(&[], &evidence);
    assert_eq!(cues.iter().map(|cue| (cue.evidence.as_str(),cue.aspect)).collect::<Vec<_>>(),
        vec![("e0000", Some("实际进展")), ("e0001", Some("交办后又提问"))]);
}

pub(super) fn measures(text: &str) -> impl Iterator<Item = (f64, &str)> {
    static MEASURE: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(&format!(
        r"({QUANTITY})\s*({QUANTITY_UNIT})"
    )).expect("constant measure expression"));
    MEASURE.captures_iter(text).filter_map(|capture| {
        let unit_match = capture.get(2)?;
        let unit = unit_match.as_str();
        if unit == "年" && text[unit_match.end()..].starts_with('级') {
            return None;
        }
        let quantity = number_value(capture.get(1)?.as_str(), unit == "年")?;
        let unit = match unit { "块钱" => "元", "周岁" => "岁", "％" => "%", _ => unit };
        Some((quantity, unit))
    })
}

pub(super) fn number_value(text: &str, year: bool) -> Option<f64> {
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

#[derive(Clone, Copy, PartialEq)]
enum PaymentModifier {
    BeforeNumber,
    AfterNumber,
    AfterCurrency,
}

struct SpokenPayment<'a> {
    action: &'static str,
    amount: f64,
    currency: &'static str,
    modifier: Option<(PaymentModifier, &'a str)>,
    number: regex::Match<'a>,
    currency_end: usize,
}

fn completed_payments(text: &str) -> impl Iterator<Item = SpokenPayment<'_>> {
    static PAYMENT: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(&format!(
        r"(?P<action>赔偿|赔付|支付|付款|退款|退还|赔|付)(?P<completed>了)?[ 	]*(?P<estimate>大约|大概|将近|约|近)?(?P<number>{QUANTITY})(?P<excess>多|余)?(?:[ 	]*(?P<currency>美元|块钱|元))?(?P<around>左右)?"
    )).expect("constant completed-payment expression"));
    PAYMENT.captures_iter(text).filter_map(|matched| {
        let verb = matched.name("action")?;
        let begin = text[..verb.start()].rsplit(['。','！','？','；','，',';',',','\n']).next()?.trim_end();
        if ["如果", "假如", "假设", "是否", "打算", "准备", "预计", "建议", "否认"]
            .iter().any(|word| begin.contains(word))
            || ["尚未", "尚不", "没有", "不再", "未", "没", "应", "需要", "必须", "将", "要", "不"]
                .iter().any(|word| begin.ends_with(word))
        {
            return None;
        }
        let end = matched.get(0)?.end();
        let tail = text[end..].trim_start();
        let after_payment = ["之后", "以后", "后"].iter().any(|word| tail.starts_with(word));
        if ["到", "至", "以上", "以下", "以内", "起"].iter().any(|word| tail.starts_with(word)) {
            return None;
        }
        let currency = matched.name("currency");
        let completed = after_payment || matched.name("completed").is_some()
            || ["已", "已经", "曾", "曾经", "实际"].iter().any(|word| begin.ends_with(word));
        if !completed || (currency.is_none() && !after_payment) {
            return None;
        }
        let number = matched.name("number")?;
        let mut modifiers = [
            (PaymentModifier::BeforeNumber, matched.name("estimate")),
            (PaymentModifier::AfterNumber, matched.name("excess")),
            (PaymentModifier::AfterCurrency, matched.name("around")),
        ].into_iter().filter_map(|(position, marker)| Some((position, marker?.as_str())));
        let modifier = modifiers.next();
        if modifiers.next().is_some() {
            return None;
        }
        Some(SpokenPayment {
            action: match verb.as_str() {
                "赔偿" | "赔付" | "赔" => "compensation",
                "支付" | "付款" | "付" => "payment",
                "退款" | "退还" => "refund",
                _ => return None,
            },
            amount: number_value(number.as_str(), false)?,
            currency: match currency.map(|token| token.as_str()) {
                Some("美元") => "美元",
                Some(_) => "元",
                None => "",
            },
            modifier, number, currency_end: currency.map_or(number.end(), |token| token.end()),
        })
    })
}

fn retain_payment_extent<'a>(statement: &str, sources: impl Iterator<Item = &'a str>) -> Option<String> {
    if statement.contains(['「', '」', '“', '”', '"']) {
        return None;
    }
    let claims = completed_payments(statement).collect::<Vec<_>>();
    if claims.iter().all(|claim| claim.modifier.is_some()) {
        return None;
    }
    let cited_payments = sources.flat_map(completed_payments).collect::<Vec<_>>();
    let mut insertions = Vec::new();
    for claim in &claims {
        let same_payment = |other: &&SpokenPayment<'_>| {
            claim.action == other.action && claim.amount == other.amount && claim.currency == other.currency
        };
        if claim.modifier.is_some() || claims.iter().filter(same_payment).count() != 1 {
            continue;
        }
        // Keep the actual expression only when both the statement and its
        // cited speech identify one completed payment of this kind and value.
        let mut witnesses = cited_payments.iter().filter(same_payment);
        let Some((position, wording)) = witnesses.next().and_then(|payment| payment.modifier) else { continue; };
        if witnesses.next().is_some() {
            continue;
        }
        let offset = match position {
            PaymentModifier::BeforeNumber => claim.number.start(),
            PaymentModifier::AfterNumber => claim.number.end(),
            PaymentModifier::AfterCurrency => claim.currency_end,
        };
        insertions.push((offset, wording));
    }
    if insertions.is_empty() {
        return None;
    }
    let mut corrected = statement.to_owned();
    for (offset, wording) in insertions.into_iter().rev() {
        corrected.insert_str(offset, wording);
    }
    line(&corrected, 90).then_some(corrected)
}

#[cfg(test)]
#[test]
fn a_paid_amount_preserves_its_own_spoken_extent_without_borrowing_another_payment() {
    let source = "说话人5: 赔偿四千多之后就没有再赔偿。";
    let draft = "咨询人C问：法院判赔四万但仅赔四千后拒赔，怎么办。";
    assert_eq!(retain_payment_extent(draft, ["法院判赔四万元。", source].into_iter()).as_deref(),
        Some("咨询人C问：法院判赔四万但仅赔四千多后拒赔，怎么办。"));
    assert_eq!(retain_payment_extent("供应方已支付4000元。", ["供应方已经支付四千元左右。"].into_iter()).as_deref(),
        Some("供应方已支付4000元左右。"));
    assert_eq!(retain_payment_extent("公司实际退款四千元。", ["公司实际退还约四千块钱。"].into_iter()).as_deref(),
        Some("公司实际退款约四千元。"));
    assert!(retain_payment_extent(draft, [source, "也提到赔偿四千后未再付。"].into_iter()).is_none());
    assert!(retain_payment_extent(draft, ["付四千多之后。"].into_iter()).is_none());
    assert!(retain_payment_extent(draft, ["赔付四千多元之后。"].into_iter()).is_none());
    assert!(retain_payment_extent(draft, ["如果赔偿四千多之后还欠钱，怎么办？"].into_iter()).is_none());
    assert!(retain_payment_extent("仅赔约四千后拒赔。", [source].into_iter()).is_none());
    assert!(retain_payment_extent("话里说「仅赔四千后拒赔」。", [source].into_iter()).is_none());
    assert!(retain_payment_extent("仅赔四千后拒赔，隔日又赔四千后离开。", [source].into_iter()).is_none());
}

fn measure_has_witness(span: &str, claim: &Value) -> bool {
    let Some((quantity, unit)) = measures(span).next() else { return true; };
    ["text", "due"].into_iter().filter_map(|key| claim[key].as_str()).flat_map(measures)
        .any(|(found, found_unit)| unit == found_unit && (found - quantity).abs() < 1e-8)
}

fn duration_ranges(text: &str) -> Vec<(std::ops::Range<usize>, f64, f64, &str)> {
    static EXPLICIT: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?P<from>[0-9０-９一二两三四五六七八九十百]+)\s*(?P<firstUnit>个月|小时|分钟|年|周|天)?\s*(?:到|至|[-–—~～])\s*(?P<to>[0-9０-９一二两三四五六七八九十百]+)\s*(?P<unit>个月|小时|分钟|年|周|天)"
    ).unwrap());
    static SPOKEN: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?P<from>[一二两三四五六七八九])(?P<to>[一二两三四五六七八九])(?P<unit>个月|小时|分钟|年|周|天)"
    ).unwrap());
    let mut ranges = Vec::new();
    for (regex, spoken) in [(&*EXPLICIT, false), (&*SPOKEN, true)] {
        for matched in regex.captures_iter(text) {
            let Some(from) = number_value(&matched["from"], false) else { continue; };
            let Some(to) = number_value(&matched["to"], false) else { continue; };
            let unit = matched.name("unit").unwrap().as_str();
            if matched.name("firstUnit").is_some_and(|first| first.as_str() != unit) {
                continue;
            }
            let whole = matched.get(0).unwrap();
            let joined_digits = text[..whole.start()].chars().next_back().is_some_and(|ch| {
                "零〇一二两三四五六七八九十百千万亿0123456789０１２３４５６７８９".contains(ch)
            });
            if joined_digits || from >= to || (spoken && to - from != 1.0) {
                continue;
            }
            ranges.push((whole.range(), from, to, unit));
        }
    }
    ranges
}

#[cfg(test)]
#[test]
fn duration_bounds_can_repeat_the_same_unit_without_changing_meaning() {
    let source = "冬天两天到三天换一次水。";
    let compact = json!({"text":"冬天两到三天换一次水。"});
    assert_eq!(cited_duration_range_matches("两天", &compact, source), Some(true));
    assert_eq!(cited_duration_range_matches("两天", &json!({"text":"冬天两天就换。"}), source), Some(false));
    assert!(duration_ranges("两周到三天").is_empty());
    assert_eq!(duration_ranges("两周至三周")[0].3, "周");
}

fn cited_duration_range_matches(span: &str, claim: &Value, source: &str) -> Option<bool> {
    let ranges = duration_ranges(source);
    let mut spans = source.match_indices(span).peekable();
    spans.peek()?;
    let mut expected = None;
    for (offset, _) in spans {
        let (_, from, to, unit) = ranges.iter()
            .find(|(range, ..)| range.start <= offset && offset + span.len() <= range.end)?;
        let value = (*from, *to, *unit);
        if expected.replace(value).is_some_and(|old| old != value) {
            return Some(false);
        }
    }
    let expected = expected?;
    let text = claim["text"].as_str()?;
    Some(duration_ranges(text).iter().any(|(_, from, to, unit)| (*from, *to, *unit) == expected))
}

fn same_half_month_context(claim: &Value, source: &str) -> bool {
    let Some(text) = claim["text"].as_str() else { return false; };
    if !claim["due"].is_null() {
        return false;
    }
    let literal = |value: &str| normalized(value).replace("半个月", "半月");
    let source = literal(source);
    let text = literal(text);
    ["为期半月", "历时半月"].iter().any(|marker| source.contains(marker) && text.contains(marker))
        && (!source.contains("近半月") || text.contains("近半月"))
}

fn contextual_duration_example(span: &str, claim: &Value, source: &str) -> bool {
    static PARALLEL: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:不可能说|不可能一直)[^。？！；]{0,44}?(?P<example>[一二两三四五六七八九十百0-9]{1,4}年[一二两三四五六七八九十百0-9]{1,4}年)\s*[，,]\s*所以"
    ).unwrap());
    let Some(example) = PARALLEL.captures(source).and_then(|matched| matched.name("example")) else {
        return false;
    };
    // Only an exact paired example contrasted with the stated duration is
    // contextual here. Independent factual review still gets the full turn.
    let already_cited = claim["text"].as_str().is_some_and(|text| {
        let after = &source[example.end()..];
        duration_ranges(after).iter().any(|(_, from, to, unit)| duration_ranges(text).iter()
            .any(|(_, other_from, other_to, other_unit)| (from, to, unit) == (other_from, other_to, other_unit)))
    });
    already_cited && source.match_indices(span).all(|(start, _)| {
        example.start() <= start && start + span.len() <= example.end()
    }) && example.as_str().contains(span)
}

fn past_period_frames_question(span: &str, claim: &Value, source: &str) -> bool {
    if !matches!(span, "一季度" | "一月" | "一年") || claim["kind"] != "unresolved" {
        return false;
    }
    let Some((background, question)) = source.split_once("我想问一下")
        .or_else(|| source.split_once("想请问")) else { return false; };
    let mut hits = background.match_indices(span).peekable();
    if hits.peek().is_none() || question.contains(span) || !hits.all(|(at, _)| {
        let prefix = &background[..at];
        prefix.ends_with('上') && ["针对", "回顾", "回看"].iter().any(|cue| prefix.contains(cue))
            && background[at + span.len()..].contains("工作情况")
    }) {
        return false;
    }
    let summary = claim["text"].as_str().unwrap_or_default();
    ["下半年", "下季度", "下月", "明年"].iter().any(|period|
        question.contains(period) && summary.contains(period))
        && ["计划", "目标", "安排"].iter().any(|cue|
            question.contains(cue) && summary.contains(cue))
}

fn annual_activity_witness(span: &str, claim: &Value, source: &str) -> Option<bool> {
    if span != "一年" { return None; }
    const ACTIVITIES: &str = "检查|审查|巡检|盘点|演练|体检|评审|评估|培训|复核|审核|考核";
    static SPOKEN: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(&format!(
        r"^一度(?:的|这个|这项|开展|组织|进行|\s)*(?P<activity>{ACTIVITIES})"
    )).unwrap());
    static WRITTEN: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(&format!(
        r"(?:年度|每年(?:一次|例行)?(?:的|开展|组织|进行)?)(?P<activity>{ACTIVITIES})|(?P<inspection>年检)"
    )).unwrap());
    let mut activities = source.match_indices(span).map(|(at, _)| {
        SPOKEN.captures(&source[at + span.len()..]).map(|hit| hit.name("activity").unwrap().as_str())
    });
    let activity = activities.next().flatten()?;
    if !activities.all(|found| found == Some(activity)) { return Some(false); }
    let text = claim["text"].as_str()?;
    if !claim["due"].is_null() || ["action", "unresolved"].contains(&claim["kind"].as_str().unwrap_or(""))
        || ["取消", "不再", "停办", "是否", "待确认", "每两年"].iter().any(|marker| text.contains(marker))
    {
        return Some(false);
    }
    Some(WRITTEN.captures_iter(text).any(|hit| {
        let written = hit.name("activity").map_or("检查", |name| name.as_str());
        written == activity
    }))
}

fn contextual_measure_witness(span: &str, claim: &Value, source: &str) -> bool {
    if let Some(matches) = cited_duration_range_matches(span, claim, source) {
        return matches;
    }
    if let Some(matches) = annual_activity_witness(span, claim, source) {
        return matches;
    }
    if span == "半个月" && same_half_month_context(claim, source) {
        return true;
    }
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
    if span == "一天" && contextual_literal(span, &|lead, _| lead.ends_with('每')) {
        return claim["text"].as_str().is_some_and(|text| ["每天", "每日", "每一天"]
            .iter().any(|period| text.contains(period)));
    }
    if past_period_frames_question(span, claim, source) {
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
    let explicit_half_month = ["半个月历时十五天", "十五天半个月", "半个月（十五天）", "半个月也就是十五天"]
        .iter().any(|syntax| normalized(source).contains(syntax));
    if span == "半个月" && measure_has_witness("十五天", claim) && (
        (explicit_half_month && claim["due"].is_null()
            && !["截止", "最晚", "之前", "到期", "前交"].iter().any(|term| source.contains(term)))
        || (claim["kind"] != "action" && claim["kind"] != "decision"
            && ["如果", "大约", "大概"].iter().any(|term| source.contains(term)))) {
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
fn compares_both_boundaries_of_a_spoken_duration() {
    let range = json!({"text":"入职过渡约一两年。"});
    let endpoint = json!({"text":"入职过渡两年。"});
    assert!(contextual_measure_witness("两年", &range, "在一到两年的工作期间"));
    assert!(!contextual_measure_witness("两年", &endpoint, "在一到两年的工作期间"));
    assert!(!contextual_measure_witness("十年", &range, "第一家公司并不会工作十年二十年"));
    assert!(contextual_measure_witness("半个月", &json!({"text":"准备十五天行程。","kind":"action"}),
        "十五天半个月的时间准备带人家去哪里"));
    assert!(!contextual_measure_witness("半个月", &json!({"text":"准备十五天行程。","kind":"action","due":"十五天"}),
        "半个月内最晚交计划。"));
    assert!(duration_ranges("等十五六年").is_empty());
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

fn restore_source_context_for_coverage(
    checks: &mut [SourceCheck], cues: &[SourceCue], claims: &[Value], evidence: &[Value],
    bindings: &HashMap<String, &Vec<String>>,
) {
    for check in checks {
        let SourceCheck::Covered { id, claim, proof } = check else { continue; };
        let Some(cue) = cues.iter().find(|cue| cue.id == *id && cue.aspect.is_none()) else { continue; };
        let Some((position, original)) = evidence.iter().enumerate().find(|(_, row)| row["id"] == cue.evidence.as_str())
            else { continue; };
        let source = original["text"].as_str().unwrap();
        let candidates = claims.iter().filter(|value| {
            value["path"].as_str().and_then(|path| bindings.get(path)).is_some_and(|ids| ids.contains(&cue.evidence))
        });
        if candidates.clone().any(|value| contextual_duration_example(&cue.span, value, source)) {
            *check = SourceCheck::Background {
                id: id.clone(), reason: "对照原话，这段连续时长是反例。同一发言的实际过渡时长已保留。".into(),
            };
            continue;
        }
        if cue.span != "半个月" {
            continue;
        }
        if let Some(witness) = candidates.into_iter().find(|value| same_half_month_context(value, source)) {
            *claim = witness["path"].as_str().unwrap().to_owned();
            *proof = None;
            continue;
        }
        let source_body = super::super::source_resolution::split_turn_label(source)
            .map_or(source, |(_, content)| content).trim().trim_end_matches(['。', '！']);
        if source_body != cue.span {
            continue;
        }
        let same_duration = [position.checked_sub(1), Some(position + 1)].into_iter().flatten()
            .filter_map(|i| evidence.get(i))
            .filter(|row| row["source"] == original["source"])
            .filter(|row| {
                let text = normalized(row["text"].as_str().unwrap());
                ["半个月历时十五天", "半个月也就是十五天"].iter().any(|word| text.contains(word))
            })
            .any(|row| {
                let adjacent_id = row["id"].as_str().unwrap();
                claims.iter().any(|value| {
                    value["path"].as_str().and_then(|path| bindings.get(path))
                        .is_some_and(|ids| ids.iter().any(|id| id == adjacent_id))
                        && value["due"].is_null() && measure_has_witness("十五天", value)
                })
            });
        if same_duration {
            *check = SourceCheck::Background {
                id: id.clone(), reason: "相邻原话已重复相同时长并换算，当前事项保留了该时长。".into(),
            };
        }
    }
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
        let wrong_measure = cue.aspect.is_none()
            && !contextual_measure_witness(&cue.span, statement, sentence["text"].as_str()?);
        let different_source = !cited.is_some_and(|ids| ids.contains(&cue.evidence));
        (wrong_measure || different_source || cue.aspect.is_some()).then(|| json!({
            "cue":cue, "claimedWitness":statement, "witnessEvidence":cited,
            "measureNeedsCheck":wrong_measure, "sourceNeedsCheck":different_source,
        }))
    }).collect()
}

fn coverage_quote_is_grounded(quote: &str, text: &str) -> bool {
    line(quote, 180) && quote.chars().filter(|ch| ch.is_alphanumeric()).count() >= 5
        && normalized(text).contains(&normalized(quote))
}

fn relative_quarter_witness(span: &str, source: &str, source_quote: &str, statement_quote: &str) -> bool {
    if span != "一季度" { return false; }
    for direction in ['上', '下'] {
        let with_number = format!("{direction}{span}");
        let mut occurrences = source.match_indices(span).peekable();
        if occurrences.peek().is_none()
            || !occurrences.all(|(start, _)| source[..start].ends_with(direction))
            || !source_quote.contains(&with_number)
        {
            continue;
        }
        return ["季度", "一季度", "个季度", "一个季度"].iter()
            .any(|term| statement_quote.contains(&format!("{direction}{term}")));
    }
    false
}

fn academic_billing_period_witness(span: &str, source: &str, source_quote: &str, statement_quote: &str) -> bool {
    static ANNUAL_PAYMENT: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:交|缴)(?:了|的是|纳)?(?:是)?一年(?:度)?"
    ).expect("constant annual payment expression"));
    static ACADEMIC_PAYMENT: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:交|缴)(?:了|的是|纳)?(?:是)?一{1,3}学年"
    ).expect("constant academic payment expression"));
    let source = normalized(source);
    let quote = normalized(source_quote);
    if span != "一年" || !ANNUAL_PAYMENT.is_match(&source) || !ACADEMIC_PAYMENT.is_match(&source)
        || !(ANNUAL_PAYMENT.is_match(&quote) || ACADEMIC_PAYMENT.is_match(&quote))
    {
        return false;
    }
    // The speaker used both names for the same payment cycle. A semester
    // or a period of non-attendance still needs a separate factual witness.
    let statement = normalized(statement_quote);
    ["按学年交费", "按学年缴费", "按学年交纳", "按学年缴纳"].iter().any(|phrase| {
        statement.match_indices(phrase).any(|(start, _)| {
            !["不", "不是", "并非", "未", "不能", "如果", "假设"].iter()
                .any(|prefix| statement[..start].ends_with(prefix))
        })
    })
}

fn daily_frequency_witness(span: &str, question: &str, answer_quote: &str, statement_quote: &str) -> bool {
    static QUESTION: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"一天([\p{Han}]{2,8}?)几次"
    ).expect("constant daily frequency question"));
    if span != "一天" { return false; }
    let Some(activity) = QUESTION.captures(question).and_then(|phrase| phrase.get(1)) else {
        return false;
    };
    let rate = regex::Regex::new(&format!(
        r"(早上|上午|中午|下午|傍晚|晚上|夜间|白天)?(?:会去|会|要|需)?{}\s*([0-9０-９]+|[一二两三四五六七八九十百]+)次",
        regex::escape(activity.as_str()),
    )).expect("frequency expression with escaped activity");
    let rates = |quote: &str| {
        rate.captures_iter(quote).filter_map(|hit| {
            let scope = hit.get(1).map_or("", |scope| match scope.as_str() {
                "上午" => "早上",
                "晚上" => "夜间",
                other => other,
            });
            Some((scope.to_owned(), number_value(hit.get(2)?.as_str(), false)?))
        }).collect::<Vec<_>>()
    };
    let daily_rates = |quote: &str| {
        if ["不用", "不能", "没有", "不会", "不再", "不必", "几次", "待定"].iter().any(|cue| quote.contains(cue)) {
            return None;
        }
        quote.find("每天").or_else(|| quote.find("每日")).map(|start| rates(&quote[start..]))
    };
    match (daily_rates(answer_quote), daily_rates(statement_quote)) {
        (Some(answer), Some(statement)) => !answer.is_empty() && answer == statement,
        _ => false,
    }
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

fn aspect_quote_covers_clause(quote: &str, required: &str, aspect: &str) -> bool {
    let quote = normalized(quote);
    let required = normalized(required);
    if quote.contains(&required) {
        return true;
    }
    if aspect != "明确限制" {
        return false;
    }
    // A question of the form "不得先了解嘛，了解了才能实践" repeats
    // the prerequisite affirmatively. An independent prohibition cannot be
    // replaced by any follow-up clause mentioning a different condition.
    let Some((question, answer)) = required.strip_prefix("不得")
        .and_then(|text| text.split_once(['嘛', '吗'])) else { return false; };
    let prerequisite = question.trim_start_matches(['有', '先']).trim();
    let answer = answer.trim_start_matches(['，', ',', '、']).trim_end_matches(['嘛', '吗']);
    prerequisite.chars().count() >= 2 && answer.starts_with(prerequisite)
        && answer.contains("才能") && quote.contains(answer)
}

fn opening_scope_is_retained(source: &str, quote: &str, purpose: &str) -> bool {
    let opening = ["今天", "会议开场", "这次会议", "本次会议", "把大家叫来"]
        .iter().any(|marker| source.contains(marker));
    let operational = ["最晚", "截止", "以前", "必须", "务必", "会后", "交付", "完成期限"]
        .iter().any(|marker| quote.contains(marker) || source.contains(marker));
    if !opening || operational || !coverage_quote_is_grounded(quote, source) {
        return false;
    }
    let scope = ["上半年", "下半年"].into_iter().find(|period| quote.contains(period));
    let same_period = scope.is_some_and(|period| {
        purpose.contains(period) && source.match_indices("半年").all(|(index, _)| {
            source[..index].ends_with(period.trim_end_matches("半年"))
        })
    });
    let recap = ["总结", "复盘", "回顾"];
    let same_activity = quote.contains("汇报") && purpose.contains("汇报")
        || recap.iter().any(|action| quote.contains(action)) && recap.iter().any(|action| purpose.contains(action));
    same_period && same_activity
}

fn retain_opening_scope(checks: &mut [SourceCheck], disputed: &[Value], doc: &Document, evidence: &[Value]) -> usize {
    let mut count = 0;
    for check in checks {
        let SourceCheck::Covered { id, claim, proof: Some(proof) } = check else { continue; };
        let purpose_proven = claim == "purpose" && coverage_quote_is_grounded(&proof.statement_quote, &doc.purpose);
        if !purpose_proven && !claim.ends_with("].title") { continue; }
        let Some(cue) = disputed.iter().map(|row| &row["cue"])
            .find(|cue| cue["id"] == id.as_str() && cue["span"] == "半年" && cue["aspect"].is_null())
        else { continue; };
        let Some(text) = evidence.iter().find(|row| row["id"] == cue["evidence"])
            .and_then(|row| row["text"].as_str()) else { continue; };
        if opening_scope_is_retained(text, &proof.source_quote, &doc.purpose) {
            *check = SourceCheck::Background {
                id: id.clone(), reason: "逐字原话描述开场汇报范围，主线已保留相同期间和汇报动作。".into(),
            };
            count += 1;
        }
    }
    count
}

fn explicit_yuan_amount(span: &str) -> Option<f64> {
    let mut found = measures(span);
    let (amount, unit) = found.next()?;
    (unit == "元" && found.next().is_none()).then_some(amount)
}

fn same_court_award(span: &str, amount: f64, utterance: &str, quote: &str) -> bool {
    if !coverage_quote_is_grounded(quote, utterance) {
        return false;
    }
    let quote = normalized(quote);
    let span = normalized(span);
    if !quote.match_indices(&span).any(|(at, _)| {
        ["判赔", "赔偿", "赔付"].iter().any(|term| quote[..at].ends_with(term))
    }) {
        return false;
    }
    let utterance = normalized(utterance);
    utterance.match_indices(&span).any(|(at, _)| {
        let lead: String = utterance[..at].chars().rev().take(42).collect::<Vec<_>>().into_iter().rev().collect();
        ["法院", "判决", "判赔"].iter().any(|term| lead.contains(term))
            && !["可能赔偿", "拟赔偿", "要求涨到"].iter().any(|term| lead.ends_with(term))
            && explicit_yuan_amount(&span) == Some(amount)
    })
}

fn bare_award_witness(quote: &str, amount: f64) -> bool {
    static AWARD: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(&format!(
        r"(?:判赔|判决赔偿|判令赔偿)(?P<amount>{QUANTITY})(?P<tail>元|块钱|但|而|并|[，。；、！。]|$)"
    )).expect("court award amount pattern"));
    let text = normalized(quote);
    AWARD.captures_iter(&text).any(|row| {
        row.name("amount").and_then(|value| number_value(value.as_str(), false)) == Some(amount)
    })
}

fn monetary_example(span: &str, source: &str, proof: &CoverageProof) -> Option<String> {
    if !coverage_quote_is_grounded(&proof.source_quote, source)
        || !proof.source_quote.contains(span) || source.matches(span).count() != 1
    {
        return None;
    }
    let (speaker, speech) = super::super::source_resolution::split_turn_label(source.trim())
        .map_or(("会上", source.trim()), |(speaker, speech)| (speaker, speech));
    let at = speech.find(span)?;
    let start = ["比如说", "例如", "举个例子", "假设"].iter()
        .filter_map(|term| speech[..at].rfind(term)).max()?;
    let preceded = &speech[start..at];
    if preceded.chars().count() > 36 || preceded.contains(['。','；','！','？','\n']) {
        return None;
    }
    let end = at + span.len();
    let after = speech[end..].trim_start();
    if !["那么", "的话", "，那么", "，这时", "，这个时候"].iter().any(|term| after.starts_with(term)) {
        return None;
    }
    let excerpt = speech[start..end].trim();
    let text = format!("{speaker}举例「{excerpt}」。");
    (line(&text, 90) && !excerpt.contains(['「', '」'])).then_some(text)
}

fn recover_monetary_coverage(
    checks: &mut [SourceCheck], disputed: &[Value], doc: &Document, evidence: &[Value],
    bindings: &HashMap<String, &Vec<String>>,
) -> Vec<Value> {
    let clauses = factual_audit::claims(doc);
    let mut recovered = Vec::new();
    for check in checks {
        let SourceCheck::Covered { id, claim, proof: Some(proof) } = check else { continue; };
        let Some(context) = disputed.iter().find(|entry| entry["cue"]["id"] == id.as_str()) else { continue; };
        if context["cue"]["aspect"].is_string() || context.get("unrepresentedSourceQuote").is_some()
            || context.get("eligibleWitnesses").is_some()
        {
            continue;
        }
        let Some(span) = context["cue"]["span"].as_str() else { continue; };
        let Some(amount) = explicit_yuan_amount(span) else { continue; };
        let anchor = context["cue"]["evidence"].as_str().unwrap_or_default();
        let Some(position) = evidence.iter().position(|row| row["id"] == anchor) else { continue; };
        let original = &evidence[position];
        let Some(source) = original["text"].as_str() else { continue; };
        let witnesses = || clauses.iter().filter(|item| item.get("sources").is_some()
            && item["text"].as_str().is_some_and(|text| coverage_quote_is_grounded(&proof.statement_quote, text)));

        if same_court_award(span, amount, source, &proof.source_quote)
            && bare_award_witness(&proof.statement_quote, amount)
        {
            let mut eligible = witnesses().filter(|item| {
                let path = item["path"].as_str().unwrap();
                let Some(ids) = bindings.get(path) else { return false; };
                if ids.iter().any(|id| id == anchor) { return true; }
                let start = position.saturating_sub(6);
                evidence[start..position].iter().enumerate().any(|(offset, row)| {
                    if row["source"] != original["source"]
                        || !row["id"].as_str().is_some_and(|id| ids.iter().any(|one| one == id))
                    { return false; }
                    let text = row["text"].as_str().unwrap_or_default();
                    let same = measures(text).any(|(amount_here, unit)| unit == "元" && amount_here == amount)
                        && (text.contains("法院") || text.contains("判决")) && text.contains("赔偿");
                    same && evidence[start + offset + 1..position].iter().all(|row| {
                        let text = row["text"].as_str().unwrap_or_default();
                        !["另一个案", "另一笔", "下一个问题", "换一个"].iter().any(|cue| text.contains(cue))
                    })
                })
            });
            let Some(witness) = eligible.next() else { continue; };
            if eligible.next().is_some() { continue; }
            let path = witness["path"].as_str().unwrap();
            recovered.push(json!({"id":id,"kind":"courtAward","previousClaim":claim,"claim":path}));
            *claim = path.to_owned();
        } else if let Some(text) = monetary_example(span, source, proof) {
            let Some(witness) = witnesses().find(|item| item["path"] == claim.as_str()) else { continue; };
            let path = witness["path"].as_str().unwrap();
            if !bindings.get(path).is_some_and(|ids| ids.iter().any(|id| id == anchor)) {
                continue;
            }
            let topic = path.strip_prefix("topics[").and_then(|path| path.split_once(']'))
                .and_then(|(index, _)| index.parse::<usize>().ok()).and_then(|index| doc.topics.get(index))
                .map(|topic| topic.title.clone());
            let id = id.clone();
            recovered.push(json!({"id":id,"kind":"sourceExample","claim":path}));
            *check = SourceCheck::Missing { id, addition: MissingItem {
                item: SourceItem { role: Role::Example, text, evidence: vec![anchor.to_owned()], owner: None, due: None },
                topic, new_aspect: None,
            }};
        }
    }
    recovered
}

#[cfg(test)]
#[test]
fn an_award_is_not_interchangeable_with_payment_or_another_currency() {
    assert!(bare_award_witness("法院判赔四万但仅赔四千后拒赔", 40_000.0));
    assert!(!bare_award_witness("法院判赔四万多，仍拒赔", 40_000.0));
    assert!(!bare_award_witness("法院判赔四万美元，尚未支付", 40_000.0));
    assert!(!bare_award_witness("法院判赔五万但被告已赔四万。", 40_000.0));
    assert!(!same_court_award("四万元",40_000.0,"法院另案判赔五万元。实际赔偿四万元。",
        "法院另案判赔五万元"));
    assert!(!same_court_award("四万元",40_000.0,"法院当时要求给受害人赔偿四万元。",
        "向受害人赔偿四万元"));
    assert!(same_court_award("四万元",40_000.0,"法院当时要求给受害人赔偿四万元。",
        "给受害人赔偿四万元"));
}

#[cfg(test)]
#[test]
fn only_a_unique_witness_can_rebind_a_repeated_award_and_keep_the_example() {
    let doc: Document = serde_json::from_value(json!({
        "purpose":"核对申请执行的事例","topics":[{"title":"情况","points":[
            {"kind":"opinion","text":"例中房屋经婚前公证，离婚时不会分给另一方。","sources":["u003"]},
            {"kind":"opinion","text":"另讨论能否保留案底。","sources":["u005"]}
        ],"details":[]}],"questions":[
            {"text":"法院判赔四万但仅赔四千后拒赔，怎么处理？","sources":["u004"]}
        ],"actionItems":[],"decisions":[]
    })).unwrap();
    let evidence = [
        json!({"id":"e0062","source":"u003","text":"说话人2：比如说结婚之前已有一套房子和十万块钱，那么离婚不会分给别人。"}),
        json!({"id":"e0090","source":"u004","text":"说话人5：法院当时要求给受害人赔偿四万元。"}),
        json!({"id":"e0092","source":"u004","text":"说话人5：赔偿四千多之后就没有再赔偿。"}),
        json!({"id":"e0095","source":"u004","text":"说话人2：一审已经判决赔偿四万块钱。"}),
    ];
    let original_home = vec!["e0062".into()];
    let original_award = vec!["e0090".into(),"e0092".into()];
    let unrelated = vec!["e0100".into()];
    let bindings = HashMap::from([("topics[0].points[0]".into(),&original_home),
        ("topics[0].points[1]".into(),&unrelated),("questions[0]".into(),&original_award)]);
    let disputed = [
        json!({"cue":{"id":"v011","evidence":"e0062","span":"十万块钱"}}),
        json!({"cue":{"id":"v012","evidence":"e0090","span":"四万元"}}),
        json!({"cue":{"id":"v014","evidence":"e0095","span":"四万块钱"}}),
    ];
    let raw = r#"{"checks":[
        {"id":"v011","status":"covered","claim":"topics[0].points[0]",
         "proof":{"sourceQuote":"结婚之前已有一套房子和十万块钱","statementQuote":"婚前公证，离婚时不会分给另一方"}},
        {"id":"v012","status":"covered","claim":"questions[0]",
         "proof":{"sourceQuote":"给受害人赔偿四万元","statementQuote":"法院判赔四万但仅赔四千后拒赔"}},
        {"id":"v014","status":"covered","claim":"topics[0].points[1]",
         "proof":{"sourceQuote":"判决赔偿四万块钱","statementQuote":"法院判赔四万但仅赔四千后拒赔"}}
        ],"additions":[]}"#;
    let mut fresh: MissingItems = parse(raw).unwrap();
    let repaired = recover_monetary_coverage(&mut fresh.checks,&disputed,&doc,&evidence,&bindings);
    assert_eq!(repaired.len(),3);
    assert!(matches!(&fresh.checks[0],SourceCheck::Missing { addition, .. }
        if addition.item.role == Role::Example && addition.item.text.contains("十万块钱")));
    assert!(matches!(&fresh.checks[2],SourceCheck::Covered {claim,..} if claim=="questions[0]"));
    let mut separate_case = evidence.clone();
    separate_case[2]["text"]=json!("下一个问题涉及已付四千多。");
    let mut negative: MissingItems = parse(raw).unwrap();
    assert_eq!(recover_monetary_coverage(&mut negative.checks,&disputed,&doc,&separate_case,&bindings).len(),2);
}

fn rejected_coverage(checks: &[SourceCheck], disputed: &[Value], doc: &Document, evidence: &[Value],
    bindings: &HashMap<String, &Vec<String>>,
) -> Vec<Value> {
    let clauses = factual_audit::claims(doc);
    checks.iter().filter_map(|check| {
        let SourceCheck::Covered { id, claim, proof } = check else { return None; };
        let context = disputed.iter().find(|row| row["cue"]["id"] == id.as_str())?;
        let source = evidence.iter().find(|row| row["id"] == context["cue"]["evidence"])?;
        let target = clauses.iter().find(|row| row["path"] == claim.as_str() && row.get("sources").is_some());
        let source_text = source["text"].as_str()?;
        let cited = bindings.get(claim);
        let grounded = proof.as_ref().is_some_and(|proof| {
            (coverage_quote_is_grounded(&proof.source_quote, source_text) || evidence.iter().any(|row| {
                row["id"].as_str().is_some_and(|e| cited.is_some_and(|ids| ids.iter().any(|id| id == e)))
                    && coverage_quote_is_grounded(&proof.source_quote, row["text"].as_str().unwrap())
            })) && target.and_then(|row| row["text"].as_str())
                .is_some_and(|text| coverage_quote_is_grounded(&proof.statement_quote, text))
        });
        let ordinary_proof = if let Some(aspect) = context["cue"]["aspect"].as_str() {
            let required = context["cue"]["span"].as_str()?;
            proof.as_ref().is_some_and(|proof| coverage_quote_is_grounded(&proof.source_quote, source_text)
                && aspect_quote_covers_clause(&proof.source_quote, required, aspect)
                && (!matches!(aspect, "交办后又提问" | "交办的内容范围") || !claim.starts_with("questions["))
                && target.is_some_and(|statement| super::source_coverage::facet_has_witness(
                    aspect, required, statement["kind"].as_str().unwrap_or(""),
                    statement["text"].as_str().unwrap_or(""))))
        } else { true };
        let span = context["cue"]["span"].as_str()?;
        let alternate_measure = grounded && proof.as_ref().is_some_and(|proof| {
            (coverage_quote_is_grounded(&proof.source_quote, source_text)
                && (relative_quarter_witness(span, source_text, &proof.source_quote, &proof.statement_quote)
                    || academic_billing_period_witness(span, source_text, &proof.source_quote, &proof.statement_quote)))
                || evidence.iter().skip_while(|row| row["id"] != source["id"]).skip(1).take(8).any(|answer| {
                    answer["source"] == source["source"]
                        && answer["id"].as_str().is_some_and(|id| cited.is_some_and(|ids| ids.iter().any(|cited| cited == id)))
                        && answer["text"].as_str().is_some_and(|text| coverage_quote_is_grounded(&proof.source_quote, text))
                        && daily_frequency_witness(span, source_text, &proof.source_quote, &proof.statement_quote)
                })
        });
        let measure_matches = context["cue"]["aspect"].is_string() || alternate_measure
            || target.is_some_and(|claim| contextual_measure_witness(span, claim, source_text));
        let omitted_qualification = restriction().find_iter(source_text).find(|hit| {
            !hit.as_str().ends_with(['吗', '么', '呢'])
                && !(hit.as_str().starts_with("没有") && source_text[..hit.start()].ends_with('有'))
        }).filter(|_| {
            context["sourceNeedsCheck"] == true && !target.and_then(|row| row["text"].as_str())
                .is_some_and(|text| restriction().is_match(text))
        });
        let linked = context["eligibleWitnesses"].as_array()
            .is_none_or(|candidates| candidates.iter().any(|entry| entry["path"] == claim.as_str()));
        if grounded && ordinary_proof && measure_matches && omitted_qualification.is_none() && linked { return None; }
        let mut issue = context.clone();
        issue["previousClaim"] = json!(claim);
        if let Some(target) = target {
            issue["rejectedWitness"] = target.clone();
            if context["cue"]["aspect"] == "明确确认的进展或方案" {
                issue["rejectedWitnessEvidence"] = json!(cited);
            }
        }
        issue["reason"] = json!(if target.is_none() {
            "事项编号与现有稿不匹配。请原样复制现有事项的 path；无法对应时说明缺失、背景或待核实。"
        } else if !ordinary_proof {
             "引文须覆盖线索标记的独立事实以及相应状态，例如时间范围、明确确认或交办。与该事实有关的提问、建议和其他阶段的事项不足以证明已写。"
        } else if !measure_matches {
            "该正文未保留原话的同一数量或时长。若原话数字只是口语描述、例子或含混片段，应说明其性质；若关乎实际理解或执行，补入正确事实或写待核实。"
        } else if omitted_qualification.is_some() {
            "原话有明确的限制或不足，所指正文只写了其他内容，未表达这条限制。"
        } else { "必须分别提供原话与现有正文实际出现的同一事实短句。" });
        if let Some(qualification) = omitted_qualification {
            issue["unrepresentedSourceQuote"] = json!(qualification.as_str());
            let anchor = context["cue"]["evidence"].as_str()?;
            issue["eligibleWitnesses"] = json!(clauses.iter().filter(|entry| {
                let Some(path) = entry["path"].as_str() else { return false; };
                path != claim && bindings.get(path).is_some_and(|ids| ids.iter().any(|id| id == anchor))
            }).collect::<Vec<_>>());
            let related = related_causal_evidence(evidence, source, qualification.as_str());
            if !related.is_empty() {
                issue["relatedCausalEvidence"] = json!(related);
            }
        }
        Some(issue)
    }).collect()
}

#[cfg(test)]
#[test]
fn coverage_supports_relative_periods_and_a_cited_answer_to_a_frequency_question() {
    assert!(relative_quarter_witness("一季度", "上一季度已找回。", "上一季度已找回", "上季度已找回"));
    assert!(!relative_quarter_witness("一季度", "第一季度已找回。", "第一季度已找回", "上季度已找回"));
    assert!(!relative_quarter_witness("一季度", "上一季度已找回。", "上一季度已找回", "下季度已找回"));
    let question = "咱们现在大概是一天巡逻几次";
    let answer = "他们每天早上会去巡逻三次，下午巡逻两次。";
    assert!(daily_frequency_witness("一天", question, answer, "每天上午巡逻3次、下午巡逻2次。"));
    assert!(!daily_frequency_witness("一天", question, answer, "每天上午巡逻2次、下午巡逻3次。"));
    assert!(!daily_frequency_witness("一天", "有一天巡逻了几次", answer, "每天上午巡逻3次、下午巡逻2次。"));
}

#[cfg(test)]
#[test]
fn coverage_compares_the_annual_cycle_of_the_same_activity() {
    let source = "我们食堂部前几天接受检查，一年一度这个检查，等级还是B级。";
    let witness = |text: &str| json!({"text":text,"kind":"status"});
    assert!(contextual_measure_witness("一年", &witness("卫生局年度检查后食堂仍为B级。"), source));
    assert!(contextual_measure_witness("一年", &witness("食堂年检仍为B级。"), source));
    assert!(!contextual_measure_witness("一年", &witness("食堂年度培训通过。"), source));
    assert!(!contextual_measure_witness("一年", &witness("食堂取消年度检查。"), source));
    assert!(!contextual_measure_witness("一年", &witness("卫生局一年内执行检查。"), source));
    assert!(!contextual_measure_witness("一年", &witness("食堂按年度检查。"), "食堂整改期为一年。"));
}

#[cfg(test)]
#[test]
fn annual_payment_alias_requires_the_source_to_name_the_same_academic_cycle() {
    let witness = "因为我们交了是一年度吗";
    let original = "因为我们交了是一年度吗，交的是一一一学年的。";
    assert!(academic_billing_period_witness("一年", original, witness, "因按学年缴费且只退本学期部分"));
    assert!(academic_billing_period_witness("一年", original, "交的是一一一学年的", "因按学年缴费且只退本学期部分"));
    assert!(!academic_billing_period_witness("一年", witness, witness, "因按学年缴费且只退本学期部分"));
    assert!(!academic_billing_period_witness("一年", original, witness, "因按学期缴费且只退本学期部分"));
    assert!(!academic_billing_period_witness("一年", original, witness, "并非按学年缴费"));
    assert!(!academic_billing_period_witness("半年", original, witness, "因按学年缴费且只退本学期部分"));
}

fn retain_acknowledgment(issue: &Value, evidence: &[Value]) -> Option<SourceCheck> {
    let cue = &issue["cue"];
    let anchor = cue["evidence"].as_str()?;
    let span = cue["span"].as_str()?;
    if cue["aspect"] != "明确确认的进展或方案"
        || issue["rejectedWitness"]["kind"] != "recommendation"
        || !issue["rejectedWitnessEvidence"].as_array()?.iter().any(|id| id == anchor)
    {
        return None;
    }
    let original = evidence.iter().find(|row| row["id"] == anchor)?["text"].as_str()?;
    let quote = super::source_coverage::verbatim_acceptance(original, span)?;
    let speaker = super::super::source_resolution::split_turn_label(original)
        .map_or("会上", |(speaker, _)| speaker);
    let text = format!("{speaker}回应「{quote}」。");
    line(&text, 90).then(|| SourceCheck::Missing {
        id: cue["id"].as_str().unwrap().to_owned(),
        addition: MissingItem {
            topic: None, new_aspect: None,
            item: SourceItem { role: Role::Status, text, evidence: vec![anchor.to_owned()],
                owner: None, due: None },
        },
    })
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

fn repeated_delay_witness(
    cue: &SourceCue, addition: &MissingItem, claims: &[Value], evidence: &[Value],
    bindings: &HashMap<String, &Vec<String>>,
) -> Option<String> {
    static REFERENCE: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"^(?P<range>[0-9零〇一二两三四五六七八九十]{1,4}\s*(?:到|至)\s*[0-9零〇一二两三四五六七八九十]{1,4}\s*(?:天|小时|周|月))(?:这(?:一)?块(?:儿)?|这段时间|这个时长)"
    ).unwrap());
    if cue.aspect.is_some() || !matches!(addition.item.role, Role::Recommendation) {
        return None;
    }
    let at = evidence.iter().position(|row| row["id"] == cue.evidence)?;
    let raw = evidence[at]["text"].as_str()?.trim();
    let speech = super::super::source_resolution::split_turn_label(raw).map_or(raw, |(_, rest)| rest.trim());
    let range = normalized(REFERENCE.captures(speech)?.name("range")?.as_str());
    if !range.contains(&normalized(&cue.span))
        || !addition.item.text.contains("提前") && !addition.item.text.contains(&format!("前{}", cue.span))
    {
        return None;
    }
    let unprefixed = |text: &str| {
        let text = text.trim_start_matches("会上曾建议：").trim_start_matches("会上建议：");
        normalized(text)
    };
    let addition_text = unprefixed(&addition.item.text);
    let duplicate = claims.iter().any(|claim| {
        let Some(path) = claim["path"].as_str() else { return false; };
        let Some(witness) = bindings.get(path) else { return false; };
        let Some(text) = claim["text"].as_str() else { return false; };
        let target = unprefixed(text);
        let same = addition_text == target || (text.starts_with("会上曾建议：")
            && addition_text.replacen("需在", "在", 1) == target);
        same && !addition.item.evidence.is_empty() && addition.item.evidence.iter().all(|id| witness.contains(id))
    });
    if !duplicate { return None; }
    let mut candidates = claims.iter().filter_map(|claim| {
        let path = claim["path"].as_str()?;
        let ids = bindings.get(path)?;
        let text = normalized(claim["text"].as_str()?);
        ["推迟", "延期", "延后"].into_iter().any(|verb| {
            let phrase = format!("{verb}{range}");
            let asserted = |text: &str| text.match_indices(&phrase).any(|(offset, _)| {
                !["不", "不能", "不要", "不得", "不会", "没有", "没", "未", "别"]
                    .iter().any(|negative| text[..offset].ends_with(negative))
            });
            asserted(&text) && evidence[at.saturating_sub(4)..at].iter().any(|earlier| {
                earlier["source"] == evidence[at]["source"]
                    && ids.iter().any(|id| earlier["id"] == id.as_str())
                    && earlier["text"].as_str().is_some_and(|raw| asserted(&normalized(raw)))
            })
        }).then_some(path)
    });
    let path = candidates.next()?;
    candidates.next().is_none().then(|| path.to_owned())
}

#[cfg(test)]
#[test]
fn a_repeated_delay_uses_the_prior_time_range_instead_of_the_forecast_lead_time() {
    let evidence = [
        json!({"id":"e0307","source":"u011","text":"说话人4: 如果路况受阻可以往后推迟一到两天。"}),
        json!({"id":"e0310","source":"u011","text":"说话人1: 一到两天这一块儿，要跟各部门沟通。"}),
        json!({"id":"e0313","source":"u011","text":"说话人3: 大堂在会议前两天联系或观察天气。"}),
    ];
    let delay = vec!["e0307".into()];
    let weather = vec!["e0313".into()];
    let bindings = HashMap::from([("topics[0].points[0]".into(),&delay),("topics[0].details[0]".into(),&weather)]);
    let mut claims = [
        json!({"path":"topics[0].points[0]","text":"如果路况受阻可推迟一到两天。"}),
        json!({"path":"topics[0].details[0]","text":"会上曾建议：大堂在会议前两天联系或观察天气。"}),
    ];
    let cue = SourceCue{id:"v006".into(),evidence:"e0310".into(),span:"两天".into(),aspect:None};
    let mut correction: MissingItem = serde_json::from_value(json!({"topic":null,"item":{"role":"recommendation",
        "text":"大堂需在会议前两天联系或观察天气。","evidence":["e0313"],"owner":null,"due":null}})).unwrap();
    assert_eq!(repeated_delay_witness(&cue,&correction,&claims,&evidence,&bindings).as_deref(),Some("topics[0].points[0]"));
    claims[0]["text"] = json!("不能推迟一到两天。");
    assert!(repeated_delay_witness(&cue,&correction,&claims,&evidence,&bindings).is_none());
    claims[0]["text"] = json!("如路况受阻，可推迟一到两天。");
    correction.item.text = "大堂需在会议前两天联系或观察天气，并通知客户。".into();
    assert!(repeated_delay_witness(&cue,&correction,&claims,&evidence,&bindings).is_none());
}

#[cfg(test)]
#[test]
fn a_structural_extra_brace_does_not_change_quoted_text_or_other_checks() {
    let raw = r#"{"checks":[{"id":"v001","status":"background","reason":"示例中的 } 和 ] 属于原话。"}},{"id":"v002","status":"background","reason":"两分钟只是举例。"}],"additions":[]}"#;
    let fixed = remove_surplus_check_brace(raw).unwrap();
    let json: Value = serde_json::from_str(&fixed).unwrap();
    assert_eq!(json["checks"][0]["reason"], "示例中的 } 和 ] 属于原话。");
    assert_eq!(json["checks"][1]["id"], "v002");
    assert!(remove_surplus_check_brace(&fixed).is_none());
    let two = raw.replace(r#"两分钟只是举例。"}"#, r#"两分钟只是举例。"}}"#);
    assert!(remove_surplus_check_brace(&two).is_none());
}

#[cfg(test)]
#[test]
fn a_source_example_can_only_be_a_discussion_item() {
    let mut source = json!({"text":"说话人2: 比如价值十万元的车可以拍卖。","source":"u000"});
    let decode = || serde_json::from_value::<SourceItem>(json!({"role":"example",
        "text":"律师举例：车辆可拍卖。","evidence":["e0001"],"owner":null,"due":null})).unwrap();
    let known_ids = HashSet::from(["e0001"]);
    let fact = decode().bind(&HashMap::from([("e0001",&source)]),&known_ids).unwrap();
    assert_eq!(fact.placement,Placement::Topic);
    assert!(fact.text.contains("举例"));
    source["text"] = json!("本次会议已决定购买这辆车。");
    assert!(decode().bind(&HashMap::from([("e0001",&source)]),&known_ids).is_err());
}

fn bind_answered_loan_amount(item: &mut SourceItem, cue: &SourceCue, evidence: &[Value]) -> bool {
    if cue.aspect.is_some() || !matches!(item.role, Role::Opinion | Role::Status)
        || item.evidence.len() >= 8 || item.evidence.contains(&cue.evidence)
    {
        return false;
    }
    let Some(amount) = explicit_yuan_amount(&cue.span) else { return false; };
    if !measures(&item.text).any(|(value, unit)| value == amount && unit == "元")
        || !item.text.contains("借") || !item.text.contains("成立")
        || ["不成立", "未成立", "能否成立", "是否成立", "成立吗"].iter().any(|term| item.text.contains(term))
    {
        return false;
    }
    let Some(position) = evidence.iter().position(|row| row["id"] == cue.evidence) else { return false; };
    let Some(reply) = evidence.get(position + 1).filter(|row| row["source"] == evidence[position]["source"])
    else { return false; };
    let split = |row: &Value| row["text"].as_str()
        .and_then(super::super::source_resolution::split_turn_label)
        .map(|(speaker, text)| (speaker.to_owned(),text.trim().to_owned()));
    let (Some((asked_by, question)),Some((answered_by, answer))) = (split(&evidence[position]),split(reply))
    else { return false; };
    let question = question.trim_end_matches(['？','?','。']);
    if answered_by == asked_by || !question.contains("借")
        || !question.strip_suffix("成立吗").is_some_and(|body| body.trim_end().ends_with(&cue.span))
        || !answer.strip_prefix("成立").is_some_and(|rest| rest.is_empty()
            || rest.starts_with(char::is_whitespace) || rest.starts_with(['，','。','！']))
    {
        return false;
    }
    let Some(reply_at) = item.evidence.iter().position(|id| reply["id"] == id.as_str()) else { return false; };
    item.evidence.insert(reply_at,cue.evidence.clone());
    true
}

#[cfg(test)]
#[test]
fn the_amount_in_an_answered_loan_question_retains_both_speaking_turns() {
    let evidence = [
        json!({"id":"e0039","source":"u001","text":"说话人2: 没有最大额度"}),
        json!({"id":"e0040","source":"u001","text":"说话人3: 他借了我两万块钱成立吗"}),
        json!({"id":"e0041","source":"u001","text":"说话人2: 成立 这属于如果他不还可以向法院起诉"}),
    ];
    let cue=SourceCue{id:"v002".into(),evidence:"e0040".into(),span:"两万块钱".into(),aspect:None};
    let item:SourceItem=serde_json::from_value(json!({"role":"status",
        "text":"有人回答借两万块钱也成立，并说明没有最大额度。","evidence":["e0039","e0041"],"owner":null,"due":null})).unwrap();
    let mut fixed=item.clone();
    assert!(bind_answered_loan_amount(&mut fixed,&cue,&evidence));
    assert_eq!(fixed.evidence,["e0039","e0040","e0041"]);
    let mut disputed=evidence.clone();
    disputed[2]["text"]=json!("说话人2: 不成立。");
    assert!(!bind_answered_loan_amount(&mut item.clone(),&cue,&disputed));
    disputed[2]["text"]=json!("说话人3: 成立。");
    assert!(!bind_answered_loan_amount(&mut item.clone(),&cue,&disputed));
}

fn bind_retrospective_context(item: &mut SourceItem, cue: &SourceCue, evidence: &[Value]) -> bool {
    // A calendar question supplies context for its immediately following answer.
    // It does not itself support the new facts stated in the answer.
    if cue.aspect.is_some() || cue.span != "半年"
        || !matches!(item.role, Role::Status | Role::Opinion | Role::Recommendation)
    {
        return false;
    }
    let Some(at) = evidence.iter().position(|row| row["id"] == cue.evidence.as_str()) else { return false; };
    let source = evidence[at]["text"].as_str().unwrap();
    let period = ["上半年", "下半年"].into_iter().find(|period| source.contains(period));
    if !period.is_some_and(|period| item.text.contains(period))
        || !["什么样", "如何", "怎么样"].iter().any(|phrase| source.contains(phrase))
    {
        return false;
    }
    let adjacent = evidence.iter().skip(at + 1).take(4).any(|row| {
        let id = row["id"].as_str().unwrap();
        item.evidence.iter().any(|given| given == id)
            && row["source"] == evidence[at]["source"]
    });
    if adjacent && item.evidence.len() < 8 {
        item.evidence.push(cue.evidence.clone());
        return true;
    }
    false
}

fn named_instruction_owner<'a>(cue: &SourceCue, original: &str, evidence: &'a [Value]) -> Option<&'a str> {
    let (before, _) = original.split_once(cue.span.as_str())?;
    let mut owners = evidence.iter().take(24).filter_map(|row| {
        let text = row["text"].as_str()?.trim();
        let (_, introduction) = super::super::source_resolution::split_turn_label(text)?;
        let (_, name) = introduction.split_once("我是")?;
        let name = name.trim().trim_end_matches(['。', '，', ',', '！']);
        if !(2..=14).contains(&name.chars().count()) || !name.chars().all(|ch| ('㐀'..='鿿').contains(&ch)) {
            return None;
        }
        let (_, after) = before.rsplit_once(name)?;
        let after = after.trim_start();
        (["这边", "这块", "这一块", "这里"].iter().any(|cue| after.starts_with(cue))
            && after.chars().count() <= 55 && !after.contains(['。', '；', '\n'])
            && !["不需要", "不用", "建议", "是否", "不必"].iter().any(|cue| after.contains(cue)))
            .then_some(name)
    });
    let one = owners.next()?;
    owners.all(|candidate| candidate == one).then_some(one)
}

fn retain_requests_before_questions(facts: &mut Vec<Fact>, evidence: &[Value]) -> Vec<String> {
    let by_id: HashMap<_, _> = evidence.iter().map(|row| (row["id"].as_str().unwrap(), row)).collect();
    let mut additions = Vec::new();
    let mut covered: HashSet<_> = facts.iter().filter(|fact| fact.placement == Placement::Action)
        .flat_map(|fact| fact.evidence.iter().cloned()).collect();
    for fact in facts.iter().filter(|fact| fact.placement == Placement::Question) {
        if facts.len() + additions.len() == FACT_LIMIT {
            break;
        }
        let candidate = fact.evidence.iter().filter(|id| !covered.contains(*id)).find_map(|id| {
            let original = by_id.get(id.as_str())?["text"].as_str()?;
            let (aspect, span) = ordinary_source_aspect(original)?;
            if aspect != "交办后又提问" || ["如果", "假如", "是否", "建议先", "要不要", "打算"]
                .iter().any(|term| original.contains(term)) {
                return None;
            }
            let cue = SourceCue { id:String::new(), evidence:id.clone(), span:span.to_owned(), aspect:Some(aspect) };
            let owner = named_instruction_owner(&cue, original, evidence)?;
            let (before, _) = original.split_once(span)?;
            let (_, qualifier) = before.rsplit_once(owner)?;
            let text = format!("{owner}{qualifier}{span}。");
            line(&text, 90).then_some(Fact {
                id:format!("{}-request",fact.id), kind:Kind::Decision, placement:Placement::Action,
                text, owner:Some(owner.to_owned()), due:None, evidence:vec![id.clone()],
            })
        });
        if let Some(action) = candidate {
            covered.extend(action.evidence.iter().cloned());
            additions.push(action);
        }
    }
    let ids = additions.iter().map(|fact| fact.id.clone()).collect();
    facts.extend(additions);
    ids
}

fn retain_instruction_clause(item: &mut SourceItem, cue: &SourceCue, original: &str, evidence: &[Value]) {
    if cue.aspect != Some("交办后又提问") || !matches!(item.role, Role::Action) {
        return;
    }
    let bound = ["随后再次询问", "随后询问", "随后问", "同时询问", "并询问", "然后再问"]
        .iter().filter_map(|cue| item.text.find(cue)).min();
    if let Some(prefix) = bound.map(|at| item.text[..at].trim_end_matches(['，', ',', '；', ' ', '。']))
        .filter(|prefix| prefix.chars().count() >= 8)
    {
        item.text = format!("{prefix}。");
    }
    if item.owner.is_some() {
        return;
    }
    let Some(owner) = named_instruction_owner(cue, original, evidence) else { return; };
    let mut actions = ["调查", "核实", "核对", "核查", "整理", "审查", "准备", "检查", "协调", "提交"]
        .into_iter().filter(|verb| cue.span.contains(verb));
    let Some(action) = actions.next().filter(|_| actions.next().is_none()) else { return; };
    let mut clauses = item.text.split(['，', ',', '；']).filter(|clause| clause.contains(action));
    if let Some(clause) = clauses.next().filter(|_| clauses.next().is_none()) {
        let clause = clause.trim();
        if line(clause, 90) && !clause.starts_with(['不', '没', '勿']) {
            item.text = clause.to_owned();
            item.owner = Some(owner.to_owned());
        }
    }
}

#[cfg(test)]
#[test]
fn a_named_group_owns_only_the_directed_clause_before_a_question() {
    let evidence = [
        json!({"id":"e0000","text":"说话人4: 零二四我是质量部"}),
        json!({"id":"e0001","text":"说话人2: 零二七我是供应部"}),
    ];
    let original = "说话人1: 维持照常发货，质量部这一块儿对设备异常要进行一次调查 你觉得有哪些情况？";
    let (_, span) = ordinary_source_aspect(original).unwrap();
    let cue = SourceCue { id:"v000".into(),evidence:"e0002".into(),span:span.into(),aspect:Some("交办后又提问") };
    let mut item: SourceItem = serde_json::from_value(json!({"role":"action","text":"维持照常发货，对设备异常进行调查，随后询问还有哪些情况。","evidence":["e0002"]})).unwrap();
    retain_instruction_clause(&mut item,&cue,original,&evidence);
    assert_eq!(item.owner.as_deref(),Some("质量部"));
    assert_eq!(item.text,"对设备异常进行调查。");
    assert!(ordinary_source_aspect("说话人1: 质量部不要进行调查 你觉得还有什么问题？").is_none());
}

fn quoted_draft_claim<'a>(text: &str, source: &str, claims: &'a [Value]) -> Option<&'a Value> {
    let tail = ["正文写“", "纪要写“", "纪要中写“"].into_iter()
        .find_map(|marker| text.split_once(marker).map(|(_, tail)| tail))?;
    let (quote, _) = tail.split_once('”')?;
    if !line(quote, 90) || quote.chars().filter(|ch| ch.is_alphanumeric()).count() < 6 {
        return None;
    }
    // The model is identifying language in its own draft. A literal target,
    // uniquely present in the draft and related to the cited speech, is
    // required before its objection can affect another displayed row.
    let glyphs: Vec<_> = quote.chars().collect();
    let source = normalized(source);
    if !glyphs.windows(3).any(|part| part.iter().all(|ch| ch.is_alphanumeric())
        && source.contains(&part.iter().collect::<String>()))
    {
        return None;
    }
    let mut hits = claims.iter().filter(|claim| claim.get("sources").is_some()
        && claim["text"].as_str().is_some_and(|text| text.contains(quote)));
    let found = hits.next()?;
    hits.next().is_none().then_some(found)
}

fn checked_additions(missing: MissingItems, cues: &[SourceCue], doc: &Document, facts: &[Fact], evidence: &[Value],
    verified_coverage: &HashSet<String>)
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
                if cue.aspect.is_none() && !verified_coverage.contains(&cue.id)
                    && !contextual_measure_witness(&cue.span, existing, known[cue.evidence.as_str()])
                {
                    return Err(fail());
                }
            }
            SourceCheck::Conflict { claim, .. } => {
                let existing = by_path.get(claim.as_str()).ok_or_else(fail)?;
                conflicts.push(json!({"claim":existing, "evidence":cue.evidence}));
            }
            check @ (SourceCheck::Missing { .. } | SourceCheck::NeedsReview { .. }) => {
                let review = matches!(check, SourceCheck::NeedsReview { .. });
                let (SourceCheck::Missing { mut addition, .. } | SourceCheck::NeedsReview { mut addition, .. }) = check else {
                    unreachable!()
                };
                let cited = addition.item.evidence.iter().any(|id| {
                    factual_audit::canonical_sentence_reference(id, &known_ids).as_deref() == Some(cue.evidence.as_str())
                });
                let contextual = !cited && !review && bind_retrospective_context(&mut addition.item, cue, evidence);
                if (!cited && !contextual) || (review && (!matches!(addition.item.role, Role::Status | Role::Question)
                    || !addition.item.text.starts_with("待核实")))
                {
                    return Err(fail());
                }
                if review {
                    if let Some(claim) = quoted_draft_claim(
                        &addition.item.text, known[cue.evidence.as_str()], &claims,
                    ) {
                        conflicts.push(json!({"claim":claim, "evidence":cue.evidence}));
                    }
                }
                retain_instruction_clause(&mut addition.item, cue, known[cue.evidence.as_str()], evidence);
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
    let mut seen_conflicts = HashSet::new();
    conflicts.retain(|conflict| seen_conflicts.insert((
        conflict["claim"]["path"].as_str().unwrap().to_owned(),
        conflict["evidence"].as_str().unwrap().to_owned(),
    )));
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
    let mut input = json!({"sourceSentences":evidence,"currentBrief":doc,"lexicalCues":cues,"claimEvidence":bindings});
    if cues.iter().any(|cue| cue.aspect.is_some()) {
        let common = "每条 aspect 核对的是引用中单独的含义。实际进展区分已做与正在做；交办和提问分开。限定和例外要保留适用情形；已发生的处置不能改成建议；交办范围要与相应待办相连。负责人和期限只写原话明确的内容。";
        let scoped = cues.iter().any(|cue| matches!(cue.aspect.as_deref(), Some("会议安排的时间范围" | "明确确认的进展或方案")));
        input["aspectInstructions"] = if scoped {
            json!(format!("{common}会议安排的时间范围要和其议题一起保留，不能当成任务的完成日期。明确确认的进展或方案应保留谁确认了什么和实际状态；连续提议、客套回应或假设仍按原话处理。"))
        } else { json!(common) };
    }
    let raw = super::request(endpoint, model, key, client, FIND_MISSING,
        input, false, start, trace, "source-items-omissions")?;
    let scan_index = trace.len() - 1;
    trace[scan_index]["omissionCues"] = json!(cues);
    let claim_values = factual_audit::claims(&doc);
    let claim_paths: HashSet<_> = claim_values.iter().filter(|value| value.get("sources").is_some())
        .filter_map(|value| value["path"].as_str()).collect();
    let expected_ids = cues.iter().map(|cue| cue.id.as_str()).collect();
    let mut checked = parse_source_check_packet(&raw, &expected_ids, &mut trace[scan_index])?;
    let duplicates = checked.coalesce_identical_checks(&claim_paths);
    if duplicates > 0 { trace[scan_index]["identicalChecksCoalesced"] = json!(duplicates); }
    let deferred = checked.defer_unrequested_omissions(&expected_ids);
    if !deferred.is_empty() { trace[scan_index]["deferredUnrequestedOmissionIds"] = json!(deferred); }
    restore_source_context_for_coverage(&mut checked.checks, &cues, &claim_values, &evidence, &bindings);
    let disputed = disputed_coverage(&checked, &cues, &doc, &evidence, &bindings);
    let mut verified_coverage = HashSet::new();
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
        let mut fixed = parse_source_check_packet(&raw, &selected, trace.last_mut().unwrap())?;
        let duplicates = fixed.coalesce_identical_checks(&claim_paths);
        if duplicates > 0 { trace.last_mut().unwrap()["identicalChecksCoalesced"] = json!(duplicates); }
        let returned: HashSet<_> = fixed.checks.iter().map(SourceCheck::id).collect();
        if returned != selected || fixed.checks.len() != selected.len() || !fixed.additions.is_empty() {
            return Err("纪要存在未完成的关键原话覆盖复核，已有结果保留。".into());
        }
        let opening = retain_opening_scope(&mut fixed.checks, &disputed, &doc, &evidence);
        if opening > 0 {
            trace.last_mut().unwrap()["openingScopeRetainedInPurpose"] = json!(opening);
        }
        let mut rejected = rejected_coverage(&fixed.checks, &disputed, &doc, &evidence, &bindings);
        let mut refund_witnesses = Vec::new();
        rejected.retain(|issue| {
            let cue = &issue["cue"];
            let (Some(id), Some(anchor), Some(span)) =
                (cue["id"].as_str(), cue["evidence"].as_str(), cue["span"].as_str()) else { return true; };
            if !matches!(span, "一年" | "半季度") ||
                !fixed.checks.iter().any(|check| matches!(check, SourceCheck::Covered { id: covered, .. } if covered == id))
            {
                return true;
            }
            let Some(source) = evidence.iter().find(|row| row["id"] == anchor)
                .and_then(|row| row["text"].as_str()) else { return true; };
            let mut matches = claim_values.iter().filter_map(|claim| {
                let path = claim["path"].as_str()?;
                let text = claim["text"].as_str()?;
                (bindings.get(path).is_some_and(|ids| ids.iter().any(|id| id == anchor))
                    && super::source_corrections::retained_refund_measure(span, text, source)).then_some(path)
            });
            let Some(path) = matches.next() else { return true; };
            if matches.next().is_some() { return true; }
            refund_witnesses.push((id.to_owned(), path.to_owned()));
            false
        });
        if !refund_witnesses.is_empty() {
            for (id, path) in &refund_witnesses {
                if let Some(SourceCheck::Covered { claim, proof, .. }) =
                    fixed.checks.iter_mut().find(|check| check.id() == id)
                {
                    *claim = path.clone();
                    *proof = None;
                }
            }
            trace.last_mut().unwrap()["refundPeriodCoverage"] = json!(refund_witnesses);
        }
        let acknowledgments: Vec<_> = rejected.iter().filter_map(|issue| retain_acknowledgment(issue, &evidence)).collect();
        if !acknowledgments.is_empty() {
            let retained: HashSet<_> = acknowledgments.iter().map(SourceCheck::id).collect();
            rejected.retain(|issue| !issue["cue"]["id"].as_str().is_some_and(|id| retained.contains(id)));
            fixed.checks.retain(|check| !retained.contains(check.id()));
            trace.last_mut().unwrap()["retainedAcknowledgments"] = json!(retained);
            fixed.checks.extend(acknowledgments);
        }
        if !rejected.is_empty() {
            let ids: HashSet<_> = rejected.iter().filter_map(|row| row["cue"]["id"].as_str()).collect();
            let raw = super::request(endpoint,model,key,client,REPAIR_COVERAGE,
                json!({"sourceSentences":context,"sourceCoverageRepair":rejected,"currentBrief":doc}),
                false,start,trace,"source-items-coverage-repair")?;
            let syntax_repaired = normalize_check_delimiter(&raw);
            let body = syntax_repaired.as_ref().map_or(raw.as_str(), |(body, _)| body.as_str());
            let (mut repair, restored) = parse_coverage_repair(body, &rejected, &evidence)?;
            if let Some((_, operation)) = syntax_repaired {
                trace.last_mut().unwrap()[operation] = json!(true);
            }
            if restored > 0 {
                trace.last_mut().unwrap()["groundedBackgroundReasons"] = json!(restored);
            }
            let duplicates = repair.coalesce_identical_checks(&claim_paths);
            if duplicates > 0 { trace.last_mut().unwrap()["identicalChecksCoalesced"] = json!(duplicates); }
            let opening = retain_opening_scope(&mut repair.checks, &rejected, &doc, &evidence);
            if opening > 0 {
                trace.last_mut().unwrap()["openingScopeRetainedInPurpose"] = json!(opening);
            }
            let money = recover_monetary_coverage(&mut repair.checks, &rejected, &doc, &evidence, &bindings);
            if !money.is_empty() {
                trace.last_mut().unwrap()["resolvedMonetaryCoverage"] = json!(money);
            }
            let returned: HashSet<_> = repair.checks.iter().map(SourceCheck::id).collect();
            let mut unresolved = rejected_coverage(&repair.checks, &rejected, &doc, &evidence, &bindings);
            unresolved.retain(|issue| !money.iter().any(|resolved| resolved["id"] == issue["cue"]["id"]));
            trace.last_mut().unwrap()["unresolvedCoverage"] = json!(unresolved);
            if returned != ids || repair.checks.len() != ids.len() || !repair.additions.is_empty()
                || !unresolved.is_empty() || !preserves_related_cause(&repair.checks, &rejected) {
                return Err("纪要存在未完成的关键原话覆盖复核，已有结果保留。".into());
            }
            fixed.checks.retain(|row| !ids.contains(row.id()));
            fixed.checks.extend(repair.checks);
        }
        // Pass the successful quoted recheck into final assembly. Looking only
        // at the original numeric span here would discard the accepted proof.
        verified_coverage.extend(fixed.checks.iter().filter_map(|check| match check {
            SourceCheck::Covered { id, .. } => Some(id.clone()),
            _ => None,
        }));
        checked.checks.retain(|check| !selected.contains(check.id()));
        checked.checks.extend(fixed.checks);
    }
    let mut rebound = Vec::new();
    let mut answered_amounts = Vec::new();
    for check in &mut checked.checks {
        let SourceCheck::Missing { id, addition } = check else { continue; };
        let Some(cue) = cues.iter().find(|cue| cue.id == *id) else { continue; };
        if bind_answered_loan_amount(&mut addition.item, cue, &evidence) {
            answered_amounts.push(json!({"cue":id,"evidence":addition.item.evidence}));
            continue;
        }
        let Some(claim) = repeated_delay_witness(cue, addition, &claim_values, &evidence, &bindings)
        else { continue; };
        verified_coverage.insert(id.clone());
        rebound.push(json!({"cue":id,"claim":claim}));
        *check = SourceCheck::Covered { id:id.clone(), claim, proof:None };
    }
    if !rebound.is_empty() {
        trace[scan_index]["reboundRepeatedDelayReferences"] = json!(rebound);
    }
    if !answered_amounts.is_empty() {
        trace[scan_index]["boundAdjacentLoanQuestions"] = json!(answered_amounts);
    }
    let (mut additions, conflicts) = checked_additions(checked, &cues, &doc, facts, &evidence, &verified_coverage)?;
    let decisions: Vec<_> = doc.decisions.iter().map(|item| item.text.as_str()).collect();
    let mut removed = 0;
    let mut separated = 0;
    if !decisions.is_empty() && additions.iter().any(|row| row.item.text.contains("超过")) {
        let labelled = super::commitments::with_turn_labels(&evidence);
        additions.retain_mut(|row| {
            use super::source_corrections::{disposal_echo, DisposalEcho};
            match disposal_echo(&row.item.text, &row.item.evidence, &decisions, &labelled) {
                Some(DisposalEcho::Drop) => { removed += 1; false }
                Some(DisposalEcho::RetainSeparateClause(text, refs)) => {
                    row.item.text = text;
                    row.item.evidence = refs;
                    separated += 1;
                    true
                }
                None => true,
            }
        });
    }
    if removed + separated != 0 {
        trace[scan_index]["disposalDuplicatesReconciled"] = json!({"removed":removed,"separated":separated});
    }
    trace[scan_index]["boundAdditions"] = json!(additions.len());
    trace[scan_index]["conflictingClaims"] = json!(conflicts);
    Ok(CheckedOmissions { doc: append_missing(additions, doc, units, &evidence)?, conflicts })
}

pub(super) fn generate(endpoint: &str, model: &str, key: &str, client: &reqwest::blocking::Client,
    units: &[Unit], start: Instant, trace: &mut Vec<Value>) -> Result<(Document, Vec<Fact>), String>
{
    let evidence = factual_audit::evidence_sentences(units);
    let mut facts = Vec::new();
    let mut context = Vec::new();
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
                        Ok((checked.facts, checked.context))
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
            let (window_facts, window_context) = items?;
            facts.extend(window_facts);
            context.extend(window_context);
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
    let (doc, projection, facts) = organize(&raw, &facts, units, &context)?;
    if let Some(last) = trace.last_mut() {
        last["layoutProjection"] = projection;
    }
    Ok((doc, facts))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn completion_and_courtesy_closing_do_not_become_assignments() {
        let report = "我给教练这些人开了一个专门儿开开了一个会，就是告诉对方要了解情况。";
        assert!(completed_report("教练部已专门开会，要求教练了解孩子情况。", &[report]));
        assert!(!completed_report("教练部已专门开会，后续继续培训。", &[report]));
        assert!(!completed_report("教练部已专门开会，要求教练了解孩子情况。", &["我没开了会。"]));
        assert!(contingent_closing("有机会再请专家交流。", &["那今天先到这儿，有机会再请专家，散会。"]));
        assert!(!contingent_closing("有机会再请专家交流。", &["今天先到这儿，有机会再请专家。会后由我约。"]));
        let mut item = Fact { id:"a000".into(),kind:Kind::Decision,placement:Placement::Action,
            text:"应要求科普生活中的法律常识。".into(),owner:None,due:None,evidence:vec!["e0000".into()] };
        let evidence = [json!({"id":"e0000","text":"说话人5: 想嗯想让他科普一下儿常识。"}),
            json!({"id":"e0001","text":"说话人2: 对给大家普及一个知识。"})];
        assert!(reconcile_spoken_scope(std::slice::from_mut(&mut item), &evidence[..1]).is_empty());
        assert_eq!(reconcile_spoken_scope(std::slice::from_mut(&mut item), &evidence), ["a000"]);
        assert_eq!(item.placement, Placement::Topic);
        assert!(item.text.contains("想嗯想让他科普一下儿常识"));
    }

    #[test]
    fn only_an_answer_supported_by_a_different_turn_moves_a_question_to_discussion() {
        let evidence = [
            json!({"id":"e0012","source":"u000","text":"主持人：嗯现在是在线上？"}),
            json!({"id":"e0014","source":"u000","text":"教务：嗯是咱们这儿是线上教学呃"}),
        ];
        let report = "校长询问目前线上教学情况，教务确认已改线上教学。";
        let mut fact = Fact {id:"a003".into(), kind:Kind::Status, placement:Placement::Question,
            text:report.into(), owner:None, due:None, evidence:vec!["e0012".into(),"e0014".into()]};
        assert_eq!(reconcile_spoken_scope(std::slice::from_mut(&mut fact), &evidence), ["a003"]);
        assert_eq!(fact.placement, Placement::Topic);
        assert_eq!(fact.text, report);

        let cited = evidence.iter().collect::<Vec<_>>();
        assert!(!answered_question(report, &cited[..1]));
        assert!(!answered_question("校长询问目前线上教学情况，教务确认已改线上教学，最终安排仍需确认。", &cited));
        let unrelated = json!({"id":"e0014","source":"u000","text":"教务：下一节讨论排课。"});
        assert!(!answered_question(report, &[&evidence[0], &unrelated]));

        let doc: Document = serde_json::from_value(json!({"purpose":"教学安排", "topics":[{
            "title":"教学安排","points":[{"kind":"status","text":"本周检查教学安排。","sources":["u000"]}]
        }],"decisions":[],"actionItems":[],"questions":[]})).unwrap();
        let addition = parse(&json!({"topic":"教学安排","item":{"role":"question","text":report,
            "evidence":["e0012","e0014"],"owner":null,"due":null}}).to_string()).unwrap();
        let units = [Unit{id:"u000".into(),text:"主持人：嗯现在是在线上？\n教务：嗯是咱们这儿是线上教学呃".into()}];
        let after = append_missing(vec![addition], doc, &units, &evidence).unwrap();
        assert!(after.questions.is_empty());
        assert_eq!(after.topics[0].details[0].text, report);
    }

    #[test]
    fn an_agenda_change_stays_in_discussion_but_later_commitments_keep_their_type() {
        let make = |text: &str, placement| Fact {id:"a000".into(),kind:Kind::Decision,placement,
            text:text.into(),owner:None,due:None,evidence:vec!["e0000".into()]};
        let agenda = make("主持人将招聘问题留待后续讨论，当前先问后勤对方案的看法。", Placement::Decision);
        let quote = "行那咱一会儿在讨论这个后勤这个你就说这个";
        assert!(live_agenda(&agenda, &[quote]));
        assert!(!live_agenda(&agenda, &["咱们下周再讨论这个后勤，这次先通过方案。"]));
        assert!(!live_agenda(&agenda, &["我们讨论过后勤方案。"]));
        let now = make("当前先谈要办什么项目，活动策划放到后面。",Placement::Decision);
        assert!(live_agenda(&now, &["咱们先谈谈要办什么东西，搞什么项目"]));
        let opening = make("召开项目启动会，各部门提出建议，先讨论选址。", Placement::Action);
        assert!(live_agenda(&opening, &["今天把各部门叫过来，咱们开一个启动会，咱们先说一下选址"]));
        let assigned = make("会后由项目部召开项目启动会，先讨论选址。", Placement::Action);
        assert!(!live_agenda(&assigned, &["今天把各部门叫过来，咱们开一个启动会，咱们先说一下选址"]));
    }

    #[test]
    fn a_pending_objection_needs_a_unique_literal_draft_quote_and_relevant_speech() {
        let text = "待核实住宿费范围：原话说退半学年，正文写“退了半年住宿费的一半”，范围不同。";
        let speech = "住宿费退一半儿，因为这半个学年没有住。";
        let claims = [
            json!({"path":"topics[0].points[0]","text":"目前只退了半年住宿费的一半。","sources":["u000"]}),
            json!({"path":"topics[0].points[1]","text":"住宿费已经退还。","sources":["u000"]}),
        ];
        assert_eq!(quoted_draft_claim(text, speech, &claims).unwrap()["path"], "topics[0].points[0]");
        assert!(quoted_draft_claim(text, "下周检查所有设备。", &claims).is_none());
        assert!(quoted_draft_claim(&text.replace("正文写", "有人说"), speech, &claims).is_none());
        assert!(quoted_draft_claim(text, speech, &[claims[0].clone(),claims[0].clone()]).is_none());
    }

    #[test]
    fn example_correction_keeps_literal_words_and_nearby_reporting() {
        let source = json!({"id":"e0000","turnSpeaker":"说话人2",
            "text":"说话人2: 我举个例子，常规方案就是 我们先冻结存量，然后立即恢复，实际上就是应急方案 就是第二种"});
        let corrected = reported_context("发言人举例：冻结存量后立即恢复属常规方案；另一种是测试流程。", &[&source]).unwrap();
        assert!(corrected.contains("我们先冻结存量，然后立即恢复，实际上就是应急方案"));
        assert!(corrected.contains("另一种是测试流程"));
        assert!(reported_context("发言人举例：冻结存量后立即恢复属于应急方案。", &[&source]).is_none());
        assert!(reported_context("未核实的数据还会再确认。", &[&source]).is_none());
        let question = json!({"text":"说话人1: 是不是七年，对不对"});
        let answer = json!({"text":"说话人2: 我觉得七年，之后不承担责任"});
        assert_eq!(reported_context("七年后不承担责任。", &[&question,&answer]).as_deref(),
            Some("说话人2称，七年后不承担责任。"));
    }

    #[test]
    fn repair_can_read_provider_claim_objects_and_report_requirements() {
        let check: SourceCheck = parse(r#"{"status":"covered","id":"v001","claim":{"path":"topics[0].points[0]","text":"任意回显"}}"#).unwrap();
        assert!(matches!(check, SourceCheck::Covered { claim, .. } if claim == "topics[0].points[0]"));
        let original = json!({"id":"e0011","text":"主持人：请保留原票，报销还需要票据。"});
        let item: SourceItem = parse(r#"{"role":"requirement","text":"报销还需要票据。","evidence":["e0011"]}"#).unwrap();
        let bound = item.bind(&HashMap::from([("e0011", &original)]), &HashSet::from(["e0011"])).unwrap();
        assert_eq!(bound.placement, Placement::Topic);
        assert_eq!(bound.text, "会上提出：报销还需要票据。");
    }

    #[test]
    fn acknowledged_plan_preserves_the_direct_quote_when_its_point_only_says_suggested() {
        let evidence = [json!({"id":"e0020","text":"经理：行就保留打印版。"})];
        let reason = json!({"cue":{"id":"v001","aspect":"明确确认的进展或方案","evidence":"e0020","span":"行就保留打印版"},
            "rejectedWitness":{"kind":"recommendation"},"rejectedWitnessEvidence":["e0020"]});
        let result = retain_acknowledgment(&reason, &evidence);
        assert!(matches!(result, Some(SourceCheck::Missing { addition, .. }) if addition.item.text == "经理回应「行就保留打印版」。"));
        let mut unrelated = reason;
        unrelated["rejectedWitnessEvidence"] = json!(["e9999"]);
        assert!(retain_acknowledgment(&unrelated, &evidence).is_none());
    }

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
        let (document, _, _) = organize(&layout.to_string(), &facts, &units, &[]).unwrap();
        assert_eq!(document.action_items.len(), 2);
        assert_eq!(document.action_items[0].owner.as_deref(), Some("采购组"));
        assert_eq!(document.action_items[1].owner.as_deref(), Some("质检组"));
        assert!(organize(&layout.to_string().replace("a000","a001"), &facts, &units, &[]).is_err());
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
    fn provider_suggestion_alias_remains_a_recommendation() {
        let parsed: Role = serde_json::from_value(json!("suggestion")).unwrap();
        assert!(matches!(parsed.category(), (Kind::Recommendation, Placement::Topic)));
        assert!(serde_json::from_value::<Role>(json!("maybe_decision")).is_err());
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
        let (assembled, projection, _) = organize(&raw, &facts, &units, &[]).unwrap();
        assert_eq!(assembled.topics[0].points.len(), 3);
        assert_eq!(projection["restoredTopicIds"], json!(["a004"]));
        assert_eq!(projection["movedToDetails"], json!(["a003"]));
        assert_eq!(assembled.topics[0].details[0].text, facts[3].text);
        assert_eq!(assembled.topics[0].details[1].text, facts[4].text);
        assert!(organize(&raw.replace("a003","a999"), &facts, &units, &[]).is_err());
    }

    #[test]
    fn crowded_topic_keeps_its_assigned_details_under_the_document_budget() {
        let units = vec![Unit {id:"u000".into(),text:"讨论供货安排。".into()}];
        let facts: Vec<_> = (0..28).map(|index| Fact {
            id:format!("a{index:03}"),kind:Kind::Status,placement:Placement::Topic,
            text:format!("原话条目{index}。"),owner:None,due:None,evidence:vec!["e0000".into()],
        }).collect();
        let selected: Vec<_> = facts[1..27].iter().map(|fact| &fact.id).collect();
        let raw = json!({"purpose":"讨论供货","topics":[
            {"title":"供货安排","points":["a000"],"details":selected},
            {"title":"费用审批","points":["a027"],"details":[]}
        ]});
        let (doc, _, _) = organize(&raw.to_string(), &facts, &units, &[]).unwrap();
        assert_eq!(doc.topics[0].details.len(), 26);
        assert_eq!(doc.topics[0].details.last().unwrap().text, facts[26].text);
        assert!(doc.topics[1].details.is_empty());
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
        assert!(checked_additions(parse(r#"{"additions":[]}"#).unwrap(), &cues, &doc, &facts, &evidence, &HashSet::new()).is_err());
        let false_coverage = parse(r#"{"checks":[{"id":"v000","status":"covered","claim":"topics[0].points[0]"}],"additions":[]}"#).unwrap();
        assert_eq!(disputed_coverage(&false_coverage, &cues, &doc, &evidence, &HashMap::new()).len(), 1);
        assert!(checked_additions(false_coverage, &cues, &doc, &facts, &evidence, &HashSet::new()).is_err());
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
        let (additions, conflicts) = checked_additions(parse(&reply.to_string()).unwrap(), &cues, &doc, &facts, &evidence, &HashSet::new()).unwrap();
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
