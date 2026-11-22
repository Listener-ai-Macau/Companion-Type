//! Checks that can be made against actual transcript spans before facts are frozen.
//! Literal overlap helps locate supporting context; it cannot establish entailment.
use std::{collections::HashSet,sync::LazyLock};
use regex::Regex;
use super::super::canonical_brief;

static MEASUREMENT:LazyLock<regex::Regex>=LazyLock::new(||{
    let number=r"(?:[0-9０-９]+(?:[.．][0-9０-９]+)?|[零〇一二两三四五六七八九十百千万亿半]+(?:点[零〇一二两三四五六七八九]+)?)";
    regex::Regex::new(&format!(r"(?:约|近|大约|最多|至少|不足)?{number}(?:(?:到|至|—|~|～){number})?(?:多|余)?\s*(?:个百分点|%|％|美元|万元|亿元|块钱|人民币|元|亿吨|万吨|公斤|吨|平方米|毫秒|分钟|小时|个月|年|天|倍|位|台|家|笔)(?:以内|以上|以下|左右)?")).expect("valid measurement expression")
});

static HISTORICAL_YEAR: LazyLock<regex::Regex> = LazyLock::new(|| {
    regex::Regex::new(r"(?:从|自|在|于|截至)\s*(?:[0-9０-９]{2,4}|[零〇一二两三四五六七八九]{2,4})年")
        .expect("valid historical year expression")
});

const OPEN_QUANTITY: &[&str] = &["有没有可能", "是否有可能", "能不能", "能否", "是否", "可不可以", "尚未确认", "还没确定", "待核实", "待核对"];

pub(super) fn unclear_percentage(source: &str, claim: &str) -> bool {
    static COLLIDING_UNITS: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"([0-9０-９]+(?:[.．][0-9０-９]+)?\s*[%％])\s*[年月日周天]\s*的"
    ).expect("percentage followed by an inconsistent unit"));
    let claim = canonical_brief::normalized(claim);
    COLLIDING_UNITS.captures_iter(source).any(|matched| {
        claim.contains(&canonical_brief::normalized(matched.get(1).unwrap().as_str()))
    })
}

pub(super) fn reversed_standalone_range(text: &str) -> bool {
    static RANGE: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?P<low>[0-9０-９零〇一二两三四五六七八九十]{1,3})\s*(?:至|到|—)\s*(?P<high>[0-9０-９零〇一二两三四五六七八九十]{1,3})\s*(?:周岁|岁|小时|分钟|个月|天|人|元|家|个|次)"
    ).expect("standalone numerical range"));
    fn count(text: &str) -> Option<u32> {
        let normalized = normalize_number(text);
        if let Ok(value) = normalized.parse() {
            return Some(value);
        }
        let digit = |word: &str| match word {
            "零" | "〇" => Some(0), "一" => Some(1), "二" | "两" => Some(2), "三" => Some(3),
            "四" => Some(4), "五" => Some(5), "六" => Some(6), "七" => Some(7),
            "八" => Some(8), "九" => Some(9), _ => None,
        };
        if let Some((tens, ones)) = normalized.split_once('十') {
            return Some(10 * if tens.is_empty() { 1 } else { digit(tens)? }
                + if ones.is_empty() { 0 } else { digit(ones)? });
        }
        digit(&normalized)
    }
    RANGE.captures_iter(text).any(|part| {
        let span = part.get(0).unwrap();
        let before = text[..span.start()].trim_end();
        !before.ends_with(['从', '由']) && matches!(
            (count(&part["low"]), count(&part["high"])), (Some(start), Some(end)) if start > end
        )
    })
}

pub(super) fn conflicting_release_time(source: &str, claim: &str) -> bool {
    static EARLIER: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:已经|现已|此前|当时)[^。；！？]{0,14}(?:上线|发布|推出|投入使用)|(?:上线|发布|推出|投入使用)了"
    ).expect("observed past release"));
    static LATER: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:这些|这批|该|这个|上述)[^。；！？]{0,18}(?:明年|下半年|下个月|下周)\s*(?:才|再|将|开始)?\s*(?:开发|研发|上线|发布|推出)"
    ).expect("future statement about the same item"));
    let Some(past) = EARLIER.find(source) else { return false; };
    let Some(later) = LATER.find(&source[past.end()..]) else { return false; };
    let scope = &source[past.end()..past.end()+later.end()];
    if ["新版本","升级版","第二批","后续版本","二期","另一"].iter().any(|term| scope.contains(term)) {
        return false;
    }
    let relevant = ["明年","下半年","下个月","下周","开发","研发","上线","发布","推出","投入使用"];
    relevant.iter().any(|term| claim.contains(term)) && shared_han_phrase(source,claim,3)
}

pub(super) fn named_place_context(source: &str) -> Option<&str> {
    let tokens = super::chapter_labels::segmenter().tag(source, false);
    let mut candidates = tokens.iter().enumerate().filter_map(|(index, token)| {
        if token.tag != "ns" || token.word.chars().count() < 2 { return None; }
        if ["山区", "农村", "乡村", "城区", "郊区", "市区", "外地", "国内", "国外", "当地"].contains(&token.word) {
            return None;
        }
        let following = tokens.iter().skip(index+1).find(|token| !token.word.trim().is_empty());
        let named_subject = following.is_some_and(|token| {
            token.tag.starts_with('n') && token.word.chars().count() >= 2
        });
        let explicit_context = source.match_indices(token.word).any(|(start, _)| {
            let before = source[..start].trim_end();
            ["在", "对", "于", "针对", "关于", "发生在"].iter().any(|lead| before.ends_with(lead))
        });
        (named_subject || explicit_context).then_some(token.word)
    });
    let first = candidates.next()?;
    candidates.all(|place| place == first).then_some(first)
}

pub(super) fn unsupported_comparative(claim: &str, anchor: &str) -> bool {
    let comparisons = ["更适用", "更适合", "更合适", "更为适用", "更为合适", "优于", "胜过"];
    comparisons.iter().any(|cue| claim.contains(cue))
        && !comparisons.iter().any(|cue| anchor.contains(cue))
}

pub(super) fn capability_is_proposed(claim: &str, preceding: &str) -> bool {
    claim.contains("可以")
        && !["已经", "目前", "现有"].iter().any(|cue| claim.contains(cue))
        && ["我们希望做", "我们希望能", "未来希望", "我们的设想", "计划开发"]
            .iter().any(|cue| preceding.contains(cue))
        && shared_han_phrase(claim, preceding, 3)
}

pub(super) fn quantity_question(source: &str) -> bool {
    has_open_qualifier(source) && MEASUREMENT.find_iter(source).any(|span| {
        let calendar_context = span.as_str() == "半年"
            && (source[..span.start()].ends_with(['上', '下'])
                || (source[..span.start()].ends_with('这')
                    && source[span.end()..].starts_with(['里', '中'])));
        !calendar_context
    })
}

pub(super) fn has_open_qualifier(text: &str) -> bool {
    OPEN_QUANTITY.iter().any(|cue| text.contains(cue))
}

pub(super) fn crosses_negated_cost_comparison(claim: &str, source: &str) -> bool {
    static NEGATED: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:没有|不比|并不)[^，。；,;]{0,22}(?:更高|高于|贵于)"
    ).unwrap());
    static POSITIVE: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:更高|高于|贵于)"
    ).unwrap());
    const COST_LABELS: &[&str] = &["价格", "价钱", "费用", "成本", "收费", "报价"];
    COST_LABELS.iter().any(|term| claim.contains(term))
        && COST_LABELS.iter().any(|term| source.contains(term))
        && POSITIVE.is_match(claim) && !NEGATED.is_match(claim)
        && !claim.contains("不高于") && !claim.contains("不贵于")
        && NEGATED.is_match(source)
}

pub(super) fn has_historical_year(source: &str) -> bool {
    HISTORICAL_YEAR.is_match(source)
}

fn normalize_number(value:&str)->String{
    value.chars().filter(|c|!c.is_whitespace()).map(|c|match c {
        '至'|'—'|'~'|'～'=>'到',
        '％'=>'%',
        '．'=>'.',
        '０'..='９'=>char::from_u32(c as u32-0xff10+u32::from(b'0')).unwrap(),
        _=>c,
    }).collect()
}

pub(super) fn unsupported_quantities(claim:&str,sources:&[&str])->Vec<String>{
    let units:HashSet<_>=sources.iter().flat_map(|source|MEASUREMENT.find_iter(source).map(|m|normalize_number(m.as_str()))).collect();
    MEASUREMENT.find_iter(claim).filter_map(|m|{
        (!units.contains(&normalize_number(m.as_str()))).then(||m.as_str().to_owned())
    }).collect()
}

pub(super) fn is_brief_thanks(source: &str) -> bool {
    let source = source.trim();
    source.chars().count() <= 15
        && ["谢谢", "好，谢谢", "好的，谢谢", "好谢谢", "好的谢谢"].iter().any(|prefix| source.starts_with(prefix))
        && !source.contains(['；', '?', '？'])
}

pub(super) fn says_meeting_ended(text: &str) -> bool {
    ["会议结束", "结束会议", "圆桌结束", "讨论结束", "暂告一段落", "暂告于段落"]
        .iter().any(|cue| text.contains(cue))
}

pub(super) fn linked_secondary_status(claim: &str, source: &str) -> bool {
    shared_han_phrase(claim, source, 3)
}

pub(super) fn copied_from_other_sentence<'a>(claim: &str, anchor: &str, nearby: impl Iterator<Item = &'a str>) -> bool {
    // A reference key alone does not establish a connection. Detect a clear
    // drop in literal support at the claimed anchor without reassigning the fact.
    let chars: Vec<_> = claim.chars().collect();
    let phrases: HashSet<_> = chars.windows(2)
        .filter(|pair| pair.iter().all(|ch| matches!(*ch, '\u{3400}'..='\u{9fff}')))
        .map(|pair| pair.iter().collect::<String>())
        .filter(|phrase| !["目前", "这个", "这些", "一些", "一个", "讨论", "问题", "认为", "建议"].contains(&phrase.as_str()))
        .collect();
    let overlap = |text: &str| phrases.iter().filter(|phrase| text.contains(phrase.as_str())).count();
    let at_anchor = overlap(anchor);
    at_anchor < 3 && nearby.into_iter().any(|text| overlap(text) >= (at_anchor + 3).max(4))
}

pub(super) fn concerns_approval(text: &str) -> bool {
    ["批准", "批复", "获批"].iter().any(|marker| text.contains(marker))
}

pub(super) fn provisional_passage(source: &str) -> Option<&str> {
    static TENTATIVE: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:暂{1,2}定){1,2}\s*[^，,。！!？?；;\r\n]{2,42}"
    ).expect("tentative spoken decision"));
    let found = TENTATIVE.find(source)?;
    let lead = &source[..found.start()];
    let lead = lead.rsplit(['。', '！', '？', '；']).next()?;
    if !["先", "就", "咱", "我们", "暂且"].iter().any(|cue| lead.contains(cue))
        || ["建议", "假设", "比如", "听说", "取消", "没有", "要不要"]
            .iter().any(|cue| lead.contains(cue))
    {
        return None;
    }
    let literal = found.as_str().trim();
    let end = ["嗯", "呃", "那咱", "然后", "行吧"]
        .into_iter().filter_map(|cue| literal.find(cue)).min().unwrap_or(literal.len());
    canonical_brief::line(&literal[..end], 66).then_some(literal[..end].trim())
}

pub(super) fn categorical_safety_claim(claim: &str, evidence: &str) -> bool {
    ["存在", "已经", "肯定", "是高风险"].iter().any(|cue| claim.contains(cue))
        && ["安全", "风险"].iter().any(|cue| claim.contains(cue) && evidence.contains(cue))
        && ["不太安全", "我担心", "不太放心", "我不放心", "会不会有风险"]
            .iter().any(|cue| evidence.contains(cue))
        && !["我担心", "担忧", "顾虑", "与会者", "有人认为", "会议中提到"]
            .iter().any(|cue| claim.contains(cue))
}

pub(super) fn risk_followed_by_mitigation(warning: &str, response: &str) -> bool {
    let response = response.trim();
    ["不安全", "有危险", "有风险", "容易受伤", "有安全隐患"]
        .iter().any(|cue| warning.contains(cue))
        && !response.contains(['？', '?'])
        && ["然后", "所以", "因此", "那就"].iter().any(|cue| response.starts_with(cue))
        && ["安全措施", "防护措施", "陪同", "工作人员带", "工作人员，带", "安排专人"]
            .iter().any(|cue| response.contains(cue))
}

pub(super) fn offers_mitigation(source: &str, next: &str) -> Option<String> {
    use super::super::source_resolution::split_turn_label;
    let (speaker, warning) = split_turn_label(source.trim())?;
    let continuation = if let Some((other, words)) = split_turn_label(next.trim()) {
        if other != speaker { return None; }
        words.trim()
    } else {
        if source.ends_with('\n') { return None; }
        next.trim()
    };
    let warning = warning.trim();
    if !risk_followed_by_mitigation(warning, continuation) { return None; }
    let separator = if warning.ends_with(['？', '?', '。', '！', '!']) { "" } else { "。" };
    let sentence = format!("{warning}{separator}{continuation}");
    canonical_brief::line(&sentence, 90).then_some(sentence)
}

/// A qualified exception carries its own literal subject. Keep that
/// source alongside earlier restrictions on the same object.
pub(super) fn restriction_exception(source: &str) -> Option<(&str, &str)> {
    static RELAXED: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:如果|若是|要是|考虑到|遇到)[^。！？；]{2,36}(?:可以不{1,2}|不必|无须|无需)\s*(?:控制|禁止|限制|拦截|强制|要求|禁止携带)"
    ).expect("condition that relaxes a restriction"));
    let words = super::super::source_resolution::split_turn_label(source.trim())
        .map_or(source.trim(), |(_, body)| body.trim());
    let found = RELAXED.find(words)?;
    let before = &words[..found.start()];
    if before.chars().count() > 32 { return None; }
    let subject = super::chapter_labels::segmenter().tag(before, false).into_iter().rev()
        .filter(|tag| tag.tag.starts_with('n'))
        .map(|tag| tag.word.trim_end_matches('儿'))
        .find(|word| {
            (2..=9).contains(&word.chars().count())
                && !["事情", "情况", "问题", "方面", "东西"].contains(word)
        })?;
    canonical_brief::line(words, 74).then_some((subject, words))
}

pub(super) fn unqualified_restriction(claim: &str, subject: &str) -> bool {
    claim.contains(subject)
        && ["禁止", "不得", "不许", "不允许", "不能携带", "不可以携带", "不准", "一律不"]
            .iter().any(|cue| claim.contains(cue))
        && !["如果", "除非", "可以不", "不必", "无需", "例外", "视情况"]
            .iter().any(|cue| claim.contains(cue))
}

pub(super) fn addressed_generalization(source: &str, claim: &str) -> bool {
    let emphatic = ["基本上", "绝对", "肯定", "根本", "一定"];
    source.contains('你')
        && ["刚毕业", "刚入职", "进了", "去了", "到那之后"].iter().any(|cue| source.contains(cue))
        && emphatic.iter().any(|cue| source.contains(cue) && claim.contains(cue))
        && !["已经核实", "数据显示", "实际记录"].iter().any(|cue| source.contains(cue))
}

pub(super) fn loses_binary_uncertainty(claim: &str, anchor: &str) -> bool {
    anchor.contains("有无") && !has_open_qualifier(claim)
        && !["有无", "有没有", "待确认", "待核", "尚不明确", "仍不明确"].iter().any(|cue| claim.contains(cue))
}

pub(super) fn adds_categorical_outcome(claim: &str, evidence: &[&str]) -> bool {
    // These expressions claim that an outcome already occurred or that a
    // scope is exhaustive. A paraphrase with no literal witness is returned
    // to the original passage before it can become a meeting conclusion.
    const OUTCOMES: &[&str] = &["严重流失", "流失严重", "大量流失", "而离开", "已辞退", "已解聘",
        "全部完成", "全部到账", "已经到账", "全部退出", "已经关闭", "已经停业", "全部停产",
        "全部批准", "全体同意", "无一例外", "基本无人参加教学", "从未发生",
        "一律取消", "已经退款", "永久停用"];
    OUTCOMES.iter().any(|term| claim.contains(term) && !evidence.iter().any(|source| source.contains(term)))
}

pub(super) fn ambiguous_payment_reference(source: &str) -> Option<usize> {
    static PAYMENT: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:他的|她的|它的|其)(?:这项|这个)?(?:收费|价格|费用|成本)"
    ).unwrap());
    let unresolved = PAYMENT.find(source)?;
    let before = &source[..unresolved.start()];
    (before.contains("和") || before.contains('或')).then_some(unresolved.start())
}

pub(super) fn payment_without_guessing(source: &str, reference: usize) -> String {
    let before = source[..reference].trim_end_matches(['，', ',', ' ', ':', '：']);
    let before = before.strip_suffix("但是").unwrap_or(before).trim_end_matches(['，', ',', ' ']);
    format!("{before}。具体收费所指待核实。")
}

pub(super) fn dropped_source_clause(claim: &str, source: &str) -> bool {
    let text = claim.trim();
    source.trim().chars().count() >= 40 && text.chars().count() <= 12
        && ["是", "就是", "因为", "然后", "主要是", "为了"].iter().any(|end| text.ends_with(end))
        && source.contains(text)
}

pub(super) fn explicit_source_uncertainty(source: &str) -> bool {
    ["情况还不清楚", "情况尚不明确", "事情还没弄清", "信息还没核实", "有点儿模棱两可", "事实暂时不清"]
        .iter().any(|cue| source.contains(cue))
}

pub(super) fn cited_but_unsettled(claim: &str, anchor: &str, preceding: &[&str]) -> Option<(usize, usize)> {
    // A speaker can deny that an event occurred and then describe an intention
    // involving the same event. A nearby explicit warning keeps that account
    // from becoming a settled status.
    static NEGATED: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:还没有|并没有|没有|并未|尚未|暂未)(?P<event>[\p{Han}]{3,8})"
    ).unwrap());
    let unresolved = preceding.iter().rposition(|text| explicit_source_uncertainty(text))?;
    if preceding[unresolved + 1..].iter().any(|text| {
        ["核实后确认", "现已核实", "最终确认", "核对后确定"].iter().any(|cue| text.contains(cue))
    }) {
        return None;
    }
    let (speaker, original) = super::super::source_resolution::split_turn_label(anchor)?;
    preceding.iter().enumerate().skip((unresolved + 1).max(preceding.len().saturating_sub(3)))
        .rev().find_map(|(offset, text)| {
            let (previous_speaker, previous_text) = super::super::source_resolution::split_turn_label(text)?;
            if previous_speaker != speaker {
                return None;
            }
            NEGATED.captures_iter(previous_text).find_map(|capture| {
                let event = capture.name("event")?.as_str();
                let at = original.find(event)?;
                let before = original[..at].trim_end();
                (claim.contains(event) && ["要", "要进行", "拟", "计划", "准备", "想"]
                    .iter().any(|cue| before.ends_with(cue))).then_some((unresolved, offset))
            })
        })
}

pub(super) fn context_only_fragment(source:&str)->bool{
    let text=source.trim().trim_end_matches(['。','！','？','；',',','，','…','.']);
    matches!(text.trim(),""|"嗯"|"呃"|"对"|"然后"|"所以"|"所以说"|"实际上"|"实际上在"|"问题"|"关于这个"|"也就是说"|"怎么说呢")
}

// In speech a tentative question and its short answer can be split across
// sentences. An opinion needs both the subject and the words expressing doubt.
const OPINION_UNCERTAINTY: &[&str] = &["比较难", "很难", "较难", "难以", "不容易", "不太可能", "可能性不大"];

pub(super) fn is_short_opinion_answer(text: &str) -> bool {
    let text = text.trim();
    let stance = ["我认为", "我个人", "我觉得", "我的看法", "我的观点", "观点其实"];
    text.chars().count() <= 36 && stance.iter().any(|cue| text.contains(cue))
        && OPINION_UNCERTAINTY.iter().any(|cue| text.contains(cue))
}

pub(super) fn links_opinion_followup(question: &str, answer: &str) -> bool {
    ["能不能", "能否", "是否", "可不可以", "行不行"].iter().any(|cue| question.contains(cue))
        && is_short_opinion_answer(answer)
}

pub(super) fn supports_followup_opinion(claim: &str, question: &str, answer: &str) -> bool {
    links_opinion_followup(question, answer)
        && OPINION_UNCERTAINTY.iter().any(|cue| claim.contains(cue))
        && shared_han_phrase(claim, question, 4)
}

// Attach a demonstrative reply to its actual question before it enters the
// fact bank. A nearby caller or a later topic supplies no subject authority.
pub(super) fn scoped_reply<'a>(question: &'a str, answer: &'a str) -> Option<(&'a str, &'a str)> {
    use super::super::source_resolution::split_turn_label;
    let (question_speaker, question) = split_turn_label(question.trim()).unwrap_or(("", question.trim()));
    let (speaker, answer) = split_turn_label(answer.trim()).unwrap_or(("", answer.trim()));
    let question = question.trim();
    let answer = answer.trim();
    if (!speaker.is_empty() && speaker == question_speaker)
        || !question.ends_with(['？', '?']) || answer.contains(['？', '?'])
        || !["这个我们", "这个的话", "这个是", "这方面我们", "这件事我们", "对此我们"]
            .iter().any(|prefix| answer.starts_with(prefix))
        || ["另一个", "另外一件", "先不谈", "以后再说"].iter().any(|cue| answer.contains(cue))
    {
        return None;
    }
    let question = question.trim_end_matches(['？', '?']);
    let (scope, ending) = question.rsplit_once(['，', ',', '。'])?;
    if !["这个", "这件事", "怎么", "如何", "最后", "当时", "要不要"]
        .iter().any(|cue| ending.trim().starts_with(cue))
        || !(10..=45).contains(&scope.trim().chars().count())
    {
        return None;
    }
    Some((scope.trim(), answer))
}

pub(super) fn bounded_scoped_reply(scope: &str, answer: &str) -> Option<String> {
    let prefix = format!("关于「{scope}」的答复：");
    if canonical_line(&prefix, answer) {
        return Some(format!("{prefix}{answer}"));
    }
    let (lead, clause) = ["我们的处理是", "最终的处理是", "最后的结论是", "现在的要求是", "具体的安排是",
        "我们的要求是", "明确的条件是", "实际的做法是"]
        .iter().find_map(|marker| answer.split_once(marker))?;
    let clause = clause.trim();
    if clause.chars().count() < 12 || !canonical_line(&prefix, clause)
        || ["如果", "除非", "只有", "仅限", "必须", "不能", "不再", "尚未"].iter()
            .any(|cue| lead.contains(cue) && !clause.contains(cue))
    {
        return None;
    }
    Some(format!("{prefix}{clause}"))
}

fn canonical_line(prefix: &str, text: &str) -> bool {
    super::super::canonical_brief::line(&format!("{prefix}{text}"), 90)
}

pub(super) fn topic_relation_clarification(text: &str, preceding: &[&str]) -> bool {
    static ASSERTED: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:两人|两个|二人|他们|她们|双方)[^。？！；]{0,12}(?:的关系|之间的关系)(?:是|就是|确实是|仍然是)[^，。？！；]{2,12}"
    ).expect("explicit relation with a stated result"));
    ASSERTED.is_match(text)
        && preceding.iter().any(|source| {
            source.trim().ends_with(['？','?'])
                && ["有关系", "有什么关系", "什么关系", "哪种关系"].iter().any(|cue| source.contains(cue))
        })
}

// Retain a contrast between two explicit conditions as one bounded quotation.
// A paraphrase can attach the second condition's permission to both groups.
pub(super) fn preserve_distinct_scope(original: &str) -> Option<(String, bool)> {
    static CONFLICT: LazyLock<regex::Regex> = LazyLock::new(|| Regex::new(
        r"(?:这个人?|他们|对方|这些人|顾客|游客|这种人)?(?:不是|并非|不属于)(?:我们(?:的)?|本公司|本单位|公司(?:的)?)?(?:员工|职工|职员)[，,\s]*(?:我们|公司|本单位)(?:是)?(?:可以|能够|能)(?:直接)?(?:从公司|从工资|扣工资|扣薪|扣款|罚款)[^，,。！？；;]{0,22}",
    ).expect("unresolved scope of a payroll deduction"));
    if let Some(witness) = CONFLICT.find(original) {
        let line = format!("原话待核：{}。", witness.as_str().trim());
        if canonical_brief::line(&line, 90) {
            return Some((line, true));
        }
    }
    static TIMED: LazyLock<regex::Regex> = LazyLock::new(|| Regex::new(
        r"(?:等|当)(?:[^。！？；,，]{2,27}?)(?:的时候|时)[^。！？；]{4,33}$"
    ).expect("first stated applicability"));
    for (at, divider) in original.match_indices("但是") {
        let before = original[..at].trim_end_matches(['，', ',', ' ']);
        let after = original[at + divider.len()..].trim_start();
        if !["像", "针对", "只给", "仅对", "对于", "如果是", "而在"]
            .iter().any(|lead| after.starts_with(lead)) {
            continue;
        }
        let Some(left) = TIMED.find_iter(before).last() else { continue; };
        let Some((condition, outcome)) = after.split_once("的时候").or_else(|| after.split_once("时")) else { continue; };
        if condition.chars().count() > 32 || !["可以", "允许", "支持", "不可以", "不得", "不能"].iter().any(|e| outcome.contains(e)) {
            continue;
        }
        let cut = ["，", ",", "。", "；", "！", "？", "这些", "那么后面", "后面的", "然后呢"]
            .iter().filter_map(|marker| outcome.find(marker)).min().unwrap_or(outcome.len());
        let end = outcome[..cut].trim_end();
        if end.chars().count() < 5 || ["这些", "那个", "然后"].iter().any(|tail| end.ends_with(tail)) {
            continue;
        }
        let right = &after[..(after.len() - outcome.len()) + end.len()];
        let line = format!("{}，但是{}。", left.as_str().trim(), right.trim());
        if canonical_brief::line(&line, 90) {
            return Some((line, false));
        }
    }
    None
}

/// Returns the literal part that distinguishes a material condition from
/// similar talking points in a chapter. The remainder still comes from source.
pub(super) fn material_condition(source: &str) -> Option<&str> {
    static ADVANCE: LazyLock<regex::Regex> = LazyLock::new(|| Regex::new(
        r"提前[0-9０-９一二两三四五六七八九十半]{1,4}(?:个?星期|个?礼拜|个?月|周|天|小时)"
    ).expect("explicit lead time"));
    if let Some(lead) = ADVANCE.find(source).filter(|_| {
        ["递交", "提交", "布置", "交付", "交给", "实施", "配合", "安排", "审查", "查看"]
            .iter().any(|cue| source.contains(cue))
    }) {
        return Some(lead.as_str());
    }
    static PERMISSION: LazyLock<regex::Regex> = LazyLock::new(|| Regex::new(
        r"(?:是否同意|取得同意|获得同意|得到同意|经[^，,。；]{1,14}同意|征得[^，,。；]{0,12}同意)[^。！？；]{0,42}(?:签字|签订|签合同|签署|授权|合同|协议)"
    ).expect("consent and agreement in the original"));
    if let Some(witness) = PERMISSION.find(source) {
        return Some(witness.as_str());
    }
    static STATUS_BOUNDARY: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:暂未|尚未|还没|还没有|没有)(?:正式)?开始(?:研发|生产|施工|安装|执行|实施|采购|签约|上线)"
    ).expect("explicit project status boundary"));
    STATUS_BOUNDARY.find(source).map(|w| w.as_str())
}

pub(super) fn isolated_revenue_scope<'a>(reported: &'a str, prior: &[&str], meeting: &str) -> Option<&'a str> {
    let (business, amounts) = reported.split_once("业务收入")?;
    if !amounts.contains("净利润") { return None; }
    let category = revenue_category(business)?;
    let industry = prior.iter().rev().find_map(|line| {
        let (lead, _) = line.split_once("行业")?;
        let lead = lead.trim_end_matches(['的', ' ']).trim_end_matches("这个").trim_end_matches("那个");
        revenue_category(lead)
    })?;
    (!business.contains(industry) && industry != category && meeting.matches(category).count() == 1)
        .then_some(category)
}

fn revenue_category(text: &str) -> Option<&str> {
    let word = super::chapter_labels::segmenter().tag(text, false).into_iter().last()?.word;
    (word.chars().count() >= 2 && word.chars().all(|ch| matches!(ch, '一'..='鿿' | '㐀'..='䶿'))
        && !["这个", "那个", "自己", "我们", "你们", "整个", "目前"].contains(&word)).then_some(word)
}

// A judgment can be categorical in the paraphrase even if only a different
// circumstance in the same paraphrase retained its condition.
pub(super) fn missing_judgment_condition<'a>(claim: &str, preceding: &[&'a str]) -> Option<(usize, &'a str)> {
    let verdict = claim.split(['。', '！', '？', '；']).next()?;
    let target = ["定性为", "判定为", "构成"].iter()
        .find_map(|signal| verdict.split_once(signal).map(|(_, target)| target))?;
    if target.chars().count() < 2
        || ["如果", "假如", "只有", "查实", "查出来", "要是", "前提"].iter().any(|cue| verdict.contains(cue)) {
        return None;
    }
    preceding.iter().enumerate().rev().find_map(|(offset, row)| {
        let words = super::super::source_resolution::split_turn_label(row).map(|(_, words)| words).unwrap_or(row);
        (["如果", "假如", "只有", "要是", "查出来"].iter().any(|cue| words.contains(cue))
            && shared_han_phrase(target, words, 2)).then_some((offset, words))
    })
}

pub(super) fn literal_repair_excerpt(original: &str, excerpt: &str) -> bool {
    if !(20..=80).contains(&excerpt.chars().count()) || !original.contains(excerpt)
        || excerpt.ends_with(['，', ',', '：', ':', '？', '?'])
        || ["因为", "如果", "但是", "就是", "的话", "没有", "不能", "还是"].iter().any(|tail| excerpt.ends_with(tail))
    {
        return false;
    }
    // An exact extract may still change the meaning by removing a condition.
    ["如果", "假如", "除非", "只有", "仅限", "不能", "没有", "不再", "不一定", "未获", "或者", "待确认"]
        .iter().all(|cue| !original.contains(cue) || excerpt.contains(cue))
        && unsupported_quantities(excerpt, &[original]).is_empty()
}

pub(super) fn shared_han_phrase(left: &str, right: &str, length: usize) -> bool {
    let chars: Vec<_> = left.chars().collect();
    chars.windows(length).any(|part| {
        part.iter().all(|ch| matches!(*ch, '\u{3400}'..='\u{9fff}'))
            && right.contains(&part.iter().collect::<String>())
    })
}

pub(super) fn supports_cost_consequence(claim: &str, context: &str) -> bool {
    const COST: &[&str] = &["成本", "费用", "支出", "开销"];
    const DIRECTIONS: &[&[&str]] = &[
        &["下降", "降低", "减少", "下调"],
        &["上升", "增加", "增长", "上调", "上涨"],
    ];
    const NEGATIONS: &[&str] = &["不", "不会", "未", "没有", "未能"];
    let changes = |text: &str, cues: &[&str]| {
        cues.iter().flat_map(|cue| text.match_indices(cue)).map(|(index, _)| {
            let before = text[..index].trim_end();
            NEGATIONS.iter().any(|negation| before.ends_with(negation))
        }).collect::<HashSet<_>>()
    };
    COST.iter().any(|cue| claim.contains(cue))
        && COST.iter().any(|cue| context.contains(cue))
        && DIRECTIONS.iter().any(|cues| {
            let expected = changes(claim, cues);
            !expected.is_empty() && expected == changes(context, cues)
        })
}

pub(super) fn adjacent_cost_support(claim: &str, anchor: &str, previous: &str) -> bool {
    if !["这", "那", "所以", "因此"].iter().any(|cue| anchor.contains(cue))
        || !supports_cost_consequence(claim, previous) {
        return false;
    }
    let context: Vec<_> = anchor.chars().collect();
    context.windows(2).filter(|pair| pair.iter().all(|ch| matches!(*ch, '\u{3400}'..='\u{9fff}')))
        .map(|pair| pair.iter().collect::<String>())
        .filter(|phrase| previous.contains(phrase.as_str()) && !["因为", "如果", "这样", "因此", "所以", "的话", "就是", "我们"].contains(&phrase.as_str()))
        .collect::<HashSet<_>>().len() >= 2
}

pub(super) fn cost_cause_needs_source(claim: &str, sources: &[&str]) -> bool {
    ["导致", "因为", "由于", "从而", "取决于"].iter().any(|cue| claim.contains(cue))
        && supports_cost_consequence(claim, claim)
        && !sources.iter().any(|source| supports_cost_consequence(claim, source))
}

pub(super) fn additional_literal_support<'a>(claim:&str,already:&[&str],nearby:&[(&'a str,&str)])->Option<&'a str>{
    // A distinctive contiguous Han phrase in the claim and one nearby source
    // can supply the missing antecedent. Ignore generic low-value overlap and
    // avoid inventing a source relationship when two candidates tie.
    let characters:Vec<char>=claim.chars().collect();
    let phrases:HashSet<String>=characters.windows(5).filter(|part|part.iter().all(|c|matches!(*c,'\u{3400}'..='\u{9fff}')))
        .map(|part|part.iter().collect::<String>())
        .filter(|phrase|!already.iter().any(|source|source.contains(phrase))&&
            !["一个非常重要的","进一步的发展","我们认为这个","目前是发现了这个问题"].iter().any(|generic|generic.contains(phrase)))
        .collect();
    if phrases.is_empty(){return None;}
    let mut best=None;
    let mut best_score=0;
    for (id,source) in nearby {
        let score=phrases.iter().filter(|phrase|source.contains(phrase.as_str())).count();
        if score>best_score{best=Some(*id);best_score=score;}
        else if score>0&&score==best_score{best=None;}
    }
    best
}
