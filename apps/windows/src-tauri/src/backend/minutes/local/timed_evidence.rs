//! Saved audio timing is additional evidence of transcript adjacency. It is
//! never a speaker identity or a replacement for the adopted transcript.
use std::{ops::Range, sync::LazyLock};

use regex::Regex;
use serde_json::{json, Value};

use crate::companion_v1::CompanionV1UtteranceSegment;

pub(super) struct Timing<'a> {
    utterances: &'a [CompanionV1UtteranceSegment],
    sentences_by_utterance: Vec<Range<usize>>,
    utterances_by_sentence: Vec<Range<usize>>,
}

impl<'a> Timing<'a> {
    pub(super) fn verified(
        source: &str, sentences: &[Value], utterances: &'a [CompanionV1UtteranceSegment],
    ) -> Option<Self> {
        if utterances.is_empty() || utterances.iter().any(|row| row.end_ms <= row.start_ms)
            || utterances.windows(2).any(|pair| pair[0].start_ms > pair[1].start_ms)
            || !source.chars().filter(|c| !c.is_whitespace()).eq(
                utterances.iter().flat_map(|row| row.text.chars().filter(|c| !c.is_whitespace())),
            )
        {
            return None;
        }
        let offsets = |values: Vec<usize>| {
            let mut cursor = 0;
            values.into_iter().map(|size| {
                let previous = cursor;
                cursor += size;
                previous..cursor
            }).collect::<Vec<_>>()
        };
        let words = |text: &str| text.chars().filter(|c| !c.is_whitespace()).count();
        let sentence_offsets = offsets(sentences.iter().map(|row| words(row["text"].as_str().unwrap())).collect());
        let utterance_offsets = offsets(utterances.iter().map(|row| words(&row.text)).collect());
        let overlaps = |range: &Range<usize>, other: &[Range<usize>]| {
            let first = other.partition_point(|candidate| candidate.end <= range.start);
            if range.is_empty() { return first..first; }
            first..other.partition_point(|candidate| candidate.start < range.end)
        };
        Some(Self {
            utterances,
            sentences_by_utterance: utterance_offsets.iter().map(|range| overlaps(range, &sentence_offsets)).collect(),
            utterances_by_sentence: sentence_offsets.iter().map(|range| overlaps(range, &utterance_offsets)).collect(),
        })
    }

    pub(super) fn receipt(&self) -> Value {
        json!({"textAlignment":"exact-except-whitespace","savedUtterances":self.utterances.len(),
            "usableTimedUtterances":self.utterances.iter().filter(|row| !row.approximate_timing).count(),
            "sentencesWithSavedUtterances":self.utterances_by_sentence.iter().filter(|range| !range.is_empty()).count(),
            "automaticSpeakerNamesUsed":false})
    }

    pub(super) fn covered_by_one_utterance(&self, indices: &[usize]) -> bool {
        indices.first().is_some_and(|&anchor| {
            self.utterances_by_sentence[anchor].clone().any(|index| {
                !self.utterances[index].approximate_timing
                    && indices.iter().all(|sentence| self.utterances_by_sentence[*sentence].contains(&index))
            })
        })
    }

    pub(super) fn neighboring_speech(&self, first: usize, second: usize) -> bool {
        let (earlier,later) = if first<second {(first,second)} else {(second,first)};
        let Some(end) = self.utterances_by_sentence[earlier].clone().last()
            .and_then(|i|self.utterances.get(i)) else { return false; };
        let start_range = &self.utterances_by_sentence[later];
        let Some(start) = self.utterances.get(start_range.start).filter(|_|!start_range.is_empty()) else {
            return false;
        };
        !end.approximate_timing && !start.approximate_timing
            && start.start_ms.saturating_sub(end.end_ms)<=2_500
    }

    fn neighborhood(&self, index: usize, before_ms: u64, after_ms: u64) -> Vec<usize> {
        let anchors = &self.utterances_by_sentence[index];
        let Some(first) = self.utterances.get(anchors.start) else { return Vec::new(); };
        let Some(last) = anchors.clone().last().and_then(|i| self.utterances.get(i)) else { return Vec::new(); };
        if first.approximate_timing || last.approximate_timing { return Vec::new(); }
        (anchors.start.saturating_sub(7)..(anchors.end + 2).min(self.utterances.len()))
            .filter(|&i| {
                let row = &self.utterances[i];
                !row.approximate_timing && row.end_ms >= first.start_ms.saturating_sub(before_ms)
                    && row.start_ms <= last.end_ms.saturating_add(after_ms)
            }).collect()
    }

    fn witness(
        &self, sentences: &[Value], positions: &[usize], anchor: usize, terms: &[&str],
    ) -> Option<usize> {
        positions.iter()
            .flat_map(|&position| self.sentences_by_utterance[position].clone())
            .filter(|&position| position <= anchor + 1)
            .find(|&position| terms.iter().all(|term| sentence(sentences, position).contains(term)))
    }
}

fn sentence(rows: &[Value], index: usize) -> &str {
    rows[index]["text"].as_str().unwrap()
}

fn has(text: &str, words: &[&str]) -> bool {
    words.iter().any(|word| text.contains(word))
}

pub(super) struct LinkedWork {
    pub(super) text: String,
    pub(super) references: Vec<usize>,
}

pub(super) fn action_context(
    timing: &Timing<'_>, sentences: &[Value], index: usize, action: &str, owner_missing: bool,
) -> Option<LinkedWork> {
    let nearby = timing.neighborhood(index, 25_000, 1_200);
    let owner_note = if owner_missing { " 负责人待核。" } else { "" };
    if has(action, &["出一个具体", "制定方案", "出方案", "写方案", "做方案"])
        && has(action, &["你这边", "你们", "你来", "审批", "上报", "报告上"])
        && !has(action, &["如果", "讨论是否", "已经审批", "不用"])
    {
        let scopes = ["元旦", "春节", "国庆", "中秋", "周年庆", "会员日", "开业", "年末", "店庆"];
        let hits = scopes.iter().filter_map(|scope| {
            timing.witness(sentences, &nearby, index, &[*scope, "活动"])
                .or_else(|| timing.witness(sentences, &nearby, index, &[*scope, "促销"]))
                .map(|reference| (*scope, reference))
        }).collect::<Vec<_>>();
        if let [(scope, reference)] = hits.as_slice() {
            let detail = if has(action, &["审批", "审核"]) && has(action, &["上报", "报告上", "报给上"]) {
                "，由会上发话者审批并上报"
            } else { "" };
            return Some(LinkedWork {
                text: format!("制定{scope}活动的具体实施方案{detail}。{owner_note}").trim().to_owned(),
                references: vec![*reference],
            });
        }
    }
    if !has(action, &["报给我", "发给我", "报上来"]) || !has(action, &["统计", "汇总"])
        || !action.contains("时间") || has(action, &["例如", "假设", "已经"])
    {
        return None;
    }
    static BATCH: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"分(?:为)?[一二两三四五六七八九十0-9]{1,2}批"
    ).expect("literal batching"));
    static DURATION: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"以(?:[一二两三四五六七八九十0-9]{1,3}天|半天)为主"
    ).expect("literal duration preference"));
    let training = timing.witness(sentences, &nearby, index, &["培训"])?;
    // The immediately preceding operational exchange must provide both
    // dimensions. Never copy a batch count or duration from another subject.
    let relevant = nearby.iter().flat_map(|&p| timing.sentences_by_utterance[p].clone())
        .filter(|&i| i>=training && i<=index).collect::<Vec<_>>();
    let (batch_id, batch) = relevant.iter().find_map(|&i| BATCH.find(sentence(sentences,i)).map(|m|(i,m.as_str())))?;
    let (duration_id,duration) = relevant.iter().find_map(|&i| DURATION.find(sentence(sentences,i)).map(|m|(i,m.as_str())))?;
    let reason = if has(sentence(sentences,duration_id), &["倒休", "轮休"]) { "考虑轮休，" } else { "" };
    Some(LinkedWork {
        text: format!("{reason}培训{batch}，{duration}。各自确定培训时间并报给发话者汇总。{owner_note}").trim().to_owned(),
        references: vec![training,batch_id,duration_id],
    })
}

pub(super) fn assigned_proposal(
    timing: &Timing<'_>, sentences: &[Value], index: usize,
) -> Option<(LinkedWork, LinkedWork)> {
    let current = sentence(sentences,index);
    if !has(current, &["再细化", "再具体一点", "完善一下"]) || current.contains(['？','?']) {
        return None;
    }
    let immediate = index.checked_sub(1);
    let lead = if has(current, &["到时候", "会后", "刚才那个"]) { index } else {
        immediate.filter(|i| has(sentence(sentences,*i), &["到时候把", "会后把", "把你刚才"]))?
    };
    let positions = timing.neighborhood(index, 90_000, 1_500);
    if positions.is_empty() || !sentences.get(index+1).and_then(|row|row["text"].as_str())
        .is_some_and(|reply| ["行","好","好的","收到"].contains(&reply.trim_matches(['。','！',' ','\r','\n']))) {
        return None;
    }
    let event = ["授课", "讲座", "培训", "分享会", "宣讲"].into_iter().find_map(|event| {
        let offer = timing.witness(sentences,&positions,index,&[event,"如果"])
            .or_else(||timing.witness(sentences,&positions,index,&[event,"决定"]));
        offer.filter(|&i| i<lead && has(sentence(sentences,i), &["如果", "要是", "决定下来", "确定要"]))
            .map(|reference|(event,reference))
    })?;
    let free = timing.witness(sentences,&positions,index,&["免费","讲"]).filter(|&i| i<event.1)?;
    let offer = sentence(sentences,event.1);
    if !has(offer, &["海报", "宣传", "推广"]) { return None; }
    let subject = if has(sentence(sentences,free), &["健身", "运动"]) { "健身" } else { "" };
    let followup = LinkedWork {text:format!("细化免费{subject}{}方案。负责人待核。",event.0),
        references:vec![lead,event.1,free]};
    let proposal = LinkedWork { text:format!("提议免费{subject}{}，确认开展后再制作海报并宣传。",event.0),
        references:vec![free,event.1]};
    Some((followup,proposal))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::backend::minutes::{canonical_brief::source_units, automatic_brief::factual_audit::evidence_sentences};

    fn row(text:&str,start_ms:u64,end_ms:u64)->CompanionV1UtteranceSegment {
        CompanionV1UtteranceSegment { text:text.to_owned(),start_ms,end_ms,speaker:None,approximate_timing:false }
    }

    #[test]
    fn verifies_the_effective_transcript_without_reassigning_an_old_revision() {
        let rows=[row("上 周 复盘。",0,1500), row("检查来访登记。",1800,2900)];
        let source="上周复盘。\n检查来访登记。";
        let sentences=evidence_sentences(&source_units(source));
        let evidence=Timing::verified(source,&sentences,&rows).unwrap();
        assert!(evidence.covered_by_one_utterance(&[0]));
        assert!(!evidence.covered_by_one_utterance(&[0,1]));
        let edited="上周复盘。\n检查送货登记。";
        assert!(Timing::verified(edited,&evidence_sentences(&source_units(edited)),&rows).is_none());
        assert_eq!(evidence.receipt()["automaticSpeakerNamesUsed"], false);
    }

    #[test]
    fn joins_an_explicit_action_to_a_nearby_activity_and_never_guesses_the_owner() {
        let first="元旦还要搞一次活动。";
        let original="你这边儿出一个具体的方案，我来审批并上报。";
        let source=format!("{first}{original}");
        let sentences=evidence_sentences(&source_units(&source));
        let fresh=[row(first,0,5000),row(original,5200,9000)];
        let timing=Timing::verified(&source,&sentences,&fresh).unwrap();
        let action=action_context(&timing,&sentences,1,original,true).unwrap();
        assert!(action.text.contains("元旦活动") && action.text.contains("负责人待核"));
        assert_eq!(action.references,[0]);
        let distant=[row(first,0,5000),row(original,60200,69000)];
        let late=Timing::verified(&source,&sentences,&distant).unwrap();
        assert!(action_context(&late,&sentences,1,original,true).is_none());
    }
}
