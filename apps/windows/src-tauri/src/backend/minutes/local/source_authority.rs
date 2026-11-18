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
        if has(source, FORECAST) { allowed.push("forecast"); }
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
        } else if has(source, EXACT_RELATION) || QUANTITY.is_match(source)
            || (source.contains("讨论") && source.contains("是否")) {
            policy.literal_topic_role(source)
        } else {
            None
        };
        policy
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
