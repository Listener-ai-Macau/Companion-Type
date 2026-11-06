//! Editable, deterministic PresentationML from the exact saved export text.
//! Pagination changes layout only. No service call or summary is generated.
use std::io::{Cursor,Write};
use zip::{ZipWriter,write::SimpleFileOptions,CompressionMethod};
use super::meeting_document_export::{xml,heading,readable_lines};
use super::export_text_layout::{wrap,visual_line};

const MAX_SLIDES:usize=250;
const BODY_LINES:usize=9;
#[derive(Clone,Debug)]
struct Slide {title:String,body:Vec<String>}

fn heading_and_overflow(title:&str)->(String,Vec<String>){
    if title.chars().count()<=48 {(title.to_owned(),Vec::new())}
    else {(format!("{}…",title.chars().take(22).collect::<String>()),wrap(title,144))}
}
fn pages(title:&str,content:&str)->Result<Vec<Slide>,String>{
    if content.chars().count()>150_000{return Err("所选内容过长，PPTX请分批导出或改用Word。".into());}
    let (cover,overflow)=heading_and_overflow(title);
    let mut slides=vec![Slide{title:cover,body:Vec::new()}];
    for chunk in overflow.chunks(BODY_LINES){slides.push(Slide{title:"会议名称（续）".into(),body:chunk.to_vec()});}
    let mut current=Slide{title:"会议材料".into(),body:Vec::new()};
    let mut explicit_heading=false;
    for line in readable_lines(title,content){
        let line=visual_line(&line);
        if let Some((_,text))=heading(line){
            if !current.body.is_empty()||explicit_heading {slides.push(current);}
            let (name,body)=heading_and_overflow(text);
            current=Slide{title:name,body:Vec::new()};explicit_heading=true;
            for value in body {
                if current.body.len()==BODY_LINES {slides.push(current.clone());current.body.clear();}
                current.body.push(value);
            }
        }else{
            for value in wrap(line,144){
                if current.body.len()==BODY_LINES {slides.push(current.clone());current.body.clear();}
                current.body.push(value);
            }
        }
        if slides.len()>MAX_SLIDES{return Err("所选内容超过250页，请减少内容或分批导出PPTX。".into());}
    }
    if !current.body.is_empty()||explicit_heading {slides.push(current);}
    if slides.len()>MAX_SLIDES{return Err("所选内容超过250页，请减少内容或分批导出PPTX。".into());}
    Ok(slides)
}

fn group()->&'static str {r#"<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>"#}
fn textbox(id:u32,name:&str,rect:(u32,u32,u32,u32),lines:&[String],size:u32,bold:bool,color:&str)->String{
    let (x,y,cx,cy)=rect;
    let empty=[String::new()];let lines=if lines.is_empty(){&empty[..]}else{lines};
    let paragraphs=lines.iter().map(|text|format!(r#"<a:p><a:pPr><a:lnSpc><a:spcPts val="{}"/></a:lnSpc><a:spcBef><a:spcPts val="0"/></a:spcBef><a:spcAft><a:spcPts val="0"/></a:spcAft></a:pPr><a:r><a:rPr lang="zh-CN" sz="{size}" b="{}"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill><a:latin typeface="Microsoft YaHei"/><a:ea typeface="Microsoft YaHei"/><a:cs typeface="Arial"/></a:rPr><a:t xml:space="preserve">{}</a:t></a:r><a:endParaRPr lang="zh-CN" sz="{size}"/></a:p>"#,if size>=4000{5200}else if size>=3000{3800}else if size>=1800{2800}else{1400},u8::from(bold),xml(text))).collect::<String>();
    format!(r#"<p:sp><p:nvSpPr><p:cNvPr id="{id}" name="{}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr><p:txBody><a:bodyPr wrap="none" lIns="0" tIns="0" rIns="0" bIns="0" anchor="t"><a:noAutofit/></a:bodyPr><a:lstStyle/>{paragraphs}</p:txBody></p:sp>"#,xml(name))
}
fn slide_xml(slide:&Slide,index:usize,total:usize)->String{
    let cover=index==0;
    let title_lines=wrap(&slide.title,if cover{72}else{96});
    let header=textbox(2,"标题",(680000,if cover{1800000}else{500000},10800000,if cover{2200000}else{1500000}),&title_lines,if cover{4200}else{3200},true,"172B40");
    let body=textbox(3,"保存的正文",(710000,1750000,10700000,4200000),&slide.body,2000,false,"27364A");
    let footer=textbox(4,"页码",(680000,6350000,10800000,220000),&[format!("{} / {}",index+1,total)],1000,false,"667589");
    format!(r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="F8FAFC"/></a:solidFill><a:effectLst/></p:bgPr></p:bg><p:spTree>{}{header}{body}{footer}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>"#,group())
}
const THEME:&str=r#"<?xml version="1.0" encoding="UTF-8"?><a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Companion"><a:themeElements><a:clrScheme name="Companion"><a:dk1><a:srgbClr val="172B40"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="27364A"/></a:dk2><a:lt2><a:srgbClr val="F8FAFC"/></a:lt2><a:accent1><a:srgbClr val="386BA0"/></a:accent1><a:accent2><a:srgbClr val="687B93"/></a:accent2><a:accent3><a:srgbClr val="92765B"/></a:accent3><a:accent4><a:srgbClr val="78729F"/></a:accent4><a:accent5><a:srgbClr val="5A828C"/></a:accent5><a:accent6><a:srgbClr val="9B777A"/></a:accent6><a:hlink><a:srgbClr val="386BA0"/></a:hlink><a:folHlink><a:srgbClr val="78729F"/></a:folHlink></a:clrScheme><a:fontScheme name="Companion"><a:majorFont><a:latin typeface="Microsoft YaHei"/><a:ea typeface="Microsoft YaHei"/><a:cs typeface="Arial"/></a:majorFont><a:minorFont><a:latin typeface="Microsoft YaHei"/><a:ea typeface="Microsoft YaHei"/><a:cs typeface="Arial"/></a:minorFont></a:fontScheme><a:fmtScheme name="Companion"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="12700"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/></a:ln><a:ln w="25400"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/></a:ln><a:ln w="38100"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme></a:themeElements><a:objectDefaults/><a:extraClrSchemeLst/></a:theme>"#;

pub fn render(title:&str,content:&str)->Result<Vec<u8>,String>{
    let slides=pages(title,content)?;
    let mut parts:Vec<(String,String)>=Vec::new();
    let slide_types=(1..=slides.len()).map(|n|format!(r#"<Override PartName="/ppt/slides/slide{n}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>"#)).collect::<String>();
    parts.push(("[Content_Types].xml".into(),format!(r#"<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/><Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/><Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/><Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>{slide_types}</Types>"#)));
    parts.push(("_rels/.rels".into(),r#"<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/></Relationships>"#.into()));
    let slide_ids=(1..=slides.len()).map(|n|format!(r#"<p:sldId id="{}" r:id="rId{n}"/>"#,255+n)).collect::<String>();
    parts.push(("ppt/presentation.xml".into(),format!(r#"<?xml version="1.0" encoding="UTF-8"?><p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rIdMaster"/></p:sldMasterIdLst><p:sldIdLst>{slide_ids}</p:sldIdLst><p:sldSz cx="12192000" cy="6858000" type="screen16x9"/><p:notesSz cx="6858000" cy="9144000"/><p:defaultTextStyle/></p:presentation>"#)));
    let rels=(1..=slides.len()).map(|n|format!(r#"<Relationship Id="rId{n}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{n}.xml"/>"#)).collect::<String>();
    parts.push(("ppt/_rels/presentation.xml.rels".into(),format!(r#"<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rIdMaster" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>{rels}</Relationships>"#)));
    parts.push(("ppt/slideMasters/slideMaster1.xml".into(),format!(r#"<?xml version="1.0" encoding="UTF-8"?><p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree>{}</p:spTree></p:cSld><p:clrMap accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" bg1="lt1" bg2="lt2" folHlink="folHlink" hlink="hlink" tx1="dk1" tx2="dk2"/><p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rIdLayout"/></p:sldLayoutIdLst><p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles></p:sldMaster>"#,group())));
    parts.push(("ppt/slideMasters/_rels/slideMaster1.xml.rels".into(),r#"<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rIdLayout" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/><Relationship Id="rIdTheme" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/></Relationships>"#.into()));
    parts.push(("ppt/slideLayouts/slideLayout1.xml".into(),format!(r#"<?xml version="1.0" encoding="UTF-8"?><p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1"><p:cSld name="Blank"><p:spTree>{}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>"#,group())));
    parts.push(("ppt/slideLayouts/_rels/slideLayout1.xml.rels".into(),r#"<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rIdMaster" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/></Relationships>"#.into()));
    parts.push(("ppt/theme/theme1.xml".into(),THEME.into()));
    for (i,slide) in slides.iter().enumerate(){
        let n=i+1;parts.push((format!("ppt/slides/slide{n}.xml"),slide_xml(slide,i,slides.len())));
        parts.push((format!("ppt/slides/_rels/slide{n}.xml.rels"),r#"<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rIdLayout" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/></Relationships>"#.into()));
    }
    let mut zip=ZipWriter::new(Cursor::new(Vec::new()));
    for (name,value) in parts {
        zip.start_file(name,SimpleFileOptions::default().compression_method(CompressionMethod::Stored)).map_err(|e|format!("PPTX生成失败：{e}"))?;
        zip.write_all(value.as_bytes()).map_err(|e|format!("PPTX生成失败：{e}"))?;
    }
    zip.finish().map(|cursor|cursor.into_inner()).map_err(|e|format!("PPTX生成失败：{e}"))
}

#[cfg(test)]
mod tests{
    use super::*;
    #[test]fn content052_presentation_paginates_without_omitting_saved_text_or_citations(){
        let body=format!("## 交付与条件\n{}\n## 原文依据\n尚未批准20%的追加费用 <A&B>","请先核对报价并确认负责人。".repeat(80));
        let slides=pages("公开复盘",&body).unwrap();
        assert!(slides.len()>3);assert!(slides.iter().all(|s|s.body.len()<=BODY_LINES));
        let flattened=slides.iter().flat_map(|s|s.body.iter()).cloned().collect::<String>();
        assert!(flattened.contains(&"请先核对报价并确认负责人。".repeat(80)));
        assert!(flattened.contains("尚未批准20%的追加费用 <A&B>"));
        assert_eq!(render("公开复盘",&body).unwrap(),render("公开复盘",&body).unwrap());
    }
}
