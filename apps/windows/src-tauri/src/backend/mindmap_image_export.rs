//! A complete local PNG of the same nodes as the editable FreeMind export.
//! Text is escaped, no remote resource/script is loaded, and oversize graphs
//! are rejected before a browser starts instead of being cropped silently.
use std::{fs,path::PathBuf,time::Duration};
use super::meeting_document_export::{mindmap_nodes,xml};
use super::export_text_layout::{wrap,root_lines};

struct Layout {x:u32,y:u32,width:u32,height:u32,lines:Vec<String>}
pub(super) struct Image {pub html:String,pub width:u32,pub height:u32}
pub(super) fn page(title:&str,content:&str)->Result<Image,String>{
    if title.chars().count()+content.chars().count()>12_000{return Err("所选内容过长，PNG请只选择一份材料，或导出可编辑思维导图。".into());}
    let nodes=mindmap_nodes(title,content);
    if nodes.len()>180{return Err("导图超过180个节点，请减少所选内容或导出可编辑思维导图。".into());}
    let mut layout:Vec<_>=nodes.iter().enumerate().map(|(i,node)|{
        // Nodes are already display text. Do not strip a second user-authored
        // quote marker, or reinterpret the meeting title as Markdown.
        let lines=if i==0{root_lines(&node.text,44)}else{wrap(&node.text,68)};
        Layout{x:0,y:0,width:if i==0{320}else{360},height:lines.len() as u32*28+32,lines}
    }).collect();
    let mut heights=vec![0u32;nodes.len()];
    for i in (0..nodes.len()).rev(){
        let children=&nodes[i].children;
        let total=children.iter().map(|c|heights[*c]).sum::<u32>()+24*children.len().saturating_sub(1) as u32;
        heights[i]=layout[i].height.max(total);
    }
    let mut queue=std::collections::VecDeque::from([(0usize,0u32,64u32)]);
    let mut width=0;
    while let Some((i,depth,top))=queue.pop_front(){
        let item=&mut layout[i];item.x=64+depth*432;item.y=top+(heights[i]-item.height)/2;
        width=width.max(item.x+item.width+64);
        let children=&nodes[i].children;
        let block=children.iter().map(|c|heights[*c]).sum::<u32>()+24*children.len().saturating_sub(1) as u32;
        let mut next=top+(heights[i]-block)/2;
        for child in children {queue.push_back((*child,depth+1,next));next+=heights[*child]+24;}
    }
    let height=heights[0]+128;
    if width>4096||height>12000||u64::from(width)*u64::from(height)>24_000_000{
        return Err("导图尺寸过大，PNG请减少所选内容或改用可编辑思维导图；未裁掉任何节点。".into());
    }
    let mut drawing=String::new();
    for (i,node) in nodes.iter().enumerate(){
        let parent=&layout[i];
        for c in &node.children {
            let child=&layout[*c];let x=parent.x+parent.width;let y=parent.y+parent.height/2;
            let end=child.y+child.height/2;let mid=(x+child.x)/2;
            drawing.push_str(&format!(r##"<path d="M{x},{y} C{mid},{y} {mid},{end} {},{end}" fill="none" stroke="#B6C5D6" stroke-width="2"/>"##,child.x));
        }
    }
    for (i,item) in layout.iter().enumerate(){
        let (fill,border,color,font)=if i==0{("#172B40","#172B40","#FFFFFF",24)}else if nodes[i].children.is_empty(){("#FFFFFF","#D8E1EB","#27364A",18)}else{("#EAF0F7","#BBCDE0","#172B40",18)};
        drawing.push_str(&format!(r##"<g><rect x="{}" y="{}" width="{}" height="{}" rx="12" fill="{fill}" stroke="{border}"/><text fill="{color}" font-size="{font}" text-anchor="{}" font-family="Microsoft YaHei,Arial,sans-serif">"##,item.x,item.y,item.width,item.height,if i==0{"middle"}else{"start"}));
        for (line,text) in item.lines.iter().enumerate(){
            drawing.push_str(&format!(r#"<tspan x="{}" y="{}" xml:space="preserve">{}</tspan>"#,if i==0{item.x+item.width/2}else{item.x+18},item.y+35+line as u32*28,xml(text)));
        }
        drawing.push_str("</text></g>");
    }
    let html=format!(r##"<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'"><title>{}</title><style>html,body{{margin:0;padding:0;width:{width}px;height:{height}px;background:#F5F7FA;overflow:hidden}}svg{{display:block}}</style></head><body><svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><rect width="100%" height="100%" fill="#F5F7FA"/>{drawing}</svg></body></html>"##,xml(title));
    Ok(Image{html,width,height})
}
struct Temporary(PathBuf);
impl Drop for Temporary {fn drop(&mut self){let _=fs::remove_dir_all(&self.0);}}
pub(crate) fn render(title:&str,content:&str)->Result<Vec<u8>,String>{
    let image=page(title,content)?;
    #[cfg(not(windows))] {let _=image;return Err("本机暂不支持PNG导图，请导出可编辑思维导图。".into());}
    #[cfg(windows)] {
        let exe=super::pdf_export::browser().ok_or("未找到Microsoft Edge或Chrome，PNG暂不可用；可先导出可编辑思维导图。")?;
        let root=std::env::temp_dir().join(format!("companion-mindmap-{}",uuid::Uuid::new_v4()));
        fs::create_dir(&root).map_err(|_|"无法创建导图临时文件。")?;
        let cleanup=Temporary(root.clone());let source=root.join("mindmap.html");let output=root.join("mindmap.png");
        fs::write(&source,&image.html).map_err(|_|"无法准备导图内容。")?;
        let url=tauri::Url::from_file_path(&source).map_err(|_|"无法准备导图路径。")?;
        let args=vec!["--headless=new".into(),"--disable-gpu".into(),"--disable-extensions".into(),"--disable-background-networking".into(),"--disable-sync".into(),"--no-first-run".into(),"--no-default-browser-check".into(),"--hide-scrollbars".into(),"--force-device-scale-factor=1".into(),"--virtual-time-budget=1000".into(),format!("--user-data-dir={}",root.join("profile").display()),format!("--window-size={},{}",image.width,image.height),format!("--screenshot={}",output.display()),url.to_string()];
        super::external_command::run_until_ready(&exe.to_string_lossy(),&args,super::external_command::Limits::for_timeout(Duration::from_secs(180)),None,
            &||super::external_command::closed_output_matches(&output,b"\x89PNG\r\n\x1a\n",b"\x00\x00\x00\x00IEND\xae\x42\x60\x82"))
            .map_err(|_|"PNG导图生成未完成，请重试或先导出可编辑思维导图。")?;
        let bytes=fs::read(&output).map_err(|_|"PNG导图生成未完成。")?;
        if bytes.len()<100||!bytes.starts_with(b"\x89PNG\r\n\x1a\n")||bytes.get(16..20)!=Some(image.width.to_be_bytes().as_slice())||bytes.get(20..24)!=Some(image.height.to_be_bytes().as_slice()){
            return Err("PNG尺寸与完整导图不符，请改用可编辑思维导图；未交付裁切图片。".into());
        }
        fs::remove_dir_all(&root).map_err(|_|"PNG已生成，但临时文件未能清理。")?;drop(cleanup);Ok(bytes)
    }
}

#[cfg(test)]
mod tests{
    use super::*;
    #[test]fn content052_mindmap_keeps_all_nodes_and_escapes_saved_content(){
        let image=page("采购 & <样品>","## 条件\n- 尚未批准20%的追加费用\n## 原文依据\n> A<B <script>alert(1)</script>").unwrap();
        for text in ["尚未批准20%的追加费用","原文依据","&lt;script&gt;","A&lt;B"]{assert!(image.html.contains(text),"missing {text}");}
        assert!(!image.html.contains("<script>"));assert!(image.width>600&&image.height>200);
        assert!(page("会议",&"- 内容\n".repeat(181)).is_err());
        assert!(page("会议",&"长段原文".repeat(4000)).is_err());
    }
}
