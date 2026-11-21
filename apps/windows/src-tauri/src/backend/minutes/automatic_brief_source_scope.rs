//! Check source-backed case context and qualifiers after grouping.
use std::{
    collections::{HashMap, HashSet},
    sync::LazyLock,
    time::Instant,
};

use serde::Deserialize;
use serde_json::{json, Value};

use super::{
    answer_layout::Placement,
    factual_audit::{self, VerifiedBrief},
    source_items::{self, MissingItem, SourceItem},
    Document, Entry, Unit,
};

const PROMPT: &str = include_str!("automatic_brief_source_scope.txt");
const FAIL: &str = "纪要的限定或案情补核缺少原话证据，已有结果保留。";

fn budget_exclusion(text: &str) -> Option<&str> {
    static EXCLUDED: LazyLock<regex::Regex> = LazyLock::new(|| {
        regex::Regex::new(
        r"(?:不在|不走|不是|并非|不计入|不从|不使用)[^，。；,;]{0,10}?(运营费|运行费|部门预算|部门经费|专项经费)"
    ).unwrap()
    });
    EXCLUDED.captures(text)?.get(1).map(|term| term.as_str())
}

fn literal_scope(quote: &str, statement: &str) -> Option<&'static str> {
    if quote.contains("报销")
        && statement.contains("报销")
        && budget_exclusion(quote).is_some_and(|account| statement.contains(account))
        && budget_exclusion(statement).is_none()
        && !statement.contains("待核实")
    {
        return Some("budgetBoundary");
    }
    static BARE_FEE: LazyLock<regex::Regex> = LazyLock::new(|| {
        regex::Regex::new(r"(?:他的|她的|它的|它这个|其)(?:这个|这项)?(?:收费|价格|费用|成本)")
            .unwrap()
    });
    if BARE_FEE.is_match(quote)
        && ["和", "或"].iter().any(|word| quote.contains(word))
        && ["收费", "价格", "费用", "成本"]
            .iter()
            .any(|word| statement.contains(word))
        && !["待核实", "待核对", "待确认"]
            .iter()
            .any(|word| statement.contains(word))
    {
        return Some("ambiguousReference");
    }
    let qualified = ["待核实", "待核对", "待确认"].iter().any(|word| statement.contains(word));
    let categorical = ["都不", "一律", "不得", "不应", "不准", "禁止"]
        .iter().any(|cue| statement.contains(cue));
    if !qualified && categorical && ["不也可以", "不也能", "不能也可以", "不可以也可以"]
        .iter().any(|cue| quote.contains(cue))
    {
        return Some("conflictingBoundary");
    }
    if ["就是强迫", "前提是强迫", "必须是强迫", "是因为违背"]
        .iter()
        .any(|word| quote.contains(word))
        && ["违法", "构成", "负责"]
            .iter()
            .any(|word| statement.contains(word))
        && !["强迫", "胁迫", "违背", "不愿", "未经同意"]
            .iter()
            .any(|word| statement.contains(word))
    {
        return Some("narrowedConclusion");
    }
    None
}

#[cfg(test)]
#[test]
fn a_conflicting_restriction_cannot_support_a_blanket_boundary() {
    let quote = "顾客不能进来了，工作人员也工作人员不也可以进来";
    assert_eq!(literal_scope(quote, "顾客和工作人员都不应进。"), Some("conflictingBoundary"));
    assert_eq!(literal_scope(quote, "顾客不能进入，工作人员能否进入待核实。"), None);
    assert_eq!(literal_scope("顾客不能进，工作人员也不能进。", "顾客和工作人员都不应进。"), None);
}

fn source_scope(verified: &VerifiedBrief, doc: &Document, source: &[Value]) -> Vec<Value> {
    let positions: HashMap<_, _> = source
        .iter()
        .enumerate()
        .map(|(i, row)| (row["id"].as_str().unwrap(), i))
        .collect();
    let original = factual_audit::claims(&verified.document);
    let current = factual_audit::claims(doc);
    let mut checks = Vec::new();
    for claim in &current {
        if !claim["path"].as_str().unwrap().starts_with("topics[") || claim.get("sources").is_none()
        {
            continue;
        }
        let prior = original.iter().find(|item| {
            ["text", "sources", "owner", "due", "kind"]
                .iter()
                .all(|key| item[*key] == claim[*key])
        });
        let Some(ids) =
            prior.and_then(|item| verified.evidence.get(item["path"].as_str().unwrap()))
        else {
            continue;
        };
        let Some((anchor, kind)) = ids
            .iter()
            .filter_map(|id| {
                let index = *positions.get(id.as_str())?;
                literal_scope(
                    source[index]["text"].as_str().unwrap(),
                    claim["text"].as_str().unwrap(),
                )
                .map(|kind| (index, kind))
            })
            .next()
        else {
            continue;
        };
        checks.push(packet(source, anchor, kind, vec![anchor], Some(claim)));
    }
    let cited: HashSet<_> = original
        .iter()
        .filter(|claim| claim.get("sources").is_some())
        .filter_map(|claim| verified.evidence.get(claim["path"].as_str().unwrap()))
        .flatten()
        .map(String::as_str)
        .collect();
    for (index, row) in source.iter().enumerate() {
        let text = row["text"].as_str().unwrap();
        if cited.contains(row["id"].as_str().unwrap()) {
            continue;
        }
        let Some((speaker, content)) = super::super::source_resolution::split_turn_label(text)
        else {
            continue;
        };
        if (content.contains("我在") && content.contains("看过"))
            && ["为了", "避让", "撞", "摔", "抢救"]
                .iter()
                .any(|word| content.contains(word))
        {
            let continuation = source
                .iter()
                .enumerate()
                .skip(index + 1)
                .take(3)
                .find(|(_, next)| {
                    super::super::source_resolution::split_turn_label(
                        next["text"].as_str().unwrap(),
                    )
                    .is_some_and(|(who, text)| {
                        who == speaker
                            && ["这个时候", "随后", "然后"]
                                .iter()
                                .any(|term| text.contains(term))
                    })
                })
                .map(|(index, _)| index);
            if let Some(next) = continuation {
                checks.push(packet(
                    source,
                    index,
                    "caseNarrative",
                    vec![index, next],
                    None,
                ));
            }
        } else if content.contains("追究")
            && ["没有结果", "没有证据", "联系不上", "原因还没查清"]
                .iter()
                .any(|word| content.contains(word))
        {
            checks.push(packet(
                source,
                index,
                "caseApplicability",
                vec![index],
                None,
            ));
        }
    }
    for answer in hypothetical_answer_checks(verified, doc, source, &positions, &current) {
        if !checks.iter().any(|check| check["claim"]["path"] == answer["claim"]["path"]) {
            checks.push(answer);
        }
    }
    for (index, check) in checks.iter_mut().enumerate() {
        check["id"] = json!(format!("s{index:03}"));
    }
    checks
}

fn hypothetical_answer_checks(
    verified: &VerifiedBrief,
    doc: &Document,
    source: &[Value],
    positions: &HashMap<&str, usize>,
    claims: &[Value],
) -> Vec<Value> {
    let labeled = super::commitments::with_turn_labels(source);
    let mut checks = Vec::new();
    for (index, row) in source.iter().enumerate() {
        let raw = row["text"].as_str().unwrap();
        let Some(setup) = super::source_coverage::independent_source_facets(raw).into_iter()
            .find(|facet| facet.label == "设例") else { continue; };
        let scenario = packet(source, index, "sourceScenario", vec![index], None);
        let Some(title) = verified_topic(verified, doc, &scenario, source) else { continue; };
        let Some(topic) = verified.document.topics.iter().position(|topic| topic.title == title) else { continue; };
        let prefix = format!("topics[{topic}].points[");
        for claim in claims.iter().filter(|claim| {
            claim["kind"] == "status" && claim["path"].as_str().is_some_and(|path| path.starts_with(&prefix))
                && claim["text"].as_str().is_some_and(|text| {
                    ["法律要求", "法律规定", "法规规定", "依法必须"].iter().any(|head| text.starts_with(head))
                })
        }) {
            let path = claim["path"].as_str().unwrap();
            let Some(point) = path.strip_prefix(&prefix).and_then(|value| value.trim_end_matches(']').parse::<usize>().ok())
                .and_then(|point| verified.document.topics[topic].points.get(point))
            else { continue; };
            if claim["text"] != point.text || claim["sources"] != json!(point.sources)
                || checks.iter().any(|check: &Value| check["claim"]["path"] == path)
            {
                continue;
            }
            let Some(accepted) = verified.evidence.get(path) else { continue; };
            if accepted.is_empty() || accepted.len() > 7 { continue; }
            let Some(offsets) = accepted.iter().map(|id| positions.get(id.as_str()).copied()).collect::<Option<Vec<_>>>()
            else { continue; };
            if offsets.iter().any(|offset| *offset <= index || *offset > index + 36 || source[*offset]["source"] != row["source"]) {
                continue;
            }
            let speakers: HashSet<_> = offsets.iter().filter_map(|offset| {
                let quoted = &labeled[*offset];
                let raw = quoted["text"].as_str()?;
                let (_, body) = super::super::source_resolution::split_turn_label(raw).unwrap_or(("", raw));
                (body.trim().chars().count() > 5).then(|| quoted["turnSpeaker"].as_str()).flatten()
            }).collect();
            if speakers.is_empty() { continue; }
            let mut names: Vec<_> = speakers.into_iter().collect();
            names.sort_unstable();
            let mut required = vec![index];
            required.extend(offsets);
            let mut check = packet(source, index, "hypotheticalAnswer", required.clone(), Some(claim));
            let mut nearby: Vec<_> = required.iter().flat_map(|offset| {
                offset.saturating_sub(1)..(*offset + 2).min(source.len())
            }).collect();
            nearby.sort_unstable();
            nearby.dedup();
            check["context"] = json!(nearby.into_iter().map(|offset| &source[offset]["id"]).collect::<Vec<_>>());
            check["scenarioQuote"] = json!(setup.quote);
            check["requiredSpeakers"] = json!(names);
            check["instruction"] = json!("把原文设例与答复写在同一条观点中。用“在这一设例中”或“在这个假设中”限定适用场景。明确标出requiredSpeakers中每位说话人的编号及各自作出的具体判断；有人只是赞同另一人的说法时，保留赞同与首提的区别。不要代会议确认普遍法条或定罪，保留已经审核的关系、判断和分歧。使用opinion，证据包括全部requiredEvidence。");
            checks.push(check);
        }
    }
    checks
}

fn packet(
    source: &[Value],
    anchor: usize,
    kind: &str,
    required: Vec<usize>,
    claim: Option<&Value>,
) -> Value {
    let context = &source[anchor.saturating_sub(2)..(anchor + 6).min(source.len())];
    let mut check = json!({"kind":kind,"requiredEvidence":required.into_iter().map(|index| &source[index]["id"]).collect::<Vec<_>>(),
           "context":context.iter().map(|row| &row["id"]).collect::<Vec<_>>(),"claim":claim});
    if kind == "budgetBoundary" {
        check["instruction"] = json!("分开写谁报销和哪项经费被排除。原话明确报销方但后半句口齿含混时，保留会上提出的报销方，将经费归属列为待核实。不可把报销写成已批准，也不可把否定的经费连到报销方。");
    }
    if kind == "conflictingBoundary" {
        check["instruction"] = json!("发言中存在允许和不允许的含混或自我更正。分别保留各主体可从原话确认的限制，听不清或有冲突的主体单独写待核实。引用相邻发言支持已确认部分，不把不同主体合并成一律禁止或一律允许。");
    }
    check
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Response {
    scope_checks: Vec<ScopedItem>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ScopedItem {
    id: String,
    item: SourceItem,
    topic: Option<String>,
}

fn has_condition(text: &str) -> bool {
    ["强迫", "胁迫", "违背", "不愿"]
        .iter()
        .any(|term| text.contains(term))
}

fn preserve_unfinished_contact(item: &mut SourceItem, check: &Value, source: &[Value]) {
    static UNFINISHED: LazyLock<regex::Regex> = LazyLock::new(|| {
        regex::Regex::new(r"联系不上[，,、\s]*(?:当时)?[\s]*(?:那个|这个)?[，,。\s]*$").unwrap()
    });
    static CONTACT: LazyLock<regex::Regex> =
        LazyLock::new(|| regex::Regex::new(r"联系不上[^，,。；;！？\s]{1,16}").unwrap());
    if check["kind"] != "caseApplicability" || !CONTACT.is_match(&item.text) {
        return;
    }
    let mut mentions = source.iter().filter(|row| {
        row["text"]
            .as_str()
            .is_some_and(|text| text.contains("联系不上"))
            && check["context"].as_array().unwrap().contains(&row["id"])
    });
    let Some(original) = mentions.next() else {
        return;
    };
    if mentions.next().is_some() || !UNFINISHED.is_match(original["text"].as_str().unwrap()) {
        return;
    }
    let id = original["id"].as_str().unwrap();
    if !item.evidence.iter().any(|evidence| evidence == id) {
        item.evidence.push(id.to_owned());
    }
    item.text = CONTACT
        .replacen(&item.text, 1, "联系不上，具体联系对象待核实")
        .into_owned();
}

fn missing_conditions(raw: &str, checks: &[Value]) -> Option<(Value, Vec<Value>)> {
    let response: Value = serde_json::from_str(super::super::strip_code_fences(raw).trim()).ok()?;
    let replies = response["scopeChecks"].as_array()?;
    let mut seen = HashSet::new();
    let mut missing = Vec::new();
    if replies.len() != checks.len() {
        return None;
    }
    for row in replies {
        let id = row["id"].as_str()?;
        let check = checks.iter().find(|check| check["id"] == id)?;
        if !seen.insert(id) {
            return None;
        }
        if check["kind"] == "narrowedConclusion" && !has_condition(row["item"]["text"].as_str()?) {
            missing.push(check.clone());
        }
    }
    (!missing.is_empty()).then_some((response, missing))
}

fn verified_topic(
    verified: &VerifiedBrief,
    doc: &Document,
    check: &Value,
    source: &[Value],
) -> Option<String> {
    let order: HashMap<_, _> = source
        .iter()
        .enumerate()
        .filter_map(|(index, row)| row["id"].as_str().map(|id| (id, index)))
        .collect();
    let anchors: Vec<_> = check["requiredEvidence"]
        .as_array()?
        .iter()
        .filter_map(|id| order.get(id.as_str()?).copied())
        .collect();
    let last = anchors.iter().copied().max()?;
    let mut ranked: Vec<_> = verified
        .document
        .topics
        .iter()
        .enumerate()
        .filter_map(|(index, topic)| {
            let current = doc
                .topics
                .iter()
                .find(|current| current.title == topic.title)?;
            if current.details.len() >= source_items::DETAILS_LIMIT {
                return None;
            }
            let prefix = format!("topics[{index}].");
            let score = verified
                .evidence
                .iter()
                .filter(|(path, _)| path.starts_with(&prefix))
                .flat_map(|(_, ids)| ids)
                .filter_map(|id| order.get(id.as_str()))
                .flat_map(|position| {
                    anchors.iter().map(move |anchor| {
                        // A reported case can be followed by the first named discussion.
                        let backwards = check["kind"] == "caseNarrative" && *position < last;
                        let outside_scenario = check["kind"] == "sourceScenario"
                            && (*position < *anchor || source[*position]["source"] != source[*anchor]["source"]);
                        (outside_scenario, position.abs_diff(*anchor), backwards)
                    })
                })
                .min()?;
            Some((score, &current.title))
        })
        .collect();
    ranked.sort();
    let (best, title) = ranked.first()?;
    (!ranked.get(1).is_some_and(|candidate| candidate.0 == *best)).then(|| (*title).clone())
}

fn previous_case_answer(
    doc: &Document,
    verified: &VerifiedBrief,
    check: &Value,
    text: &str,
    evidence: &[String],
) -> Option<String> {
    if check["kind"] != "caseApplicability" || !text.contains("追究") {
        return None;
    }
    let previous = factual_audit::claims(&verified.document);
    let mut candidates = factual_audit::claims(doc).into_iter().filter_map(|claim| {
        let path = claim["path"].as_str()?;
        let approved = verified.evidence.get(path)?;
        (path.starts_with("topics[")
            && claim.get("sources").is_some()
            && claim["text"].as_str()?.contains("追究")
            && !approved.is_empty()
            && approved.iter().all(|id| evidence.contains(id))
            && previous.contains(&claim))
        .then(|| path.to_owned())
    });
    let path = candidates.next()?;
    candidates.next().is_none().then_some(path)
}

fn apply_scope(
    mut doc: Document,
    raw: &str,
    checks: &[Value],
    units: &[Unit],
    source: &[Value],
    verified: &VerifiedBrief,
) -> Result<Document, String> {
    let fail = || FAIL.to_owned();
    let response: Response =
        serde_json::from_str(super::super::strip_code_fences(raw).trim()).map_err(|_| fail())?;
    let mut pending: HashMap<_, _> = checks
        .iter()
        .map(|row| (row["id"].as_str().unwrap(), row))
        .collect();
    let known: HashMap<_, _> = source
        .iter()
        .map(|row| (row["id"].as_str().unwrap(), row))
        .collect();
    let ids = known.keys().copied().collect();
    let mut replacements = Vec::new();
    let mut additions = Vec::new();
    for mut reply in response.scope_checks {
        let check = pending.remove(reply.id.as_str()).ok_or_else(fail)?;
        preserve_unfinished_contact(&mut reply.item, check, source);
        let fact = reply.item.clone().bind(&known, &ids)?;
        if fact.placement != Placement::Topic
            || fact.evidence.iter().any(|id| {
                !check["context"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .any(|candidate| candidate == id.as_str())
            })
            || check["requiredEvidence"]
                .as_array()
                .unwrap()
                .iter()
                .any(|id| !fact.evidence.iter().any(|evidence| id == evidence.as_str()))
        {
            return Err(fail());
        }
        if matches!(check["kind"].as_str(), Some("ambiguousReference" | "conflictingBoundary"))
            && !fact.text.contains("待核实")
        {
            return Err(fail());
        }
        if check["kind"] == "budgetBoundary"
            && !(fact.text.contains("报销")
                && (fact.text.contains("待核实")
                    || budget_exclusion(&fact.text).is_some()
                    || check["requiredEvidence"]
                        .as_array()
                        .unwrap()
                        .iter()
                        .filter_map(Value::as_str)
                        .all(|id| {
                            budget_exclusion(known[id]["text"].as_str().unwrap())
                                .is_some_and(|name| !fact.text.contains(name))
                        })))
        {
            return Err(fail());
        }
        if check["kind"] == "narrowedConclusion" && !has_condition(&fact.text) {
            return Err(fail());
        }
        let hypothetical_answer = check["kind"] == "hypotheticalAnswer";
        if hypothetical_answer && (!matches!(fact.kind, super::Kind::Opinion)
            || !["设例", "假设", "例子"].iter().any(|cue| fact.text.contains(cue))
            || check["requiredSpeakers"].as_array().into_iter().flatten().filter_map(Value::as_str)
                .any(|speaker| !fact.text.contains(speaker)))
        {
            return Err(fail());
        }
        let path = check["claim"]["path"]
            .as_str()
            .map(str::to_owned)
            .or_else(|| previous_case_answer(&doc, verified, check, &fact.text, &fact.evidence));
        if let Some(path) = path {
            let mut seen = HashSet::new();
            let sources = fact
                .evidence
                .iter()
                .map(|id| known[id.as_str()]["source"].as_str().unwrap())
                .filter(|id| seen.insert(*id))
                .map(str::to_owned)
                .collect();
            replacements.push((
                path,
                Entry {
                    text: fact.text,
                    sources,
                    quantity_needs_review: false,
                },
                hypothetical_answer,
            ));
        } else {
            additions.push(MissingItem {
                item: reply.item,
                topic: verified_topic(verified, &doc, check, source).or(reply.topic),
                new_aspect: None,
            });
        }
    }
    if !pending.is_empty() {
        return Err(fail());
    }
    if !replacements.is_empty() {
        let mut value = serde_json::to_value(doc).map_err(|_| fail())?;
        for (path, entry, hypothetical_answer) in replacements {
            let pointer = format!(
                "/{}",
                path.replace('[', "/").replace(']', "").replace('.', "/")
            );
            let target = value.pointer_mut(&pointer).ok_or_else(fail)?;
            target["text"] = json!(entry.text);
            target["sources"] = json!(entry.sources);
            if hypothetical_answer {
                target["kind"] = json!(super::Kind::Opinion);
            }
        }
        doc = serde_json::from_value(value).map_err(|_| fail())?;
    }
    source_items::append_missing(additions, doc, units, source)
}

fn restore_source_facets(
    doc: Document, verified: &VerifiedBrief, units: &[Unit], source: &[Value], trace: &mut Vec<Value>,
) -> Result<Document, String> {
    let claims = factual_audit::claims(&doc);
    let count = claims.iter().filter(|claim| claim.get("sources").is_some()).count();
    let budget = super::SOURCE_ITEMS_FACT_LIMIT.saturating_sub(count).min(7);
    if budget == 0 { return Ok(doc); }
    let mut added = Vec::new();
    let mut seen = HashSet::new();
    for (index, row) in source.iter().enumerate() {
        let Some(source_text) = row["text"].as_str() else { continue; };
        let Some((speaker, _)) = super::super::source_resolution::split_turn_label(source_text) else { continue; };
        let mut facets: Vec<_> = super::source_coverage::independent_source_facets(source_text)
            .into_iter().map(|facet| (facet, None)).collect();
        if let Some((responder, reply)) = source.get(index + 1).and_then(|other| other["text"].as_str())
            .and_then(super::super::source_resolution::split_turn_label)
            .filter(|(responder, _)| *responder != speaker)
        {
            if let Some((facet, response)) = super::source_coverage::answered_hypothesis(source_text, reply) {
                facets.push((facet, Some((responder, response))));
            }
        }
        for (facet, answer) in facets {
            let related = |claim: &&Value| claim["sources"].as_array()
                .is_some_and(|ids| ids.contains(&row["source"]));
            if claims.iter().filter(related).any(|claim| claim["text"].as_str()
                .is_some_and(|text| facet.represented_by(text)))
            {
                continue;
            }
            let mut references = vec![index];
            let attribution = match answer {
                Some((responder, response)) => {
                    references.push(index + 1);
                    format!("{speaker}举例「{}」。{responder}回应「{response}」。", facet.quote)
                }
                None if facet.label == "设例" => format!("{speaker}举例提问「{}」。", facet.quote),
                None if facet.label == "分开讨论的情形" => format!("{speaker}区分了不同情形，其中提到「{}」。", facet.quote),
                None => format!("{speaker}在讨论{}时提到「{}」。", facet.label, facet.quote),
            };
            let kind = if facet.label == "设例" && references.len() == 1 { "sourceScenario" } else { "sourceFacet" };
            let measure = packet(source, index, kind, references.clone(), None);
            let Some(topic) = verified_topic(verified, &doc, &measure, source) else { continue; };
            let room = doc.topics.iter().find(|entry| entry.title == topic)
                .map(|entry| source_items::DETAILS_LIMIT.saturating_sub(entry.details.len())).unwrap_or(0);
            if added.iter().filter(|entry: &&MissingItem| entry.topic.as_deref() == Some(topic.as_str())).count() >= room
                || !super::line(&attribution, 90) || !seen.insert(super::normalized(facet.quote))
            {
                continue;
            }
            added.push(MissingItem {
                item: SourceItem::attributed_opinion(attribution, references.into_iter()
                    .map(|offset| source[offset]["id"].as_str().unwrap().to_owned()).collect()),
                topic: Some(topic), new_aspect: None,
            });
            if added.len() == budget { break; }
        }
        if added.len() == budget { break; }
    }
    if added.is_empty() { return Ok(doc); }
    trace.push(json!({"stage":"source-independent-clause-recovery","additions":added.iter()
        .map(|entry| json!({"text":entry.item.text,"evidence":entry.item.evidence,"topic":entry.topic}))
        .collect::<Vec<_>>()}));
    source_items::append_missing(added, doc, units, source)
}

#[cfg(test)]
#[test]
fn a_source_clause_survives_a_different_claim_with_the_same_reference() {
    let units = vec![Unit { id:"u000".into(),
        text:"说话人2: 待讨论的验收标准是以送审清单为准，现场只是初筛。".into() }];
    let doc: Document = serde_json::from_value(json!({"purpose":"讨论验收",
        "topics":[{"title":"验收流程","points":[{"kind":"status","text":"现场只是初筛。","sources":["u000"]}],"details":[]}],
        "decisions":[],"questions":[],"actionItems":[]})).unwrap();
    let source = factual_audit::evidence_sentences(&units);
    assert!(source[0].get("turnSpeaker").is_none());
    let verified = VerifiedBrief{document:doc.clone(),evidence:HashMap::from([
        ("topics[0].points[0]".into(),vec!["e0000".into()])]),pending_quotes:Vec::new()};
    let mut trace = Vec::new();
    let repaired = restore_source_facets(doc,&verified,&units,&source,&mut trace).unwrap();
    assert_eq!(repaired.topics[0].points[0].text,"现场只是初筛。");
    let detail = &repaired.topics[0].details[0];
    assert_eq!(detail.sources, ["u000"]);
    assert!(detail.text.contains("说话人2"));
    assert!(detail.text.contains("以送审清单为准"));
    let repeated = restore_source_facets(repaired,&verified,&units,&source,&mut trace).unwrap();
    assert_eq!(repeated.topics[0].details.len(),1);
}

#[cfg(test)]
#[test]
fn a_setup_goes_with_the_following_explanation_in_its_own_source_unit() {
    let units = vec![Unit { id:"u000".into(),text:"说话人3: 先确认器材。".into() },
        Unit { id:"u001".into(),text:"说话人2: 举个例子，两份资料都丢了，你是先找原件还是先问负责人？暂且看看讨论。稍后说一下回答。".into() }];
    let doc: Document = serde_json::from_value(json!({"purpose":"确认流程", "topics":[
        {"title":"器材","points":[{"kind":"status","text":"先确认器材。","sources":["u000"]}],"details":[]},
        {"title":"找回资料","points":[{"kind":"status","text":"之后会讨论回答。","sources":["u001"]}],"details":[]}],
        "decisions":[],"actionItems":[],"questions":[]})).unwrap();
    let source = factual_audit::evidence_sentences(&units);
    let verified = VerifiedBrief{document:doc.clone(),evidence:HashMap::from([
        ("topics[0].points[0]".into(),vec!["e0000".into()]),
        ("topics[1].points[0]".into(),vec!["e0003".into()])]),pending_quotes:Vec::new()};
    let repaired = restore_source_facets(doc,&verified,&units,&source,&mut Vec::new()).unwrap();
    assert!(repaired.topics[0].details.is_empty());
    assert!(repaired.topics[1].details[0].text.contains("两份资料都丢了"));
}

#[cfg(test)]
#[test]
fn a_hypothetical_answer_requires_attribution_to_the_actual_responders() {
    let units = vec![Unit{id:"u000".into(),text:concat!(
        "说话人2: 举个例子，两台仪器都损坏了，你是先修甲机还是先换乙机？
",
        "说话人2: 这个情况下只修甲机，乙机没有必要换。
",
        "说话人1: 也许还要检查同一批仪器。"
    ).into()}];
    let doc: Document = serde_json::from_value(json!({"purpose":"交流设备处置",
        "topics":[{"title":"维修问答","points":[
            {"kind":"status","text":"法规规定应先修甲机，可继续检查同批仪器。","sources":["u000"]},
            {"kind":"status","text":"周五完成例行巡检。","sources":["u000"]}
        ],"details":[]}],"decisions":[],"questions":[],"actionItems":[]})).unwrap();
    let verified = VerifiedBrief{document:doc.clone(),evidence:HashMap::from([
        ("topics[0].points[0]".into(),vec!["e0001".into(),"e0002".into()])
    ]),pending_quotes:Vec::new()};
    let source = factual_audit::evidence_sentences(&units);
    let checks = source_scope(&verified,&doc,&source);
    assert_eq!(checks.len(),1);
    assert_eq!(checks[0]["requiredSpeakers"],json!(["说话人1","说话人2"]));
    assert_eq!(checks[0]["requiredEvidence"],json!(["e0000","e0001","e0002"]));
    let mut reply = json!({"scopeChecks":[{"id":"s000","topic":null,
        "item":{"role":"opinion","text":"在这一设例中，说话人2主张先修甲机，说话人1认为也许还需判断同批仪器。",
            "evidence":["e0000","e0001","e0002"],"owner":null,"due":null}}]});
    let result = apply_scope(doc.clone(),&reply.to_string(),&checks,&units,&source,&verified).unwrap();
    assert!(matches!(result.topics[0].points[0].kind,super::Kind::Opinion));
    assert_eq!(result.topics[0].points[1].text,"周五完成例行巡检。");
    reply["scopeChecks"][0]["item"]["text"] = json!("在这一设例中，说话人2主张先修甲机并检查同批仪器。");
    assert!(apply_scope(doc,&reply.to_string(),&checks,&units,&source,&verified).is_err());
}

pub(super) fn review(
    endpoint: &str,
    model: &str,
    key: &str,
    client: &reqwest::blocking::Client,
    verified: &VerifiedBrief,
    doc: Document,
    units: &[Unit],
    start: Instant,
    trace: &mut Vec<Value>,
) -> Result<Document, String> {
    let source = factual_audit::evidence_sentences(units);
    let checks = source_scope(verified, &doc, &source);
    let doc = if checks.is_empty() {
        doc
    } else {
        let needed: HashSet<_> = checks
            .iter()
            .filter_map(|row| row["context"].as_array())
            .flatten()
            .filter_map(Value::as_str)
            .collect();
        let context: Vec<_> = source
            .iter()
            .filter(|row| needed.contains(row["id"].as_str().unwrap()))
            .collect();
        let mut raw = super::request(
            endpoint,
            model,
            key,
            client,
            PROMPT,
            json!({"scopeChecks":checks,"sourceSentences":context}),
            false,
            start,
            trace,
            "source-scope-review",
        )?;
        if let Some((mut original, missing)) = missing_conditions(&raw, &checks) {
            let ids: HashSet<_> = missing
                .iter()
                .flat_map(|row| row["requiredEvidence"].as_array().unwrap())
                .filter_map(Value::as_str)
                .collect();
            let excerpts: Vec<_> = source
                .iter()
                .filter(|row| ids.contains(row["id"].as_str().unwrap()))
                .collect();
            let corrected = super::request(
                endpoint,
                model,
                key,
                client,
                PROMPT,
                json!({"scopeChecks":missing, "sourceSentences":excerpts,
                    "scopeRecovery": "上次遗漏了断言的必要条件。只返回这些 id。以 requiredEvidence 中强迫、胁迫、违背或不愿的原话为条件，并标为该发言人的意见。删去不带条件的结论及其他话题，只引用 requiredEvidence。"}),
                false,
                start,
                trace,
                "source-scope-condition-repair",
            )?;
            let failure = || FAIL.to_owned();
            let replacement: Value =
                serde_json::from_str(super::super::strip_code_fences(&corrected).trim())
                    .map_err(|_| failure())?;
            let replacements = replacement["scopeChecks"].as_array().ok_or_else(failure)?;
            if replacements.len() != missing.len() {
                return Err(failure());
            }
            let replies = original["scopeChecks"].as_array_mut().ok_or_else(failure)?;
            for check in &missing {
                let replacement = replacements
                    .iter()
                    .find(|row| row["id"] == check["id"])
                    .ok_or_else(failure)?;
                let required = check["requiredEvidence"].as_array().unwrap();
                if !replacement["item"]["evidence"]
                    .as_array()
                    .is_some_and(|evidence| evidence.iter().all(|id| required.contains(id)))
                {
                    return Err(failure());
                }
                let reply = replies
                    .iter_mut()
                    .find(|row| row["id"] == check["id"])
                    .ok_or_else(failure)?;
                *reply = replacement.clone();
            }
            raw = original.to_string();
        }
        apply_scope(doc, &raw, &checks, units, &source, verified)?
    };
    let doc = restore_source_facets(doc, verified, units, &source, trace)?;
    factual_audit::review_and_repair_since(
        endpoint,
        model,
        key,
        client,
        &doc,
        units,
        Some(&verified.document),
        start,
        trace,
    )
}

#[cfg(test)]
#[test]
#[ignore = "local paired replay of complete public minutes"]
fn review_from_verified_public_scope() {
    let setting = |name| std::env::var(name).expect(name);
    assert!(source_items::enabled());
    assert_eq!(setting("DEEPSEEK_API_KEY"), "qm06-unified-relay");
    assert!(setting("DEEPSEEK_BASE_URL").starts_with("http://127.0.0.1:"));
    let fixture: Value =
        serde_json::from_slice(&std::fs::read(setting("QM06_INPUT")).unwrap()).unwrap();
    let units = super::source_units(fixture["text"].as_str().unwrap());
    let verified = VerifiedBrief {
        document: serde_json::from_value(fixture["document"].clone()).unwrap(),
        evidence: serde_json::from_value(fixture["priorEvidence"].clone()).unwrap(),
        pending_quotes: Vec::new(),
    };
    super::validate(&verified.document, &units).unwrap();
    let candidate = fixture.get("candidate").map_or_else(
        || verified.document.clone(),
        |value| serde_json::from_value(value.clone()).unwrap(),
    );
    super::validate(&candidate, &units).unwrap();
    let client = reqwest::blocking::Client::builder()
        .no_proxy()
        .build()
        .unwrap();
    let mut trace = Vec::new();
    let start = Instant::now();
    let output = review(
        &setting("DEEPSEEK_BASE_URL"),
        &setting("DEEPSEEK_MODEL"),
        &setting("DEEPSEEK_API_KEY"),
        &client,
        &verified,
        candidate,
        &units,
        start,
        &mut trace,
    );
    std::fs::write(
        setting("QM06_RESULT"),
        serde_json::to_vec_pretty(&json!({
            "accepted":output.is_ok(),"document":output.as_ref().ok(),"error":output.as_ref().err(),
            "calls":trace,"seconds":start.elapsed().as_secs_f64()
        }))
        .unwrap(),
    )
    .unwrap();
}
