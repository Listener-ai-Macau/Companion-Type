//! Recheck commitments and execution details against the cited turns before delivery.
use std::{collections::{HashMap, HashSet}, sync::LazyLock, time::Instant};

use serde::Deserialize;
use serde_json::{Value, json};

use super::{Action, Document, Entry, Kind, Unit, answer_layout::Placement, factual_audit, source_items};

const PROMPT: &str = include_str!("automatic_brief_commitments.txt");

fn needs_review(claim: &Value, cited: &[&str]) -> bool {
    let path = claim["path"].as_str().unwrap();
    if path.starts_with("actionItems[") || path.starts_with("decisions[") {
        return true;
    }
    static ASSIGNMENT: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:到时候|会后|下去以后|散会后|你们?|得|要).{0,38}(?:具体.{0,6}计划|计划.{0,5}(?:写|充分)|写.{0,10}(?:计划|方案)|主抓|交给|提交)"
    ).unwrap());
    static TIME: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:接下来|未来|打算|计划|准备).{0,24}(?:半年|[一二两三四五六七八九十0-9]{1,4}(?:年|个?月))"
    ).unwrap());
    let text = claim["text"].as_str().unwrap();
    let stated_possibility = ["建议", "拟", "考虑", "可以", "提议", "设想", "备选", "待核实"]
        .iter().any(|term| text.contains(term));
    cited.iter().any(|quote| ASSIGNMENT.is_match(quote) || TIME.is_match(quote)
        || (!stated_possibility && ["可以采用", "也可以", "我觉得可以", "我建议", "还可考虑"]
            .iter().any(|cue| quote.contains(cue))))
}

fn candidates(doc: &factual_audit::VerifiedBrief, source: &[Value]) -> Vec<Value> {
    let positions: HashMap<_, _> = source.iter().enumerate()
        .map(|(index, row)| (row["id"].as_str().unwrap(), index)).collect();
    let mut candidates = Vec::new();
    for claim in factual_audit::claims(&doc.document) {
        let path = claim["path"].as_str().unwrap();
        if claim.get("sources").is_none() || path.starts_with("questions[") { continue; }
        let Some(ids) = doc.evidence.get(path) else { continue; };
        let cited: Vec<_> = ids.iter().filter_map(|id| positions.get(id.as_str()))
            .map(|index| source[*index]["text"].as_str().unwrap()).collect();
        if !needs_review(&claim, &cited) { continue; }
        let mut context = Vec::new();
        for index in ids.iter().filter_map(|id| positions.get(id.as_str())) {
            // Keep both sides of the turn boundary. The surrounding turn can
            // identify an addressee, but it is never on its own an assignment.
            context.extend(index.saturating_sub(6)..(*index + 4).min(source.len()));
        }
        context.sort_unstable();
        context.dedup();
        let context: Vec<_> = context.into_iter().map(|index| &source[index]["id"]).collect();
        candidates.push(json!({"id":path,"claim":claim,"basis":ids,"context":context}));
    }
    candidates
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Response {
    #[serde(rename = "roleChecks")]
    role_checks: Vec<Check>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Check {
    id: String,
    replacement: Option<source_items::SourceItem>,
}

fn apply(doc: &Document, candidates: &[Value], source: &[Value], raw: &str, units: &[Unit]) -> Result<Document, String> {
    let fail = || "纪要负责人或决定的定向核对没有返回完整证据，已有结果保留。".to_string();
    let response: Response = serde_json::from_str(super::super::strip_code_fences(raw).trim()).map_err(|_| fail())?;
    if response.role_checks.len() != candidates.len() { return Err(fail()); }
    let mut by_id: HashMap<_, _> = candidates.iter().map(|row| (row["id"].as_str().unwrap(), row)).collect();
    let known: HashMap<_, _> = source.iter().map(|s| (s["id"].as_str().unwrap(), s)).collect();
    let known_ids = known.keys().copied().collect();
    let mut work = serde_json::to_value(doc).map_err(|_| fail())?;
    let mut removals = Vec::new();
    let mut additions = Vec::new();
    for check in response.role_checks {
        let original = by_id.remove(check.id.as_str()).ok_or_else(fail)?;
        let Some(item) = check.replacement else { continue; };
        let (owner, due) = (item.owner.clone(), item.due.clone());
        let fact = item.bind(&known, &known_ids)?;
        let context: HashSet<_> = original["context"].as_array().unwrap().iter().filter_map(Value::as_str).collect();
        if fact.evidence.iter().any(|id| !context.contains(id.as_str()))
            || !fact.evidence.iter().any(|id| original["basis"].as_array().unwrap().iter().any(|value| value.as_str() == Some(id.as_str())))
            || (fact.placement == Placement::Action && (owner != fact.owner || due != fact.due)) {
            return Err(fail());
        }
        if fact.placement == Placement::Question && !fact.text.contains("待核实") {
            return Err(fail());
        }
        let mut sources: Vec<_> = fact.evidence.iter().map(|id| known[id.as_str()]["source"].as_str().unwrap().to_owned()).collect();
        sources.sort_unstable();
        sources.dedup();
        let path = &check.id;
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
    let source = factual_audit::evidence_sentences(units);
    let review = candidates(&verified, &source);
    if review.is_empty() { return Ok(verified.document); }
    let selected: HashSet<_> = review.iter().flat_map(|item| item["context"].as_array().unwrap().iter())
        .filter_map(Value::as_str).collect();
    let quotes: Vec<_> = source.iter().filter(|row| selected.contains(row["id"].as_str().unwrap())).collect();
    let raw = super::request(endpoint,model,key,client,PROMPT,json!({"roleChecks":review,"sourceSentences":quotes}),
        false,start,trace,"source-commitment-review")?;
    if std::env::var_os("COMPANION_TYPE_AUTOMATIC_BRIEF_TRACE_PATH").is_some() {
        if let Some(call) = trace.last_mut() {
            call["priorEvidence"] = json!(&verified.evidence);
        }
    }
    let improved = apply(&verified.document, &review, &source, &raw, units)?;
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
