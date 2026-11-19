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
        r"再(?:跟再|再)?(?:具体[体上商]?)?(?:来)?(确认|确定|核对|复核|审阅|讨论)(?:一下)?"
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
    if let Some(task) = spoken_group_handoff(source) {
        return Some(task);
    }
    let mut days = DAY.find_iter(source);
    let day = days.next()?;
    let repeated_week = source[..day.start()].ends_with("下");
    if days.next().is_some() {
        return None;
    }
    let timing_phrase = &source[day.end()..];
    let review = REVIEW.captures(timing_phrase)?;
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
    // A repeated relative week can be a transcription stutter or a real
    // later week. Retain a strongly anchored review without guessing its date.
    if repeated_week && !(cites_previous
        && has(&source[..day.start()], &["好吧", "就这样"])
        && has(timing_phrase, &["的时候", "那天"])
        && has(&timing_phrase[..review.get(0)?.start()], &["我们", "咱们"]))
    {
        return None;
    }
    let timing_note = if repeated_week { "（复核日期待确认）" } else { "" };
    Some(Followup {
        action: crate::companion_v1::CompanionV1ActionItem {
            text: format!("再{}{object}{timing_note}", review.get(1)?.as_str()),
            owner: None,
            due: (!repeated_week).then(|| day.as_str().to_owned()),
        },
        context: cites_previous.then_some(FollowupContext::Previous),
    })
}

fn spoken_group_handoff(source: &str) -> Option<Followup> {
    static REQUEST: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(concat!(
        r"(?:各自?部门|各个部门|各自?小组|各个小组)儿?[啊嗯呃，, ]*",
        r"(?:散会后|会后|回去之后|回去以后)[，, ]*(?:把|将)(?:这个|这份|这些)?",
        r"(?P<item>方案|报价|预算|计划|排期|报告|样品|设计稿)[，, ]*",
        r"(?:都)?(?:要|得|会)?(?:抓紧|尽快|赶紧)(?:完成|做(?:好|完)?|准备)(?:起来|出来)?",
        r"[吧啊呀。！，, ]*$",
    )).expect("valid spoken group handoff pattern"));
    let task = REQUEST.captures(source.trim())?;
    let item = task.name("item")?.as_str();
    Some(Followup {
        action: crate::companion_v1::CompanionV1ActionItem {
            text: format!("会后尽快完成{item}"),
            owner: None,
            due: None,
        },
        context: None,
    })
}

/// Recover explicitly addressed work without requiring the speaker to state a
/// calendar date or name. Suggestions and questions do not count as handoffs.
pub(super) fn spoken_work_request(source: &str) -> Option<Followup> {
    use crate::companion_v1::CompanionV1ActionItem;
    if has(source, &["不用", "不必", "不需要", "不要", "不打算", "不会请", "还没答应", "或许",
        "比如", "举个例", "如果", "假如", "上次", "上周", "曾经", "建议", "有没有",
        "能不能", "是否", "不确定", "要不要", "计划不"]) {
        return None;
    }
    let work = |text: String, owner: Option<&str>| Some(Followup {
        action: CompanionV1ActionItem { text, owner: owner.map(str::to_owned), due: None },
        context: None,
    });
    static DELIVERABLE: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(concat!(
        r"后期(?:的话)?[，, ]*(?:你(?:们)?(?:这块|这边)?(?:的话)?|咱们这边)?",
        r"[，, ]*(?:就(?:是)?|要)?[嗯呃啊，, ]*(?P<verb>做|出|写|列|提交)",
        r"(?:一个|一份|一张|一下)?[嗯呃啊 ]*(?P<item>数据报表|报表|方案|清单|排期|预算|报告|设计稿|报价单)"
    )).expect("valid addressed deliverable pattern"));
    static OBJECT: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"怎么把(?:这个|这批)?(?P<subject>[\x{3400}-\x{9fff}]{2,10}?)(?:咱(?:们)?(?:怎么)?|怎么)(?:进行)?(?P<goal>促销|交付|上线|推广|部署|销售)"
    ).expect("valid work object pattern"));
    if (has(source, &["你后期", "你们后期"]) || has(source, &["你这块", "你出", "你这边"]))
        && !has(source, &["可以", "要问", "不一定"])
    {
        if let Some(request) = DELIVERABLE.captures(source) {
            let item = request.name("item")?.as_str();
            let tail = &source[request.get(0)?.end()..];
            if source.contains(['？', '?']) && !tail.trim_start_matches(['，', ',', ' ', '嗯', '呃']).starts_with("怎么") {
                return None;
            }
            let text = if item == "方案" {
                if let Some(goal) = OBJECT.captures(tail) {
                    format!("拟定{}{}方案", goal.name("subject")?.as_str(), goal.name("goal")?.as_str())
                } else if source[..request.get(0)?.start()].contains("柜台") {
                    "拟定柜台陈列方案".to_owned()
                } else {
                    "拟定方案".to_owned()
                }
            } else if has(tail, &["报给我", "提交给我", "发给我"]) {
                format!("编制并上报{item}")
            } else {
                format!("准备{item}")
            };
            return work(text, None);
        }
    }
    if source.contains(['？', '?']) || has(source, &["考虑", "未同意", "没承诺"]) { return None; }
    static TRAINING: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:(?P<company>公司)[^。！？；]{0,12}会请|我会请)(?P<partner>(?:设备|产品|原)?(?:厂家|供应商|厂商))[^。！？；]{1,20}培训"
    ).expect("valid training commitment pattern"));
    if let Some(request) = TRAINING.captures(source) {
        let partner = request.name("partner")?.as_str();
        return work(format!("邀请{partner}给员工培训"), request.name("company").map(|owner| owner.as_str()));
    }
    if has(source, &["你们把时间报给我", "各部门把时间报给我"])
        && has(source, &["我来统计", "我来汇总"])
    {
        let task = if source.contains("培训") { "确定并上报培训时间" } else { "确定并上报时间" };
        return work(task.to_owned(), None);
    }
    if has(source, &["回去", "会后"]) && has(source, &["员工们", "员工", "同事"])
        && has(source, &["传达一下", "转达一下", "转告一下"])
    {
        let mut request = work("向员工传达本次会议内容".to_owned(), None)?;
        request.context = Some(FollowupContext::Next);
        return Some(request);
    }
    None
}

pub(super) fn linked_procurement_request(source: &str, next: Option<&str>) -> Option<Followup> {
    static REQUEST: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(concat!(
        r"请{1,2}(?P<owner>公司|采购部|采购团队|供应部门)(?:呢|啊)?(?:尽快|抓紧)",
        r"(?:把|将)(?:这个|这条|该)?(?P<channel>进货渠道|供应渠道|采购渠道)[。.，, ]*$"
    )).expect("valid cross-sentence procurement request pattern"));
    if source.contains(['？', '?']) || has(source, &["不用", "不要", "不需要", "之前", "如果", "假如", "建议", "能不能"]) {
        return None;
    }
    let request = REQUEST.captures(source.trim())?;
    let continuation = next?.trim_start_matches(['，', ',', ' ', '嗯', '呃', '啊']);
    let directive = ["尽快能疏疏通", "尽快能疏通", "尽快疏通", "疏通", "先疏通", "打通"]
        .iter().any(|cue| continuation.starts_with(cue));
    if !directive || continuation.contains(['？', '?'])
        || has(continuation, &["不用", "不能", "不必", "可能无法"]) {
        return None;
    }
    let channel = request.name("channel")?.as_str();
    let text = if continuation.contains("交了定金")
        && (continuation.contains("拿到") || continuation.contains("拿拿到")) {
        format!("尽快疏通{channel}，让已交定金的顾客拿到货")
    } else {
        format!("尽快疏通{channel}")
    };
    Some(Followup {
        action: crate::companion_v1::CompanionV1ActionItem {
            text, owner: Some(request.name("owner")?.as_str().to_owned()), due: None,
        },
        context: Some(FollowupContext::Next),
    })
}

#[cfg(test)]
mod spoken_work_tests {
    use super::*;

    #[test]
    fn recovers_undated_work_only_when_it_is_directly_requested() {
        let ask = |source| spoken_work_request(source).map(|item| item.action);
        let report = ask("你后期就是做一个数据报表，嗯，把它报给我。").unwrap();
        assert_eq!(report.text, "编制并上报数据报表");
        assert!(report.owner.is_none() && report.due.is_none());
        assert_eq!(ask("我会请设备厂商给现有员工培训。").unwrap().text, "邀请设备厂商给员工培训");
        assert_eq!(ask("公司会请厂商给现有员工培训。").unwrap().owner.as_deref(), Some("公司"));
        assert_eq!(ask("你们把时间报给我，我来统计。").unwrap().text, "确定并上报时间");
        for example in [
            "如果合适，你后期出一份方案。",
            "后期你可以出一份方案。",
            "建议你后期作一份报告。",
            "我想问后期是不是可以写报告。",
            "你后期出一个方案吗？",
            "公司不会请厂家给员工培训。",
        ] {
            assert!(ask(example).is_none(), "{example}");
        }
    }

    #[test]
    fn completes_a_procurement_request_across_utterances() {
        let first = "所以说请请公司呢尽快把这个进货渠道。";
        let result = linked_procurement_request(first, Some("尽快能疏疏通一下，然后让这些交了定金的顾客，尽快的把货拿拿到。")).unwrap();
        assert_eq!(result.action.text, "尽快疏通进货渠道，让已交定金的顾客拿到货");
        assert_eq!(result.action.owner.as_deref(), Some("公司"));
        assert!(linked_procurement_request(first, Some("这个以后再议。")).is_none());
        assert!(linked_procurement_request("如果可以，请采购部尽快把进货渠道。", Some("尽快疏通。")).is_none());
    }
}

// Keep an explicit assignment to contact suppliers and its comparison
// instruction together even when transcription punctuation changes.
pub(super) fn literal_supplier_comparison(source: &str, next: Option<&str>) -> Option<Followup> {
    static REQUEST: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:你这边安排|你安排|请安排|安排人|你负责|由你)[^。！？；]{0,20}(?P<vendor>厂商|供应商|厂家)[^。！？；]{0,17}?(?:找|联系|询价)"
    ).expect("valid delegated search pattern"));
    const NON_DIRECTIVE: &[&str] = &[
        "如果", "假如", "要是", "建议", "比如", "例如", "举例", "可能", "要不要", "能不能", "不知道",
        "不需要", "不用", "不要", "取消", "不再", "没必要", "不由你", "无需安排", "上周", "去年", "已经",
        "曾经", "听说", "可以安排", "可以先安排", "可以请", "可考虑", "比方",
    ];
    const MULTIPLE_SUPPLIERS: &[&str] = &["多找几家", "多联系几家", "至少找两家", "找几家"];
    let is_directive = |text: &str| !text.contains(['？', '?']) && !has(text, NON_DIRECTIVE);
    if !is_directive(source) {
        return None;
    }
    let request = REQUEST.captures(source)?;
    let vendor = request.name("vendor")?;
    let remainder = &source[request.get(0)?.end()..];
    let explicit_count = has(&source[vendor.end()..], MULTIPLE_SUPPLIERS);
    let (multiple, context) = if has(remainder, &["比价", "对比一下", "做个对比", "进行对比", "比较一下", "比一比"])
        && (explicit_count || has(remainder, &["多找", "多联系", "多询价"]))
    {
        (explicit_count, None)
    } else {
        let following = next?.trim_start_matches(['啊', '嗯', '呃', '，', ',', ' ']);
        if !is_directive(following)
            || !MULTIPLE_SUPPLIERS.iter().any(|lead| following.starts_with(lead))
            || !has(following, &["比价", "对比", "比较", "比一比"])
        {
            return None;
        }
        (true, Some(FollowupContext::Next))
    };
    let count = if multiple { "多家" } else { "" };
    Some(Followup {
        action: crate::companion_v1::CompanionV1ActionItem {
            text: format!("联系{count}{}并比较", vendor.as_str()),
            owner: None,
            due: None,
        },
        context,
    })
}

// Keep a clearly requested review with its explicit organizational owner.
// The words being reviewed must be stated, and a question in the object does
// not make a directive into an unassigned suggestion.
pub(super) fn literal_review_task(source: &str) -> Option<Followup> {
    static REVIEW: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        concat!(
            r"(?:^|[，,])\s*(?P<team>[\p{Han}]{2,7}?(?:部门|部|组|团队))",
            r"(?:(?:这一块|这块|这边)?让(?:他们|它们)(?:去)?|(?:这一块儿?|这块儿?|这边)[，, ]*(?:然后|请|麻烦)(?:去)?)",
            r"(?:看一下|核对一下|评估一下)[，, ]*\s*(?:就是)?(?P<work>[^。！？；]{4,100})",
        )
    ).expect("valid organizational review pattern"));
    static TABLE: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"列{1,3}(?:出)?(?:这个|一份|一张|个)?(?:进度表|表格)(?:过来|给我|发来|提交)"
    ).expect("valid progress table instruction pattern"));
    if has(source, &["建议", "可以考虑", "或许", "可能", "如果", "假如", "要是", "要不要", "是不是",
        "能不能", "可不可以", "或者", "不要", "暂缓", "取消", "没有要求", "不需要", "不用", "不再",
        "上周", "曾经", "举例", "比如", "例如", "比方", "听说", "可以让", "可以请", "可以先",
        "已经让", "已经请", "已经安排", "已经核对"]) {
        return None;
    }
    let (text, owner) = if let Some(review) = REVIEW.captures(source) {
        let team = review.name("team")?.as_str();
        if has(team, &["这个", "那个", "相关", "他们", "某个", "某部门", "其他", "所有", "由谁"]) { return None; }
        let work = review.name("work")?.as_str();
        let mut subjects: Vec<_> = ["主打颜色", "主推意向", "成本预算", "风险清单", "测试范围", "供应商报价",
            "发布方案", "样品规格", "设备配置"].iter().filter_map(|topic| work.find(topic).map(|index| (index, *topic))).collect();
        if subjects.is_empty() || subjects.len() > 3 { return None; }
        subjects.sort_unstable();
        let text = format!("核对{}", subjects.into_iter().map(|(_, topic)| topic).collect::<Vec<_>>().join("、"));
        (text, Some(team.to_owned()))
    } else if !source.contains(['？', '?'])
        && has(source, &["方案实行进度", "方案实施进度", "方案执行进度", "项目进度", "交付进度"])
        && TABLE.is_match(source) {
        ("列出进度表".to_owned(), None)
    } else {
        return None;
    };
    Some(Followup {
        action: crate::companion_v1::CompanionV1ActionItem { text, owner, due: None },
        context: None,
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
