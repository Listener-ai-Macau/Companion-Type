//! Read facts that affect execution directly from the original turn. The
//! surrounding prose and headings are still chosen by the existing organizer.
use std::sync::LazyLock;

use regex::Regex;
use serde_json::Value;

use super::super::{canonical_brief, source_resolution::split_turn_label};

fn has(value: &str, patterns: &[&str]) -> bool {
    patterns.iter().any(|word| value.contains(word))
}

fn body(text: &str) -> &str {
    split_turn_label(text.trim()).map_or(text.trim(), |(_, words)| words.trim())
}

pub(super) fn execution_passage(original: &str) -> Option<&str> {
    static THRESHOLD: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:[0-9零一二两三四五六七八九十]{1,4}月|(?:超过|不超过|不少于|不低于|至少)[0-9零一二两三四五六七八九十]{1,5}(?:天|日|小时|班|分钟)|百分之)"
    ).expect("stated limit or date"));
    static REPLY_END: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"[，, ]*(?:明白吗|知道吗|对吧|行吗|好吧|是吧)[？?。.\s]*$"
    ).expect("a spoken request for acknowledgment"));

    let words = body(original);
    let words = REPLY_END.replace(words, "");
    let full = words.trim_end_matches(['。', '！', '，', ',', ' ']).trim();
    if full.contains(['？', '?']) || has(full, &["举个例", "如果我是", "假设", "上一次", "上次我们", "听说", "可能会"]) {
        return None;
    }
    let source = body(original);
    let full = source.get(..full.len())?;
    let requirement = has(full, &["必须", "务必", "不得", "不允许", "需要", "及时", "要做好", "要知道", "要控制"]);
    let operation = has(full, &[
        "核查", "核验", "核实", "报告", "报修", "上报", "复查", "复检", "查验", "检查", "巡逻", "巡查",
        "挂失", "消毒", "清洗", "控温", "温度", "水温", "登记", "维修", "更换", "防汛", "整改",
        "来找谁", "报警", "安全通道", "消防", "应对", "体格", "通知", "工作交接",
    ]);
    let time_window = THRESHOLD.is_match(full)
        && has(full, &["时间是", "时间为", "安排在", "到中旬", "月份到", "月份儿到", "截止", "必须", "目标", "合格"]);
    let target = full.contains("百分之") && has(full, &["目标", "达到", "完好率", "满意程度", "回访率"])
        && has(full, &["响应", "回访", "达标", "完好", "上岗", "满意"]);
    let escalates = has(full, &["如果发现", "发现问题", "有故障", "有损坏", "发现故障"])
        && has(full, &["上报", "维修", "更换", "通知", "报告", "转交"]);
    if (requirement && operation) || time_window || target || escalates {
        return (full.chars().count() >= 8).then_some(full);
    }
    None
}

pub(super) struct OpeningAgenda {
    pub(super) text: String,
    pub(super) citations: Vec<String>,
}

pub(super) fn opening_agenda(sentences: &[Value], roles: &[(usize, &str, &str)]) -> Option<OpeningAgenda> {
    let first_turn = sentences.iter().take(24).position(|sentence| {
        sentence["text"].as_str().is_some_and(|text| {
            let Some((speaker, words)) = split_turn_label(text.trim()) else { return false; };
            roles.iter().any(|(_, label, role)| *label==speaker && super::source_commitments::meeting_lead(role))
                && has(words, &["今天", "本次", "这场"])
                && has(words, &["开会", "开一个", "开一场", "开个", "叫过来", "叫来", "主持", "会议", "商讨"])
        })
    })?;
    let window = &sentences[first_turn..(first_turn+12).min(sentences.len())];
    let find = |patterns: &[&str]| window.iter().find(|row| row["text"].as_str().is_some_and(|text| has(text, patterns)));
    let mut cited = vec![&window[0]];
    let period = [
        (&["上半年度", "上半年"][..], "上半年"),
        (&["上个季度", "上季度", "上一季度"][..], "上季度"),
        (&["上一年度", "去年"][..], "上一年度"),
    ].into_iter().find_map(|(forms, period)| find(forms).map(|row| (row, period)));
    let review = [
        (&["销售情况", "销售儿情况"][..], "销售情况"),
        (&["经营情况", "运营情况"][..], "运营情况"),
        (&["工作情况", "总结会议", "总结一下"][..], "工作情况"),
    ].into_iter().find_map(|(forms, scope)| find(forms).map(|row| (row, scope)));
    let text = if let (Some((period_row, period)), Some((review_row, scope))) = (period, review) {
        cited.extend([period_row, review_row]);
        let mut text = format!("回顾{period}{scope}");
        if let Some(row) = find(&["下半年", "下半年度", "下个月"]).filter(|row| {
            let words = row["text"].as_str().unwrap_or("");
            has(words, &["工作计划", "工作安排", "工作的一个安排", "本部门儿的一个工作计划"])
        }) {
            cited.push(row);
            let words = row["text"].as_str().unwrap_or("");
            let next = if has(words, &["下半年度", "下半年"]) { "下半年" } else { "下个月" };
            text.push_str(&format!("，讨论{next}工作安排"));
        }
        text
    } else if let (Some(project), Some(comparison)) = (
        find(&["团建活动", "团建项目"]),
        find(&["谁表现的最好", "谁的方案", "各抒己见", "比选"]),
    ) {
        cited.extend([project, comparison]);
        "讨论团建方案，并比较承接部门".to_owned()
    } else {
        return None;
    };
    let mut citations = Vec::new();
    for row in cited {
        let id = row["id"].as_str()?.to_owned();
        if !citations.contains(&id) { citations.push(id); }
    }
    canonical_brief::line(&text, 80).then_some(OpeningAgenda { text, citations })
}

pub(super) fn presents_bid(sentences: &[Value], evidence: &[String]) -> bool {
    let Some(opening) = sentences.iter().take(28).position(|row| {
        row["text"].as_str().is_some_and(|text| {
            has(text, &["谁表现的最好", "谁的方案好", "比选", "择优"])
                && has(text, &["交给", "负责", "承接", "方案", "选择"])
        })
    }) else { return false; };
    evidence.iter().any(|id| {
        sentences.iter().skip(opening+1).find(|row| row["id"].as_str()==Some(id.as_str()))
            .and_then(|row| row["text"].as_str()).is_some_and(|text| {
                let words = body(text);
                has(words, &["我们会", "我会", "我们可以", "我建议", "我们能"])
                    && has(words, &["让他们", "安排", "方案", "带他们", "提供"])
                    && !has(words, &["已经", "最终决定", "已确定"])
            })
    })
}
