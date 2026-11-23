//! Restore adjacent, confirmed assignments using the transcript's own roles.
use std::sync::LazyLock;

use regex::Regex;
use serde_json::Value;

use super::{closing_recap::RecapHandoff, reader_turns::{Conversation, Turn}};
use super::super::canonical_brief;
use crate::companion_v1::CompanionV1ActionItem;

#[derive(Clone, Copy)]
struct Role<'a> {
    speaker: &'a str,
    name: &'a str,
    introduction: usize,
}

fn contains(text: &str, cues: &[&str]) -> bool {
    cues.iter().any(|cue| text.contains(cue))
}

fn binding(text: &str) -> bool {
    !contains(text, &["？", "?", "建议", "我觉得", "比如", "例如", "假设", "如果", "考虑一下",
        "暂定", "不用", "取消", "不需要", "先不", "之前说过", "曾经", "已经", "有可能", "要不要"])
}

fn agreement(text: &str) -> bool {
    matches!(text.trim_matches(['。', '，', '！', ' ', '嗯', '啊', '呃']),
        "好" | "行" | "好的" | "行的" | "可以" | "收到" | "没问题")
}

fn roles<'a>(turns: &[Turn<'a>]) -> (Option<&'a str>, Vec<Role<'a>>) {
    static TEAM: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(r"^[\p{Han}]{2,8}(?:部门|部|团队|小组|组)$").unwrap()
    });
    const CHAIRS: &[&str] = &["总经理", "主持人", "主持", "项目经理", "负责人", "主任", "副院长", "院长",
        "副校长", "校长", "主管", "董事长"];
    let mut chairs = Vec::new();
    let mut owners = Vec::new();
    for (index, turn) in turns.iter().take(30).enumerate() {
        let Some(speaker) = turn.speaker else { continue };
        let Some((prefix, name)) = turn.words.split_once("我是") else { continue };
        if !prefix.chars().all(|ch| ch.is_ascii_digit() || "零一二三四五六七八九幺零,.，。啊嗯呃 ".contains(ch))
            && !matches!(prefix, "大家好，" | "大家好" | "各位好，")
        {
            continue;
        }
        let name = name.trim_matches(['。', '！', ' ', '，']);
        if CHAIRS.contains(&name) && !chairs.contains(&speaker) {
            chairs.push(speaker);
        } else if TEAM.is_match(name) {
            owners.push(Role { speaker, name, introduction: index });
        }
    }
    if chairs.len() != 1 {
        return (None, Vec::new());
    }
    let counts = owners.clone();
    owners.retain(|role| counts.iter().filter(|other| other.speaker == role.speaker || other.name == role.name).count() == 1);
    (chairs.first().copied(), owners)
}

fn addresses<'a>(words: &str, roles: &[Role<'a>]) -> Vec<(usize, usize, Role<'a>)> {
    let mut found = Vec::new();
    for role in roles {
        let short = ["部门", "小组", "团队", "部", "组"].iter()
            .find_map(|suffix| role.name.strip_suffix(suffix)).unwrap_or(role.name);
        for (start, actual) in words.match_indices(short) {
            let end = start + actual.len();
            let tail = &words[end..];
            let rest = tail.strip_prefix("部门").or_else(|| tail.strip_prefix('部')).unwrap_or(tail);
            if let Some(mark) = ["这边儿", "这边", "这块儿", "这块", "这一块儿", "这一块", "这方面"].iter()
                .find(|marker| rest.starts_with(**marker))
            {
                found.push((start, words.len() - rest.len() + mark.len(), *role));
            }
        }
    }
    found.sort_by_key(|entry| entry.0);
    if found.windows(2).any(|pair| pair[0].0 == pair[1].0) {
        return Vec::new();
    }
    found
}

fn paired_work(text: &str) -> Option<&str> {
    static ARTIFACT: LazyLock<Regex> = LazyLock::new(|| Regex::new(concat!(
        r"^[^，,。；！？\r\n]{0,39}?(?:进行|制作|做出|拿出|提交|整理|拟定|准备|制定|编制|做)",
        r"[^，,。；！？\r\n]{1,25}?(?:计划书|计划|方案|清单|说明|报告|预算|条例)"
    )).unwrap());
    let task = ARTIFACT.find(text.trim())?.as_str();
    canonical_brief::line(task, 86).then_some(task)
}

fn sibling_assignments(
    turns: &[Turn<'_>], roles: &[Role<'_>], chair: &str, directive: usize,
) -> Vec<RecapHandoff> {
    let turn = &turns[directive];
    let named = addresses(turn.words, roles);
    if named.len() < 2 || has_repeated_role(&named) || !binding(turn.words)
        || !contains(turn.words, &["你", "要", "请", "负责"])
    {
        return Vec::new();
    }
    let paired = (directive.saturating_sub(3)..directive).rev().find(|&index| {
        let earlier = &turns[index];
        earlier.speaker == Some(chair) && binding(earlier.words)
            && contains(earlier.words, &["两个", "两套", "各自", "分别"])
            && contains(earlier.words, &["方案", "计划", "分工"])
    });
    let following = &turns[directive + 1..(directive + 4).min(turns.len())];
    let acknowledged = following.iter().position(|reply| {
        named.iter().any(|(_, _, role)| reply.speaker == Some(role.speaker)) && agreement(reply.words)
    });
    let (Some(paired), Some(acknowledged)) = (paired, acknowledged) else { return Vec::new() };
    if following.iter().any(|row| contains(row.words, &["取消", "不用", "不做", "不要做"])) {
        return Vec::new();
    }
    let common = following.iter().enumerate().find_map(|(index, row)| {
        let words = row.words;
        (row.speaker == Some(chair) && binding(words) && words.contains("包括")
            && contains(words, &["成本", "预算", "费用"])
            && contains(words, &["计划", "估算", "测算", "核算"])
            && canonical_brief::line(words, 35)).then_some((directive + index + 1, words))
    });
    named.iter().enumerate().map(|(index, (_, end, role))| {
        let stop = named.get(index + 1).map_or(turn.words.len(), |next| next.0);
        let work = paired_work(&turn.words[*end..stop])?;
        let mut text = work.to_owned();
        let mut citations = vec![directive, role.introduction, paired, directive + 1 + acknowledged];
        if let Some((cost, words)) = common {
            let joined = format!("{text}，{}", words.trim_end_matches(['。', '！']));
            if canonical_brief::line(&joined, 100) {
                text = joined;
                citations.push(cost);
            }
        }
        Some(RecapHandoff {
            item: CompanionV1ActionItem { text, owner: Some(role.name.to_owned()), due: None },
            citations, directive,
        })
    }).collect::<Option<Vec<_>>>().unwrap_or_default()
}

fn has_repeated_role(roles: &[(usize, usize, Role<'_>)]) -> bool {
    roles.iter().enumerate().any(|(index, (_, _, owner))| {
        roles[..index].iter().any(|(_, _, earlier)| earlier.speaker == owner.speaker)
    })
}

fn noted_assignment(
    turns: &[Turn<'_>], roles: &[Role<'_>], chair: &str, directive: usize,
) -> Option<RecapHandoff> {
    let words = turns[directive].words;
    if !binding(words) || !contains(words, &["你下去以后", "你回去以后", "你会后", "请你会后"]) {
        return None;
    }
    let reply = turns.get(directive + 1)?;
    let owner = roles.iter().find(|role| reply.speaker == Some(role.speaker))?;
    if !agreement(reply.words) {
        return None;
    }
    let (pivot, named) = (directive.saturating_sub(10)..directive).rev().find_map(|index| {
        let turn = &turns[index];
        if turn.speaker != Some(chair) { return None; }
        let addressed = addresses(turn.words, roles);
        let [(_, _, role)] = addressed.as_slice() else { return None };
        Some((index, *role))
    })?;
    if owner.name != named.name || turns[pivot + 1..directive].iter().any(|line| {
        line.speaker.is_some_and(|speaker| speaker != chair && speaker != owner.speaker)
            || (line.speaker == Some(chair) && addresses(line.words, roles).len() > 1)
    }) {
        return None;
    }
    let context = (pivot + 1..directive).find(|&index| {
        let turn = &turns[index];
        turn.speaker == Some(owner.speaker) && turn.words.chars().count() >= 10
    })?;
    let (subject, request) = words.split_once('你')?;
    let (_, followup) = request.split_once(['，', ','])?;
    let object = subject.trim_start_matches(['嗯', '啊', '呃', ' '])
        .trim_start_matches("到时候儿").trim_start_matches("到时候");
    let action = paired_work(followup.trim_start().trim_start_matches('你'))?;
    if !contains(object, &["这一块", "这方面", "这个", "这件"]) || object.chars().count() > 20 {
        return None;
    }
    let text = format!("{}，{action}", object.trim_end_matches(['，', ' ']));
    canonical_brief::line(&text, 90).then(|| RecapHandoff {
        item: CompanionV1ActionItem { text, owner: Some(owner.name.to_owned()), due: None },
        citations: vec![directive, owner.introduction, pivot, context, directive + 1],
        directive,
    })
}

pub(super) fn from_transcript(sentences: &[Value]) -> Vec<RecapHandoff> {
    let conversation = Conversation::new(sentences);
    let turns = conversation.turns();
    let (Some(chair), roles) = roles(turns) else { return Vec::new() };
    if roles.is_empty() { return Vec::new(); }
    let mut actions = Vec::new();
    for (index, _) in turns.iter().enumerate().filter(|(_, turn)| turn.speaker == Some(chair)) {
        actions.extend(sibling_assignments(turns, &roles, chair, index));
        actions.extend(noted_assignment(turns, &roles, chair, index));
    }
    actions
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::backend::minutes::{automatic_brief::factual_audit::evidence_sentences, canonical_brief::source_units};

    fn source() -> String {
        [
            "说话人1: 我是总经理",
            "说话人2: 我是项目部",
            "说话人3: 我是运营部",
            "说话人1: 两个方案都分别做一下计划",
            "说话人1: 项目这边儿对实地参观项目做一个详细方案还有运营这块儿你也要对虚拟参观做一个计划",
            "说话人3: 可以",
            "说话人1: 包括成本测算计划",
            "说话人1: 再说运营这一块儿",
            "说话人3: 现在场馆运营需要拟订入场的详细条例",
            "说话人1: 这个条例这一块儿你下去以后，你做一个详细的计划",
            "说话人3: 行",
        ].join("\n") + "\n"
    }

    #[test]
    fn separate_owners_share_only_an_explicit_common_requirement() {
        let text = source();
        let rows = evidence_sentences(&source_units(&text));
        let got = from_transcript(&rows);
        assert_eq!(got.len(), 3);
        assert_eq!(got[0].directive, got[1].directive);
        assert!(got[0].item.text.contains("成本测算"));
        assert!(got[1].item.text.contains("成本测算"));
        assert!(got[2].item.text.contains("条例"));
        assert!(got.iter().all(|task| task.item.due.is_none()));

        let fuzzy = text.replace("说话人3: 行\n", "说话人2: 行\n");
        let got = from_transcript(&evidence_sentences(&source_units(&fuzzy)));
        assert_eq!(got.len(), 2);
    }

    #[test]
    #[ignore = "runs the SHA-bound ordinary Windows kickoff source through the same source splitter"]
    fn kickoff_keeps_both_roles_cost_and_the_confirmed_pronoun_assignment() {
        use sha2::{Digest, Sha256};
        let path = std::env::var_os("COMPANION_TEST_KICKOFF_SOURCE").unwrap();
        let sha = std::env::var("COMPANION_TEST_KICKOFF_SHA").unwrap();
        let input = std::fs::read_to_string(path).unwrap();
        assert_eq!(format!("{:x}", Sha256::digest(input.as_bytes())), sha);
        let rows = evidence_sentences(&source_units(&input));
        let all = from_transcript(&rows);
        for item in &all {
            println!("{:?}",item.item);
        }
        let project = all.iter().find(|item| item.item.owner.as_deref()==Some("项目部")
            && item.item.text.contains("计划书")).expect("original on-site plan");
        let virtual_plan = all.iter().find(|item| item.item.owner.as_deref()==Some("运营部")
            && item.item.text.contains("V R")).expect("original virtual plan");
        assert_eq!(project.directive, virtual_plan.directive);
        assert!(project.item.text.contains("成本") && virtual_plan.item.text.contains("成本"));
        assert!(all.iter().any(|item| item.item.owner.as_deref()==Some("运营部") && item.item.text.contains("条令")));
        assert!(all.iter().all(|item| item.item.due.is_none()));
        assert_eq!(all.len(),3, "the frozen source has only three newly resolved assignments");
    }
}
