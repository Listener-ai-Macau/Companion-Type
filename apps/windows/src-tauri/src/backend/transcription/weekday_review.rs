//! Verify an ambiguous relative week near a transcription boundary against the recording.
use std::{fs::File, ops::Range, sync::LazyLock};

use crate::companion_v1::CompanionV1UtteranceSegment;
use super::{battery_term_review::read_audio, shared::Runtime};

static WEEK: LazyLock<regex::Regex> = LazyLock::new(|| {
    regex::Regex::new(r"下{1,2}周[一二三四五六日天]").expect("valid relative weekday pattern")
});

fn review_instruction(text: &str) -> bool {
    let clause: String = text.split(['。', '；', '！', '？']).next().unwrap_or_default()
        .chars().take(40).collect();
    clause.contains('再')
        && ["确认", "确定", "核对", "复核", "审阅", "商定"].iter().any(|verb| clause.contains(verb))
        && !["不要", "不用", "不需要", "如果", "比如", "或者", "还是", "不是", "是否", "提议", "建议", "可以", "改成"]
            .iter().any(|uncertain| clause.contains(uncertain))
}

fn ambiguous_week(text: &str) -> Option<Range<usize>> {
    let mut weeks = WEEK.find_iter(text);
    let day = weeks.next()?;
    (weeks.next().is_none() && day.as_str().starts_with("下下")
        && text[..day.start()].chars().take(13).count() < 13
        && review_instruction(&text[day.end()..])).then(|| day.range())
}

fn confirms_week(text: &str, expected: &str) -> bool {
    let mut weeks = WEEK.find_iter(text);
    let Some(day) = weeks.next() else { return false; };
    let prefix = &text[..day.start()];
    day.as_str() == expected && weeks.next().is_none() && !prefix.ends_with('下')
        && !["如果", "比如", "建议", "不是", "改成"].iter().any(|cue| prefix.contains(cue))
        && review_instruction(&text[day.end()..])
}

pub(super) fn candidates(texts: &[String], anchors: &[CompanionV1UtteranceSegment]) -> Vec<(usize, Range<usize>)> {
    texts.iter().enumerate().skip(1).filter_map(|(index, text)| {
        let gap = anchors[index].start_ms.saturating_sub(anchors[index - 1].end_ms);
        if gap > 500 {
            return None;
        }
        ambiguous_week(text).map(|weekday| (index, weekday))
    }).take(2).collect()
}

pub(super) fn apply(
    reviewer: &Runtime, file: &mut File, data: (u64, u64),
    texts: &mut [String], anchors: &[CompanionV1UtteranceSegment],
    candidates: Vec<(usize, Range<usize>)>, check_cancelled: &mut impl FnMut() -> Result<(), String>,
) -> Result<(), String> {
    for (index, weekday) in candidates {
        let start = anchors[index].start_ms;
        let expected = &texts[index][weekday.start + '下'.len_utf8()..weekday.end];
        let mut confirmed = true;
        // Context on both sides restores the short phrase near the original
        // cut. All windows must agree before changing a date.
        for (before, after) in [(3_300, 6_000), (5_200, 5_200), (7_000, 4_500)] {
            check_cancelled()?;
            let Some(pcm) = read_audio(file, data.0, data.1, start.saturating_sub(before), start + after) else {
                confirmed = false;
                break;
            };
            if !reviewer.transcribe(&pcm).is_ok_and(|review| confirms_week(&review, expected)) {
                confirmed = false;
                break;
            }
        }
        if confirmed {
            texts[index].replace_range(weekday.start..weekday.start + '下'.len_utf8(), "");
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn accepts_only_matching_unambiguous_rechecks_in_review_context() {
        assert!(ambiguous_week("好吧下下周三的时候我们再再具体上核对一下").is_some());
        assert!(ambiguous_week("回顾了下下周三的可售库存").is_none());
        assert!(confirms_week("然后下周三的时候我们再具体商确定一下", "下周三"));
        for source in [
            "然后下下周三再确认",
            "然后下周四再确认",
            "下周三或者下周四再确定",
            "如果下周三的时候再确认",
            "下周三的时候不需要再确认",
            "下周三的时候通报进度",
        ] {
            assert!(!confirms_week(source, "下周三"), "{source}");
        }
    }
}
