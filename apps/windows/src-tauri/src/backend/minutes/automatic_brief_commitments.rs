//! Recheck commitments and execution details against the cited turns before delivery.
use std::{collections::{HashMap, HashSet}, sync::LazyLock, time::Instant};

use serde::Deserialize;
use serde_json::{Value, json};

use super::{Action, Document, Entry, Kind, Unit, answer_layout::{Fact, Placement}, factual_audit, source_items};

const PROMPT: &str = include_str!("automatic_brief_commitments.txt");
const INCOMPLETE: &str = "纪要定向核对没有返回完整证据，已有结果保留。";

fn with_turn_labels(source: &[Value]) -> Vec<Value> {
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
    let mut candidates = Vec::new();
    for claim in factual_audit::claims(&doc.document) {
        let path = claim["path"].as_str().unwrap();
        if claim.get("sources").is_none() || path.starts_with("questions[") { continue; }
        let Some(ids) = doc.evidence.get(path) else { continue; };
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

fn preserve_assigned_action(original: &Value, fact: &Fact) -> bool {
    let claim = &original["claim"];
    claim["kind"] == "action" && fact.placement == Placement::Action && (
        (fact.owner.is_none() && !claim["owner"].is_null())
        || (fact.due.is_none() && !claim["due"].is_null())
        || (fact.owner.is_none() && fact.text.contains("待核实"))
    )
}

type SourceIndex<'a> = HashMap<&'a str, &'a Value>;

fn bind_edit(check: Check, original: &Value, known: &SourceIndex<'_>, known_ids: &HashSet<&str>) -> Result<Option<Fact>, &'static str> {
    let context: HashSet<_> = original["context"].as_array().unwrap().iter().filter_map(Value::as_str).collect();
    let basis: HashSet<_> = original["basis"].as_array().unwrap().iter().filter_map(Value::as_str).collect();
    let allowed = |id: &str| factual_audit::canonical_sentence_reference(id, known_ids)
        .filter(|id| context.contains(id.as_str()));
    let fact = match (check.replacement, check.clarification, check.owner_evidence) {
        (None, None, None) => return Ok(None),
        (Some(mut item), None, owner_evidence) => {
            let requested = item.owner.clone();
            let due = item.due.clone();
            let evidence_ids: HashSet<_> = item.evidence.iter()
                .filter_map(|id| factual_audit::canonical_sentence_reference(id, known_ids)).collect();
            if !evidence_ids.iter().any(|id| basis.contains(id.as_str())) {
                return Err("任务缺少 basis 中说明原事项的句子。承接者发言不能代替任务原话。");
            }
            if let Some(proof) = owner_evidence {
                let proof = allowed(&proof).ok_or("ownerEvidence 不在本条相邻原话中。")?;
                let owner = requested.as_deref().ok_or("ownerEvidence 需要对应明确的 owner。")?;
                let quote = known[proof.as_str()]["text"].as_str().unwrap();
                if !super::normalized(quote).contains(&super::normalized(owner))
                    && spoken_department(owner, std::iter::once(quote)).is_none() {
                    return Err("ownerEvidence 未出现所填负责人。请区分承接者、主持人和附近讨论者。");
                }
                if !evidence_ids.contains(&proof) { item.evidence.push(proof); }
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
    if rows.is_empty() { return Ok(verified.document); }
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
    let improved = apply(&verified.document, &rows, bound.accepted, &known, units)?;
    factual_audit::review_and_repair_since(endpoint,model,key,client,&improved,units,Some(&verified.document),start,trace)
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
