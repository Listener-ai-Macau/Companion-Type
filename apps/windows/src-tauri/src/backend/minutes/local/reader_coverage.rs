//! Keep explicit, source-backed information that can be lost in the overview.
use std::{collections::HashSet, sync::LazyLock};

use regex::Regex;
use serde_json::Value;

use super::atomic_document::{ExtractedFact, MAX_FACTS};

const MAX_REVIEW_ITEMS: usize = 6;
const MAX_ITEM_CHARS: usize = 90;

struct Item {
    row: usize,
    evidence: Vec<usize>,
    key: String,
    role: &'static str,
    text: String,
}

fn source(row: &Value) -> &str {
    row["text"].as_str().unwrap_or_default()
}

// Only remove conversational glue here. Numbers, verbs, and qualifiers are
// kept as spoken. The complete original line is still attached to the item.
fn compact(text: &str) -> String {
    let mut clean = text.to_owned();
    for filler in [
        "基本上就是",
        "那么这种情况的话",
        "那么皆大欢喜",
        "咱们就是",
        "那么",
        "没有就是没有",
        "就是说",
        "或者说这个",
        "如果说",
        "皆大欢喜，",
        "直接呢",
        "看看呢",
        "呃",
        "嗯",
    ] {
        let replacement = match filler {
            "没有就是没有" => "没有",
            "或者说这个" => "或",
            "如果说" => "如果",
            "直接呢" => "直接",
            "看看呢" => "看看",
            _ => "",
        };
        clean = clean.replace(filler, replacement);
    }
    clean
        .trim_matches([' ', '，', ',', '。', '啊', '呀', '呢', '吧', '\r', '\n'])
        .to_owned()
}

fn tentative_arrangement(row: usize, raw: &str) -> Option<Item> {
    static WHEN: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(concat!(
            r"(?P<before>大概|大约|暂定|拟定|预计|初步定在|计划在)?[在要啊的 ]{0,3}",
            r"(?P<date>(?:[0-9一二三四五六七八九十零〇]{1,4}[号日]|",
            r"(?:下下|下|本|这)?周[一二三四五六日天]|[今明后]天)(?:左右|前后)?)",
        ))
        .expect("valid tentative arrangement pattern")
    });
    const MOVES: &[&str] = &[
        "搬",
        "上线",
        "交付",
        "验收",
        "启动",
        "切换",
        "提交",
        "发布",
        "发货",
        "开工",
        "停机",
        "进场",
        "到货",
        "开会",
        "开始测试",
    ];
    let text = compact(raw);
    for part in WHEN.captures_iter(&text) {
        let date = part.name("date")?;
        if part.name("before").is_none()
            && !["左右", "前后"]
                .iter()
                .any(|end| date.as_str().ends_with(*end))
        {
            continue;
        }
        let before = &text[..date.start()];
        if [
            "已经",
            "原定",
            "上次",
            "如果",
            "假如",
            "取消",
            "改到",
            "改成",
            "可能不是",
        ]
        .iter()
        .any(|cue| before.contains(cue))
        {
            continue;
        }
        let after = &text[date.end()..];
        let after = after
            .trim_start_matches("的话")
            .trim_start_matches(['，', ',', ' ']);
        if after.starts_with(['前', '后']) || after.starts_with("之前") || after.starts_with("之后")
        {
            continue;
        }
        let action = after
            .split(['，', ',', '。', '；', '？', '！'])
            .next()
            .unwrap_or_default()
            .trim();
        let Some(operation) = MOVES.iter().find(|op| action.contains(**op)) else {
            continue;
        };
        if action.is_empty()
            || action.chars().count() > 24
            || ["不搬", "不用", "不做", "不确定", "是不是", "是否", "能不能"]
                .iter()
                .any(|cue| action.contains(cue))
        {
            continue;
        }
        let point = format!("暂按{}考虑，{}。", date.as_str(), action);
        let date_key = date
            .as_str()
            .trim_end_matches("左右")
            .trim_end_matches("前后");
        return Some(Item {
            row,
            evidence: vec![row],
            key: format!("time:{date_key}:{operation}"),
            role: "question",
            text: point,
        });
    }
    None
}

fn period_comparison(row: usize, raw: &str) -> Option<Item> {
    static PERIOD: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(r"周[一二三四五](?:到|至)周?[二三四五]|周六[和及、， ]?周[日天]|工作日|周末|平日|上午|下午|白天|晚上|淡季|旺季|上半年|下半年")
            .expect("valid paired period")
    });
    let text = compact(raw);
    if ["如果", "假设", "举例", "要是"]
        .iter()
        .any(|cue| text.contains(cue))
    {
        return None;
    }
    let periods = PERIOD.find_iter(&text).collect::<Vec<_>>();
    let [a, b] = periods.as_slice() else {
        return None;
    };
    if a.as_str() == b.as_str() {
        return None;
    }
    let first = compact(&text[a.end()..b.start()]);
    let last = compact(text[b.end()..].split(['，', ',', '。', '；']).next()?);
    let describes = |part: &str| {
        !part.is_empty()
            && part.chars().count() <= 22
            && [
                "多", "少", "高", "低", "快", "慢", "还行", "一般", "拥堵", "集中", "紧张", "稳定",
                "充足", "正常",
            ]
            .iter()
            .any(|word| part.contains(word))
    };
    if !describes(&first) || !describes(&last) || first == last {
        return None;
    }
    Some(Item {
        row,
        evidence: vec![row],
        key: format!("contrast:{}:{}", a.as_str(), b.as_str()),
        role: "status",
        text: format!("{}{first}，{}{last}。", a.as_str(), b.as_str()),
    })
}

fn conditional(row: usize, raw: &str) -> Option<Item> {
    static LEAD: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(r"^(?:呃|嗯|那|那么|当然|然后|还有|再说|[，, ]){0,6}(如果说|如果|要是|若)")
            .expect("valid spoken condition marker")
    });
    let raw = raw.trim();
    let lead = LEAD.find(raw)?;
    if raw.contains(['？', '?']) {
        return None;
    }
    let rest = &raw[lead.end()..];
    let (condition, result) = ["的话，", "的话,", "，那么", "，那就", "，就", "，则"]
        .iter()
        .filter_map(|sep| rest.find(sep).map(|i| (i, sep.len())))
        .min()
        .map(|(i, len)| (&rest[..i], &rest[i + len..]))?;
    let condition = compact(condition).trim_start_matches("这个如果").to_owned();
    let result = compact(result);
    let result = result
        .trim_start_matches("呢")
        .trim_start_matches("咱们")
        .trim_start_matches(['，', ',', ' ']);
    if condition.is_empty()
        || condition.chars().count() > 34
        || result.is_empty()
        || ["比如", "举个例", "不能确定", "能不能", "怎么办"]
            .iter()
            .any(|cue| condition.contains(cue))
        || ![
            "可以", "安排", "考虑", "改", "采用", "邮寄", "拜访", "让", "先", "停止", "再", "买",
            "继续", "联系", "必须", "需要", "应当",
        ]
        .iter()
        .any(|cue| result.contains(cue))
    {
        return None;
    }
    let proposed = ["看看", "能不能", "我觉得"]
        .iter()
        .any(|cue| result.contains(cue));
    let result = result
        .split("，能不能")
        .next()?
        .split("，我觉得")
        .next()?
        .trim_end_matches("看看");
    let result = if result.chars().count() > 55 {
        result
            .rsplit_once("，然后")
            .filter(|(prior, tail)| {
                ["买", "选"].iter().any(|verb| prior.starts_with(*verb))
                    && ![
                        "必须", "只能", "不要", "不能", "之前", "以后", "如果", "审批", "确认",
                    ]
                    .iter()
                    .any(|cue| prior.contains(cue))
                    && prior.split(['，', ',', '啊']).next().is_some_and(|first| {
                        // Omit the examples only if the later action also
                        // names what to use. Preserve earlier prerequisites.
                        let reversed: Vec<_> = first.chars().rev().take(3).collect();
                        let subject: String = reversed.iter().rev().collect();
                        reversed.len() == 3 && tail.contains(&subject)
                    })
            })
            .map_or(result, |(_, tail)| tail)
            .trim_start_matches("呢")
    } else {
        result
    };
    let mode = if proposed
        && !["可以", "考虑", "必须", "需要", "应当", "不能", "禁止"]
            .iter()
            .any(|cue| result.contains(cue))
    {
        "可考虑"
    } else {
        ""
    };
    let option = format!("如果{condition}，{mode}{result}。");
    (option.chars().count() <= MAX_ITEM_CHARS && result.chars().count() >= 3).then(|| Item {
        row,
        evidence: vec![row],
        key: format!("condition:{condition}"),
        role: "question",
        text: option,
    })
}

fn link_condition_object(branch: &mut Item, rows: &[Value]) {
    static REPEATED_QUESTION: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(r"(?P<verb>[\p{Han}]{2})不(?P<repeat>[\p{Han}]{2})(?P<object>[\p{Han}]{2,10})(?:[，,。？！]|$)")
            .expect("valid spoken yes-or-no object")
    });
    let Some(prior) = branch.row.checked_sub(1) else {
        return;
    };
    for capture in REPEATED_QUESTION.captures_iter(source(&rows[prior])) {
        if capture["verb"] != capture["repeat"] {
            continue;
        }
        let prefix = format!("如果{}了，", &capture["verb"]);
        let Some(rest) = branch.text.strip_prefix(&prefix) else {
            continue;
        };
        let clarified = format!("如果{}{}，{rest}", &capture["verb"], &capture["object"]);
        if clarified.chars().count() <= MAX_ITEM_CHARS {
            branch.text = clarified;
            branch.evidence.insert(0, prior);
        }
        break;
    }
}

pub(super) fn check(rows: &[Value], facts: &mut Vec<ExtractedFact>) -> usize {
    // Search every source row independently of the model's short list.
    let mut dates = Vec::new();
    let mut comparisons = Vec::new();
    let mut branches = Vec::<Vec<Item>>::new();
    for (index, row) in rows.iter().enumerate() {
        let raw = source(row);
        dates.extend(tentative_arrangement(index, raw));
        comparisons.extend(period_comparison(index, raw));
        if let Some(mut branch) = conditional(index, raw) {
            link_condition_object(&mut branch, rows);
            if let Some(group) = branches
                .last_mut()
                .filter(|group| group.last().is_some_and(|prior| index - prior.row <= 2))
            {
                group.push(branch);
            } else {
                branches.push(vec![branch]);
            }
        }
    }
    let alternatives = branches
        .into_iter()
        .filter(|group| group.len() >= 2)
        .max_by_key(|group| (group.len().min(3), group.last().map(|item| item.row)))
        .into_iter()
        .flatten()
        .take(3);
    let mut seen = HashSet::new();
    let mut added = 0;
    let dates = dates
        .into_iter()
        .filter({
            let mut keys = HashSet::new();
            move |item| keys.insert(item.key.clone())
        })
        .take(2);
    let comparisons = comparisons.into_iter().take(1);
    for item in dates.chain(comparisons).chain(alternatives) {
        if added >= MAX_REVIEW_ITEMS || facts.len() >= MAX_FACTS {
            break;
        }
        if !seen.insert(item.key) {
            continue;
        }
        let anchors = item
            .evidence
            .iter()
            .filter_map(|&index| rows[index]["id"].as_str())
            .collect::<Vec<_>>();
        let Some(first) = anchors.first() else {
            continue;
        };
        let mut fact = ExtractedFact::verbatim(first, item.role, &item.text);
        fact.evidence = anchors.into_iter().map(str::to_owned).collect();
        fact.reader_required = true;
        if let Some(known) = facts.iter_mut().find(|known| {
            known.role == fact.role
                && known.text.trim_end_matches('。') == fact.text.trim_end_matches('。')
        }) {
            known.reader_required = true;
        } else {
            facts.push(fact);
        }
        added += 1;
    }
    if added > 0 {
        facts.sort_by_key(|fact| {
            fact.evidence
                .first()
                .and_then(|id| id.get(1..)?.parse::<usize>().ok())
                .unwrap_or(usize::MAX)
        });
    }
    added
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn source_checks_keep_uncertainty_and_time_contrast_without_a_model_draft() {
        let rows = [
            json!({"id":"e0000","text":"上午写入延迟较高，下午速度正常。"}),
            json!({"id":"e0001","text":"试验设备暂定十七号进场。"}),
            json!({"id":"e0002","text":"十七号之前完成采购计划。"}),
            json!({"id":"e0003","text":"如果主通道恢复的话，那么先切换主通道。"}),
            json!({"id":"e0004","text":"如果主通道不能恢复的话，那么必须停止测试。"}),
        ];
        let mut facts = Vec::new();
        assert_eq!(check(&rows, &mut facts), 4);
        let found: Vec<_> = facts
            .iter()
            .map(|item| {
                (
                    item.evidence[0].as_str(),
                    item.role.as_str(),
                    item.text.as_str(),
                )
            })
            .collect();
        assert_eq!(
            found,
            [
                ("e0000", "status", "上午写入延迟较高，下午速度正常。"),
                ("e0001", "question", "暂按十七号考虑，进场。"),
                ("e0003", "question", "如果主通道恢复，先切换主通道。"),
                ("e0004", "question", "如果主通道不能恢复，必须停止测试。"),
            ]
        );
        assert!(facts.iter().all(|fact| fact.reader_required));
    }
}
