//! Select material source clauses the first extraction may have lost.
use std::{collections::HashMap, sync::LazyLock};
use regex::Regex;
use serde_json::Value;
use super::{Kind, answer_layout::{Fact, Placement}, line, normalized};

#[derive(Clone, Copy, Eq, Hash, PartialEq)]
enum Focus {
    Contrast,
    Restriction,
    CompletedChange,
    PlanScope,
    Practice,
    CalendarScope,
    AcceptedProposal,
}

impl Focus {
    const ORDER: [Self; 7] = [
        Self::Contrast, Self::CompletedChange, Self::PlanScope, Self::Restriction,
        Self::Practice, Self::CalendarScope, Self::AcceptedProposal,
    ];

    fn label(self) -> &'static str {
        match self {
            Self::Contrast => "不同情形的限定",
            Self::Restriction => "明确限制",
            Self::CompletedChange => "已发生的变更或处置",
            Self::PlanScope => "交办的内容范围",
            Self::Practice => "实际做法",
            Self::CalendarScope => "会议安排的时间范围",
            Self::AcceptedProposal => "明确确认的进展或方案",
        }
    }
}

fn source_body(text: &str) -> &str {
    super::super::source_resolution::split_turn_label(text)
        .map_or(text, |(_, body)| body).trim()
}

pub(super) fn corrected_example(source: &str, summary: &str) -> Option<String> {
    static CORRECTION: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:举个例子|举一个例子|举例)[，,：:\s]*(?P<announced>[\p{Han}]{3,12}?)(?:就是|是)[\s，,]*(?P<case>[^。！？；\n]{5,76}?)(?:实际上|其实)(?:就是|是)(?P<conclusion>[\p{Han}]{3,12}?)(?:\s|[，,。；！？]|$)"
    ).unwrap());
    let example = CORRECTION.captures(source_body(source))?;
    let announced = example.name("announced")?.as_str();
    let conclusion = example.name("conclusion")?;
    if announced == conclusion.as_str()
        || announced.ends_with(conclusion.as_str()) || conclusion.as_str().ends_with(announced)
    {
        return None;
    }
    // Only the opening assertion is qualified. A different conclusion in a
    // second example does not repair an inversion in this example.
    let statement = summary.split(['；', ';', '。']).next()?;
    if !["算", "属", "为", "是"].iter().any(|word| {
        let assertion = format!("{word}{announced}");
        statement.match_indices(&assertion).any(|(at, _)| {
            !statement[..at].ends_with(['不', '非', '未'])
        })
    }) {
        return None;
    }
    let from = example.name("case")?.start();
    let source = source_body(source);
    let quote = source[from..conclusion.end()].trim();
    (quote.chars().count() <= 65).then(|| quote.to_owned())
}

pub(super) fn omitted_reported_step<'a>(source: &'a str, summary: &str) -> Option<&'a str> {
    static REPORTED: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:我们|咱们)(?P<lead>(?:就是|是|会|先|通常|一般|经常|实际|还|也|都|[ \t]){1,5})(?P<step>(?:进行|采取|开展|办理)[\p{Han}]{4,28})"
    ).unwrap());
    static TRANSITION: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"然后|接着|随后|再(?:去|由|请|把|查|联系|记录|复核|通知)"
    ).unwrap());
    let body = source_body(source);
    let capture = REPORTED.captures(body)?;
    let reported = capture.get(0)?;
    let lead = body[..reported.start()].rsplit(['，', '。', '！', '？', '；']).next()?;
    if ["可以", "建议", "打算", "如果", "假设", "比如", "比方", "没有", "不是"]
        .iter().any(|marker| lead.contains(marker))
        || body[..reported.start()].trim_end().ends_with(['不', '没'])
    {
        return None;
    }
    let found = capture.name("step")?;
    let step = TRANSITION.split(found.as_str()).next()?;
    let tail = &body[found.start() + step.len()..];
    if (step == found.as_str() && tail.starts_with(char::is_alphanumeric))
        || (!tail.contains('先') && !capture.name("lead")?.as_str().contains('先'))
    {
        return None;
    }
    let meaning = normalized(step).replace("就是进行", "").replace("就是", "");
    let meaning = meaning.trim_start_matches("进行").trim_start_matches("采取")
        .trim_start_matches("开展").trim_start_matches("办理");
    if meaning.chars().count() < 4 || normalized(summary).contains(meaning) {
        return None;
    }
    // Require separate anchors from the ordered clauses. A single shared
    // word in a nearby discussion does not establish a partly retained process.
    let summary = normalized(summary);
    let witnessed: std::collections::HashSet<_> = TRANSITION.split(tail).filter_map(|clause| {
        let letters: Vec<_> = normalized(clause).chars().collect();
        letters.windows(3).filter(|part| part.iter().all(|ch| ch.is_alphanumeric()))
            .map(|part| part.iter().collect::<String>())
            .find(|part| summary.contains(part))
    }).collect();
    (witnessed.len() >= 2).then_some(step)
}

#[cfg(test)]
#[test]
fn reported_steps_require_a_partially_represented_process_and_literal_source() {
    let source = "说话人7: 对这个工作啊是我们就是进行上门就是进行调解纠纷 就是举报以后，我们是先通过查监控然后了解业主，然后咱们就是可以通过给他打电话，请他注意。";
    assert_eq!(omitted_reported_step(source, "物业应对投诉的流程是：查监控了解涉事业主，打电话提醒注意。"),
        Some("进行上门就是进行调解纠纷"));
    assert!(omitted_reported_step(source, "物业先查监控、打电话，也会上门调解纠纷。").is_none());
    assert!(omitted_reported_step(source, "物业发现视频记录问题。").is_none());
    let delivery = "我们通常先进行现场确认，然后记录编号，接着通知值班员。";
    assert_eq!(omitted_reported_step(delivery, "记录编号并通知值班员。"), Some("进行现场确认"));
    assert!(omitted_reported_step("如果我们通常先进行现场确认，然后记录编号，接着通知值班员。", "记录编号并通知值班员。").is_none());
}

fn calendar_end() -> &'static Regex {
    static PERIOD: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:一直到|持续到|延续到|截至|截止到|截止|到|至)[\s嗯呃]*(?P<month>1[012]|[1-9]|十一|十二|十|[一二三四五六七八九])\s*月(?:份儿?)?(?P<part>月底|底|初|上旬|中旬|下旬)?"
    ).unwrap());
    &PERIOD
}

fn accepted_proposal() -> &'static Regex {
    static ACCEPTED: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:^|[，。！？；\s])(?P<decision>(?:行[，,\s]*就|就按|同意采用|同意按|就这么定)[\p{Han}]{3,24})"
    ).unwrap());
    &ACCEPTED
}

fn month_end(text: &str) -> Option<(u8, &str)> {
    let captures = calendar_end().captures(text)?;
    let month = captures.name("month")?.as_str();
    let month = month.parse().ok().or_else(|| {
        ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二"]
            .iter().position(|value| *value == month).map(|index| index as u8 + 1)
    })?;
    let rest = text[captures.get(0)?.end()..].trim_start();
    // A day-specific limit is checked as a separate quantity, not as a month.
    if rest.starts_with(['0','1','2','3','4','5','6','7','8','9','一','二','三','四','五','六','七','八','九','十']) {
        return None;
    }
    Some((month, captures.name("part").map_or("", |part| part.as_str().trim_start_matches('月'))))
}

pub(super) fn facet_has_witness(aspect: &str, span: &str, kind: &str, claim: &str) -> bool {
    if aspect == Focus::CalendarScope.label() {
        return month_end(span).is_some_and(|end| month_end(claim) == Some(end));
    }
    if aspect == Focus::AcceptedProposal.label() {
        return kind == "decision" || (kind != "recommendation"
            && !["不同意", "不认可", "尚未确认", "等待确认", "有待确定", "待确认"].iter().any(|marker| claim.contains(marker))
            && ["同意", "认可", "确认采用", "已确定", "明确决定", "确定采用", "拍板"]
                .iter().any(|marker| claim.contains(marker)));
    }
    true
}

fn material_spans(text: &str) -> Vec<(Focus, &str)> {
    static CONTRAST: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?P<limit>[\p{Han}]{2,16}(?:时|时候|情况下)可以[嗯呃\s]*不[\p{Han}]{1,14})[，,]\s*但(?:是)?[^。；？！]{2,45}(?:必须|一定要|不得)"
    ).unwrap());
    static RESTRICTION: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?P<limit>(?:不能|不得|不许|不允许)[\p{Han}]{2,25})"
    ).unwrap());
    static CHANGE: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?P<change>(?:已经|直接把|就把)[^，。；？！]{0,24}?(?:撤掉|撤回|取消|停用|停掉|换成|改成|调离|下架)[\p{Han}]{0,10}?了)"
    ).unwrap());
    static SCOPE: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?P<scope>(?:主要就是|主要包括|重点是|重点放在)[^，。；？！]{4,34}(?:计划|安排|方案|改进|检查|交付|培训|招生|招募))"
    ).unwrap());
    static PRACTICE: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?P<practice>(?:由[\p{Han}]{2,18}(?:带动|负责|引导|组织|核实|检查)[\p{Han}]{3,20}|每个[\p{Han}]{2,14}(?:几乎都|都)[\p{Han}]{5,24}))"
    ).unwrap());
    let text = source_body(text);
    let mut hits = Vec::new();
    for (focus, pattern, name) in [
        (Focus::Contrast, &*CONTRAST, "limit"),
        (Focus::Restriction, &*RESTRICTION, "limit"),
        (Focus::CompletedChange, &*CHANGE, "change"),
        (Focus::PlanScope, &*SCOPE, "scope"),
        (Focus::Practice, &*PRACTICE, "practice"),
    ] {
        for found in pattern.captures_iter(text).filter_map(|captures| captures.name(name)) {
            let before = text[..found.start()].rsplit(['。', '；', '，', '！', '？']).next().unwrap_or("");
            let after = text[found.end()..].trim_start();
            let questioned = after.starts_with(['吗', '么', '?', '？'])
                || ["是否", "是不是", "能不能", "会不会", "假如"].iter().any(|cue| before.contains(cue));
            let contrary = focus == Focus::Restriction && (before.trim_end().ends_with(['不', '没']) || before.trim_end().ends_with("不会"));
            let proposed = focus == Focus::CompletedChange
                && ["如果", "准备", "计划", "建议"].iter().any(|cue| before.contains(cue));
            let example = focus == Focus::Restriction
                && ["比如", "比方", "举例", "不能说"].iter().any(|cue| before.contains(cue) || found.as_str().starts_with(cue));
            if questioned || contrary || proposed || example {
                continue;
            }
            let span = if found.as_str().chars().count() < 5 {
                let extra = before.char_indices().rev().nth(4).map_or(before, |(start, _)| &before[start..]);
                &text[found.start() - extra.len()..found.end()]
            } else {
                found.as_str()
            };
            if line(span, 82) && span.chars().filter(|c| c.is_alphanumeric()).count() >= 5 {
                hits.push((focus, span));
                break;
            }
        }
    }
    for hit in calendar_end().find_iter(text) {
        let span = hit.as_str();
        let before = &text[..hit.start()];
        if (span.starts_with("一直") || span.starts_with("持续") || span.starts_with("延续")
            || ["计划", "安排", "范围", "覆盖", "有效", "活动"].iter().any(|word| before.contains(word)))
            && month_end(&text[hit.start()..]).is_some()
        {
            hits.push((Focus::CalendarScope, span));
        }
    }
    if let Some(found) = accepted_proposal().captures(text).and_then(|row| row.name("decision")) {
        let before = text[..found.start()].rsplit(['。', '；', '！', '？']).next().unwrap_or("");
        if !["如果", "假设", "要是", "要不要", "考虑", "能不能", "不是"].iter().any(|marker| before.contains(marker)) {
            hits.push((Focus::AcceptedProposal, found.as_str()));
        }
    }
    hits
}

pub(super) fn verbatim_acceptance<'a>(source: &'a str, expected: &str) -> Option<&'a str> {
    material_spans(source).into_iter().find_map(|(focus, quote)| {
        (focus == Focus::AcceptedProposal && quote == expected && !quote.contains(['「', '」']))
            .then_some(quote)
    })
}

pub(super) fn material_cues(facts: &[Fact], evidence: &[Value]) -> Vec<(String, String, &'static str)> {
    let mut cited = HashMap::<&str, Vec<&Fact>>::new();
    for fact in facts {
        for id in &fact.evidence {
            cited.entry(id).or_default().push(fact);
        }
    }
    let mut pool = HashMap::<Focus, Vec<(&str, &str)>>::new();
    for source in evidence {
        let id = source["id"].as_str().unwrap();
        for (focus, span) in material_spans(source["text"].as_str().unwrap()) {
            if !cited.get(id).is_some_and(|draft| draft.iter().any(|fact| {
                let text = normalized(&fact.text);
                if focus == Focus::CalendarScope {
                    return facet_has_witness(focus.label(), span, "", &text);
                }
                text.contains(&normalized(span)) && (focus != Focus::AcceptedProposal
                    || fact.placement == Placement::Decision || matches!(fact.kind, Kind::Status))
            })) {
                pool.entry(focus).or_default().push((id, span));
            }
        }
    }
    // Spread coverage across the whole meeting and the different kinds of
    // change. No source can consume all of the bounded review space.
    let mut chosen = Vec::new();
    for focus in Focus::ORDER {
        let Some(entries) = pool.get(&focus) else { continue; };
        let max = match focus {
            Focus::Restriction => 4,
            Focus::CalendarScope | Focus::AcceptedProposal => 2,
            _ => 3,
        };
        let count = entries.len().min(max);
        for index in 0..count {
            let (id,span) = entries[index * entries.len() / count];
            chosen.push((id.to_owned(), span.to_owned(), focus.label()));
        }
    }
    chosen
}

pub(super) struct SourceFacet<'a> {
    pub(super) label: &'static str,
    pub(super) quote: &'a str,
    pub(super) witnesses: Vec<&'a str>,
}

impl SourceFacet<'_> {
    pub(super) fn represented_by(&self, statement: &str) -> bool {
        let stated = normalized(statement);
        if stated.contains(&normalized(self.quote)) {
            return true;
        }
        self.witnesses.iter().all(|required| stated.contains(&normalized(required)))
            && (self.label != "设例" || ["例", "假设", "如果", "问", "情境"].iter().any(|cue| stated.contains(cue)))
            && (self.label != "分开讨论的情形" || self.witnesses.last().is_some_and(|required| {
                ["没有", "没", "不", "未能", "未"].iter().any(|negation| stated.contains(&format!("{negation}{required}")))
            }))
    }
}

pub(super) fn independent_source_facets(text: &str) -> Vec<SourceFacet<'_>> {
    static RULE: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:叫|依据|原则(?:是)?|口径(?:是)?|标准(?:是)?)[^，。；！？\n]{0,16}?(?P<quote>从[\p{Han}]{1,2}兼从[\p{Han}]{1,2}|以[\p{Han}]{2,16}为准)"
    ).unwrap());
    static PROCEDURE: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?P<quote>只要[^，。；！？\n]{0,16}?(?P<gate>鉴定|审批|核验|验证|检测|验收)(?:只要|且|并)(?P<condition>[^，。；！？\n]{3,17}?)(?:那么|那(?:他|她)?|就|则)[^，。；！？\n\s]{3,23})"
    ).unwrap());
    static BRANCH: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?P<quote>第[一二三四五]种(?:情况)?(?:如果|要是|若)是(?P<subject>[\p{Han}]{2,12}?)的情况[^。；！？\n]{0,8}?(?:没有|未能|未|不)(?P<condition>[\p{Han}]{2,12})[，,][^，。；！？]{4,36})"
    ).unwrap());
    static CHOICE: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?P<quote>(?P<setup>[^\n，。；！？、]{5,22})[，,]\s*(?:你|他|我们|大家)(?:是|会|要|该|应该)?(?:先|选)[^，。；！？]{1,12}还是[^，。；！？]{1,12})"
    ).unwrap());
    let body = source_body(text);
    let mut facets = Vec::new();
    for (label, pattern, required) in [
        ("适用原则", &*RULE, &["quote"][..]),
        ("适用条件", &*PROCEDURE, &["gate", "condition"][..]),
        ("分开讨论的情形", &*BRANCH, &["subject", "condition"][..]),
        ("设例", &*CHOICE, &["setup"][..]),
    ] {
        for found in pattern.captures_iter(body) {
            let Some(span) = found.name("quote") else { continue; };
            if label == "设例" && !["这个问题", "举个例", "举例", "比如", "假设"]
                .iter().any(|cue| body[..span.start()].contains(cue))
            {
                continue;
            }
            if !line(span.as_str(), 67) || span.as_str().contains(['「', '」']) { continue; }
            let witnesses = required.iter().filter_map(|name| found.name(name)).map(|part| {
                let raw = part.as_str();
                if label == "适用条件" && part.start() != span.start() && raw.chars().count() > 4 {
                    // ASR often keeps the verb and its particle in the condition.
                    // Its value must still be witnessed alongside the procedure.
                    raw.char_indices().rev().nth(1).map_or(raw, |(at, _)| &raw[at..])
                } else {
                    raw
                }
            }).collect();
            facets.push(SourceFacet { label, quote: span.as_str(), witnesses });
        }
    }
    facets
}

pub(super) fn answered_hypothesis<'a>(question: &'a str, reply: &'a str) -> Option<(SourceFacet<'a>, &'a str)> {
    static PREMISE: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:如果说|假如说|假设|要是)(?P<scenario>[^。！？；\n]{9,44})"
    ).unwrap());
    let question = source_body(question);
    let reply = source_body(reply);
    if !["那是不是也算", "那是不是算", "那这算", "那这就", "这属于", "这就属于"]
        .iter().any(|cue| reply.starts_with(cue)) || !line(reply, 25)
    {
        return None;
    }
    let scenario = PREMISE.captures_iter(question).last()?.name("scenario")?.as_str().trim();
    let witness = scenario.char_indices().rev().nth(4).map_or(scenario, |(at, _)| &scenario[at..]);
    (!scenario.contains(['「', '」']) && !reply.contains(['「', '」'])
        && !["谁", "怎么", "什么时候", "是否完成", "能不能", "要不要"].iter().any(|cue| scenario.contains(cue)))
        .then_some((SourceFacet { label:"设例", quote:scenario, witnesses:vec![witness] }, reply))
}

fn literal_overlap(claim: &str, before: &str) -> bool {
    shared_literal(claim, before, 5)
}

fn shared_literal(claim: &str, source: &str, width: usize) -> bool {
    let claim = normalized(claim).chars().collect::<Vec<_>>();
    claim.windows(width).filter(|chunk| chunk.iter().all(|ch| ch.is_alphanumeric()))
        .any(|chunk| source.contains(&chunk.iter().collect::<String>()))
}

pub(super) fn restore_cited_limits(facts: &mut [Fact], evidence: &[Value]) -> Vec<String> {
    let source: HashMap<_, _> = evidence.iter().map(|row| (row["id"].as_str().unwrap(), row["text"].as_str().unwrap())).collect();
    let mut retained = Vec::new();
    for fact in facts.iter_mut().filter(|fact| fact.placement == Placement::Topic) {
        let correction = fact.evidence.iter().find_map(|id| {
            let text = *source.get(id.as_str())?;
            if ["如果", "假设", "比如", "比方", "是否", "能不能"].iter().any(|cue| text.contains(cue))
                || text.contains(['？', '?']) {
                return None;
            }
            material_spans(text).into_iter().find_map(|(focus, span)| {
                if !matches!(focus, Focus::Contrast | Focus::Restriction) || span.contains(['「', '」']) {
                    return None;
                }
                let (before, after) = text.split_once(span)?;
                let rest = if focus == Focus::Contrast { after } else { before };
                (literal_overlap(&fact.text, rest) && !normalized(&fact.text).contains(&normalized(span)))
                    .then(|| format!("{}。同一处发言另有原话「{span}」。", fact.text.trim_end_matches('。')))
                    .filter(|text| line(text, 90))
            })
        });
        if let Some(text) = correction {
            fact.text = text;
            retained.push(fact.id.clone());
        }
    }
    retained
}

#[derive(Clone, Copy, PartialEq)]
struct CalendarDate(u8, u8);

fn calendar_dates(text: &str) -> impl Iterator<Item = (regex::Match<'_>, CalendarDate, Option<CalendarDate>)> {
    static DATE: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?P<month>[0-9０-９一二三四五六七八九十]{1,3})月(?P<day>[0-9０-９一二三四五六七八九十]{1,3})[日号](?:[\s]*(?:至|到|和|及|、|[-–—~～])[\s]*(?:(?P<endMonth>[0-9０-９一二三四五六七八九十]{1,3})月)?(?P<endDay>[0-9０-９一二三四五六七八九十]{1,3})[日号])?"
    ).unwrap());
    DATE.captures_iter(text).filter_map(|row| {
        let number = |part: &str, limit: u8| {
            let value = super::source_items::number_value(part, false)?;
            (value >= 1.0 && value <= f64::from(limit) && value.fract() == 0.0).then_some(value as u8)
        };
        let date = CalendarDate(number(&row["month"], 12)?, number(&row["day"], 31)?);
        let end = if let Some(day) = row.name("endDay") {
            let month = match row.name("endMonth") {
                Some(month) => number(month.as_str(), 12)?,
                None => date.0,
            };
            Some(CalendarDate(month, number(day.as_str(), 31)?))
        } else {
            None
        };
        Some((row.get(0)?, date, end))
    })
}

pub(super) fn preserve_tentative_date<'a>(
    claim: &str, sources: impl Iterator<Item = &'a str>,
) -> Option<String> {
    static CONFIRMED: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?P<marker>已(?:经)?(?:确定|定下|定在|定于|定)|正式确定|确定为|确定在|敲定|定于)(?P<bridge>[^。，,；？！\r\n]{0,16})$"
    ).unwrap());
    static TENTATIVE: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:大概|大致|大约|预计|暂定|暂拟|初步|可能)[在是为于这个\s呃啊嗯的]{0,9}$"
    ).unwrap());
    let mut dates = calendar_dates(claim);
    let (date, first, last) = dates.next()?;
    if dates.next().is_some() || claim.contains(['「', '」', '“', '”']) {
        return None;
    }
    let prefix = &claim[..date.start()];
    let definite = CONFIRMED.captures(prefix)?;
    let marker = definite.name("marker")?;
    let bridge = definite.name("bridge")?.as_str();
    if prefix[..marker.start()].ends_with(['未', '不', '没']) || TENTATIVE.is_match(prefix) {
        return None;
    }

    let mut found_estimate = false;
    for source in sources.map(source_body) {
        for (mentioned, _, _) in calendar_dates(source).filter(|(_, from, to)| (*from, *to) == (first, last)) {
            let before = source[..mentioned.start()].trim_end();
            if TENTATIVE.is_match(before) {
                found_estimate = true;
            } else if CONFIRMED.is_match(before) {
                return None;
            }
        }
    }
    if !found_estimate {
        return None;
    }

    let mut text = claim.to_owned();
    let replacement = if bridge.trim().is_empty() && marker.as_str().ends_with('在') {
        "预计在"
    } else {
        "预计"
    };
    text.replace_range(marker.range(), replacement);
    line(&text, 90).then_some(text)
}

fn retain_recruitment_count(claim: &str, raw: &str) -> Option<String> {
    static COUNTED: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?P<verb>抽调|选派|招聘|增派|安排|找)(?P<count>[一二两三四五六七八九十0-9]{1,4}[个名位])(?P<skill>有经验|有资质|持证|熟悉[^，,。；？！\s]{2,9}|有[^，,。；？！\s]{2,9}经验)"
    ).unwrap());
    let source = source_body(raw);
    let matched = COUNTED.captures(source)?;
    if COUNTED.captures_iter(source).nth(1).is_some() {
        return None;
    }
    let all = matched.get(0)?;
    let skill = matched.name("skill")?.as_str();
    let tail = source[all.end()..].split(['。', '；', '！', '？']).next()?;
    let tail = tail.chars().take(32).collect::<String>();
    if !["人", "同事", "员工", "专员"].iter().any(|noun| tail.contains(noun))
        || ["如果", "假如", "是不是", "要不要"].iter().any(|cue| source[..all.start()].contains(cue))
        || ["不", "未", "没", "不要", "不能", "不必", "禁止", "不许", "无需"]
            .iter().any(|cue| source[..all.start()].trim_end().ends_with(cue))
    {
        return None;
    }
    let verb = matched.name("verb")?.as_str();
    let label = format!("{verb}{skill}");
    let mut claims = claim.match_indices(&label);
    let (start, _) = claims.next()?;
    if claims.next().is_some() || claim[..start].ends_with(['不', '没', '未']) {
        return None;
    }
    let mut corrected = claim.to_owned();
    corrected.insert_str(start + verb.len(), matched.name("count")?.as_str());
    line(&corrected, 90).then_some(corrected)
}

fn retain_additional_cause(claim: &str, raw: &str) -> Option<String> {
    static CHAIN: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:又加上|再加上|还由于|另一个原因是)(?P<cause>[^。；？！\r\n]{10,58}?)(?:所以|因此|从而|导致|使得)(?P<outcome>[^。；？！\r\n]{4,35})"
    ).unwrap());
    let source = source_body(raw);
    let matched = CHAIN.captures(source)?;
    let lead = &source[..matched.get(0)?.start()];
    if ["如果", "假如", "比方", "假设", "要不要", "是否"].iter().any(|cue| lead.contains(cue)) {
        return None;
    }
    let cause = matched.name("cause")?.as_str().trim();
    let outcome = normalized(matched.name("outcome")?.as_str());
    if cause.contains(['「', '」'])
        || !["费用", "成本", "支出", "投入", "工期", "经费", "预算", "损失", "风险", "人手"]
            .iter().any(|term| cause.contains(term))
        || !shared_literal(claim, &outcome, 4)
        || literal_overlap(claim, &normalized(cause))
    {
        return None;
    }
    let claim = claim.trim_end_matches('。');
    let corrected = format!("{claim}。另提到「{cause}」。");
    line(&corrected, 90).then_some(corrected)
}

fn retain_service_audience(claim: &str, raw: &str) -> Option<String> {
    static SERVICE_NEED: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:还有|仍有|有)+(?P<group>[\p{Han}]{2,10}?)(?:仍|还)?需要(?P<use>(?:去|来)?(?:就餐|用餐|办理|使用|借用))"
    ).unwrap());
    let source = source_body(raw);
    if !["仅开", "只开", "仅保留", "只保留"].iter().any(|word| claim.contains(word))
        || !["窗口", "场所", "网点", "通道"].iter().any(|term| claim.contains(term) && source.contains(term))
    {
        return None;
    }
    let matched = SERVICE_NEED.captures(source)?;
    let group = matched.name("group")?.as_str();
    let use_case = matched.name("use")?.as_str();
    let preceding = source[..matched.get(0)?.start()].rsplit(['。', '；', '！', '？']).next()?;
    if claim.contains(group) || ["如果", "假如", "可能", "未必", "是否"].iter().any(|cue| preceding.contains(cue)) {
        return None;
    }
    let revised = format!("{}；仍有{group}需要{use_case}。", claim.trim_end_matches('。'));
    line(&revised, 90).then_some(revised)
}

pub(super) fn retain_context_schedule(facts: &mut [Fact], context: &[Fact], evidence: &[Value]) -> Vec<Value> {
    static MONTH: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?P<month>[0-9０-９一二三四五六七八九十]{1,3})月份?(?:预计|将会?|会|要|开始)"
    ).unwrap());
    let sources: HashMap<_, _> = evidence.iter().map(|row| (evidence_id(row), utterance(row))).collect();
    let mut changes = Vec::new();
    for fact in facts.iter_mut().filter(|fact| fact.placement == Placement::Topic && !fact.text.contains('月')) {
        let mut witnesses = context.iter().filter(|alternative| alternative.placement == Placement::Topic
            && alternative.kind == fact.kind).filter_map(|alternative| {
            let (opening, same_claim) = alternative.text.split_once(['，', ',', '。', '；'])?;
            let month = MONTH.captures(opening)?;
            let date = super::source_items::number_value(&month["month"], false)?;
            if month.get(0)?.start() > 9 || !(1.0..=12.0).contains(&date)
                || normalized(same_claim) != normalized(&fact.text)
            {
                return None;
            }
            fact.evidence.iter().filter(|id| alternative.evidence.contains(id)).find_map(|id| {
                let quoted = sources.get(id.as_str())?;
                let month = MONTH.captures(quoted)?;
                if super::source_items::number_value(&month["month"], false)? != date
                    || !shared_literal(&fact.text, &normalized(quoted), 4)
                {
                    return None;
                }
                let at = month.get(0)?.start();
                let earlier = quoted[..at].rsplit(['。', '；', '！', '？']).next()?;
                if ["如果", "假如", "要不要", "是否"].iter().any(|cue| earlier.contains(cue)) {
                    return None;
                }
                let tail = quoted[at..].split(" 然后").next()?;
                let literal = tail.split(['。', '，', '；', '！', '？']).next()?.trim();
                (line(literal, 34) && !literal.contains(['「', '」']) && literal.chars().count() >= 8)
                    .then_some((id, literal))
            })
        });
        if let Some((id, literal)) = witnesses.next() {
            let revised = format!("会上提到「{literal}」。{}", fact.text);
            if witnesses.all(|(other, quote)| id == other && literal == quote) && line(&revised, 90) {
                changes.push(serde_json::json!({"id":fact.id,"evidence":id,"quote":literal}));
                fact.text = revised;
            }
        }
    }
    changes
}

pub(super) fn retain_cited_details(facts: &mut [Fact], evidence: &[Value]) -> Vec<Value> {
    let source: HashMap<_, _> = evidence.iter().map(|row| {
        (row["id"].as_str().unwrap(), row["text"].as_str().unwrap())
    }).collect();
    let repairs: [(&str, fn(&str, &str) -> Option<String>); 3] = [
        ("headcount", retain_recruitment_count), ("additionalCause", retain_additional_cause),
        ("serviceAudience", retain_service_audience),
    ];
    let mut changes = Vec::new();
    for fact in facts.iter_mut().filter(|fact| fact.placement == Placement::Topic) {
        for (detail, restore) in repairs {
            let mut matches = fact.evidence.iter().filter_map(|id| {
                restore(&fact.text, source.get(id.as_str())?).map(|text| (id, text))
            });
            if let Some((id, text)) = matches.next() {
                if matches.all(|(_, other)| text == other) {
                    fact.text = text;
                    changes.push(serde_json::json!({"id":fact.id,"evidence":id,"detail":detail}));
                }
            }
        }
    }
    changes
}

fn addressed_assignment(source: &str, continuation: &str, statement: &str) -> Option<String> {
    static DIRECT: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:^|刚才|[，。；\s])(?P<team>[\p{Han}]{2,10}?)(?:这一块儿?|那一块儿?|这边儿?|那边儿?)[\s，,]*(?:一定要|务必|必须|你们先|你们要)(?P<subject>[^。；？！\r\n]{4,36})"
    ).unwrap());
    let source = source_body(source);
    let assignment = DIRECT.captures(source)?;
    let team = assignment.name("team")?.as_str().rsplit("刚才").next()?.trim_start_matches(['嗯', '啊', '呃']);
    if team.chars().count() < 2 || team.contains(['你', '我', '他', '您'])
        || ["如果", "假如", "建议", "考虑", "要不要"].iter().any(|cue| source.contains(cue))
        || !["你要", "你们", "还要", "落实", "安排", "完成", "处理", "提交"].iter().any(|cue| continuation.contains(cue))
    {
        return None;
    }
    let subject = normalized(assignment.name("subject")?.as_str());
    let object = subject.char_indices().rev().nth(1).map(|(at, _)| &subject[at..])?;
    let generic = ["这个", "那个", "一下", "事项", "工作", "情况", "安排", "落实", "做好", "完成", "下去", "一下儿"];
    if generic.contains(&object) || !object.chars().all(|ch| ch.is_alphabetic())
        || !normalized(statement).contains(object) || !normalized(continuation).contains(object)
    {
        return None;
    }
    Some(team.to_owned())
}

fn brief_interruption(text: &str, statement: &str) -> bool {
    let text = normalized(source_body(text));
    text.chars().count() <= 5 && (text.chars().all(|ch| ['嗯', '哦', '对', '是', '好'].contains(&ch))
        || ["落实", "确定", "执行", "安排", "检查", "处理", "完成", "提交"].iter().any(|verb| {
            text.starts_with(verb) && statement.contains(verb)
        }))
}

pub(super) fn bind_nearby_assignment(facts: &mut [Fact], evidence: &[Value]) -> Vec<Value> {
    let positions: HashMap<_, _> = evidence.iter().enumerate()
        .map(|(position, row)| (row["id"].as_str().unwrap(), position)).collect();
    let mut changes = Vec::new();
    for fact in facts.iter_mut().filter(|fact| fact.placement == Placement::Action
        && fact.owner.is_none() && fact.evidence.len() < 8)
    {
        let mut options = Vec::new();
        for &position in fact.evidence.iter().filter_map(|id| positions.get(id.as_str())) {
            let continuation = &evidence[position];
            let Some(speaker) = continuation["turnSpeaker"].as_str() else { continue; };
            let continuation_text = source_body(continuation["text"].as_str().unwrap());
            for earlier in position.saturating_sub(4)..position {
                let row = &evidence[earlier];
                if row["turnSpeaker"] != speaker || row["source"] != continuation["source"]
                    || evidence[earlier + 1..position].iter().any(|middle| {
                        let text = middle["text"].as_str().unwrap();
                        !brief_interruption(text, &fact.text) && !(middle["turnSpeaker"] == speaker
                            && ["这个", "这个呃", "那个", "那个呃"].contains(&normalized(source_body(text)).as_str()))
                    })
                {
                    continue;
                }
                if let Some(team) = addressed_assignment(row["text"].as_str().unwrap(), continuation_text, &fact.text) {
                    options.push((team, row["id"].as_str().unwrap()));
                }
            }
        }
        options.sort_unstable();
        options.dedup();
        if let [(team, id)] = options.as_slice() {
            fact.owner = Some(team.clone());
            if !fact.evidence.iter().any(|existing| existing.as_str() == *id) {
                fact.evidence.insert(0, (*id).to_owned());
            }
            changes.push(serde_json::json!({"id":fact.id,"evidence":id,"owner":team}));
        }
    }
    changes
}

fn utterance(row: &Value) -> &str {
    source_body(row["text"].as_str().unwrap_or_default())
}

fn evidence_id(row: &Value) -> &str {
    row["id"].as_str().unwrap()
}

fn retain_fact_evidence(fact: &mut Fact, proof: &[&str]) -> bool {
    let mut additional = Vec::new();
    for &id in proof {
        if !fact.evidence.iter().any(|known| known == id) && !additional.contains(&id) {
            additional.push(id);
        }
    }
    if fact.evidence.len() + additional.len() > 8 {
        return false;
    }
    fact.evidence.extend(additional.into_iter().map(str::to_owned));
    true
}

fn reporting_addressee<'a>(
    issuer: &Value, previous: &'a [Value], fact: &Fact,
    bindings: &super::source_bindings::SourceBindings<'a>,
) -> Option<(&'a str, Vec<&'a str>)> {
    static ADDRESSED: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"你们?(?:那|这)边儿?\s*(?P<team>[\p{Han}]{2,8}?(?:处|部|科|组|中心))(?:管的|负责的)?[，\s]*(?:有没有|是否有|怎么|是怎么)"
    ).unwrap());
    let issuer_label = issuer["turnSpeaker"].as_str()?;
    let statement = normalized(&fact.text);
    if !["统计", "登记", "汇总"].iter().any(|word| statement.contains(word))
        || !["上报", "报表", "报送"].iter().any(|word| statement.contains(word))
    {
        return None;
    }
    let mut matches = previous.iter().enumerate().filter_map(|(index, ask)| {
        if ask["turnSpeaker"] != issuer_label { return None; }
        let team = ADDRESSED.captures(utterance(ask))?.name("team")?.as_str();
        let stem = team.trim_end_matches("中心").trim_end_matches(['处', '部', '科', '组']);
        if stem.chars().count() < 2 || previous[index + 1..].iter().any(|row| {
            ["换个话题", "另一个部门", "下一个部门", "接下来讨论"].iter().any(|cue| utterance(row).contains(cue))
        }) {
            return None;
        }
        let answers = &previous[index + 1..];
        let answer = answers.iter().take(4).find(|row| {
            row["turnSpeaker"] != issuer_label && utterance(row).chars().count() >= 10 && !utterance(row).contains('？')
        })?;
        let speaker = answer["turnSpeaker"].as_str()?;
        let (identity, intro) = bindings.introduction(speaker)?;
        if identity != team && !identity.strip_prefix(stem).is_some_and(|role| {
            ["主任", "部长", "组长", "主管", "负责人", "经理"].contains(&role)
        }) {
            return None;
        }
        let recent = answers.iter().rev().take(5).find(|row| {
            row["turnSpeaker"] == speaker && utterance(row).chars().count() >= 8
        })?;
        Some((team, vec![intro, evidence_id(ask), evidence_id(answer), evidence_id(recent)]))
    });
    let result = matches.next()?;
    matches.next().is_none().then_some(result)
}

fn proposal_addressee<'a>(
    issuer: &Value, nearby: &'a [Value], reply: Option<&'a Value>, fact: &Fact,
    bindings: &super::source_bindings::SourceBindings<'a>,
) -> Option<(&'a str, Vec<&'a str>)> {
    let instruction = normalized(utterance(issuer));
    if !["拟一个方案", "拟一份方案", "写一个方案", "做一个方案"].iter().any(|cue| instruction.contains(cue))
        || !fact.text.contains("方案")
    {
        return None;
    }
    let reply = reply?;
    let speaker = reply["turnSpeaker"].as_str()?;
    if issuer["turnSpeaker"] == speaker || !["想法就是", "我的想法", "我会", "我来", "好我"]
        .iter().any(|cue| normalized(utterance(reply)).starts_with(cue))
    {
        return None;
    }
    let (identity, intro) = bindings.introduction(speaker)?;
    let previous = nearby.iter().rev().find(|row| {
        row["turnSpeaker"] == speaker && shared_literal(&fact.text, &normalized(utterance(row)), 4)
    })?;
    Some((identity, vec![intro, evidence_id(previous), evidence_id(reply)]))
}

fn accepted_deliverable<'a>(issuer: &Value, previous: &Value, reply: &'a Value, fact: &Fact) -> Option<&'a str> {
    static DELIVERABLE: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"^(?:对|好|嗯对)[，、\s]*(?:做|编|整理|提交|出)(?P<item>[\p{Han}]{2,12}?(?:表|清单|报告|手册))[。！\s]*$"
    ).unwrap());
    let same_participant = previous["turnSpeaker"].is_string() && previous["turnSpeaker"] == reply["turnSpeaker"];
    let instruction = normalized(utterance(issuer));
    if !same_participant || issuer["turnSpeaker"] == reply["turnSpeaker"]
        || !instruction.contains("具体的计划") || !fact.text.contains("计划")
        || !shared_literal(&fact.text, &normalized(utterance(previous)), 4)
    {
        return None;
    }
    let item = DELIVERABLE.captures(utterance(reply))?.name("item")?.as_str();
    (!fact.text.contains(item)).then_some(item)
}

pub(super) fn retain_assignment_dialogue(
    facts: &mut [Fact], evidence: &[Value], bindings: &super::source_bindings::SourceBindings<'_>,
) -> Vec<Value> {
    let positions: HashMap<_, _> = evidence.iter().enumerate()
        .map(|(index, row)| (evidence_id(row), index)).collect();
    let mut changes = Vec::new();
    for fact in facts.iter_mut().filter(|fact| fact.placement == Placement::Action) {
        let anchors: Vec<_> = fact.evidence.iter().filter_map(|id| positions.get(id.as_str()).copied()).collect();
        for position in anchors {
            let issuer = &evidence[position];
            let text = normalized(utterance(issuer));
            let directly_addressed = ["你到时候", "你先", "你们先", "你们到时候", "你负责"].iter().any(|cue| text.contains(cue));
            if fact.owner.is_none() && directly_addressed {
                let prior = &evidence[position.saturating_sub(16)..position];
                let addressee = reporting_addressee(issuer, prior, fact, bindings).or_else(|| {
                    proposal_addressee(issuer, &evidence[position.saturating_sub(4)..position],
                        evidence.get(position + 1), fact, bindings)
                });
                if let Some((owner, proof)) = addressee {
                    if retain_fact_evidence(fact, &proof) {
                        fact.owner = Some(owner.to_owned());
                        changes.push(serde_json::json!({"id":fact.id,"owner":owner,"evidence":proof}));
                    }
                }
            }
            if let (Some(previous), Some(reply)) = (position.checked_sub(1).and_then(|pos| evidence.get(pos)), evidence.get(position + 1)) {
                if let Some(deliverable) = accepted_deliverable(issuer, previous, reply, fact) {
                    let revised = format!("{}，并制作{}。", fact.text.trim_end_matches('。'), deliverable);
                    let proof = [evidence_id(previous), evidence_id(reply)];
                    if line(&revised, 90) && retain_fact_evidence(fact, &proof) {
                        fact.text = revised;
                        changes.push(serde_json::json!({"id":fact.id,"deliverable":deliverable,"evidence":proof}));
                    }
                }
            }
        }
    }
    changes
}

pub(super) fn retain_opening_host(
    purpose: &mut String, evidence: &[Value], bindings: &super::source_bindings::SourceBindings<'_>,
) -> Option<Value> {
    static TRANSFER: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:接下来|接着|下面|现在)由(?:咱们这个|我们这个|咱们的|我们的|这个)?(?P<host>[\p{Han}]{2,12}?)来?主持(?:一下儿?)?(?:这次|这场|这个|本次)?会议"
    ).unwrap());
    for (index, issuer) in evidence.iter().take(18).enumerate() {
        let source = normalized(utterance(issuer));
        let Some(transfer) = TRANSFER.captures(&source) else { continue; };
        let host = transfer.name("host")?.as_str();
        if purpose.contains("主持") || ["如果", "要不要", "能不能", "是否"].iter().any(|cue| source.contains(cue)) {
            continue;
        }
        let opened = evidence.iter().skip(index + 1).take(3).find(|row| {
            row["turnSpeaker"] != issuer["turnSpeaker"] && row["turnSpeaker"].as_str()
                .and_then(|speaker| bindings.introduction(speaker)).is_some_and(|(name, _)| name == host)
                && ["会议开始", "开始开会", "开始今天的会议"].iter().any(|cue| utterance(row).contains(cue))
        });
        let Some(opened) = opened else { continue; };
        let called_by = issuer["turnSpeaker"].as_str().and_then(|speaker| bindings.introduction(speaker));
        let host_clause = if let Some((caller, _)) = called_by.filter(|_| {
            ["叫过来", "召集", "请大家"].iter().any(|cue| source.contains(cue))
        }) {
            format!("{caller}召集会议并交由{host}主持。")
        } else {
            format!("本次会议由{host}主持。")
        };
        let combined = format!("{host_clause}{purpose}");
        if !line(&combined, 120) { continue; }
        *purpose = combined;
        return Some(serde_json::json!({"host":host,"evidence":[evidence_id(issuer),evidence_id(opened)]}));
    }
    None
}

fn assignment_owner<'a>(statement: &str, source: &'a str) -> Option<&'a str> {
    static NAMED: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:任务|工作)[^，。；？！\n]{0,12}(?:分给|交给|交由)(?:这个|那个)?(?P<owner>[\p{Han}]{2,16}?)(?:让|去|负责|来|[，。])"
    ).unwrap());
    static COLLECTIVE: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:下去以后|会后|散会后)[^。；？！\n]{0,16}?(?P<owner>各[\p{Han}]{1,8}?)(?:儿|把)[^。；？！\n]{2,30}(?:拿出来|交过来|提交|报送)"
    ).unwrap());
    if ["是否", "要不要", "能不能", "假如", "建议"].iter().any(|term| source.contains(term))
        || source.contains(['？', '?']) {
        return None;
    }
    let owner = if ["任务", "工作"].iter().any(|term| statement.contains(term))
        && ["分给", "交给", "交由"].iter().any(|term| statement.contains(term)) {
        NAMED.captures(source)?.name("owner")?.as_str()
    } else if statement.contains("会后") && ["提交", "拿出", "报送"].iter().any(|term| statement.contains(term)) {
        COLLECTIVE.captures(source)?.name("owner")?.as_str()
    } else {
        return None;
    };
    statement.contains(owner).then_some(owner)
}

pub(super) fn restore_delivery_scope(facts: &mut [Fact], evidence: &[Value]) -> Vec<String> {
    const PERIODS: [&str; 6] = ["上半年", "下半年", "本季度", "下季度", "本年度", "下一年度"];
    let positions: HashMap<_, _> = evidence.iter().enumerate()
        .map(|(position, row)| (row["id"].as_str().unwrap(), position)).collect();
    let mut covered = Vec::new();
    for fact in facts.iter_mut().filter(|fact| fact.placement == Placement::Action
        && fact.evidence.len() < 8 && fact.text.contains("计划")
        && ["发给", "提交", "交给", "报送"].iter().any(|verb| fact.text.contains(verb))) {
        let Some(period) = PERIODS.into_iter().find(|period| fact.text.contains(period)) else {
            continue;
        };
        let scopes: Vec<_> = fact.evidence.iter().filter_map(|id| positions.get(id.as_str()).copied())
            .flat_map(|position| {
                let anchor = &evidence[position];
                evidence[position.saturating_sub(4)..=position].iter().filter(move |row| {
                    anchor["source"] == row["source"] && anchor["turnSpeaker"].is_string()
                        && anchor["turnSpeaker"] == row["turnSpeaker"]
                })
            }).filter_map(|row| {
                let original = row["text"].as_str()?;
                if ["如果", "我建议", "假如", "要不要", "不一定"].iter().any(|marker| original.contains(marker)) {
                    return None;
                }
                let spans = material_spans(original);
                let (_, span) = spans.into_iter().find(|(kind, span)| {
                    *kind == Focus::PlanScope && span.contains(period) && span.contains("计划")
                })?;
                Some((row["id"].as_str()?, span))
            }).collect();
        let Some((id, span)) = scopes.first().copied() else { continue; };
        if scopes.iter().any(|(_, other)| *other != span) || normalized(&fact.text).contains(&normalized(span)) {
            continue;
        }
        let text = format!("{}。同一发言说明「{span}」。", fact.text.trim_end_matches('。'));
        if line(&text, 90) {
            if !fact.evidence.iter().any(|current| current == id) {
                fact.evidence.push(id.to_owned());
            }
            fact.text = text;
            covered.push(fact.id.clone());
        }
    }
    covered
}

fn was_completed(text: &str, source: &str) -> bool {
    let past = ["上个月", "上月", "上周", "上季度", "去年"];
    let events = [("成立", "成立了"), ("组建", "组建了"), ("完成", "完成了"), ("交付", "交付了")];
    past.iter().any(|word| text.contains(word) && source.contains(word))
        && events.iter().any(|(event, original)| text.contains(event) && source.contains(original))
        && !["后续", "接下来", "还要", "需要", "要求", "必须", "没", "尚未", "计划", "打算"]
            .iter().any(|word| text.contains(word) || source.contains(word))
}

fn is_report_or_meeting_process(text: &str, source: &str) -> bool {
    let follows_after = ["会后", "散会后", "后续", "接下来要", "必须继续", "请继续", "务必"];
    if follows_after.iter().any(|word| text.contains(word) || source.contains(word)) {
        return false;
    }
    let meeting_chair = text.contains("主持") && ["本次会议", "这场会议"].iter().any(|word| text.contains(word))
        && source.contains("主持") && ["这场会议", "这次会议", "本次会议"].iter().any(|word| source.contains(word));
    let ongoing = text.contains("正在") && ["现在", "目前", "正在"].iter().any(|word| source.contains(word))
        && ["在招", "在培训", "在检查", "在处理", "在跟进"].iter().any(|word| source.contains(word));
    meeting_chair || ongoing
}

fn addressed_team<'a>(statement: &str, source: &'a str) -> Option<&'a str> {
    static ADDRESS: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:^|[，。；\s])(?:[嗯呃][\s]*)*(?P<team>[\p{Han}]{2,12}?(?:这|那)边儿?)[\s，,]*(?:你们|各位)(?:把|去|先|安排|找|负责|抽时间)"
    ).unwrap());
    let matched = ADDRESS.captures(source)?;
    let team = matched.name("team")?;
    let lead = source[..team.start()].rsplit(['。', '；', '！', '？']).next().unwrap_or("");
    if ["如果", "假设", "比如", "建议", "要不要", "能不能"].iter().any(|word| lead.contains(word))
        || team.as_str().contains(['你', '我', '他', '您']) || source.contains(['？', '?']) {
        return None;
    }
    let task = normalized(&source[team.end()..]).replace("那个", "").replace("那些", "").replace("你们", "");
    literal_overlap(statement, &task).then(|| team.as_str())
}

pub(super) fn preserve_spoken_roles(facts: &mut [Fact], evidence: &[Value]) -> Vec<String> {
    let source: HashMap<_, _> = evidence.iter().map(|row| (row["id"].as_str().unwrap(), source_body(row["text"].as_str().unwrap()))).collect();
    let mut changed = Vec::new();
    for fact in facts {
        let sources = fact.evidence.iter().filter_map(|id| source.get(id.as_str()).copied());
        match fact.placement {
            Placement::Decision => {
                let Some(owner) = sources.filter_map(|source| assignment_owner(&fact.text, source)).next() else { continue; };
                fact.owner = Some(owner.to_owned());
                fact.placement = Placement::Action;
            },
            Placement::Action if fact.evidence.len() == 1 => {
                let Some(source) = sources.into_iter().next() else { continue; };
                if fact.due.is_none() && (was_completed(&fact.text, source) || is_report_or_meeting_process(&fact.text, source)) {
                    fact.kind = Kind::Status;
                    fact.placement = Placement::Topic;
                    fact.owner = None;
                } else if fact.owner.is_none() {
                    let Some(team) = addressed_team(&fact.text, source) else { continue; };
                    fact.owner = Some(team.to_owned());
                } else {
                    continue;
                }
            },
            _ => continue,
        }
        changed.push(fact.id.clone());
    }
    changed
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn turn(id: &str, speaker: &str, text: &str) -> Value {
        json!({"id":id,"turnSpeaker":speaker,"text":format!("{speaker}：{text}")})
    }

    fn item(id: &str, text: &str, basis: &str, kind: Kind, placement: Placement) -> Fact {
        Fact {id:id.into(), kind, placement, text:text.into(), owner:None, due:None, evidence:vec![basis.into()]}
    }

    #[test]
    fn contextual_copy_can_restore_a_verified_month_without_creating_tasks() {
        let source = turn("e0143", "说话人5", "等到九月份会有一批新的同学然后来我们的学校 然后我觉得该把资金放在招生宣传和招生咨询上");
        let fact = item("a046", "建议把资金放在招生宣传和招生咨询上。", "e0143", Kind::Recommendation, Placement::Topic);
        let mut facts = [fact];
        let matching = "九月份将迎来新生，建议把资金放在招生宣传和招生咨询上。";
        let wrong = matching.replace("九月", "八月");
        let wrong = item("", &wrong, "e0143", Kind::Recommendation, Placement::Topic);
        let matching = item("", matching, "e0143", Kind::Recommendation, Placement::Topic);
        assert!(retain_context_schedule(&mut facts, &[wrong], &[source.clone()]).is_empty());
        assert_eq!(retain_context_schedule(&mut facts, &[matching], &[source]).len(), 1);
        assert!(facts[0].text.contains("九月份会有一批新的同学"));
        assert!(facts[0].due.is_none());
    }

    #[test]
    fn two_sided_dialogue_binds_the_original_action_and_reply() {
        let mut source = vec![
            turn("e0006","说话人7","我是教务主任"),
            turn("e0010","副院长","你们那边儿教务处管的有没有登记表格儿之类的？"),
            turn("e0011","说话人7","疫情期间每天都需要打卡报备。"),
            turn("e0012","副院长","打卡方式是什么？"),
            turn("e0013","说话人7","在学校系统打卡和报备信息。"),
            turn("e0014","副院长","那你到时候通知班长做统计，做报表并每天上报。"),
            turn("e0015","财务","管理人员需要做好设施安全培训。"),
            turn("e0016","负责人","你这边做个具体的计划。"),
            turn("e0017","财务","对做财务表"),
        ];
        let mut facts = [
            item("a001","通知班长做统计，做报表并每天上报。","e0014",Kind::Decision,Placement::Action),
            item("a002","针对设施安全培训做一个具体的计划。","e0016",Kind::Decision,Placement::Action),
        ];
        let bindings = super::super::source_bindings::SourceBindings::new(&source);
        assert_eq!(retain_assignment_dialogue(&mut facts, &source, &bindings).len(), 2);
        assert_eq!(facts[0].owner.as_deref(), Some("教务处"));
        assert!(facts[0].due.is_none());
        assert!(facts[0].evidence.iter().any(|id| id == "e0010"));
        assert!(facts[1].text.contains("制作财务表"));
        assert!(facts[1].evidence.iter().any(|id| id == "e0017"));
        source[8] = turn("e0017","后勤","对做财务表");
        let mut fact = [item("a002","针对设施安全培训做一个具体的计划。","e0016",Kind::Decision,Placement::Action)];
        let bindings = super::super::source_bindings::SourceBindings::new(&source);
        assert!(retain_assignment_dialogue(&mut fact, &source, &bindings).is_empty());
    }

    #[test]
    fn meeting_opening_and_service_audience_need_their_own_source() {
        let source = [
            turn("e0000","说话人1","我是院长"),
            turn("e0002","说话人3","我是副院长"),
            turn("e0007","说话人1","把各部门叫过来开会，接下来由咱们这个副院长来主持一下这个会议"),
            turn("e0008","说话人3","好，现在会议开始了"),
            turn("e0074","说话人6","食堂开设的窗口儿比较少，但是有有老师需要去就餐。"),
        ];
        let bindings = super::super::source_bindings::SourceBindings::new(&source);
        let mut purpose = "会议回顾上半年网课与经费情况。".to_string();
        assert!(retain_opening_host(&mut purpose, &source, &bindings).is_some());
        assert!(purpose.starts_with("院长召集会议并交由副院长主持。"));
        let mut fact = [item("a002","食堂上学期仅开三个窗口，收入不可观。","e0074",Kind::Status,Placement::Topic)];
        assert_eq!(retain_cited_details(&mut fact, &source).len(), 1);
        assert!(fact[0].text.contains("老师需要去就餐"));
        let planning = "食堂开设的窗口儿比较少，如果有老师需要去就餐。";
        assert!(retain_service_audience("食堂上学期仅开三个窗口。",planning).is_none());
    }

    #[test]
    fn direct_date_qualifier_survives_confirmation_without_concrete_dates() {
        let sources = [
            "说话人2: 教务处已经把期末考时间定下来了。",
            "说话人2: 然后呃嗯大概是在七月六号和七月七号嗯考两天。",
        ];
        assert_eq!(preserve_tentative_date("教务处已定期末考时间为7月6日至7日，考两天。", sources.into_iter()).as_deref(),
            Some("教务处预计期末考时间为7月6日至7日，考两天。"));
        assert!(preserve_tentative_date("期末考已定七月六号。", sources.into_iter()).is_none());
        assert!(preserve_tentative_date("未确定考试时间为七月六号至七号。", sources.into_iter()).is_none());
        assert!(preserve_tentative_date("教务处已定期末考时间为七月六号至七号。",
            sources.into_iter().chain(["后来确定在七月六号至七号。"])).is_none());
    }

    #[test]
    fn cited_details_restore_only_the_count_and_cause_of_the_same_statement() {
        let draft = "运营部计划先找有经验的人做大概计划，再与财务对预算。";
        let counted = "说话人5: 准备首先先是多找两个有经验，然后有过做过特别好规划的人，然后先做一下大概的计划。";
        assert_eq!(retain_recruitment_count(draft, counted).as_deref(),
            Some("运营部计划先找两个有经验的人做大概计划，再与财务对预算。"));
        assert!(retain_recruitment_count(draft, "建议安排三位有经验的员工。").is_none());
        assert!(retain_recruitment_count(draft, "不能找两个有经验的员工。").is_none());
        assert!(retain_recruitment_count("先找三位有经验的员工。", counted).is_none());

        let claim = "与智能公司的合作项目因疫情耽误，财务状况不乐观。";
        let source = "说话人6: 对因为呃上半年咱们和别人的呃这些联合项目因为疫情嘛情况所以我们很难进行下去这方面合作就有了一些耽误 然后又加上呃这个各部门什么产品需要什么费用呃我们已经开发出来的这些产品然后呃又后续进行了一些拓展 所以升级呃我们这个财务状况其实不太乐观现在";
        let restored = retain_additional_cause(claim, source).unwrap();
        assert!(restored.contains("费用") && restored.contains("进行了一些拓展"));
        assert!(retain_additional_cause(&restored, source).is_none());
        assert!(retain_additional_cause("对方未能按时交货。", source).is_none());
        assert!(retain_additional_cause(claim, &format!("说话人6: 如果{}", source_body(source))).is_none());
    }

    #[test]
    fn a_short_interruption_can_keep_the_nearby_assignment_while_a_new_turn_cannot() {
        let evidence = [
            json!({"id":"e0432","source":"u015","turnSpeaker":"说话人1",
                   "text":"说话人1: 嗯 啊还有就是刚才运营这一块儿，一定要把大堂这个刚才说这个蛋糕"}),
            json!({"id":"e0433","source":"u015","turnSpeaker":"说话人5","text":"说话人5: 好"}),
            json!({"id":"e0434","source":"u015","turnSpeaker":"说话人1","text":"说话人1: 这个呃"}),
            json!({"id":"e0435","source":"u015","turnSpeaker":"说话人4","text":"说话人4: 落实下来"}),
            json!({"id":"e0436","source":"u015","turnSpeaker":"说话人1",
                   "text":"说话人1: 这个蛋糕还有优惠啊就是你要落实下去，与市场相结合宣传。"}),
        ];
        let action = Fact {id:"a000".into(),kind:Kind::Decision,placement:Placement::Action,
            text:"落实蛋糕及赠送给客人的优惠，并与市场相结合做好宣传。".into(),
            owner:None,due:None,evidence:vec!["e0436".into()]};
        let mut facts = [action.clone()];
        assert_eq!(bind_nearby_assignment(&mut facts, &evidence).len(), 1);
        assert_eq!(facts[0].owner.as_deref(), Some("运营"));
        assert_eq!(facts[0].evidence, ["e0432", "e0436"]);
        let mut interrupted = evidence.clone();
        interrupted[3]["text"] = json!("说话人4: 关于下一次发布会，财务要把报表报上去。");
        assert!(bind_nearby_assignment(&mut [action.clone()], &interrupted).is_empty());
        let mut new_speaker = evidence.clone();
        new_speaker[4]["turnSpeaker"] = json!("说话人2");
        assert!(bind_nearby_assignment(&mut [action], &new_speaker).is_empty());
    }

    #[test]
    fn uncited_schedule_scope_and_acceptance_become_independent_checks() {
        let evidence = [
            json!({"id":"e0001","text":"主持人：咱们这次一直到嗯 九月份儿的防暑安排。"}),
            json!({"id":"e0002","text":"主管：价格可以。行就装点儿空调。"}),
            json!({"id":"e0003","text":"委员：如果有钱，行就再安排一次调研。"}),
        ];
        let cues = material_cues(&[], &evidence);
        assert!(cues.iter().any(|(id, _, aspect)| id == "e0001" && *aspect == Focus::CalendarScope.label()));
        assert!(cues.iter().any(|(id, _, aspect)| id == "e0002" && *aspect == Focus::AcceptedProposal.label()));
        assert!(!cues.iter().any(|(id, _, aspect)| id == "e0003" && *aspect == Focus::AcceptedProposal.label()));
        assert!(facet_has_witness(Focus::CalendarScope.label(), "一直到九月份儿", "status", "防暑安排延续到9月。"));
        assert!(!facet_has_witness(Focus::CalendarScope.label(), "一直到九月份儿", "status", "防暑安排延续到9月底。"));
        assert!(!facet_has_witness(Focus::AcceptedProposal.label(), "行就装点儿空调", "recommendation", "建议给工人装空调。"));
    }

    #[test]
    fn independent_clauses_require_their_own_content_in_the_body() {
        let result = independent_source_facets("说话人2: 法律追诉叫 从轻兼那个从旧兼从轻");
        assert_eq!(result[0].quote, "从旧兼从轻");
        assert!(!result[0].represented_by("律师说明不能等到十八岁再处理。"));
        assert!(result[0].represented_by("律师介绍从旧兼从轻的口径。"));
        let result = independent_source_facets("说话人8: 只要经过独立检测且确认达到合格等级就可以交付");
        assert_eq!(result[0].label, "适用条件");
        assert!(!result[0].represented_by("只要达到合格等级便可交付。"));
        assert!(result[0].represented_by("经过检测并达到合格等级才可以交付。"));
        let result = independent_source_facets("说话人3: 第一种如果是过期证件的情况下他没有补办，不能发放。另一种继续核对。");
        assert_eq!(result[0].label, "分开讨论的情形");
        assert!(!result[0].represented_by("过期证件要补办。"));
        assert!(result[0].represented_by("过期证件未补办则不能发放。"));
    }

    #[test]
    fn hypotheses_and_real_decisions_have_separate_source_shapes() {
        let example = independent_source_facets("说话人2: 我举例问一个问题，两份方案都延期了，你是先改单还是先通知对方？");
        assert_eq!(example[0].label, "设例");
        assert!(independent_source_facets("说话人2: 两份方案都延期了，你是先改单还是先通知对方？").is_empty());
        let reply = answered_hypothesis("说话人7: 如果说就是为了得到遗产把他兄弟毒死了",
            "说话人2: 那是不是也算是故意杀人罪了").unwrap();
        assert!(reply.0.quote.contains("得到遗产"));
        assert!(reply.1.contains("也算"));
        assert!(answered_hypothesis("说话人7: 如果说你来安排是能不能及时完成",
            "说话人2: 那这就算了").is_none());
    }

    #[test]
    fn only_the_addressed_group_in_the_action_sentence_can_own_it() {
        let source = "你这边儿的话这个 嗯场地这边儿你们把这个抽时间你们找几个人，然后上去把塔吊那个驾驶室那些绝缘绝缘的那个看一下";
        let action = "抽时间找几个人上去检查塔吊驾驶室的绝缘情况。";
        assert_eq!(addressed_team(action, source), Some("场地这边儿"));
        assert_eq!(addressed_team("找财务核对项目预算。", source), None);
        assert_eq!(addressed_team(action, &format!("如果那天有空 {source}")), None);
        assert_eq!(addressed_team(action, "那你这边儿你们先检查塔吊驾驶室的绝缘"), None);
    }
}
