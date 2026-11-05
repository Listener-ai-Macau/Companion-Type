//! Export a saved mobile meeting using the same document writer as Windows.
use jni::{objects::{JClass, JString}, sys::{jboolean, jbyteArray}, JNIEnv};

fn saved_content(saved_json:&str, stale:bool)->Result<String,String>{
    let value:serde_json::Value=serde_json::from_str(saved_json).map_err(|_|"已保存的纪要无法读取。")?;
    let markdown=value.get("markdown").and_then(|x|x.as_str()).filter(|x|!x.trim().is_empty()).ok_or("已保存的纪要没有正文。")?;
    let mut content=String::new();
    if stale {content.push_str("> 整理来源已变化或不可用：以下为之前保留的结果，请核对原文。\n\n");}
    if value.get("quality").and_then(|v|v.as_str())==Some("draft") ||
       value.get("processing").and_then(|v|v.get("complete")).and_then(|v|v.as_bool())==Some(false) {
        content.push_str("> 草稿：以下是已保存的部分整理内容。\n\n");
    }
    content.push_str(markdown);
    Ok(content)
}

fn render(title:&str, saved_json:&str, extra:&str, stale:bool, word:bool)->Result<Vec<u8>,String>{
    if title.trim().is_empty(){return Err("会议标题不能为空。".into());}
    let mut content=saved_content(saved_json,stale)?;
    if !extra.trim().is_empty(){content.push_str("\n\n");content.push_str(extra);}
    if word {crate::meeting_document_export::word(title,&content)} else {Ok(crate::meeting_document_export::mindmap(title,&content))}
}

#[no_mangle]
pub extern "system" fn Java_com_denzic_companion_mobile_NativeMeetingDocuments_savedTextNative(
    mut env:JNIEnv, _class:JClass, saved_json:JString, stale:jboolean
)->jni::sys::jstring {
    let result=std::panic::catch_unwind(std::panic::AssertUnwindSafe(||->Result<String,String>{
        let saved:String=env.get_string(&saved_json).map_err(|e|e.to_string())?.into();
        saved_content(&saved,stale!=0)
    }));
    match result {
        Ok(Ok(value))=>match env.new_string(value){Ok(s)=>s.into_raw(),Err(e)=>{let _=env.throw_new("java/io/IOException",e.to_string());std::ptr::null_mut()}},
        Ok(Err(error))=>{let _=env.throw_new("java/io/IOException",error);std::ptr::null_mut()},
        Err(_)=>{let _=env.throw_new("java/io/IOException","会议内容读取失败，已保存的内容保持不变。");std::ptr::null_mut()},
    }
}

#[no_mangle]
pub extern "system" fn Java_com_denzic_companion_mobile_NativeMeetingDocuments_exportSavedNative(
    mut env:JNIEnv, _class:JClass, title:JString, saved_json:JString, extra:JString, stale:jboolean, word:jboolean
)->jbyteArray {
    let result=std::panic::catch_unwind(std::panic::AssertUnwindSafe(||->Result<Vec<u8>,String>{
        let title:String=env.get_string(&title).map_err(|e|e.to_string())?.into();
        let saved:String=env.get_string(&saved_json).map_err(|e|e.to_string())?.into();
        let extra:String=env.get_string(&extra).map_err(|e|e.to_string())?.into();
        render(&title,&saved,&extra,stale!=0,word!=0)
    }));
    match result {
        Ok(Ok(bytes))=>match env.byte_array_from_slice(&bytes){Ok(a)=>a.into_raw(),Err(e)=>{let _=env.throw_new("java/io/IOException",e.to_string());std::ptr::null_mut()}},
        Ok(Err(error))=>{let _=env.throw_new("java/io/IOException",error);std::ptr::null_mut()},
        Err(_)=>{let _=env.throw_new("java/io/IOException","文档导出失败，已保存的内容保持不变。");std::ptr::null_mut()},
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn mobile_saved_documents_retain_source_notice_and_notes() {
        use std::io::{Cursor,Read};
        let json=serde_json::json!({"markdown":"## 分段原文依据\n- 小王周五发报价"}).to_string();
        let word=render("会议",&json,"## 用户补充\n蓝色文件夹",true,true).unwrap();
        let mut archive=zip::ZipArchive::new(Cursor::new(word)).unwrap();let mut body=String::new();archive.by_name("word/document.xml").unwrap().read_to_string(&mut body).unwrap();
        for text in ["整理来源已变化","小王周五发报价","蓝色文件夹"] {assert!(body.contains(text));}
        let map=String::from_utf8(render("会议",&json,"## 用户补充\n蓝色文件夹",true,false).unwrap()).unwrap();
        for text in ["整理来源已变化","小王周五发报价","蓝色文件夹"] {assert!(map.contains(text));}
        let draft=serde_json::json!({"markdown":"已保存片段", "quality":"draft", "processing":{"complete":false}}).to_string();
        let partial=String::from_utf8(render("会议",&draft,"",false,false).unwrap()).unwrap();
        assert!(partial.contains("草稿") && partial.contains("已保存片段"));
        assert!(render("会议","{}","",false,true).is_err());
        assert!(saved_content(&draft,true).unwrap().contains("整理来源已变化"));
        assert!(saved_content(&draft,true).unwrap().contains("草稿"));
        assert!(saved_content("{}",false).is_err());
    }
}
