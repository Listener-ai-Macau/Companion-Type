//! Literal human evidence, separate from ASR and inferred meeting decisions.
use crate::companion_v1::CompanionV1HostSession;
use serde::{Deserialize,Deserializer,Serialize};
use sha2::{Digest,Sha256};
use std::collections::HashSet;

#[derive(Clone,Copy,Debug,Default,Deserialize,Serialize,PartialEq,Eq)]
#[serde(rename_all="camelCase")]
pub enum NoteKind {#[default] Note,Followup}
impl NoteKind {pub fn is_note(&self)->bool{*self==Self::Note}}
#[derive(Clone,Copy,Debug,Deserialize,Serialize,PartialEq,Eq)]
#[serde(rename_all="camelCase")]
pub enum EvidenceKind {Document,Transcript}
#[derive(Clone,Debug,Deserialize,Serialize,PartialEq,Eq)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
pub struct Evidence {
 pub id:String,pub kind:EvidenceKind,pub name:String,pub source_sha256:String,pub quote:String,
 #[serde(default,deserialize_with="present_string",skip_serializing_if="Option::is_none")] pub document_id:Option<String>,
 #[serde(default,deserialize_with="present_string",skip_serializing_if="Option::is_none")] pub extraction_sha256:Option<String>,
 #[serde(default,deserialize_with="present_string",skip_serializing_if="Option::is_none")] pub section_id:Option<String>,
 #[serde(default,deserialize_with="present_string",skip_serializing_if="Option::is_none")] pub section_label:Option<String>,
 #[serde(default,deserialize_with="present_row",skip_serializing_if="Option::is_none")] pub row:Option<u32>,
}
fn present_string<'de,D:Deserializer<'de>>(d:D)->Result<Option<String>,D::Error>{String::deserialize(d).map(Some)}
fn present_row<'de,D:Deserializer<'de>>(d:D)->Result<Option<u32>,D::Error>{u32::deserialize(d).map(Some)}
fn invalid()->String{"人工引用的内容或身份无效；原备注和资料保留。".into()}
fn uuid(value:&str)->bool{uuid::Uuid::parse_str(value).is_ok_and(|id|id.to_string()==value)}
fn sha(value:&str)->bool{value.len()==64&&value.bytes().all(|b|b.is_ascii_digit()||(b'a'..=b'f').contains(&b))}
fn controls(text:&str,quote:bool)->bool{text.chars().any(|c|c.is_control()&&!(quote&&matches!(c,'\n'|'\r'|'\t')))}
fn blank(text:&str)->bool{text.chars().all(|c|c.is_whitespace()||c=='\u{feff}')}
pub fn validate(references:&[Evidence])->Result<(),String>{
 if references.len()>16{return Err("每条备注最多引用16处依据，请先整理已有引用；原资料保留。".into());}
 let mut ids=HashSet::new();let mut total=0usize;
 for item in references {
  let chars=item.quote.encode_utf16().count();
  if chars>4000{return Err("单处引用最多4000个字符，请选择更短的片段；完整原件仍保留。".into());}
  if !uuid(&item.id)||!ids.insert(&item.id)||blank(&item.name)||item.name.encode_utf16().count()>200||controls(&item.name,false)||!sha(&item.source_sha256)||blank(&item.quote)||controls(&item.quote,true){return Err(invalid());}
  total+=chars;if total>16000{return Err("这条备注的引用文字超过16000个字符，请减少或分开保存；完整原件仍保留。".into());}
  match item.kind {
   EvidenceKind::Transcript=>{if item.name!="会议转写"||item.document_id.is_some()||item.extraction_sha256.is_some()||item.section_id.is_some()||item.section_label.is_some()||item.row.is_some(){return Err(invalid());}}
   EvidenceKind::Document=>{
    if !item.document_id.as_deref().is_some_and(uuid)||!item.extraction_sha256.as_deref().is_some_and(sha){return Err(invalid());}
    let part=item.section_id.as_deref().ok_or_else(invalid)?;
    let n=part.strip_prefix("part-").filter(|s|!s.is_empty()&&s.len()<=3&&s.bytes().all(|b|b.is_ascii_digit())).and_then(|s|s.parse::<u16>().ok());
    let label=item.section_label.as_deref().ok_or_else(invalid)?;
    if !n.is_some_and(|n|n>0&&n<1000)||label.encode_utf16().count()>160||controls(label,false)||item.row.is_some_and(|n|n==0||n>1048576){return Err(invalid());}
   }
  }
 }
 Ok(())
}
pub fn hash(text:&str)->String{format!("{:x}",Sha256::digest(text.as_bytes()))}
pub fn verify_transcript(item:&Evidence,text:&str)->Result<(),String>{
 validate(std::slice::from_ref(item))?;
 if item.kind!=EvidenceKind::Transcript||hash(text)!=item.source_sha256||!text.contains(&item.quote){return Err("转写文字已变化或引文不匹配，请重新选择依据；便签输入仍保留。".into());}Ok(())
}
pub fn table_quote(row:&super::super::document_context::TableRow)->String{
 row.cells.iter().map(|cell|format!("{}{}\t{}",cell.column,row.row,cell.text)).collect::<Vec<_>>().join("\n")
}
pub fn verify_document(item:&Evidence,document:&super::super::document_context::Document,extraction:&super::super::document_context::Extraction)->Result<(),String>{
 validate(std::slice::from_ref(item))?;
 if item.kind!=EvidenceKind::Document||item.document_id.as_deref()!=Some(document.id.as_str())||item.name!=document.name||item.source_sha256!=document.source_sha256||item.extraction_sha256.as_deref()!=document.extraction.as_ref().map(|e|e.sha256.as_str())||item.source_sha256!=extraction.source_sha256{return Err("材料或提取版本已变化，请重新选择依据；当前便签输入仍保留。".into());}
 let section=extraction.sections.iter().find(|s|Some(s.id.as_str())==item.section_id.as_deref()).ok_or_else(invalid)?;
 if Some(section.label.as_str())!=item.section_label.as_deref(){return Err(invalid());}
 if let Some(number)=item.row {
  let row=section.table_rows.as_deref().unwrap_or_default().iter().find(|r|r.row==number).ok_or("所引用的单元格暂不可读取；原引文保留。")?;
  if table_quote(row)!=item.quote{return Err("所引用的单元格文字与已保存材料不符；未改变便签。".into());}
 }else if !section.text.contains(&item.quote){return Err("引用文字不在这段已保存材料中，请重新选择；输入仍保留。".into());}
 Ok(())
}
pub fn verify(item:&Evidence,session:&CompanionV1HostSession)->Result<(),String>{
 match item.kind {
  EvidenceKind::Transcript=>verify_transcript(item,&super::super::transcript_review::effective_text(session)),
  EvidenceKind::Document=>{
   let id=item.document_id.as_deref().ok_or_else(invalid)?;
   let row=session.document_context.rows.iter().find(|d|d.id==id).ok_or("这份材料已移除；已有引文仍保留，请重新选择新的依据。")?;
   let extracted=super::super::document_context::extraction(session,id,session.document_context.revision)?;
   verify_document(item,row,&extracted)
  }
 }
}
pub fn verify_changed(session:&CompanionV1HostSession,previous:&[Evidence],proposed:&[Evidence])->Result<(),String>{
 validate(previous)?;validate(proposed)?;
 for item in proposed {if !previous.iter().any(|old|old==item){verify(item,session)?;}}
 Ok(())
}

#[cfg(test)]
mod tests {
 use super::*;
 #[test] fn literal_transcript_binding_rejects_new_text_and_invented_words(){
  let text="嗯，项目还未批准。🙂\n负责人待确认。";
  let value=serde_json::json!({"id":uuid::Uuid::new_v4().to_string(),"kind":"transcript","name":"会议转写","sourceSha256":hash(text),"quote":"项目还未批准"});
  let item:Evidence=serde_json::from_value(value.clone()).unwrap();verify_transcript(&item,text).unwrap();assert!(verify_transcript(&item,&format!("{text}\n已补充新内容。" )).is_err());
  let mut forged=item.clone();forged.quote="项目已经批准".into();assert!(verify_transcript(&forged,text).is_err());assert!(validate(&[item.clone(),item]).is_err());
  let mut unknown=value;unknown["path"]=serde_json::json!("/another-library/private-file");assert!(serde_json::from_value::<Evidence>(unknown).is_err());
 }
}
