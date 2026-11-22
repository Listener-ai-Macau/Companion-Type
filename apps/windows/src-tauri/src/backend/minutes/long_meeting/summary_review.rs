use std::{ops::Range, sync::LazyLock};

use regex::Regex;

use super::{CompanionV1HostSession, CompanionV1MeetingMinutes, Evidence};

static RELATIVE_SPEAKER: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"^(?:一位发言者[（(])?说话人[0-9]+(?:之前|之后|前面|后面)的(?:发言者|讲话者)[）)]?")
        .unwrap()
});
static PERIOD_PAIR: LazyLock<Regex> = LazyLock::new(|| {
    let period = r"每天|每日|每星期|每周|每个月|每月|每季度|每季|每年";
    Regex::new(&format!(r"({period})[ \t]*({period})")).unwrap()
});

#[derive(PartialEq, Eq)]
pub(super) struct CitedTurn<'a> {
    pub(super) offset: usize,
    pub(super) full_line: &'a str,
    pub(super) chapter_text: &'a str,
}

pub(super) fn cite_turn<'a>(
    full: &'a str,
    chapter: &Range<usize>,
    quote: &str,
) -> Option<CitedTurn<'a>> {
    if quote.is_empty() || quote.contains('\n') {
        return None;
    }
    let mut matches = full.match_indices(quote);
    let (start, _) = matches.next()?;
    if matches.next().is_some() || start < chapter.start || start + quote.len() > chapter.end {
        return None;
    }
    let line_start = full[..start].rfind('\n').map_or(0, |previous| previous + 1);
    let line_end = full[start..]
        .find('\n')
        .map_or(full.len(), |length| start + length);
    Some(CitedTurn {
        offset: line_start,
        full_line: &full[line_start..line_end],
        chapter_text: &full[line_start.max(chapter.start)..line_end.min(chapter.end)],
    })
}

pub(super) fn one_cited_turn<'a>(
    source: &'a str,
    chapter: &Range<usize>,
    quotes: &[&str],
) -> Option<CitedTurn<'a>> {
    let (first, rest) = quotes.split_first()?;
    let turn = cite_turn(source, chapter, first)?;
    rest.iter()
        .all(|quote| cite_turn(source, chapter, quote).as_ref() == Some(&turn))
        .then_some(turn)
}

pub(super) fn same_speaker_lines<'a>(
    source: &'a str,
    chapter: &Range<usize>,
    turn: &CitedTurn<'a>,
    names: &[String],
) -> Option<Vec<&'a str>> {
    let speaker =
        super::super::speaker_line(turn.full_line, names).filter(|line| !line.unresolved)?;
    let end = (turn.offset + turn.full_line.len()).min(chapter.end);
    let later = source[end..chapter.end].strip_prefix('\n').unwrap_or("");
    // A new or unlabelled speaker stops the scan. A chapter cannot borrow
    // evidence after its source boundary.
    let adjacent = later.split('\n').take(2).take_while(|next| {
        super::super::speaker_line(next, names)
            .is_some_and(|tag| !tag.unresolved && tag.label == speaker.label)
    });
    Some(std::iter::once(turn.chapter_text).chain(adjacent).collect())
}

fn period_label(value: &str) -> &str {
    match value {
        "每日" => "每天",
        "每星期" => "每周",
        "每个月" => "每月",
        "每季度" => "每季",
        _ => value,
    }
}

fn clause_tail(value: &str) -> &str {
    value
        .split([
            '，', '。', '；', '、', ',', '.', ';', '？', '！', '?', '!', '：', ':',
        ])
        .next()
        .unwrap_or("")
        .trim_end()
}

fn same_activity(left: &str, right: &str) -> bool {
    // A shared suffix anchors the frequency to the activity in this clause.
    // Separate frequency phrases and unrelated activities are left alone.
    left.chars()
        .rev()
        .zip(right.chars().rev())
        .take_while(|(a, b)| a == b && matches!(*a, '\u{3400}'..='\u{9fff}'))
        .take(2)
        .count()
        == 2
}

pub(super) fn review(
    session: &CompanionV1HostSession,
    chapter: Range<usize>,
    minutes: &mut CompanionV1MeetingMinutes,
    evidence: &mut Vec<Evidence>,
) {
    let names = super::super::reviewed_speaker_names(session);
    for (index, summary) in minutes.summary.iter_mut().enumerate() {
        let relative_speaker = RELATIVE_SPEAKER
            .find(summary)
            .map(|matched| matched.range());
        if relative_speaker.is_none() && !PERIOD_PAIR.is_match(summary) {
            continue;
        }
        let mut quotes = evidence
            .iter()
            .filter(|entry| entry.field == "summary" && entry.index == index);
        let turn = quotes
            .next()
            .and_then(|entry| cite_turn(&session.transcript_text, &chapter, &entry.quote))
            .filter(|turn| {
                quotes.all(|entry| {
                    cite_turn(&session.transcript_text, &chapter, &entry.quote).as_ref()
                        == Some(turn)
                })
            });
        if let Some(prefix) = relative_speaker {
            let tag = turn
                .as_ref()
                .and_then(|turn| super::super::speaker_line(turn.full_line, &names))
                .filter(|speaker| !speaker.unresolved)
                .map_or("一位发言者（归属待核对）", |speaker| {
                    speaker.label
                });
            summary.replace_range(prefix, tag);
        }
        let Some(turn) = turn else { continue };
        let mut ranges = Vec::new();
        for stated in PERIOD_PAIR.captures_iter(summary) {
            let pair = stated.get(0).unwrap();
            let first = period_label(&stated[1]);
            let second = period_label(&stated[2]);
            if first == second {
                continue;
            }
            let activity = clause_tail(&summary[pair.end()..]);
            for original in PERIOD_PAIR.captures_iter(turn.chapter_text) {
                let start = original.get(0).unwrap();
                let tail = clause_tail(&turn.chapter_text[start.end()..]);
                if second == period_label(&original[1])
                    && first == period_label(&original[2])
                    && same_activity(activity, tail)
                {
                    ranges.push(pair.range());
                    let quote = &turn.chapter_text[start.start()..start.end() + tail.len()];
                    if quote.len() <= 1024
                        && evidence.len() < 512
                        && !evidence.iter().any(|entry| {
                            entry.field == "summary" && entry.index == index && entry.quote == quote
                        })
                    {
                        evidence.push(Evidence {
                            field: "summary".into(),
                            index,
                            quote: quote.into(),
                        });
                    }
                    break;
                }
            }
        }
        for range in ranges.into_iter().rev() {
            summary.replace_range(range, "（频率待核对）");
        }
    }
}
