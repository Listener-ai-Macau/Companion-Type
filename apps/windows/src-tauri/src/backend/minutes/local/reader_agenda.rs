//! Keep explicit changes and paired choice constraints together before optional ranking.
use std::collections::HashSet;
use std::sync::LazyLock;

use regex::Regex;
use serde_json::Value;

use super::{reader_exchanges::SelectedReply, reader_turns::{Conversation, Turn}};
use super::super::canonical_brief;

fn has(text: &str, cues: &[&str]) -> bool {
    cues.iter().any(|cue| text.contains(cue))
}

fn question_or_report(text: &str) -> bool {
    text.trim_end_matches(['。', '，', ',', ' ', '呢', '呀']).ends_with(['？', '?', '吗'])
        || has(text, &["不是说", "听说", "前年", "曾经", "据说", "说过", "是不是", "要不要"])
}

fn hypothetical(text: &str) -> bool {
    has(text, &["如果", "假设", "万一"])
}

fn boundary(text: &str) -> bool {
    has(text, &["换个话题", "另一个议题", "接下来请", "另一个问题", "下一个问题", "先告一段落", "散会"])
}

fn stopped_between(turns: &[Turn<'_>], start: usize, end: usize) -> bool {
    turns[start.saturating_add(1)..end].iter().any(|turn| boundary(turn.words))
}

fn source_clause(words: &str) -> &str {
    words.trim().trim_end_matches(['。', '！', '，', ',', ' ', '；'])
}

fn quote_parts(turns: &[Turn<'_>], quotes: &[(usize, &str)]) -> Option<SelectedReply> {
    let mut sources = Vec::new();
    let mut lines = Vec::new();
    for &(index, piece) in quotes {
        let row = &turns[index];
        let piece = source_clause(piece);
        if piece.is_empty() || !row.words.contains(piece) {
            return None;
        }
        if !sources.iter().any(|source| source == row.id) {
            sources.push(row.id.to_owned());
        }
        lines.push(piece);
    }
    let text = format!("这项讨论的原话：{}", lines.join("；"));
    canonical_brief::line(&text, 120).then_some(SelectedReply { text, sources, priority: true })
}

fn shared_subject(alternative: &str, support: &str) -> bool {
    const FILLER: &[&str] = &["这个", "那个", "这些", "咱们", "我们", "然后", "可以", "需要", "联系", "一下", "起来", "当地", "就是"];
    let a: Vec<char> = alternative.chars().collect();
    a.windows(2).any(|pair| {
        if !pair.iter().all(|ch| matches!(ch, '\u{3400}'..='\u{9fff}')) {
            return false;
        }
        let term: String = pair.iter().collect();
        !FILLER.contains(&term.as_str()) && support.contains(&term)
    })
}

fn notice(words: &str) -> Option<&str> {
    let start = ["希望", "建议", "应当", "需要", "请"].iter()
        .filter_map(|cue| words.find(cue)).min()?;
    let text = &words[start..];
    let end = ["，因为", "因为", "，如果", "。", "；"].iter()
        .filter_map(|stop| text.find(stop)).min().unwrap_or(text.len());
    let text = &text[..end];
    (text.contains("通知") && (12..=43).contains(&text.chars().count())).then_some(text)
}

fn preparation(words: &str) -> Option<&str> {
    let start = ["需要采购", "需要购买", "需要准备", "需要配备", "建议采购", "建议购买", "建议配备",
        "要采购", "要购买", "要配备", "应当配备", "建议准备"].iter()
        .filter_map(|cue| words.find(cue)).min()?;
    let text = &words[start..];
    let end = ["，", "。", "；"].iter().filter_map(|stop| text.find(stop)).min().unwrap_or(text.len());
    let text = &text[..end];
    (text.chars().count() >= 10 && text.chars().count() <= 35).then_some(text)
}

fn correction(
    turns: &[Turn<'_>], index: usize, protected: &HashSet<&str>,
) -> Option<SelectedReply> {
    static REPLACEMENT: LazyLock<Regex> = LazyLock::new(|| Regex::new(concat!(
        r"(?:不用|不必|不需要|无需)(?P<old>[\p{Han}]{2,9}?)(?:了)?[，,]\s*",
        r"(?P<new>[^。！？；]{0,9}?(?:联系|改用|改为|换成|换用|直接|采用)[^。！？；]{6,33})"
    )).unwrap());
    let current = &turns[index];
    if question_or_report(current.words) || hypothetical(current.words) || protected.contains(current.id) {
        return None;
    }
    let captures = REPLACEMENT.captures(current.words)?;
    let previous = captures.name("old")?.as_str().trim_end_matches('了');
    let replacement = captures.name("new")?.as_str();
    let excerpt = captures.get(0)?.as_str();
    let from = index.saturating_sub(12);
    let prior = &turns[from..index];
    if !prior.iter().any(|turn| turn.words.contains(previous)) {
        return None;
    }
    let relevant = |at: usize| !question_or_report(turns[at].words)
        && !protected.contains(turns[at].id) && !stopped_between(turns, at, index)
        && shared_subject(replacement, turns[at].words);
    let preparation = (from..index).filter(|&at| relevant(at)).rev()
        .find_map(|at| preparation(turns[at].words).map(|quote| (at, quote)))?;
    let notice = (preparation.0.saturating_add(1)..index).filter(|&at| relevant(at))
        .find_map(|at| notice(turns[at].words).map(|quote| (at, quote)))?;
    quote_parts(turns, &[preparation, notice, (index, excerpt)])
}

fn contrasted_example(
    turns: &[Turn<'_>], index: usize, protected: &HashSet<&str>,
) -> Option<SelectedReply> {
    static LIMIT: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:不是所有|并非所有)[\p{Han}]{1,12}都(?:能|要|需要|必须)[\p{Han}]{2,13}"
    ).unwrap());
    static MATCH: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:就得|应该|应当|要|就要|得|需要)(?:对准|针对|面向|选择)[^，,。！？；]{4,23}"
    ).unwrap());
    let row = &turns[index];
    let speaker = row.speaker?;
    let usable = |at: usize| turns[at].speaker == Some(speaker)
        && !protected.contains(turns[at].id) && !question_or_report(turns[at].words);
    if !usable(index) || hypothetical(row.words) { return None; }
    let limitation = LIMIT.find(row.words)?.as_str();
    let later = (index + 1..(index + 14).min(turns.len())).filter(|&at| usable(at) && !hypothetical(turns[at].words)
        && !stopped_between(turns, index, at))
        .find_map(|at| MATCH.find(turns[at].words).map(|quote| (at, quote.as_str())))?;
    let same_audience = ["顾客", "客户", "消费者", "消费人群", "买家"].iter().any(|word| limitation.contains(word))
        && ["顾客", "客户", "消费者", "消费人群", "买家"].iter().any(|word| later.1.contains(word));
    if !same_audience && !shared_subject(limitation, later.1) {
        return None;
    }
    let example = (index.saturating_sub(13)..index).rev().filter(|&at| usable(at)
        && !stopped_between(turns, at, index))
        .find_map(|at| {
            let text = turns[at].words.split_once("比如")?.1;
            let (first, second) = text.split_once("或者")?;
            if !has(first, &["比它", "相比", "更"]) || !has(second, &["比它", "相比", "更"]) {
                return None;
            }
            let start = turns[at].words.find("比如")?;
            let after = &turns[at].words[start..];
            let end = ["，所以", "所以说", "。", "，这样"].iter()
                .filter_map(|marker| after.find(marker)).min().unwrap_or(after.len());
            let quoted = &after[..end];
            (quoted.chars().count() <= 50).then_some((at, quoted))
        })?;
    quote_parts(turns, &[example, (index, limitation), later])
}

pub(super) fn reserve(
    rows: &[Value], protected: &HashSet<&str>,
) -> Vec<SelectedReply> {
    let conversation = Conversation::new(rows);
    let turns = conversation.turns();
    let mut result = Vec::new();
    if let Some(reply) = (0..turns.len()).find_map(|at| correction(turns, at, protected)) {
        result.push(reply);
    }
    if let Some(reply) = (0..turns.len()).find_map(|at| contrasted_example(turns, at, protected)) {
        if !result.iter().any(|earlier| earlier.sources.iter().any(|id| reply.sources.contains(id))) {
            result.push(reply);
        }
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn rows(lines: &[&str]) -> Vec<Value> {
        lines.iter().enumerate().map(|(i,line)|json!({"id":format!("e{i:04}"),"text":line})).collect()
    }

    #[test]
    fn the_replacement_carries_the_preparations_and_the_notice() {
        let source = rows(&[
            "说话人2：接下来这段说一下园区清运。",
            "说话人3：现阶段需要采购封闭式园区回收的专用箱子。",
            "说话人4：希望提醒一下园区住户，建议通知大家园区回收点的位置，因为天气还在变化。",
            "说话人1：需要叫上两辆拖车。",
            "说话人3：我刚才说叫拖车来搬。",
            "说话人4：不用叫拖车了，联系当地的园区回收点就可以了。",
        ]);
        let selected = reserve(&source, &HashSet::new());
        assert_eq!(selected.len(), 1);
        let display = &selected[0].text;
        assert!(display.contains("需要采购"));
        assert!(display.contains("通知"));
        assert!(display.contains("不用叫拖车"));
        assert_eq!(selected[0].sources, ["e0001","e0002","e0005"]);
        let mut conditional = source.clone();
        conditional[5]["text"] = json!("说话人4：如果条件都变了，不用叫拖车了，联系当地的园区回收点就可以了。");
        assert!(reserve(&conditional, &HashSet::new()).is_empty());
    }

    #[test]
    fn a_scope_limit_keeps_a_comparison_and_the_later_audience() {
        let source = rows(&[
            "说话人5：比如说和同类比它更好携带，或者手感上比它更顺手，这些也都是各自的优点。",
            "说话人5：咱们不是所有参观者都要留住，有些人想看其他的。",
            "说话人5：那就得面向喜欢这些展览的参观者。",
        ]);
        let selected = reserve(&source, &HashSet::new());
        assert_eq!(selected.len(), 1);
        assert!(selected[0].text.contains("比如"));
        assert!(selected[0].text.contains("不是所有"));
        assert!(selected[0].text.contains("面向"));
        assert!(reserve(&source, &HashSet::from(["e0002"])).is_empty());
        let mut another_speaker = source;
        another_speaker[2]["text"] = json!("说话人6：那就得面向喜欢这些展览的参观者。");
        assert!(reserve(&another_speaker, &HashSet::new()).is_empty());
    }
}
