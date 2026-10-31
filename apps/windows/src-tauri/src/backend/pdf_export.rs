//! Local PDF generation for an already saved meeting. No remote content is loaded.
use std::{fs, path::PathBuf, time::Duration};

fn escape(value:&str)->String {
    let mut out=String::with_capacity(value.len());
    for c in value.chars(){match c {'&'=>out.push_str("&amp;"),'<'=>out.push_str("&lt;"),'>'=>out.push_str("&gt;"),'"'=>out.push_str("&quot;"),'\''=>out.push_str("&#39;"),'\0'=>out.push('\u{fffd}'),_=>out.push(c)}}
    out
}

pub(super) fn html(title:&str, content:&str)->String {
    let mut body=String::new();
    for line in content.lines(){
        let trimmed=line.trim_start();let depth=trimmed.bytes().take_while(|x|*x==b'#').count();
        if (1..=3).contains(&depth) && trimmed.as_bytes().get(depth)==Some(&b' ') {
            let tag=depth+1;body.push_str(&format!("<h{tag}>{}</h{tag}>",escape(&trimmed[depth+1..])));
        } else if trimmed.is_empty(){body.push_str("<div class=\"gap\"></div>");}
        else {body.push_str("<p>");body.push_str(&escape(line));body.push_str("</p>");}
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
}
