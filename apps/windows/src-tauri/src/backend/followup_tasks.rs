//! Recover narrowly supported follow-up fields for meetings without saved outcomes.
use regex::Regex;
use std::{collections::HashMap, sync::LazyLock};

struct ReviewWork<'a> {
    action: String,
    owner: Option<&'a str>,
    timing: Option<&'a str>,
    condition: Option<&'static str>,
    after_check: bool,
    evidence: Vec<&'a str>,
}

fn exact_turn(line: &str) -> Option<&str> {
    let (label, speech) = line.split_once([':', '：'])?;
    label.strip_prefix("说话人").filter(|n| !n.is_empty() && n.chars().all(|c| c.is_ascii_digit()))?;
    Some(speech.trim())
}

fn deadline_check<'a>(index: usize, turns: &[&'a str]) -> Option<ReviewWork<'a>> {
    // Time attaches only to the inspection verb in the promise. The preceding
    // repair discussion does not inherit that deadline.
    static INSPECTION: LazyLock<Regex> = LazyLock::new(|| Regex::new(concat!(
        r"(?:保证|安排|计划|会在|要在)(?:在)?(?P<when>[^，。！？；]{2,25}(?:之前|前)(?:[一二两三四五六七八九十0-9]{1,3}(?:个)?(?:星期|周|天|小时))?)",
        r"[，, ]*(?:我们|咱们|我)?(?:一定)?(?:会|要)?(?:把)?[^，。！？；]{0,15}?(?:检查|检验|核查)(?:一遍|一次|完)"
    )).expect("literal event time attached to an inspection"));
    let raw = turns[index];
    let speech = exact_turn(raw)?;
    let found = INSPECTION.captures(speech)?;
    let timing = found.name("when")?.as_str();
    let leading = &speech[..found.get(0)?.start()];
    if ["如果", "假如", "比如", "要不要", "能不能", "原来要", "听说", "上次", "去年", "曾经", "上个月"]
        .iter().any(|cue| leading.contains(cue)) {
        return None;
    }
    let previous = turns[index.saturating_sub(3)..index].iter().rev()
        .find(|line| ["设备", "设施", "器材"].iter().any(|noun| line.contains(noun)));
    let things = ["设备", "设施", "器材"].iter().copied().find(|noun| {
        speech.contains(noun) || previous.is_some_and(|line| line.contains(noun))
    })?;
    let use_specialist = (leading.contains("专业人员") || leading.contains("专业的人员"))
        && leading.contains("检查");
    let tradeoffs = leading.contains("维修") && leading.contains("更换");
    let action = format!("{}检查{things}一遍", if use_specialist { "安排专业人员" } else { "" });
    let mut evidence = vec![raw];
    if !speech.contains(things) {
        evidence.push(*previous?);
    }
    Some(ReviewWork {action, owner:None, timing:Some(timing), condition:None, after_check:tradeoffs, evidence})
}

fn conditional_booking<'a>(index: usize, turns: &[&'a str]) -> Option<ReviewWork<'a>> {
    let raw = turns[index];
    let speech = exact_turn(raw)?;
    let (speaker, _) = raw.split_once([':', '：'])?;
    let has_guidance = ["指导", "引导"].iter().any(|cue| speech.contains(cue));
    let has_booking = ["提前预约", "提前约好", "提前跟他们约好"].iter().any(|cue| speech.contains(cue));
    if !speech.contains("设施") || !speech.contains("需要") || !speech.contains("专业") || !has_guidance
        || !has_booking || ["不用预约", "不需要预约", "比如", "假如"].iter().any(|cue| speech.contains(cue))
    { return None; }
    let condition = turns[index + 1..(index + 4).min(turns.len())].iter().find(|line|
        exact_turn(line).is_none_or(|words| !words.trim_matches(['嗯','哦','啊','对','好','。','，',' ']).is_empty()))?;
    let (other, words) = condition.split_once([':', '：'])?;
    if other != speaker || !words.trim().starts_with("如果") || !words.contains("玩")
        || !(words.contains("教练") || words.contains("专业人员")) || !words.contains("指导")
    { return None; }
    Some(ReviewWork {
        action:"提前约好专业人员提供指导".into(), owner:None, timing:None,
        condition:Some("团队使用需要专业指导的设施时"), after_check:false, evidence:vec![raw,*condition],
    })
}

fn closing_delivery(raw: &str) -> Option<ReviewWork<'_>> {
    static HANDOFF: LazyLock<Regex> = LazyLock::new(|| Regex::new(concat!(
        r"^(?:嗯|那|行|然后|这边|，| |下去之后|散会后|会后|会议结束后|下去以后|回去后)*",
        r"(?:你们|大家|咱们|我们)?(?:都要|请|需要|务必|就是|要|都|将|把|，| ){0,10}",
        r"(?P<owner>各(?:个)?(?:部门|小组|项目组|单位|团队|门店))(?:儿)?",
        r"[^。！？；]{0,24}?(?P<object>计划书|计划|方案|清单|报告|台账|材料)(?:然后|然后再|再|就是|，| ){0,7}",
        r"(?:报给|交给|发给|提交给)(?P<recipient>经理|项目经理|董事长|主管|负责人|主任)"
    )).expect("explicit grouped work sent to a named recipient"));
    let speech = exact_turn(raw)?;
    if !speech.contains("散会") && !speech.contains("会议结束") && !speech.contains("到此结束") {
        return None;
    }
    let instruction = speech.split("好吧").next().unwrap_or(speech);
    if instruction.contains(['？', '?']) || ["要不要", "如果", "示例", "比如", "不用", "建议", "曾经"]
        .iter().any(|cue| instruction.contains(cue))
    {
        return None;
    }
    let task = HANDOFF.captures(instruction)?;
    Some(ReviewWork {
        action:format!("把{}交给{}{}", &task["object"], &task["recipient"],
            if instruction.contains("过目") { "过目" } else { "" }),
        owner:Some(task.name("owner")?.as_str()), timing:None, condition:None, after_check:false, evidence:vec![raw],
    })
}

pub(super) fn render(source: &str) -> Option<String> {
    let turns = source.lines().map(str::trim).filter(|line| !line.is_empty()).collect::<Vec<_>>();
    let mut counts = HashMap::new();
    for &line in &turns {
        *counts.entry(line).or_insert(0usize) += 1;
    }
    let mut work = Vec::new();
    for (index, &line) in turns.iter().enumerate() {
        let closing = index + 12 >= turns.len();
        if let Some(item) = deadline_check(index, &turns)
            .or_else(|| conditional_booking(index, &turns))
            .or_else(|| closing.then(|| closing_delivery(line)).flatten())
        {
            if item.evidence.iter().all(|quote| counts.get(quote) == Some(&1))
                && !work.iter().any(|saved: &ReviewWork| saved.action == item.action)
            {
                work.push(item);
            }
        }
        if work.len() == 8 { break; }
    }
    if work.is_empty() { return None; }
    let cards = work.into_iter().map(|item| {
        let mut line = format!("- {}。责任：{}。时间：{}。",
            item.action, item.owner.unwrap_or("待核实"), item.timing.unwrap_or("待核实"));
        if let Some(condition) = item.condition {
            line.push_str(&format!("适用条件：{condition}。"));
        }
        if item.after_check {
            line.push_str("检查后按需维修或更换，完成时间待核实。");
        }
        for evidence in item.evidence {
            line.push_str(&format!("\n> {evidence}"));
        }
        line
    }).collect::<Vec<_>>().join("\n\n");
    Some(format!("## 待核实的跟进清单\n\n{cards}"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn inspection_due_does_not_become_a_repair_due() {
        let text = "说话人3: 现场设备要先检查。\n说话人1: 我们请专业人员过来检查，有问题再维修或更换，安排在顾客来之前两天，我要把设备检查一遍。";
        let card = render(text).unwrap();
        assert!(card.contains("安排专业人员检查设备一遍。责任：待核实。时间：顾客来之前两天。"));
        assert!(card.contains("检查后按需维修或更换，完成时间待核实。"));
        assert!(render("说话人1: 上次我们谈的是设备，安排在顾客来之前两天，我要把设备检查一遍。").is_none());
    }

    #[test]
    fn a_booking_needs_the_same_speakers_condition() {
        let first = "说话人2: 有的设施需要专业人员指导，我们会提前预约。";
        let same = "说话人2: 如果他们想玩那些设施，我们会派教练提供指导。";
        let other = "说话人4: 换个话题，我们要取消这个项目。";
        assert!(render(&format!("{first}\n说话人1: 嗯。\n{same}")).unwrap().contains("适用条件：团队使用需要专业指导的设施时。"));
        assert!(render(&format!("{first}\n{other}\n{same}")).is_none());
    }

    #[test]
    fn closing_transfer_retains_the_owner_and_no_invented_deadline() {
        let action = "说话人1: 会后你们把各小组的清单交给主任，让主任过目，好吧？那现在散会。";
        assert!(render(action).unwrap().contains("把清单交给主任过目。责任：各小组。时间：待核实。"));
        assert!(render("说话人1: 会后要不要各小组写清单交给主任？今天散会。").is_none());
    }
}
