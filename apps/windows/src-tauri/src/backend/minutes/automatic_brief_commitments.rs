//! Recheck commitments and execution details against the cited turns before delivery.
use std::{collections::{HashMap, HashSet}, sync::LazyLock, time::Instant};

use serde::Deserialize;
use serde_json::{Value, json};

use super::{Action, Document, Entry, Kind, Unit, answer_layout::{Fact, Placement}, factual_audit, source_items};

const PROMPT: &str = include_str!("automatic_brief_commitments.txt");
const STANCE_PROMPT: &str = include_str!("automatic_brief_commitment_stance.txt");
const EXECUTION_PROMPT: &str = include_str!("automatic_brief_execution_scope.txt");
const INCOMPLETE: &str = "纪要定向核对没有返回完整证据，已有结果保留。";

pub(super) fn with_turn_labels(source: &[Value]) -> Vec<Value> {
    let mut label = None;
    let mut beginning_of_line = true;
    source.iter().map(|row| {
        let text = row["text"].as_str().unwrap();
        if beginning_of_line {
            label = super::super::source_resolution::split_turn_label(text)
                .filter(|(speaker, _)| speaker.chars().any(char::is_alphabetic))
                .map(|(speaker, _)| (speaker, &row["id"]));
        }
        beginning_of_line = text.ends_with('\n');
        let mut labelled = row.clone();
        if let Some((speaker, evidence)) = label {
            labelled["turnSpeaker"] = json!(speaker);
            labelled["speakerEvidence"] = evidence.clone();
        }
        labelled
    }).collect()
}

fn source_signals(quote: &str) -> Vec<&'static str> {
    static ASSIGNMENT: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:到时候|会后|下去以后|散会后|你们?|得|要).{0,38}(?:具体.{0,6}计划|计划.{0,5}(?:写|充分)|写.{0,10}(?:计划|方案)|主抓|交给|提交)"
    ).unwrap());
    static TIME: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:接下来|未来|打算|计划|准备).{0,24}(?:半年|[一二两三四五六七八九十0-9]{1,4}(?:年|个?月))"
    ).unwrap());
    let optional = ["可以采用", "也可以", "我觉得可以", "我建议", "还可考虑"];
    [
        ("交办与承接者", ASSIGNMENT.is_match(quote)),
        ("时间是谁提出的", TIME.is_match(quote)),
        ("可选方案及其条件", optional.iter().any(|cue| quote.contains(cue))),
    ].into_iter().filter_map(|(name, matched)| matched.then_some(name)).collect()
}

fn candidates(doc: &factual_audit::VerifiedBrief, source: &[Value]) -> Vec<Value> {
    let positions: HashMap<_, _> = source.iter().enumerate()
        .map(|(index, row)| (row["id"].as_str().unwrap(), index)).collect();
    let bindings = super::source_bindings::SourceBindings::new(source);
    let mut candidates = Vec::new();
    for claim in factual_audit::claims(&doc.document) {
        let path = claim["path"].as_str().unwrap();
        if claim.get("sources").is_none() || path.starts_with("questions[") { continue; }
        let Some(ids) = doc.evidence.get(path) else { continue; };
        // A checked clause naming its own team cannot be replaced with the
        // addressee of the other clause in the same turn.
        if path.starts_with("actionItems[") && bindings.is_separate_assignment(&claim, ids) {
            continue;
        }
        let signals: Vec<_> = ids.iter().filter_map(|id| {
            let index = *positions.get(id.as_str())?;
            let checks = source_signals(source[index]["text"].as_str().unwrap());
            (!checks.is_empty()).then(|| json!({"evidence":id,"checks":checks}))
        }).collect();
        let required = path.starts_with("actionItems[") || path.starts_with("decisions[");
        let text = claim["text"].as_str().unwrap();
        let stated_possibility = ["建议", "拟", "考虑", "可以", "提议", "设想", "备选", "待核实"]
            .iter().any(|term| text.contains(term));
        let has_material_signal = signals.iter().any(|signal| {
            signal["checks"].as_array().unwrap().iter().any(|check| check != "可选方案及其条件" || !stated_possibility)
        });
        if !required && !has_material_signal { continue; }
        let mut context = Vec::new();
        for index in ids.iter().filter_map(|id| positions.get(id.as_str())) {
            // Keep both sides of the turn boundary. The surrounding turn can
            // identify an addressee, but it is never on its own an assignment.
            context.extend(index.saturating_sub(6)..(*index + 4).min(source.len()));
        }
        let turn_starts: Vec<_> = context.iter().filter_map(|index| source[*index]["speakerEvidence"].as_str())
            .filter_map(|id| positions.get(id).copied()).collect();
        context.extend(turn_starts);
        context.sort_unstable();
        context.dedup();
        let context: Vec<_> = context.into_iter().map(|index| &source[index]["id"]).collect();
        candidates.push(json!({"id":path,"claim":claim,"basis":ids,"context":context,"sourceSignals":signals}));
    }
    candidates
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Response {
    #[serde(default, rename = "type")]
    _format: super::ResponseFormatMarker,
    #[serde(rename = "roleChecks")]
    role_checks: Vec<Value>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Check {
    #[serde(rename = "id")]
    _id: String,
    replacement: Option<source_items::SourceItem>,
    clarification: Option<Clarification>,
    #[serde(rename = "ownerEvidence")]
    owner_evidence: Option<String>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Clarification {
    evidence: String,
    quote: String,
}

fn spoken_department<'a>(requested: &str, snippets: impl Iterator<Item = &'a str> + Clone) -> Option<String> {
    let stem = requested.strip_suffix("部门").or_else(|| requested.strip_suffix('部'))?;
    if !(2..=18).contains(&stem.chars().count()) || !stem.chars().all(|c| ('\u{3400}'..='\u{9fff}').contains(&c)) {
        return None;
    }
    ["的部门", "这边"].into_iter().map(|ending| format!("{stem}{ending}"))
        .find(|form| snippets.clone().any(|text| super::normalized(text).contains(form)))
}

fn spoken_collective(requested: &str, quote: &str) -> Option<String> {
    if requested == "各园" && quote.contains("各院") {
        return Some("各院".to_owned());
    }
    let group = requested.strip_prefix('各')?;
    if !(2..=14).contains(&group.chars().count()) || !group.chars().all(|ch| ('㐀'..='鿿').contains(&ch)) {
        return None;
    }
    ["每个", "每一个", "每位", "每一位"].into_iter().map(|prefix| format!("{prefix}{group}"))
        .find(|utterance| quote.contains(utterance))
}

pub(super) fn owner_as_spoken(requested: &str, row: &Value) -> Option<String> {
    let quote = row["text"].as_str()?;
    if super::normalized(quote).contains(&super::normalized(requested)) {
        return Some(requested.to_owned());
    }
    if let Some(literal) = spoken_collective(requested, quote)
        .or_else(|| spoken_department(requested, std::iter::once(quote))) {
        return Some(literal);
    }
    let group = requested.strip_suffix("园长")?;
    if group.is_empty() || !quote.contains(group) || !["我会", "我来"].iter().any(|phrase| quote.contains(phrase)) {
        return None;
    }
    let (speaker, _) = super::super::source_resolution::split_turn_label(quote)?;
    (row["turnSpeaker"].as_str() == Some(speaker)).then(|| speaker.to_owned())
}

#[cfg(test)]
#[test]
fn checks_literal_collectives_and_first_person_attribution() {
    assert_eq!(owner_as_spoken("各园长", &json!({"text":"每个园长在园里开会时都要强调。"})).as_deref(),Some("每个园长"));
    assert_eq!(owner_as_spoken("各园", &json!({"text":"各院把计划发给我。"})).as_deref(),Some("各院"));
    let first_person = json!({"turnSpeaker":"说话人2","text":"说话人2: 我会给下面的老师吩咐。我们一幼讲究创新。"});
    assert_eq!(owner_as_spoken("一幼园长", &first_person).as_deref(),Some("说话人2"));
    assert!(owner_as_spoken("二幼园长", &first_person).is_none());
    assert!(owner_as_spoken("一幼园长",&json!({"turnSpeaker":"说话人2","text":"说话人2: 一幼园长会处理。"})).is_some());
    assert!(owner_as_spoken("一幼园长",&json!({"turnSpeaker":"说话人2","text":"说话人2: 我希望一幼有人处理。"})).is_none());
}

fn preserve_assigned_action(original: &Value, fact: &Fact) -> bool {
    let claim = &original["claim"];
    claim["kind"] == "action" && fact.placement == Placement::Action && (
        (fact.owner.is_none() && !claim["owner"].is_null())
        || (fact.due.is_none() && !claim["due"].is_null())
        || (fact.owner.is_none() && fact.text.contains("待核实"))
    )
}

type SourceIndex<'a> = HashMap<&'a str, &'a Value>;

fn recover_collective_owner(
    original: &Value, item: &mut source_items::SourceItem, requested: &str, bad_proof: &str,
    known: &SourceIndex<'_>,
) -> Option<String> {
    let claim = &original["claim"];
    let text = claim["text"].as_str()?;
    let original_prefix = text.trim_end_matches(['。', '！', '？']);
    let original_modified = item.text.strip_prefix(original_prefix)?;
    let basis = original["basis"].as_array()?;
    let context = original["context"].as_array()?;
    if claim["kind"] != "action" || !claim["owner"].is_null() || !item.is_action()
        || claim["due"].as_str() != item.due.as_deref()
        || !requested.starts_with('各')
        || !["要求", "交给", "请", "由", "让"].iter().any(|cue| text.contains(&format!("{cue}{requested}")))
        || !original_modified.is_empty() && !original_modified.starts_with(['。', '，', '；', '、', ',', ';'])
        || !basis.iter().any(|id| id == bad_proof)
    {
        return None;
    }
    let sentence_number = |id: &str| id.strip_prefix('e')?.parse::<u32>().ok();
    let anchor = sentence_number(bad_proof)?;
    let speaker = known[bad_proof]["turnSpeaker"].as_str()?;
    let addresses = [format!("你们{requested}"), format!("咱们{requested}")];
    let mut witnesses = item.evidence.iter().filter_map(|id| {
        let quote = known.get(id.as_str())?;
        let distance = sentence_number(id)?.checked_sub(anchor)?;
        (distance > 0 && distance <= 3 && quote["turnSpeaker"] == speaker
            && context.iter().any(|entry| entry == id)
            && addresses.iter().any(|form| quote["text"].as_str().is_some_and(|text| text.contains(form))))
            .then_some(id.as_str())
    });
    let proof = witnesses.next()?.to_owned();
    if witnesses.any(|id| id != proof) { return None; }

    // Keep the already audited task text. A nearby witness may fill owner,
    // but it cannot merge another operation into the original task.
    item.text = text.to_owned();
    item.evidence = basis.iter().filter_map(Value::as_str).map(str::to_owned).collect();
    Some(proof)
}

#[cfg(test)]
#[test]
fn collective_owner_rebinds_only_from_nearby_audited_assignment() {
    let original = json!({
        "claim":{"kind":"action","text":"主持人要求各组整理清单。","owner":null,"due":null},
        "basis":["e0041","e0042"],"context":["e0041","e0042","e0043"]
    });
    let proposed = json!({
        "id":"actionItems[0]",
        "replacement":{"role":"action","text":"主持人要求各组整理清单，然后发给经理。","owner":"各组","due":null,
            "evidence":["e0041","e0042","e0043"]},"ownerEvidence":"e0041"
    });
    let source = [
        json!({"id":"e0041","text":"主持人：请大家整理一下。","turnSpeaker":"主持人"}),
        json!({"id":"e0042","text":"整理成一份清单。","turnSpeaker":"主持人"}),
        json!({"id":"e0043","text":"主持人：你们各组的清单随后发给经理。","turnSpeaker":"主持人"}),
    ];
    let run = |rows: &[Value], claim: &Value| {
        let known: SourceIndex<'_> = rows.iter().map(|row| (row["id"].as_str().unwrap(), row)).collect();
        let ids = known.keys().copied().collect();
        bind_edit(serde_json::from_value(proposed.clone()).unwrap(), claim, &known, &ids)
    };
    let edit = run(&source, &original).unwrap().unwrap();
    assert_eq!(edit.text, "主持人要求各组整理清单。");
    assert_eq!(edit.owner.as_deref(), Some("各组"));
    assert_eq!(edit.evidence, ["e0041","e0042","e0043"]);

    let mut unrelated = source;
    unrelated[2]["turnSpeaker"] = json!("其他发言");
    assert!(run(&unrelated, &original).is_err());
}

fn bind_edit(check: Check, original: &Value, known: &SourceIndex<'_>, known_ids: &HashSet<&str>) -> Result<Option<Fact>, &'static str> {
    let context: HashSet<_> = original["context"].as_array().unwrap().iter().filter_map(Value::as_str).collect();
    let basis: HashSet<_> = original["basis"].as_array().unwrap().iter().filter_map(Value::as_str).collect();
    let allowed = |id: &str| factual_audit::canonical_sentence_reference(id, known_ids)
        .filter(|id| context.contains(id.as_str()));
    let fact = match (check.replacement, check.clarification, check.owner_evidence) {
        (None, None, None) => return Ok(None),
        (Some(mut item), None, owner_evidence) => {
            let mut requested = item.owner.clone();
            let due = item.due.clone();
            let evidence_ids: HashSet<_> = item.evidence.iter()
                .filter_map(|id| factual_audit::canonical_sentence_reference(id, known_ids)).collect();
            if !evidence_ids.iter().any(|id| basis.contains(id.as_str())) {
                return Err("任务缺少 basis 中说明原事项的句子。承接者发言不能代替任务原话。");
            }
            if let Some(proof) = owner_evidence {
                let mut proof = allowed(&proof).ok_or("ownerEvidence 不在本条相邻原话中。")?;
                let owner = requested.as_deref().ok_or("ownerEvidence 需要对应明确的 owner。")?;
                let literal = if let Some(literal) = owner_as_spoken(owner, known[proof.as_str()]) {
                    literal
                } else {
                    proof = recover_collective_owner(original, &mut item, owner, &proof, known)
                        .ok_or("ownerEvidence 未出现所填负责人。请区分承接者、主持人和附近讨论者。")?;
                    owner.to_owned()
                };
                // Store the words the source actually supports, including a
                // collective alias or the label of an explicit self-commitment.
                item.owner = Some(literal.clone());
                requested = Some(literal);
                if !item.evidence.iter().any(|id|
                    factual_audit::canonical_sentence_reference(id, known_ids).as_deref() == Some(proof.as_str()))
                {
                    item.evidence.push(proof);
                }
            }
            let mut fact = item.bind(known, known_ids).map_err(|_| "修正的文字、类型或证据编号无效。")?;
            if fact.placement == Placement::Action {
                if let Some(requested) = requested.filter(|_| fact.owner.is_none()) {
                    let snippets = fact.evidence.iter().map(|id| known[id.as_str()]["text"].as_str().unwrap());
                    fact.owner = Some(spoken_department(&requested, snippets)
                        .ok_or("任务原话没有所填负责人。若相邻原话能确认承接者，请填写 ownerEvidence。若所指不明，请引用原话写待核实。")?);
                }
                if due != fact.due { return Err("没有证据说明该时间是这个任务的截止时间。"); }
            }
            fact
        },
        (None, Some(item), None) => {
            let id = allowed(&item.evidence).ok_or("待核实证据不在本条相邻原话中。")?;
            let quote = item.quote.trim();
            if !super::line(quote, 66) || quote.contains(['「', '」'])
                || !super::normalized(known[id.as_str()]["text"].as_str().unwrap()).contains(&super::normalized(quote)) {
                return Err("待核实引语必须是给定原话中的连续片段。");
            }
            Fact {
                id: String::new(), kind: Kind::Status, placement: Placement::Topic,
                text: format!("会上提到「{quote}」，具体所指待核实。"),
                owner: None, due: None, evidence: vec![id],
            }
        },
        _ => return Err("每条只能选择一种修正或待核实方式。"),
    };
    if fact.evidence.iter().any(|id| !context.contains(id.as_str()))
        || !fact.evidence.iter().any(|id| basis.contains(id.as_str())) {
        return Err("修正必须引用本条相邻原话，且至少包含一条 basis。");
    }
    Ok((!preserve_assigned_action(original, &fact)).then_some(fact))
}

#[derive(Default)]
struct BoundEdits {
    accepted: HashMap<String, Fact>,
    rejected: Vec<Value>,
}

fn decode_edits(candidates: &[Value], raw: &str, known: &SourceIndex<'_>, must_resolve: bool) -> Result<BoundEdits, String> {
    let response: Response = serde_json::from_str(super::super::strip_code_fences(raw).trim()).map_err(|_| INCOMPLETE.to_owned())?;
    let mut by_id: HashMap<&str, Vec<&Value>> = HashMap::new();
    for row in &response.role_checks {
        if let Some(id) = row["id"].as_str() { by_id.entry(id).or_default().push(row); }
    }
    let known_ids = known.keys().copied().collect();
    let mut result = BoundEdits::default();
    for original in candidates {
        let id = original["id"].as_str().unwrap();
        let rows = by_id.get(id).map_or(&[][..], Vec::as_slice);
        let bound = match rows {
            [row] => serde_json::from_value::<Check>((*row).clone()).map_err(|_| "返回字段不符合单条核对格式。")
                .and_then(|check| bind_edit(check, original, known, &known_ids)),
            [] => Err("本条未返回处理结果。"),
            _ => Err("本条返回了多份处理结果。"),
        };
        let reason = match bound {
            Ok(Some(fact)) => { result.accepted.insert(id.to_owned(), fact); continue; },
            Ok(None) if !must_resolve => continue,
            Ok(None) => "缺证据的条目必须给出可验证的修正，或按可确认的原话写待核实。",
            Err(reason) => reason,
        };
        result.rejected.push(json!({"id":id,"reason":reason,"previousAnswer":rows.first()}));
    }
    Ok(result)
}

fn statement_has_literal_commitment(text: &str, evidence: &Value, known: &SourceIndex<'_>) -> bool {
    // An exact content-bearing requirement survives a mixed utterance. Only
    // the surrounding optional proposals need the additional stance check.
    let statement = super::normalized(text);
    ["一定要", "必须", "不得", "不允许", "禁止"].iter().any(|marker| {
        let Some((before, after)) = statement.split_once(marker) else { return false; };
        let clause = after.trim_end_matches(['。', '！', '；', '.', '!']);
        if clause.chars().count() < 5 || clause.contains(['，', '。', '；', ',', ';']) {
            return false;
        }
        let subject: String = before.chars().rev().take(4).collect::<Vec<_>>().into_iter().rev().collect();
        if subject.chars().count() < 4 { return false; }
        let anchor = format!("{subject}{marker}{clause}");
        evidence.as_array().unwrap().iter().filter_map(Value::as_str).any(|id| {
            let quote = super::normalized(known[id]["text"].as_str().unwrap());
            quote.match_indices(&anchor).any(|(start, _)| {
                let lead: String = quote[..start].chars().rev().take(11).collect::<Vec<_>>().into_iter().rev().collect();
                !["如果", "可以", "建议", "未定", "未确认", "有人提", "并非", "不是", "不", "考虑"].iter().any(|cue| lead.contains(cue))
            })
        })
    })
}

fn stance_checks(rows: &[Value], accepted: &HashMap<String, Fact>, known: &SourceIndex<'_>) -> Vec<Value> {
    rows.iter().filter_map(|row| {
        let claim = &row["claim"];
        let proposed = accepted.get(row["id"].as_str().unwrap());
        let text = proposed.map(|fact| fact.text.as_str()).unwrap_or_else(|| claim["text"].as_str().unwrap());
        let decision = proposed.map(|fact| fact.placement == Placement::Decision).unwrap_or(claim["kind"] == "decision");
        let action = proposed.map(|fact| fact.placement == Placement::Action).unwrap_or(claim["kind"] == "action");
        let financial_condition = ["费用", "运费", "收费", "分摊", "支付", "承担一半", "扣款"].iter().any(|term| text.contains(term));
        let option = ["建议", "考虑", "备选", "拟定", "可以", "可选", "尚未决定"].iter().any(|term| text.contains(term));
        let risk = row["sourceSignals"].as_array().unwrap().iter().any(|signal| {
            signal["checks"].as_array().unwrap().iter().any(|check| check == "可选方案及其条件")
        });
        if !risk || option || (!decision && (action || !financial_condition)) { return None; }
        if proposed.is_none() && decision && statement_has_literal_commitment(text, &row["basis"], known) {
            return None;
        }
        let mut row = row.clone();
        if let Some(proposed) = proposed {
            row["claim"]["text"] = json!(&proposed.text);
            row["claim"]["kind"] = json!(if decision {"decision"} else {"status"});
        }
        Some(row)
    }).collect()
}

fn execution_checks(rows: &[Value], accepted: &HashMap<String, Fact>, known: &SourceIndex<'_>) -> Vec<Value> {
    static DURATION: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:接下来|未来|计划|打算|准备).{0,12}?([一二两三四五六七八九十半0-9]{1,4}(?:个?月|年))"
    ).unwrap());
    static SPEAKER: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(r"^说话人[0-9]+").unwrap());
    static FOLLOWUP: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"还有.{0,20}?(?:提到|说到)(?:这个|这项)?([\p{Han}0-9A-Za-z]{2,16}?)这个问题"
    ).unwrap());
    let mut checks = Vec::new();
    for row in rows {
        let path = row["id"].as_str().unwrap();
        let claim = &row["claim"];
        let proposed = accepted.get(path);
        let text = proposed.map_or_else(|| claim["text"].as_str().unwrap(), |fact| fact.text.as_str());
        let mut evidence = Vec::new();
        if claim["kind"] == "forecast" && proposed.is_none() {
            for id in row["basis"].as_array().unwrap().iter().filter_map(Value::as_str) {
                let source = known[id];
                let Some(speaker) = source["turnSpeaker"].as_str() else { continue; };
                let Some(duration) = DURATION.captures(source["text"].as_str().unwrap()).and_then(|m| m.get(1)) else { continue; };
                if SPEAKER.find(text).is_some_and(|actor| actor.as_str() != speaker) && text.contains(duration.as_str()) {
                    evidence.push(json!({"kind":"timeSpeaker","evidence":id,"speaker":speaker,"duration":duration.as_str()}));
                }
            }
        }
        if let Some(fact) = proposed.filter(|fact| fact.placement == Placement::Action) {
            for id in &fact.evidence {
                let quote = known[id.as_str()]["text"].as_str().unwrap();
                let Some(cue) = FOLLOWUP.captures(quote).and_then(|m| m.get(1)) else { continue; };
                let condition = cue.as_str().trim_end_matches('儿');
                if !text.contains(condition) {
                    evidence.push(json!({"kind":"executionCondition","evidence":id,"condition":condition}));
                }
            }
        }
        if !evidence.is_empty() {
            let mut packet = row.clone();
            packet["requiredChecks"] = json!(evidence);
            packet["claim"]["text"] = json!(text);
            if let Some(fact) = proposed {
                packet["claim"]["owner"] = json!(&fact.owner);
                packet["claim"]["due"] = json!(&fact.due);
            }
            checks.push(packet);
        }
    }
    checks
}

fn decode_execution(candidates: &[Value], raw: &str, known: &SourceIndex<'_>,
    previous: &HashMap<String, Fact>,
) -> Result<HashMap<String, Fact>, String> {
    let fail = || "纪要仍有时间归属或执行条件未核对，已有结果保留。".to_owned();
    let mut response: Value = serde_json::from_str(super::super::strip_code_fences(raw).trim()).map_err(|_| fail())?;
    for row in response["roleChecks"].as_array_mut().ok_or_else(fail)? {
        let Some(prior) = row["id"].as_str().and_then(|id| previous.get(id))
            .filter(|fact| fact.placement == Placement::Action) else { continue; };
        let item = &mut row["replacement"];
        if item["role"] != "action" || item["owner"] != json!(&prior.owner) || item["due"] != json!(&prior.due) {
            continue;
        }
        // This pass changes execution wording only. Reuse the evidence for
        // the identical assignee and due date already bound in the first pass.
        if let Some(ids) = item["evidence"].as_array_mut() {
            for value in [&prior.owner, &prior.due].into_iter().flatten() {
                let value = super::normalized(value);
                let contains = |id: &str| known.get(id).is_some_and(|quote| {
                    super::normalized(quote["text"].as_str().unwrap()).contains(&value)
                });
                if !ids.iter().filter_map(Value::as_str).any(contains) {
                    if let Some(id) = prior.evidence.iter().find(|id| contains(id.as_str())) {
                        ids.push(json!(id));
                    }
                }
            }
        }
    }
    let bound = decode_edits(candidates, &response.to_string(), known, true)?;
    if !bound.rejected.is_empty() { return Err(fail()); }
    for row in candidates {
        let fact = bound.accepted.get(row["id"].as_str().unwrap()).ok_or_else(fail)?;
        for check in row["requiredChecks"].as_array().unwrap() {
            if !fact.evidence.iter().any(|id| check["evidence"] == id.as_str()) {
                return Err(fail());
            }
            if check["kind"] == "timeSpeaker" {
                let Some(speaker) = check["speaker"].as_str() else { return Err(fail()); };
                let attributed = fact.text.strip_prefix(speaker).and_then(|remainder| remainder.chars().next())
                    .is_some_and(|next| !next.is_ascii_digit());
                if fact.placement != Placement::Topic || !attributed
                    || !fact.text.contains(check["duration"].as_str().unwrap()) { return Err(fail()); }
            } else if fact.placement != Placement::Action || json!(&fact.owner) != row["claim"]["owner"]
                || json!(&fact.due) != row["claim"]["due"] || !fact.text.contains(check["condition"].as_str().unwrap()) {
                return Err(fail());
            }
        }
    }
    Ok(bound.accepted)
}

fn explicit_stance(quote: &str, statement: &str) -> bool {
    let definite = ["已经决定", "明确决定", "定下来", "拍板", "确定", "已通过", "一致同意", "就这么办",
        "一定要", "必须", "不允许", "禁止", "以此为准"];
    let optional = ["可以", "如果", "建议", "是否", "可能", "考虑", "没决定", "未确定", "没有确定", "尚未决定", "不一定", "待确认"];
    let chars: Vec<_> = statement.chars().collect();
    let relevant = chars.windows(4).any(|window| quote.contains(&window.iter().collect::<String>()));
    relevant && definite.iter().any(|term| quote.contains(term)) && !optional.iter().any(|term| quote.contains(term))
}

fn decode_stance(candidates: &[Value], raw: &str, known: &SourceIndex<'_>) -> Result<HashMap<String, Fact>, String> {
    let fail = || "仍有候选方案缺少定案依据，已有结果保留。".to_owned();
    let mut response: Value = serde_json::from_str(super::super::strip_code_fences(raw).trim()).map_err(|_| fail())?;
    let rows = response["roleChecks"].as_array_mut().ok_or_else(fail)?;
    if rows.len() != candidates.len() { return Err(fail()); }
    let allowed: HashMap<_,_> = candidates.iter().map(|row| (row["id"].as_str().unwrap(), row)).collect();
    for row in rows {
        let candidate = allowed.get(row["id"].as_str().ok_or_else(fail)?).ok_or_else(fail)?;
        let proof = row.as_object_mut().ok_or_else(fail)?.remove("confirmation");
        if row["replacement"].is_null() && row["clarification"].is_null() {
            let proof: Clarification = serde_json::from_value(proof.ok_or_else(fail)?).map_err(|_| fail())?;
            let source = known.get(proof.evidence.as_str()).ok_or_else(fail)?;
            let context = candidate["context"].as_array().unwrap();
            if !super::line(&proof.quote, 80) || !context.contains(&json!(proof.evidence))
                || !source["text"].as_str().unwrap().contains(&proof.quote)
                || !explicit_stance(&proof.quote, candidate["claim"]["text"].as_str().unwrap()) {
                return Err(fail());
            }
        } else {
            if proof.is_some() { return Err(fail()); }
            if let Some(edit) = row["replacement"].as_object() {
                let text = edit["text"].as_str().ok_or_else(fail)?;
                if !matches!(edit["role"].as_str(), Some("recommendation" | "status"))
                    || !["建议","考虑","可","拟","设想","待定","尚未","待核实"].iter().any(|term| text.contains(term)) {
                    return Err(fail());
                }
            }
        }
    }
    let bound = decode_edits(candidates, &response.to_string(), known, false)?;
    if !bound.rejected.is_empty() { return Err(fail()); }
    Ok(bound.accepted)
}

fn apply(doc: &Document, candidates: &[Value], mut edits: HashMap<String, Fact>, known: &SourceIndex<'_>, units: &[Unit]) -> Result<Document, String> {
    let fail = || INCOMPLETE.to_owned();
    let mut work = serde_json::to_value(doc).map_err(|_| fail())?;
    let mut removals = Vec::new();
    let mut additions = Vec::new();
    for row in candidates {
        let path = row["id"].as_str().unwrap();
        let Some(fact) = edits.remove(path) else { continue; };
        let mut sources: Vec<_> = fact.evidence.iter().map(|id| known[id.as_str()]["source"].as_str().unwrap().to_owned()).collect();
        sources.sort_unstable();
        sources.dedup();
        let pointer = format!("/{}", path.replace('[', "/").replace(']', "").replace('.', "/"));
        let topical = path.starts_with("topics[");
        let entry = Entry {text: fact.text, sources, quantity_needs_review: false};
        let new_value = match fact.placement {
            Placement::Action => json!(Action {text: entry.text.clone(), owner:fact.owner, due:fact.due, sources:entry.sources.clone()}),
            _ => json!(&entry),
        };
        let same_section = (topical && fact.placement == Placement::Topic)
            || (path.starts_with("decisions[") && fact.placement == Placement::Decision)
            || (path.starts_with("actionItems[") && fact.placement == Placement::Action);
        if same_section || (topical && path.contains(".points[")) {
            let target = work.pointer_mut(&pointer).ok_or_else(fail)?;
            if topical {
                let mut updated = json!(&entry);
                if path.contains(".points[") {
                    updated["kind"] = json!(if same_section { fact.kind } else { Kind::Status });
                }
                *target = updated;
            } else { *target = new_value.clone(); }
        } else {
            let (list, index) = pointer.rsplit_once('/').ok_or_else(fail)?;
            removals.push((list.to_owned(), index.parse::<usize>().map_err(|_| fail())?));
        }
        if !same_section { additions.push((fact.placement, entry, new_value)); }
    }
    removals.sort_unstable_by(|a,b| b.cmp(a));
    for (list,index) in removals {
        let rows = work.pointer_mut(&list).and_then(Value::as_array_mut).ok_or_else(fail)?;
        if index >= rows.len() { return Err(fail()); }
        rows.remove(index);
    }
    let mut checked: Document = serde_json::from_value(work).map_err(|_| fail())?;
    for (placement,entry,serialized) in additions {
        match placement {
            Placement::Topic => {
                let index = source_items::omission_topic(&checked, &entry.sources, units).ok_or_else(fail)?;
                if !checked.topics[index].details.iter().any(|item| item.text == entry.text) {
                    checked.topics[index].details.push(entry);
                }
            },
            Placement::Action => {
                let action: Action = serde_json::from_value(serialized).map_err(|_| fail())?;
                if !checked.action_items.iter().any(|item| item.text == action.text && item.owner == action.owner && item.due == action.due) {
                    checked.action_items.push(action);
                }
            },
            Placement::Decision => checked.decisions.push(entry),
            Placement::Question => checked.questions.push(entry),
        }
    }
    super::validate(&checked, units)?;
    Ok(checked)
}

pub(super) fn review(endpoint:&str, model:&str, key:&str, client:&reqwest::blocking::Client,
    verified:factual_audit::VerifiedBrief, units:&[Unit], start:Instant, trace:&mut Vec<Value>) -> Result<Document, String>
{
    let source = with_turn_labels(&factual_audit::evidence_sentences(units));
    let rows = candidates(&verified, &source);
    if rows.is_empty() {
        return super::source_scope::review(endpoint,model,key,client,&verified,verified.document.clone(),units,start,trace);
    }
    let quotes_for = |rows: &[Value]| {
        let selected: HashSet<_> = rows.iter().flat_map(|item| item["context"].as_array().unwrap().iter())
            .filter_map(Value::as_str).collect();
        source.iter().filter(|row| selected.contains(row["id"].as_str().unwrap())).collect::<Vec<_>>()
    };
    let raw = super::request(endpoint,model,key,client,PROMPT,json!({"roleChecks":rows,"sourceSentences":quotes_for(&rows)}),
        false,start,trace,"source-commitment-review")?;
    if std::env::var_os("COMPANION_TYPE_AUTOMATIC_BRIEF_TRACE_PATH").is_some() {
        if let Some(call) = trace.last_mut() {
            call["priorEvidence"] = json!(&verified.evidence);
        }
    }
    let known: SourceIndex<'_> = source.iter().map(|row| (row["id"].as_str().unwrap(), row)).collect();
    let mut bound = decode_edits(&rows, &raw, &known, false)?;
    if !bound.rejected.is_empty() {
        let rejected_ids: HashSet<_> = bound.rejected.iter().filter_map(|issue| issue["id"].as_str()).collect();
        let requested: Vec<_> = rows.iter().filter(|row| rejected_ids.contains(row["id"].as_str().unwrap())).cloned().collect();
        let request = json!({"roleChecks":requested,"sourceSentences":quotes_for(&requested),"rejectedEdits":bound.rejected});
        let retry = super::request(endpoint,model,key,client,PROMPT,request,false,start,trace,"source-commitment-evidence")?;
        let repaired = decode_edits(&requested, &retry, &known, true)?;
        if !repaired.rejected.is_empty() {
            return Err(format!("仍有{}条纪要修正缺少原话证据，已有结果保留。", repaired.rejected.len()));
        }
        bound.accepted.extend(repaired.accepted);
    }
    let stance = stance_checks(&rows, &bound.accepted, &known);
    if !stance.is_empty() {
        let input = json!({"stanceChecks":stance,"sourceSentences":quotes_for(&stance)});
        let raw = super::request(endpoint,model,key,client,STANCE_PROMPT,input,false,start,trace,"source-commitment-stance")?;
        bound.accepted.extend(decode_stance(&stance, &raw, &known)?);
    }
    let execution = execution_checks(&rows, &bound.accepted, &known);
    if !execution.is_empty() {
        let input = json!({"executionChecks":execution,"sourceSentences":quotes_for(&execution)});
        let raw = super::request(endpoint,model,key,client,EXECUTION_PROMPT,input,false,start,trace,"source-execution-scope")?;
        let edits = decode_execution(&execution, &raw, &known, &bound.accepted)?;
        bound.accepted.extend(edits);
    }
    let improved = apply(&verified.document, &rows, bound.accepted, &known, units)?;
    super::source_scope::review(endpoint,model,key,client,&verified,improved,units,start,trace)
}

#[cfg(test)]
#[test]
#[ignore = "paired replay of an already audited public transcript through the real final review"]
fn review_from_verified_public_minutes() {
    let setting = |name| std::env::var(name).expect(name);
    assert!(source_items::enabled());
    assert_eq!(setting("DEEPSEEK_API_KEY"), "qm06-unified-relay");
    assert!(setting("DEEPSEEK_BASE_URL").starts_with("http://127.0.0.1:"));
    let fixture: Value = serde_json::from_slice(&std::fs::read(setting("QM06_INPUT")).unwrap()).unwrap();
    let units = super::source_units(fixture["text"].as_str().unwrap());
    let verified = factual_audit::VerifiedBrief {
        document: serde_json::from_value(fixture["document"].clone()).unwrap(),
        evidence: serde_json::from_value(fixture["priorEvidence"].clone()).unwrap(),
        pending_quotes: Vec::new(),
    };
    super::validate(&verified.document, &units).unwrap();
    let client = reqwest::blocking::Client::builder().no_proxy().build().unwrap();
    let mut trace = Vec::new();
    let start = Instant::now();
    let output = review(&setting("DEEPSEEK_BASE_URL"), &setting("DEEPSEEK_MODEL"), &setting("DEEPSEEK_API_KEY"),
        &client, verified, &units, start, &mut trace);
    std::fs::write(setting("QM06_RESULT"), serde_json::to_vec_pretty(&json!({
        "accepted":output.is_ok(),"document":output.as_ref().ok(),"error":output.as_ref().err(),
        "calls":trace,"seconds":start.elapsed().as_secs_f64()
    })).unwrap()).unwrap();
}
