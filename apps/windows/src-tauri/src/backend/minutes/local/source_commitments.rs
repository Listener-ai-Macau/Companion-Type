//! Source-bound follow-ups are recorded before the reader chooses highlights.
//! A spoken condition stays with its assignment and does not become a due date.
use std::{collections::HashSet, sync::LazyLock};

use regex::Regex;
use serde_json::Value;

use super::super::{canonical_brief, source_resolution::{self_introduced_identity, split_turn_label}};
use crate::companion_v1::CompanionV1ActionItem;

pub(super) struct BoundCommitment {
    pub(super) item: CompanionV1ActionItem,
    pub(super) prerequisite: Option<usize>,
    pub(super) continuation: Option<usize>,
    pub(super) needs_review: bool,
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
const CONTEXT: &[&str] = &["如果", "要是", "若是", "只有", "一旦", "除非", "等到"];
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
        r"^(?:\s|[呃嗯就先也再将把去]|及时|马上|尽快|提前|继续|时刻|专门|负责|进行|直接|一定){0,11}(?:(?:与|和|跟)[^，,。！？；;]{1,22}?)?(?:协商|安排|协调|推进|提交|汇报|通知|起草|制定|制订|编制|做(?:一个|一份|出)|发出|发送|交付|交给|报给|登记|提供|核查|核对|核实|检查|确认|复核|整改|完成|处理|回复|整理|准备|联系|对接|沟通|协助|组织|上报|走访|投标|报名|关注|跟进|找|发给|签约|采购|培训|检测|调试|录入|上线|修改|加强|换回|接手|撤回|补齐|交接)"
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
    static SUFFIX: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:合格|通过|确认|批准|到货|同意|符合要求|验收|结束|满足|准备好)(?:儿|了)?(?:的话|以后|之后|后)"
    ).expect("spoken prerequisite suffix"));
    text.split(['，', ',']).rev().map(str::trim).find(|part| contains(part, CONTEXT) || SUFFIX.is_match(part))
}

/// Look back only within the speaker's continuation, allowing another speaker
/// to acknowledge it without taking ownership of the attached action.
fn prior_condition<'a>(sentences: &'a [Value], index: usize, action: &str) -> Option<(usize, &'a str, bool)> {
    if !["然后", "那", "所以", "之后", "再", "接着"].iter().any(|cue| action.starts_with(cue))
        && !contains(action, &["我们就", "咱们就", "我就", "我们再"]) {
        return None;
    }
    let (speaker, _) = split(&sentences[index]);
    let speaker = speaker?;
    for previous in (index.saturating_sub(4)..index).rev() {
        let (label, words) = split(&sentences[previous]);
        if backchannel(words) { continue; }
        if label != Some(speaker) || words.contains(['？', '?', '！', '!'])
            || contains(words, &["转述", "举例", "假设", "我建议", "听说"]) {
            break;
        }
        if let Some(condition) = conditional_clause(words) {
            let condition = condition.trim_end_matches(['，', ',', ' ']);
            let incomplete = !complete_piece(condition)
                || contains(condition, &["想想的", "如果就是说", "看行不行"]);
            return Some((previous, condition, incomplete));
        }
        // One short linking fragment is allowed, but a self-contained
        // assertion starts a different record.
        if !["这个", "那个", "然后", "嗯", "呃"].iter().any(|cue| words.starts_with(cue)) {
            break;
        }
    }
    None
}

fn attach_prerequisite(sentences: &[Value], index: usize, mut record: BoundCommitment) -> BoundCommitment {
    if conditional_clause(&record.item.text).is_some() { return record; }
    if let Some((previous, condition, incomplete)) = prior_condition(sentences, index, &record.item.text) {
        record.prerequisite = Some(previous);
        let full = format!("{condition}，{}", record.item.text);
        if !incomplete && canonical_brief::line(&full, 90) {
            record.item.text = full;
        } else {
            record.needs_review = true;
        }
    }
    record
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
                    .find_map(|(_, _, actor): &(usize, Option<usize>, Option<String>)| actor.clone());
            }
            // One prerequisite can govern an exchange and the action that
            // follows it. Retain both steps when the speaker joins them.
            let continued = ["然后", "接着", "再", "之后"].iter().any(|cue| clause.starts_with(cue));
            let lookback = if continued { 2 } else { 1 };
            let condition = (index.saturating_sub(lookback)..index).rev()
                .take_while(|&previous| !contains(clauses[previous], &["另一个", "另外", "回到", "换个"]))
                .find(|&previous| conditional_clause(clauses[previous]).is_some_and(|part|
                    !contains(part, &["哈哈", "举例", "建议", "假设"])));
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
            || contains(part, &["的时候儿会把", "的时候会把", "然后"])
            || part.starts_with("包括"))
        .last().map_or(last, |(index, _)| index);
    let first = first_condition.unwrap_or(*first);
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


pub(super) struct ConfirmedDelegation {
    pub(super) decision: String,
    pub(super) owner: String,
    pub(super) scope: String,
    pub(super) confirmation: usize,
    pub(super) followup: Option<(usize, CompanionV1ActionItem, Option<usize>)>,
    pub(super) dispute: Option<usize>,
}

fn role_of<'a>(sentences: &'a [Value], speaker: &str) -> Option<&'a str> {
    sentences.iter().take(80).find_map(|sentence| {
        let (label, body) = split(sentence);
        (label == Some(speaker)).then(|| self_introduced_identity(body)).flatten()
    })
}

fn meeting_lead(role: &str) -> bool {
    ["主持人", "负责人", "总经理", "总裁", "董事长", "主管", "组长", "主任", "校长", "副校长"]
        .contains(&role)
}

pub(super) fn meeting_roles(sentences: &[Value]) -> Vec<(usize, &str, &str)> {
    sentences.iter().take(80).enumerate().filter_map(|(index, sentence)| {
        let (speaker, text) = split(sentence);
        Some((index, speaker?, self_introduced_identity(text)?))
    }).collect()
}

pub(super) struct DirectedWork {
    pub(super) item: CompanionV1ActionItem,
    pub(super) support: Vec<usize>,
}

fn preceding_turn(sentences: &[Value], index: usize) -> Option<(usize, &str)> {
    (index.saturating_sub(3)..index).rev().find_map(|previous| {
        let (speaker, words) = split(&sentences[previous]);
        if words.chars().count() > 28 && speaker.is_none() { return None; }
        speaker.map(|speaker| (previous, speaker))
    })
}

fn explicit_agreement(words: &str) -> bool {
    let words = spread_trim(words);
    ["好", "好的", "行", "可以", "收到", "明白", "没问题"].contains(&words)
}

fn spread_trim(text: &str) -> &str {
    text.trim_matches([' ', '，', ',', '。', '！', '嗯', '呃', '啊'])
}

/// Keep the named recipients and each distinct deliverable when assignments
/// are spoken in one turn, and resolve a following "you" through its reply.
pub(super) fn directed_work(
    sentences: &[Value], index: usize, roles: &[(usize, &str, &str)],
) -> Vec<DirectedWork> {
    static DELIVERABLE: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:做|出|提交|形成|拟定|制定|编制|准备|写|进行|拿出)[^，,。！？；;]{0,26}?(?:计划书|计划|方案|报告|清单|时间表|预算表|财务表|记录|纪要)"
    ).expect("work deliverable"));
    static OPERATION: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"^(?:儿|呃|嗯|\s|就|也|再|先|来|要|需要|务必|具体|负责){0,12}(?:总结|整理|汇总|复核|核对|统计|主持)(?:一下儿?)?"
    ).expect("directed operation"));
    static CLOSING_OBJECT: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:下去以后|会后|散会后|回去以后)[^。！？；;]{0,18}?(?:各部门|各单位|各团队|各小组)(?:儿)?\s*(?P<work>把[^。！？；;，,]{2,28}?(?:拿出来|交上来|报上来|发过来))"
    ).expect("collective delivery"));
    let (speaker, words) = split(&sentences[index]);
    let inherited = speaker.is_none().then(|| preceding_turn(sentences, index)).flatten();
    let Some(speaker) = speaker.or_else(|| inherited.map(|(_, label)| label)) else { return Vec::new(); };
    if !meeting_lead(roles.iter().find(|(_, label, _)| *label == speaker).map_or(speaker, |(_, _, role)| *role))
        || contains(words, &["听说", "转述", "当时说", "示例"])
    {
        return Vec::new();
    }
    let future = contains(words, &["会后", "散会后", "下去以后", "下次", "到时候", "接下来", "随后"]);
    let mut addresses = Vec::new();
    // Roles are drawn from the actual introduction. A shortened role is
    // accepted only with a spoken address suffix.
    for &(intro, label, role) in roles.iter().filter(|(_, label, _)| *label != speaker) {
        let short = role.strip_suffix(['部', '组', '处']).unwrap_or(role);
        for alias in [role, short] {
            for (start, _) in words.match_indices(alias) {
                let tail = start + alias.len();
                if let Some(suffix) = ["这边儿", "这边", "这块儿", "这块", "那边儿", "那边"]
                    .into_iter().find(|suffix| words[tail..].starts_with(suffix))
                {
                    addresses.push((start, tail + suffix.len(), label, role, intro));
                }
            }
        }
    }
    addresses.sort_unstable_by_key(|x| (x.0, x.1));
    addresses.dedup();
    let mut work = Vec::new();
    for (address_index, &(start, after, recipient, owner, intro)) in addresses.iter().enumerate() {
        let end = addresses.get(address_index + 1).map_or(words.len(), |x| x.0);
        let fragment = &words[after..end];
        let clause = fragment.split(['。', '！', '？', '；']).next().unwrap_or(fragment);
        let (operation, position) = if let Some(op) = OPERATION.find(clause) {
            (op.as_str(), op.end())
        } else if let Some(op) = DELIVERABLE.find(clause) {
            (&clause[..op.end()], op.end())
        } else { continue; };
        let previous = words[..start].rsplit(['，', ',', '。', '！', '？', '；']).next().unwrap_or("");
        if contains(operation, SOFT) || contains(operation, CONTEXT) || contains(operation, NEGATION)
            || contains(previous, &["我建议", "比如", "如果", "假设", "如果由", "曾经", "只是在"])
            || clause[position..].trim_start().starts_with(['？', '?', '吗'])
        {
            continue;
        }
        let agrees = sentences.get(index + 1).is_some_and(|row| {
            let (label, reply) = split(row);
            label == Some(recipient) && explicit_agreement(reply)
        });
        let force = contains(operation, &["也要", "要进行", "必须", "务必", "你来", "负责"]);
        if !(future || agrees || force) { continue; }
        let mut text = words[start..after + position].trim().to_owned();
        if let Some((_, subject)) = previous.rsplit_once('把') {
            let subject = subject.trim();
            if (2..=25).contains(&subject.chars().count()) {
                text = format!("把{subject}{text}");
            }
        }
        if !canonical_brief::line(&text, 90) || !complete_piece(&text) { continue; }
        let support = [
            Some(intro), inherited.map(|(position, _)| position), agrees.then_some(index + 1),
        ].into_iter().flatten().collect();
        work.push(DirectedWork { item: CompanionV1ActionItem {text,owner:Some(owner.to_owned()),due:None}, support });
    }
    if let Some(group) = CLOSING_OBJECT.captures(words) {
        let requested = group.name("work").unwrap().as_str();
        let scope = group.get(0).unwrap().as_str();
        if !contains(scope, CONTEXT) && !contains(scope, NEGATION) {
            let owner = ["各部门", "各单位", "各团队", "各小组"].into_iter()
                .find(|owner| scope.contains(owner)).unwrap();
            let text = format!("{owner}会后{requested}");
            work.push(DirectedWork {
                item: CompanionV1ActionItem { text,owner:Some(owner.to_owned()),due:None },
                support: inherited.map(|(position, _)| position).into_iter().collect(),
            });
        }
    }
    if work.is_empty() && future && words.contains("你来主持") {
        if let (Some(prior), Some(reply), Some(next)) = (
            index.checked_sub(2).and_then(|i| sentences.get(i)),
            index.checked_sub(1).and_then(|i| sentences.get(i)),
            sentences.get(index + 1),
        ) {
            let (lead, directive) = split(prior);
            let (receiving, accepted) = split(reply);
            let (next_label, next_reply) = split(next);
            if lead == Some(speaker) && receiving.is_some() && receiving == next_label
                && explicit_agreement(accepted) && explicit_agreement(next_reply)
                && !contains(words, SOFT) && !contains(words, CONTEXT) && !contains(words, NEGATION)
                && canonical_brief::line(words, 90)
            {
                if let Some((intro, _, owner)) = roles.iter().find(|(_, label, role)| Some(*label) == receiving && directive.contains(role)) {
                    work.push(DirectedWork {
                        item: CompanionV1ActionItem { text: words.to_owned(),owner:Some((*owner).to_owned()),due:None },
                        support: vec![*intro, index - 2, index - 1, index + 1],
                    });
                }
            }
        }
    }
    if work.is_empty() && future && !contains(words, SOFT) && !contains(words, CONTEXT)
        && !contains(words, NEGATION) && DELIVERABLE.is_match(words)
    {
        if let Some(row) = sentences.get(index + 1) {
            let (recipient, reply) = split(row);
            let reply = spread_trim(reply);
            let acknowledgement = reply.strip_prefix("好的").or_else(|| reply.strip_prefix('对'));
            if let (Some(label), Some(phrase)) = (recipient, acknowledgement) {
                if let Some((intro, _, owner)) = roles.iter().find(|(_, participant, _)| *participant == label && label != speaker) {
                    let text = spread_trim(phrase);
                    if DELIVERABLE.find(text).is_some_and(|artifact| artifact.start() == 0 && artifact.end() == text.len())
                        && canonical_brief::line(text, 90)
                    {
                        work.push(DirectedWork {
                            item: CompanionV1ActionItem { text: text.to_owned(),owner:Some((*owner).to_owned()),due:None },
                            support: vec![*intro, index + 1],
                        });
                    }
                }
            }
        }
    }
    work
}

/// A conversational handoff is binding only when its scope and recipient are
/// explicit and a nearby turn confirms it. Each part keeps its own source.
pub(super) fn confirmed_delegation(
    sentences: &[Value], index: usize,
) -> Option<ConfirmedDelegation> {
    static ASSIGNMENT: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"^(?:那|好|行|这次|本次|咱们|咱|我们|\s|，|,)*(?P<scope>[\p{Han}A-Za-z0-9]{2,24}?(?:任务|工作|项目|事项|安排))(?:就|正式|统一)*(?:交给|交由)(?P<owner>[\p{Han}A-Za-z0-9·]{2,16}?)(?:这边儿?|那边儿?)?(?:来负责|负责|承接)?(?:吧|了)?$"
    ).expect("explicit delegation"));
    let (speaker, body) = split(&sentences[index]);
    if contains(body, CONTEXT) || contains(body, NEGATION) || body.contains(['？', '?'])
        || contains(body, &["假设", "假如", "举例", "比如", "例如", "听说", "曾经", "暂定"])
    {
        return None;
    }
    let text = body.split(['，', ',', '。', '！', '；']).next()?.trim();
    if contains(text, SOFT) { return None; }
    let assignment = ASSIGNMENT.captures(text)?;
    let owner = assignment.name("owner")?.as_str();
    let scope = assignment.name("scope")?.as_str();
    if contains(owner, &["他们", "他来", "你们", "那个人", "某个", "有关方面"]) {
        return None;
    }
    let speaker = speaker?;
    let authority = role_of(sentences, speaker).unwrap_or(speaker);
    if !meeting_lead(authority) {
        return None;
    }
    let nearby = index + 1..(index + 9).min(sentences.len());
    let confirmation = nearby.clone().take(4).find(|&position| {
        let (label, words) = split(&sentences[position]);
        if words.contains(['？', '?']) || contains(words, SOFT) || contains(words, NEGATION) {
            return false;
        }
        let firm_instruction = label == Some(speaker) && words.contains(owner)
            && contains(words, &["一定要负责", "务必负责", "正式负责", "由你们负责", "就交给"]);
        let recipient = label.and_then(|name| role_of(sentences, name));
        let accepts = recipient.is_some_and(|role| role.starts_with(owner))
            && contains(words, &["我们来负责", "我们负责", "我们接下来负责", "我们接受", "我们来承接"]);
        firm_instruction || accepts
    });
    let dispute = nearby.clone().find(|&position| {
        let (_, words) = split(&sentences[position]);
        (words.contains(owner) || words.contains(scope))
            && contains(words, &["暂缓", "还没定", "还没有定", "没有决定", "先别定", "取消", "改由", "不能交给"])
    });
    if confirmation.is_none() && dispute.is_none() {
        return None;
    }
    let confirmation = confirmation.unwrap_or(index);
    let followup = nearby.clone().filter(|&position| position >= confirmation).find_map(|position| {
        let (label, reply) = split(&sentences[position]);
        let role = role_of(sentences, label?)?;
        if !role.starts_with(owner) {
            return None;
        }
        let mut item = scoped_commitment(reply, true)?;
        item.owner = Some(owner.to_owned());
        let handoff = nearby.clone().filter(|&other| other > position).find_map(|other| {
            let (label, words) = split(&sentences[other]);
            let current_speaker = label.or_else(|| (position..other).rev()
                .find_map(|previous| split(&sentences[previous]).0));
            if current_speaker != Some(speaker) || contains(words, SOFT)
                || contains(words, NEGATION) || words.contains(['？', '?']) {
                return None;
            }
            let offset = ["交给", "提交给", "发给", "报给"].into_iter()
                .filter_map(|verb| words.find(verb)).min()?;
            let lead = &words[..offset];
            if !contains(lead, &["这个", "这些", "它", "计划", "清单", "方案", "材料", "报告"]) {
                return None;
            }
            let delivery = words[offset..].split(['，', ',', '。', '！', '；']).next()?.trim();
            let delivery = delivery.strip_suffix("看一").unwrap_or(delivery).trim_end();
            if delivery.chars().count() < 5 || delivery.chars().count() > 26 {
                return None;
            }
            Some((other, delivery))
        });
        let continuation = handoff.and_then(|(position, delivery)| {
            let linked = format!("{}，{delivery}", item.text);
            if !canonical_brief::line(&linked, 90) { return None; }
            item.text = linked;
            Some(position)
        });
        Some((position, item, continuation))
    });
    Some(ConfirmedDelegation {
        decision: text.to_owned(), owner: owner.to_owned(), scope: scope.to_owned(),
        confirmation, followup, dispute,
    })
}

fn explicit_delivery_of_existing_material(text: &str) -> Option<CompanionV1ActionItem> {
    static MATERIAL: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:拍摄了|录制了|已准备好|已整理好|已经写好|已经做完)[^，,。！？；;]{2,40}(?:视频|材料|文档|报告|清单|表格|照片|说明|录音)"
    ).expect("existing deliverable"));
    static DELIVERY: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:到时候|稍后|会后|散会后|之后)?(?:我|我们|咱们)(?:会|就会|将|一定会)(?:把.{1,18})?(?:发给|分享给|送给|交给)(?:你们|大家|各位|参会者)"
    ).expect("personal delivery commitment"));
    let material = MATERIAL.find(text)?;
    let delivery = DELIVERY.find_at(text, material.end())?;
    let between = &text[material.end()..delivery.start()];
    let scope_start = text[..material.start()].rfind(['，', ',', '。', '！', '？', '；']).unwrap_or_default();
    let utterance = &text[scope_start..delivery.end()];
    if utterance.contains(['？', '?']) || contains(utterance, SOFT) || contains(utterance, NEGATION)
        || contains(utterance, CONTEXT) || between.chars().count() > 26
        || contains(between, &["另外", "改说", "或者", "但是"])
    {
        return None;
    }
    let following = text[delivery.end()..].trim_start_matches([' ', '，', ',']);
    if CONTEXT.iter().any(|signal| following.starts_with(signal))
        && !following.split_once(['，', ',']).is_some_and(|(_, consequence)| {
            ["你就", "你们就", "客户就", "对方就"]
                .iter().any(|subject| consequence.trim_start().starts_with(subject))
        })
    {
        return None;
    }
    let text = text[material.start()..delivery.end()].trim();
    canonical_brief::line(text, 90).then(|| CompanionV1ActionItem {
        text: text.to_owned(), owner: None, due: None,
    })
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
            return Some(attach_prerequisite(sentences, index, BoundCommitment {
                item, prerequisite: None, continuation: Some(next), needs_review: false,
            }));
        }
    }
    let item = agreed_handoff(first)
        .or_else(|| scoped_commitment(first, institutional_voice))
        .or_else(|| explicit_delivery_of_existing_material(first))?;
    Some(attach_prerequisite(sentences, index, BoundCommitment {
        item, prerequisite: None, continuation: None, needs_review: false,
    }))
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
    fn preserves_a_prerequisite_from_the_same_speaker_before_an_acknowledgment() {
        let rows = sentences(&[
            "说话人2: 我是设计部。",
            "说话人2: 图纸审核合格的话，这周会跟我们对接",
            "说话人1: 嗯",
            "说话人2: 然后我们会和施工队对接，让他们安排施工。",
        ]);
        let bound = at(&rows, 3, &meeting_actor_labels(&rows)).unwrap();
        assert_eq!(bound.prerequisite, Some(1));
        assert!(bound.item.text.contains("图纸审核合格的话") && bound.item.text.contains("施工队对接"));
        assert!(!bound.needs_review);
    }

    #[test]
    fn keeps_a_prerequisite_shared_by_two_linked_steps_in_one_speech() {
        let rows = sentences(&[
            "说话人2: 我是设计部。",
            "说话人2: 对 已经发给他们的那个构造师让他们去检查，看合不合格儿合格儿的话，这周儿会和我们对接，然后我们会和这个施工队儿也对接，让他们去施工",
        ]);
        let item = at(&rows, 1, &meeting_actor_labels(&rows)).unwrap().item;
        assert!(item.text.contains("合格儿的话，这周儿会和我们对接，然后我们会和这个施工队儿也对接"));
        assert_eq!(item.owner, None);
    }

    #[test]
    fn incomplete_condition_goes_to_review_instead_of_becoming_a_task() {
        let rows = sentences(&[
            "说话人4: 我是市场部。",
            "说话人4: 如果就是说楼盘这次这个想想的那个",
            "说话人1: 嗯",
            "说话人4: 然后我们就会去找开发商进行洽谈",
        ]);
        let bound = at(&rows, 3, &meeting_actor_labels(&rows)).unwrap();
        assert_eq!(bound.prerequisite, Some(1));
        assert!(bound.needs_review);
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
