//! Checks that can be made against actual transcript spans before facts are frozen.
//! Literal overlap helps locate supporting context; it cannot establish entailment.
use std::{collections::HashSet,sync::LazyLock};

static MEASUREMENT:LazyLock<regex::Regex>=LazyLock::new(||{
    let number=r"(?:[0-9０-９]+(?:[.．][0-9０-９]+)?|[零〇一二两三四五六七八九十百千万亿半]+(?:点[零〇一二两三四五六七八九]+)?)";
    regex::Regex::new(&format!(r"(?:约|近|大约|最多|至少|不足)?{number}(?:(?:到|至|—|~|～){number})?(?:多|余)?\s*(?:个百分点|%|％|美元|万元|亿元|块钱|人民币|元|亿吨|万吨|公斤|吨|平方米|毫秒|分钟|小时|个月|年|天|倍|位|台|家|笔)(?:以内|以上|以下|左右)?")).expect("valid measurement expression")
});

static HISTORICAL_YEAR: LazyLock<regex::Regex> = LazyLock::new(|| {
    regex::Regex::new(r"(?:从|自|在|于|截至)\s*(?:[0-9０-９]{2,4}|[零〇一二两三四五六七八九]{2,4})年")
        .expect("valid historical year expression")
});

const OPEN_QUANTITY: &[&str] = &["有没有可能", "是否有可能", "能不能", "能否", "是否", "可不可以", "尚未确认", "还没确定"];

pub(super) fn quantity_question(source: &str) -> bool {
    has_open_qualifier(source) && MEASUREMENT.is_match(source)
}

pub(super) fn has_open_qualifier(text: &str) -> bool {
    OPEN_QUANTITY.iter().any(|cue| text.contains(cue))
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

pub(super) fn loses_binary_uncertainty(claim: &str, anchor: &str) -> bool {
    anchor.contains("有无") && !has_open_qualifier(claim)
        && !["有无", "有没有", "待确认", "待核", "尚不明确", "仍不明确"].iter().any(|cue| claim.contains(cue))
}

pub(super) fn context_only_fragment(source:&str)->bool{
    let text=source.trim().trim_end_matches(['。','！','？','；',',','，','…','.']);
    matches!(text.trim(),""|"嗯"|"呃"|"对"|"然后"|"所以"|"所以说"|"实际上"|"实际上在"|"问题"|"关于这个"|"也就是说"|"怎么说呢")
}

// In speech a tentative question and its short answer can be split across
// sentences. An opinion needs both the subject and the words expressing doubt.
pub(super) fn supports_followup_opinion(claim: &str, question: &str, answer: &str) -> bool {
    let invites_judgment = ["能不能", "能否", "是否", "可不可以", "行不行"]
        .iter()
        .any(|cue| question.contains(cue));
    let short_answer = answer.trim();
    if !invites_judgment || short_answer.chars().count() > 36 {
        return false;
    }

    let explicit_stance = ["我认为", "我个人", "我觉得", "我的看法", "我的观点", "观点其实"]
        .iter()
        .any(|cue| short_answer.contains(cue));
    let uncertainty = ["比较难", "很难", "较难", "难以", "不容易", "不太可能", "可能性不大"];
    explicit_stance
        && uncertainty.iter().any(|cue| short_answer.contains(cue))
        && uncertainty.iter().any(|cue| claim.contains(cue))
        && shared_han_phrase(claim, question, 4)
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
