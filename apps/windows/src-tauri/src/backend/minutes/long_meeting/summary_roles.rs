use std::{
    collections::{BTreeMap, HashSet},
    ops::Range,
    sync::LazyLock,
};

use regex::{Match, Regex};

use super::{
    summary_review::{cite_turn, one_cited_turn, same_speaker_context},
    CompanionV1HostSession, CompanionV1MeetingMinutes, Evidence,
};

const COMPARISON_LABEL: &str = "补充对比原话";
const HANDOFF_LABEL: &str = "补充分发原话";
static AXIS: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"从(?P<axis>[\p{Han}]{2,10}?)(?:上)?来(?:说|讲|看)").unwrap());
static ACTOR: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
    r"(?P<single>一个人|一个作者|独立作者|单个作者|一人|单人|个人)|(?P<group>大团队|小团队|团队|多人|集体|小组|跨部门)"
).unwrap()
});
static OUTCOME: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"有优势|占优势|是强项|是长处|更稳定|更快|更有力|最顶端|更完整|更复杂").unwrap()
});
static HANDOFF: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
    r"由(?P<collector>[\p{Han}]{2,12}?)把[^。！？；\r\n]{6,36}?(?:汇总|收集好|整理好)[^。！？；\r\n]{0,22}?提前[0-9一二两三四五六七八九十]{1,4}(?:个工作日|工作日|个月|星期|天|周)(?:让|请|由)[\p{Han}]{2,10}?(?:发给|转给|交给)(?P<relay>[\p{Han}]{2,14})[，,]\s*(?:再)?由(?P<recipient>[\p{Han}]{2,12}?)(?:一次性(?:的|地)?|统一|再|随后|直接|逐一|负责)?(?:把[\p{Han}]{1,7}?)?(?:发给|转给|交给)[\p{Han}]{2,22}"
).unwrap()
});

#[derive(Clone, Copy, PartialEq, Eq)]
enum Participant {
    Individual,
    Group,
}

fn participants(text: &str) -> impl Iterator<Item = (Match<'_>, Participant)> {
    ACTOR.captures_iter(text).filter_map(|captured| {
        let actor = captured.get(0)?;
        if text[..actor.start()].ends_with(['每', '各']) {
            return None;
        }
        let kind = if captured.name("single").is_some() {
            Participant::Individual
        } else {
            Participant::Group
        };
        Some((actor, kind))
    })
}

fn comparison_side(body: &str) -> Option<(Participant, Vec<&str>)> {
    let mut actors = participants(body);
    let (actor, kind) = actors.next()?;
    if actors.any(|(_, other)| other != kind) {
        return None;
    }
    let description = body[actor.start()..]
        .split(['，', ',', '。', '；', '！', '？'])
        .next()?
        .trim();
    let evaluation = body
        .split(['，', ',', '。', '；', '！', '？'])
        .map(str::trim)
        .rev()
        .find(|line| {
            OUTCOME.is_match(line)
                && !["没有优势", "不占优势", "不是强项", "不具备", "并非"]
                    .iter()
                    .any(|word| line.contains(word))
        })?;
    if description.chars().count() > 54
        || evaluation.chars().count() > 54
        || !body[actor.start()..].contains(evaluation)
    {
        return None;
    }
    let mut spans = vec![description];
    if !description.contains(evaluation) {
        spans.push(evaluation);
    }
    Some((kind, spans))
}

fn two_axes<'a>(line: &'a str, summary: &str) -> Option<Vec<Vec<&'a str>>> {
    let mut headers = Vec::new();
    for item in AXIS.captures_iter(line) {
        let axis = item.name("axis")?.as_str();
        if headers.last().is_none_or(|(last, _)| *last != axis) {
            headers.push((axis, item.get(0)?));
        }
    }
    let [(left_axis, left), (right_axis, right)] = headers.as_slice() else {
        return None;
    };
    if !summary.contains(left_axis) || !summary.contains(right_axis) {
        return None;
    }
    let (first, mut left_quotes) = comparison_side(&line[left.end()..right.start()])?;
    let (second, mut right_quotes) = comparison_side(&line[right.end()..])?;
    let mentioned: Vec<_> = participants(summary).map(|(_, kind)| kind).collect();
    if first == second || mentioned.contains(&first) && mentioned.contains(&second) {
        return None;
    }
    left_quotes.insert(0, left.as_str());
    right_quotes.insert(0, right.as_str());
    Some(vec![left_quotes, right_quotes])
}

fn handoff_in_line<'a>(line: &'a str, summary: &str) -> Option<&'a str> {
    let mut candidates = HANDOFF.captures_iter(line).filter_map(|parsed| {
        let raw = parsed.get(0)?;
        let relay = &parsed["relay"];
        let next = &parsed["recipient"];
        let relay = ["各班", "每班", "各组", "每组", "各位", "各"]
            .iter()
            .find_map(|prefix| relay.strip_prefix(prefix))
            .unwrap_or(relay);
        if relay != next
            || parsed["collector"] == parsed["recipient"]
            || [
                "如果",
                "假设",
                "若是",
                "要不要",
                "能不能",
                "计划",
                "建议",
                "预计",
                "考虑",
            ]
            .iter()
            .any(|cue| raw.as_str().contains(cue))
            || line[raw.end()..].trim_start().starts_with(['？', '?'])
            || summary.contains("提前")
            || ![
                "传达", "发放", "转发", "下发", "分发", "汇总", "发送", "发给",
            ]
            .iter()
            .any(|verb| summary.contains(verb))
        {
            return None;
        }
        let before = &line[..raw.start()];
        let preceding_clause = before.rsplit(['。', '；', '！', '？']).next().unwrap_or("");
        if ["如果", "假设", "若是", "也许", "可能", "是不是"]
            .iter()
            .any(|clue| preceding_clause.contains(clue))
        {
            return None;
        }
        // The preceding topic must already be in the summary. A handoff
        // from a later unrelated topic by the same speaker cannot be added.
        let context: Vec<char> = before.chars().rev().take(200).collect();
        let linked = context.windows(5).any(|chars| {
            chars
                .iter()
                .all(|ch| matches!(*ch, '\u{3400}'..='\u{9fff}'))
                && summary.contains(&chars.iter().rev().collect::<String>())
        });
        linked.then_some(raw.as_str())
    });
    let first = candidates.next()?;
    candidates.all(|other| other == first).then_some(first)
}

pub(super) fn restore(
    session: &CompanionV1HostSession,
    chapter: Range<usize>,
    minutes: &mut CompanionV1MeetingMinutes,
    evidence: &mut Vec<Evidence>,
) {
    let source = &session.transcript_text;
    let names = super::super::reviewed_speaker_names(session);
    for (index, summary) in minutes.summary.iter_mut().enumerate() {
        if summary.contains(COMPARISON_LABEL)
            || summary.contains(HANDOFF_LABEL)
            || evidence.len() > 506
        {
            continue;
        }
        let quotes: Vec<&str> = evidence
            .iter()
            .filter(|row| row.field == "summary" && row.index == index)
            .map(|row| row.quote.as_str())
            .collect();
        let mut turns = BTreeMap::new();
        for quote in quotes.iter().copied().collect::<HashSet<_>>() {
            if let Some(turn) = cite_turn(source, &chapter, quote) {
                let occurrence = turns.entry(turn.offset).or_insert((turn, 0usize));
                occurrence.1 += 1;
            }
        }
        let mut comparisons = turns
            .values()
            .filter(|(turn, count)| {
                *count >= 2
                    && super::super::speaker_line(turn.full_line, &names)
                        .is_some_and(|label| !label.unresolved)
            })
            .filter_map(|(turn, _)| two_axes(turn.chapter_text, summary));
        let result = if let Some(sides) = comparisons.next() {
            if comparisons.next().is_some() {
                continue;
            }
            Some((COMPARISON_LABEL, sides))
        } else {
            one_cited_turn(source, &chapter, &quotes).and_then(|turn| {
                let lines = same_speaker_context(source, &chapter, &turn, &names, 7, 16 * 1024)?;
                let mut matches = lines
                    .into_iter()
                    .filter_map(|line| handoff_in_line(line, summary));
                let first = matches.next()?;
                matches
                    .all(|other| other == first)
                    .then_some((HANDOFF_LABEL, vec![vec![first]]))
            })
        };
        let Some((label, rows)) = result else {
            continue;
        };
        if rows
            .iter()
            .flatten()
            .any(|span| span.contains(['「', '」', '\r', '\n']) || span.len() > 1024)
        {
            continue;
        }
        let appended = rows
            .iter()
            .map(|side| {
                side.iter()
                    .map(|quote| format!("「{quote}」"))
                    .collect::<Vec<_>>()
                    .join("")
            })
            .collect::<Vec<_>>()
            .join("。另一侧原话");
        let complete = format!("{}。{label}{appended}。", summary.trim_end_matches('。'));
        if complete.len() > 4096 {
            continue;
        }
        let mut present = quotes.into_iter().collect::<HashSet<_>>();
        let new_quotes = rows
            .into_iter()
            .flatten()
            .filter(|span| present.insert(span))
            .map(str::to_string)
            .collect::<Vec<_>>();
        *summary = complete;
        for quote in new_quotes {
            evidence.push(Evidence {
                field: "summary".into(),
                index,
                quote,
            });
        }
    }
}
