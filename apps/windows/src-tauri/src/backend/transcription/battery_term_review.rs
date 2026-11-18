//! Audio-backed confirmation for a known homophone in battery discussions.
use std::{
    fs::File,
    io::{Read, Seek, SeekFrom},
    path::{Path, PathBuf},
};

use crate::companion_v1::CompanionV1UtteranceSegment;
use super::shared::{Runtime, RATE};

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

pub(super) fn apply(
    file: &mut File, data_start: u64, data_len: u64, root: &Path,
    texts: &mut [String], anchors: &[CompanionV1UtteranceSegment],
    mut check_cancelled: impl FnMut() -> Result<(), String>,
) -> Result<(), String> {
    let candidates: Vec<_> = texts.iter().enumerate()
        .filter_map(|(index, text)| candidate(text).map(|position| (index, position)))
        .take(MAX_REVIEW_SEGMENTS).collect();
    if candidates.is_empty() { return Ok(()); }

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
            let first = (from * BYTES_PER_SECOND / 1000).min(data_len);
            let last = (to * BYTES_PER_SECOND / 1000).min(data_len);
            if last <= first { continue; }
            let mut audio = vec![0; (last - first) as usize];
            if file.seek(SeekFrom::Start(data_start + first)).and_then(|_| file.read_exact(&mut audio)).is_err() {
                break;
            }
            if reviewer.transcribe(&audio).is_ok_and(|text| supports_cell(&text)) {
                confirmations += 1;
                if confirmations == 2 {
                    texts[index].replace_range(position..position + "电信".len(), "电芯");
                    break;
                }
            }
        }
    }
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
