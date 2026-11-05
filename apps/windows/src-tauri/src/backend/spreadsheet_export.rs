//! Ordinary XLSX export of selected saved content, not AI template filling.
use std::io::{Cursor,Write};
fn xml(text:&str)->String {
    text.chars().map(|c|match c {'&'=>"&amp;".into(),'<'=>"&lt;".into(),'>'=>"&gt;".into(),'"'=>"&quot;".into(),'\''=>"&apos;".into(),c if (c<'\u{20}'&&c!='\n'&&c!='\r'&&c!='\t')||c=='\u{fffe}'||c=='\u{ffff}'=>"�".into(),c=>c.to_string()}).collect()
}
fn chunks(text:&str)->Vec<String>{
    let mut out=Vec::new();let mut current=String::new();let mut units=0;
    for c in text.chars(){if units+c.len_utf16()>30_000{out.push(std::mem::take(&mut current));units=0;}units+=c.len_utf16();current.push(c);}
    out.push(current);out
}
pub fn render(title:&str,content:&str)->Result<Vec<u8>,String>{
    let mut sheet=String::from("<?xml version=\"1.0\" encoding=\"UTF-8\"?><worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"><sheetViews><sheetView workbookViewId=\"0\"><pane ySplit=\"1\" topLeftCell=\"A2\" activePane=\"bottomLeft\" state=\"frozen\"/></sheetView></sheetViews><cols><col min=\"1\" max=\"1\" width=\"28\" customWidth=\"1\"/><col min=\"2\" max=\"2\" width=\"100\" customWidth=\"1\"/></cols><sheetData>");
    let mut row=0usize;
    let mut add=|section:&str,text:&str|->Result<(),String>{
        for chunk in chunks(text){row+=1;if row>1_048_576{return Err("所选内容超过Excel行数上限，请分开导出。".into());}
            sheet.push_str(&format!("<row r=\"{row}\"><c r=\"A{row}\" t=\"inlineStr\" s=\"1\"><is><t xml:space=\"preserve\">{}</t></is></c><c r=\"B{row}\" t=\"inlineStr\" s=\"1\"><is><t xml:space=\"preserve\">{}</t></is></c></row>",xml(section),xml(&chunk)));
        }Ok(())
    };
    add("章节","内容")?;add("会议",title)?;let mut section="正文";
    for line in content.lines(){if let Some(head)=line.strip_prefix("## "){section=head;}add(section,line)?;}
    drop(add);sheet.push_str(&format!("</sheetData><autoFilter ref=\"A1:B{row}\"/></worksheet>"));
    let files=[("[Content_Types].xml",r#"<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>"#),
        ("_rels/.rels",r#"<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>"#),
        ("xl/workbook.xml",r#"<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="会议内容" sheetId="1" r:id="rId1"/></sheets></workbook>"#),
        ("xl/_rels/workbook.xml.rels",r#"<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>"#),
        ("xl/styles.xml",r#"<?xml version="1.0" encoding="UTF-8"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="1"><font><sz val="11"/><name val="Microsoft YaHei"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="2"><xf/><xf applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>"#),
        ("xl/worksheets/sheet1.xml",sheet.as_str())];
    let mut zip=zip::ZipWriter::new(Cursor::new(Vec::new()));
    for (name,value) in files {zip.start_file(name,zip::write::SimpleFileOptions::default().compression_method(zip::CompressionMethod::Stored)).map_err(|e|e.to_string())?;zip.write_all(value.as_bytes()).map_err(|e|e.to_string())?;}
    zip.finish().map(|c|c.into_inner()).map_err(|e|e.to_string())
}
#[cfg(test)] mod tests {
    use super::*;
    #[test] fn content051_xlsx_preserves_unicode_long_cells_and_formula_looking_text_as_strings(){
        let long="😀中".repeat(12_000);let content=format!("## 原文\n=HYPERLINK(\"not-an-executable-formula\")\n{long}\n末尾：尚未批准采购");
        let bytes=render("公开测试",&content).unwrap();let mut zip=zip::ZipArchive::new(Cursor::new(bytes)).unwrap();let mut xml=String::new();use std::io::Read;zip.by_name("xl/worksheets/sheet1.xml").unwrap().read_to_string(&mut xml).unwrap();
        assert!(!xml.contains("<f>"));assert!(xml.contains("=HYPERLINK"));assert!(xml.contains("末尾：尚未批准采购"));assert_eq!(xml.matches('😀').count(),12_000);
    }
}
