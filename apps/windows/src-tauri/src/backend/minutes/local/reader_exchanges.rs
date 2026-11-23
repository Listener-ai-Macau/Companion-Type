//! Offer complete original replies as choices before assigning reading space.
use std::collections::{BTreeMap, HashSet};
use std::ops::Range;

use serde_json::{json, Value};

use super::{atomic_document::{array, object}, reader_turns::{Conversation, Turn}};
use super::super::canonical_brief;

pub(super) const STAGE_PREFIX: &str = "chapter-review-reply-group-";
const PROMPT: &str = "为读者选出有用的讨论要点，只选编号。每个编号对应同一人回答中的一组已核实原话。\
    保留重要的具体做法、经过及原因、结果或限制。优先让不同议题都有实质内容，排除背景、闲聊和重复。\
    组内问句只作为回答的场景。不要补写，不要把设想或个人经验变成会议决定。";
const MAX_WINDOW: usize = 74;

pub(super) struct SelectedReply {
    pub(super) text: String,
    pub(super) sources: Vec<String>,
}

struct Card {
    text: String,
    sources: Vec<String>,
    answers: Vec<String>,
}

fn contains(text: &str, cues: &[&str]) -> bool {
    cues.iter().any(|cue| text.contains(cue))
}

fn trimmed(text: &str) -> &str {
    text.trim().trim_start_matches(['啊', '嗯', '哦', '呃', '唉', '，', ',', ' '])
}

fn substance(text: &str) -> usize {
    trimmed(text).chars().filter(|ch| ch.is_alphanumeric()).count()
}

fn question(text: &str) -> bool {
    let text = text.trim_end_matches(['。', '！', ' ']);
    text.ends_with(['？', '?', '吗']) || contains(text, &[
        "是什么", "什么样", "什么看法", "有什么", "为什么", "想告诉", "哪方面", "有哪些",
        "怎么样", "怎么做", "怎么调整", "怎么解决", "怎么办", "怎样", "如何", "多久",
        "哪个", "哪些", "哪一项", "哪位", "哪种", "多长时间",
    ])
}

fn handoff_ranges<'a>(turns: &[Turn<'a>]) -> Option<(&'a str, Vec<Range<usize>>)> {
    let mut questioners = BTreeMap::new();
    for turn in turns {
        if let Some(speaker) = turn.speaker.filter(|_| question(turn.words) && substance(turn.words) >= 6) {
            *questioners.entry(speaker).or_insert(0_usize) += 1;
        }
    }
    let mut ranked = questioners.into_iter().collect::<Vec<_>>();
    ranked.sort_by_key(|(_, count)| std::cmp::Reverse(*count));
    let &(host, count) = ranked.first()?;
    if count < 3 || ranked.get(1).is_some_and(|(_, other)| *other >= count) {
        return None;
    }
    let dominant = |rows: &[Turn<'a>]| {
        let mut authors = BTreeMap::new();
        for turn in rows {
            if let Some(speaker) = turn.speaker.filter(|&speaker| speaker != host) {
                if !turn.words.trim().ends_with(['？', '?', '吗']) {
                    *authors.entry(speaker).or_insert(0_usize) += substance(turn.words).min(30);
                }
            }
        }
        let total: usize = authors.values().sum();
        authors.into_iter().find_map(|(speaker, score)| (score >= 76 && score * 5 >= total * 4).then_some(speaker))
    };
    let mut cuts = Vec::new();
    for index in 12..turns.len().saturating_sub(12) {
        let turn = &turns[index];
        if turn.speaker != Some(host)
            || (!question(turn.words) && !contains(turn.words, &["讲到", "说到", "下面请", "接下来", "换一位"]))
        {
            continue;
        }
        let before = dominant(&turns[index.saturating_sub(18)..index]);
        let after = dominant(&turns[index + 1..(index + 19).min(turns.len())]);
        if let (Some(before), Some(after)) = (before, after) {
            if before != after && (cuts.last().is_none_or(|prior| index - prior > 10))
                && !turns[index + 1..index + 5].iter().any(|row| row.speaker == Some(before) && substance(row.words) >= 8)
            {
                cuts.push(index);
            }
        }
    }
    let ranges = cuts.iter().enumerate().map(|(i, &start)| {
        let end = cuts.get(i + 1).copied().unwrap_or(turns.len()).min(start + MAX_WINDOW);
        start..end
    }).collect();
    Some((host, ranges))
}

fn marks(words: &str) -> u16 {
    const SIGNALS: &[&[&str]] = &[
        &["之前", "以前", "前期", "最初", "起初", "当时"],
        &["之后", "以后", "随后", "后来", "最后", "上映"],
        &["如果", "除非", "只有", "未定", "暂定", "可能"],
        &["因为", "由于", "所以", "导致", "造成"],
        &["没有", "不清楚", "不知道", "还没", "没法", "不能", "不太"],
        &["通过", "先做", "选择", "一边", "自己学", "具体分析"],
        &["调整", "改善", "降低", "增加", "改进", "解决", "改变"],
    ];
    SIGNALS.iter().enumerate().filter(|(_, cues)| contains(words, cues)).fold(0, |bits, (index, _)| bits | (1 << index))
}

struct Piece<'a> {
    at: usize,
    piece: &'a str,
    question: Option<&'a Turn<'a>>,
    tags: u16,
}

impl Piece<'_> {
    fn render(&self) -> String {
        if let Some(prior) = self.question {
            format!("问{}，答{}", trimmed(prior.words), self.piece)
        } else {
            self.piece.to_owned()
        }
    }
}

fn cards_for_exchange(rows: &[Turn<'_>], host: &str) -> Vec<Card> {
    let mut by_speaker: BTreeMap<&str, Vec<Piece<'_>>> = BTreeMap::new();
    let mut last_question = None;
    for (at, row) in rows.iter().enumerate() {
        let Some(speaker) = row.speaker else { continue };
        let mut text = trimmed(row.words);
        if speaker == host {
            last_question = (question(text) || contains(text, &["哪个", "哪一项", "哪位"]))
                .then_some((at, row)).or(last_question);
            continue;
        }
        if text.ends_with(['？', '?', '吗']) { continue; }
        if let Some(prefix) = text.strip_suffix("然后").filter(|prefix| {
            prefix.chars().count() > 18 && ["吧", "嘛", "的", "了", "兴趣", "为主"].iter().any(|end| prefix.ends_with(end))
        }) {
            text = prefix.trim_end_matches(['，', ',', ' ']);
        }
        let length = substance(text);
        let short_reply = if (3..13).contains(&length) {
            last_question.filter(|(prior, query)| *prior + 1 == at && query.words.chars().count() <= 32).map(|(_, query)| query)
        } else {
            None
        };
        if length < 13 && short_reply.is_none() { continue; }
        let ending = text.trim_end_matches(['。', '，', ',', '；', ' ']);
        if ["因为", "所以", "的话", "还有", "然后", "不是", "就是", "和", "以及", "或者说", "一个",
            "是个", "但是", "不知道", "不清楚", "没有", "不能", "先跟", "还要", "要去", "然后又"]
            .iter().any(|suffix| ending.ends_with(suffix))
        {
            continue;
        }
        by_speaker.entry(speaker).or_default().push(Piece {at, piece: text, question: short_reply, tags: marks(text)});
    }
    let mut cards = Vec::new();
    for (speaker, pieces) in by_speaker {
        let Some(first) = pieces.iter().position(|piece| {
            (piece.piece.chars().count() >= 24 || piece.tags != 0)
                && piece.render().chars().count() + speaker.chars().count() < 120
        }) else { continue };
        let mut selected = vec![first];
        let mut flags = pieces[first].tags;
        let mut available = 119 - speaker.chars().count() - pieces[first].render().chars().count();
        for _ in 0..2 {
            let next = pieces.iter().enumerate().filter(|(index, piece)| {
                let adds_meaning = (piece.tags & !flags) != 0 || piece.question.is_some()
                    || (selected.len() == 1 && piece.tags != 0
                        && !super::source_grounding::shared_han_phrase(pieces[first].piece, piece.piece, 6));
                !selected.contains(index) && piece.render().chars().count() + 1 <= available && adds_meaning
            }).max_by_key(|(index, piece)| {
                    (5 * (piece.tags & !flags).count_ones() + 8 * u32::from(piece.question.is_some()),
                     std::cmp::Reverse(*index))
                });
            let Some((index, piece)) = next else { break };
            selected.push(index);
            flags |= piece.tags;
            available -= piece.render().chars().count() + 1;
        }
        selected.sort_unstable();
        let mut sources = Vec::new();
        let mut answers = Vec::new();
        let mut lines = Vec::new();
        for index in selected {
            let piece = &pieces[index];
            if let Some(query) = piece.question {
                sources.push(query.id.to_owned());
            }
            let answer = rows[piece.at].id.to_owned();
            sources.push(answer.clone());
            answers.push(answer);
            lines.push(piece.render());
        }
        let text = format!("{speaker}：{}", lines.join("；"));
        if canonical_brief::line(&text, 120) && !sources.is_empty() {
            cards.push(Card { text, sources, answers });
        }
    }
    cards
}

fn related_question(left: &str, right: &str) -> bool {
    let without_filler = |text: &str| {
        let mut text = text.trim().to_owned();
        for word in ["你这个", "这个", "那个", "刚才", "咱们", "我想", "您这", "您原来",
            "哪方面", "哪些", "哪个", "怎么", "如何"]
        {
            text = text.replace(word, "");
        }
        text
    };
    super::source_grounding::shared_han_phrase(&without_filler(left), &without_filler(right), 4)
}

fn make_choices(turns: &[Turn<'_>], host: &str) -> Vec<Card> {
    let mut groups = Vec::new();
    let mut start = 0;
    let mut reply_count = 0;
    let mut prior_question = None;
    for (at, row) in turns.iter().enumerate() {
        if row.speaker == Some(host) && question(row.words) {
            let same = reply_count <= 4 && prior_question.is_some_and(|prior| related_question(prior, row.words));
            if reply_count > 0 && !same {
                groups.push(start..at);
                start = at;
                reply_count = 0;
            }
            prior_question = Some(row.words);
        }
        if row.speaker != Some(host) && substance(row.words) >= 4 {
            reply_count += 1;
        }
    }
    groups.push(start..turns.len());
    groups.into_iter().flat_map(|range| cards_for_exchange(&turns[range], host)).take(12).collect()
}

pub(super) fn select(
    rows: &[Value], already_selected: &HashSet<&str>, protected_actions: &HashSet<&str>,
    mut ask: impl FnMut(&'static str, Value, Value, &str) -> Result<String, String>,
) -> Result<Vec<SelectedReply>, String> {
    let conversation = Conversation::new(rows);
    let turns = conversation.turns();
    let Some((host, ranges)) = handoff_ranges(turns) else { return Ok(Vec::new()); };
    let mut results = Vec::new();
    for (number, range) in ranges.into_iter().take(3).enumerate() {
        let source = &turns[range];
        let enough = source.iter().take(20).filter(|row| row.speaker != Some(host)
            && already_selected.contains(row.id)).count() >= 3;
        if enough { continue; }
        let choices: Vec<_> = make_choices(source, host).into_iter().filter(|card| {
            card.answers.iter().all(|source| !protected_actions.contains(source.as_str()))
                && card.answers.iter().any(|source| !already_selected.contains(source.as_str()))
        }).collect();
        if choices.len() < 3 { continue; }
        let offered = (1..=choices.len()).map(|n| format!("q{n:02}")).collect::<Vec<_>>();
        let data = offered.iter().zip(&choices).map(|(key, card)| json!([key, card.text])).collect::<Vec<_>>();
        let schema = object(json!({"selected":array(json!({"type":"string","enum":offered}), 2, choices.len().min(4))}));
        let output = ask(PROMPT, json!({"要点":data}), schema, &format!("{STAGE_PREFIX}{}", number + 1))?;
        let output = crate::backend::minutes::strip_code_fences(&output);
        let Ok(doc) = serde_json::from_str::<Value>(output.trim()) else { continue };
        let Some(ids) = doc["selected"].as_array() else { continue };
        let matching = ids.iter().map(|id| offered.iter().position(|key| id.as_str() == Some(key)))
            .collect::<Option<Vec<_>>>();
        let Some(mut matching) = matching else { continue };
        if !(2..=choices.len().min(4)).contains(&matching.len()) { continue; }
        matching.truncate(3);
        matching.sort_unstable();
        matching.dedup();
        if matching.len() < 2 { continue; }
        for index in matching {
            let card = &choices[index];
            results.push(SelectedReply { text: card.text.clone(), sources:card.sources.clone() });
        }
    }
    Ok(results)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::backend::minutes::{automatic_brief::factual_audit::evidence_sentences, canonical_brief::source_units};

    #[test]
    #[ignore = "uses the SHA-bound full industry interview and the actual request schema"]
    fn full_source_offers_compact_linked_replies_before_the_model_selects_them() {
        use sha2::{Digest, Sha256};
        let path=std::env::var_os("COMPANION_TEST_EXCHANGE_SOURCE").unwrap();
        let digest=std::env::var("COMPANION_TEST_EXCHANGE_SHA").unwrap();
        let source=std::fs::read_to_string(path).unwrap();
        assert_eq!(format!("{:x}", Sha256::digest(source.as_bytes())), digest);
        let mut requested = Vec::new();
        let choices=select(&evidence_sentences(&source_units(&source)), &HashSet::new(), &HashSet::new(),
            |prompt, input, schema, stage| {
                println!("{stage} {input}");
                requested.push(json!({"prompt":prompt,"input":input,"schema":schema,"stage":stage}));
                let rows = input["要点"].as_array().unwrap();
                let first = rows.iter().find(|row| row[1].as_str().is_some_and(|line|
                    line.contains("大四") && line.contains("毕业以后") && line.contains("土木工程")));
                let startup = rows.iter().find(|row| row[1].as_str().is_some_and(|line|
                    line.contains("没有盈利") && line.contains("流程是什么")));
                if let (Some(first), Some(startup)) = (first, startup) {
                    return Ok(json!({"selected":[first[0],startup[0]]}).to_string());
                }
                Ok("{}".into())
            }).unwrap();
        if let Some(path)=std::env::var_os("COMPANION_TEST_EXCHANGE_REQUESTS") {
            std::fs::write(path,serde_json::to_vec_pretty(&requested).unwrap()).unwrap();
        }
        assert!(choices.iter().any(|reply| reply.text.contains("土木工程") && reply.text.contains("大四")));
        assert!(choices.iter().any(|reply| reply.text.contains("没有盈利") && reply.text.contains("流程是什么")));
        assert!(choices.iter().all(|reply| reply.text.chars().count() <= 120 && !reply.sources.is_empty()));
    }
}
