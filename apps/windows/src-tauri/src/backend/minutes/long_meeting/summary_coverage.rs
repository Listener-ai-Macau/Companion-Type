use std::{ops::Range, sync::LazyLock};

use regex::Regex;

use super::{
    summary_review::{cite_turn, CitedTurn},
    CompanionV1HostSession, CompanionV1MeetingMinutes, Evidence,
};

const NUMBER: &str = r"[0-9一二两三四五六七八九十百千万]{1,8}";
const ACTIVITY: &str = r"响应|处理|接收|完成|复核|开展|举办|交付|巡检|发放|回访|接待|审核";
const COUNT_UNIT: &str = r"节课|门课|次|起|件|份|项|场|台|套|笔|批|人|户";

static ACTIVITY_COUNT: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(&format!(
    r"(?P<verb>{ACTIVITY})\s*(?:了)?\s*(?P<count>{NUMBER})\s*(?:多|余)?\s*(?P<unit>{COUNT_UNIT})"
)).unwrap()
});
static EXPLICIT_COUNT: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(&format!(r"{NUMBER}\s*(?P<unit>{COUNT_UNIT})")).unwrap());
static PERIOD_RANGE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(&format!(
    r"(?:这个|那个|这一|那一|当时的|该)(?:阶段|时期|期间)[里中内]?\s*(?:我们|各组|团队)?\s*(?P<period>每(?:年|季度|季|月|周|天|日))\s*(?:也|通常|平均|大约|大概|约)?\s*(?P<verb>{ACTIVITY})\s*(?:约)?\s*(?P<low>{NUMBER})\s*(?:到|至|[-–—~～])\s*(?P<high>{NUMBER})\s*(?P<unit>{COUNT_UNIT})"
)).unwrap()
});
static SCOPED_LIMIT: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(&format!(
    r"(?P<scope>[\p{{Han}}]{{2,14}})[，,]\s*(?P<subject>[\p{{Han}}]{{2,14}}?)(?:只安排|只开设|就安排|只排|只有|仅有|最多|不超过|就|只|仅)\s*(?P<count>{NUMBER})\s*(?P<unit>{COUNT_UNIT})"
)).unwrap()
});
static SCOPE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
    r"^(?:小学|初中|高中|本科|幼儿园|[一二三四五六七八九1-9]年级|(?:本|该|这|上述|当前)[\p{Han}]{1,8})$"
).unwrap()
});

fn literal_clause(text: &str, span: &Range<usize>) -> bool {
    let before = text[..span.start]
        .rsplit(['。', '；', '！', '？', '\n'])
        .next()
        .unwrap_or("");
    let after = text[span.end..]
        .split(['。', '；', '！', '？', '\n'])
        .next()
        .unwrap_or("");
    let matched = &text[span.clone()];
    ![
        "如果",
        "假如",
        "假设",
        "比如",
        "举例",
        "要不要",
        "是不是",
        "是否",
        "可能",
        "计划",
        "预计",
        "建议",
        "试行",
        "并非",
        "实际上没有",
        "改成",
        "改为",
        "不再",
        "取消",
        "或许",
        "备选",
    ]
    .iter()
    .any(|cue| before.contains(cue) || matched.contains(cue) || after.contains(cue))
        && !["不", "未", "没", "没有", "不曾", "未曾"]
            .iter()
            .any(|cue| before.trim_end().ends_with(cue))
        && !after.contains(['吗', '么', '?'])
        && !text[span.end..].trim_start().starts_with(['?', '？'])
}

fn shared_activity(context: &str, summary: &str) -> bool {
    let chars: Vec<char> = context.chars().take(180).collect();
    chars.windows(4).any(|part| {
        part.iter().all(|ch| matches!(*ch, '\u{3400}'..='\u{9fff}'))
            && summary.contains(&part.iter().collect::<String>())
    })
}

fn cited_limit<'a>(quotes: &[&'a str], turn: &CitedTurn<'a>, summary: &str) -> Option<&'a str> {
    let mut candidates = quotes
        .iter()
        .filter_map(|quote| turn.chapter_text.find(quote).map(|offset| (quote, offset)))
        .flat_map(|(quote, offset)| {
            SCOPED_LIMIT.captures_iter(quote).filter_map(move |claim| {
                let span = claim.get(0)?;
                let body = &quote[span.end()..];
                let scope = claim.name("scope")?.as_str();
                let scope = scope.strip_prefix("因为").unwrap_or(scope);
                let scope = scope.strip_prefix("确实").unwrap_or(scope);
                if !SCOPE.is_match(scope)
                    || !literal_clause(
                        turn.chapter_text,
                        &(offset + span.start()..offset + span.end()),
                    )
                {
                    return None;
                }
                // The actual citation must connect the restricted activity to the
                // summary. Avoid attaching an adjacent number about a different task.
                if !summary.contains(&claim["subject"]) && !shared_activity(body, summary) {
                    return None;
                }
                let already_has_quantity = EXPLICIT_COUNT
                    .captures_iter(summary)
                    .any(|amount| amount["unit"] == claim["unit"]);
                let quote_start = span.start() + claim["scope"].len() - scope.len();
                (!already_has_quantity).then(|| &quote[quote_start..span.end()])
            })
        });
    let first = candidates.next()?;
    candidates
        .all(|candidate| candidate == first)
        .then_some(first)
}

fn period_in_turn<'a>(
    turn: &'a str,
    summary: &str,
    total: &regex::Captures<'_>,
) -> Option<&'a str> {
    let mut ranges = PERIOD_RANGE
        .captures_iter(turn)
        .filter(|period| period["verb"] == total["verb"] && period["unit"] == total["unit"]);
    let period = ranges.next()?;
    let span = period.get(0)?;
    if ranges.next().is_some()
        || summary.contains(&period["period"])
        || period["low"] == period["high"]
        || !literal_clause(turn, &span.range())
    {
        return None;
    }
    let shares_cumulative_count =
        ACTIVITY_COUNT
            .captures_iter(&turn[span.end()..])
            .any(|source_total| {
                source_total["verb"] == total["verb"]
                    && source_total["count"] == total["count"]
                    && source_total["unit"] == total["unit"]
            });
    shares_cumulative_count.then_some(span.as_str())
}

fn cited_period<'a>(
    source: &'a str,
    chapter: &Range<usize>,
    turn: &CitedTurn<'a>,
    names: &[String],
    summary: &str,
) -> Option<&'a str> {
    let total = ACTIVITY_COUNT.captures(summary)?;
    if ACTIVITY_COUNT.captures_iter(summary).nth(1).is_some()
        || !literal_clause(summary, &total.get(0)?.range())
    {
        return None;
    }
    let speaker =
        super::super::speaker_line(turn.full_line, names).filter(|line| !line.unresolved)?;
    let end = (turn.offset + turn.full_line.len()).min(chapter.end);
    let later = source[end..chapter.end].strip_prefix('\n').unwrap_or("");
    // Keep the continued scope inside this chapter and at most two adjacent
    // lines by the cited speaker. A new or unlabelled speaker stops the scan.
    let adjacent = later.split('\n').take(2).take_while(|next| {
        super::super::speaker_line(next, names)
            .is_some_and(|tag| !tag.unresolved && tag.label == speaker.label)
    });
    let mut observed = std::iter::once(turn.chapter_text)
        .chain(adjacent)
        .filter_map(|line| period_in_turn(line, summary, &total));
    let first = observed.next()?;
    observed.all(|other| other == first).then_some(first)
}

pub(super) fn restore(
    session: &CompanionV1HostSession,
    chapter: Range<usize>,
    minutes: &mut CompanionV1MeetingMinutes,
    evidence: &mut Vec<Evidence>,
) {
    let names = super::super::reviewed_speaker_names(session);
    for (index, summary) in minutes.summary.iter_mut().enumerate() {
        if evidence.len() >= 512 || summary.contains("补充原话「") {
            continue;
        }
        let quotes: Vec<&str> = evidence
            .iter()
            .filter(|entry| entry.field == "summary" && entry.index == index)
            .map(|entry| entry.quote.as_str())
            .collect();
        let mut locations = quotes
            .iter()
            .map(|quote| cite_turn(&session.transcript_text, &chapter, quote));
        let Some(Some(turn)) = locations.next() else {
            continue;
        };
        if locations.any(|location| location.as_ref() != Some(&turn)) {
            continue;
        }
        let Some(clause) = cited_limit(&quotes, &turn, summary)
            .or_else(|| cited_period(&session.transcript_text, &chapter, &turn, &names, summary))
        else {
            continue;
        };
        if clause.contains(['「', '」', '\r', '\n']) || summary.len() + clause.len() + 32 > 4096 {
            continue;
        }
        *summary = format!("{}。补充原话「{clause}」。", summary.trim_end_matches('。'));
        if !quotes.contains(&clause) {
            evidence.push(Evidence {
                field: "summary".into(),
                index,
                quote: clause.into(),
            });
        }
    }
}
