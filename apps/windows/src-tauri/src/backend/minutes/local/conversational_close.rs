//! A group can close an operational discussion without announcing a recap.
use std::collections::{HashMap, HashSet};

use serde_json::Value;

use super::super::source_resolution::split_turn_label;

pub(super) struct ConfirmedPlan {
    pub(super) index: usize,
    pub(super) support: Vec<usize>,
    pub(super) timing: Vec<usize>,
    pub(super) earlier_alternatives: Vec<usize>,
}

// These distinguish concrete steps. They do not identify an owner or convert
// dates mentioned during the discussion into confirmed deadlines.
const STEPS: &[&[&str]] = &[
    &["打扫", "清洁", "清理现场", "清理场地", "清扫", "消毒", "整理场地"],
    &["采购", "购买", "买东西", "集中购买", "买完", "下单", "领用"],
    &["布置", "安装", "摆放", "摆好", "装配"],
    &["报名", "登记", "填写", "登记报名"],
    &["核对", "复核", "验收", "检查", "确认结果"],
    &["通知", "汇报", "提交", "发布", "发给"],
];

fn has(text: &str, cues: &[&str]) -> bool {
    cues.iter().any(|cue| text.contains(cue))
}

fn mentioned_steps(text: &str) -> Vec<usize> {
    let mut steps = STEPS.iter().enumerate().filter_map(|(index, cues)| {
        cues.iter().filter_map(|cue| text.find(cue)).min().map(|offset| (offset,index))
    }).collect::<Vec<_>>();
    steps.sort_unstable();
    steps.into_iter().map(|(_,index)|index).collect()
}

fn labeled(row: &Value) -> Option<(&str,&str)> {
    split_turn_label(row["text"].as_str()?.trim())
}

fn affirmative(text: &str) -> bool {
    let text = text.trim_matches(|ch: char| {
        ch.is_whitespace() || matches!(ch,'。'|'，'|'、'|'!'|'！'|'嗯'|'呃'|'啊'|'哦')
    });
    ["是", "好", "好的", "对", "行", "可以", "没问题", "我觉得挺好的", "这样行", "好的可以", "同意"]
        .contains(&text)
}

fn weekday(text: &str) -> Option<usize> {
    ["周一", "周二", "周三", "周四", "周五", "周六", "周日", "周天"].into_iter()
        .enumerate().filter(|(_,day)| text.contains(day))
        .map(|(index,_)| index.min(6))
        .try_fold(None, |seen, index| {
            if seen.is_none_or(|prior| prior==index) { Ok(Some(index)) } else { Err(()) }
        }).ok().flatten()
}

pub(super) fn confirmed_plan(rows: &[Value]) -> Option<ConfirmedPlan> {
    let first=rows.len()*3/4;
    for index in (first..rows.len()).rev() {
        let Some((lead, proposal)) = labeled(&rows[index]) else { continue };
        if !proposal.contains('先') || !proposal.contains('再')
            || !has(proposal, &["就先这样", "大家觉得怎么样", "你们觉得怎么样", "按这个顺序", "咱们这样安排"])
            || has(proposal, &["假设", "如果", "上次", "上周", "举例", "听说", "尚未决定", "还没决定"])
        {
            continue;
        }
        let operations = mentioned_steps(proposal);
        if operations.len() < 2 { continue; }
        let mut speakers = HashSet::new();
        let mut replies = Vec::new();
        let mut confirmation = None;
        for position in index+1..(index+9).min(rows.len()) {
            let Some((speaker,reply)) = labeled(&rows[position]) else { continue };
            if speaker==lead {
                if speakers.len()>=2 && has(reply, &["行动起来", "就这么办", "按这个执行", "按这个来做", "就这样做", "照这样做"])
                    && !has(reply, &["暂不", "先别", "还要确认", "不能"])
                {
                    confirmation=Some(position);
                }
                break;
            }
            if has(reply, &["我不同意", "我反对", "不行", "不能", "需要再讨论", "还没定"]) {
                break;
            }
            if affirmative(reply) && speakers.insert(speaker) { replies.push(position); }
        }
        let Some(confirmation) = confirmation else { continue };
        let mut timing = Vec::new();
        let mut earlier_alternatives = Vec::new();
        let mut received = HashSet::new();
        for position in (index.saturating_sub(54)..index).rev() {
            let Some((speaker,text)) = labeled(&rows[position]) else { continue };
            if speaker!=lead && !speakers.contains(speaker) { continue; }
            let steps = mentioned_steps(text);
            let dates = ["今明", "周一", "周二", "周三", "周四", "周五", "周六", "周日", "周天",
                "下周", "明天", "后天", "下班后", "下班之后", "晚上", "月底"];
            let split_first_step = speaker==lead && steps.len()==1 && steps.first()==operations.first()
                && dates.iter().filter(|cue|text.contains(**cue)).count()>=2;
            if (!split_first_step && steps.len() < 2) || !steps.iter().all(|step| operations.contains(step)) { continue; }
            let ordered = operations.iter().filter(|step| steps.contains(step)).eq(steps.iter());
            if !ordered && text.contains('先') && text.contains('再')
                && has(text, &["我感觉", "我觉得", "要不然", "我建议"])
            {
                earlier_alternatives.push(position);
            }
            if ordered && !has(text, &["如果", "只是假设", "比如说", "要不要"])
                && has(text, &dates)
                && received.insert(*steps.last().unwrap())
            {
                timing.push(position);
            }
        }
        let latest_weekdays = timing.iter().filter_map(|&position| {
            let (_,text)=labeled(&rows[position])?;
            Some((*mentioned_steps(text).last()?,(position,weekday(text)?)))
        }).collect::<HashMap<_,_>>();
        for position in index.saturating_sub(54)..index {
            if timing.contains(&position) { continue; }
            let Some((speaker,text))=labeled(&rows[position]) else { continue };
            if speaker!=lead && !speakers.contains(speaker) { continue; }
            let steps=mentioned_steps(text);
            if steps.len()<2 || !steps.iter().all(|step| operations.contains(step)) { continue; }
            let Some((latest,day))=steps.last().and_then(|step| latest_weekdays.get(step)) else { continue };
            if position<*latest && weekday(text).is_some_and(|previous| previous!=*day) {
                earlier_alternatives.push(position);
            }
        }
        timing.sort_unstable();
        earlier_alternatives.sort_unstable();
        earlier_alternatives.dedup();
        replies.push(confirmation);
        return Some(ConfirmedPlan {index,support:replies,timing,earlier_alternatives});
    }
    None
}

#[cfg(test)]
mod tests {
    #[test]
    fn an_accepted_sequence_needs_independent_replies_and_a_commit_cue() {
        let mut rows=[
            serde_json::json!({"text":"说话人1: 先说场地和报名渠道。"}),
            serde_json::json!({"text":"说话人2: 我觉得先布置再打扫。"}),
            serde_json::json!({"text":"说话人1: 先清理场地，再布置展区，就先这样，大家觉得怎么样。"}),
            serde_json::json!({"text":"说话人2: 可以。"}),
            serde_json::json!({"text":"说话人3: 好的。"}),
            serde_json::json!({"text":"说话人1: 那就行动起来。"}),
        ].to_vec();
        // Add earlier conversation so the candidate is in the closing quarter.
        rows.splice(0..0,(0..10).map(|_|serde_json::json!({"text":"说话人4: 听得见。"})));
        // Four-turn closure must be kept even on a very short document.
        rows.splice(0..0,(0..4).map(|_|serde_json::json!({"text":"说话人4: 到会人已齐。"})));
        let summary=super::confirmed_plan(&rows).unwrap();
        assert_eq!(summary.support.len(),3);
        let confirmation=rows.len()-1;
        rows[confirmation]["text"]=serde_json::json!("说话人1: 回去再想想。");
        assert!(super::confirmed_plan(&rows).is_none());
    }
}
