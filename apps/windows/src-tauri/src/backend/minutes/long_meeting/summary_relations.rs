use std::{ops::Range, sync::LazyLock};

use regex::Regex;

use super::{
    summary_review::{one_cited_turn, same_speaker_lines},
    CompanionV1HostSession, CompanionV1MeetingMinutes, Evidence,
};

const LABEL: &str = "补充条件原话";
static IF_THEN: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
    r"(?:如果|若是|要是)(?P<condition>[^，。！？；\r\n]{3,54})[，,]\s*(?:那么|那就|则)(?P<result>[^。！？；\r\n]{3,68})"
).unwrap()
});
static NEGATIVE_OUTCOME: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"没有用|没用|不起作用|失去作用|无效|白费|不再适用|不能|无法|不会|不可|不成立")
        .unwrap()
});
static EXCEPTION: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
    r"(?P<bound>(?:可以|允许|也能)(?:超出|超过|突破)[^，。！？；\r\n]{2,28})[，,][^。！？；\r\n]{1,70}?(?:但是|不过|但)(?P<effect>[^。！？；\r\n]{2,35}(?:预期|理解|判断|看法)[^。！？；\r\n]{0,16}?(?:改变|变化))[，,](?P<result>[^。！？；\r\n]{5,78})"
).unwrap()
});
static PREREQUISITE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
    r"(?:拐点|转折点|前提)(?:应该|可能|通常|往往)?(?:是|在|要)[^。！？；\r\n]{4,74}?(?:成熟|完成|达标|就绪|完善)(?:之后|以后|后)[，,][^。！？；\r\n]{0,15}?(?:只有当|只有|必须)(?P<condition>[^。！？；\r\n]{3,42}?)才(?:可以|能|会|可)(?P<result>[^。！？；\r\n]{4,64})"
).unwrap()
});

fn shared_chinese(source: &str, summary: &str, width: usize, minimum: usize) -> bool {
    let chars: Vec<char> = source.chars().collect();
    let mut witnesses = Vec::with_capacity(minimum);
    for part in chars.windows(width) {
        if !part.iter().all(|ch| matches!(*ch, '\u{3400}'..='\u{9fff}')) {
            continue;
        }
        let part: String = part.iter().collect();
        if [
            "我们", "他们", "这个", "那个", "其实", "已经", "真正", "觉得", "那么", "之一", "之后",
            "以前", "应该", "这样", "可以", "需要", "时候", "就是",
        ]
        .contains(&part.as_str())
            || !summary.contains(&part)
            || witnesses.contains(&part)
        {
            continue;
        }
        witnesses.push(part);
        if witnesses.len() == minimum {
            return true;
        }
    }
    false
}

fn statement_fragment(source: &str, end: usize) -> bool {
    // The patterns end before the closing punctuation. Consult the original
    // line so a question cannot become an asserted relationship.
    !source[end..].trim_start().starts_with(['？', '?'])
}

fn stops_before_shift(text: &str) -> &str {
    let end = ["但是", "不过", "，所以", "，因此"]
        .iter()
        .filter_map(|cue| text.find(cue))
        .min()
        .unwrap_or(text.len());
    text[..end].trim_end_matches([',', '，', ' '])
}

fn if_then<'a>(source: &'a str, summary: &str) -> Option<Vec<&'a str>> {
    let mut candidates = IF_THEN.captures_iter(source).filter_map(|relation| {
        let exact = relation.get(0)?;
        let condition = &relation["condition"];
        let result = &relation["result"];
        let negative = NEGATIVE_OUTCOME.find(result)?.as_str();
        if !statement_fragment(source, exact.end())
            || condition.contains("是否")
            || !shared_chinese(condition, summary, 2, 1)
            || !shared_chinese(result, summary, 3, 1)
            || summary.contains(negative)
            || (["没有用", "没用", "无效", "白费", "不起作用"].contains(&negative)
                && ["没有用", "没用", "无效", "白费", "不起作用"]
                    .iter()
                    .any(|cue| summary.contains(cue)))
        {
            return None;
        }
        Some(vec![exact.as_str()])
    });
    let first = candidates.next()?;
    candidates.all(|other| other == first).then_some(first)
}

fn exception<'a>(source: &'a str, summary: &str) -> Option<Vec<&'a str>> {
    let mut candidates = EXCEPTION.captures_iter(source).filter_map(|relation| {
        let exact = relation.get(0)?;
        let bound = relation.name("bound")?.as_str();
        let effect = relation.name("effect")?;
        let result = relation.name("result")?;
        let reading = stops_before_shift(result.as_str());
        if !statement_fragment(source, exact.end())
            || !["超出", "超过", "突破"]
                .iter()
                .any(|clue| summary.contains(clue) && bound.contains(clue))
            || !["预期", "理解", "判断", "看法"]
                .iter()
                .any(|clue| summary.contains(clue) && effect.as_str().contains(clue))
            || !["当成", "看作", "理解为", "理解成", "视为", "误认为", "判为"]
                .iter()
                .any(|clue| reading.contains(clue))
            || shared_chinese(reading, summary, 4, 1)
        {
            return None;
        }
        Some(vec![
            bound,
            &source[effect.start()..result.start() + reading.len()],
        ])
    });
    let first = candidates.next()?;
    candidates.all(|other| other == first).then_some(first)
}

fn prerequisite<'a>(source: &'a str, summary: &str) -> Option<Vec<&'a str>> {
    let mut candidates = PREREQUISITE.captures_iter(source).filter_map(|relation| {
        let exact = relation.get(0)?;
        let result = relation.name("result")?;
        let outcome = stops_before_shift(result.as_str());
        if !statement_fragment(source, exact.end())
            || outcome.chars().count() < 4
            || !shared_chinese(outcome, summary, 2, 2)
            || !["难以", "很难", "无法", "不会", "不能", "还没"]
                .iter()
                .any(|cue| summary.contains(cue))
            || ["成熟", "就绪", "达标", "只有", "转折点", "拐点", "才能"]
                .iter()
                .any(|cue| summary.contains(cue))
        {
            return None;
        }
        Some(vec![&source[exact.start()..result.start() + outcome.len()]])
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
        if summary.contains(LABEL) || evidence.len() > 510 {
            continue;
        }
        let quotes: Vec<&str> = evidence
            .iter()
            .filter(|entry| entry.field == "summary" && entry.index == index)
            .map(|entry| entry.quote.as_str())
            .collect();
        let Some(turn) = one_cited_turn(source, &chapter, &quotes) else {
            continue;
        };
        let Some(lines) = same_speaker_lines(source, &chapter, &turn, &names) else {
            continue;
        };
        let mut matches = lines.into_iter().flat_map(|line| {
            [
                if_then(line, summary),
                exception(line, summary),
                prerequisite(line, summary),
            ]
            .into_iter()
            .flatten()
        });
        let Some(spans) = matches.next() else {
            continue;
        };
        if matches.any(|other| other != spans)
            || spans
                .iter()
                .any(|span| span.contains(['「', '」', '\r', '\n']) || span.len() > 1024)
        {
            continue;
        }
        drop(matches);
        let addition = spans
            .iter()
            .map(|span| format!("「{span}」"))
            .collect::<Vec<_>>()
            .join("、");
        let updated = format!("{}。{LABEL}{addition}。", summary.trim_end_matches('。'));
        if updated.len() > 4096 {
            continue;
        }
        *summary = updated;
        for span in spans
            .into_iter()
            .filter(|span| !quotes.contains(span))
            .map(str::to_string)
            .collect::<Vec<_>>()
        {
            evidence.push(Evidence {
                field: "summary".into(),
                index,
                quote: span,
            });
        }
    }
}
