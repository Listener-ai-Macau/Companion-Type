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

fn literal_scope(quote: &str, statement: &str) -> Option<&'static str> {
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
    for (index, check) in checks.iter_mut().enumerate() {
        check["id"] = json!(format!("s{index:03}"));
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
    json!({"kind":kind,"requiredEvidence":required.into_iter().map(|index| &source[index]["id"]).collect::<Vec<_>>(),
           "context":context.iter().map(|row| &row["id"]).collect::<Vec<_>>(),"claim":claim})
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

fn apply_scope(
    mut doc: Document,
    raw: &str,
    checks: &[Value],
    units: &[Unit],
    source: &[Value],
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
    for reply in response.scope_checks {
        let check = pending.remove(reply.id.as_str()).ok_or_else(fail)?;
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
        if check["kind"] == "ambiguousReference" && !fact.text.contains("待核实") {
            return Err(fail());
        }
        if check["kind"] == "narrowedConclusion"
            && !["强迫", "胁迫", "违背", "不愿"]
                .iter()
                .any(|term| fact.text.contains(term))
        {
            return Err(fail());
        }
        if let Some(path) = check["claim"]["path"].as_str() {
            let mut seen = HashSet::new();
            let sources = fact
                .evidence
                .iter()
                .map(|id| known[id.as_str()]["source"].as_str().unwrap())
                .filter(|id| seen.insert(*id))
                .map(str::to_owned)
                .collect();
            replacements.push((
                path.to_owned(),
                Entry {
                    text: fact.text,
                    sources,
                    quantity_needs_review: false,
                },
            ));
        } else {
            additions.push(MissingItem {
                item: reply.item,
                topic: reply.topic,
                new_aspect: None,
            });
        }
    }
    if !pending.is_empty() {
        return Err(fail());
    }
    if !replacements.is_empty() {
        let mut value = serde_json::to_value(doc).map_err(|_| fail())?;
        for (path, entry) in replacements {
            let pointer = format!(
                "/{}",
                path.replace('[', "/").replace(']', "").replace('.', "/")
            );
            let target = value.pointer_mut(&pointer).ok_or_else(fail)?;
            target["text"] = json!(entry.text);
            target["sources"] = json!(entry.sources);
        }
        doc = serde_json::from_value(value).map_err(|_| fail())?;
    }
    source_items::append_missing(additions, doc, units, source)
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
        let raw = super::request(
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
        apply_scope(doc, &raw, &checks, units, &source)?
    };
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
    };
    super::validate(&verified.document, &units).unwrap();
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
        verified.document.clone(),
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
