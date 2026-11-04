//! Saved meeting documents. The source is the same persisted Markdown used by
//! existing exports; these conversions never call a service or modify a session.
use std::io::{Cursor, Write};
use zip::{write::SimpleFileOptions, CompressionMethod, ZipWriter};

fn xml(value: &str) -> String {
    let mut out = String::with_capacity(value.len());
    for c in value.chars() {
        match c {
            '&' => out.push_str("&amp;"), '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"), '"' => out.push_str("&quot;"),
            '\'' => out.push_str("&apos;"),
            '\n' => out.push_str("&#10;"), '\r' => out.push_str("&#13;"), '\t' => out.push_str("&#9;"),
            c if c < '\u{20}' || c == '\u{fffe}' || c == '\u{ffff}' => out.push('\u{fffd}'),
            c => out.push(c),
        }
    }
    out
}

fn heading(line: &str) -> Option<(usize, &str)> {
    let clean = line.trim_start();
    let n = clean.bytes().take_while(|b| *b == b'#').count();
    if (1..=6).contains(&n) && clean.as_bytes().get(n) == Some(&b' ') {
        Some((n, clean[n + 1..].trim_end()))
    } else { None }
}

fn paragraph(out: &mut String, value: &str, style: Option<&str>) {
    out.push_str("<w:p>");
    if let Some(style) = style { out.push_str(&format!("<w:pPr><w:pStyle w:val=\"{style}\"/></w:pPr>")); }
    out.push_str("<w:r><w:t xml:space=\"preserve\">");
    out.push_str(&xml(value));
    out.push_str("</w:t></w:r></w:p>");
}

pub fn word(title: &str, markdown: &str) -> Result<Vec<u8>, String> {
    let mut body = String::new();
    paragraph(&mut body, title, Some("Title"));
    for line in markdown.lines() {
        match heading(line) {
            Some((level, text)) => paragraph(&mut body, text, Some(match level { 1 => "Heading1", 2 => "Heading2", _ => "Heading3" })),
            None => paragraph(&mut body, line, None),
        }
    }
    let document = format!(r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{body}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/></w:sectPr></w:body></w:document>"#);
    let styles = r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="Microsoft YaHei"/><w:sz w:val="22"/></w:rPr></w:rPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style><w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:rPr><w:b/><w:sz w:val="34"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="30"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:sz w:val="26"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="2"/></w:pPr><w:rPr><w:b/><w:sz w:val="23"/></w:rPr></w:style></w:styles>"#;
    let content_types = r#"<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>"#;
    let rels = r#"<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>"#;
    let document_rels = r#"<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>"#;
    let mut archive = ZipWriter::new(Cursor::new(Vec::new()));
    let options = SimpleFileOptions::default().compression_method(CompressionMethod::Stored);
    for (name, value) in [("[Content_Types].xml",content_types),("_rels/.rels",rels),("word/document.xml",document.as_str()),("word/styles.xml",styles),("word/_rels/document.xml.rels",document_rels)] {
        archive.start_file(name,options).map_err(|e| format!("生成 Word 文件失败：{e}"))?;
        archive.write_all(value.as_bytes()).map_err(|e| format!("生成 Word 文件失败：{e}"))?;
    }
    archive.finish().map(|x| x.into_inner()).map_err(|e| format!("生成 Word 文件失败：{e}"))
}

#[derive(Default)]
struct Node { text: String, children: Vec<usize> }

/// FreeMind-compatible XML: section headings form branches; every nonblank
/// line remains a node, including source quotes and user notes.
pub fn mindmap(title: &str, markdown: &str) -> Vec<u8> {
    let mut nodes=vec![Node{text:title.to_owned(),children:Vec::new()}];
    let mut headings=vec![(0usize,0usize)];
    for line in markdown.lines().filter(|line| !line.trim().is_empty()) {
        let (level,text,is_heading)=match heading(line) {
            Some((depth,text))=>(depth,text,true),
            None=>(usize::MAX,line.trim(),false),
        };
        if is_heading { while headings.last().is_some_and(|(depth,_)| *depth>=level) {headings.pop();} }
        let parent=headings.last().map(|(_,index)|*index).unwrap_or(0);
        let index=nodes.len();nodes.push(Node{text:text.to_owned(),children:Vec::new()});nodes[parent].children.push(index);
        if is_heading {headings.push((level,index));}
    }
    // Iterative rendering avoids a recursive stack proportional to input size.
    let mut out=String::from("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<map version=\"1.0.1\">");
    let mut stack=vec![(0usize,false)];
    while let Some((i,close))=stack.pop() {
        if close {out.push_str("</node>");continue;}
        out.push_str("<node TEXT=\"");out.push_str(&xml(&nodes[i].text));out.push_str("\">");
        stack.push((i,true));for child in nodes[i].children.iter().rev(){stack.push((*child,false));}
    }
    out.push_str("</map>\n");out.into_bytes()
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn word_preserves_chinese_citations_and_xml_characters() {
        use std::io::Read;
        let bytes=word("会议 & <样品>","## 摘要\n- 小王确认 \"A&B\"\n\n## 分段原文依据\n> 会议原话：测试完成").unwrap();
        let mut zip=zip::ZipArchive::new(Cursor::new(bytes)).unwrap();let mut body=String::new();zip.by_name("word/document.xml").unwrap().read_to_string(&mut body).unwrap();
        for text in ["会议 &amp; &lt;样品&gt;","小王确认 &quot;A&amp;B&quot;","分段原文依据","会议原话：测试完成"] {assert!(body.contains(text),"missing {text}");}
    }
    #[test]
    fn mindmap_keeps_every_saved_line_and_groups_sections() {
        let xml=String::from_utf8(mindmap("报价 & 交付","## 摘要\n- 明天开会\n## 原文依据\n> 会议原话：A<B")).unwrap();
        for text in ["报价 &amp; 交付","摘要","- 明天开会","原文依据","会议原话：A&lt;B"] {assert!(xml.contains(text),"missing {text}");}
        assert!(xml.contains("TEXT=\"摘要\"><node TEXT=\"- 明天开会\""));
    }
}
