//! Build a compact follow-up from literal turns, with participant scope and status kept separate.
use std::{collections::HashMap, sync::LazyLock};

use regex::Regex;
use serde_json::Value;

use super::super::source_resolution::{self_introduced_identity, split_turn_label};
use super::source_commitments;

#[derive(Clone, Copy)]
pub(super) struct Participant<'a> {
    pub(super) label: &'a str,
    pub(super) introduction: usize,
}

pub(super) struct ReviewItem {
    pub(super) text: String,
    pub(super) subject: String,
    pub(super) sources: Vec<usize>,
}

pub(super) struct Agenda<'a> {
    rows: &'a [Value],
    participants: HashMap<&'a str, Option<Participant<'a>>>,
}

fn turn(row: &Value) -> (Option<&str>, &str) {
    let original = row["text"].as_str().unwrap_or_default();
    split_turn_label(original).map_or((None, original), |(label, words)| (Some(label), words.trim()))
}

fn starts_with_acknowledgment(words: &str) -> bool {
    let bare = words.trim_matches([' ', '。', '！', '，', ',', '嗯', '呃', '哦']);
    matches!(bare, "对" | "好" | "行" | "对的" | "可以" | "明白")
        || ["对，", "对的，", "好，", "这个挺好", "挺好的", "可以，"].iter().any(|cue| bare.starts_with(cue))
}

fn explicitly_unsettled(words: &str) -> bool {
    ["取消", "没决定", "先不", "暂不", "不能", "否决", "不同意", "已经完成", "已经通知"]
        .iter().any(|cue| words.contains(cue))
}

fn compact_event_name(words: &str) -> String {
    static FILLERS: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"一个|这个|那个|呃|嗯").unwrap());
    FILLERS.replace_all(words, "").trim().to_owned()
}

impl<'a> Agenda<'a> {
    pub(super) fn new(rows: &'a [Value]) -> Self {
        let mut participants = HashMap::<_, Option<Participant<'a>>>::new();
        let roll_call_with_fillers = rows.iter().take(12).enumerate().filter_map(|(index,row)| {
            let (speaker, words) = turn(row);
            let body = words.trim_start_matches(|ch:char| ch.is_ascii_digit() || "零〇一二三四五六七八九十幺 、，,啊呃嗯哦".contains(ch));
            if body == words { return None; }
            Some((index,speaker?,self_introduced_identity(body)?))
        }).collect::<Vec<_>>();
        let original = source_commitments::meeting_roles(rows).into_iter().filter(|(index,_,_)|
            !roll_call_with_fillers.iter().any(|(corrected,_,_)| corrected==index));
        for (introduction, speaker, label) in original.chain(roll_call_with_fillers.iter().copied()) {
            let next = Participant {label, introduction};
            participants.entry(speaker).and_modify(|current| {
                if let Some(old) = current {
                    if label.starts_with(old.label) && label.len() > old.label.len() {
                        *old = next;
                    } else if !old.label.starts_with(label) {
                        *current = None;
                    }
                }
            }).or_insert(Some(next));
        }
        Self { rows, participants }
    }

    pub(super) fn participant(&self, index: usize) -> Option<Participant<'a>> {
        let (speaker, _) = turn(&self.rows[index]);
        self.participants.get(speaker?).copied().flatten().filter(|entry| entry.introduction < index)
    }

    fn acknowledged_by(&self, index: usize) -> Option<(usize, Participant<'a>)> {
        let (origin, _) = turn(&self.rows[index]);
        for reply in index + 1..(index + 4).min(self.rows.len()) {
            let (speaker, words) = turn(&self.rows[reply]);
            if words.trim_matches([' ', '。', '，', ',', '嗯', '呃', '哦']).is_empty() { continue; }
            if origin==speaker || explicitly_unsettled(words) || !starts_with_acknowledgment(words) { return None; }
            return Some((reply, self.participant(reply)?));
        }
        None
    }

    fn is_answer_to_plan_question(&self, index: usize) -> bool {
        let (speaker, _) = turn(&self.rows[index]);
        (index.saturating_sub(3)..index).rev().find_map(|previous| {
            let (other, words) = turn(&self.rows[previous]);
            if words.trim_matches([' ', '。', '，', ',', '嗯', '呃', '哦']).is_empty() {
                return None;
            }
            Some(other!=speaker && ["什么计划", "什么安排", "怎么安排", "怎么开展", "有什么打算"]
                .iter().any(|cue| words.contains(cue)))
        }).unwrap_or(false)
    }

    pub(super) fn review_items(&self) -> Vec<ReviewItem> {
        static NOTICE: LazyLock<Regex> = LazyLock::new(|| Regex::new(concat!(
            r"(?:需要|要|务必|记得|应当)(?:先|提前|及时)?(?:跟|和|向|与)(?P<audience>家长|客户|员工|成员|供应商|参与者|参会人员|同事|学生|用户)",
            r"[^。！？\r\n]{0,26}?(?:说明|沟通|说一下|通知|确认)[^。！？\r\n]{0,38}?",
            r"(?P<event>考试|会议|培训|验收|交接|面试|演示|评审|比赛|演练|上课|发布|面谈|发货|到场)时间"
        )).unwrap());
        static PROPOSAL: LazyLock<Regex> = LazyLock::new(|| Regex::new(concat!(
            r"(?:是否可以|能不能|要不要|是否需要)[^。！？\r\n]{0,24}?(?:开展|举行|举办|召开|组织|增加|安排|开)",
            r"(?P<event>[\p{Han}A-Za-z0-9]{2,20}?(?:沟通会|说明会|家长会|座谈会|研讨会|演练|彩排|面试|走访|培训|评审|测试|复盘|演示|检查))"
        )).unwrap());
        static RECURRING: LazyLock<Regex> = LazyLock::new(|| Regex::new(concat!(
            r"(?:我想|我们想|我打算|我们打算|我们的计划是)[^。！？\r\n]{0,24}?",
            r"每(?P<period>一?周|一?月|一?天)(?:儿)?\s*(?:有|做|进行|开展|组织|安排)(?:一次|一项|一个|一轮|一遍)?",
            r"(?P<event>[\p{Han}A-Za-z0-9]{0,12}?(?:测验|测试|演练|巡查|核对|培训|交流|复盘|检查|评审|走访))"
        )).unwrap());
        let mut output = Vec::new();
        for (index, row) in self.rows.iter().enumerate() {
            let (_, words) = turn(row);
            if explicitly_unsettled(words)
                || ["举例", "比如", "例如", "假设", "如果", "听说", "转述", "往年", "以前", "通常"].iter().any(|cue|words.contains(cue)) {
                continue;
            }
            if let (Some((reply, participant)), Some(notice)) = (self.acknowledged_by(index), NOTICE.captures(words)) {
                let audience = &notice["audience"];
                let subject = format!("{}时间", &notice["event"]);
                output.push(ReviewItem {
                    text: format!("{}｜向{audience}说明{subject}，通知安排待确认。", participant.label),
                    subject, sources: vec![index,reply,participant.introduction],
                });
                continue;
            }
            if let (Some((reply, participant)), Some(proposal)) = (self.acknowledged_by(index), PROPOSAL.captures(words)) {
                let subject = compact_event_name(&proposal["event"]);
                if subject.chars().count()>=3 {
                    output.push(ReviewItem {
                        text: format!("{}｜{}的安排待确认。", participant.label, subject),
                        subject, sources: vec![index,reply,participant.introduction],
                    });
                }
                continue;
            }
            if let (Some(participant), Some(plan)) = (self.participant(index), RECURRING.captures(words)) {
                if !self.is_answer_to_plan_question(index) { continue; }
                let period = plan["period"].trim_start_matches('一');
                let name = compact_event_name(&plan["event"]).replace("的", "");
                let subject = format!("每{period}{name}");
                output.push(ReviewItem {
                    text: format!("{}｜{}的日程待确认。", participant.label, subject),
                    subject, sources: vec![index,participant.introduction],
                });
            }
        }
        output.retain(|item| !self.rows[item.sources[0]+1..].iter().any(|row| {
            let (_, words) = turn(row);
            words.contains(&item.subject)
                && ["取消", "已经通知", "已经定下", "已经确定", "就这么定", "先不办"].iter().any(|cue| words.contains(cue))
        }));
        output
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn an_acknowledged_notice_can_keep_scope_without_assigning_the_speaker() {
        let rows = [
            "说话人2: 零零四啊我是交付组。",
            "说话人1: 咱们要向客户沟通一下，说明现场验收时间。",
            "说话人2: 对。",
            "说话人1: 如果需要向客户沟通一下验收时间就另说。",
            "说话人2: 行。",
        ].into_iter().map(|text|json!({"text":text})).collect::<Vec<_>>();
        let agenda = Agenda::new(&rows);
        let reviews = agenda.review_items();
        assert_eq!(reviews.len(),1);
        assert_eq!(reviews[0].text,"交付组｜向客户说明验收时间，通知安排待确认。");
        assert_eq!(reviews[0].sources,[1,2,0]);
        let mut resolved=rows;
        resolved.push(json!({"text":"说话人2: 客户已经通知过了，验收时间是下午。"}));
        assert!(Agenda::new(&resolved).review_items().is_empty());
    }
}
