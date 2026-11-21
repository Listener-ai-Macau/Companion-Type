//! Preserve the source scope of high-impact claims before factual review.
use std::{collections::HashMap, sync::LazyLock};

use regex::Regex;
use serde_json::{json, Value};

use super::{answer_layout::{Fact, Placement}, line, normalized, Document, Entry, Kind};

fn half_refund<'a>(source: &'a str, fee: &str) -> Option<&'a str> {
    source.match_indices(fee).find_map(|(at, _)| {
        let tail = &source[at + fee.len()..];
        ["返还了一半", "返还一半", "退还了一半", "退还一半", "退回了一半", "退了一半", "退一半"]
            .iter().find_map(|word| tail.strip_prefix(*word))
    })
}

fn paid_term() -> &'static Regex {
    static PAID_TERM: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:交的是|交了|缴纳的是|缴了|缴费按|已交|已缴|收的是|收了|收取|按)[^，。；;！？\n]{0,9}?(?P<term>一学年|整学年|一年度|整年|全年|一年)"
    ).unwrap());
    &PAID_TERM
}

fn billed_annual_refund(source: &str, fee: &str) -> Option<&'static str> {
    static RETURNED_TERM: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:只(?:是)?把[^，。；;！？\n]{0,12}?(?:一个学期|一学期)[^，。；;！？\n]{0,12}?(?:退款|退回|退还|返还)|(?:退还|返还|退回|退)(?:了)?[^，。；;！？\n]{0,7}?(?:一个学期|一学期))"
    ).unwrap());
    half_refund(source, fee)?;
    let mut periods = paid_term().captures_iter(source).filter_map(|hit| hit.name("term"));
    let first = periods.next()?.as_str();
    if !RETURNED_TERM.is_match(source) {
        return None;
    }
    let academic = first.contains("学年") || periods.any(|term| term.as_str().contains("学年"));
    Some(if academic { "一学年" } else { "一年" })
}

fn refund_period<'a>(statement: &'a str, source: &str) -> Option<(String, &'a str)> {
    static SHORT_BASE: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:半个?学年|半年|一个学期|一学期|六个月)(?P<fee>[\p{Han}]{2,7}费)(?:的)?(?:一半|50[%％])"
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
    let replacement = billed_annual_refund(&source, fee)?;
    let mut corrected = statement.to_owned();
    corrected.replace_range(whole.range(), &format!("{replacement}{fee}的一半（一个学期）"));
    line(&corrected, 90).then_some((corrected, fee))
}

pub(super) fn retained_refund_measure(span: &str, statement: &str, source: &str) -> bool {
    if !matches!(span, "一年" | "半季度") {
        return false;
    }
    static REFUND: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:退了|退还了|退回了|返还了)(?P<cycle>一学年|一年)(?P<fee>[\p{Han}]{2,7}费)的一半（一个学期）"
    ).unwrap());
    let statement = normalized(statement);
    let source = normalized(source);
    let Some(refund) = REFUND.captures(&statement) else { return false; };
    if billed_annual_refund(&source, &refund["fee"]) != Some(&refund["cycle"]) {
        return false;
    }
    let mut occurrences = source.match_indices(span).peekable();
    occurrences.peek().is_some() && occurrences.all(|(start, word)| {
        let end = start + word.len();
        if span == "一年" {
            return paid_term().captures_iter(&source).any(|match_| {
                match_.name("term").is_some_and(|term| term.start() == start && term.end() >= end)
            });
        }
        let before = source[..start].rsplit(['，', ',', '。', '；']).next().unwrap_or("");
        let after = &source[end..];
        before.contains('从') && ["开始交", "开始缴"].iter().any(|word| after.starts_with(word))
            && paid_term().is_match(after.split(['。', '；']).next().unwrap_or(""))
    })
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

fn verification_before_disposal(statement: &str, origin: usize, evidence: &[Value]) -> Option<(String, Vec<String>)> {
    static DISPOSAL: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"超过(?P<limit>[零一二两三四五六七八九十百0-9]{1,5}(?:天|小时|个?月))(?:的(?:[\p{Han}]{2,9}?)?)?(?:我们|咱们)?(?:就|即|直接|一律)?(?:要|须|必须)?(?:清理|清退|处置|销毁|报废)"
    ).unwrap());
    static REFERRED_CHECK: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:刚才说的|刚说的|刚才提到的|前面说的|上述)(?:那种|这种|这类|这批|的)?(?P<object>[\p{Han}]{2,12}?)(?:我们|咱们)?(?:不允许|不准|不得|若|如果)?超过(?P<limit>[零一二两三四五六七八九十百0-9]{1,5}(?:天|小时|个?月))(?:你|我们|就|要|的|先|必须|一定|得){1,8}(?P<check>核查|核实|查清|确认)"
    ).unwrap());
    let draft = normalized(statement);
    let limit = DISPOSAL.captures(&draft)?.name("limit")?.as_str();
    if ["先核", "先查", "先确认", "负责核查", "待核实", "如果", "建议", "尚未", "暂不",
        "无需", "不得清", "不清理", "不应", "不能清", "禁止"].iter().any(|word| draft.contains(word))
    {
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

pub(super) fn widens_verified_disposal(
    original: &str, verified_ids: &[String], proposed: &Fact, evidence: &[Value],
) -> bool {
    if proposed.placement != Placement::Decision
        || !proposed.evidence.iter().all(|id| verified_ids.contains(id))
    {
        return false;
    }
    proposed.evidence.iter().any(|id| {
        let Some(position) = evidence.iter().position(|row| row["id"] == id.as_str()) else { return false; };
        verification_before_disposal(&proposed.text, position, evidence).is_some_and(|(scope, ids)| {
            normalized(original) == normalized(&scope) && ids.iter().all(|id| verified_ids.contains(id))
        })
    })
}

pub(super) enum DisposalEcho {
    Drop,
    RetainSeparateClause(String, Vec<String>),
}

pub(super) fn disposal_echo(
    statement: &str, refs: &[String], kept_decisions: &[&str], evidence: &[Value],
) -> Option<DisposalEcho> {
    if !statement.contains("超过") || kept_decisions.is_empty() {
        return None;
    }
    for id in refs {
        let Some(position) = evidence.iter().position(|row| row["id"] == id.as_str()) else { continue; };
        let Some((prior, _)) = verification_before_disposal(statement, position, evidence) else { continue; };
        if !kept_decisions.iter().any(|kept| normalized(kept) == normalized(&prior)) {
            continue;
        }
        let separate: Vec<_> = statement.split(['；', ';']).filter(|clause| {
            !clause.trim().is_empty() && verification_before_disposal(clause, position, evidence).is_none()
        }).collect();
        if separate.is_empty() {
            return Some(DisposalEcho::Drop);
        }
        let refs: Vec<_> = refs.iter().filter(|other| *other != id).cloned().collect();
        return if refs.is_empty() { None }
            else { Some(DisposalEcho::RetainSeparateClause(separate.join("；"), refs)) };
    }

    static CHECK_ECHO: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"^对(?:停放)?超过(?P<period>[零一二两三四五六七八九十百0-9]{1,5}(?:天|小时|个?月))的[\p{Han}]{2,12}?必须(?:核查|核实|查清|确认)(?:，不允许超过[^。；！？]{2,8})?。?$"
    ).unwrap());
    let [id] = refs else { return None; };
    let statement = normalized(statement);
    let repeated = CHECK_ECHO.captures(&statement)?;
    let period = repeated.name("period")?.as_str();
    let anchor = normalized(evidence.iter().find(|row| row["id"] == id.as_str())?["text"].as_str()?);
    if !anchor.contains(&format!("超过{period}")) || !anchor.contains("必须核查") {
        return None;
    }
    let checked = kept_decisions.iter().find(|kept|
        kept.starts_with(&format!("对超过{period}的")) && kept.contains("先核查"))?;
    let (subject, _) = checked.strip_prefix(&format!("对超过{period}的"))?.split_once("先核查")?;
    anchor.contains(subject).then_some(DisposalEcho::Drop)
}

fn explicit_affiliation_correction(claim: &str, source: &str) -> Option<(String, String, String)> {
    static CORRECTION: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:其实是|准确(地)?说(?:是)?|更正为|说反了[：:，,]?)(?:一个|一家|一所)?\s*(?P<parent>[\p{Han}]{2,8}?)(?P<org>公司|集团|机构|单位|企业)\s*(?:的|旗下)?(?:一个|一家|一所)?\s*(?P<region>[\p{Han}]{2,8}?)(?P<branch>分部|分公司|子公司|办事处)"
    ).unwrap());
    let mut repairs = CORRECTION.captures_iter(source).filter_map(|row| {
        let parent = &row["parent"];
        let region = &row["region"];
        let organisation = &row["org"];
        let branch = &row["branch"];
        if parent == region { return None; }
        let earlier = &source[..row.get(0)?.start()];
        let original_org = format!("{region}{organisation}");
        if !earlier.contains(&original_org) && !earlier.contains(&format!("{region}的{organisation}")) {
            return None;
        }
        // Apply the later wording only to the exact inverse affiliation.
        let invalid = [format!("{original_org}的{parent}{branch}"),
            format!("{original_org}{parent}{branch}"), format!("{region}的{organisation}的{parent}{branch}")];
        let wrong = invalid.iter().find(|text| claim.matches(text.as_str()).count() == 1)?;
        let corrected_org = format!("{parent}{organisation}的{region}{branch}");
        let revised = claim.replacen(wrong, &corrected_org, 1);
        line(&revised, 90).then_some((revised, original_org, corrected_org))
    });
    let original = repairs.next()?;
    repairs.all(|other| other == original).then_some(original)
}

fn age_range(text: &str) -> Option<(regex::Match<'_>, u8)> {
    static RANGE: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"[0-9０-９一二三四五六七八九十]{1,3}(?:到|至|[-–—~～])[0-9０-９一二三四五六七八九十]{1,3}(?:周)?岁"
    ).unwrap());
    static UPPER: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?P<age>[0-9０-９一二三四五六七八九十]{1,3})(?:周)?岁"
    ).unwrap());
    let mut matches = RANGE.find_iter(text);
    let span = matches.next()?;
    if matches.next().is_some() { return None; }
    let upper = UPPER.captures(span.as_str())?.name("age")?.as_str();
    Some((span, age_years(upper)?))
}

fn age_years(raw: &str) -> Option<u8> {
    let number = super::source_items::number_value(raw, false)?;
    (number.fract() == 0.0 && (1.0..=130.0).contains(&number)).then_some(number as u8)
}

fn alternative_age_limits(text: &str) -> Option<[u8; 2]> {
    static LIMIT: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?P<age>[0-9０-９一二三四五六七八九十]{1,3})(?:周)?岁(?:之间|以内|上下)"
    ).unwrap());
    if ["分别", "男性", "女性", "男生", "女生", "各组", "已经确定", "最终确定"]
        .iter().any(|cue| text.contains(cue))
        || !["可以", "或者", "对吧", "备选"].iter().any(|cue| text.contains(cue))
    {
        return None;
    }
    let mut ages = LIMIT.captures_iter(text).filter_map(|row| age_years(&row["age"]));
    let values = [ages.next()?, ages.next()?];
    (ages.next().is_none() && values[0] != values[1]).then_some(values)
}

fn cited_age_alternatives<'a>(
    text: &str, evidence: &'a [&'a Value], universe: &'a [Value], near: usize,
) -> Option<(&'a Value, [u8; 2])> {
    let (_, upper) = age_range(text)?;
    if !["年龄", "人群", "岁对应的", "岁之间"].iter().any(|cue| text.contains(cue)) {
        return None;
    }
    let mut witnesses = universe.iter().enumerate().filter_map(|(index, row)| {
        let alternatives = alternative_age_limits(row["text"].as_str()?)?;
        if !alternatives.contains(&upper)
            || !universe[index.saturating_sub(near)..(index + near + 1).min(universe.len())].iter()
                .any(|nearby| evidence.iter().any(|anchor| anchor["id"] == nearby["id"] && anchor["source"] == row["source"]))
        {
            return None;
        }
        let settled = universe.iter().skip(index + 1).take(6).any(|later| {
            let source = later["text"].as_str().unwrap_or_default();
            later["source"] == row["source"] && ["最终确定", "已经定为", "正式定为", "已确定"]
                .iter().any(|cue| source.contains(cue))
                && ["年龄", "人群"].iter().any(|cue| source.contains(cue)) && age_range(source).is_some()
        });
        (!settled).then_some((row, alternatives))
    });
    let one = witnesses.next()?;
    witnesses.next().is_none().then_some(one)
}

fn retain_age_dependency(text: &str) -> Option<String> {
    let (span, _) = age_range(text)?;
    let rest = &text[span.end()..];
    let independent = rest.strip_prefix("对应的")
        .or_else(|| rest.strip_prefix("人群的")).or_else(|| rest.strip_prefix("年龄组的"))?;
    let revised = format!("{}目标人群的{}（年龄范围待核实）。", &text[..span.start()],
        independent.trim_end_matches(['。', '！', '？']));
    line(&revised, 90).then_some(revised)
}

fn age_pending_text(values: [u8; 2]) -> String {
    format!("待核实：年龄上限提到{}岁和{}岁，实际范围尚未确认。", values[0], values[1])
}

fn unresolved_assignment_discussion(fact: &Fact, cited: &[&Value]) -> bool {
    if fact.placement != Placement::Action || fact.owner.is_some() || fact.due.is_some() {
        return false;
    }
    let text = normalized(&fact.text);
    let discusses = ["讨论", "询问", "征询", "会上讨论", "会上征询"].iter().any(|cue| text.starts_with(cue));
    let unassigned = ["未明确分派", "尚未分派", "承接方尚未确定", "承担尚未确定", "未确定负责人"]
        .iter().any(|cue| text.contains(cue));
    if !discusses || !unassigned || ["会后", "下次会议", "拟定名单", "待提交"].iter().any(|cue| text.contains(cue)) {
        return false;
    }
    cited.iter().any(|row| {
        let quote = normalized(row["text"].as_str().unwrap_or_default());
        ["哪个部门", "哪个团队", "哪一方", "由谁负责", "交给谁"].iter().any(|cue| quote.contains(cue))
            && !["请在", "必须", "务必", "回去以后"].iter().any(|cue| quote.contains(cue))
    })
}

fn retain_opening_period(purpose: &mut String, evidence: &[Value]) -> Option<Value> {
    static REVIEW: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?P<period>上(?:个|一)?季度|上个?月|上半年)的?(?P<scope>销售情况|经营情况|运营情况|工作情况|收入情况|业绩情况|项目进展)(?:哈|啊)?(?:咱们|我们)?(?:来|要)?(?:开(?:一)?(?:场|个)会议|进行复盘|做总结)"
    ).unwrap());
    if ["上个季度", "上一季度", "上季度", "本季度", "上个月", "上月", "本月", "上半年", "下半年"]
        .iter().any(|cue| purpose.contains(cue))
    {
        return None;
    }
    let mut reviewed = evidence.iter().take(18).filter_map(|row| {
        let speech = normalized(row["text"].as_str()?);
        if !["今天", "本次会议", "各部门", "大家"].iter().any(|cue| speech.contains(cue)) {
            return None;
        }
        let fragment = REVIEW.captures(&speech)?;
        let period = match &fragment["period"] {
            "上个季度" | "上一季度" => "上季度",
            "上个月" => "上月",
            _ => &fragment["period"],
        };
        let prefix = format!("回顾{period}{}。", &fragment["scope"]);
        Some((row["id"].as_str()?, prefix))
    });
    let (id, prefix) = reviewed.next()?;
    if reviewed.next().is_some() { return None; }
    let revised = format!("{prefix}{purpose}");
    if !line(&revised, 120) { return None; }
    *purpose = revised;
    Some(json!({"id":"purpose","evidence":id,"state":"reportedOpeningScope"}))
}

pub(super) fn restore_reported_decision_boundary(doc: &mut super::Document, units: &[super::Unit]) -> Vec<Value> {
    let mut moved = Vec::new();
    let mut pending = Vec::new();
    for (index, candidate) in doc.decisions.iter().enumerate() {
        let Some(proposed) = ["会上提出", "会上建议", "会上提议"].into_iter()
            .find_map(|prefix| candidate.text.strip_prefix(prefix)) else { continue; };
        let core = proposed.split(['，','。','；','、']).next().unwrap_or_default();
        if !line(core, 28) || core.chars().count() < 6 { continue; }
        if let Some(later) = doc.decisions.iter().skip(index + 1).find(|decision| {
            decision.text.starts_with("决定") && decision.text.contains(core)
                && decision.sources.iter().any(|id| candidate.sources.contains(id))
        }) {
            if let Some(topic) = super::source_items::omission_topic(doc, &candidate.sources, units) {
                pending.push((index, topic, later.text.clone()));
            }
        }
    }
    for (index, topic, kept) in pending.into_iter().rev() {
        let ordinary = &mut doc.topics[topic];
        if ordinary.details.len() >= super::topic_details_limit() { continue; }
        let item = doc.decisions.remove(index);
        moved.push(json!({"proposal":item.text,"retainedDecision":kept,"sources":item.sources}));
        if !ordinary.points.iter().any(|row| row.text == item.text)
            && !ordinary.details.iter().any(|row| row.text == item.text)
        {
            ordinary.details.push(item);
        }
    }
    moved
}

fn same_or_adjacent_unit(a: &str, b: &str) -> bool {
    fn position(id: &str) -> Option<usize> { id.strip_prefix('u')?.parse().ok() }
    a == b || position(a).zip(position(b)).is_some_and(|(a,b)| a.abs_diff(b) == 1)
}

fn cited_real_report(summary: &str, source: &str) -> bool {
    static COMPLETED_REPORT: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:我们|我方|本公司|本部门|本组)(?:最近|刚刚|此前|上周|上月|上个月|去年|已经)(?:买|购|签|汇|支付|付|交|提交|投入|完成|收|报|启动|卖|售|寄|做|部署)"
    ).unwrap());
    let source = normalized(source);
    let hypothetical = ["假设", "假如", "设例", "如果", "虚构", "设想"];
    let actual_time = ["近期", "最近", "已", "刚", "此前", "上周", "上月", "上个月", "去年"];
    if hypothetical.iter().any(|cue| summary.contains(cue)) {
        return false;
    }

    // An explicit return to present conditions closes the preceding example.
    // It qualifies only a summary that actually shares wording after the reset.
    if ["但是就目前而言", "回到实际情况", "就目前实情", "实际情况是"].iter()
        .filter_map(|cue| source.split_once(cue).map(|(_,tail)| tail))
        .any(|tail| super::source_coverage::shared_literal(summary, tail, 4))
    {
        return true;
    }
    actual_time.iter().any(|cue| summary.contains(cue))
        && COMPLETED_REPORT.find_iter(&source).any(|event| {
            let lead = &source[..event.start()];
            let scope = lead.rsplit(['。','！','？','；']).next().unwrap_or_default();
            !hypothetical.iter().any(|cue| scope.contains(cue))
                && super::source_coverage::shared_literal(summary, &source[event.start()..], 4)
        })
}

fn example_context(text: &str, fact: &Fact, evidence: &[Value], positions: &HashMap<&str, usize>) -> bool {
    let text = normalized(text);
    let framing = ["举个例子", "举一个例子", "举例", "设例", "比方说", "比如说", "假设", "假如"];
    if framing.iter().any(|marker| text.contains(marker)) || text.starts_with("待核") {
        return false;
    }
    let anchors: Vec<_> = fact.evidence.iter().filter_map(|id| positions.get(id.as_str()).copied()).collect();
    if anchors.iter().any(|at| {
        evidence[*at]["text"].as_str().is_some_and(|quote| cited_real_report(&text,quote))
    }) {
        return false;
    }
    anchors.into_iter().any(|at| {
        let span = at.saturating_sub(12)..=at;
        span.rev().take_while(|index| {
            evidence[*index]["source"].as_str().zip(evidence[at]["source"].as_str())
                .is_some_and(|(a,b)| same_or_adjacent_unit(a,b))
        }).any(|index| {
            let raw = evidence[index]["text"].as_str().unwrap_or_default();
            let (_, content) = super::super::source_resolution::split_turn_label(raw).unwrap_or(("", raw));
            let example = normalized(content);
            if !framing.iter().any(|marker| example.contains(marker)) {
                return false;
            }
            // A nearby example qualifies only the same subject. Sharing the
            // generic words for hypothetical speech is insufficient.
            let predicate = framing.iter().fold(example, |words, marker| words.replace(marker, ""));
            super::source_coverage::shared_literal(&text, &predicate, 4)
        })
    })
}

fn narrated_chain(text: &str) -> Option<(&str, Vec<&str>)> {
    let (_, narration) = ["案子是", "案例是", "事情经过是", "事件经过是"].iter()
        .find_map(|marker| text.split_once(marker))?;
    let end = ["的案子", "，就是", "。", "；"].iter().filter_map(|marker| narration.find(marker)).min()?;
    let narration = narration[..end].trim();
    let links: Vec<_> = narration.split(['，', ',']).map(str::trim).collect();
    if !(3..=5).contains(&links.len())
        || !links.iter().all(|link| (3..=12).contains(&link.chars().count())
            && link.chars().all(char::is_alphanumeric))
        || !links.windows(2).all(|pair| {
            (1..=3).any(|count| {
                let subject: String = pair[1].chars().take(count).collect();
                pair[0].ends_with(&subject)
            })
        })
    {
        return None;
    }
    Some((narration, links))
}

fn restore_discussion_condition(
    text: &str, sources: &[String], facts: &[Fact], evidence: &[Value], positions: &HashMap<&str, usize>,
) -> Option<String> {
    let (attribution, summary) = text.split_once("称，").filter(|(label, _)| {
        !label.contains(['，', '。', '：']) && label.chars().count() <= 24
    }).unwrap_or(("", text));
    if ["若", "如果", "假如", "待核", "会上举例"].iter().any(|marker| summary.starts_with(marker)) {
        return None;
    }
    let mut facts = facts.iter().filter(|fact| {
        fact.placement == Placement::Topic && (fact.text == text || fact.text == summary)
    });
    let fact = facts.next()?;
    if facts.next().is_some() { return None; }

    let cited: Vec<_> = fact.evidence.iter().filter_map(|id| {
        let row = &evidence[*positions.get(id.as_str())?];
        let source = row["source"].as_str()?;
        if !sources.iter().any(|id| id == source) { return None; }
        let raw = row["text"].as_str()?;
        Some(super::super::source_resolution::split_turn_label(raw).unwrap_or(("", raw)))
    }).collect();

    for (speaker, quote) in &cited {
        if !attribution.is_empty() && *speaker != attribution { continue; }
        let quote = normalized(quote);
        let Some((condition, outcome)) = quote.split_once("的话") else { continue; };
        if condition.chars().count() < 6 || condition.contains(['，', '。', '；'])
            || !outcome.starts_with(['，', ','])
            || !summary.strip_prefix(condition).is_some_and(|rest| rest.starts_with(['，', ',']))
        {
            continue;
        }
        // The repeated condition must have an explicit lead-in from the same speaker.
        // A nearby discussion, or the words “的话” alone, do not establish it.
        let corroborated = cited.iter().any(|(other_speaker, other_quote)| {
            if speaker != other_speaker { return false; }
            let other_quote = normalized(other_quote);
            let opening = other_quote.trim_start_matches(['呃', '嗯']);
            let Some(opening) = opening.strip_prefix("如果说").or_else(|| opening.strip_prefix("假如说")) else {
                return false;
            };
            let condition_opening = opening.split(['，', '。', '；']).next().unwrap_or_default();
            super::source_coverage::shared_literal(condition, condition_opening, 6)
        });
        if corroborated {
            let prefix = &text[..text.len() - summary.len()];
            let revised = format!("{prefix}若{summary}");
            return line(&revised, 90).then_some(revised);
        }
    }
    None
}

pub(super) fn preserve_published_discussion(doc: &mut Document, facts: &[Fact], evidence: &[Value]) -> Vec<Value> {
    let positions: HashMap<_, _> = evidence.iter().enumerate().filter_map(|(at,row)| Some((row["id"].as_str()?,at))).collect();
    let mut changes = Vec::new();
    for topic in &mut doc.topics {
        let qualify = |text: &mut String, sources: &[String]| {
            if let Some(revised) = restore_discussion_condition(text, sources, facts, evidence, &positions) {
                *text = revised;
                return Some("discussionCondition");
            }
            let original = text.trim_start_matches(super::DRAFT_CONFLICT_PREFIX);
            let fact = facts.iter().find(|fact| fact.text == original && fact.placement == Placement::Topic)?;
            if !example_context(original, fact, evidence, &positions) { return None; }
            let revised = text.replacen(original, &format!("会上举例讨论，{original}"), 1);
            if !line(&revised, 90) { return None; }
            *text = revised;
            Some("exampleContext")
        };
        for item in &mut topic.points {
            if !matches!(item.kind, Kind::Status | Kind::Opinion) { continue; }
            if let Some(kind) = qualify(&mut item.text, &item.sources) {
                item.kind = Kind::Opinion;
                changes.push(json!({"kind":kind,"sources":item.sources}));
            }
        }
        for item in &mut topic.details {
            if let Some(kind) = qualify(&mut item.text, &item.sources) {
                changes.push(json!({"kind":kind,"sources":item.sources}));
            }
        }
    }
    for row in evidence {
        let Some(source) = row["source"].as_str() else { continue; };
        let Some((narration, links)) = row["text"].as_str().and_then(narrated_chain) else { continue; };
        let Some(head) = links.first() else { continue; };
        let Some(tail) = links.last() else { continue; };
        let mut topics = doc.topics.iter_mut().filter(|topic| {
            let cited: Vec<_> = topic.points.iter().map(|item| (&item.text, &item.sources))
                .chain(topic.details.iter().map(|item| (&item.text, &item.sources)))
                .filter(|(_, ids)| ids.iter().any(|id| same_or_adjacent_unit(id, source))).map(|(text,_)| normalized(text)).collect();
            cited.iter().any(|text| super::source_coverage::shared_literal(head, text, 2))
                && cited.iter().any(|text| super::source_coverage::shared_literal(tail, text, 2))
                && links[1..links.len()-1].iter().any(|link| !cited.iter().any(|text| text.contains(*link)))
        });
        let Some(topic) = topics.next() else { continue; };
        if topics.next().is_some() || topic.details.len() >= super::topic_details_limit() { continue; }
        let text = format!("会上讲述的案例经过是「{narration}」。");
        if line(&text, 90) {
            topic.details.push(Entry {text, sources:vec![source.to_owned()], quantity_needs_review:false});
            changes.push(json!({"kind":"narratedChain","evidence":row["id"]}));
        }
    }
    changes
}

#[cfg(test)]
#[test]
fn published_discussion_distinguishes_a_linked_example_and_restores_a_cited_chain() {
    let mut doc: Document = serde_json::from_value(json!({
        "purpose":"复盘设备事件与处置",
        "topics":[{
            "title":"故障复盘",
            "points":[
                {"kind":"status","text":"主机误报时可以继续工作。","sources":["u001"]},
                {"kind":"status","text":"周五继续例行检查。","sources":["u001"]},
                {"kind":"status","text":"进水导致停机，停机又导致延误。","sources":["u001"]}
            ],
            "details":[]
        }],"decisions":[],"questions":[],"actionItems":[]
    })).unwrap();
    let raw = [
        json!({"id":"e0000","source":"u000","text":"说话人1：我举个例子，主机误报时怎么办？"}),
        json!({"id":"e0001","source":"u001","text":"说话人2：在这个例子里，可以继续工作。"}),
        json!({"id":"e0002","source":"u001","text":"说话人3：周五继续例行检查。"}),
        json!({"id":"e0003","source":"u001","text":"说话人3：事情经过是箱体进水，进水致断电，断电致停机，停机致延误。"}),
    ];
    let facts: Vec<_> = doc.topics[0].points.iter().enumerate().map(|(i,item)| Fact {
        id:format!("a{i:03}"),kind:Kind::Status,placement:Placement::Topic,text:item.text.clone(),
        owner:None,due:None,evidence:vec![format!("e{:04}",i+1)],
    }).collect();
    let changes = preserve_published_discussion(&mut doc, &facts, &raw);
    assert_eq!(changes.len(),2);
    assert!(matches!(doc.topics[0].points[0].kind, Kind::Opinion));
    assert_eq!(doc.topics[0].points[1].text,"周五继续例行检查。");
    assert!(doc.topics[0].details[0].text.contains("进水致断电"));
    assert!(preserve_published_discussion(&mut doc, &facts, &raw).is_empty());
    assert!(narrated_chain("事情经过是有人报告，另一人猜测，之后再统计。").is_none());
}

#[cfg(test)]
#[test]
fn reported_past_events_inside_an_example_keep_their_actual_scope() {
    let evidence = [
        json!({"id":"e0041","source":"u003","text":"研发成本是不是比较高？"}),
        json!({"id":"e0042","source":"u003","text":"比如说我们最近买的这个专利是国外公司的成果，我们买回来再进行研发，但是就目前而言回本较慢，目标人群属于少数。"}),
        json!({"id":"e0043","source":"u003","text":"假设上个月我们已经提交登记，这时手续完成后就能验收。"}),
        json!({"id":"e0044","source":"u003","text":"我们最近提交的方案还有另一个范围。"}),
    ];
    let positions: HashMap<_, _> = evidence.iter().enumerate().map(|(i,r)|(r["id"].as_str().unwrap(),i)).collect();
    let classify = |text:&str, id:&str| {
        let fact=Fact{id:"a000".into(),kind:Kind::Status,placement:Placement::Topic,text:text.into(),
            owner:None,due:None,evidence:vec![id.into()]};
        example_context(text,&fact,&evidence,&positions)
    };
    assert!(!classify("近期购买国外公司专利并进行研发。","e0042"));
    assert!(!classify("研发回本较慢，因目标人群属于少数。","e0042"));
    assert!(classify("上个月我们已经提交登记，这时就能验收。","e0043"));
    assert!(!classify("最近提交的方案还有另一个范围。","e0044"));
}

#[cfg(test)]
#[test]
fn published_opinion_keeps_a_repeated_spoken_condition() {
    let rows = [
        json!({"id":"e0001","source":"u001","text":"说话人2：呃如果说送过去的样品反复出现漏液，那就暂停新的试产。"}),
        json!({"id":"e0002","source":"u001","text":"说话人2：样品反复出现漏液的话，就暂停新的试产。"}),
        json!({"id":"e0003","source":"u001","text":"说话人1：样品反复出现漏液，我们已经暂停新的试产。"}),
    ];
    let positions = HashMap::from([("e0001",0), ("e0002",1), ("e0003",2)]);
    let text = "说话人2称，样品反复出现漏液，暂停新的试产。";
    let mut fact = Fact {
        id:"a001".into(), kind:Kind::Status, placement:Placement::Topic,
        text:"样品反复出现漏液，暂停新的试产。".into(), owner:None, due:None,
        evidence:vec!["e0001".into(), "e0002".into()],
    };
    let sources = ["u001".into()];
    assert_eq!(restore_discussion_condition(text, &sources, std::slice::from_ref(&fact), &rows, &positions).as_deref(),
        Some("说话人2称，若样品反复出现漏液，暂停新的试产。"));
    assert!(restore_discussion_condition("说话人1称，样品反复出现漏液，暂停新的试产。",
        &sources, std::slice::from_ref(&fact), &rows, &positions).is_none());
    fact.evidence = vec!["e0002".into(), "e0003".into()];
    assert!(restore_discussion_condition(text, &sources, &[fact], &rows, &positions).is_none());
}

pub(super) fn retain_spoken_state(facts: &mut [Fact], evidence: &[Value], purpose: Option<&mut String>) -> Vec<Value> {
    let source: HashMap<_, _> = evidence.iter().map(|row| (row["id"].as_str().unwrap(), row)).collect();
    let mut changes = Vec::new();
    let mut corrected_labels = Vec::new();
    for fact in facts.iter_mut() {
        let cited: Vec<_> = fact.evidence.iter().filter_map(|id| source.get(id.as_str()).copied()).collect();
        let mut affiliations = cited.iter().filter_map(|row| {
            explicit_affiliation_correction(&fact.text, row["text"].as_str()?).map(|change| (*row, change))
        });
        if let Some((row, (text, former, corrected))) = affiliations.next() {
            if affiliations.all(|(_, other)| other.0 == text) {
                fact.text = text;
                changes.push(json!({"id":fact.id,"evidence":row["id"],"state":"explicitAffiliationCorrection"}));
                corrected_labels.push((former, corrected, row["id"].as_str().unwrap()));
            }
        }
        if matches!(fact.placement, Placement::Action | Placement::Decision) {
            if let Some((witness, values)) = cited_age_alternatives(&fact.text, &cited, evidence, 4) {
                let revised = if fact.placement == Placement::Decision {
                    fact.placement = Placement::Question;
                    fact.kind = Kind::Status;
                    fact.owner = None;
                    fact.due = None;
                    Some(age_pending_text(values))
                } else {
                    retain_age_dependency(&fact.text)
                };
                if let Some(text) = revised {
                    fact.text = text;
                    let anchor = witness["id"].as_str().unwrap();
                    if fact.evidence.len() < 8 && !fact.evidence.iter().any(|id| id == anchor) {
                        fact.evidence.push(anchor.to_owned());
                    }
                    changes.push(json!({"id":fact.id,"evidence":anchor,"state":"unresolvedAgeScope"}));
                }
            }
        }
        if unresolved_assignment_discussion(fact, &cited) {
            fact.placement = Placement::Question;
            fact.kind = Kind::Status;
            changes.push(json!({"id":fact.id,"evidence":fact.evidence,"state":"unassignedDiscussion"}));
        }
        if fact.placement == Placement::Action {
            let quotes: Vec<_> = cited.iter().filter_map(|row| row["text"].as_str()).collect();
            if let Some(text) = super::final_bindings::retain_source_timing(&fact.text, &quotes) {
                fact.text = text;
                changes.push(json!({"id":fact.id,"evidence":fact.evidence,"state":"unresolvedTimingObject"}));
            }
        }
    }
    corrected_labels.sort_unstable();
    corrected_labels.dedup();
    let mut purpose = purpose;
    if let (Some(purpose), [(former, corrected, anchor)]) = (purpose.as_deref_mut(), corrected_labels.as_slice()) {
        let unrelated = facts.iter().any(|fact| !fact.evidence.iter().any(|id| id == *anchor) && fact.text.contains(former));
        if !unrelated && purpose.matches(former).count() == 1 {
            let revised = purpose.replacen(former, corrected, 1);
            if line(&revised, 120) {
                *purpose = revised;
                changes.push(json!({"id":"purpose","evidence":anchor,"state":"explicitAffiliationCorrection"}));
            }
        }
    }
    if let Some(change) = purpose.and_then(|text| retain_opening_period(text, evidence)) {
        changes.push(change);
    }
    changes
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
                return verification_before_disposal(&fact.text, origin, evidence);
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

    fn source_fact(id: &str, text: &str, evidence: &[&str], placement: Placement) -> Fact {
        Fact {id:id.into(),text:text.into(),evidence:evidence.iter().map(|id| (*id).to_owned()).collect(),
            owner:None,due:None,kind:Kind::Status,placement}
    }

    #[test]
    fn explicit_affiliation_correction_applies_to_the_claim_and_its_overview() {
        let mut facts = [source_fact("a001","美国公司的中国分部约五十人团建。",&["e0010"],Placement::Topic)];
        let mut purpose = "讨论美国公司半月团建接待。".to_string();
        let evidence = [json!({"id":"e0010","source":"u000",
            "text":"一个美国的公司，呃它其实是一个中国公司一个美国分部，然后他们那儿有一个团建活动。"})];
        assert_eq!(retain_spoken_state(&mut facts,&evidence,Some(&mut purpose)).len(),2);
        assert_eq!(facts[0].text,"中国公司的美国分部约五十人团建。");
        assert_eq!(purpose,"讨论中国公司的美国分部半月团建接待。");
        assert!(explicit_affiliation_correction("美国公司的法国分部团建。",evidence[0]["text"].as_str().unwrap()).is_none());
        assert!(explicit_affiliation_correction("美国公司的中国分部团建。","一个美国公司的中国分部，另一个是中国公司美国分部。").is_none());
    }

    #[test]
    fn unconfirmed_age_does_not_override_dependent_work_or_a_later_clear_agreement() {
        let initial = [
            source_fact("a004","年龄段可定为18到45岁之间，跨度不用特别大。",&["e0030","e0031"],Placement::Decision),
            source_fact("a005","后续再确定18到45岁对应的色彩元素和颜色。",&["e0033","e0034"],Placement::Action),
            source_fact("elsewhere","赞助另一个项目的年龄段可定为18到45岁之间。",&["e0200"],Placement::Decision),
            source_fact("time","在方案中列出最低折扣、产品出品时间，以及各平台促销力度。",&["e0316"],Placement::Action),
        ];
        let mut facts = initial.clone();
        let mut source = vec![
            json!({"id":"e0030","source":"u001","text":"跨度不用特别大。"}),
            json!({"id":"e0031","source":"u001","text":"18~3~35岁之间大家我觉得可以啊45岁之间都可以对吧对对对"}),
            json!({"id":"e0033","source":"u001","text":"后续再定一下这个就是。"}),
            json!({"id":"e0034","source":"u001","text":"咱们到时候确定颜色。"}),
            json!({"id":"e0200","source":"u009","text":"另一个项目前面已经定了。"}),
            json!({"id":"e0316","source":"u014","text":"看那个最低能够给到几折，还有看咱们的东西出来的时间。"}),
        ];
        assert_eq!(retain_spoken_state(&mut facts,&source,None).len(),3);
        assert_eq!(facts[0].placement,Placement::Question);
        assert!(facts[0].text.contains("35岁和45岁"));
        assert_eq!(facts[1].placement,Placement::Action);
        assert!(facts[1].text.contains("颜色（年龄范围待核实）"));
        assert!(!facts[1].text.contains("45岁"));
        assert_eq!(facts[2].text,initial[2].text);
        assert!(facts[3].text.contains("「咱们的东西出来的时间」（具体对象待核实）"));
        assert!(!facts[3].text.contains("产品出品时间"));
        source.insert(4,json!({"id":"e0035","source":"u001","text":"最终确定年龄范围为18到45岁。"}));
        let mut fixed = initial;
        assert_eq!(retain_spoken_state(&mut fixed,&source,None).len(),1);
        assert_eq!(fixed[0].placement,Placement::Decision);
        assert!(fixed[1].text.contains("18到45岁"));
    }

    #[test]
    fn a_retrospective_opening_and_unassigned_discussion_keep_their_actual_roles() {
        let evidence = [
            json!({"id":"e0007","source":"u000","text":"说话人3: 今天咱们开就是就上个季度的销售情况咱们来开一场会议。"}),
            json!({"id":"e0245","source":"u018","text":"说话人1: 我们交给哪个部门儿去承担这个接待工作行吧。"}),
        ];
        let mut facts = [
            source_fact("a010","讨论接待工作由哪个部门承担，会上征询，未明确分派。",&["e0245"],Placement::Action),
            source_fact("a011","各部门下去做接待计划书并报总经理。",&["e0245"],Placement::Action),
        ];
        let mut purpose = "围绕安保、卫生与促销交流。".to_string();
        let changes = retain_spoken_state(&mut facts,&evidence,Some(&mut purpose));
        assert_eq!(changes.len(),2);
        assert_eq!(purpose,"回顾上季度销售情况。围绕安保、卫生与促销交流。");
        assert_eq!(facts[0].placement,Placement::Question);
        assert_eq!(facts[1].placement,Placement::Action);
    }

    #[test]
    fn a_reported_proposal_does_not_remain_a_second_decision() {
        let units = [super::super::Unit{id:"u004".into(),text:"这些措施属于门店安全管理。".into()}];
        let mut doc: super::super::Document=serde_json::from_value(json!({
            "purpose":"谈门店安全。","topics":[{"title":"门店安全","points":[{
                "kind":"status","text":"有巡逻安排。","sources":["u004"]
            }],"details":[]}],"decisions":[
              {"text":"会上提出加大店内巡逻，发现异常及时报警。","sources":["u004"]},
              {"text":"决定保安加大店内巡逻力度并联络警察。","sources":["u004"]}
            ],"questions":[],"actionItems":[]
        })).unwrap();
        assert_eq!(restore_reported_decision_boundary(&mut doc,&units).len(),1);
        assert_eq!(doc.decisions.len(),1);
        assert!(doc.decisions[0].text.starts_with("决定"));
        assert!(doc.topics[0].details[0].text.starts_with("会上提出"));
    }

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
    fn only_the_same_billing_period_or_its_start_satisfies_the_refund_cue() {
        let source = "只有住宿费返还了一半，交了是一年度，从上半季度开始交，交的是一学年，只把一个学期的住宿费退款。";
        let statement = "退了一学年住宿费的一半（一个学期）。";
        assert!(retained_refund_measure("一年", statement, source));
        assert!(retained_refund_measure("半季度", statement, source));
        assert!(!retained_refund_measure("半季度", statement, &format!("{source}半季度后要付下一笔。")));
        assert!(!retained_refund_measure("一年", statement, &format!("{source}一年后再退。")));
        assert!(!retained_refund_measure("一年", "退了一学年伙食费的一半（一个学期）。", source));
        assert!(!retained_refund_measure("半年", statement, source));
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
        let mut later_proposal = original.clone();
        later_proposal.text = "对超过一天的车辆要清理，须找到车主及时开走。".into();
        later_proposal.evidence.push("e0182".into());
        let verified = ["e0164".into(), "e0180".into(), "e0182".into()];
        assert!(widens_verified_disposal(&rows[0].text, &verified, &later_proposal, &evidence));
        assert!(!widens_verified_disposal(&rows[0].text, &later_proposal.evidence, &later_proposal, &evidence));
        let mut negative = later_proposal.clone();
        negative.text = "对超过一天的车辆暂不清理，须找到车主及时开走。".into();
        assert!(!widens_verified_disposal(&rows[0].text, &verified, &negative, &evidence));
        later_proposal.evidence.push("e0190".into());
        assert!(!widens_verified_disposal(&rows[0].text, &verified, &later_proposal, &evidence));
        let kept = [rows[0].text.as_str()];
        let broad = "车辆停放超过一天即须清理，不能停放半个月。";
        assert!(matches!(disposal_echo(broad, &["e0164".into()], &kept, &evidence), Some(DisposalEcho::Drop)));
        let combined = "外部人员登记须记录来意和何时走；超过一天的就要清理，而不是半个月。";
        let result = disposal_echo(combined, &["e0163".into(),"e0164".into()], &kept, &evidence).unwrap();
        let DisposalEcho::RetainSeparateClause(text, ids) = result else { panic!("registration must survive"); };
        assert_eq!(text, "外部人员登记须记录来意和何时走");
        assert_eq!(ids, ["e0163"]);
        let check_echo = "对停放超过一天的车辆必须核查，不允许超过一天。";
        assert!(matches!(disposal_echo(check_echo, &["e0180".into()], &kept, &evidence), Some(DisposalEcho::Drop)));
        assert!(disposal_echo(broad, &["e0164".into()], &[], &evidence).is_none());
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
