//! Source-bound follow-ups are recorded before the reader chooses highlights.
//! A spoken condition stays with its assignment and does not become a due date.
use std::{collections::HashSet, sync::LazyLock};

use regex::Regex;
use serde_json::Value;

use super::super::{canonical_brief, source_resolution::{self_introduced_identity, split_turn_label}};
use crate::companion_v1::CompanionV1ActionItem;

pub(super) struct BoundCommitment {
    pub(super) item: CompanionV1ActionItem,
    pub(super) continuation: Option<usize>,
}

const ROLES: &[&str] = &[
    "市场", "运营", "后勤", "财务", "销售", "研发", "设计", "施工", "技术", "采购", "客服",
    "行政", "项目", "质量", "人事", "生产", "安保", "大堂", "法务", "仓储", "交付", "管理",
];
const SOFT: &[&str] = &[
    "我觉得", "我想", "我建议", "希望", "建议", "可能", "大概", "考虑", "打算", "拟定",
    "可以", "未确认", "没有确认", "没决定", "不一定", "要不要", "能不能", "是否",
    "举例", "比如", "例如", "假设", "假如", "曾说", "说过", "听说", "转述",
];
const CONTEXT: &[&str] = &["如果", "若是", "只有", "一旦", "除非", "等到"];
const NEGATION: &[&str] = &["不用", "无需", "不必", "不再", "不会", "不能", "取消", "没有安排"];

fn contains(text: &str, choices: &[&str]) -> bool {
    choices.iter().any(|choice| text.contains(choice))
}

fn split(value: &Value) -> (Option<&str>, &str) {
    let text = value["text"].as_str().expect("source sentence").trim();
    split_turn_label(text).map_or((None, text), |(label, words)| (Some(label), words.trim()))
}

fn backchannel(text: &str) -> bool {
    text.chars().all(|ch| ch.is_whitespace() || matches!(ch,
        '嗯' | '哦' | '呃' | '啊' | '对' | '好' | '，' | ',' | '。' | '！' | '.'))
}

fn complete_piece(text: &str) -> bool {
    let tail = text.trim_end_matches(['，', ',', '。', '！', ' ']);
    tail.chars().count() >= 4
        && !["然后", "还有", "就是", "就是要", "的一些", "室内的", "去做的", "这个", "那个", "方面的"]
            .iter().any(|fragment| tail.ends_with(fragment))
}

pub(super) fn meeting_actor_labels(sentences: &[Value]) -> HashSet<&str> {
    sentences.iter().take(80).filter_map(|sentence| {
        let (speaker, text) = split(sentence);
        let label = speaker?;
        let role = self_introduced_identity(text)?;
        ROLES.iter().any(|name| role.contains(name)).then_some(label)
    }).collect()
}

fn actionable(phrase: &str) -> bool {
    static VERB: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"^(?:\s|[呃嗯就先也再将把去]|及时|马上|尽快|提前|继续|时刻|专门|负责|进行|直接|一定){0,11}(?:(?:与|和|跟)[^，,。！？；;]{1,22}?)?(?:协商|安排|协调|推进|提交|汇报|通知|起草|发出|发送|交付|交给|报给|登记|提供|核查|核对|核实|检查|确认|复核|整改|完成|处理|回复|整理|准备|联系|对接|沟通|协助|组织|上报|走访|投标|报名|关注|跟进|找|发给|签约|采购|培训|检测|调试|录入|上线|修改|加强|换回|接手|撤回|补齐|交接)"
    ).expect("future operational verbs"));
    if VERB.is_match(phrase) {
        return true;
    }
    let trimmed = phrase.trim_start_matches(['嗯', '啊', '对', '，', ',', ' ']);
    if trimmed != phrase && VERB.is_match(trimmed) {
        return true;
    }
    let prefix = trimmed.strip_prefix('把').or_else(|| trimmed.strip_prefix("先把"));
    prefix.is_some_and(|body| {
        body.char_indices().take(24).skip(2).any(|(offset, _)| {
            !body[..offset].contains(['，', ',', '。']) && VERB.is_match(&body[offset..])
        })
    })
}

fn explicit_speaker(lead: &str, modal: &str) -> Option<Option<String>> {
    let before = lead.trim_end_matches(['，', ',', ' ']);
    if let Some(role) = ROLES.iter().copied().find(|role| {
        ["这边", "这边儿", "部这边", "部这边儿", "组这边", "组这边儿",
         "部门这边", "部门这边儿", "部", "组", ""].iter().any(|suffix| {
            let plain = format!("{role}{suffix}");
            [plain.clone(), format!("{plain}也"), format!("{plain}就"), format!("{plain}我")]
                .iter().any(|ending| before.ends_with(ending))
        })
    }) {
        if ["他们", "她们", "供应商", "客户", "对方"].iter().any(|word| before.contains(word))
            && !contains(before, &["我们", "咱们"]) {
            return None;
        }
        let owner = ["部门", "部", "组"].into_iter().map(|suffix| format!("{role}{suffix}"))
            .find(|name| before.contains(name)).unwrap_or_else(|| role.to_owned());
        return Some(Some(owner));
    }
    // Generic first-person promises can have an action without a confirmed owner.
    if ["我们", "咱们", "我这边", "我们这边", "我们这边儿", "咱们这边", "咱们这边儿",
        "我就", "我们就", "咱们就", "我们也", "咱们也", "我来", "我负责", "我们负责"]
        .iter().any(|actor| before.ends_with(actor))
        || (before.ends_with('我') && ["会", "来", "负责"].contains(&modal))
    {
        return Some(None);
    }
    None
}

fn conditional_clause(text: &str) -> Option<&str> {
    text.split(['，', ',']).rev().map(str::trim).find(|part| contains(part, CONTEXT))
}

fn scoped_commitment(body: &str, institutional_voice: bool) -> Option<CompanionV1ActionItem> {
    static MODAL: LazyLock<Regex> =
        LazyLock::new(|| Regex::new(r"一定会|会|将|来负责|负责").expect("spoken commitment"));
    let body = body.trim_end_matches(['。', '！', '，', ',', ' ']);
    if body.contains(['？', '?']) || contains(body, &["曾经", "当时", "实际上已经",
        "常规就是", "通常", "往年", "刚才说过", "已完成", "已经完成"])
    {
        return None;
    }
    let clauses: Vec<_> = body.split(['，', ',', '。', '；', ';']).map(str::trim).collect();
    let mut candidates = Vec::new();
    for (index, clause) in clauses.iter().enumerate() {
        if contains(clause, SOFT) || contains(clause, NEGATION)
            || index.checked_sub(1).is_some_and(|previous| {
                contains(clauses[previous], &["举例", "比如", "例如", "假设", "如果说有人", "听说", "转述", "你建议"])
            })
        {
            continue;
        }
        for commitment in MODAL.find_iter(clause) {
            let before = &clause[..commitment.start()];
            let followup = clause[commitment.end()..].trim_start();
            let has_operation = actionable(followup)
                || (followup.starts_with(['跟', '和', '与'])
                    && clauses.iter().skip(index + 1).take(2)
                        .take_while(|part| !contains(part, SOFT) && !contains(part, NEGATION))
                        .any(|part| actionable(part)));
            if contains(before, CONTEXT) || !has_operation {
                continue;
            }
            let Some(mut owner) = explicit_speaker(before, commitment.as_str()) else {
                continue;
            };
            if owner.is_none() && !institutional_voice
                && !contains(body, &["会后", "散会后", "下周", "明天", "后天", "截止", "下次会议"])
                && candidates.is_empty()
            {
                continue;
            }
            // A first-person continuation in the same speech can carry the
            // already stated department without treating a recipient as owner.
            if owner.is_none() {
                owner = candidates.iter().rev().take(1)
                    .find_map(|(_, _, actor): &(usize, Option<&str>, Option<String>)| actor.clone());
            }
            let condition = index.checked_sub(1).and_then(|previous| {
                let context = clauses[previous];
                conditional_clause(context).filter(|part| !contains(part, &["哈哈", "举例", "建议", "假设"]))
            });
            candidates.push((index, condition, owner));
            break;
        }
    }
    let (first, first_condition, owner) = candidates.first()?;
    let last = candidates.iter().take_while(|(index, _, actor)| {
        *index <= first + 2 && (actor == owner || actor.is_none() || owner.is_none())
    }).last()?.0;
    let end = clauses.iter().enumerate().skip(last + 1).take(3)
        .take_while(|(_, part)| !contains(part, SOFT) && !contains(part, NEGATION))
        .take_while(|(_, part)| backchannel(part) || actionable(part)
            || contains(part, &["的时候儿会把", "的时候会把", "然后"]))
        .last().map_or(last, |(index, _)| index);
    let first = if first_condition.is_some() { first - 1 } else { *first };
    let mut tail = end;
    if clauses[tail].is_empty() { tail = tail.checked_sub(1)?; }
    let text = clauses[first..=tail].iter().filter(|s| !s.is_empty()).copied().collect::<Vec<_>>().join("，");
    let text = text.trim_end_matches(['，', ',', ' ']).trim_end_matches("然后").trim_end_matches(['，', ',', ' ']).trim();
    // The full trigger must fit with the action. Partial matches are kept in
    // the original transcript, not shortened into unconditional tasks.
    if !complete_piece(text) || !canonical_brief::line(text, 90) {
        return None;
    }
    Some(CompanionV1ActionItem { text: text.into(), owner: owner.clone(), due: None })
}

fn agreed_handoff(text: &str) -> Option<CompanionV1ActionItem> {
    static HANDOFF: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"^(?:行|好的|好)[，,]\s*(?:那么|那就|那)?(?P<record>[^，,。！？；;]{2,34}?(?:准备好|写好|完成|确认|审核通过|回来|结束|确定下来|下来)(?:了)?(?:以后|之后|后)[，,]?\s*(?:就|再)(?:由[^，,。！？；;]{1,14})?(?:交给|转给|提交给|发给)[^，,。！？；;]{2,34})"
    ).expect("agreed source handoff"));
    let m = HANDOFF.captures(text)?;
    let literal = m.name("record")?.as_str();
    let end = ["昂然后", "啊然后", "然后", "咱再说"].iter()
        .filter_map(|tail| literal.find(tail)).min().unwrap_or(literal.len());
    let body = literal[..end].trim();
    if contains(body, SOFT) || contains(body, NEGATION) || !canonical_brief::line(body, 90) {
        return None;
    }
    Some(CompanionV1ActionItem { text: body.into(), owner: None, due: None })
}

pub(super) fn at(sentences: &[Value], index: usize, linked_actors: &HashSet<&str>) -> Option<BoundCommitment> {
    let (speaker, first) = split(&sentences[index]);
    let institutional_voice = speaker.is_some_and(|label| linked_actors.contains(label));
    let mut linked = None;
    if let Some(label) = speaker {
        let unfinished = first.trim_end_matches(['，', ',', '。', '！', ' ']);
        if unfinished.ends_with("然后") || unfinished.ends_with('的') {
            let mut offered_object = false;
            for next in index + 1..=(index + 2).min(sentences.len() - 1) {
                let (next_speaker, fragment) = split(&sentences[next]);
                if backchannel(fragment) {
                    continue;
                }
                if next_speaker != Some(label) && unfinished.ends_with('的')
                    && fragment.trim_end_matches(['。', '，', ',', ' ']).chars().count() <= 15
                    && !fragment.contains(['？', '?']) {
                    offered_object = true;
                    continue;
                }
                if next_speaker == Some(label) && (!offered_object || fragment.starts_with('对'))
                    && !contains(fragment, SOFT)
                    && !contains(fragment, NEGATION) && !fragment.contains(['？', '?'])
                    && (actionable(fragment) || contains(fragment, &["的时候", "前会", "会把", "以前", "先", "以后"]))
                {
                    linked = Some((next, fragment));
                }
                break;
            }
        }
    }
    if let Some((next, tail)) = linked {
        let joined = format!("{}，{tail}", first.trim_end_matches(['，', ',', '。', '！', ' ']));
        if let Some(mut item) = scoped_commitment(&joined, institutional_voice) {
            // The second part may supply a date or the practical completion
            // step. Do not merge it if the validated action did not use it.
            if !item.text.contains(tail.trim_end_matches(['。', '！', '，', ',', ' '])) {
                if canonical_brief::line(&joined, 90) && complete_piece(tail) {
                    item.text = joined;
                } else {
                    return None;
                }
            }
            return Some(BoundCommitment { item, continuation: Some(next) });
        }
    }
    let item = agreed_handoff(first).or_else(|| scoped_commitment(first, institutional_voice))?;
    Some(BoundCommitment { item, continuation: None })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn sentences(rows: &[&str]) -> Vec<Value> {
        rows.iter().enumerate().map(|(i, text)| json!({
            "id":format!("e{i:04}"), "source":"u000", "text":text
        })).collect()
    }

    #[test]
    fn preserves_a_confirmed_trigger_and_the_department_in_one_action() {
        let rows = sentences(&[
            "说话人4: 我们市场这边也会时刻关注各大银行的官网，如果有招标信息发布的话，我们会及时投标。",
        ]);
        let result = at(&rows, 0, &meeting_actor_labels(&rows)).expect("explicit conditional commitment");
        assert_eq!(result.item.owner.as_deref(), Some("市场"));
        assert!(result.item.text.contains("关注各大银行的官网")
            && result.item.text.contains("如果有招标信息发布的话，我们会及时投标"));
        assert!(result.item.due.is_none());
    }

    #[test]
    fn joins_the_same_owner_across_an_acknowledgment_with_original_timing() {
        let rows = sentences(&[
            "说话人5: 啊运营这边儿会和后勤这边儿提前协商好看婚车多少辆然后",
            "说话人1: 嗯",
            "说话人5: 位置提前咱们彩排的时候儿会把这些都安排",
        ]);
        let result = at(&rows, 0, &meeting_actor_labels(&rows)).expect("same-speaker continuation");
        assert_eq!(result.continuation, Some(2));
        assert_eq!(result.item.owner.as_deref(), Some("运营"));
        assert!(result.item.text.contains("婚车多少辆") && result.item.text.contains("彩排的时候儿"));
        assert!(result.item.due.is_none());
    }

    #[test]
    fn agreed_handoff_has_a_condition_but_the_receiver_is_not_the_sender() {
        let rows = sentences(&["说话人7: 行，那剧本写好以后就交给角色设计了昂然后再研究别的事。"]);
        let result = at(&rows, 0, &meeting_actor_labels(&rows)).unwrap();
        assert_eq!(result.item.text, "剧本写好以后就交给角色设计了");
        assert!(result.item.owner.is_none() && result.item.due.is_none());
    }

    #[test]
    fn suggestions_case_examples_and_forecasts_do_not_create_new_work() {
        let rows = sentences(&[
            "说话人1: 我建议会后找合作伙伴沟通问题。",
            "说话人2: 比如如果图纸交了，我们市场会及时投标。",
            "说话人3: 如果我们会提交文件那今天就能处理。",
            "说话人4: 我会安排人员和设备，这个例子里是这样。",
            "说话人5: 下周我们这边可能会采购新的设备。",
            "说话人6: 听说他们运营这边会处理材料。",
            "说话人7: 市场部会有明显增长。",
        ]);
        let labels = meeting_actor_labels(&rows);
        assert!((0..rows.len()).all(|i| at(&rows, i, &labels).is_none()));
    }
}
