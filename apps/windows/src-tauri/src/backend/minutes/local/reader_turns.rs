//! Keep the source of a visible answer or confirmed assignment together when
//! short acknowledgements split the underlying transcript into several rows.
use serde_json::Value;
use std::collections::HashSet;

use super::super::{canonical_brief, source_resolution::split_turn_label};
use super::{reader_context::ExamplePassage, source_context, source_review};

pub(super) struct Turn<'a> {
    pub(super) id: &'a str,
    pub(super) speaker: Option<&'a str>,
    pub(super) words: &'a str,
}

pub(super) struct Conversation<'a> {
    turns: Vec<Turn<'a>>,
}

pub(super) struct Answer<'a> {
    pub(super) text: String,
    pub(super) sources: Vec<&'a str>,
}

fn has(text: &str, cues: &[&str]) -> bool {
    cues.iter().any(|cue| text.contains(cue))
}

fn phrase(text: &str) -> &str {
    text.trim()
        .trim_end_matches(['，', ',', '。', '！', '？', '.', '；', ' '])
}

fn acknowledgement(text: &str) -> bool {
    let text = phrase(text);
    matches!(
        text,
        "好的" | "是的" | "可以" | "收到" | "明白了" | "我知道了"
    ) || text.chars().all(|c| "啊哦嗯呃好对是行，。 ".contains(c))
}

fn opening_question(text: &str) -> bool {
    source_context::question_only(text)
        || has(
            text,
            &[
                "想问",
                "是什么",
                "怎么办",
                "怎么样",
                "如何",
                "怎么做",
                "怎么处理",
                "怎么解决",
                "是不是说",
                "想告诉他们",
                "想告诉大家",
                "有什么问题",
            ],
        )
}

fn end_of_subject(text: &str) -> bool {
    has(
        text,
        &[
            "换个话题",
            "另一个问题",
            "下一位",
            "下一个",
            "再问",
            "到此结束",
            "散会",
        ],
    )
}

impl<'a> Conversation<'a> {
    pub(super) fn new(rows: &'a [Value]) -> Self {
        let mut speaker = None;
        let turns = rows
            .iter()
            .map(|row| {
                let raw = row["text"].as_str().unwrap_or("");
                if let Some((label, _)) = split_turn_label(raw) {
                    speaker = Some(label);
                }
                Turn {
                    id: row["id"].as_str().unwrap_or(""),
                    speaker,
                    words: source_review::bare(raw),
                }
            })
            .collect();
        Self { turns }
    }

    pub(super) fn turns(&self) -> &[Turn<'a>] {
        &self.turns
    }

    fn continuation(&self, index: usize) -> Vec<usize> {
        let Some(speaker) = self.turns.get(index).and_then(|turn| turn.speaker) else {
            return Vec::new();
        };
        let mut last = self.turns[index].words;
        let mut sequence = Vec::new();
        for pos in index + 1..(index + 18).min(self.turns.len()) {
            let turn = &self.turns[pos];
            let words = phrase(turn.words);
            if end_of_subject(words) {
                break;
            }
            let length = words.chars().count();
            let echo = (2..=4).contains(&length) && last.contains(words) && !words.contains('不');
            if acknowledgement(words) || (turn.speaker != Some(speaker) && echo) {
                continue;
            }
            if turn.speaker != Some(speaker) || opening_question(words) {
                break;
            }
            last = words;
            sequence.push(pos);
        }
        sequence
    }

    pub(super) fn answer(
        &self,
        index: usize,
        shown: &str,
        visible: &HashSet<usize>,
        limit: usize,
    ) -> Option<Answer<'a>> {
        let lead = self.turns.get(index)?;
        let speaker = lead.speaker?;
        let original = phrase(lead.words);
        let curtailed = ["也", "需要", "另外", "因为", "还有", "所以"]
            .iter()
            .any(|suffix| original.ends_with(suffix));
        let recommendation = has(original, &["那就要", "那就得", "就应该"]);
        if phrase(source_review::bare(shown)) != original
            || opening_question(original)
            || !(curtailed || recommendation)
        {
            return None;
        }
        let question = self.turns[index.saturating_sub(6)..index]
            .iter()
            .rev()
            .find(|turn| !acknowledgement(turn.words))?;
        if question.speaker == Some(speaker)
            || question.speaker.is_none()
            || !opening_question(question.words)
        {
            return None;
        }
        let mut candidates = self
            .continuation(index)
            .into_iter()
            .filter(|pos| !visible.contains(pos))
            .filter_map(|pos| {
                let turn = &self.turns[pos];
                let words = phrase(turn.words);
                (words.chars().count() >= 8).then_some((turn.id, words))
            })
            .collect::<Vec<_>>();
        let mut available =
            limit.checked_sub(speaker.chars().count() + 2 + original.chars().count())?;
        // Prefer the later answer when a long prefatory fragment used up the
        // available range. Restore quotes in their original order.
        if candidates
            .iter()
            .map(|(_, text)| text.chars().count() + 1)
            .sum::<usize>()
            > available
        {
            candidates.reverse();
            candidates.retain(|(_, text)| {
                let size = text.chars().count() + 1;
                if size > available {
                    return false;
                }
                available -= size;
                true
            });
            candidates.reverse();
        }
        candidates.truncate(7);
        if candidates.is_empty() {
            return None;
        }
        let mut text = format!("{speaker}：{original}");
        for (_, part) in &candidates {
            text.push('；');
            text.push_str(part);
        }
        canonical_brief::line(&text, limit).then(|| Answer {
            text,
            sources: std::iter::once(lead.id)
                .chain(candidates.into_iter().map(|(id, _)| id))
                .collect(),
        })
    }

    pub(super) fn closing_followup(
        &self,
        index: usize,
        confirmed: &HashSet<usize>,
    ) -> Option<ExamplePassage<'a>> {
        let turn = self.turns.get(index)?;
        let words = phrase(turn.words);
        if opening_question(words)
            || has(
                words,
                &[
                    "假如",
                    "如果",
                    "要是",
                    "不办",
                    "不再",
                    "不用",
                    "没有",
                    "还没定",
                    "暂定",
                    "是否",
                    "建议",
                    "考虑",
                ],
            )
            || !has(words, &["咱们", "我们", "大家"])
            || !has(
                words,
                &[
                    "召集", "组织", "召开", "通知", "发布", "登记", "安排", "提交", "复核", "对接",
                ],
            )
        {
            return None;
        }
        let previous = self.turns.get(index.checked_sub(1)?)?;
        if !(previous.speaker == turn.speaker
            && has(previous.words, &["然后", "接着", "随后", "之后"])
            || has(words, &["然后", "接着", "随后", "之后"]))
        {
            return None;
        }
        let anchored = (index.saturating_sub(6)..index)
            .rev()
            .any(|prior| confirmed.contains(&prior) && self.continuation(prior).contains(&index));
        let closes = self.turns.iter().skip(index + 1).take(6).any(|after| {
            after.speaker == turn.speaker && has(after.words, &["到此结束", "会议结束", "散会"])
        });
        let text = format!("收尾时提出的后续安排：{words}");
        (anchored && closes && canonical_brief::line(&text, 100)).then_some(ExamplePassage {
            source: turn.id,
            text,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rows(lines: &[&str]) -> Vec<Value> {
        lines
            .iter()
            .enumerate()
            .map(|(index, line)| serde_json::json!({"id":format!("e{index:04}"),"text":line}))
            .collect()
    }

    #[test]
    fn a_visible_reply_can_include_its_next_related_source_sentences() {
        let spoken = [
            "说话人1：目前最大的难题是什么？",
            "说话人2：主要是供应这边也",
            "说话人1：嗯对。",
            "说话人2：供应商没有把货送到，客户订单现在无法交付。",
            "说话人1：下一个问题是仓库。",
            "说话人2：我们换了一批设备。",
        ];
        let turns = rows(&spoken);
        let dialog = Conversation::new(&turns);
        let answer = dialog
            .answer(1, spoken[1], &HashSet::from([1]), 90)
            .unwrap();
        assert_eq!(answer.sources, ["e0001", "e0003"]);
        assert!(answer.text.contains("客户订单现在无法交付"));
        assert!(!answer.text.contains("设备"));
        assert!(dialog
            .answer(1, spoken[1], &HashSet::from([1, 3]), 90)
            .is_none());
        assert!(dialog
            .answer(1, spoken[1], &HashSet::from([1]), 20)
            .is_none());
        let mut uncertain = spoken;
        uncertain[3] = "说话人2：这是不是说供货已经解决了";
        let turns = rows(&uncertain);
        let dialog = Conversation::new(&turns);
        assert!(dialog
            .answer(1, spoken[1], &HashSet::from([1]), 90)
            .is_none());

        let mut interrupted = spoken;
        interrupted[2] = "说话人1：不，这件事不是供应商造成的。";
        let turns = rows(&interrupted);
        let dialog = Conversation::new(&turns);
        assert!(dialog
            .answer(1, spoken[1], &HashSet::from([1]), 90)
            .is_none());
    }

    #[test]
    fn a_closing_followup_stays_linked_to_confirmed_work() {
        let spoken = [
            "说话人1：下去以后由物料组复核登记表。",
            "说话人2：好的。",
            "说话人1：然后给仓库同事。",
            "说话人1：咱们组织同事到现场做一次操作说明。",
            "说话人2：行。",
            "说话人1：今天就到此结束，散会。",
        ];
        let turns = rows(&spoken);
        let dialog = Conversation::new(&turns);
        let item = dialog.closing_followup(3, &HashSet::from([0])).unwrap();
        assert_eq!(item.source, "e0003");
        assert_eq!(
            item.text,
            "收尾时提出的后续安排：咱们组织同事到现场做一次操作说明"
        );
        assert!(dialog.closing_followup(3, &HashSet::new()).is_none());

        let mut interrupted = spoken;
        interrupted[1] = "说话人2：我不同意这个安排，先核对实施条件。";
        let turns = rows(&interrupted);
        let dialog = Conversation::new(&turns);
        assert!(dialog.closing_followup(3, &HashSet::from([0])).is_none());
    }
}
