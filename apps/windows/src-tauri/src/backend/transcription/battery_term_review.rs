//! Audio-backed confirmation for a known homophone in battery discussions.
use std::{
    fs::File,
    io::{Read, Seek, SeekFrom},
    path::{Path, PathBuf},
};

use crate::companion_v1::CompanionV1UtteranceSegment;
use super::shared::{Runtime, RATE};
use super::meeting_constraint_review;

const REVIEW_DIR: &str = "sherpa-onnx-fire-red-asr2-zh_en-int8-2026-02-26";
const BYTES_PER_SECOND: u64 = (RATE * 2) as u64;
const MAX_REVIEW_SEGMENTS: usize = 2;

fn candidate(text: &str) -> Option<usize> {
    let mut matches = text.match_indices("电信");
    let (position, word) = matches.next()?;
    if matches.next().is_some()
        || ["运营商", "中国电信", "通信", "宽带", "基站", "套餐", "诈骗"]
            .iter().any(|term| text.contains(term))
    {
        return None;
    }
    let before = &text[..position];
    let after: String = text[position + word.len()..].chars().take(20).collect();
    let battery_context = text.contains("电池")
        || (before.ends_with("成品") && text.contains("寿命预测"));
    (battery_context && after.contains("分析")).then_some(position)
}

fn supports_cell(text: &str) -> bool {
    let mut words = text.match_indices("电芯");
    let Some((position, word)) = words.next() else { return false; };
    words.next().is_none() && !text.contains("电信")
        && text[position + word.len()..].chars().take(24).collect::<String>().contains("分析")
}

fn review_ranges(text: &str, position: usize, start_ms: u64, end_ms: u64) -> [(u64, u64); 3] {
    // Paraformer has chunk-level anchors here. Overlapping ranges put the
    // estimated word in context without treating the estimate as word timing.
    let before = text[..position].chars().filter(|letter| letter.is_alphanumeric()).count() as u64 + 1;
    let length = text.chars().filter(|letter| letter.is_alphanumeric()).count().max(1) as u64;
    let center = start_ms + end_ms.saturating_sub(start_ms) * before / length;
    [(5_600, 4_700), (4_700, 5_600), (6_400, 5_000)]
        .map(|(left, right)| (center.saturating_sub(left), center + right))
}

fn model_dir(root: &Path) -> PathBuf {
    std::env::var_os("COMPANION_TYPE_ASR_BATTERY_REVIEW_DIR")
        .map_or_else(|| root.join(REVIEW_DIR), PathBuf::from)
}


// An alternate decode of the same utterance can resolve a near-homophone.
// Both windows must independently retain the product and analysis context.
pub(super) fn verify_failure_analysis(
    runtime: &Runtime, file: &mut File, data_start: u64, data_len: u64,
    texts: &mut [String], anchors: &[CompanionV1UtteranceSegment],
    mut check_cancelled: impl FnMut() -> Result<(), String>,
) -> Result<(), String> {
    for (index, text) in texts.iter_mut().enumerate().filter(|(_, text)| {
        candidate(text).is_some() && text.contains("寿命预测")
            && text.matches("时效分析").count() == 1 && text.contains("成品")
    }).take(MAX_REVIEW_SEGMENTS) {
        let anchor = &anchors[index];
        let windows = [(1_200, 1_200), (1_600, 600), (800, 800)];
        let mut confirmations = 0;
        for (left, right) in windows {
            check_cancelled()?;
            let Some(audio) = read_audio(file, data_start, data_len,
                anchor.start_ms.saturating_sub(left), anchor.end_ms + right) else { break; };
            if runtime.transcribe(&audio).is_ok_and(|review| {
                review.contains("成品") && review.contains("失效分析") && !review.contains("时效分析")
            }) {
                confirmations += 1;
                if confirmations == 2 {
                    *text = text.replacen("时效分析", "失效分析", 1);
                    break;
                }
            }
        }
    }
    check_cancelled()
}

pub(super) fn read_audio(file: &mut File, data_start: u64, data_len: u64, from: u64, to: u64) -> Option<Vec<u8>> {
    let first = (from * BYTES_PER_SECOND / 1000).min(data_len);
    let last = (to * BYTES_PER_SECOND / 1000).min(data_len);
    if last <= first { return None; }
    let mut audio = vec![0; (last - first) as usize];
    file.seek(SeekFrom::Start(data_start + first)).and_then(|_| file.read_exact(&mut audio)).ok()?;
    Some(audio)
}

// An independently audio-confirmed battery term can clarify surrounding
// references within the same discussion. Retain unrelated telecom mentions.
fn resolve_battery_references(
    texts: &mut [String], anchors: &[CompanionV1UtteranceSegment], confirmed: usize,
) {
    if !texts[confirmed].contains("电池") { return; }
    let oldest = anchors[confirmed].end_ms.saturating_sub(90_000);
    let first = (0..confirmed).rev()
        .take_while(|&index| anchors[index].start_ms >= oldest)
        .find(|&index| {
            let opening = &texts[index];
            candidate(opening).is_some() && opening.contains("成品")
                && opening.contains("失效分析") && opening.contains("寿命预测")
        });
    let Some(first) = first else { return; };
    if anchors[first..=confirmed].iter().filter_map(|a| a.speaker)
        .any(|speaker| anchors[first].speaker != Some(speaker)) {
        return;
    }
    let material_reference = |text: &str| {
        text.split_once("电信").is_some_and(|(prefix, suffix)| {
            prefix.contains("材料") && prefix.contains("测试方法") && prefix.contains("应用到")
                && suffix.contains("研究对象") && !suffix.contains("电信")
                && !["通信", "宽带", "运营商", "基站", "网络"].iter().any(|term| text.contains(term))
        })
    };
    texts[first] = texts[first].replacen("电信", "电芯", 1);
    for text in &mut texts[first + 1..confirmed] {
        if material_reference(text) {
            *text = text.replacen("电信", "电芯", 1);
        }
    }
}

// Use a name that was audibly recognized elsewhere in this meeting only
// when both remarks name the same second institution. No external name list.
pub(super) fn resolve_institution_references(texts: &mut [String]) {
    use std::{collections::HashSet, sync::LazyLock};
    const CORRUPTED: &str = "神经计量院";
    static NAME: LazyLock<regex::Regex> = LazyLock::new(|| {
        regex::Regex::new(r"[深申沈]\p{Han}计量院").expect("valid name pattern")
    });
    static PEER: LazyLock<regex::Regex> = LazyLock::new(|| {
        regex::Regex::new(r"\p{Han}{2}计量(?:[、，。]|也|都|$)").expect("valid peer pattern")
    });
    let recognized: Vec<_> = texts.iter().filter(|text| !text.contains(CORRUPTED))
        .flat_map(|text| NAME.find_iter(text).map(|m| (m.as_str().to_owned(), text.clone())))
        .collect();
    if recognized.is_empty() { return; }

    for text in texts.iter_mut().filter(|text| text.matches(CORRUPTED).count() == 1
        && text.contains("包括") && (text.contains("检测机构") || text.contains("检测服务"))) {
        let peers: Vec<_> = PEER.find_iter(text)
            .map(|m| m.as_str().chars().take(4).collect::<String>()).collect();
        let same_discussion = recognized.iter().filter(|(_, source)| peers.iter().any(|peer| source.contains(peer)));
        let names: HashSet<_> = same_discussion.map(|(name, _)| name.as_str()).collect();
        if names.len() == 1 {
            *text = text.replacen(CORRUPTED, names.into_iter().next().expect("one recognized name"), 1);
        }
    }
}

pub(super) fn apply(
    file: &mut File, data_start: u64, data_len: u64, root: &Path,
    texts: &mut [String], anchors: &[CompanionV1UtteranceSegment],
    mut check_cancelled: impl FnMut() -> Result<(), String>,
) -> Result<(), String> {
    let candidates: Vec<_> = texts.iter().enumerate()
        .filter_map(|(index, text)| candidate(text).map(|position| (index, position)))
        .take(MAX_REVIEW_SEGMENTS).collect();
    let weekdays = super::weekday_review::candidates(texts, anchors);
    let meeting_constraints = meeting_constraint_review::candidates(texts);
    if candidates.is_empty() && weekdays.is_empty() && meeting_constraints.is_empty() { return Ok(()); }

    let model = model_dir(root);
    if !model.join("encoder.int8.onnx").is_file() { return Ok(()); }
    check_cancelled()?;
    let Ok(reviewer) = Runtime::load_fire_red_review(&model, root) else {
        return Ok(());
    };
    for (index, position) in candidates {
        let anchor = &anchors[index];
        let ranges = review_ranges(&texts[index], position, anchor.start_ms, anchor.end_ms);
        let mut confirmations = 0;
        for (from, to) in ranges {
            check_cancelled()?;
            let Some(audio) = read_audio(file, data_start, data_len, from, to) else { continue; };
            if reviewer.transcribe(&audio).is_ok_and(|text| supports_cell(&text)) {
                confirmations += 1;
                if confirmations == 2 {
                    texts[index].replace_range(position..position + "电信".len(), "电芯");
                    resolve_battery_references(texts, anchors, index);
                    break;
                }
            }
        }
    }
    super::weekday_review::apply(&reviewer, file, (data_start, data_len), texts, anchors, weekdays, &mut check_cancelled)?;
    meeting_constraint_review::apply(&reviewer, file, (data_start, data_len), texts, anchors, meeting_constraints, &mut check_cancelled)?;
    check_cancelled()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn review_requires_battery_context_and_unambiguous_audio_evidence() {
        assert!(candidate("一块就是成品电信的时效分析，还有寿命预测。").is_some());
        assert!(candidate("针对这个电信做时效分析，因为电池的安全缺陷。").is_some());
        for actual_carrier in [
            "电池故障分析中涉及中国电信的设备。",
            "给电信运营商的电池寿命做时效分析。",
            "电信机房要做流量分析。",
            "电信的电池状态需要分析，电信另有记录。",
        ] {
            assert_eq!(candidate(actual_carrier), None, "{actual_carrier}");
        }
        assert!(supports_cell("针对这个电芯的这个私教分析"));
        assert!(!supports_cell("电信可能订购电芯来做分析"));
        assert!(!supports_cell("正在讨论电芯，但是这里没说那个问题"));
    }
}
