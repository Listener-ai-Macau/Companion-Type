//! Conservative CJK/Latin line wrapping, preserving every non-format character.
/// One presentation quote, removed exactly once by rich document renderers.
/// The saved speech itself is never parsed as Markdown structure.
pub(super) fn quote_literal_lines(text:&str)->String{
    text.lines().map(|line|format!("> {line}")).collect::<Vec<_>>().join("\n")
}
pub(super) fn visual_line(text:&str)->&str {
    let trimmed=text.trim_start();trimmed.strip_prefix("> ").unwrap_or(text)
}
fn units(c:char)->usize {
    match c {
        '\t'=>16,
        'W'|'M'|'w'|'m'|'@'|'#'|'%'=>4,
        _=>match c as u32 {
            0x0300..=0x036f|0xfe00..=0xfe0f|0x200d=>0,
            0..=0x7f=>if c.is_whitespace()||"ilI.,:;!'`|".contains(c){2}else{3},
            0x80..=0x024f=>3,
            _=>4,
        }
    }
}
pub(super) fn wrap(text:&str,limit:usize)->Vec<String>{
    let chars=text.chars().collect::<Vec<_>>();
    if chars.is_empty(){return vec![String::new()];}
    let mut result=Vec::new();let mut start=0;
    while start<chars.len(){
        let mut end=start;let mut width=0;let mut last_space=None;
        while end<chars.len()&&(width+units(chars[end])<=limit||end==start){
            width+=units(chars[end]);end+=1;
            if chars[end-1].is_whitespace()&&chars[start..end].iter().any(|c|!c.is_whitespace()){last_space=Some(end);}
        }
        if end<chars.len(){if let Some(space)=last_space{end=space;}}
        result.push(chars[start..end].iter().collect());start=end;
    }
    result
}
pub(super) fn root_lines(text:&str,limit:usize)->Vec<String>{
    let mut rows=wrap(text,limit);
    if rows.len()>1&&rows.last().is_some_and(|line|line.chars().count()<=2)
        &&text.chars().any(|c|('\u{4e00}'..='\u{9fff}').contains(&c))
        &&text.chars().all(|c|!c.is_ascii_alphanumeric()&&!c.is_whitespace()) {
        let last=rows.pop().unwrap();let prior=rows.pop().unwrap();let combined=(prior+&last).chars().collect::<Vec<_>>();
        let middle=combined.len().div_ceil(2);
        rows.push(combined[..middle].iter().collect());rows.push(combined[middle..].iter().collect());
    }
    rows
}
#[cfg(test)]mod tests{
    use super::*;
    #[test]fn content052_wrapping_keeps_words_and_all_source_characters(){
        let source="The purchase has not been approved. 尚未批准20%的追加费用。";
        let rows=wrap(source,34);assert_eq!(rows.concat(),source);
        assert!(rows.iter().any(|s|s.contains("approved.")));
        assert!(wrap("先核对开发内容与引用出处。",16).len()>1);
        let wide="W".repeat(60);let rows=wrap(&wide,68);
        assert!(rows.iter().all(|row|row.len()<=17));assert_eq!(rows.concat(),wide);
        let title="公开示例·采购与交付复盘";let rows=root_lines(title,44);
        assert_eq!(rows.concat(),title);assert!(rows.iter().all(|line|line.chars().count()>=3));
    }
}
