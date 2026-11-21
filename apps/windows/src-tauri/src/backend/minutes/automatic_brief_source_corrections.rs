//! Preserve the source scope of high-impact claims before factual review.
use std::{collections::HashMap, sync::LazyLock};

use regex::Regex;
use serde_json::{json, Value};

use super::{answer_layout::{Fact, Placement}, line, normalized};

fn half_refund<'a>(source: &'a str, fee: &str) -> Option<&'a str> {
    source.match_indices(fee).find_map(|(at, _)| {
        let tail = &source[at + fee.len()..];
        ["返还了一半", "返还一半", "退还了一半", "退还一半", "退回了一半", "退了一半", "退一半"]
            .iter().find_map(|word| tail.strip_prefix(*word))
    })
}

fn refund_period<'a>(statement: &'a str, source: &str) -> Option<(String, &'a str)> {
    static SHORT_BASE: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?P<period>半个?学年|半年|一个学期|一学期|六个月)(?P<fee>[\p{Han}]{2,7}费)(?:的)?(?:一半|50[%％])"
    ).unwrap());
    static PAID_TERM: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:交的是|交了|缴纳的是|缴了|缴费按|已交|已缴|收的是|收了|收取|按)[^，。；;！？\n]{0,9}?(?P<term>一学年|整学年|一年度|整年|全年|一年)"
    ).unwrap());
    static RETURNED_TERM: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:只(?:是)?把[^，。；;！？\n]{0,12}?(?:一个学期|一学期)[^，。；;！？\n]{0,12}?(?:退款|退回|退还|返还)|(?:退还|返还|退回|退)(?:了)?[^，。；;！？\n]{0,7}?(?:一个学期|一学期))"
    ).unwrap());
    let mut hits = SHORT_BASE.captures_iter(statement);
    let hit = hits.next()?;
    if hits.next().is_some() {
        return None;
    }
    let whole = hit.get(0)?;
    let lead = &statement[..whole.start()];
    if !["退了", "退还了", "退回了", "返还了", "退", "退还"].iter().any(|word| lead.ends_with(word))
        || ["如果", "假设", "建议", "待核实", "没有退"].iter().any(|word| lead.contains(word))
    {
        return None;
    }
    let source = normalized(source);
    let fee = hit.name("fee")?.as_str();
    half_refund(&source, fee)?;
    let mut billed_terms = PAID_TERM.captures_iter(&source).filter_map(|hit| hit.name("term"));
    let first = billed_terms.next()?.as_str();
    if !RETURNED_TERM.is_match(&source) {
        return None;
    }
    let academic = first.contains("学年") || billed_terms.any(|term| term.as_str().contains("学年"));
    let replacement = if academic { "一学年" } else { "一年" };
    let mut corrected = statement.to_owned();
    corrected.replace_range(whole.range(), &format!("{replacement}{fee}的一半（一个学期）"));
    line(&corrected, 90).then_some((corrected, fee))
}

fn refund_absence(fee: &str, origin: usize, evidence: &[Value]) -> Option<(String, [String; 2])> {
    static ABSENCE: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"^(?:呃|嗯)*(?:没有|没){1,3}(?:那[个些]|这[个些])?(?P<occupant>学生|学员|住户|租户)(?:来住|入住|住宿)"
    ).unwrap());
    let speaker = evidence[origin]["turnSpeaker"].as_str()?;
    let mut candidates = evidence.iter().enumerate().skip(origin + 1).take(100).filter_map(|(at, row)| {
        if row["turnSpeaker"].as_str()? != speaker {
            return None;
        }
        let text = normalized(row["text"].as_str()?);
        let cause = half_refund(&text, fee)?.trim_start_matches('儿').strip_prefix("因为")?;
        if !cause.contains("半年") || !(cause.ends_with("没有") || cause.ends_with('没')) {
            return None;
        }
        let following = evidence.iter().skip(at + 1).take(3).find(|other| {
            other["source"] == row["source"] && other["turnSpeaker"] == row["turnSpeaker"]
        })?;
        let (_, body) = super::super::source_resolution::split_turn_label(following["text"].as_str()?)?;
        let body = normalized(body);
        let occupant = ABSENCE.captures(&body)?.name("occupant")?.as_str();
        Some((format!("原因是这半年{occupant}未实际住宿。"),
              [row["id"].as_str()?.to_owned(), following["id"].as_str()?.to_owned()]))
    });
    let candidate = candidates.next()?;
    candidates.next().is_none().then_some(candidate)
}

fn verification_before_disposal(fact: &Fact, origin: usize, evidence: &[Value]) -> Option<(String, Vec<String>)> {
    static DISPOSAL: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"超过(?P<limit>[零一二两三四五六七八九十百0-9]{1,5}(?:天|小时|个?月))的?(?:我们|咱们)?(?:就|即|直接|一律)?(?:要|须|必须)?(?:清理|清退|处置|销毁|报废)"
    ).unwrap());
    static REFERRED_CHECK: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:刚才说的|刚说的|刚才提到的|前面说的|上述)(?:那种|这种|这类|这批|的)?(?P<object>[\p{Han}]{2,12}?)(?:我们|咱们)?(?:不允许|不准|不得|若|如果)?超过(?P<limit>[零一二两三四五六七八九十百0-9]{1,5}(?:天|小时|个?月))(?:你|我们|就|要|的|先|必须|一定|得){1,8}(?P<check>核查|核实|查清|确认)"
    ).unwrap());
    let draft = normalized(&fact.text);
    let limit = DISPOSAL.captures(&draft)?.name("limit")?.as_str();
    if ["先核", "先查", "先确认", "负责核查", "待核实", "如果", "建议"].iter().any(|word| draft.contains(word)) {
        return None;
    }
    let previous = &evidence[origin];
    let earlier = normalized(previous["text"].as_str()?);
    let earlier_limit = DISPOSAL.captures(&earlier)?.name("limit")?.as_str();
    if limit != earlier_limit {
        return None;
    }
    let speaker = previous["turnSpeaker"].as_str()?;
    let mut corrections = evidence.iter().enumerate().skip(origin + 1).take(24).filter_map(|(position, row)| {
        if row["turnSpeaker"].as_str()? != speaker {
            return None;
        }
        let text = normalized(row["text"].as_str()?);
        let checked = REFERRED_CHECK.captures(&text)?;
        let object = checked.name("object")?.as_str();
        if checked.name("limit")?.as_str() != limit || !evidence[origin.saturating_sub(12)..=origin]
            .iter().any(|earlier| earlier["text"].as_str().is_some_and(|line| line.contains(object)))
        {
            return None;
        }
        let check = checked.name("check")?.as_str();
        let next = evidence.iter().skip(position + 1).take(3)
            .find(|next| next["turnSpeaker"] == row["turnSpeaker"]);
        let next = next.and_then(|next| {
            let text = next["text"].as_str()?;
            let (_, text) = super::super::source_resolution::split_turn_label(text)?;
            let clause = text.trim().split(['，', '。', '；', '！', '？', '呃', '\n']).next()?.trim();
            (["找到", "联系", "核实", "确认"].iter().any(|word| clause.starts_with(word))
                && !clause.contains(['「', '」']) && line(clause, 28))
                .then_some((clause, next["id"].as_str()?))
        });
        let mut repaired = format!("对超过{limit}的{object}先{check}。");
        let mut sources = vec![row["id"].as_str()?.to_owned()];
        if let Some((clause, id)) = next {
            repaired.push_str(&format!("后续原话「{clause}」。"));
            sources.push(id.to_owned());
        }
        line(&repaired, 90).then_some((repaired, sources))
    });
    let correction = corrections.next()?;
    corrections.all(|next| next.0 == correction.0).then_some(correction)
}

pub(super) fn correct(facts: &mut [Fact], evidence: &[Value]) -> Vec<Value> {
    let positions: HashMap<_, _> = evidence.iter().enumerate()
        .filter_map(|(index, row)| Some((row["id"].as_str()?, index))).collect();
    let mut changes = Vec::new();
    for fact in facts {
        let mut proposals = fact.evidence.iter().filter_map(|id| {
            let origin = *positions.get(id.as_str())?;
            if let Some((mut reworded, fee)) = refund_period(&fact.text, evidence[origin]["text"].as_str()?) {
                let mut sources = fact.evidence.clone();
                if let Some((cause, ids)) = refund_absence(fee, origin, evidence) {
                    let with_cause = format!("{reworded}{cause}");
                    if line(&with_cause, 90) && sources.len() + ids.len() <= 8 {
                        reworded = with_cause;
                        for id in ids {
                            if !sources.contains(&id) { sources.push(id); }
                        }
                    }
                }
                return Some((reworded, sources));
            }
            if fact.placement == Placement::Decision {
                return verification_before_disposal(fact, origin, evidence);
            }
            None
        });
        let Some((text, sources)) = proposals.next() else { continue; };
        if proposals.any(|next| next.0 != text) {
            continue;
        }
        changes.push(json!({"id":fact.id,"oldEvidence":fact.evidence,"evidence":sources}));
        fact.text = text;
        fact.evidence = sources;
    }
    changes
}

#[cfg(test)]
mod tests {
    use super::*;
    use super::super::Kind;

    #[test]
    fn refund_uses_the_billed_period_when_the_same_fee_and_refunded_period_are_explicit() {
        let draft = "住宿费、学费、书费中目前只退了半年住宿费的一半。";
        let source = "说话人2: 只有这个住宿费返还了一半，因为我们交了是一年度吗，他是从上个上半季度开始交了交的是一一一学年的，咱们只是把这半这一个学期的住宿费退款。";
        assert_eq!(refund_period(draft, source).map(|(text, _)| text).as_deref(),
            Some("住宿费、学费、书费中目前只退了一学年住宿费的一半（一个学期）。"));
        assert!(refund_period(draft, &source.replace("一个学期", "一个月")).is_none());
        assert!(refund_period(draft, &source.replace("住宿费返还了", "书费返还了")).is_none());
        assert!(refund_period("若退了半年住宿费的一半。", "只说交了一学年的住宿费。").is_none());
        assert!(refund_period("住宿费退了全年住宿费的一半。", source).is_none());
    }

    #[test]
    fn a_repeated_refund_keeps_the_stated_reason_with_the_billing_scope() {
        let mut evidence = [
            json!({"id":"e0021","source":"u001","turnSpeaker":"说话人2","text":"住宿费返还了一半，交的是一学年的，只是把这一个学期的住宿费退款。"}),
            json!({"id":"e0101","source":"u005","turnSpeaker":"说话人2","text":"说话人2: 对住宿费退一半儿因为这学年这半年这个这半个学年没有"}),
            json!({"id":"e0102","source":"u005","turnSpeaker":"说话人1","text":"说话人1: 那个住宿费退一半儿"}),
            json!({"id":"e0103","source":"u005","turnSpeaker":"说话人2","text":"说话人2: 没有没有那个学生来住有反馈啊"}),
        ];
        let old = Fact {id:"a044".into(), placement:Placement::Topic, kind:Kind::Status,
            text:"目前只退了半年住宿费的一半。".into(), owner:None, due:None,
            evidence:vec!["e0021".into()]};
        let mut facts = [old.clone()];
        assert_eq!(correct(&mut facts, &evidence).len(), 1);
        assert_eq!(facts[0].text, "目前只退了一学年住宿费的一半（一个学期）。原因是这半年学生未实际住宿。");
        assert_eq!(facts[0].evidence,["e0021","e0101","e0103"]);
        evidence[3]["turnSpeaker"] = json!("说话人1");
        let mut facts = [old];
        assert_eq!(correct(&mut facts, &evidence).len(), 1);
        assert_eq!(facts[0].evidence,["e0021"]);
    }

    #[test]
    fn later_verification_requires_the_same_speaker_threshold_and_referred_subject() {
        let original = Fact { id:"a021".into(), placement:Placement::Decision, kind:Kind::Decision,
            text:"厂区没有宾馆，外来车辆停放超过一天的就要清理，不能停半个月。".into(),
            owner:None, due:None, evidence:vec!["e0164".into()] };
        let evidence = vec![
            json!({"id":"e0156","turnSpeaker":"说话人3","text":"外来人士把停车场当免费停车场，有的就是僵尸车。"}),
            json!({"id":"e0164","turnSpeaker":"说话人4","text":"超过一天的 因为厂区里面没有宾馆，超过一天的我们就要清理，而不是半个月。"}),
            json!({"id":"e0180","turnSpeaker":"说话人4","text":"说话人4: 要做好机动车辆管理，杜绝刚才说的那种僵尸车我们不允许超过一天你必须核查\n"}),
            json!({"id":"e0181","turnSpeaker":"说话人3","text":"嗯 对"}),
            json!({"id":"e0182","turnSpeaker":"说话人4","text":"说话人4: 找到这辆车的主人及时开走呃其实从入口就要查清楚。"}),
        ];
        let mut rows = vec![original.clone()];
        assert_eq!(correct(&mut rows, &evidence).len(), 1);
        assert_eq!(rows[0].text,"对超过一天的僵尸车先核查。后续原话「找到这辆车的主人及时开走」。");
        assert_eq!(rows[0].evidence,["e0180","e0182"]);
        for (position, field, replacement) in [
            (2,"turnSpeaker","说话人1"),
            (0,"text","说话人在讨论物料报废。"),
            (2,"text","上述僵尸车超过半个月你必须核查。"),
        ] {
            let mut altered = evidence.clone();
            altered[position][field] = json!(replacement);
            assert!(correct(&mut [original.clone()], &altered).is_empty());
        }
    }
}
