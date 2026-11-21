//! A source-bound disagreement can qualify a duplicate assertion in the rendered minutes.
use serde_json::{json, Value};

use super::{factual_audit, Document, Unit};

struct Dispute<'a> {
    positive: &'a str,
    negative: String,
    witnesses: [&'a Value; 2],
}

fn reported_polarity(text: &str) -> Option<(&str, String)> {
    let (first, second) = text.split_once(['；', ';'])?;
    let (_, positive) = second.split_once("否认")?;
    let positive = positive.trim().trim_end_matches(['。', '！', '？']);
    if !super::line(positive, 20) || positive.chars().count() < 4
        || positive.contains(['，', '；', '：', '、', '。', '！', '？'])
        || !first.contains(positive)
        || !["称", "质疑", "认为", "据"].iter().any(|cue| first.contains(cue))
    {
        return None;
    }
    let negative = if positive.starts_with('有') {
        format!("没{positive}")
    } else if positive.starts_with(['会', '能', '应', '是']) {
        format!("不{positive}")
    } else {
        return None;
    };
    (!first.contains(&negative)).then_some((positive, negative))
}

fn shared_referent(first: &str, second: &str, report: &str) -> bool {
    let recent: Vec<_> = first.chars().rev().take(16).collect();
    recent.windows(4).any(|window| {
        let literal: String = window.iter().rev().collect();
        literal.chars().all(|c| c.is_alphanumeric()) && second.contains(&literal) && report.contains(&literal)
    })
}

fn dispute<'a>(report: &'a str, sources: &[String], evidence: &'a [Value]) -> Option<Dispute<'a>> {
    let (positive, negative) = reported_polarity(report)?;
    let direct = |row: &Value| sources.iter().any(|unit| row["source"] == unit.as_str());
    let split = super::super::source_resolution::split_turn_label;
    for (index, first) in evidence.iter().enumerate().filter(|(_, row)| direct(row)) {
        let Some((first_speaker, first_content)) = first["text"].as_str().and_then(split) else { continue };
        let Some((first_prefix, _)) = first_content.split_once(positive) else { continue };
        if first_content.contains(&negative) { continue; }
        for (offset, second) in evidence[index + 1..].iter().take(8).enumerate().filter(|(_, row)| direct(row)) {
            let Some((second_speaker, second_content)) = second["text"].as_str().and_then(split) else { continue };
            let Some((second_prefix, _)) = second_content.split_once(&negative) else { continue };
            if first_speaker == second_speaker || !shared_referent(first_prefix, second_prefix, report) {
                continue;
            }
            let resolved = evidence[index + offset + 2..].iter().any(|row| {
                let text = row["text"].as_str().unwrap_or("");
                text.contains(positive) && ["已核实", "已确认", "经核实", "现已查明", "核对结果", "最终确定"]
                    .iter().any(|cue| text.contains(cue))
            });
            if !resolved { return Some(Dispute { positive, negative, witnesses: [first, second] }); }
        }
    }
    None
}

fn qualify(
    text: &mut String, sources: &mut Vec<String>, disputes: &[Dispute<'_>], limit: usize,
) -> Vec<Value> {
    let mut changes = Vec::new();
    for item in disputes {
        if !item.witnesses.iter().any(|row| sources.iter().any(|id| row["source"] == id.as_str())) {
            continue;
        }
        let mut changed = false;
        let revised: String = text.split_inclusive(['，', '；', '。', ',', ';']).map(|chunk| {
            let clause = chunk.trim_end_matches(['，', '；', '。', ',', ';']);
            if clause.trim() == item.positive || clause.trim() == item.negative {
                changed = true;
                format!("是否{}待核实{}", item.positive, &chunk[clause.len()..])
            } else {
                chunk.to_owned()
            }
        }).collect();
        if !changed || !super::line(&revised, limit) { continue; }
        let mut expanded = sources.clone();
        for row in item.witnesses {
            let id = row["source"].as_str().unwrap();
            if !expanded.iter().any(|existing| existing == id) { expanded.push(id.to_owned()); }
        }
        if expanded.len() > 8 { continue; }
        *text = revised;
        *sources = expanded;
        changes.push(json!({"text":text,"evidence":item.witnesses.map(|row| &row["id"])}));
    }
    changes
}

pub(super) fn mark_pending(doc: &mut Document, units: &[Unit]) -> Vec<Value> {
    let evidence = factual_audit::evidence_sentences(units);
    let mut changes = Vec::new();
    for topic in &mut doc.topics {
        let reports: Vec<_> = topic.points.iter().map(|p| (p.text.clone(), p.sources.clone()))
            .chain(topic.details.iter().map(|p| (p.text.clone(), p.sources.clone()))).collect();
        let disputes: Vec<_> = reports.iter().filter_map(|(text, units)| dispute(text, units, &evidence))
            .filter(|item| !doc.decisions.iter().any(|decision| decision.text.contains(item.positive)))
            .collect();
        for detail in &mut topic.details {
            changes.extend(qualify(&mut detail.text, &mut detail.sources, &disputes, 120));
        }
    }
    changes
}

#[cfg(test)]
#[test]
fn only_grounded_unresolved_opposition_qualifies_the_literal_duplicate() {
    let units = vec![
        Unit{id:"u000".into(),text:"说话人2：据调查临时仓库好像会积水。\n".into()},
        Unit{id:"u001".into(),text:"说话人4：临时仓库是不会积水的。\n".into()},
    ];
    let mut doc: Document = serde_json::from_value(json!({
        "purpose":"核对临时仓库",
        "topics":[{"title":"仓库","points":[{"kind":"status","text":"设备还在原位。","sources":["u000"]}],
          "details":[{"text":"临时仓库通风，不会积水；库存待盘点。","sources":["u001"]},
                     {"text":"说话人2称临时仓库会积水；说话人4随后否认会积水。","sources":["u000","u001"]}]}],
        "decisions":[],"actionItems":[],"questions":[]
    })).unwrap();
    let mut unlabelled = units.clone();
    unlabelled[1].text = "临时仓库是不会积水的。".into();
    assert!(mark_pending(&mut doc.clone(), &unlabelled).is_empty());
    let mut closed = units.clone();
    closed.push(Unit{id:"u002".into(),text:"说话人1：经核实临时仓库不会积水。".into()});
    assert!(mark_pending(&mut doc.clone(), &closed).is_empty());
    assert_eq!(mark_pending(&mut doc, &units).len(), 1);
    assert_eq!(doc.topics[0].details[0].text, "临时仓库通风，是否会积水待核实；库存待盘点。");
    assert_eq!(doc.topics[0].details[0].sources, ["u001","u000"]);
    assert!(mark_pending(&mut doc, &units).is_empty());
}
