//! Preserve the scope of spoken judgments and assignments in the published document.
use serde_json::Value;

use super::{commitments, factual_audit, line, Action, Document, Kind, Unit, SOURCE_ITEMS_FACT_LIMIT};

pub(super) struct ReportedCondition {
    text: String,
    sources: Vec<String>,
    speaker: String,
}

pub(super) fn conditional_speakers(brief: &factual_audit::VerifiedBrief, units: &[Unit]) -> Vec<ReportedCondition> {
    let turns = commitments::with_turn_labels(&factual_audit::evidence_sentences(units));
    let mut reported = Vec::new();
    for (i, topic) in brief.document.topics.iter().enumerate() {
        for (j, point) in topic.points.iter().enumerate() {
            if !matches!(point.kind, Kind::Status | Kind::Opinion)
                || !["如果", "假如", "倘若"].iter().any(|cue| point.text.starts_with(cue))
            {
                continue;
            }
            let Some([id]) = brief.evidence.get(&format!("topics[{i}].points[{j}]")).map(Vec::as_slice) else { continue };
            let Some(turn) = turns.iter().find(|row| row["id"] == id.as_str()
                && point.sources.iter().any(|unit| row["source"] == unit.as_str()))
            else { continue };
            let Some(speaker) = turn["turnSpeaker"].as_str() else { continue };
            reported.push(ReportedCondition {text:point.text.clone(),sources:point.sources.clone(),speaker:speaker.to_owned()});
        }
    }
    reported
}

fn content(turn: &Value) -> &str {
    let text = turn["text"].as_str().unwrap_or("");
    super::super::source_resolution::split_turn_label(text).map_or(text, |(_, speech)| speech)
}

fn bound_scope(action: &Action, turns: &[Value]) -> Option<[Action; 2]> {
    let owner = action.owner.as_deref()?;
    let (joint, rest) = action.text.split_once(['，', '；', ',', ';'])?;
    let personal = rest.trim().strip_prefix('由')?.strip_prefix(owner)?.trim();
    let joint_key: String = joint.chars().take(5).collect();
    let verb: String = personal.chars().take(2).collect();
    if action.due.is_some() || !joint.starts_with('把') || joint_key.chars().count() < 5
        || verb.chars().count() != 2 || !line(personal, 176) || rest.matches(owner).count() != 1
        || personal.contains(['，', '；', ',', ';'])
    {
        return None;
    }
    let request = [format!("你来{verb}"), format!("你负责{verb}"), format!("请你{verb}")];
    let cited = |row: &Value| action.sources.iter().any(|id| row["source"] == id.as_str());
    let witnesses = turns.windows(2).enumerate().find_map(|(index, adjacent)| {
        let [speaking, acknowledgement] = adjacent else { return None };
        let ask = content(speaking);
        let assent = content(acknowledgement).trim().trim_end_matches(['。', '！', '，', '、']).trim();
        let directing = speaking["turnSpeaker"].as_str()?;
        if directing == owner || acknowledgement["turnSpeaker"] != owner
            || !matches!(assent, "行" | "好" | "好的" | "可以" | "嗯好")
            || !cited(speaking) || !cited(acknowledgement) || !request.iter().any(|form| ask.contains(form))
        {
            return None;
        }
        let mention = turns[index.saturating_sub(3)..index].iter().rev().find(|row| {
            let spoken = content(row);
            let Some((before, _)) = spoken.split_once(&joint_key) else { return false };
            cited(row) && row["turnSpeaker"] == directing
                && ["我们", "咱们", "大家", "共同"].iter().any(|group| before.contains(group))
                && !["不用", "不要", "先不", "取消", "暂停"].iter().any(|stop| before.contains(stop))
        })?;
        Some([mention, speaking, acknowledgement])
    })?;
    let [joint_quote, directed_quote, confirmation] = witnesses;
    let source = |row: &Value| row["source"].as_str().unwrap().to_owned();
    let mut personal_sources = vec![source(directed_quote)];
    let accepted_unit = source(confirmation);
    if personal_sources[0] != accepted_unit { personal_sources.push(accepted_unit); }
    Some([
        Action{text:format!("{}。",joint.trim_end_matches('。')),owner:None,due:None,sources:vec![source(joint_quote)]},
        Action{text:personal.to_owned(),owner:Some(owner.to_owned()),due:None,sources:personal_sources},
    ])
}

pub(super) fn apply(doc: &mut Document, units: &[Unit], reported: Vec<ReportedCondition>) -> (usize, usize) {
    let mut attributed = 0;
    for point in doc.topics.iter_mut().flat_map(|topic| &mut topic.points) {
        if !matches!(point.kind, Kind::Status | Kind::Opinion) { continue; }
        if let Some(claim) = reported.iter().find(|claim| claim.text == point.text && claim.sources == point.sources) {
            let text = format!("{}：{}", claim.speaker, point.text);
            if line(&text, 90) {
                point.text = text;
                point.kind = Kind::Opinion;
                attributed += 1;
            }
        }
    }
    let total_facts = doc.topics.iter().map(|topic| topic.points.len()+topic.details.len()).sum::<usize>()
        + doc.action_items.len() + doc.decisions.len() + doc.questions.len();
    let mut room = (20usize.saturating_sub(doc.action_items.len())).min(SOURCE_ITEMS_FACT_LIMIT.saturating_sub(total_facts));
    if room == 0 { return (attributed, 0); }
    let turns = commitments::with_turn_labels(&factual_audit::evidence_sentences(units));
    let mut split = 0;
    let original = doc.action_items.clone();
    doc.action_items = std::mem::take(&mut doc.action_items).into_iter().flat_map(|action| {
        if room > 0 {
            if let Some(scoped) = bound_scope(&action, &turns) {
                if !scoped.iter().any(|row| original.iter().any(|existing| row.text == existing.text)) {
                    room -= 1;
                    split += 1;
                    return Vec::from(scoped);
                }
            }
        }
        vec![action]
    }).collect();
    (attributed, split)
}

#[cfg(test)]
#[test]
fn splits_accepted_personal_step_from_the_cited_collective_task() {
    let text = concat!("说话人1：咱们把设备清点过来，然后开个会。\n",
                       "说话人1：接下来你来主持一下下次。\n",
                       "说话人2：行。\n");
    let units = vec![Unit{id:"u001".into(),text:text.into()}];
    let turns = commitments::with_turn_labels(&factual_audit::evidence_sentences(&units));
    let task = Action{text:"把设备清点好再开会，由说话人2主持下次会议。".into(),
        owner:Some("说话人2".into()),due:None,sources:vec!["u001".into()]};
    let [joint, personal] = bound_scope(&task, &turns).unwrap();
    assert!(joint.owner.is_none() && joint.text.contains("把设备清点"));
    assert_eq!(personal.owner.as_deref(), Some("说话人2"));
    assert_eq!(personal.text, "主持下次会议。");
    assert!(bound_scope(&task, &turns[..2]).is_none());
    let mut dated = task;
    dated.due = Some("周三".into());
    assert!(bound_scope(&dated, &turns).is_none());
}

#[cfg(test)]
#[test]
fn retains_the_speaker_for_an_opinion_on_the_same_turn() {
    use serde_json::json;
    let units = vec![Unit{id:"u000".into(),text:"说话人2：这是我的看法。如果货架太低，就不适合存放这些货。\n".into()}];
    let doc: Document = serde_json::from_value(json!({
        "purpose":"讨论货架",
        "topics":[{"title":"货架高度","points":[{"kind":"opinion","text":"如果货架太低，就不适合存放这些货。","sources":["u000"]}]}],
        "actionItems":[],"decisions":[],"questions":[]
    })).unwrap();
    let brief = factual_audit::VerifiedBrief{document:doc.clone(),
        evidence:std::collections::HashMap::from([("topics[0].points[0]".into(),vec!["e0001".into()])]),
        pending_quotes:Vec::new()};
    let mut published = doc;
    let speakers = conditional_speakers(&brief, &units);
    assert_eq!(apply(&mut published, &units, speakers), (1,0));
    assert_eq!(published.topics[0].points[0].text, "说话人2：如果货架太低，就不适合存放这些货。");
}
