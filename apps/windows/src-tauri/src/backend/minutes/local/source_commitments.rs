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

fn established_routine(clause: &str, previous: Option<&str>) -> bool {
    let new_work = [
        "会后", "散会后", "下一步", "下次", "明天", "下周", "下个月",
        "今后改", "以后改", "改成", "改为", "调整为", "新增", "第一次",
        "从今天起", "从现在起", "开始执行",
    ];
    if contains(clause, &new_work) { return false; }
    let repeated = |clause: &str| contains(clause, &[
        "一直都是", "以前就是", "三班倒", "三班儿倒", "两班倒", "两班儿倒",
        "轮流值守",
        "闭店状态", "平时", "以往", "现行做法", "照例", "照常",
    ]);
    let describes_repetition = |words: &str| {
        let actor_and_schedule = words.split_once('会').map_or(words, |(before, _)| before);
        repeated(words) || contains(actor_and_schedule, &["每次", "每班", "每天", "每周"])
    };
    describes_repetition(clause)
        || previous.is_some_and(|words| describes_repetition(words) && !contains(words, &new_work))
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
        let previous = index.checked_sub(1).map(|previous| clauses[previous]);
        if contains(clause, SOFT) || contains(clause, NEGATION) || established_routine(clause, previous)
            || previous.is_some_and(|previous| {
                contains(previous, &["举例", "比如", "例如", "假设", "如果说有人", "听说", "转述", "你建议"])
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

pub(super) fn meeting_lead(role: &str) -> bool {
    ["主持人", "负责人", "经理", "总裁", "董事长", "主管", "组长", "主任", "校长"]
        .iter().any(|title| role.ends_with(title))
}

pub(super) fn meeting_roles(sentences: &[Value]) -> Vec<(usize, &str, &str)> {
    static ROLL_CALL: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"^[零〇一二三四五六七八九十幺0-9]{2,6}[ 、，,\s]*(?P<role>[\p{Han}]{0,12}(?:部门|部儿?|组|处|地区|主管|经理|总裁|董事长|主任|校长))$"
    ).expect("role named during the meeting roll call"));
    sentences.iter().take(80).enumerate().filter_map(|(index, sentence)| {
        let (speaker, text) = split(sentence);
        let role = self_introduced_identity(text).or_else(|| {
            if index >= 12 { return None; }
            ROLL_CALL.captures(spread_trim(text))?.name("role").map(|role| role.as_str())
        })?;
        Some((index, speaker?, role))
    }).collect()
}

pub(super) struct DirectedWork {
    pub(super) item: CompanionV1ActionItem,
    pub(super) support: Vec<usize>,
}

/// An assignee spoken in the instruction is available even when the
/// transcript has no reliable label for the person giving the instruction.
pub(super) fn explicitly_named_work(sentences: &[Value], index: usize) -> Vec<DirectedWork> {
    const OWNER: &str = r"(?:[A-Z](?:[\s、和与]+[A-Z])?\s*(?:两位)?(?:同学|老师|工程师)|[\p{Han}]{1,6}?(?:小组|团队|部门|同学|经理|主管|部长|工程师|负责人|老师|组|部)|部长|副部长|负责人|项目经理|主持人)";
    static DIRECT: LazyLock<Regex> = LazyLock::new(|| Regex::new(&format!(
        r"由(?P<owner>{OWNER})\s*(?:来|就|负责|先|要|务必){{0,4}}(?P<work>(?:制作|做|编制|整理|提交|准备|提供|核对|复核|更新|撰写|编写|统计|计算|核算|估算)[^，,。！？；;？?\r\n]{{2,40}})"
    )).expect("explicitly named recipient and work"));
    static INVERTED: LazyLock<Regex> = LazyLock::new(|| Regex::new(&format!(
        r"(?:^|[，,；;]|然后|另外|还有)\s*(?P<deliverable>[\p{{Han}}A-Za-z]{{2,12}})\s*由(?P<owner>{OWNER})\s*(?:来|就|负责)?(?:制作|做|编制|整理|提交|准备|提供|核对|更新)(?:一下儿?)?(?:吧|了)?(?:$|[，,。！；;])"
    )).expect("deliverable followed by an explicit recipient"));
    static REPEATED: LazyLock<Regex> = LazyLock::new(|| Regex::new(&format!(
        r"(?P<owner>{OWNER})[^，。！？；]{{0,19}}[，,\s]+(?:她|他|他们|她们)(?:也)?(?:可以|来|负责)(?P<work>(?:制作|做|编制|整理|提交|准备|提供|核对|更新)[^，,。！？；;\r\n]{{2,50}})"
    )).expect("named proposal with a later confirmation"));
    static ARTIFACT: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?i:p\s*p\s*t|excel|word|pdf)|预算清单|预算表|项目方案|执行方案|交付方案|测试报告|验收报告|工作清单|活动方案|采购清单|原型|条幅"
    ).expect("literal work product"));
    let (_, words) = split(&sentences[index]);
    if contains(words, CONTEXT) || contains(words, NEGATION)
        || contains(words, &["我建议", "建议由", "可以考虑", "最好", "之前", "当时", "上次", "已经由", "曾由", "听说", "比如", "例如", "举例", "演示", "暂定", "尚未决定", "没有决定", "没有确认"])
        || index.checked_sub(1).is_some_and(|previous| {
            let (_, context) = split(&sentences[previous]);
            contains(context, &["举个例子", "举一个例子", "模拟一下", "比如有一个", "假设一个", "作为演示"])
        })
    {
        return Vec::new();
    }
    let accepted = (index + 1..(index + 4).min(sentences.len()))
        .take_while(|&next| {
            let (_, words) = split(&sentences[next]);
            explicit_agreement(words) || backchannel(words)
        }).find(|&next| {
            let (_, words) = split(&sentences[next]);
            explicit_agreement(words)
        });
    let mut output = Vec::new();
    for (form, matches) in [(0, DIRECT.captures_iter(words)), (1, INVERTED.captures_iter(words)), (2, REPEATED.captures_iter(words))] {
        for m in matches {
            let owner = m.name("owner").unwrap().as_str();
            let clause = m.get(0).unwrap();
            let tail = words[clause.end()..].trim_start();
            let lead = words[..clause.start()].rsplit(['，', ',', '；', ';', '。']).next().unwrap_or("");
            if tail.starts_with(['?', '？'])
                || clause.as_str().trim_end_matches(['。', '！', ' ', '，']).ends_with(['吗', '么', '呢'])
                || contains(lead, &["要不要", "是否", "能不能", "可不可以", "请问", "想问", "是不是"])
                || contains(clause.as_str(), &["要不要", "能不能", "可不可以", "完成了", "提交了", "做过", "做完了", "已交付", "已经交给"]) {
                continue;
            }
            let mut text = m.name("work").map(|work| work.as_str().trim_end_matches(['吧', '。', ' ']).to_owned())
                .unwrap_or_else(|| format!("制作{}", &m["deliverable"]));
            if text.contains('？') || !complete_piece(&text) || !canonical_brief::line(&text, 90) { continue; }
            let artifact = ARTIFACT.find(&text).map(|found| {
                (found.end(), canonical_brief::normalized(found.as_str()).to_ascii_lowercase())
            });
            let confirmation = artifact.as_ref().and_then(|(_, product)| {
                (index + 1..(index + 5).min(sentences.len())).find(|&next| {
                    let (_, response) = split(&sentences[next]);
                    response.split_inclusive(['，', ',', '。', '？', '?', '；']).any(|part| {
                        !part.contains(['?', '？']) && !contains(part, CONTEXT)
                            && !contains(part, NEGATION)
                            && !contains(response, &["改由", "改让", "换个人", "换成别人", "收回"])
                            && contains(part, &["让他做", "让她做", "你做", "你来做", "由你", "发给你"])
                            && canonical_brief::normalized(part).to_ascii_lowercase().contains(product)
                    })
                })
            });
            let tentative = form == 2 || clause.as_str().trim_end_matches(['。','！','；','，',' ']).ends_with('吧');
            let support = if form == 2 { confirmation } else { accepted.or(confirmation) };
            if tentative && support.is_none() { continue; }
            // A repeated mention can confirm the work product without supplying
            // an assignee or due date for a different instruction.
            if let Some((end, _)) = artifact {
                if form == 2 && contains(&text[end..], &["预算", "账目", "消费记录"]) {
                    text = format!("{}，整理预算。", &text[..end]);
                }
            }
            let tail = words[clause.end()..].trim_start_matches(['，', ',', ' ']);
            if let Some(following) = tail.split(['，', '。', '；']).next().filter(|next| {
                canonical_brief::line(next, 35) && contains(next, &["再看看要不要", "再决定是否", "再确认是否"])
            }) {
                let linked = format!("{text}，{following}");
                if canonical_brief::line(&linked, 90) { text = linked; }
            }
            if output.iter().any(|work: &DirectedWork| work.item.owner.as_deref() == Some(owner)
                && canonical_brief::normalized(&work.item.text) == canonical_brief::normalized(&text)) {
                continue;
            }
            output.push(DirectedWork {
                item: CompanionV1ActionItem { text, owner: Some(owner.to_owned()), due: None },
                support: support.into_iter().collect(),
            });
        }
    }
    output
}

/// A deliverable started by a wrap-up directive can follow a brief
/// acknowledgment. The unfinished verb and the explicit submission must both
/// be present before this is recorded as work.
pub(super) fn continued_collective_work(
    sentences: &[Value], index: usize, timing: Option<&super::timed_evidence::Timing<'_>>,
) -> Option<(DirectedWork, usize)> {
    static UNFINISHED: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?P<owner>各部门|各单位|各项目组|各团队|各小组)(?:儿)?[^。！？；?]{1,40}?(?:做一个|写一个|做个|写个|整理一份|提交一份)[，,。\s]*$"
    ).expect("an explicit group with an unfinished deliverable"));
    static COMPLETION: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"^(?:嗯|呃|啊|\s)*(?P<work>工作总结|总结|报告|方案|清单|记录)(?:儿)?[，,\s]*(?:然后|接着|再|就|是|就是|\s){0,5}(?:发给|交给|提交给|报给)(?:咱们的|我们的|咱们|我们)?(?P<recipient>[\p{Han}]{2,12}?)(?:让|请|看|审|确认|[，,。！？；\s]|$)"
    ).expect("a named deliverable and recipient"));
    let (speaker, words) = split(&sentences[index]);
    if !contains(words, &["散会后", "下去", "回去以后", "会后", "回去先"])
        || words.contains(['?', '？']) || contains(words, CONTEXT) || contains(words, NEGATION)
        || contains(words, &["要不要", "我的建议", "举例", "比方说", "模拟", "曾经", "已经"])
    { return None; }
    let start = UNFINISHED.captures(words)?;
    let last = (index+1..(index+4).min(sentences.len())).find(|&position| {
        !backchannel(split(&sentences[position]).1)
    })?;
    let (finisher, ending) = split(&sentences[last]);
    if speaker.zip(finisher).is_some_and(|(a,b)|a != b) || contains(ending, NEGATION)
        || contains(ending, &["还不确定", "不要交", "没决定", "要不要", "举例"]) { return None; }
    let result = COMPLETION.captures(ending)?;
    let confirmed = sentences.get(last+1).is_some_and(|row| explicit_agreement(split(row).1));
    if !timing.is_some_and(|timing| timing.neighboring_speech(index,last))
        && !speaker.zip(finisher).is_some_and(|(a,b)|a == b) && !confirmed {
        return None;
    }
    let work = result.name("work")?.as_str();
    let work = if work == "总结" && words.contains("工作") { "本部门工作总结" } else { work };
    let recipient = result.name("recipient")?.as_str();
    let owner = start.name("owner")?.as_str();
    let text = format!("会后整理{work}并交给{recipient}。");
    let mut support = vec![last];
    if confirmed { support.push(last+1); }
    Some((DirectedWork {
        item: CompanionV1ActionItem { text, owner: Some(owner.to_owned()), due: None },
        support,
    }, last))
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

pub(super) fn current_procedure_reply(sentences: &[Value], index: usize) -> Option<usize> {
    let (respondent, answer) = split(&sentences[index]);
    let respondent = respondent?;
    let previous = index.checked_sub(1)?;
    let (asker, question) = split(&sentences[previous]);
    if asker.is_none() || asker == Some(respondent)
        || !contains(question, &["怎么处理", "怎么做", "怎么安排", "如何处理", "怎么操作", "如何操作"])
        || !contains(question, &["平时", "目前", "通常", "现行", "遇到", "对外来", "对顾客", "对客户", "日常"])
        || contains(question, &["这次", "本次", "新出现", "临时", "以后改", "发生了"])
        || contains(answer, &["会后", "下次", "明天", "下周", "接下来改", "改为", "新安排"])
    {
        return None;
    }
    contains(answer, &["我们会", "我们先", "咱们会", "向来", "一般", "通常", "一直"])
        .then_some(previous)
}

fn collective_written_plan(words: &str) -> Option<CompanionV1ActionItem> {
    static REQUEST: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?P<group>大家|各部门|各单位|各项目组|各团队)(?:儿)?\s*(?:下去以后|散会后|会后|回去以后)(?P<body>[^。！？；]{4,220})"
    ).expect("collective follow-up with an explicit deliverable"));
    static DOCUMENT: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:写|制订|制定|编制|形成|整理|做|提交|完成)[^，。！？；]{0,18}?(?P<name>计划书|方案|报告|清单|时间表|预算表)"
    ).expect("requested document"));
    static SEND: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:发给|交给|提交给|报给)(?:咱们这个|我们这个|咱们|我们|这个)?\s*(?P<to>[\p{Han}]{2,14}?)(?:这边|那边|然后|[，。！？；,\s]|$)"
    ).expect("recipient explicitly named"));
    static DAYS: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:[0-9一二两三四五六七八九十]{1,4}天(?:半个月)?|半个月)"
    ).expect("plan duration, not a due date"));
    let request = REQUEST.captures(words)?;
    let body = request.name("body")?.as_str();
    if contains(body, &["要不要", "如果要做", "不用", "先别", "还没决定"]) {
        return None;
    }
    let document = DOCUMENT.captures_iter(body).last()?.name("name")?.as_str();
    let group = request.name("group")?.as_str();
    let owner = if group == "大家" {
        ["各部门", "各单位", "各项目组", "各团队"].into_iter()
            .find(|role| body.contains(role)).unwrap_or(group)
    } else {
        group
    };
    let duration = DAYS.find(body).filter(|m| contains(&body[m.end()..], &["路途", "行程", "路线", "安排"]));
    let payload = duration.map_or_else(|| document.to_owned(), |span| {
        let duration = span.as_str().trim_end_matches("半个月");
        let duration = if duration.is_empty() { span.as_str() } else { duration };
        let scope = ["行程", "路线", "路途"].into_iter().find(|word| body.contains(word)).unwrap_or("安排");
        format!("{duration}{scope}{document}")
    });
    let recipient = SEND.captures(body).and_then(|m| m.name("to")).map(|m| {
        let name = m.as_str();
        name.char_indices().find_map(|(i, _)| {
            let (first, second) = name.split_at(i);
            (first == second).then_some(first)
        }).unwrap_or(name)
    });
    let text = recipient.map_or_else(|| format!("会后完成{payload}"), |owner| format!("会后完成{payload}并发给{owner}"));
    Some(CompanionV1ActionItem { text, owner: Some(owner.to_owned()), due: None })
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
    if work.is_empty() {
        if let Some(item) = collective_written_plan(words) {
            work.push(DirectedWork { item, support: inherited.map(|(position, _)| position).into_iter().collect() });
        } else if future && contains(words, &["再细化", "再具体一点"]) && words.contains("你刚才") {
            if let Some((label, answer)) = sentences.get(index+1).map(split) {
                if label != Some(speaker) && explicit_agreement(answer) {
                    if let Some((intro, _, role)) = roles.iter().find(|(_, person, _)| Some(*person)==label) {
                        // An earlier proposal and the assignee's acceptance both
                        // belong to this action. A bare "you" is insufficient.
                        if let Some(proposal) = (index.saturating_sub(12)..index).rev().find(|&position| {
                            let (person, body) = split(&sentences[position]);
                            person==label && contains(body, &["我觉得", "我们可以", "建议", "的话", "想法"])
                        }) {
                            let (_, body) = split(&sentences[proposal]);
                            let object = ["授课", "培训", "方案", "计划", "安排"].into_iter().find(|word| body.contains(word))
                                .unwrap_or("刚才的提案");
                            work.push(DirectedWork {
                                item: CompanionV1ActionItem {
                                    text: format!("会后细化{object}"), owner: Some((*role).to_owned()), due: None,
                                },
                                support: vec![*intro, proposal, index+1],
                            });
                        }
                    }
                }
            }
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
    fn explicit_work_keeps_the_spoken_recipient_and_requires_a_supported_soft_assignment() {
        let rows = sentences(&[
            "那由D同学做一个P P T吧。",
            "让他做一个P P T，还有C同学也是学计算机的，她可以做一个Excel来拟定一下预算。",
            "嗯。",
            "我把预算清单发给你，然后你做一个Excel清单。",
            "然后条幅由A B两位同学来做吧。",
            "好。",
            "先由部长计算设备和人员的钱，然后再看看要不要搞外联。",
        ]);
        let action = |index| explicitly_named_work(&rows,index).into_iter().next().unwrap().item;
        assert_eq!(action(0).owner.as_deref(),Some("D同学"));
        assert_eq!(action(1).owner.as_deref(),Some("C同学"));
        assert_eq!(action(4).owner.as_deref(),Some("A B两位同学"));
        assert!(action(6).text.contains("再看看要不要搞外联"));

        for text in ["那由C同学做一个预算表吧。", "如果由C同学做一个预算表，这项暂时不定。",
            "这是举例，由C同学做一个预算表。", "要不要由C同学准备预算表。",
            "已经由C同学准备了预算表。", "由项目组提交了验收报告。"] {
            assert!(explicitly_named_work(&sentences(&[text]),0).is_empty(),"{text}");
        }
        let changed = sentences(&["C同学有这些资料，她可以做一个Excel。", "行，我来做Excel。"]);
        assert!(explicitly_named_work(&changed,0).is_empty());
    }

    #[test]
    fn a_trailing_question_does_not_erase_an_independent_named_instruction() {
        let rows = sentences(&[
            "嗯，那由D同学做一个P P T吧，他是学计算机的，然后是让他做那个什么？",
            "让他做一个P P T，预算表先等下。",
        ]);
        let assignments=explicitly_named_work(&rows,0);
        assert_eq!(assignments.len(),1);
        assert_eq!(assignments[0].item.owner.as_deref(),Some("D同学"));
        assert!(explicitly_named_work(&sentences(&["那由D同学做一个PPT吗？","我听听意见。"]),0).is_empty());
        assert!(explicitly_named_work(&sentences(&["是否由D同学做一个PPT。","还没回答。"]),0).is_empty());
    }

    #[test]
    fn a_split_closing_instruction_preserves_the_group_and_recipient() {
        let rows = sentences(&[
            "那你们下去，各部门儿都对各部门的工作做一个",
            "嗯。",
            "总结，然后就是交给我们的台长让他看一下儿。",
            "好。",
        ]);
        let (work, last) = continued_collective_work(&rows,0,None).unwrap();
        assert_eq!(last,2);
        assert_eq!(work.item.owner.as_deref(),Some("各部门"));
        assert_eq!(work.item.due,None);
        assert!(work.item.text.contains("工作总结") && work.item.text.contains("台长"));
        let detached = sentences(&[
            "你们下去，各部门的工作做一个",
            "接下来聊聊别的内容。",
            "总结，然后交给台长。",
        ]);
        assert!(continued_collective_work(&detached,0,None).is_none());
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
