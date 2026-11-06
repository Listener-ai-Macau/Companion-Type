//! Local PDF generation for an already saved meeting. No remote content is loaded.
use std::{fs, path::{Path,PathBuf}, time::Duration};

fn escape(value:&str)->String {
    let mut out=String::with_capacity(value.len());
    for c in value.chars(){match c {'&'=>out.push_str("&amp;"),'<'=>out.push_str("&lt;"),'>'=>out.push_str("&gt;"),'"'=>out.push_str("&quot;"),'\''=>out.push_str("&#39;"),'\0'=>out.push('\u{fffd}'),_=>out.push(c)}}
    out
}


pub(super) fn html(title:&str, content:&str)->String {
    let mut body=String::new();
    for line in super::meeting_document_export::readable_lines(title,content) {
        let trimmed=line.trim_start();let depth=trimmed.bytes().take_while(|x|*x==b'#').count();
        if (1..=3).contains(&depth) && trimmed.as_bytes().get(depth)==Some(&b' ') {
            let tag=depth+1;body.push_str(&format!("<h{tag}>{}</h{tag}>",escape(&trimmed[depth+1..])));
        } else if trimmed.is_empty(){body.push_str("<div class=\"gap\"></div>");}
        else if let Some(quote)=trimmed.strip_prefix("> ") {
            body.push_str("<p class=\"quote\">");body.push_str(&escape(quote));body.push_str("</p>");
        } else if let Some(item)=trimmed.strip_prefix("- ") {
            body.push_str("<p class=\"list\">• ");body.push_str(&escape(item));body.push_str("</p>");
        } else {body.push_str("<p>");body.push_str(&escape(&line));body.push_str("</p>");}
    }
    format!("<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'\"><title>{}</title><style>@page{{size:A4;margin:20mm;@bottom-center{{content:counter(page) \" / \" counter(pages);font:10px sans-serif;color:#777}}}}body{{font:14px/1.6 'Microsoft YaHei','Noto Sans CJK SC',sans-serif;color:#151515;overflow-wrap:anywhere}}h1{{font-size:22px;margin:0 0 18px}}h2{{font-size:18px;margin:20px 0 8px}}h1,h2,h3,h4{{break-after:avoid;page-break-after:avoid}}h3,h4{{font-size:15px;margin:14px 0 5px}}p{{white-space:pre-wrap;margin:0 0 4px}}.gap{{height:6px;break-after:avoid}}p{{orphans:2;widows:2}}.quote{{color:#666}}.list{{padding-left:1em;text-indent:-1em}}</style></head><body><h1>{}</h1>{body}</body></html>",escape(title),escape(title))
}

#[cfg(windows)]
pub(super) fn browser()->Option<PathBuf>{
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

/// Windows can release the final profile handles just after its process job
/// becomes empty. Retry only those bounded filesystem-close races, and only
/// for a verified, UUID-named rendering directory directly under our temp root.
pub(super) fn remove_render_cache(path:&Path)->std::io::Result<()>{
    let resolved=match path.canonicalize(){Ok(value)=>value,Err(error) if error.kind()==std::io::ErrorKind::NotFound=>return Ok(()),Err(error)=>return Err(error)};
    let base=std::env::temp_dir().canonicalize()?;
    let name=resolved.file_name().and_then(|name|name.to_str()).unwrap_or_default();
    let own=name.strip_prefix("companion-pdf-").or_else(||name.strip_prefix("companion-mindmap-")).is_some_and(|suffix|uuid::Uuid::parse_str(suffix).is_ok());
    if !own||resolved.parent()!=Some(base.as_path()){return Err(std::io::Error::new(std::io::ErrorKind::PermissionDenied,"not an owned render cache"));}
    let start=std::time::Instant::now();
    loop{
        match fs::remove_dir_all(&resolved){
            Ok(())=>return Ok(()),
            Err(error) if error.kind()==std::io::ErrorKind::NotFound=>return Ok(()),
            Err(error) if cfg!(windows)&&matches!(error.raw_os_error(),Some(5|32|33|145))&&start.elapsed()<Duration::from_secs(2)=>std::thread::sleep(Duration::from_millis(20)),
            Err(error)=>return Err(error),
        }
    }
}

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
        super::external_command::run_until_ready(&exe.to_string_lossy(),&args,super::external_command::Limits::for_timeout(Duration::from_secs(180)),None,
            &||super::external_command::closed_output_matches(&output,b"%PDF-",b"%%EOF"))
            .map_err(|_|"PDF 生成未完成；已保存的会议内容不受影响，请重试或先导出 Word。")?;
        let bytes=fs::read(&output).map_err(|_|"PDF 生成未完成，请重试。")?;
        if !bytes.starts_with(b"%PDF-") || bytes.len()<100 {return Err("PDF 生成未完成，请重试。".into());}
        remove_render_cache(&root).map_err(|_|"PDF 已生成，但临时文件未能清理；请检查本机临时目录。")?;
        drop(cleanup);Ok(bytes)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[cfg(windows)]
    #[test]fn render_cache_waits_for_transient_writer_close_and_refuses_other_roots(){
        use std::os::windows::fs::OpenOptionsExt;
        let root=std::env::temp_dir().join(format!("companion-pdf-{}",uuid::Uuid::new_v4()));fs::create_dir(&root).unwrap();let file=root.join("controlled.txt");fs::write(&file,b"public synthetic fixture").unwrap();
        let (send,receive)=std::sync::mpsc::channel();
        let writer=std::thread::spawn(move||{let _handle=fs::OpenOptions::new().read(true).share_mode(0).open(file).unwrap();send.send(()).unwrap();std::thread::sleep(Duration::from_millis(100));});
        receive.recv().unwrap();remove_render_cache(&root).unwrap();writer.join().unwrap();assert!(!root.exists());
        let other=std::env::temp_dir().join(format!("not-render-cache-{}",uuid::Uuid::new_v4()));fs::create_dir(&other).unwrap();let marker=other.join("keep.txt");fs::write(&marker,b"keep").unwrap();
        assert!(remove_render_cache(&other).is_err());assert!(marker.exists());fs::remove_file(marker).unwrap();fs::remove_dir(other).unwrap();
    }
    #[test] fn page_escapes_meeting_content_and_has_no_external_loads(){
        let s=html("会议 <样品>","## 纪要\n- 小王 <script>报价</script> & 原话\n原文依据：蓝色文件夹");
        assert!(s.contains("会议 &lt;样品&gt;") && s.contains("&lt;script&gt;报价&lt;/script&gt; &amp; 原话"));
        assert!(s.contains("default-src 'none'") && !s.contains("<script>"));
    }
    #[test] fn generated_header_is_readable_without_changing_unrelated_content(){
        let saved="## 会议概览\n- 讨论报价\n\n# 会议\n\nGenerated: 2026-11-01T12:07:35.721Z\nDuration: 7817647 ms\nSource: importedAudio\nMinutes engine: llm_deepseek (final)\n\n## Summary\n- 讨论报价\n\n## Decisions\n- None captured\n\n## Action Items\n- 小王发报价 (owner: 小王, due: 周五)\n\n## Questions\n- None captured\n\n## Keywords\n报价\n\n## 原文依据\n- 逐字原话";
        let rendered=super::super::meeting_document_export::readable_lines("会议",saved).join("\n");
        for text in ["## 会议概览","生成时间：","时长：02:10:17","来源：导入的音频","整理方式：AI 整理","## 会议摘要","## 待办事项","小王发报价 (owner: 小王, due: 周五)","## 原文依据","逐字原话"] {assert!(rendered.contains(text),"missing {text}");}
        assert!(!rendered.contains("llm_deepseek") && !rendered.contains("7817647 ms") && !rendered.contains("None captured"));
        let authored="# 自己的笔记\nGenerated: 我的原话\n## Summary\n不要改这段";
        assert_eq!(super::super::meeting_document_export::readable_lines("会议",authored).join("\n"),authored);
        assert!(saved.contains("llm_deepseek"),"the persisted source must not be modified");
    }
}
