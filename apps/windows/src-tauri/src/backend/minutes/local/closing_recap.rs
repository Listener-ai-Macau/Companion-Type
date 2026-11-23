//! Promote concrete follow-ups and amounts from an explicitly announced recap.
use std::sync::LazyLock;

use regex::Regex;
use serde_json::Value;

use super::source_review::bare;
use super::super::source_resolution::split_turn_label;

pub(super) struct ClosingRecap<'a> {
    pub(super) start: usize,
    pub(super) budget_statements: Vec<(&'a str, &'a str)>,
}

fn has(text: &str, cues: &[&str]) -> bool {
    cues.iter().any(|cue| text.contains(cue))
}

fn tentative(text: &str) -> bool {
    text.contains(['？', '?'])
        || has(text, &["假设", "比如", "如果", "还没定", "尚未", "要不要", "能不能", "听说"])
}

fn amount() -> &'static Regex {
    static AMOUNT: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"[0-9零一二三四五六七八九十百两点.]+(?:到[0-9零一二三四五六七八九十百两点.]+)?(?:千元|万元|万块|千块|万|千|元|块钱)",
    ).expect("an explicitly stated currency amount"));
    &AMOUNT
}

fn stated_budget(text: &str) -> Option<&str> {
    static SUBJECT: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:^|[，,。； ])(?:那|关于)?(?P<subject>[\p{Han}]{2,10}?)(?:这件事儿?|这一项|这块儿?|这一块儿?|方面)",
    ).expect("a named item in the closing recap"));
    if tentative(text) || !has(text, &["最后", "最终", "以此为准", "统一口径"])
        || !has(text, &["费用", "预算", "采购", "外包", "报价"])
        || !amount().is_match(text)
    {
        return None;
    }
    let subject = SUBJECT.captures(text)?.name("subject")?.as_str();
    (!has(subject, &["这个", "那个", "然后"])).then_some(subject)
}

pub(super) fn detect(sentences: &[Value]) -> Option<ClosingRecap<'_>> {
    let first = sentences.len() * 3 / 5;
    let (start, lead) = (first..sentences.len()).find_map(|index| {
        let raw = sentences[index]["text"].as_str()?;
        let (lead, text) = split_turn_label(raw)?;
        if tentative(text) || !has(text, &["会议主题总结", "总结一下会议", "总结一下今天", "把今天的会议总结", "会议做个总结", "我做个会议总结", "现在总结"])
        {
            return None;
        }
        let confirmation = (index..(index + 3).min(sentences.len())).take_while(|&pos| {
            sentences[pos]["text"].as_str().is_some_and(|row| {
                split_turn_label(row).is_none_or(|(speaker, _)| speaker == lead)
            })
        }).any(|pos| sentences[pos]["text"].as_str().is_some_and(|row| {
            has(bare(row), &["最后的方案", "最终方案", "后续安排", "确认的事项", "费用和最后", "确认的决定"])
        }));
        confirmation.then_some((index,lead))
    })?;
    let mut active = Some(lead);
    let mut budget_statements = Vec::new();
    for row in &sentences[start..] {
        let Some(raw) = row["text"].as_str() else { continue };
        if let Some((speaker, _)) = split_turn_label(raw) {
            active = Some(speaker);
        }
        if active != Some(lead) {
            continue;
        }
        let text = bare(raw);
        if has(text, &["现在散会", "会议到这里结束", "大家散会"]) {
            break;
        }
        if let Some((id, subject)) = row["id"].as_str().zip(stated_budget(text)) {
            budget_statements.push((id, subject));
        }
    }
    Some(ClosingRecap { start, budget_statements })
}

pub(super) fn timed_followup(text: &str) -> bool {
    let text = bare(text);
    !tentative(text)
        && has(text, &["下周", "本周", "明天", "后天", "下个月", "月底", "月内", "下次"])
        && has(text, &["你找", "你去", "由你", "负责", "再次开会", "再开会", "复盘", "再次核对", "再次检查"])
        && !has(text, &["我建议", "仅供参考", "看情况再", "再说吧"])
}

pub(super) fn early_estimate(text: &str, subject: &str) -> bool {
    let text = bare(text);
    text.contains(subject) && has(text, &["大概可能", "预计", "先估", "初步估计"])
        && has(text, &["费用", "预算", "报价"]) && amount().is_match(text)
}

#[cfg(test)]
mod tests {
    #[test]
    fn closing_context_requires_an_announced_recap_and_its_scope() {
        let row = |id,text| serde_json::json!({"id":id,"text":text});
        let data = [
            row("e0000","说话人2: 先讨论展位，预计费用五千元。"),
            row("e0001","说话人2: 延期要核对实际流程。"),
            row("e0002","说话人1: 各自提出想法。"),
            row("e0003","说话人1: 我做个会议总结，最后的方案再说一下。"),
            row("e0004","这件事还要确认。"),
        ];
        assert_eq!(super::detect(&data).unwrap().start,3);
        assert!(super::detect(&data[..3]).is_none());
        assert!(super::timed_followup("说话人1: 我们下周五再次开会检查进展。"));
        assert!(!super::timed_followup("说话人1: 如果有进展，下周五再开会？"));
    }
}
