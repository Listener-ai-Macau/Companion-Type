//! Recheck consequential calendar details against the original audio.
use std::{fs::File, ops::Range, sync::LazyLock};

use regex::Regex;

use super::{battery_term_review::read_audio, shared::Runtime};
use crate::companion_v1::CompanionV1UtteranceSegment;

static WORK_WEEK: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"周一(?:到|至)周?五").expect("valid work-week range"));
static CONTRAST: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?P<day>周[一二三四五])[、，, ]*周[日天]").expect("valid spoken day pair")
});
static WEEKEND: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"周六[、，, ]*周[日天]").expect("valid weekend pair"));
static UNCLEAR_DATE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?P<anchor>大概|暂定|预计)(?:要|是|在){0,3}(?P<continuation>画(?:上)?日程|划(?:上)?日程|安排日程|排日程)")
        .expect("valid unfinished schedule phrase")
});
static DATE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(concat!(
        r"(?P<qualifier>大概|暂定|预计)(?:要|是|在|定在){0,3}",
        r"(?P<day>(?:[1-9]|[12][0-9]|3[01]|[一二三四五六七八九]|[一二]?十[一二三四五六七八九]?|三十一?)[号日])",
    ))
    .expect("valid tentative day of month")
});

#[derive(Clone, Copy)]
enum Kind<'a> {
    Weekend,
    TentativeDate(&'a str),
}

pub(super) struct Candidate<'a> {
    index: usize,
    replace: Range<usize>,
    kind: Kind<'a>,
}

pub(super) fn candidates(texts: &[String]) -> Vec<Candidate<'_>> {
    let mut found = Vec::new();
    for (index, text) in texts.iter().enumerate() {
        if WORK_WEEK.is_match(text) && !WEEKEND.is_match(text) {
            let mut pairs = CONTRAST.captures_iter(text);
            if let Some(pair) = pairs.next().filter(|_| pairs.next().is_none()) {
                found.push(Candidate {
                    index,
                    replace: pair.name("day").expect("named weekday").range(),
                    kind: Kind::Weekend,
                });
            }
        }
        if !DATE.is_match(text) && text.contains("排班") {
            if let Some(phrase) = UNCLEAR_DATE.captures(text) {
                let qualifier = phrase.name("anchor").expect("named qualifier");
                let continuation = phrase.name("continuation").expect("named continuation");
                found.push(Candidate {
                    index,
                    replace: qualifier.start()..continuation.start(),
                    kind: Kind::TentativeDate(qualifier.as_str()),
                });
            }
        }
    }
    found.truncate(2);
    found
}

fn verify(kind: Kind<'_>, fresh: &str) -> Option<String> {
    if [
        "不是", "改到", "改成", "还是", "或者", "假如", "如果", "不用", "不要",
    ]
    .iter()
    .any(|cue| fresh.contains(cue))
    {
        return None;
    }
    match kind {
        Kind::Weekend if WEEKEND.find_iter(fresh).count() == 1 && !CONTRAST.is_match(fresh) => {
            Some("周六".into())
        }
        Kind::TentativeDate(qualifier) if fresh.contains("排班") || fresh.contains("日程") => {
            let mut dates = DATE.captures_iter(fresh);
            let date = dates.next()?;
            (dates.next().is_none() && date["qualifier"] == *qualifier)
                .then(|| format!("{qualifier}{}，", &date["day"]))
        }
        _ => None,
    }
}

pub(super) fn apply(
    recognizer: &Runtime,
    file: &mut File,
    data: (u64, u64),
    texts: &mut [String],
    anchors: &[CompanionV1UtteranceSegment],
    mut check: impl FnMut() -> Result<(), String>,
) -> Result<(), String> {
    let mut edits = Vec::new();
    for candidate in candidates(texts) {
        let anchor = &anchors[candidate.index];
        let text = &texts[candidate.index];
        let length = text.chars().count().max(1) as u64;
        let offset = text[..candidate.replace.start].chars().count() as u64;
        let center = anchor.start_ms + (anchor.end_ms - anchor.start_ms) * offset / length;
        // Both crops contain the suspected phrase. Do not treat the estimated
        // center as a word timestamp.
        let windows = [(5_600, 5_900), (6_600, 5_200)];
        let mut first = None;
        for (left, right) in windows {
            check()?;
            let text = read_audio(
                file,
                data.0,
                data.1,
                center.saturating_sub(left),
                center + right,
            )
            .and_then(|pcm| recognizer.transcribe(&pcm).ok());
            let Some(replacement) = text
                .as_deref()
                .and_then(|text| verify(candidate.kind, text))
            else {
                break;
            };
            if let Some(first) = &first {
                if *first == replacement {
                    edits.push((candidate.index, candidate.replace, replacement));
                }
                break;
            }
            first = Some(replacement);
        }
    }
    // Byte ranges were computed on the recognizer's original result.
    edits.sort_by_key(|(index, range, _)| (*index, range.start));
    for (index, range, replacement) in edits.into_iter().rev() {
        texts[index].replace_range(range, &replacement);
    }
    check()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn calendar_rechecks_require_an_explicit_contrast_or_unclear_tentative_date() {
        let samples = [
            "周一至周五基本人不多周一周日还行".into(),
            "周一周日还行".into(),
            "周一至周五基本人不多周六周日还行".into(),
            "搬家这些流程就是大概要要画日程了然后定一下排班".into(),
            "搬家暂定二十号再安排日程和排班".into(),
        ];
        let revisions = candidates(&samples);
        assert_eq!(
            revisions.iter().map(|x| x.index).collect::<Vec<_>>(),
            [0, 3]
        );
        assert_eq!(&samples[0][revisions[0].replace.clone()], "周一");
        assert_eq!(&samples[3][revisions[1].replace.clone()], "大概要要");
        assert_eq!(
            verify(Kind::Weekend, "人不多周六周日还行").as_deref(),
            Some("周六")
        );
        assert!(verify(Kind::Weekend, "周一周日还行不是周六周日").is_none());
        assert_eq!(
            verify(
                Kind::TentativeDate("大概"),
                "搬家大概要二十号然后我们定一下排班"
            )
            .as_deref(),
            Some("大概二十号，"),
        );
        assert!(verify(
            Kind::TentativeDate("大概"),
            "大概二十号或者大概二十一号再讨论排班"
        )
        .is_none());
        assert!(verify(Kind::TentativeDate("大概"), "大概要二十号逛商场").is_none());
    }
}
