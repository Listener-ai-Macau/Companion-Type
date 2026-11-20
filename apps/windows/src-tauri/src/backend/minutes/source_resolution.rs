//! Bind spoken commitments and decisions to their own source context.
use std::{
    collections::{HashMap, HashSet},
    sync::LazyLock,
};

use regex::Regex;

use super::{split_segments, CompanionV1ActionItem, CompanionV1MeetingMinutes};

static INTRODUCTION: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"^[零〇一二三四五六七八九十幺0-9 、]*(?:我叫|我是)\s*([\p{Han}A-Za-z·]{2,14})$")
        .unwrap()
});
static ASSIGN: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
    r"行动项[:：]|待办[:：]|分给.{2,28}(?:让|去|跟|和|合作)|(?:请|交给|由).{2,40}(?:完成|提交|制作|核对|调查|出具)|(?:你|你们).{0,35}(?:做.{0,22}(?:计划|方案)|拿出|提交|抓一下|发给|进行.{0,10}(?:计划|调查|核对))|(?:下去以后|会后|散会后).{0,42}(?:拿出来|提交|发给|做.{0,22}(?:计划|方案))|(?:把|将).{2,39}(?:发给我|提交给|交给)|我会.{0,28}(?:发给|转达|吩咐|提交|完成)|(?:这边儿|这边|这一块儿).{0,28}(?:要进行|进行一个).{0,14}(?:调查|计划书|核对)|(?:加大|加强)对.{2,20}管理力度"
).unwrap()
});
static UNCERTAIN: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
    r"建议|提议|我觉得.{0,18}(?:可以|可以让)|(?:能不能|要不要).{0,18}(?:做|提交|安排)|是否(?:同意|决定|派工)|(?:取消|撤回|无须|无需|不再).{0,10}(?:安排|提交|完成)|不需要|如果|假如|假设|尚未决定|不确定"
).unwrap()
});
static ACRONYM: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?-u:\b)[A-Z](?:\s*[A-Z0-9]){1,7}(?-u:\b)").unwrap());
static WORK_IN_PROGRESS: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"现在.{0,18}(?:已经|正在|也是在|就在)").unwrap());
static FINAL_POLICY: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?:下半年|下阶段|下一步|以后).{0,24}在保证.{2,25}情况下.{0,8}再").unwrap()
});
static DECISION: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
    r"决定[:：]|(?:最终|正式|明确|董事会|全体|已经)(?:决定|通过|同意|确认)|一致(?:批准|通过|同意)|暂.{0,2}定|就(?:这么定|按.{2,18}(?:做|办|执行))|以后.{0,8}(?:都)?要按照|以.{2,18}为准"
).unwrap()
});
static BLOCKED_CLOSING: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
    r"建议|提议|如果|假如|是否|要不要|能不能|(?:未|没|不|尚未).{0,6}(?:决定|通过|同意|拍板)|例如|比如|举例|(?:怎么|何时)(?:决定|确定)"
).unwrap()
});
static POSSIBLE_PERMISSION: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
    r"(?:不会|并非|并不|也不)不(?:允许|准|能|可以|让)(?:他们|她们|大家|顾客|游客)?(?P<action>[\p{Han}]{2,15}?)\s*(?:也可以|或者|或是|[，,。；]|$)"
).unwrap()
});
static PROHIBITION: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
    r"(?P<marker>不允许|不准|不得|不能|禁止)(?:他们|她们|大家|顾客|游客)?(?P<action>[\p{Han}]{2,15}?)\s*(?:也可以|或者|或是|或|[，,。；）)]|$)"
).unwrap()
});
static DEADLINE_CONTEXT: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?:前|之前|以内|之内|截止|截至|最迟|必须在|不晚于|当天|当日|按时)").unwrap()
});
static PRIOR_REQUIREMENT: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"只有(?:就)?(?P<condition>[^，。；]{3,28})[，,]?(?:咱们|我们|他们)?才(?:能|可以)(?:就是)?(?:成为|进入|加入|办理|允许|申请|参加)(?:咱们|我们)?(?P<scope>[\p{Han}]{2,16})").unwrap()
});
static LATER_REQUIREMENT: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"只要(?P<condition>[^，。；]{2,24})(?:即可|就可以|就行|便可|就能)").unwrap()
});

#[derive(Clone)]
struct Turn {
    speaker: String,
    text: String,
}

pub(super) struct Source<'a> {
    turns: Vec<Turn>,
    roles: HashMap<String, String>,
    original: &'a str,
    revisions: Vec<Revision>,
}

struct Revision {
    prior: HashSet<String>,
    later: HashSet<String>,
}

impl<'a> Source<'a> {
    pub(super) fn new(original: &'a str) -> Self {
        let mut turns = Vec::new();
        let mut roles = HashMap::new();
        for line in original.lines() {
            let (speaker, text) = line
                .split_once([':', '：'])
                .filter(|(label, _)| {
                    !label.is_empty()
                        && label.chars().count() <= 16
                        && label.chars().all(|ch| ch.is_alphanumeric() || ch == '·')
                        && !matches!(*label, "决定" | "结论" | "问题" | "行动项" | "待办")
                })
                .unwrap_or(("", line));
            if !speaker.is_empty() {
                if let Some(captures) = INTRODUCTION.captures(text.trim()) {
                    roles
                        .entry(speaker.to_string())
                        .or_insert_with(|| captures[1].to_string());
                } else if !speaker.starts_with("说话人") {
                    roles
                        .entry(speaker.to_string())
                        .or_insert_with(|| speaker.to_string());
                }
            }
            turns.extend(split_segments(text).into_iter().map(|text| Turn {
                speaker: speaker.to_string(),
                text,
            }));
        }
        let revisions = requirement_revisions(&turns);
        Self {
            turns,
            roles,
            original,
            revisions,
        }
    }

    fn role(&self, turn: &Turn) -> Option<&str> {
        self.roles.get(&turn.speaker).map(String::as_str)
    }

    fn context(&self, index: usize, actor: &str) -> String {
        self.turns[..index]
            .iter()
            .rev()
            .take(8)
            .filter(|t| self.role(t).is_some_and(|name| role_eq(name, actor)))
            .take(3)
            .map(|t| t.text.as_str())
            .collect::<Vec<_>>()
            .join("。")
    }

    fn assigned(&self, index: usize, clause: &str, actor: &str) -> bool {
        let turn = &self.turns[index];
        if names_actor(clause, actor) {
            return true;
        }
        if clause.contains("我会") && self.role(turn).is_some_and(|name| role_eq(name, actor)) {
            return true;
        }
        if !clause.contains('你') {
            return false;
        }
        self.turns
            .iter()
            .skip(index + 1)
            .take(2)
            .find(|row| !row.text.trim().is_empty() && row.speaker != turn.speaker)
            .is_some_and(|row| {
                let response = normalize(&row.text);
                self.role(row).is_some_and(|name| role_eq(name, actor))
                    && (matches!(
                        response.as_str(),
                        "行" | "好" | "好的" | "行好的" | "对好" | "嗯对" | "可以"
                    ) || response.starts_with("对做"))
            })
    }

    fn action(&self, plan: &CompanionV1ActionItem) -> Option<CompanionV1ActionItem> {
        self.action_in(plan, None)
    }

    pub(super) fn action_in(
        &self,
        plan: &CompanionV1ActionItem,
        cited_passages: Option<&[&str]>,
    ) -> Option<CompanionV1ActionItem> {
        let actors: Vec<_> = plan
            .owner
            .as_deref()
            .unwrap_or("")
            .split(['、', ',', '，'])
            .map(|name| name.split(['（', '(']).next().unwrap_or("").trim())
            .filter(|name| !name.is_empty() && !matches!(*name, "待确认" | "未知" | "待核实"))
            .collect();
        let action_subject = actors.iter().fold(plan.text.clone(), |text, actor| {
            text.replace(actor, "").replace(&role_key(actor), "")
        });
        let wanted = subjects(&action_subject);
        let acronyms: Vec<_> = ACRONYM
            .find_iter(&action_subject)
            .map(|m| normalize(m.as_str()))
            .collect();
        let mut candidates = Vec::new();
        for (index, turn) in self.turns.iter().enumerate() {
            let parts = turn
                .text
                .replace("这个还有刚才", "\n")
                .replace("还有刚才你说的", "\n");
            for clause in parts.lines() {
                let clause = clause
                    .split_once("你觉得")
                    .map_or(clause, |(before, _)| before);
                if !ASSIGN.is_match(clause)
                    || UNCERTAIN.is_match(clause)
                    || cited_passages.is_some_and(|texts| {
                        !texts.iter().any(|source| source.contains(clause.trim()))
                    })
                {
                    continue;
                }
                let named = !actors.is_empty()
                    && actors
                        .iter()
                        .all(|actor| self.assigned(index, clause, actor));
                let local = common(&wanted, clause);
                let same_acronym = !acronyms.is_empty()
                    && acronyms.iter().all(|term| normalize(clause).contains(term));
                let context = actors
                    .iter()
                    .filter(|actor| self.assigned(index, clause, actor))
                    .map(|actor| common(&wanted, &self.context(index, actor)))
                    .max()
                    .unwrap_or(0);
                if (named && (local >= 2 || context >= 3 || same_acronym))
                    || (actors.is_empty() && local >= 5)
                {
                    candidates.push((index, clause.to_string(), local + context.min(3)));
                }
            }
        }
        let best = candidates.iter().map(|x| x.2).max()?;
        let best: Vec<_> = candidates.iter().filter(|x| x.2 == best).collect();
        let due = plan.due.as_ref().filter(|due| {
            !due.is_empty()
                && best.iter().all(|(_, clause, _)| {
                    clause.contains(due.as_str()) && DEADLINE_CONTEXT.is_match(clause)
                })
        });
        if plan
            .due
            .as_ref()
            .is_some_and(|old| due.is_none() && plan.text.contains(old.as_str()))
        {
            return None;
        }
        Some(CompanionV1ActionItem {
            text: plan.text.clone(),
            owner: (!actors.is_empty()).then(|| actors.join("、")),
            due: due.cloned(),
        })
    }

    fn decision(&self, decision: &str) -> bool {
        let wanted = subjects(decision);
        if wanted.len() < 2 {
            return false;
        }
        self.turns.iter().enumerate().any(|(index, turn)| {
            let end_policy = self.turns.len() - index <= 8
                && self
                    .role(turn)
                    .is_some_and(|r| matches!(r, "董事长" | "总经理" | "主持人" | "负责人"))
                && FINAL_POLICY.is_match(&turn.text);
            let closure = (DECISION.is_match(&turn.text) || end_policy)
                && !BLOCKED_CLOSING.is_match(&turn.text)
                && (!turn.text.contains("暂定") || decision.contains("暂定"));
            if !closure {
                return false;
            }
            let local = common(&wanted, &turn.text);
            if local >= 3 && (local * 2 >= wanted.len() || decision.contains("暂定")) {
                return true;
            }
            if local < 2 || !turn.text.contains("按照") {
                return false;
            }
            let context = self.turns[index.saturating_sub(3)..=index]
                .iter()
                .map(|t| t.text.as_str())
                .collect::<Vec<_>>()
                .join("。");
            common(&wanted, &context) >= 4
        })
    }

    fn repair_negation(&self, text: &str) -> String {
        PROHIBITION
            .replace_all(text, |negative: &regex::Captures<'_>| {
                let span = negative.get(0).unwrap();
                let action = &negative["action"];
                let before = &text[..span.start()];
                let topic = before
                    .rsplit(['；', '。', '，', ',', '：'])
                    .find(|part| part.chars().count() >= 4)
                    .unwrap_or("");
                let terms = subjects(topic);
                let supported = self.turns.iter().find(|turn| {
                    POSSIBLE_PERMISSION.captures_iter(&turn.text).any(|source| {
                        &source["action"] == action
                            && (common(&terms, &turn.text) >= 1
                                || (action.chars().count() >= 6 && topic.is_empty()))
                    })
                });
                let opposing = self.turns.iter().any(|turn| {
                    common(&terms, &turn.text) >= 1
                        && !POSSIBLE_PERMISSION.is_match(&turn.text)
                        && PROHIBITION
                            .captures_iter(&turn.text)
                            .any(|source| &source["action"] == action)
                });
                if supported.is_some() && !opposing {
                    span.as_str().replacen(&negative["marker"], "可以", 1)
                } else {
                    span.as_str().to_string()
                }
            })
            .into_owned()
    }

    pub(super) fn mixed_requirements(&self, text: &str) -> bool {
        self.revisions
            .iter()
            .any(|r| common(&r.prior, text) >= 2 && common(&r.later, text) >= 2)
    }

    pub(super) fn explains_requirement_change(&self, prose: &str, decision: &str) -> bool {
        (prose.contains("前段提议") || prose.contains("先后口径待核实"))
            && self.revisions.iter().any(|r| {
                [prose, decision]
                    .iter()
                    .all(|text| common(&r.prior, text) >= 2 && common(&r.later, text) >= 2)
            })
    }

    pub(super) fn reconcile_text(&self, text: &str) -> String {
        let repaired = self.repair_negation(text);
        let Some(change) = self
            .revisions
            .iter()
            .find(|r| common(&r.prior, &repaired) >= 2 && common(&r.later, &repaired) >= 2)
        else {
            return repaired;
        };
        if repaired.contains("口径待核实") || repaired.contains("前段提议") {
            return repaired;
        }
        let mut labeled = String::new();
        for part in repaired.split_inclusive(['；', '。', '，', ',']) {
            if common(&change.prior, part) >= 2 {
                let marker = if common(&change.later, part) >= 2 {
                    "先后口径待核实："
                } else {
                    "前段提议："
                };
                labeled.push_str(marker);
            }
            labeled.push_str(part);
        }
        labeled
    }

    pub(super) fn reconcile(
        &self,
        minutes: &mut CompanionV1MeetingMinutes,
        raw: &[CompanionV1ActionItem],
    ) -> bool {
        let actions_before = minutes.action_items.len();
        let decisions_before = minutes.decisions.len();
        minutes.action_items.retain(|item| {
            item.owner.is_some()
                || !WORK_IN_PROGRESS.is_match(&item.text)
                || ASSIGN.is_match(&item.text)
        });
        let mut changed = actions_before != minutes.action_items.len();
        for action in raw.iter().filter_map(|item| self.action(item)) {
            if !minutes.action_items.iter().any(|current| {
                current.text == action.text
                    || (current.owner == action.owner
                        && current.due == action.due
                        && super::source_fact_covered(&action.text, &current.text)
                        && super::source_fact_covered(&current.text, &action.text))
            }) {
                minutes.action_items.push(action);
                changed = true;
            }
        }
        let has_speakers = !self.roles.is_empty() || self.original.contains("说话人");
        if has_speakers {
            minutes
                .decisions
                .retain(|item| self.decision(item) && !self.mixed_requirements(item));
        }
        changed |= minutes.decisions.len() != decisions_before;
        for item in minutes
            .summary
            .iter_mut()
            .chain(minutes.questions.iter_mut())
        {
            let corrected = self.reconcile_text(item);
            changed |= *item != corrected;
            *item = corrected;
        }
        changed
    }
}

fn requirement_revisions(turns: &[Turn]) -> Vec<Revision> {
    let mut revisions = Vec::new();
    for (index, turn) in turns.iter().enumerate() {
        let Some(prior) = PRIOR_REQUIREMENT.captures(&turn.text) else {
            continue;
        };
        let subject: String = prior["scope"]
            .chars()
            .rev()
            .take(2)
            .collect::<Vec<_>>()
            .into_iter()
            .rev()
            .collect();
        let prior = subjects(prior["condition"].trim_start_matches('就'));
        if prior.len() < 2 {
            continue;
        }
        for (offset, later) in turns.iter().enumerate().skip(index + 1).take(12) {
            let Some(sufficient) = LATER_REQUIREMENT.captures(&later.text) else {
                continue;
            };
            let context = &turns[offset.saturating_sub(2).max(index + 1)..=offset];
            let related = context.iter().any(|near| near.text.contains(&subject));
            let revisits_prior = context.iter().any(|near| {
                ["刚才", "之前", "前面"]
                    .iter()
                    .any(|marker| near.text.contains(marker))
                    && common(&prior, &near.text) != 0
            });
            let latter = subjects(sufficient["condition"].trim_start_matches("有这种"));
            if related && revisits_prior && latter.difference(&prior).count() >= 2 {
                revisions.push(Revision {
                    prior: prior.clone(),
                    later: latter,
                });
                break;
            }
        }
    }
    revisions
}

fn normalize(text: &str) -> String {
    text.chars()
        .filter(|ch| ch.is_alphanumeric())
        .flat_map(char::to_lowercase)
        .collect()
}

fn role_key(role: &str) -> String {
    let compact = normalize(role).replace("各院", "各园");
    compact
        .strip_suffix("部门")
        .or_else(|| compact.strip_suffix('部'))
        .unwrap_or(&compact)
        .to_string()
}

fn role_eq(a: &str, b: &str) -> bool {
    role_key(a) == role_key(b)
}

fn names_actor(clause: &str, role: &str) -> bool {
    let compact = normalize(clause).replace("各院", "各园");
    let name = normalize(role).replace("各院", "各园");
    let stem = role_key(role);
    compact.contains(&name)
        || (!stem.is_empty()
            && ["部", "这块", "这边", "负责"]
                .iter()
                .any(|suffix| compact.contains(&format!("{stem}{suffix}"))))
}

fn subjects(text: &str) -> HashSet<String> {
    const FILL: &[&str] = &[
        "这个",
        "那个",
        "进行",
        "可以",
        "我们",
        "就是",
        "相关",
        "具体",
        "计划",
        "充分",
        "方案",
        "一下",
        "需要",
        "到时候",
        "也要",
        "还有",
        "负责人",
        "的话",
        "这边",
        "项目",
        "工作",
        "决定",
        "确定",
    ];
    let compact = FILL
        .iter()
        .fold(normalize(text), |text, word| text.replace(word, " "));
    compact
        .split_whitespace()
        .flat_map(|token| {
            let chars: Vec<_> = token.chars().collect();
            chars
                .windows(2)
                .map(|pair| pair.iter().collect::<String>())
                .collect::<Vec<_>>()
        })
        .collect()
}

fn common(wanted: &HashSet<String>, source: &str) -> usize {
    subjects(source).intersection(wanted).count()
}
