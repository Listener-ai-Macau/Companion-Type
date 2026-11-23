//! Promote concrete follow-ups and amounts from an explicitly announced recap.
use std::sync::LazyLock;

use regex::Regex;
use serde_json::Value;

use super::source_review::bare;
use super::super::source_resolution::split_turn_label;

pub(super) struct ClosingRecap<'a> {
    pub(super) start: usize,
    lead: &'a str,
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
    Some(ClosingRecap { start, lead, budget_statements })
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

pub(super) struct RecapHandoff {
    pub(super) item: crate::companion_v1::CompanionV1ActionItem,
    pub(super) citations: Vec<usize>,
    pub(super) directive: usize,
}

fn recap_subject(text: &str) -> Option<&str> {
    static SUBJECT: LazyLock<Regex> = LazyLock::new(|| Regex::new(concat!(
        r"^(?:[呃嗯啊哦对好，,\s]|那|然后|接下来|另外)*",
        r"(?:第[一二三四五六七八九十0-9]+个(?:问题|事项)?(?:就是关于|是关于|就是|是)|还有一个问题是关于|就是|是)",
        r"(?P<item>[\p{Han}]{2,14}?)(?:这块儿?|这件事儿?|这一项|这方面|[，,。]|$)"
    )).expect("an item introduced by the meeting recap"));
    let subject = SUBJECT.captures(text)?.name("item")?.as_str();
    (!has(subject, &["这个", "那个", "我们", "他们", "还是"])).then_some(subject)
}

fn assignment(text: &str) -> Option<&str> {
    static DIRECT: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:由你|你来|你[，, ]+来)(?:[来去就先再给把啊呃嗯，, ]|后续){0,12}(?P<operation>跟进|执行|把控|负责|发(?:个|一下|一个)?通知|整理|核对|采购|联系|协调|处理|提交|准备|查验|复核|登记|汇报)",
    ).expect("direct assignment to the person being addressed"));
    if tentative(text) || has(text, &["不用你", "不由你", "你不必", "别安排", "建议你", "可以由你", "之前", "曾经", "上次", "去年", "以前"]) {
        return None;
    }
    let operation = DIRECT.captures(text)?.name("operation")?.as_str();
    if has(text, &["现在请你", "在会上直接", "当场回答", "当场汇报"])
        || (operation=="汇报" && !has(text, &["会后", "下周", "明天", "后天", "月底"]))
    {
        return None;
    }
    Some(operation)
}

fn numbered_speaker(label: &str) -> bool {
    label.strip_prefix("说话人").or_else(|| label.strip_prefix("发言人"))
        .is_some_and(|n| !n.is_empty() && n.chars().all(|c| c.is_ascii_digit()))
}

fn assent(text: &str, operation: &str, adjacent: bool) -> bool {
    if tentative(text) || has(text, &["不行", "不能", "不负责", "不是我", "我不", "需要再确认", "到时候再看"])
    {
        return false;
    }
    let chunks = text.split(['，', ',', '。', '！', '!']).map(|s| {
        s.trim().trim_matches([' ', '嗯', '啊', '呃', '哦'])
    }).filter(|s| !s.is_empty()).collect::<Vec<_>>();
    let repeated_yes = !chunks.is_empty() && chunks.iter().all(|part| {
        part.strip_prefix("没问题").is_some_and(|tail| tail.is_empty() || tail == "没问题")
    });
    let volunteered_same_work = if operation.contains("通知") {
        has(text, &["我来发个通知", "我来发通知", "我来发一下通知"])
    } else {
        let opt = ["我来", "我负责"].iter()
            .find_map(|prefix| text.split_once(prefix).map(|(_,after)| after));
        opt.is_some_and(|after| {
            after.trim_start_matches([' ', '去', '做', '来']).starts_with(operation)
        })
    };
    volunteered_same_work || (adjacent && (repeated_yes
        || has(text, &["我来我来没问题", "我来，没问题", "我负责，没问题"])))
}

fn extra_work_detail(text: &str, section: &str, operation: &str) -> (String,Option<String>) {
    static DATED: LazyLock<Regex> = LazyLock::new(|| Regex::new(concat!(
        r"(?P<due>下周[一二三四五六日天]?|本周[一二三四五六日天]?|明天|后天)",
        r"[，, ]*(?:你|你就|由你)\s*(?P<work>(?:找|联系|准备|整理|提交|核对)[^，,。！？；;]{3,34})"
    )).expect("dated next step spoken by the recap speaker"));
    if operation=="执行" {
        if let Some(parts) = DATED.captures(text) {
            return (format!("{section}：{}", &parts["work"]),Some(parts["due"].to_owned()));
        }
    }
    (format!("{section}：{operation}"),None)
}

fn changes_topic(text: &str) -> bool {
    recap_subject(text.trim()).is_some()
        || has(text, &["换个话题", "换一件事", "下一个问题", "另一个问题", "最后一项", "接下来说"])
}

impl ClosingRecap<'_> {
    pub(super) fn accepted_handoffs(&self, sentences: &[Value]) -> Vec<RecapHandoff> {
        use crate::companion_v1::CompanionV1ActionItem;
        let mut result = Vec::new();
        let mut section = None;
        for index in self.start+1..sentences.len() {
            let Some(raw) = sentences[index]["text"].as_str() else { continue };
            let Some((speaker, text)) = split_turn_label(raw) else { continue };
            if speaker != self.lead { continue; }
            if has(text, &["现在散会", "会议到这里结束", "大家散会"]) { break; }
            if let Some(topic) = recap_subject(text.trim()) {
                section = Some((index,topic));
            } else if changes_topic(text) {
                section = None;
            }
            let Some((topic_turn,topic)) = section.filter(|(start,_)| index-start <= 60) else { continue };
            let extension = sentences.get(index+1).and_then(|line| line["text"].as_str())
                .filter(|line| split_turn_label(line).is_none()
                    && has(line, &["来去", "来负责", "来跟进", "就负责", "安排一下", "把控"]));
            let combined = extension.map(|line| {
                let lead = text.trim_end_matches(['。','，', ' ']).trim_end_matches("那个");
                format!("{lead}{line}")
            });
            let Some(operation) = assignment(combined.as_deref().unwrap_or(text)) else { continue };
            let start_reply = index + 1 + usize::from(extension.is_some());
            let mut immediate = true;
            let mut channel = None;
            let mut found = None;
            for pos in start_reply..(start_reply+3).min(sentences.len()) {
                let Some(line) = sentences[pos]["text"].as_str() else { break; };
                if let Some((answerer, words)) = split_turn_label(line) {
                    if answerer == speaker { break; }
                    if numbered_speaker(answerer) && assent(words,operation,immediate) {
                        found = Some((pos,answerer)); break;
                    }
                    if operation.contains("通知") && has(words, &["群里", "群内"])
                        && has(words, &["说一下", "发一下", "发个通知", "说一声"])
                    {
                        channel = Some(pos);
                    } else if !words.trim().is_empty() {
                        break;
                    }
                    immediate = false;
                } else if !line.trim().trim_matches([' ', '嗯', '呃', '啊', '哦', '。', '，', ',']).is_empty() {
                    break;
                }
            }
            let Some((acceptance,owner)) = found else { continue };
            let contradictory = sentences.iter().skip(acceptance+1).take(2).any(|row| {
                row["text"].as_str().and_then(split_turn_label).is_some_and(|(label,words)| {
                    (label==speaker && has(words, &["不是你", "改由", "改让", "先不安排"]))
                    || (label!=speaker && label!=owner && assent(words,operation,false))
                })
            });
            if contradictory { continue; }
            let opener = bare(sentences[topic_turn]["text"].as_str().unwrap());
            let subject = if operation.contains("通知") {
                opener.split_once("把").and_then(|(_,tail)| tail.split([',','，','。']).next())
                    .filter(|name| (2..=14).contains(&name.chars().count())).unwrap_or(topic)
            } else { topic };
            let mut citations = vec![topic_turn,index];
            if extension.is_some() { citations.push(index+1); }
            if let Some(pos)=channel { citations.push(pos); }
            citations.push(acceptance);
            let mut work = extra_work_detail(text,subject,operation);
            if operation=="执行" && work.1.is_none() {
                for pos in acceptance+1..(acceptance+9).min(sentences.len()) {
                    let Some(row)=sentences[pos]["text"].as_str() else { break; };
                    let Some((next,spoken))=split_turn_label(row) else { continue; };
                    if next!=speaker { continue; }
                    if changes_topic(spoken) || tentative(spoken) { break; }
                    let specifics=extra_work_detail(spoken,subject,operation);
                    if specifics.1.is_some() {
                        work=specifics;citations.push(pos);break;
                    }
                }
            }
            if operation.contains("通知") && channel.is_some() {
                work.0 = format!("{subject}：在群里发通知");
            }
            if operation=="把控" {
                for pos in acceptance+1..(acceptance+5).min(sentences.len()) {
                    let Some(row)=sentences[pos]["text"].as_str() else { break; };
                    let Some((next,spoken))=split_turn_label(row) else { continue; };
                    if next!=speaker { continue; }
                    if changes_topic(spoken) || tentative(spoken) { break; }
                    if spoken.contains(subject) && has(spoken, &["结束以后", "结束后", "完成以后", "完成后", "通过以后"]) {
                        let first_cue=spoken.find('等').or_else(||spoken.find('待'));
                        if let Some(start)=first_cue {
                            let clause=spoken[start..].trim().trim_end_matches(['。','，',' ']);
                            if clause.chars().count() <= 25 {
                                work.0.push_str(&format!("（{clause}）")); citations.push(pos);
                            }
                        }
                        break;
                    }
                }
            }
            citations.sort_unstable();
            citations.dedup();
            let owner=owner.to_owned();
            if result.iter().any(|task: &RecapHandoff| task.item.text==work.0) { continue; }
            result.push(RecapHandoff {item:CompanionV1ActionItem {text:work.0,owner:Some(owner),due:work.1},citations,directive:index});
        }
        result
    }
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
    #[test]
    fn anonymous_handoff_requires_a_direct_request_and_a_specific_reply() {
        let row=|id,text|serde_json::json!({"id":id,"text":text});
        let mut data=vec![
            row("e0000","说话人1: 先列出材料。"),
            row("e0001","说话人2: 费用登记过了。"),
            row("e0002","说话人1: 其余费用之后再说。"),
            row("e0003","说话人1: 我做个会议总结，最后的方案再说一下。"),
            row("e0004","说话人1: 第一个是库存。"),
            row("e0005","说话人1: 那就你来核对库存。"),
            row("e0006","说话人2: 没问题，没问题。\n"),
        ];
        let recap=super::ClosingRecap {start:3,lead:"说话人1",budget_statements:vec![]};
        let found=recap.accepted_handoffs(&data);
        assert_eq!(found.len(),1);
        assert_eq!(found[0].item.owner.as_deref(),Some("说话人2"));
        assert_eq!(found[0].citations,[4,5,6]);
        data[6]=row("e0006","说话人3: 好。");
        assert!(recap.accepted_handoffs(&data).is_empty());
        data[6]=row("e0006","说话人2: 我来核对。");
        data.push(row("e0007","说话人1: 不是你，改由仓库小组。"));
        assert!(recap.accepted_handoffs(&data).is_empty());
        data.pop();
        data[5]=row("e0005","说话人1: 你来汇报一下这几天当场看到的问题。");
        data[6]=row("e0006","说话人2: 没问题。");
        assert!(recap.accepted_handoffs(&data).is_empty());

        data[4]=row("e0004","说话人1: 然后是志愿活动这块，通知要把集合地点写清楚。");
        data[5]=row("e0005","说话人1: 你来发个通知。");
        data[6]=row("e0006","嗯。\n");
        data.push(row("e0007","说话人4: 群里说一下就行了。\n"));
        data.push(row("e0008","说话人3: 我来发个通知。\n"));
        let found=recap.accepted_handoffs(&data);
        assert_eq!(found.len(),1);
        assert_eq!(found[0].item.owner.as_deref(),Some("说话人3"));
        assert_eq!(found[0].citations,[4,5,7,8]);
    }
}
