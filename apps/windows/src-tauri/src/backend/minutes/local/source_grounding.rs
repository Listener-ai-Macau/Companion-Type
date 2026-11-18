//! Checks that can be made against actual transcript spans before facts are frozen.
//! Literal overlap helps locate supporting context; it cannot establish entailment.
use std::{collections::HashSet,sync::LazyLock};

static MEASUREMENT:LazyLock<regex::Regex>=LazyLock::new(||{
    let number=r"(?:[0-9０-９]+(?:[.．][0-9０-９]+)?|[零〇一二两三四五六七八九十百千万亿半]+(?:点[零〇一二两三四五六七八九]+)?)";
    regex::Regex::new(&format!(r"(?:约|近|大约|最多|至少|不足)?{number}(?:(?:到|至|—|~|～){number})?(?:多|余)?\s*(?:个百分点|%|％|美元|万元|亿元|块钱|人民币|元|亿吨|万吨|公斤|吨|平方米|毫秒|分钟|小时|个月|年|天|倍|位|台|家|笔)(?:以内|以上|以下|左右)?")).expect("valid measurement expression")
});

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

pub(super) fn context_only_fragment(source:&str)->bool{
    let text=source.trim().trim_end_matches(['。','！','？','；',',','，','…','.']);
    matches!(text.trim(),""|"嗯"|"呃"|"对"|"然后"|"所以"|"所以说"|"实际上"|"实际上在"|"问题"|"关于这个"|"也就是说"|"怎么说呢")
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
