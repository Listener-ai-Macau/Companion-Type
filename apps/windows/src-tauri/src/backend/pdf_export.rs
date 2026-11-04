//! Local PDF generation for an already saved meeting. No remote content is loaded.
use std::{fs, path::PathBuf, time::Duration};

fn escape(value:&str)->String {
    let mut out=String::with_capacity(value.len());
    for c in value.chars(){match c {'&'=>out.push_str("&amp;"),'<'=>out.push_str("&lt;"),'>'=>out.push_str("&gt;"),'"'=>out.push_str("&quot;"),'\''=>out.push_str("&#39;"),'\0'=>out.push('\u{fffd}'),_=>out.push(c)}}
    out
}

// Older saved minutes contain an English machine-generated header. Translate
// only the complete, recognizable template in the exported presentation;
// never rewrite the saved markdown or headings outside that template.
fn readable_lines(title:&str,content:&str)->Vec<String> {
    let lines=content.lines().collect::<Vec<_>>();
    let marker=format!("# {title}");
    let Some(start)=(0..lines.len().saturating_sub(7)).find(|&i|
        lines[i]==marker && lines[i+1].is_empty() && lines[i+2].starts_with("Generated: ")
        && lines[i+3].starts_with("Duration: ") && lines[i+4].starts_with("Source: ")
        && lines[i+5].starts_with("Minutes engine: ") && lines[i+6].is_empty()
        && lines[i+7]=="## Summary") else {return lines.into_iter().map(str::to_owned).collect()};
    let headings=["## Summary","## Decisions","## Action Items","## Questions","## Keywords"];
    let labels=["## 会议摘要","## 决定","## 待办事项","## 待确认问题","## 关键词"];
    let mut indices=vec![start+7];
    for heading in headings.iter().skip(1) {
        let Some(offset)=lines[indices.last().unwrap()+1..].iter().position(|line|line==heading) else {
            return lines.into_iter().map(str::to_owned).collect();
        };
        indices.push(indices.last().unwrap()+1+offset);
    }
    let generated=lines[start+2].trim_start_matches("Generated: ");
    let generated=chrono::DateTime::parse_from_rfc3339(generated)
        .map(|date|date.with_timezone(&chrono::Local).format("%Y-%m-%d %H:%M").to_string())
        .unwrap_or_else(|_|generated.to_owned());
    let duration=lines[start+3].trim_start_matches("Duration: ");
    let duration=duration.strip_suffix(" ms").and_then(|v|v.parse::<u64>().ok()).map(|ms|{
        let seconds=ms/1000;format!("{:02}:{:02}:{:02}",seconds/3600,(seconds/60)%60,seconds%60)
    }).unwrap_or_else(||duration.to_owned());
    let source=lines[start+4].trim_start_matches("Source: ");
    let source=match source {"importedAudio"=>"导入的音频","boardDevice"=>"录音卡", "hostMicrophone"=>"电脑麦克风", "hostMeeting"=>"电脑会议", "importedTranscript"=>"导入的文字", _=>source};
    let engine=lines[start+5].trim_start_matches("Minutes engine: ");
    let engine=if engine.starts_with("llm_") {"AI 整理"} else if engine.starts_with("rules_") {"本地整理"} else {engine};
    let mut out=Vec::new();let mut i=0;
    while i<lines.len() {
        if i==start {
            out.extend([format!("生成时间：{generated}"),format!("时长：{duration}"),format!("来源：{source}"),format!("整理方式：{engine}"),String::new()]);
            i+=7;continue;
        }
        if let Some(pos)=indices.iter().position(|index|*index==i) {out.push(labels[pos].into());}
        else if indices.iter().any(|index|*index+1==i) && matches!(lines[i],"- None captured"|"None captured") {
            out.push(if lines[i].starts_with('-') {"- 暂无"} else {"暂无"}.into());
        } else {out.push(lines[i].to_owned());}
        i+=1;
    }
    out
}

pub(super) fn html(title:&str, content:&str)->String {
    let mut body=String::new();
    for line in readable_lines(title,content) {
        let trimmed=line.trim_start();let depth=trimmed.bytes().take_while(|x|*x==b'#').count();
        if (1..=3).contains(&depth) && trimmed.as_bytes().get(depth)==Some(&b' ') {
            let tag=depth+1;body.push_str(&format!("<h{tag}>{}</h{tag}>",escape(&trimmed[depth+1..])));
        } else if trimmed.is_empty(){body.push_str("<div class=\"gap\"></div>");}
        else {body.push_str("<p>");body.push_str(&escape(&line));body.push_str("</p>");}
    }
    format!("<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'\"><title>{}</title><style>@page{{size:A4;margin:20mm}}body{{font:14px/1.6 'Microsoft YaHei','Noto Sans CJK SC',sans-serif;color:#151515;overflow-wrap:anywhere}}h1{{font-size:22px;margin:0 0 18px}}h2{{font-size:18px;margin:20px 0 8px}}h3,h4{{font-size:15px;margin:14px 0 5px}}p{{white-space:pre-wrap;margin:0 0 4px}}.gap{{height:6px}}</style></head><body><h1>{}</h1>{body}</body></html>",escape(title),escape(title))
}

#[cfg(windows)]
fn browser()->Option<PathBuf>{
    let mut roots=Vec::new();
    for key in ["PROGRAMFILES(X86)","PROGRAMFILES","LOCALAPPDATA"] {if let Some(value)=std::env::var_os(key){roots.push(PathBuf::from(value));}}
    roots.push(PathBuf::from(r"C:\Program Files (x86)"));roots.push(PathBuf::from(r"C:\Program Files"));
    for relative in [r"Microsoft\Edge\Application\msedge.exe",r"Google\Chrome\Application\chrome.exe"] {
        for root in &roots {let candidate=root.join(relative);if candidate.is_file(){return Some(candidate);}}
    }
    None
}

struct Temporary(PathBuf);
impl Drop for Temporary {fn drop(&mut self){let _=fs::remove_dir_all(&self.0);}}

pub(crate) fn render(title:&str,content:&str)->Result<Vec<u8>,String>{
    #[cfg(not(windows))] {let _=(title,content);return Err("本机暂不支持直接生成 PDF。".into());}
    #[cfg(windows)] {
        let exe=browser().ok_or("未找到 Microsoft Edge 或 Chrome，暂时无法生成 PDF；可以先导出 Word。")?;
        let root=std::env::temp_dir().join(format!("companion-pdf-{}",uuid::Uuid::new_v4()));
        fs::create_dir(&root).map_err(|_|"无法创建临时文件，未生成 PDF。")?;
        let cleanup=Temporary(root.clone());let source=root.join("document.html");let output=root.join("document.pdf");let profile=root.join("profile");
        fs::write(&source,html(title,content)).map_err(|_|"无法准备 PDF 内容。")?;
        let url=tauri::Url::from_file_path(&source).map_err(|_|"无法准备 PDF 路径。")?;
        let args=vec!["--headless=new".into(),"--disable-gpu".into(),"--disable-extensions".into(),"--disable-background-networking".into(),"--disable-sync".into(),"--no-first-run".into(),"--no-default-browser-check".into(),"--no-pdf-header-footer".into(),format!("--user-data-dir={}",profile.display()),format!("--print-to-pdf={}",output.display()),url.to_string()];
        super::external_command::run(&exe.to_string_lossy(),&args,super::external_command::Limits::for_timeout(Duration::from_secs(180)),None)
            .map_err(|_|"PDF 生成未完成；已保存的会议内容不受影响，请重试或先导出 Word。")?;
        let bytes=fs::read(&output).map_err(|_|"PDF 生成未完成，请重试。")?;
        if !bytes.starts_with(b"%PDF-") || bytes.len()<100 {return Err("PDF 生成未完成，请重试。".into());}
        fs::remove_dir_all(&root).map_err(|_|"PDF 已生成，但临时文件未能清理；请检查本机临时目录。")?;
        drop(cleanup);Ok(bytes)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn page_escapes_meeting_content_and_has_no_external_loads(){
        let s=html("会议 <样品>","## 纪要\n- 小王 <script>报价</script> & 原话\n原文依据：蓝色文件夹");
        assert!(s.contains("会议 &lt;样品&gt;") && s.contains("&lt;script&gt;报价&lt;/script&gt; &amp; 原话"));
        assert!(s.contains("default-src 'none'") && !s.contains("<script>"));
    }
    #[test] fn generated_header_is_readable_without_changing_unrelated_content(){
        let saved="## 会议概览\n- 讨论报价\n\n# 会议\n\nGenerated: 2026-11-01T12:07:35.721Z\nDuration: 7817647 ms\nSource: importedAudio\nMinutes engine: llm_deepseek (final)\n\n## Summary\n- 讨论报价\n\n## Decisions\n- None captured\n\n## Action Items\n- 小王发报价 (owner: 小王, due: 周五)\n\n## Questions\n- None captured\n\n## Keywords\n报价\n\n## 原文依据\n- 逐字原话";
        let rendered=readable_lines("会议",saved).join("\n");
        for text in ["## 会议概览","生成时间：","时长：02:10:17","来源：导入的音频","整理方式：AI 整理","## 会议摘要","## 待办事项","小王发报价 (owner: 小王, due: 周五)","## 原文依据","逐字原话"] {assert!(rendered.contains(text),"missing {text}");}
        assert!(!rendered.contains("llm_deepseek") && !rendered.contains("7817647 ms") && !rendered.contains("None captured"));
        let authored="# 自己的笔记\nGenerated: 我的原话\n## Summary\n不要改这段";
        assert_eq!(readable_lines("会议",authored).join("\n"),authored);
        assert!(saved.contains("llm_deepseek"),"the persisted source must not be modified");
    }
}
