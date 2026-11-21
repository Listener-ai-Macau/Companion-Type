//! A source-bound disagreement can qualify a duplicate assertion in the rendered minutes.
use std::sync::LazyLock;
use serde_json::{json, Value};

use super::{factual_audit, Document, Unit};

struct Dispute<'a> {
    positive: &'a str,
    negative: String,
    witnesses: [&'a Value; 2],
}

fn reported_polarity(text: &str) -> Option<(&str, String)> {
    let (first, positive) = ["否认", "回应", "反驳"].into_iter().find_map(|verb| {
        let (earlier, later) = text.split_once(verb)?;
        let clause = later.trim().split(['，', '；', '：', '、', '。', '！', '？', ',', ';']).next()?;
        let positive = if verb == "否认" { clause } else { clause.strip_prefix(['不', '没'])? };
        earlier.contains(positive).then_some((earlier, positive))
    })?;
    if !super::line(positive, 20) || positive.chars().count() < 3
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
                text.split_once(positive).is_some_and(|(prefix, _)| shared_referent(first_prefix, prefix, report))
                    && ["已核实", "已确认", "经核实", "现已查明", "核对结果", "最终确定"]
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

fn reported_financial_values(text: &str) -> Option<[f64; 3]> {
    static FIELDS: LazyLock<[regex::Regex; 3]> = LazyLock::new(|| {
        ["营业利润", "营业外(?:支)?净支出", "净利润"].map(|field| regex::Regex::new(&format!(
            r"{field}[\s为是约在实现共计合计大概有：:]{{0,7}}(?P<value>[-－]?[零〇一二两三四五六七八九十百千万亿半0-9０-９.．]+(?:元|块钱|美元))"
        )).unwrap())
    });
    if ["所得税", "税后调整", "另有", "冲回", "更正为", "修正为", "净收益"].iter()
        .any(|cue| text.contains(cue))
    {
        return None;
    }
    let mut totals = [0.0; 3];
    for (rule, total) in FIELDS.iter().zip(&mut totals) {
        let mut hits = rule.captures_iter(text);
        let amount = hits.next()?.name("value")?.as_str();
        if hits.next().is_some() || amount.starts_with(['-', '－']) { return None; }
        let (quantity, unit) = super::source_items::measures(amount).next()?;
        if unit != "元" { return None; }
        *total = quantity;
    }
    Some(totals)
}

pub(super) fn mark_financial_pending(doc: &mut Document, units: &[Unit]) -> Vec<Value> {
    const NOTE: &str = "三项财务口述数字之间的关系待核实";
    let evidence = factual_audit::evidence_sentences(units);
    let reports: Vec<_> = evidence.iter().filter_map(|row| {
        let values = reported_financial_values(row["text"].as_str()?)?;
        // Keep the reported amounts. When the implied intermediate balance
        // cannot explain the stated net figure, expose the open reconciliation.
        (values[2] > values[0] - values[1] + 0.01).then_some((row, values))
    }).collect();
    let mut changes = Vec::new();
    let mut qualify = |text: &mut String, cited: &[String], limit| {
        if text.contains("待核实") { return; }
        let Some((matched, _)) = reports.iter().find(|(row, amounts)| cited.iter().any(|id| row["source"] == id.as_str())
            && reported_financial_values(text) == Some(*amounts)) else { return; };
        let revised = format!("{}。{NOTE}。", text.trim_end_matches(['。', '！', '？']));
        if !super::line(&revised, limit) { return; }
        *text = revised;
        changes.push(json!({"evidence":matched["id"],"text":text}));
    };
    for topic in &mut doc.topics {
        for point in &mut topic.points { qualify(&mut point.text, &point.sources, 90); }
        for entry in &mut topic.details { qualify(&mut entry.text, &entry.sources, 120); }
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
fn oral_financial_comparison_preserves_amounts_and_stays_grounded() {
    let brief = |unit: &str| serde_json::from_value::<Document>(json!({
        "purpose":"复盘经营",
        "topics":[{"title":"财务","points":[{"kind":"status","sources":[unit],
          "text":"主营收入约100万元，营业利润80万元，营业外净支出70万元，净利润50万元。"}],"details":[]}],
        "decisions":[],"actionItems":[],"questions":[]
    })).unwrap();
    let unit = Unit { id:"u000".into(), text:"说话人5: 上半年主营业务收入约一百万元，营业利润是在八十万元 营业外支净支出是七十万元 咱们总共实现净利润为五十万元".into() };
    let mut doc = brief("u000");
    assert_eq!(mark_financial_pending(&mut doc,&[unit]).len(),1);
    assert_eq!(doc.topics[0].points[0].text,
        "主营收入约100万元，营业利润80万元，营业外净支出70万元，净利润50万元。三项财务口述数字之间的关系待核实。");
    let other = Unit { id:"u000".into(), text:"营业利润八十万元，营业外净支出七十万元，另有专项减免，净利润五十万元。".into() };
    assert!(mark_financial_pending(&mut brief("u000"), &[other]).is_empty());
    let other = Unit { id:"u001".into(), text:"营业利润八十万元，营业外净支出七十万元，净利润五十万元。".into() };
    assert!(mark_financial_pending(&mut brief("u000"), &[other]).is_empty());
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
    let mut reply = doc.clone();
    reply.topics[0].details[1].text = "说话人2称临时仓库会积水，另一方当场回应不会积水、通风正常。".into();
    assert_eq!(mark_pending(&mut reply, &units).len(), 1);
    assert_eq!(mark_pending(&mut doc, &units).len(), 1);
    assert_eq!(doc.topics[0].details[0].text, "临时仓库通风，是否会积水待核实；库存待盘点。");
    assert_eq!(doc.topics[0].details[0].sources, ["u001","u000"]);
    assert!(mark_pending(&mut doc, &units).is_empty());
}
