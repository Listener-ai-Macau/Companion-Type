//! Preserve whether a statement was an example or a third-party report even
//! when the transcript cuts the explanation into several evidence sentences.
use std::ops::Range;

use serde_json::Value;

use super::{super::source_resolution::split_turn_label, timed_evidence::Timing};

#[derive(Clone, Copy, PartialEq, Eq)]
pub(super) enum Kind {
    Example,
    Reported,
}

pub(super) struct Frame {
    pub(super) sentences: Range<usize>,
    pub(super) kind: Kind,
}

fn text(sentences: &[Value], index: usize) -> &str {
    let text = sentences[index]["text"].as_str().expect("source sentence").trim();
    split_turn_label(text).map_or(text, |(_, words)| words.trim())
}

fn has(text: &str, words: &[&str]) -> bool {
    words.iter().any(|word| text.contains(word))
}

fn opening(words: &str) -> Option<Kind> {
    if has(words, &["告示", "公告", "通告", "通知", "一张纸", "一份文件", "一条消息", "网上", "新闻"])
        && has(words, &["我看到", "看到这么", "看到一张", "有人说", "听说", "据说", "转述", "上面写", "网传"])
        && has(words, &["可能", "据了解", "据称", "看到", "声称", "写着", "听说", "网传"])
    {
        return Some(Kind::Reported);
    }
    let start = ["比方说", "举个例子", "举一个例子", "比如举例", "假设有个例子", "模拟一下"]
        .into_iter().filter_map(|cue| words.find(cue)).min()?;
    let lead = &words[..start];
    // A confirmed arrangement in the lead still owns its wording. This
    // frame is for an utterance introducing an example as such.
    if lead.chars().count() <= 25
        && !has(lead, &["负责", "已经", "确定", "截止", "共计", "必须", "已批准", "必须先", "结论是"])
    {
        Some(Kind::Example)
    } else {
        None
    }
}

fn filler(words: &str) -> bool {
    words.chars().all(|c| c.is_whitespace() || "嗯啊哦呃好对是行，。！？".contains(c))
}

fn changes_context(words: &str) -> bool {
    let words = words.trim_start_matches(|c: char| c.is_whitespace() || "嗯呃哦啊对，,".contains(c));
    ["回到实际", "实际安排是", "实际上我们", "换个话题", "下一项", "下一个", "接下来讨论",
        "关于另一项", "经核实", "我们核实了", "现已确认", "以此为准", "我决定", "会议决定",
        "说回正题", "现实里", "别把这个当成"].iter().any(|cue| words.starts_with(cue))
}

fn continues_reference(kind: Kind, words: &str) -> bool {
    let words = words.trim_start_matches(|c: char| c.is_whitespace() || "嗯呃哦啊对，,".contains(c));
    match kind {
        Kind::Reported => ["其中", "上面写", "上面说", "告示里", "通知里", "里面写", "纸上", "它说",
            "告示称", "通知称"].iter().any(|cue| words.starts_with(cue)),
        Kind::Example => ["这个例子", "在这个例子", "这个假设", "假设中", "示例中"]
            .iter().any(|cue| words.starts_with(cue)),
    }
}

pub(super) fn frames(sentences: &[Value], timing: Option<&Timing<'_>>) -> Vec<Frame> {
    let mut frames = Vec::new();
    let mut start = 0;
    while start < sentences.len() {
        let Some(kind) = opening(text(sentences, start)) else {
            start += 1;
            continue;
        };
        let mut end = start + 1;
        // A verified utterance establishes its own extent. Without timing,
        // continue only inside the same source line or by explicit reference.
        let same_line = |end: usize| {
            !sentences[start..end].iter().any(|row| row["text"].as_str().unwrap().contains('\n'))
        };
        while end < (start + 8).min(sentences.len()) {
            let words = text(sentences, end);
            if changes_context(words) || opening(words).is_some() { break; }
            let same_speech = if let Some(timing) = timing {
                timing.covered_by_one_utterance(&[start,end])
            } else {
                same_line(end)
            };
            if !same_speech {
                let lookahead = if filler(words) { end + 1 } else { end };
                if lookahead >= sentences.len()
                    || !continues_reference(kind,text(sentences,lookahead))
                    || !timing.is_none_or(|timing| timing.neighboring_speech(end - 1,lookahead)) {
                    break;
                }
            }
            end += 1;
        }
        frames.push(Frame { sentences:start..end, kind });
        start = end;
    }
    frames
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::backend::minutes::{automatic_brief::factual_audit::evidence_sentences, canonical_brief::source_units};
    use crate::companion_v1::CompanionV1UtteranceSegment;

    #[test]
    fn an_example_covers_fragments_of_the_same_utterance() {
        let rows = [
            "比方说，把一件货挂到网店里，是吧？然后来了三十个订单。接着卖出两百件。",
            "回到实际，这周只准备五件样品。",
        ];
        let source = rows.join("\n");
        let sentences = evidence_sentences(&source_units(&source));
        let utterances: Vec<_> = rows.iter().enumerate().map(|(i, text)| CompanionV1UtteranceSegment {
            text: (*text).into(), start_ms: i as u64 * 3000, end_ms: i as u64 * 3000 + 2500,
            speaker: None, approximate_timing: false,
        }).collect();
        let timing = Timing::verified(&source, &sentences, &utterances).unwrap();
        let revised = frames(&sentences,Some(&timing));
        assert_eq!(revised.len(),1);
        assert_eq!(revised[0].sentences,0..3);
        assert!(revised[0].kind==Kind::Example);
    }

    #[test]
    fn attribution_crosses_an_acknowledgment_but_does_not_spread_to_a_new_topic() {
        let source = "我看到一张告示，可能是对方贴的。\n嗯。\n其中有一条儿说本月不开放。\n下一项，讨论维修安排。";
        let sentences = evidence_sentences(&source_units(source));
        let revised = frames(&sentences,None);
        assert_eq!(revised.len(),1);
        assert_eq!(revised[0].sentences,0..3);
        assert!(revised[0].kind==Kind::Reported);
    }
}
