//! Conservative permissions for claims that appear as decisions or tasks.
//! Protected clauses retain their original wording and attribution.
use std::sync::LazyLock;

use super::super::canonical_brief;

const DECISION: &[&str] = &[
    "会议决定", "一致决定", "一致同意", "共同决定", "我们决定", "大家同意",
    "本次会议通过", "同意通过", "确认先", "最终确定", "就这么定", "就按这个执行",
];
const ACTION: &[&str] = &["我承诺", "我负责", "我来负责", "由你负责", "由他负责", "请", "负责提交", "负责交付"];
const NEXT_WORK: &[&str] = &["会后", "下次会议", "下周", "本周", "明天", "后天", "周一", "周二", "周三", "周四", "周五", "周六", "周日", "周末", "截止", "之前", "下班前"];
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

// These are assertions by a participant, even if spoken without an
// explicit first-person marker. A minutes entry cannot establish a legal
// exemption on that basis. A report of an already issued approval is separate.
pub(super) fn reader_opinion(source: &str) -> bool {
    if timed_forecast(source) { return false; }
    if has(source, OPINION) || has(source, &["在我看来", "我个人来讲"]) { return true; }
    has(source, &["碳税", "关税", "免税", "免征", "缴税", "征税", "缴纳税款", "审批", "许可证"])
        && has(source, &["不需要", "无需", "不用", "不必", "不应", "不该", "可以免", "可以不交"])
}


#[derive(Clone, Copy)]
pub(super) enum FollowupContext {
    Previous,
    Next,
}
pub(super) struct Followup {
    pub(super) action: crate::companion_v1::CompanionV1ActionItem,
    pub(super) context: Option<FollowupContext>,
}

// Record a definite dated review as a task. If the spoken follow-up uses a
// pronoun or drops its object, only the immediately preceding work instruction
// may supply it. Missing names are left empty.
pub(super) fn literal_followup(source: &str, previous: Option<&str>) -> Option<Followup> {
    static DAY: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:本周|这周|下周|星期)[一二三四五六日天](?:上午|下午|晚上)?"
    ).expect("valid review date pattern"));
    static REVIEW: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"再(?:具体[上商]?)?(?:来)?(确认|确定|核对|复核|审阅|讨论)(?:一下)?"
    ).expect("valid review request pattern"));
    const OBJECTS: &[&str] = &["时间表", "交付计划", "设计稿", "方案", "报价", "预算", "计划", "排期", "需求", "报告", "样品"];
    const CONDITIONAL: &[&str] = &["如果", "假如", "要是", "可能", "建议", "比如", "例如", "举例",
        "未确定", "不用", "取消", "不再", "不需要", "不要", "上周", "当时", "听说"];
    const ALTERNATIVES: &[&str] = &["或者", "还是", "要不要", "能不能", "能否", "好不好", "行不行",
        "有没有意见", "要不", "是否"];
    if source.contains(['？', '?']) || has(source, CONDITIONAL) {
        return None;
    }
    static DIRECTIVE: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:散会后|会后|回去之后|回去以后)[^。！？；]{0,18}(?:把|将)(?:这个|这份|这些)?(方案|报价|预算|计划|排期|报告|样品|设计稿)[^。！？；]{0,20}(整理|汇总|补齐|落实|提交|发来|交付)"
    ).expect("valid post-meeting work request pattern"));
    if has(source, &["给我", "请", "必须", "由"]) {
        if let Some(work) = DIRECTIVE.captures(source).filter(|work| {
            work.get(0).is_some_and(|directive| !has(directive.as_str(), ALTERNATIVES))
        }) {
            return Some(Followup {
                action: crate::companion_v1::CompanionV1ActionItem {
                    text: format!("{}{}", work.get(2)?.as_str(), work.get(1)?.as_str()),
                    owner: None,
                    due: None,
                },
                context: None,
            });
        }
    }
    if has(source, ALTERNATIVES) { return None; }
    let mut days = DAY.find_iter(source);
    let day = days.next()?;
    if days.next().is_some() || source[..day.start()].ends_with("下") {
        return None;
    }
    let review = REVIEW.captures(&source[day.end()..])?;
    let after_review = source[day.end() + review.get(0)?.end()..].trim_start_matches([' ', '，', ',']);
    let after_review = after_review.strip_prefix("这个").or_else(|| after_review.strip_prefix('这')).unwrap_or(after_review);
    let object = OBJECTS.iter().copied().find(|object| after_review.starts_with(object));
    let (object, cites_previous) = match object {
        Some(object) => (object, false),
        None => {
            let rest = after_review.trim_matches([' ', '。', '！', '，', ',', '.']);
            if !rest.is_empty() { return None; }
            let prior = previous?.trim().trim_end_matches(['。', '.', '！']);
            if prior.contains(['？', '?']) || has(prior, CONDITIONAL) || has(prior, ALTERNATIVES)
                || !has(prior, &["安排", "回去", "催", "赶紧", "提交", "发来", "会后"]) {
                return None;
            }
            (OBJECTS.iter().copied().find(|object| prior.ends_with(object))?, true)
        }
    };
    Some(Followup {
        action: crate::companion_v1::CompanionV1ActionItem {
            text: format!("再{}{object}", review.get(1)?.as_str()),
            owner: None,
            due: Some(day.as_str().to_owned()),
        },
        context: cites_previous.then_some(FollowupContext::Previous),
    })
}

// An explicit delegated search and the immediately following comparison
// instruction are one task. The continuation must name both the multiple
// candidates and the comparison; no date or person's identity is inferred.
pub(super) fn literal_supplier_comparison(source: &str, next: &str) -> Option<Followup> {
    static REQUEST: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:你这边安排|你安排|请安排|安排人|你负责|由你)[^。！？；]{0,20}(?:厂商|供应商|厂家)[^。！？；]{0,17}(?:找|联系|询价)"
    ).expect("valid delegated search pattern"));
    if [source, next].iter().any(|text| text.contains(['？', '?']) || has(text, &[
        "如果", "假如", "要是", "建议", "比如", "例如", "可能", "要不要", "能不能", "不知道", "不需要",
        "不用", "不要", "取消", "不再", "没必要", "不由你", "无需安排", "上周", "去年", "已经", "曾经", "听说",
    ])) {
        return None;
    }
    let request = REQUEST.find(source)?.as_str();
    let search = next.trim_start_matches(['啊', '嗯', '呃', '，', ',', ' ']);
    if !["多找几家", "多联系几家", "至少找两家", "找几家"].iter().any(|lead| search.starts_with(lead))
        || !has(search, &["比价", "对比", "比较", "比一比"]) {
        return None;
    }
    let counterpart = ["厂商", "供应商", "厂家"].iter().find(|term| request.contains(**term))?;
    Some(Followup {
        action: crate::companion_v1::CompanionV1ActionItem {
            text: format!("联系多家{counterpart}并比较"),
            owner: None,
            due: None,
        },
        context: Some(FollowupContext::Next),
    })
}

fn has(source: &str, markers: &[&str]) -> bool {
    markers.iter().any(|marker| source.contains(marker))
}

#[derive(Clone)]
pub(super) struct Authority {
    pub(super) allowed: Vec<&'static str>,
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
        if !non_binding && !has(source, IN_MEETING) && has(source, NEXT_WORK) && has(source, ACTION) {
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
        if !canonical_brief::line(source.trim(), 90)
            || self.allowed.iter().any(|role| matches!(*role, "decision" | "action" | "question")) {
            return None;
        }
        ["recommendation", "forecast", "opinion", "status"]
            .into_iter()
            .find(|role| self.allowed.contains(role))
    }
}
