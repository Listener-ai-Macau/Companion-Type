//! Conservative permissions for claims that appear as decisions or tasks.
//! Protected clauses retain their original wording and attribution.
use std::sync::LazyLock;

use super::super::canonical_brief;
use crate::companion_v1::CompanionV1ActionItem;

const DECISION: &[&str] = &[
    "会议决定", "一致决定", "一致同意", "共同决定", "我们决定", "大家同意",
    "本次会议通过", "同意通过", "确认先", "最终确定", "就这么定", "就按这个执行",
];
const ACTION: &[&str] = &["我承诺", "我负责", "我来负责", "由你负责", "由他负责", "负责提交", "负责交付"];
const NEXT_WORK: &[&str] = &["会后", "下次会议", "下周", "本周", "明天", "后天", "周一", "周二", "周三", "周四", "周五", "周六", "周日", "周末", "截止", "下班前"];
const NON_BINDING: &[&str] = &[
    "没有决定", "未作决定", "还没决定", "没有同意", "不决定", "不承诺", "还未确认",
    "如果", "假如", "假设", "建议", "希望", "可能", "讨论是否", "曾经", "上周", "上次", "过去", "之前已经",
];
const IN_MEETING: &[&str] = &["请发言", "请介绍", "请回答", "请讲", "请分享", "请谈", "接下来请", "下面请", "有请"];
const OPEN: &[&str] = &["未决", "待回答", "还没确定", "尚未确定", "还没有确定", "没有给明确答复", "没有明确答复"];
const OPEN_AGENDA: &[&str] = &["未决事项", "未决问题", "记为未决", "列为未决", "还有一个未决"];
const CLOSED_AGENDA: &[&str] = &["没有未决", "无未决", "已解决", "已经解决", "都已处理", "全部处理", "上次的未决", "上周的未决"];
const REFERENCED_AGENDA: &[&str] = &["上述", "前述", "以上", "这些未决", "前面提到的", "刚才列出的"];
const RECOMMEND: &[&str] = &["建议", "希望", "不妨", "可以考虑"];
const FORECAST: &[&str] = &["预计", "预测", "预估", "大概会", "可能会", "有望"];
const OPINION: &[&str] = &["我认为", "我觉得", "我的看法", "个人认为", "我判断", "我个人的观点", "个人的观点"];
const EXACT_RELATION: &[&str] = &[
    "报价", "价格", "费用", "收费", "成本", "预算", "金额", "计费", "付款", "采购价",
    "不意味着", "才具备", "必须先", "条件不满足", "不能因为", "不能把", "不会只", "不承诺", "没有批准", "没有约定", "除非", "顺延",
];

static QUANTITY: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
    r"(?:[0-9]+(?:[.．][0-9]+)?|[零〇一二两三四五六七八九十百千万亿半]+)\s*(?:[%％]|元|美元|块钱|台|家|天|小时|分钟|笔|吨|公斤|个月)"
).expect("valid source quantity pattern"));

static FORECAST_HORIZON: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
    r"(?:[0-9０-９]+|[零〇一二两三四五六七八九十百半]+)(?:个?月|年|周|天)"
).expect("valid forecast horizon"));

pub(super) fn timed_forecast(source: &str) -> bool {
    let source = source.trim().trim_end_matches(['。', '！', '.']);
    if source.contains(['？', '?']) || has(source, &["是否", "能不能", "还没确定", "曾经预测"]) {
        return false;
    }
    let Some((beginning, outcome)) = source.split_once("就会").or_else(|| source.split_once("将会")) else {
        return false;
    };
    // The time phrase and a complete outcome must both be present.
    has(beginning, &["未来", "往后", "接下来", "预计", "预测", "预估"])
        && FORECAST_HORIZON.is_match(beginning)
        && outcome.trim_start_matches(['，', '、', ' ', '。']).chars().take(2).count() == 2
}

fn has(source: &str, markers: &[&str]) -> bool {
    markers.iter().any(|marker| source.contains(marker))
}

fn has_direct_request(source: &str) -> bool {
    let body = super::super::source_resolution::split_turn_label(source)
        .map_or(source, |(_, words)| words);
    body.split(['，', ',', '。', '；']).any(|clause| {
        let clause = clause.trim_start_matches([' ', '嗯', '呃', '那', '就']);
        let after_time = NEXT_WORK.iter().find_map(|time| clause.strip_prefix(*time))
            .map(|rest| rest.strip_prefix("之前").or_else(|| rest.strip_prefix('前')).unwrap_or(rest));
        after_time.unwrap_or(clause).trim_start()
            .strip_prefix('请')
            .is_some_and(|rest| !rest.starts_with(['的', '了', '过'])
                && !rest.starts_with("来的"))
    })
}

#[derive(Clone)]
pub(super) struct Authority {
    pub(super) allowed: Vec<&'static str>,
    pub(super) confirmed_deadline_action: Option<CompanionV1ActionItem>,
    pub(super) verbatim: Option<&'static str>,
    pub(super) context_only: bool,
}

impl Authority {
    pub(super) fn from_source(source: &str) -> Self {
        let source = source.trim();
        let mut allowed = vec!["status"];
        if has(source, RECOMMEND) { allowed.push("recommendation"); }
        let timed_prediction = timed_forecast(source);
        if has(source, FORECAST) || timed_prediction { allowed.push("forecast"); }
        if has(source, OPINION) { allowed.push("opinion"); }
        let non_binding = has(source, NON_BINDING);
        if !non_binding && has(source, DECISION) { allowed.push("decision"); }
        if !non_binding && !has(source, IN_MEETING) && has(source, NEXT_WORK)
            && (has(source, ACTION) || has_direct_request(source))
        {
            allowed.push("action");
        }
        if has(source, OPEN) && !has(source, CLOSED_AGENDA) && !has(source, REFERENCED_AGENDA) {
            allowed.push("question");
        }
        if allowed.as_slice()==["status","opinion"]{allowed.remove(0);}

        let explicit_open_item = allowed.contains(&"question") && !allowed.contains(&"action")
            && !allowed.contains(&"decision") && !non_binding
            && has(source, OPEN_AGENDA) && !has(source, CLOSED_AGENDA);
        let mut policy = Self {
            allowed,
            confirmed_deadline_action: confirmed_deadline_action(source),
            verbatim: None,
            context_only: super::source_grounding::context_only_fragment(source),
        };
        policy.verbatim = if explicit_open_item && canonical_brief::line(source, 90) {
            Some("question")
        } else if timed_prediction || has(source, EXACT_RELATION) || QUANTITY.is_match(source)
            || super::source_grounding::quantity_question(source)
            || super::source_grounding::has_historical_year(source)
            || (source.contains("讨论") && source.contains("是否")) {
            policy.literal_topic_role(source)
        } else {
            None
        };
        policy
    }

    pub(super) fn literal_collective_decision(&self, source: &str) -> bool {
        self.allowed.contains(&"decision")
            && canonical_brief::line(source.trim(), 90)
            && ["会议决定", "本次会议通过", "一致决定", "共同决定", "我们决定", "大家一致同意", "一致同意"]
                .iter().any(|cue| source.trim_start().starts_with(cue))
    }

    pub(super) fn literal_named_assignment(source: &str) -> Option<crate::companion_v1::CompanionV1ActionItem> {
        let source = source.trim();
        if !canonical_brief::line(source, 90) || has(source, NON_BINDING)
            || has(source, &["暂定", "举例", "比如", "例如", "示例", "曾说", "声称", "听说", "已经", "已于", "已在",
                "完成了", "提交了", "交付了", "核对了", "确认了", "跟进了"]) {
            return None;
        }
        let assignments = super::super::named_deadline_actions(source);
        let [assignment] = assignments.as_slice() else { return None; };
        let owner = assignment.owner.as_deref()?;
        if has(owner, &["暂定", "计划", "拟", "由", "要求", "安排", "会上", "会议", "当时", "曾经", "表示", "预计", "负责人"])
            || assignment.text != source.trim_end_matches(['。', '！', '.']) {
            return None;
        }
        assignments.into_iter().next()
    }

    pub(super) fn literal_topic_role(&self, source: &str) -> Option<&'static str> {
        if !canonical_brief::line(source.trim(), 90) {
            return None;
        }
        self.safe_topic_role()
    }

    pub(super) fn safe_topic_role(&self) -> Option<&'static str> {
        if self.allowed.iter().any(|role| matches!(*role, "decision" | "action" | "question")) {
            return None;
        }
        self.discussion_role()
    }

    pub(super) fn discussion_role(&self) -> Option<&'static str> {
        ["recommendation", "forecast", "opinion", "status"]
            .into_iter()
            .find(|role| self.allowed.contains(role))
    }
}

// A confirmed deadline can carry a concrete deliverable without naming its owner.
fn confirmed_deadline_action(source: &str) -> Option<CompanionV1ActionItem> {
    static TASK: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(concat!(
        r"^(?:(?:对|好|行|就这么定)[，,]\s*|(?:请|务必|一定要|必须)\s*)(?:在)?",
        r"(?P<due>(?:(?:本|这|下)?(?:周|星期)[一二三四五六日天]|今天|明天|后天|[0-9]{1,2}月[0-9]{1,2}[日号])(?:上午|中午|下午|晚上)?(?:之前|前))",
        r"\s*(?:务必|一定要|必须)?(?:(?:完成|提交|交付|确认|发出)[^，,。！？；;\r\n]{2,40}|把[^，,。！？；;\r\n]{2,36}(?:做完|定完|定下来|定过来|交上来|发过来|交付|提交|完成))$",
    )).expect("valid confirmed deadline pattern"));
    let original = source.trim();
    let body = super::super::source_resolution::split_turn_label(original)
        .map_or(original, |(_, body)| body.trim());
    if !canonical_brief::line(body, 90)
        || has(body, NON_BINDING) || has(body, OPINION) || has(body, OPEN)
        || has(body, &["不知道", "比如", "例如", "举例", "示例", "暂定", "打算", "考虑", "争取",
            "尽量", "听说", "据说", "转述", "说过", "曾说", "已经", "不用", "不再", "不必",
            "不要", "不需要", "取消", "不一定", "能不能", "是否", "不可能"])
    {
        return None;
    }
    let task = TASK.captures(body.trim_end_matches(['。', '！', '.']))?;
    Some(CompanionV1ActionItem {
        text: body.to_owned(),
        owner: None,
        due: Some(task.name("due")?.as_str().to_owned()),
    })
}

pub(super) fn spoken_assignment(source: &str) -> Option<CompanionV1ActionItem> {
    static DEPARTMENT_TASK: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?P<owner>各部门|各小组|各单位|各分部|各团队|每个部门|每个小组)(?:儿)?\s*(?P<task>(?:会后|回去|下去以后|散会后)?\s*(?:就|要|务必|需要|请)?\s*(?:写|调查|核实|汇报|提交|整理|准备|检查|汇总|完成|联系|交付)[^，,。！？；;\r\n]{2,65})"
    ).unwrap());
    static NAMED_FOLLOWUP: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?P<owner>总监|主管|负责人|组长|项目经理|经理|主持人)(?:这边儿?|那边儿?)\s*(?:一定要|务必|必须)"
    ).unwrap());
    static WORK: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:咱们|我们)?(?:要做|需要做|要制定|需要制定|要准备|需要准备|要完成|需要完成)[^，,。！？；;\r\n]{2,65}"
    ).unwrap());
    static GROUP_WORK: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:也要|务必|必须)(?:给|对|为)[^，,。！？；;\r\n]{2,28}?(?:做|组织|开展|安排|进行)[^，,。！？；;\r\n]{1,25}?(?:培训|交接|演练|核验|复盘|走查|检查)"
    ).unwrap());
    let original = source.trim();
    let text = super::super::source_resolution::split_turn_label(original)
        .map_or(original, |(_, body)| body.trim());
    if has(text, NON_BINDING) || has(text, IN_MEETING) || has(text, OPEN)
        || has(text, &["能不能", "要不要", "可不可以", "有没有", "是不是", "不一定",
            "已完成", "已经", "当时", "听说", "举例", "比如", "例如", "示例"])
        || text.contains(['？', '?'])
    {
        return None;
    }
    const NEGATIONS: &[&str] = &["无需", "不用", "不再", "不要", "没有安排", "不必", "不需要", "取消"];
    // Direct exchanges often omit dates. Require both the requested verb and
    // the receiving party's undertaking, keeping the two spoken roles literal.
    static PAIRED_HANDOFF: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:你们|您|你)(?:这边儿?|那边儿?)\s*(?:负责|来|要|就)?(?:出|提交|整理|准备|提供|完成|拟定)[^，,。！？；;\r\n]{2,36}[，,]\s*(?:我们|我)(?:这边儿?|那边儿?)\s*(?:来|负责|进行)?(?:一些|一下)?(?:审批|审核|验收|确认|汇总|统计|复核)(?:[，,]?\s*(?:并|再)?(?:报告|上报)[^，,。！？；;\r\n]{1,16})?"
    ).expect("valid direct handoff pattern"));
    static COLLECT_HANDOFF: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:你们|您|你)(?:这边儿?|那边儿?)?\s*把[^，,。！？；;\r\n]{1,24}?(?:报给|发给|交给)我[，,]?\s*我(?:这边儿?)?\s*(?:来|负责)(?:汇总|统计|登记|复核|审核)"
    ).expect("valid collection handoff pattern"));
    if !has(text, NEGATIONS) && !has(text, OPINION)
        && !has(text, &["曾说", "说过", "转述", "演示", "设想", "我建议", "可以考虑"])
    {
        let mut pairs = PAIRED_HANDOFF.find_iter(text).chain(COLLECT_HANDOFF.find_iter(text));
        if let Some(pair) = pairs.next().filter(|_| pairs.next().is_none()) {
            let action = pair.as_str().trim();
            if canonical_brief::line(action, 90) {
                return Some(CompanionV1ActionItem { text: action.to_owned(), owner: None, due: None });
            }
        }
    }
    let mut group_work = GROUP_WORK.find_iter(text);
    if let Some(task) = group_work.next().filter(|_| group_work.next().is_none()) {
        // The preceding description can mention something unnecessary. An
        // explicit new subject starts a separately authorized instruction.
        let before = &text[..task.start()];
        let context = before.rfind("咱们这边").or_else(|| before.rfind("我们这边"))
            .map_or(text, |start| &text[start..]);
        if !has(context, NEGATIONS) {
            return Some(CompanionV1ActionItem { text: task.as_str().to_owned(), owner: None, due: None });
        }
    }
    if has(text, NEGATIONS) {
        return None;
    }
    if has(text, &["会后", "散会后", "回去", "下去以后", "先开到这儿", "会议结束后"]) {
        let mut matches = DEPARTMENT_TASK.captures_iter(text);
        if let Some(item) = matches.next().filter(|_| matches.next().is_none()) {
            return Some(CompanionV1ActionItem {
                text: item.get(0)?.as_str().trim().to_owned(),
                owner: Some(item.name("owner")?.as_str().to_owned()),
                due: None,
            });
        }
    }
    let mut owners = NAMED_FOLLOWUP.captures_iter(text);
    let recipient = owners.next().filter(|_| owners.next().is_none())?;
    let owner = recipient.name("owner")?.as_str();
    let prefix = &text[..recipient.get(0)?.start()];
    let mut tasks = WORK.find_iter(prefix);
    let task = tasks.next().filter(|_| tasks.next().is_none())?;
    let action = text[task.start()..].trim_end_matches(['，', '、', ',', ' ']).trim();
    canonical_brief::line(action, 90).then(|| CompanionV1ActionItem {
        text: action.to_owned(),
        owner: Some(owner.to_owned()),
        due: None,
    })
}

#[cfg(test)]
mod tests {
    use super::spoken_assignment;

    #[test]
    fn a_pair_of_spoken_undertakings_remains_a_handoff_without_an_invented_owner_or_date() {
        for (source, second_party) in [
            ("嗯，年关的时候，这不是马上呃 元旦了嘛，咱也也要搞一次活动，这个的话，呃你这边儿出一个具体的一个方案实施，我这边儿进行一些审批，报告上边儿领导，呃，咱把这个活动搞起来。", "审批，报告上边儿领导"),
            ("就是你们下边就各个定时间你们把时间报给我我来统计别的应该就是没有什么大问题了。", "把时间报给我我来统计"),
            ("你们这边整理交付清单，我们这边负责验收。", "负责验收"),
        ] {
            let assignment = spoken_assignment(source).expect("both sides make a concrete undertaking");
            assert!(source.contains(&assignment.text) && assignment.text.contains(second_party));
            assert!(assignment.owner.is_none() && assignment.due.is_none());
        }
        for source in [
            "比如你这边出一份方案，我这边来审批。",
            "如果你这边出方案，我这边审批。",
            "有人曾说你这边出方案，我这边审批。",
            "你这边不要准备方案，我这边负责审核。",
            "我觉得你这边准备一份方案，我这边审批。",
            "你这边出一份方案，我这边可以审批。",
            "请你这边介绍方案，我这边来审批。",
        ] {
            assert!(spoken_assignment(source).is_none(), "{source}");
        }
    }
}

pub(super) fn explicit_followup_object(assignment: &str, source: &str, previous: &str) -> Option<String> {
    static SUBJECT: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:员工|客户|学员|供应商|产品|设备|现场|门店)[\p{Han}]{1,10}?(?:问题|情况|状态)"
    ).unwrap());
    if !has(source, &["这个事情", "这件事", "这个问题", "这一点"]) {
        return None;
    }
    let (prefix, verb) = ["调查", "核实", "核对", "检查"].into_iter().find_map(|verb| {
        let (prefix, end) = assignment.rsplit_once(verb)?;
        matches!(end.trim_end_matches(['。', ' ']), "" | "下" | "一下" | "一下儿")
            .then_some((prefix, verb))
    })?;
    let mut subjects = SUBJECT.find_iter(previous);
    let subject = subjects.next().filter(|_| subjects.next().is_none())?.as_str();
    let joined = format!("{prefix}{verb}{subject}");
    canonical_brief::line(&joined, 90).then_some(joined)
}

pub(super) fn protected_stance(source: &str) -> Option<&'static str> {
    // A speaker can make a proposal, estimate or judgment without saying
    // “I think”. The role is governed by the original clause, not by the model.
    if has(source, &["仅代表", "只代表", "仅以个人", "这是我的想法"])
        && has(source, &["意见", "打算", "想法", "提议", "我想"])
    {
        return Some("recommendation");
    }
    if has(source, &["好像", "大概", "估计", "预计", "约莫", "大约"]) && QUANTITY.is_match(source) {
        // Approximation describes precision. Only treat a clearly reported
        // past amount as status when there is no forecast or future cue.
        let forward = has(source, FORECAST) || has(source, &[
            "接下来", "未来", "今后", "以后", "将会", "将要", "还要", "计划", "打算", "如果", "假如", "要是",
        ]);
        let retrospective = has(source, &["当时", "那时候", "此前", "以前", "过去", "上一年", "去年"]);
        let measured = source.split(['，', ',', '。', '；', ';']).any(|clause| {
            QUANTITY.is_match(clause) && has(clause, &[
                "给了", "收了", "退回了", "发了", "付了", "花了", "卖了", "用了", "赔了", "完成了",
            ])
        });
        return Some(if !forward && (retrospective || measured) { "status" } else { "forecast" });
    }
    let compact = source.replace(char::is_whitespace, "");
    if !has(&compact, DECISION)
        && (has(&compact, &["我感觉可以", "我感觉啊可以", "我想可以"])
            || (has(&compact, &["接下来", "刚开业", "在前几个月", "后面", "将来"])
                && has(&compact, &["工作内容可以", "运营方式可以", "活动安排可以", "试行方式可以"])))
    {
        return Some("recommendation");
    }
    let hypothetical = has(source, &["如果", "假如", "假设", "比如", "举个例", "请问"]);
    let uncertain = has(source, &["可能", "会不会", "是否", "好像", "有待", "尚不清楚"]);
    let judgment = has(source, &["负主要责任", "负次要责任", "有责任", "没有责任", "违法", "违规",
        "承担责任", "构成犯罪", "承担行政", "赔偿责任", "负全责", "责任可能", "违背意愿"]);
    if (hypothetical && has(source, &["案例", "责任", "请问", "违法", "是否", "个人", "怎么办"]))
        || (judgment && (hypothetical || uncertain || has(source, &["合情合法", "就是强迫", "我觉得"])))
    {
        return Some("opinion");
    }
    None
}

#[cfg(test)]
#[test]
fn a_past_approximate_amount_keeps_the_original_reporting_time() {
    assert_eq!(
        protected_stance("呃四五万块钱，有当时每个人的股份大概也就才"),
        Some("status")
    );
    assert_eq!(protected_stance("后来退的时候给了大概四五万块钱。"), Some("status"));
    assert_eq!(protected_stance("当时预计要花大约五万元。"), Some("forecast"));
    assert_eq!(protected_stance("下次付款大概还要五万元。"), Some("forecast"));
    assert_eq!(protected_stance("如果已经花了大概五万元，可以再提交。"), Some("forecast"));
    assert_eq!(protected_stance("好像是两天到三天。"), Some("forecast"));
}
