//! Verify consequential terms that were lost near a chunk boundary or came
//! out garbled. The alternative recognizer must agree across two short spans.
use std::{fs::File, sync::LazyLock};

use regex::Regex;

use super::{battery_term_review::read_audio, shared::Runtime};
use crate::companion_v1::CompanionV1UtteranceSegment;

const METRICS: &[&str] = &["粉丝量", "观看量", "阅读量", "曝光量"];
const QUALITY_REQUIREMENT: &str = "也要保证质量";

pub(super) enum Review {
    Quality { previous: usize },
    PromotionMetric { index: usize, token: String },
}

pub(super) fn candidates(texts: &[String]) -> Vec<Review> {
    static INCLUDED: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(
            r"包括(?:说(?:及)?|了)?(?P<metric>[\x{3400}-\x{9fff}]{2,5}?)(?:的)?问题[，, ]*(?:咱们|我们)?都要",
        )
        .expect("valid spoken selection criteria pattern")
    });
    let mut reviews = Vec::new();
    for (index, text) in texts.iter().enumerate() {
        if let Some(previous) = index.checked_sub(1) {
            if text.contains("越便宜越好")
                && text.contains("送的东西")
                && (text.contains("大家看不上") || text.contains("客户看不上"))
                && texts[previous].contains("越便宜")
                && !texts[previous].contains("保证质量")
                && !text.contains("保证质量")
            {
                reviews.push(Review::Quality { previous });
            }
        }
        if text.contains("档期")
            && (text.contains("费用") || text.contains("报价") || text.contains("预算"))
        {
            if let Some(metric) = INCLUDED.captures(text).and_then(|m| m.name("metric")) {
                let token = metric.as_str();
                if text.matches(token).count() == 1 && !METRICS.contains(&token) {
                    reviews.push(Review::PromotionMetric {
                        index,
                        token: token.to_owned(),
                    });
                }
            }
        }
        if reviews.len() >= 2 {
            break;
        }
    }
    reviews
}

fn explicit_quality(text: &str) -> Option<&'static str> {
    (text.contains(QUALITY_REQUIREMENT)
        && text.contains("不能说越便宜越好")
        && ![
            "不需要保证质量",
            "不用保证质量",
            "并非也要保证质量",
            "不必保证质量",
            "能不能保证质量",
        ]
        .iter()
        .any(|cue| text.contains(cue)))
    .then_some(QUALITY_REQUIREMENT)
}

fn supported_metric(text: &str) -> Option<&'static str> {
    if !text.contains("档期") || !text.contains("要考虑") {
        return None;
    }
    let mut supported = METRICS.iter().copied().filter(|term| {
        text.contains(&format!("{term}问题")) || text.contains(&format!("{term}的问题"))
    });
    let metric = supported.next()?;
    supported.next().is_none().then_some(metric)
}

pub(super) fn apply(
    runtime: &Runtime,
    file: &mut File,
    range: (u64, u64),
    texts: &mut [String],
    anchors: &[CompanionV1UtteranceSegment],
    reviews: Vec<Review>,
    mut check: impl FnMut() -> Result<(), String>,
) -> Result<(), String> {
    for review in reviews {
        let (ranges, validate): ([_; 3], fn(&str) -> Option<&'static str>) = match &review {
            Review::Quality { previous } => {
                let seam = anchors[*previous].end_ms;
                (
                    [(4_600, 7_400), (3_600, 8_400), (5_600, 6_400)]
                        .map(|(left, right)| (seam.saturating_sub(left), seam + right)),
                    explicit_quality,
                )
            }
            Review::PromotionMetric { index, .. } => {
                let from = anchors[*index].start_ms;
                (
                    [(0, 11_800), (1_600, 11_600), (2_600, 13_600)]
                        .map(|(offset, end)| (from + offset, from + end)),
                    supported_metric,
                )
            }
        };
        let mut confirmed = None;
        for (from, to) in ranges {
            check()?;
            let Some(audio) = read_audio(file, range.0, range.1, from, to) else {
                continue;
            };
            let Ok(text) = runtime.transcribe(&audio) else {
                continue;
            };
            let Some(value) = validate(&text) else {
                continue;
            };
            if let Some(first) = confirmed {
                if first != value {
                    break;
                }
                match &review {
                    // The quality clause starts before the boundary we reread.
                    Review::Quality { previous } => {
                        let prior = &mut texts[*previous];
                        if !prior.ends_with(['。', '！', '？', '.', '!', '?']) {
                            prior.push('。');
                        }
                        prior.push_str(QUALITY_REQUIREMENT);
                        prior.push('。');
                    }
                    Review::PromotionMetric { index, token } => {
                        texts[*index] = texts[*index].replacen(token, value, 1);
                    }
                }
                break;
            }
            confirmed = Some(value);
        }
    }
    check()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn confirmations_require_the_constraint_and_its_context() {
        assert_eq!(
            explicit_quality("也要保证质量吧，我觉得也不能说越便宜越好"),
            Some("也要保证质量")
        );
        assert!(explicit_quality("不用保证质量，不能说越便宜越好").is_none());
        assert_eq!(
            supported_metric("粉丝量的问题也要考虑，还要看档期"),
            Some("粉丝量")
        );
        assert!(supported_metric("粉丝量问题或阅读量问题都要考虑，还要看档期").is_none());
        let raw = vec!["费用上计然后包括某近音问题我们都要考虑而且应该是档期问题".to_owned()];
        let reviews = candidates(&raw);
        assert!(
            matches!(reviews.as_slice(), [Review::PromotionMetric { index: 0, token }] if token == "某近音")
        );
        assert!(
            candidates(&["费用上计然后包括阅读量的问题我们都要考虑档期".to_owned()]).is_empty()
        );
    }
}
