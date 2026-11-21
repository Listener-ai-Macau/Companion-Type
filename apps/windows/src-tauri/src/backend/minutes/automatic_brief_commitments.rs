//! Recheck commitments and execution details against the cited turns before delivery.
use std::{collections::{HashMap, HashSet}, sync::LazyLock, time::Instant};

use serde::Deserialize;
use serde_json::{Value, json};

use super::{Action, Document, Entry, Kind, Unit, answer_layout::{Fact, Placement}, factual_audit, source_items};

const PROMPT: &str = include_str!("automatic_brief_commitments.txt");
const DECISION_ORDER: &str = "laterEvidence 指向这项决定可能相关的后段原话。比较实际议题、执行对象、适用条件及顺序。后段明确确认同一事项的新口径时，replacement 引入后段明确口径，并同时引用 basis 和后段原话。各有适用对象时分别保留。未解决冲突时用 clarification 留原话待核。后段的设想、客套话、同名的其他项目不能覆盖早前已确认事项。";
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

fn later_decision_evidence(
    statement: &str, basis: &[String], source: &[Value],
    positions: &HashMap<&str, usize>, verified_claims: &[Value],
    verified_evidence: &HashMap<String, Vec<String>>,
) -> Vec<usize> {
    static FINAL_WORDING: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:我们|咱们)?(?:刚刚|刚才|现在|最后)?(?:已经|已|最终|正式)(?:确定|决定|定下|议定|拍板|确认)"
    ).unwrap());
    let latest = basis.iter().filter_map(|id| positions.get(id.as_str()).copied()).max();
    let Some(latest) = latest else { return Vec::new(); };
    let original: Vec<_> = basis.iter().filter_map(|id| positions.get(id.as_str()))
        .filter_map(|index| source[*index]["text"].as_str()).map(super::normalized).collect();
    let statement = super::normalized(statement);
    verified_claims.iter().filter(|claim| {
        claim["path"].as_str().is_some_and(|path| path.starts_with("topics["))
            && claim["text"].as_str().is_some_and(|text| FINAL_WORDING.is_match(text))
    }).filter_map(|claim| {
        let text = claim["text"].as_str()?;
        let verified = super::normalized(text);
        if verified == statement { return None; }
        let ids = verified_evidence.get(claim["path"].as_str()?)?;
        ids.iter().filter_map(|id| positions.get(id.as_str()).copied()).filter(|index| *index > latest)
            .find(|index| {
                let quote = source[*index]["text"].as_str().unwrap_or_default();
                FINAL_WORDING.find_iter(quote).any(|marker| {
                    let earlier = &quote[..marker.start()];
                    if earlier.trim_end().ends_with(['没', '不', '未']) || earlier.trim_end().ends_with("没有") {
                        return false;
                    }
                    let clause = earlier.rsplit(['。', '；', '？', '！', '\n']).next().unwrap_or_default();
                    let recent: Vec<_> = clause.chars().rev().take(16).collect();
                    recent.windows(3).any(|part| {
                        let literal: String = part.iter().rev().collect();
                        literal.chars().all(char::is_alphanumeric)
                            && statement.contains(&literal) && verified.contains(&literal)
                            && original.iter().any(|quote| quote.contains(&literal))
                    })
                })
            })
    }).take(4).collect()
}

fn candidates(doc: &factual_audit::VerifiedBrief, source: &[Value]) -> Vec<Value> {
    let positions: HashMap<_, _> = source.iter().enumerate()
        .map(|(index, row)| (row["id"].as_str().unwrap(), index)).collect();
    let bindings = super::source_bindings::SourceBindings::new(source);
    let mut candidates = Vec::new();
    let claims = factual_audit::claims(&doc.document);
    for claim in &claims {
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
        let later = if path.starts_with("decisions[") {
            later_decision_evidence(text, ids, source, &positions, &claims, &doc.evidence)
        } else {
            Vec::new()
        };
        for index in &later {
            context.extend(index.saturating_sub(1)..(*index + 2).min(source.len()));
        }
        let turn_starts: Vec<_> = context.iter().filter_map(|index| source[*index]["speakerEvidence"].as_str())
            .filter_map(|id| positions.get(id).copied()).collect();
        context.extend(turn_starts);
        context.sort_unstable();
        context.dedup();
        let context: Vec<_> = context.into_iter().map(|index| &source[index]["id"]).collect();
        let mut candidate = json!({"id":path,"claim":claim,"basis":ids,"context":context,"sourceSignals":signals});
        if !later.is_empty() {
            candidate["laterEvidence"] = json!(later.iter().map(|index| &source[*index]["id"]).collect::<Vec<_>>());
        }
        candidates.push(candidate);
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

fn department_stem(requested: &str) -> Option<&str> {
    let stem = requested.strip_suffix("部门").or_else(|| requested.strip_suffix('部'))?;
    ((2..=18).contains(&stem.chars().count()) && stem.chars().all(|ch| ('㐀'..='鿿').contains(&ch))).then_some(stem)
}

fn spoken_department<'a>(requested: &str, snippets: impl Iterator<Item = &'a str> + Clone) -> Option<String> {
    let stem = department_stem(requested)?;
    ["的部门", "这边"].into_iter().map(|ending| format!("{stem}{ending}"))
        .find(|form| snippets.clone().any(|text| super::normalized(text).contains(form)))
}

fn directed_department(requested: &str, proof: &Value) -> Option<String> {
    let stem = department_stem(requested)?;
    let quote = proof["text"].as_str()?;
    let normalized = super::normalized(quote);
    ["儿那边儿", "儿这边儿", "那边儿", "儿那边", "儿这边", "那边"].into_iter()
        .map(|ending| format!("{stem}{ending}"))
        .find(|form| normalized.split_once(form).is_some_and(|(_, after)|
            after.starts_with(['你', '您', '要', '先', '得'])))
        .or_else(|| assigned_department_short_name(stem, quote))
}

fn assigned_department_short_name(stem: &str, quote: &str) -> Option<String> {
    let mut assignments = quote.match_indices(stem).filter(|(start, label)| {
        let (before, after) = (&quote[..*start], &quote[*start + label.len()..]);
        let before = before.rsplit(['。', '？', '！', '，', '；']).next().unwrap_or("").trim_end();
        let after = after.trim_start();
        let Some(lead) = ["需要", "要求", "安排", "交给", "请", "让", "由"].into_iter()
            .find_map(|directive| before.strip_suffix(directive))
        else {
            return false;
        };
        let lead = lead.trim_end();
        if ["没有", "没", "不", "别", "无需", "无须", "并非", "不用"].iter().any(|word| lead.ends_with(word))
            || ["如果", "假如", "要不要", "能否", "是否", "考虑", "拟", "原先"].iter().any(|word| lead.contains(word))
        {
            return false;
        }
        after.starts_with("负责") || after.strip_prefix('去').is_some_and(|work| {
            ["调查", "核对", "准备", "跟进", "收集", "整理", "联系", "处理", "安排", "确认", "提交", "沟通"]
                .iter().any(|action| work.trim_start().starts_with(action))
        })
    });
    let (_, original) = assignments.next()?;
    assignments.next().is_none().then(|| original.to_owned())
}

fn spoken_collective(requested: &str, quote: &str) -> Option<String> {
    if requested == "各园" && quote.contains("各院") {
        return Some("各院".to_owned());
    }
    let group = requested.strip_prefix('各')?;
    if !(2..=14).contains(&group.chars().count()) || !group.chars().all(|ch| ('㐀'..='鿿').contains(&ch)) {
        return None;
    }
    ["各自", "每个", "每一个", "每位", "每一位"].into_iter().map(|prefix| format!("{prefix}{group}"))
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
    assert_eq!(owner_as_spoken("各部门", &json!({"text":"各自部门儿回去之后把这个方案都赶紧做出来。"})).as_deref(),Some("各自部门"));
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
    let basis = original["basis"].as_array()?;
    let context = original["context"].as_array()?;
    if claim["kind"] != "action" || !claim["owner"].is_null() || !item.is_action()
        || claim["due"].as_str() != item.due.as_deref()
        || !requested.starts_with('各')
        || !["要求", "交给", "请", "由", "让"].iter().any(|cue| text.contains(&format!("{cue}{requested}")))
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
    let run = |rows: &[Value], proposal: Value| {
        let known: SourceIndex<'_> = rows.iter().map(|row| (row["id"].as_str().unwrap(), row)).collect();
        let ids = known.keys().copied().collect();
        bind_edit(serde_json::from_value(proposal).unwrap(), &original, &known, &ids)
    };
    let mut shortened = proposed.clone();
    shortened["replacement"]["text"] = json!("各组整理清单，然后发给经理。");
    for proposal in [proposed, shortened.clone()] {
        let edit = run(&source, proposal).unwrap().unwrap();
        assert_eq!(edit.text, "主持人要求各组整理清单。");
        assert_eq!(edit.owner.as_deref(), Some("各组"));
        assert_eq!(edit.evidence, ["e0041","e0042","e0043"]);
    }

    let mut unrelated = source;
    unrelated[2]["turnSpeaker"] = json!("其他发言");
    assert!(run(&unrelated, shortened).is_err());
}

fn unchanged_action_with_unbound_owner(original: &Value, item: &mut source_items::SourceItem,
    proof: &str, known: &SourceIndex<'_>) -> bool
{
    let claim = &original["claim"];
    let Some(text) = claim["text"].as_str() else { return false };
    let Some(basis) = original["basis"].as_array() else { return false };
    let quote = super::normalized(known[proof]["text"].as_str().unwrap_or(""));
    if claim["kind"] != "action" || !claim["owner"].is_null() || !item.is_action()
        || item.text.as_str() != text || claim["due"].as_str() != item.due.as_deref()
        || !basis.iter().any(|id| id == proof)
        || !["你那边", "你这边"].iter().any(|form| quote.contains(form))
    {
        return false;
    }
    let pending = if text.contains("负责人待核实") {
        text.to_owned()
    } else {
        format!("{}（负责人待核实）。", text.trim_end_matches(['。', '！', '？']))
    };
    if !super::line(&pending, 90) { return false; }

    // The role checker only tried to enrich an already audited assignment.
    // An ambiguous addressee cannot replace it or add a deadline.
    item.text = pending;
    item.owner = None;
    item.evidence = basis.iter().filter_map(Value::as_str).map(str::to_owned).collect();
    true
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
                let witness = known[proof.as_str()];
                let literal = if let Some(literal) = owner_as_spoken(owner, witness)
                    .or_else(|| directed_department(owner, witness))
                {
                    literal
                } else if let Some(recovered) = recover_collective_owner(original, &mut item, owner, &proof, known) {
                    proof = recovered;
                    owner.to_owned()
                } else if unchanged_action_with_unbound_owner(original, &mut item, &proof, known) {
                    return item.bind(known, known_ids).map(Some)
                        .map_err(|_| "已核任务的负责人待核说明无法保留。");
                } else {
                    return Err("ownerEvidence 未出现所填负责人。请区分承接者、主持人和附近讨论者。");
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
                if due != fact.due {
                    let claim = &original["claim"];
                    let unchanged_action = claim["kind"] == "action" && claim["due"].is_null()
                        && fact.due.is_none()
                        && claim["text"].as_str().is_some_and(|text| super::normalized(text) == super::normalized(&fact.text));
                    if !unchanged_action { return Err("没有证据说明该时间是这个任务的截止时间。"); }
                }
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

#[cfg(test)]
#[test]
fn keeps_dialect_owner_and_defers_an_unbound_pronoun_without_losing_the_task() {
    let original = json!({
        "claim":{"kind":"action","text":"检查设备资质。","owner":null,"due":null},
        "basis":["e0041"],"context":["e0041"]
    });
    let bind = |quote: &str, owner: &str, text: &str| {
        let row = json!({"text":quote,"turnSpeaker":"主持人"});
        let known = SourceIndex::from([("e0041",&row)]);
        let ids = HashSet::from(["e0041"]);
        let edit = json!({"id":"actionItems[0]","ownerEvidence":"e0041",
            "replacement":{"role":"action","text":text,"owner":owner,"due":null,"evidence":["e0041"]}});
        bind_edit(serde_json::from_value(edit).unwrap(),&original,&known,&ids)
    };
    let named = bind("主持人：物料儿那边儿你先检查这个设备资质。","物料部","检查设备资质。").unwrap().unwrap();
    assert_eq!(named.owner.as_deref(),Some("物料儿那边儿"));
    let survey = json!({"text":"负责人：这边儿需要市场去调查一下客户做一下问卷。"});
    assert_eq!(directed_department("市场部", &survey).as_deref(),Some("市场"));
    for utterance in ["不需要市场去调查。", "如果需要市场去调查，之后再说。", "需要市场数据做参考。",
        "请研究市场发展趋势。", "让研发去调查、请研发去准备。"] {
        assert!(directed_department("市场部", &json!({"text":utterance})).is_none());
    }
    assert!(directed_department("研发部", &json!({"text":"让研发去调查、请研发去准备。"})).is_none());
    let pending = bind("主持人：那你那边儿先检查这个设备资质。","说话人3","检查设备资质。").unwrap().unwrap();
    assert!(pending.owner.is_none());
    assert_eq!(pending.text,"检查设备资质（负责人待核实）。");
    assert!(bind("主持人：那你那边儿先检查这个设备资质。","说话人3","检查设备资质并交给财务。").is_err());
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
        let basis = proposed.map_or_else(|| row["basis"].clone(), |fact| json!(&fact.evidence));
        let restricted_decision = decision
            && ["只对", "只给", "只向", "仅对", "仅给", "仅供", "仅限", "只限", "面向"]
                .iter().any(|cue| text.contains(cue))
            && !basis.as_array().unwrap().iter().filter_map(Value::as_str)
                .any(|id| explicit_stance(known[id]["text"].as_str().unwrap(), text));
        if !(risk || restricted_decision) || option || (!decision && (action || !financial_condition)) {
            return None;
        }
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
    if optional.iter().any(|term| quote.contains(term)) { return false; }
    if relevant && definite.iter().any(|term| quote.contains(term)) { return true; }
    // An affirmative decision not to impose a restriction can use ordinary
    // negative phrasing. Bind that phrasing to the same short restriction.
    let said_no = ["不必要", "不必", "无需"].iter().find_map(|term| {
        let (before, after) = quote.split_once(term)?;
        ["咱", "我们", "本次", "现在"].iter().any(|marker| before.contains(marker))
            .then_some(after)
    });
    said_no.is_some_and(|after| {
        let task: String = after.chars().take_while(|ch| ch.is_alphanumeric()).take(2).collect();
        task.chars().count() == 2
            && statement.find(&task).is_some_and(|at| statement[..at].contains('不'))
    })
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
            let statement = candidate["claim"]["text"].as_str().unwrap();
            if !super::line(&proof.quote, 80) || !context.contains(&json!(proof.evidence))
                || !source["text"].as_str().unwrap().contains(&proof.quote)
            {
                return Err(fail());
            }
            let agreeing = proof.quote.trim().starts_with('对')
                && !["不对", "不赞同", "不能", "不可以", "我建议", "如果"].iter().any(|term| proof.quote.contains(term));
            let ordinal = |id: &str| id.strip_prefix('e')?.parse::<usize>().ok();
            let exact_basis = agreeing && candidate["basis"].as_array().unwrap().iter().filter_map(Value::as_str)
                .any(|id| {
                    let basis = known[id];
                    let near = ordinal(&proof.evidence).zip(ordinal(id))
                        .is_some_and(|(response, prior)| (1..=2).contains(&response.saturating_sub(prior)));
                    near && basis["source"] == source["source"] && context.contains(&json!(id))
                        && explicit_stance(basis["text"].as_str().unwrap(), statement)
                });
            if !explicit_stance(&proof.quote, statement) && !exact_basis { return Err(fail()); }
        } else {
            if proof.is_some() { return Err(fail()); }
            if let Some(edit) = row["replacement"].as_object() {
                let text = edit["text"].as_str().ok_or_else(fail)?;
                let tentative = ["建议","考虑","可","拟","设想","待定","尚未","待核实"]
                    .iter().any(|term| text.contains(term));
                let attributed_description = edit["role"] == "status"
                    && ["会上仅说明", "会上仅介绍", "会上说明", "会上介绍", "会上有人说明"]
                        .iter().any(|term| text.starts_with(term))
                    && ["不构成新决定", "未形成新的决定", "仍待确认"].iter().any(|term| text.contains(term));
                if !matches!(edit["role"].as_str(), Some("recommendation" | "status"))
                    || !(tentative || attributed_description) {
                    return Err(fail());
                }
            }
        }
    }
    let bound = decode_edits(candidates, &response.to_string(), known, false)?;
    if !bound.rejected.is_empty() { return Err(fail()); }
    Ok(bound.accepted)
}

fn explicit_setting(text: &str) -> Option<(&str, &str, &str)> {
    let first = text.split(['，', '。', '；', ',', ';']).next()?.trim();
    let head = ["本次会议", "会议", "会上"].iter().find_map(|prefix| first.strip_prefix(prefix)).unwrap_or(first);
    let head = ["先", "最初", "原先", "当时", "当前"].iter().find_map(|prefix| head.strip_prefix(prefix)).unwrap_or(head);
    let setting = ["最终确定", "已经确定", "已确定", "已明确", "已确认", "确定", "定下"]
        .iter().find_map(|prefix| head.strip_prefix(prefix))?;
    let (subject, value) = setting.split_once('为')?;
    let subject = subject.strip_prefix("最基本的").unwrap_or(subject).trim();
    if !(3..=22).contains(&subject.chars().count()) || !subject.chars().all(char::is_alphanumeric)
        || !super::line(value, 36) || ["可以", "考虑", "待核", "如果", "可能", "拟"]
            .iter().any(|marker| value.contains(marker))
    {
        return None;
    }
    Some((subject, value.trim(), first))
}

fn retain_verified_later_settings(
    verified: &factual_audit::VerifiedBrief, rows: &[Value], known: &SourceIndex<'_>,
    edits: &mut HashMap<String, Fact>,
) -> Vec<Value> {
    let claims = factual_audit::claims(&verified.document);
    let mut used = Vec::new();
    for row in rows {
        let Some(path) = row["id"].as_str().filter(|path| path.starts_with("decisions[")) else { continue; };
        let Some([id]) = row["laterEvidence"].as_array().map(Vec::as_slice) else { continue; };
        let Some(id) = id.as_str() else { continue; };
        let Some(edit) = edits.get_mut(path).filter(|edit|
            edit.placement == Placement::Decision && edit.evidence.iter().any(|e| e == id))
        else { continue; };
        let Some(before) = row["claim"]["text"].as_str().and_then(explicit_setting) else { continue; };
        let Some(proposed) = explicit_setting(&edit.text) else { continue; };
        if before.0 != proposed.0 || before.1 != proposed.1 { continue; }
        let Some(quote) = known.get(id).and_then(|row| row["text"].as_str()) else { continue; };
        if !quote.contains(before.0) || ["另一个", "另一家", "另一套", "其他门店"]
            .iter().any(|cue| quote.contains(cue)) {
            continue;
        }
        let candidates: HashSet<_> = claims.iter().filter_map(|claim| {
            let path = claim["path"].as_str().filter(|path| path.starts_with("topics["))?;
            let evidence = verified.evidence.get(path)?;
            if !evidence.iter().any(|e| e == id) { return None; }
            let (subject, value, text) = explicit_setting(claim["text"].as_str()?)?;
            (subject == before.0 && value != before.1).then_some(text)
        }).collect();
        if candidates.len() != 1 { continue; }
        let text = *candidates.iter().next().unwrap();
        let next = format!("{}。", text.trim_end_matches('。'));
        used.push(json!({"path":path,"laterEvidence":id,"previousText":edit.text,"confirmedText":next}));
        edit.text = next;
    }
    used
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
    let order_prompt = rows.iter().any(|row| row.get("laterEvidence").is_some())
        .then(|| format!("{PROMPT}\n{DECISION_ORDER}"));
    let prompt = order_prompt.as_deref().unwrap_or(PROMPT);
    let raw = super::request(endpoint,model,key,client,prompt,json!({"roleChecks":rows,"sourceSentences":quotes_for(&rows)}),
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
        let retry = super::request(endpoint,model,key,client,prompt,request,false,start,trace,"source-commitment-evidence")?;
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
    let carried = retain_verified_later_settings(&verified, &rows, &known, &mut bound.accepted);
    if !carried.is_empty() {
        trace.push(json!({"stage":"source-verified-later-settings","changes":carried}));
    }
    let improved = apply(&verified.document, &rows, bound.accepted, &known, units)?;
    // Source-scope review independently audits all changed assertions once.
    super::source_scope::review(endpoint,model,key,client,&verified,improved,units,start,trace)
}

#[cfg(test)]
#[test]
fn an_attributed_description_and_a_bound_acknowledgment_are_distinct_outcomes() {
    let source = [
        json!({"id":"e0187","source":"u012","text":"前台对于一些固定的客户赠送。"}),
        json!({"id":"e0253","source":"u016","text":"对咱这走的不是自助那种形式，咱这种不必要限时嗯"}),
        json!({"id":"e0254","source":"u016","text":"对不用限可以啊"}),
    ];
    let known: SourceIndex<'_> = source.iter().map(|row| (row["id"].as_str().unwrap(),row)).collect();
    let candidates = [
        json!({"id":"decisions[2]","basis":["e0187"],"context":["e0187"],
            "claim":{"kind":"decision","text":"前台饮品面向固定客户赠送。"}}),
        json!({"id":"decisions[3]","basis":["e0253","e0254"],"context":["e0253","e0254"],
            "claim":{"kind":"decision","text":"明确不对顾客限时，因火锅不同于自助餐。"}}),
    ];
    let mut reply = json!({"roleChecks":[
        {"id":"decisions[2]","replacement":{"role":"status","text":"会上仅说明前台饮品面向固定客户赠送，此现状说明不构成新决定。",
            "owner":null,"due":null,"evidence":["e0187"]}},
        {"id":"decisions[3]","replacement":null,"confirmation":{"evidence":"e0254","quote":"对不用限可以啊"}}
    ]});
    let result = decode_stance(&candidates,&reply.to_string(),&known).unwrap();
    assert_eq!(result["decisions[2]"].placement,Placement::Topic);
    assert!(!result.contains_key("decisions[3]"));
    reply["roleChecks"][1]["confirmation"]["quote"] = json!("对肯定限时");
    assert!(decode_stance(&candidates,&reply.to_string(),&known).is_err());
}

#[cfg(test)]
#[test]
fn a_restricted_offer_needs_confirmation_even_when_the_source_sounds_declarative() {
    let candidate = json!({"id":"decisions[2]","claim":{"kind":"decision","text":"前台免费赠饮面向固定客户。"},
        "basis":["e0187"],"context":["e0187","e0191"],"sourceSignals":[]});
    let mut evidence = json!({"text":"这个在前台免费赠送，对于一些固定的客户赠送。"});
    let known = HashMap::from([("e0187", &evidence)]);
    assert_eq!(stance_checks(&[candidate.clone()], &HashMap::new(), &known), [candidate.clone()]);
    evidence["text"] = json!("明确决定前台免费赠饮面向固定客户，按这个规则执行。");
    let known = HashMap::from([("e0187", &evidence)]);
    assert!(stance_checks(&[candidate], &HashMap::new(), &known).is_empty());
}

#[cfg(test)]
#[test]
fn a_revision_cannot_cite_the_later_value_and_keep_the_earlier_setting() {
    let document: Document = serde_json::from_value(json!({"purpose":"讨论装修",
        "topics":[{"title":"装修颜色","points":[{"kind":"status","text":"已确定主色调为棕色加一些红色，灯光用暖色调。","sources":["u002"]}],"details":[]}],
        "decisions":[{"text":"会议先定下最基本的主色调为红色，可画黄色或白色涂鸦。","sources":["u000"]}],
        "questions":[],"actionItems":[]})).unwrap();
    let verified = factual_audit::VerifiedBrief {
        document, evidence: HashMap::from([("topics[0].points[0]".into(),vec!["e0002".into()])]),
        pending_quotes: Vec::new(),
    };
    let original = "会议先定下最基本的主色调为红色，可画黄色或白色涂鸦。";
    let item = Fact {id:String::new(),kind:Kind::Decision,placement:Placement::Decision,
        text:"先定下最基本的主色调为红色，可画黄色或白色涂鸦。".into(),owner:None,due:None,
        evidence:vec!["e0000".into(),"e0002".into()]};
    let mut edits = HashMap::from([("decisions[0]".into(),item.clone())]);
    let row = json!({"id":"decisions[0]","claim":{"text":original},"laterEvidence":["e0002"]});
    let other = json!({"text":"另一家店主色调我们已经确定是棕色加一些红色。"});
    assert!(retain_verified_later_settings(
        &verified,std::slice::from_ref(&row),&HashMap::from([("e0002",&other)]),&mut edits).is_empty());
    let same = json!({"text":"这个主色调我们刚刚已经确定啦，就是棕色，然后加一些红色。"});
    let known = HashMap::from([("e0002",&same)]);
    assert_eq!(retain_verified_later_settings(
        &verified,std::slice::from_ref(&row),&known,&mut edits).len(),1);
    assert_eq!(edits["decisions[0]"].text,"已确定主色调为棕色加一些红色。");
    assert_eq!(edits["decisions[0]"].evidence,["e0000","e0002"]);
    let mut edits = HashMap::from([("decisions[0]".into(),item)]);
    edits.get_mut("decisions[0]").unwrap().evidence.pop();
    assert!(retain_verified_later_settings(&verified,&[row],&known,&mut edits).is_empty());
}

#[cfg(test)]
#[test]
fn later_confirmation_keeps_the_original_subject_and_source_order() {
    let source = vec![
        json!({"id":"e0000","text":"说话人1: 主色调当时定红色。"}),
        json!({"id":"e0001","text":"说话人1: 主色调现在可以考虑蓝色。"}),
        json!({"id":"e0002","text":"说话人2: 有关休息区地板我们已经确定用浅灰。"}),
        json!({"id":"e0003","text":"说话人1: 这个主色调我们刚刚已经确定了，是棕色加些红色。"}),
    ];
    let positions = source.iter().enumerate().map(|(i,row)| (row["id"].as_str().unwrap(),i)).collect();
    let claims = [json!({"path":"topics[0].points[0]","text":"主色调可考虑蓝色。"}),
        json!({"path":"topics[0].points[1]","text":"地板已确定浅灰。"}),
        json!({"path":"topics[0].points[2]","text":"已确定主色调为棕色加一些红色。"})];
    let bound = HashMap::from([("topics[0].points[0]".into(),vec!["e0001".into()]),
        ("topics[0].points[1]".into(),vec!["e0002".into()]),
        ("topics[0].points[2]".into(),vec!["e0003".into()])]);
    assert_eq!(later_decision_evidence("先确定主色调为红色。",&["e0000".into()],&source,&positions,&claims,&bound),[3]);
    assert!(later_decision_evidence("确定主色调棕色加红色。",&["e0003".into()],&source,&positions,&claims,&bound).is_empty());
    assert!(explicit_stance("咱这种不必要限时", "明确不对顾客限时"));
    assert!(!explicit_stance("咱这种不必要限时", "同意开始限时"));
    assert!(!explicit_stance("咱这种也可以不必要限时", "明确不对顾客限时"));
    assert!(!explicit_stance("咱这种不必要限时", "确认不要降价"));
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


#[cfg(test)]
#[test]
fn a_second_meeting_time_does_not_become_an_existing_tasks_deadline() {
    let evidence = [
        json!({"id":"e0010","text":"回去赶紧出方案。"}),
        json!({"id":"e0011","text":"然后下周二的时候我们再具体确定一下。"}),
    ];
    let known: HashMap<_, _> = evidence.iter().map(|row| (row["id"].as_str().unwrap(), row)).collect();
    let ids = known.keys().copied().collect();
    let original = json!({"claim":{"kind":"action","text":"回去赶紧出方案，下周二再具体确定。","owner":null,"due":null},
        "basis":["e0010","e0011"],"context":["e0010","e0011"]});
    let proposal = |text| serde_json::from_value(json!({"id":"actionItems[0]","replacement":{"role":"action",
        "text":text,"owner":null,"due":"下周二","evidence":["e0010","e0011"]}})).unwrap();
    let kept = bind_edit(proposal("回去赶紧出方案，下周二再具体确定。"), &original, &known, &ids).unwrap().unwrap();
    assert_eq!(kept.due, None);
    assert!(bind_edit(proposal("回去赶紧出合同，下周二再具体确定。"), &original, &known, &ids).is_err());
}
