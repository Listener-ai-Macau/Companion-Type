//! Preserve wording supported by an explicit speaker, proposal, or assignment.
use std::collections::{HashMap, HashSet};
use serde_json::Value;
use super::{Kind, answer_layout::{Fact, Placement}, line, normalized};

pub(super) struct SourceBindings<'a> {
    by_id: HashMap<&'a str, &'a Value>,
    names: HashMap<&'a str, &'a str>,
}

struct Assignment<'a> {
    owner: &'a str,
    clause: &'a str,
}

impl<'a> SourceBindings<'a> {
    pub(super) fn new(source: &'a [Value]) -> Self {
        let by_id = source.iter().map(|row| (row["id"].as_str().unwrap(), row)).collect();
        let mut names = HashMap::new();
        let mut contested = HashSet::new();
        for row in source.iter().take(24) {
            let Some(speaker) = row["turnSpeaker"].as_str() else { continue; };
            let text = row["text"].as_str().unwrap();
            let Some((_, name)) = text.split_once("我是") else { continue; };
            let name = name.trim().trim_end_matches(['。', '！']);
            if !(2..=14).contains(&name.chars().count()) || !name.chars().all(|c| ('㐀'..='鿿').contains(&c)) {
                continue;
            }
            if names.insert(speaker, name).is_some_and(|former| former != name) {
                contested.insert(speaker);
            }
        }
        names.retain(|speaker, _| !contested.contains(speaker));
        Self { by_id, names }
    }

    pub(super) fn correct_attribution(&self, fact: &mut Fact) -> Option<(String, String)> {
        if fact.placement != Placement::Topic {
            return None;
        }
        let source: Vec<_> = fact.evidence.iter().map(|id| self.by_id.get(id.as_str()).copied())
            .collect::<Option<_>>()?;
        let speaker = source.first()?["turnSpeaker"].as_str()?;
        if source.iter().any(|row| row["turnSpeaker"].as_str() != Some(speaker)) {
            return None;
        }
        let actual = *self.names.get(speaker)?;
        let claimed = self.names.values().copied().filter(|name| fact.text.starts_with(name))
            .max_by_key(|name| name.len())?;
        let suffix = &fact.text[claimed.len()..];
        if actual == claimed || source.iter().any(|row| row["text"].as_str().unwrap().contains(claimed)) {
            return None;
        }
        let first_person = source.iter().any(|row| {
            let text = row["text"].as_str().unwrap();
            ["我们", "我园", "本校", "本组"].iter().any(|cue| text.contains(cue))
        });
        let attribution = ["反映", "表示", "称", "介绍", "指出"].iter().any(|cue| suffix.starts_with(cue));
        if !first_person && !attribution {
            return None;
        }
        let corrected = format!("{actual}{suffix}");
        if !line(&corrected, 90) {
            return None;
        }
        fact.text = corrected;
        Some((claimed.to_owned(), actual.to_owned()))
    }

    fn assignments(&self, id: &str) -> Option<[Assignment<'a>; 2]> {
        let row = self.by_id.get(id).copied()?;
        let utterance = row["text"].as_str()?.trim();
        let mut roles = Vec::new();
        for name in self.names.values() {
            let Some(team) = name.strip_suffix("部门").or_else(|| name.strip_suffix('部'))
                else { continue; };
            let found = ["这边儿", "这一块儿", "这块儿", "这边", "这一块", "这块"]
                .into_iter().find_map(|suffix| {
                    let marker = format!("{team}{suffix}");
                    utterance.find(&marker).map(|start| (start, marker.len()))
                });
            if let Some(found) = found {
                roles.push(found);
            }
        }
        roles.sort_unstable();
        roles.dedup();
        let [(first, first_len), (second, second_len)] = roles.as_slice() else { return None; };
        let first_end = first + first_len;
        if first_end >= *second {
            return None;
        }
        let prefix = &utterance[..*first];
        if ["如果", "假设", "要不要", "能不能"].iter().any(|cue| prefix.contains(cue)) {
            return None;
        }
        let first_clause = &utterance[first_end..*second];
        let separator = ["还有刚才", "然后对于", "接下来", "另由", "同时由"]
            .iter().filter_map(|cue| first_clause.find(cue)).min()?;
        let second_end = second + second_len;
        let candidate = [
            Assignment { owner: &utterance[*first..first_end], clause: first_clause[..separator].trim() },
            Assignment { owner: &utterance[*second..second_end], clause: utterance[second_end..].trim() },
        ];
        let direct = |clause: &str| line(clause, 89)
            && ["进行", "负责", "做", "提交", "核实", "准备", "完成"].iter().any(|cue| clause.contains(cue))
            && !["不要", "不用", "无需", "如果", "还是", "能不能"].iter().any(|cue| clause.contains(cue));
        candidate.iter().all(|binding| direct(binding.clause)).then_some(candidate)
    }

    pub(super) fn is_separate_assignment(&self, claim: &Value, evidence: &[String]) -> bool {
        let (Some(owner), Some(text)) = (claim["owner"].as_str(), claim["text"].as_str()) else { return false; };
        evidence.iter().filter_map(|id| self.assignments(id)).flatten()
            .any(|assignment| {
                owner == assignment.owner
                    && normalized(text.trim_end_matches('。')) == normalized(assignment.clause.trim_end_matches('。'))
            })
    }

    pub(super) fn split_assignments(&self, facts: &mut Vec<Fact>) -> Vec<String> {
        let mut replaced = HashSet::new();
        let mut output = Vec::with_capacity(facts.len());
        let mut observations = Vec::new();
        for fact in facts.drain(..) {
            let split = (fact.placement == Placement::Action && fact.owner.is_none() && fact.due.is_none())
                .then(|| fact.evidence.iter().find_map(|id| {
                    let bindings = self.assignments(id)?;
                    let compound = ["分别", "各自", "两项"].iter().any(|cue| fact.text.contains(cue))
                        || bindings.iter().all(|part| fact.text.contains(part.owner.trim_end_matches(['儿', '边', '块', '这'])));
                    compound.then_some((id, bindings))
                })).flatten();
            let Some((id, bindings)) = split else { output.push(fact); continue; };
            // Keep original constraints in the same brief. There is no
            // authority to assign a shared cost condition to only one team.
            let has_cost = fact.text.contains("成本");
            let cost = fact.evidence.iter().find_map(|id| {
                let text = self.by_id.get(id.as_str())?["text"].as_str()?.trim();
                if !text.contains("成本") { return None; }
                let quote = text.split_once("还有").map_or(text, |(head, _)| head);
                line(quote, 53).then_some((id, quote))
            });
            if has_cost && cost.is_none() {
                output.push(fact);
                continue;
            }
            if !replaced.insert(id.clone()) {
                continue;
            }
            observations.push(id.clone());
            for (index, part) in bindings.into_iter().enumerate() {
                let text = format!("{}。", part.clause.trim_end_matches('。'));
                output.push(Fact { id: format!("{}-{}", fact.id, index + 1), kind: Kind::Decision,
                    placement: Placement::Action, text, owner: Some(part.owner.to_owned()), due: None,
                    evidence: vec![id.clone()] });
            }
            if let Some((cost_id, quote)) = cost.filter(|_| has_cost) {
                output.push(Fact { id: format!("{}-cost", fact.id), kind: Kind::Status, placement: Placement::Topic,
                    text: format!("会上另提到「{quote}」，各方案的成本要求待核实。"), owner: None, due: None,
                    evidence: vec![id.clone(), cost_id.clone()] });
            }
        }
        *facts = output;
        observations
    }
}

pub(super) fn mark_proposal(fact: &mut Fact) -> bool {
    if !matches!(fact.kind, Kind::Recommendation)
        || ["建议", "提议", "提出", "设想", "可考虑", "待定"].iter().any(|cue| fact.text.contains(cue))
    {
        return false;
    }
    let marked = format!("会上曾建议：{}", fact.text);
    if !line(&marked, 90) {
        return false;
    }
    fact.text = marked;
    true
}
