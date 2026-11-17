//! Shared canonical source-bound minutes contract, used by both providers.
//! Shape, literal task fields and source references are mechanical checks only.
use std::collections::{HashMap,HashSet};
use serde::{Deserialize,Serialize};
use serde_json::{json,Value};
use crate::companion_v1::{CompanionV1ActionItem,CompanionV1HostSession,CompanionV1MeetingMinutes};
const MAX_REQUEST_BYTES:usize=96*1024;
#[path="automatic_brief_local_document.rs"]
pub(super) mod local_document;
#[derive(Debug,Clone,Deserialize,Serialize)]
#[serde(deny_unknown_fields)]
pub(in crate::backend::minutes) struct Entry {pub(in crate::backend::minutes) text:String,pub(in crate::backend::minutes) sources:Vec<String>}
#[derive(Debug,Clone,Deserialize,Serialize)]
#[serde(rename_all="lowercase")]
pub(in crate::backend::minutes) enum Kind {Opinion,Recommendation,Forecast,Status,Decision}
impl Kind {pub(in crate::backend::minutes) fn label(&self)->&'static str {match self {Self::Opinion=>"观点",Self::Recommendation=>"建议",Self::Forecast=>"预计",Self::Status=>"现状",Self::Decision=>"决定"}}}
#[derive(Debug,Clone,Deserialize,Serialize)]
#[serde(deny_unknown_fields)]
pub(in crate::backend::minutes) struct Point {pub(in crate::backend::minutes) kind:Kind,pub(in crate::backend::minutes) text:String,pub(in crate::backend::minutes) sources:Vec<String>}
#[derive(Debug,Clone,Deserialize,Serialize)]
#[serde(deny_unknown_fields)]
pub(in crate::backend::minutes) struct Topic {pub(in crate::backend::minutes) title:String,pub(in crate::backend::minutes) points:Vec<Point>,#[serde(default)]pub(in crate::backend::minutes) details:Vec<Entry>}
#[derive(Debug,Clone,Deserialize,Serialize)]
#[serde(deny_unknown_fields)]
pub(in crate::backend::minutes) struct Action {pub(in crate::backend::minutes) text:String,pub(in crate::backend::minutes) owner:Option<String>,pub(in crate::backend::minutes) due:Option<String>,pub(in crate::backend::minutes) sources:Vec<String>}
#[derive(Debug,Clone,Deserialize,Serialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
pub(in crate::backend::minutes) struct Document {pub(in crate::backend::minutes) purpose:String,pub(in crate::backend::minutes) topics:Vec<Topic>,pub(in crate::backend::minutes) decisions:Vec<Entry>,pub(in crate::backend::minutes) action_items:Vec<Action>,pub(in crate::backend::minutes) questions:Vec<Entry>}
#[derive(Debug,Clone,Serialize)]
pub(in crate::backend::minutes) struct Unit {pub(in crate::backend::minutes) id:String,pub(in crate::backend::minutes) text:String}
#[derive(Debug,Clone,Serialize)]
pub(in crate::backend::minutes) struct Constraint {pub(in crate::backend::minutes) id:String,pub(in crate::backend::minutes) source:String,pub(in crate::backend::minutes) quote:String}

pub(in crate::backend::minutes) fn source_units(text:&str)->Vec<Unit> {
    let mut parts=Vec::new();let mut part=String::new();
    for line in text.split_inclusive('\n') {
        if !part.is_empty()&&part.len()+line.len()>1800 {parts.push(std::mem::take(&mut part));}
        for ch in line.chars() {
            if !part.is_empty()&&part.len()+ch.len_utf8()>1800 {parts.push(std::mem::take(&mut part));}
            part.push(ch);
        }
    }
    if !part.is_empty(){parts.push(part);}
    parts.into_iter().enumerate().map(|(i,text)|Unit{id:format!("u{i:03}"),text}).collect()
}
pub(in crate::backend::minutes) fn constraints(units:&[Unit])->Vec<Constraint> {
    const KEYS:[&str;20]=["成本","费用","预算","报价","代价","价格","只有","除非","前提","如果","尚未","还没","未通过","暂定","未决定","不批准","不确定","不能","风险","条件"];
    let mut out=Vec::new();let mut seen=HashSet::new();
    for unit in units {
        let mut previous=String::new();let mut sentence=String::new();
        for c in unit.text.chars().chain(std::iter::once('\n')) {
            sentence.push(c);
            if !matches!(c,'。'|'！'|'？'|'；'|'\n'){continue;}
            let part=sentence.trim().to_string();sentence.clear();
            if part.is_empty(){continue;}
            if KEYS.iter().any(|key|part.contains(key)) {
                let quote=if previous.chars().count()+part.chars().count()<=300 {format!("{previous} {part}").trim().to_string()}else{part.clone()};
                if quote.chars().count()<=300&&seen.insert(quote.clone()) {out.push(Constraint{id:format!("c{:03}",out.len()),source:unit.id.clone(),quote});}
            }
            previous=part;
        }
    }
    out
}
pub(in crate::backend::minutes) fn line(text:&str,max:usize)->bool {!text.trim().is_empty()&&text.chars().count()<=max&&!text.contains(['\n','\r'])}
pub(in crate::backend::minutes) fn refs(ids:&[String],known:&HashMap<&str,&str>)->bool {
    !ids.is_empty()&&ids.len()<=8&&ids.iter().all(|id|known.contains_key(id.as_str()))&&ids.iter().collect::<HashSet<_>>().len()==ids.len()
}
pub(in crate::backend::minutes) fn normalized(text:&str)->String {text.chars().filter(|c|!c.is_whitespace()).collect()}
pub(in crate::backend::minutes) fn validate_with_details_limit(doc:&Document,units:&[Unit],details_limit:usize)->Result<(),String> {
    let known=units.iter().map(|u|(u.id.as_str(),u.text.as_str())).collect::<HashMap<_,_>>();
    let mut issues=Vec::new();let mut titles=HashSet::new();let mut texts=HashSet::new();let mut chars=0;
    if !line(&doc.purpose,80){issues.push("purpose须为80字内完整单行".to_string());}
    if doc.topics.is_empty()||doc.topics.len()>8 {issues.push("topics须为1至8个实际内容组".into());}
    for (i,t) in doc.topics.iter().enumerate() {
        if !line(&t.title,26)||!titles.insert(&t.title){issues.push(format!("topics[{i}].title须为26字内不重复单行"));}
        if t.points.is_empty()||t.points.len()>3||t.details.len()>details_limit {issues.push(format!("topics[{i}]主回答1至3条、补充0至{details_limit}条"));}
        for (j,p) in t.points.iter().enumerate() {
            if !line(&p.text,90)||!refs(&p.sources,&known)||!texts.insert(&p.text){issues.push(format!("topics[{i}].points[{j}]须为90字内不重复单行并引用实际原id"));}
            chars+=p.text.chars().count();
        }
        for (j,p) in t.details.iter().enumerate() {if !line(&p.text,120)||!refs(&p.sources,&known){issues.push(format!("topics[{i}].details[{j}]须为120字内单行并引用实际原id"));}}
    }
    if chars>1000{issues.push("主要回答超出1000字安全上限，须保留要义并收短".into());}
    for (name,items) in [("decisions",&doc.decisions),("questions",&doc.questions)] {
        if items.len()>20{issues.push(format!("{name}超出20项"));}
        for (i,p) in items.iter().enumerate(){if !line(&p.text,180)||!refs(&p.sources,&known){issues.push(format!("{name}[{i}]须为180字内单行并引用实际原id"));}}
    }
    if doc.action_items.len()>20{issues.push("actionItems超出20项".into());}
    for (i,a) in doc.action_items.iter().enumerate() {
        if !line(&a.text,180)||!refs(&a.sources,&known){issues.push(format!("actionItems[{i}]须为180字内单行并引用实际原id"));continue;}
        let original=normalized(&a.sources.iter().map(|id|known[id.as_str()]).collect::<Vec<_>>().join("\n"));
        for (field,v) in [("owner",&a.owner),("due",&a.due)] {
            if v.as_ref().is_some_and(|v|!line(v,80)||!original.contains(&normalized(v))) {issues.push(format!("actionItems[{i}].{field}只能为原话明确出现的字面值，否则null"));}
        }
    }
    if issues.is_empty(){Ok(())}else{Err(issues.join("；"))}
}
pub(in crate::backend::minutes) fn render(doc:&Document,units:&[Unit],speaker:Option<&str>)->String {
    let known=units.iter().map(|u|(u.id.as_str(),u.text.as_str())).collect::<HashMap<_,_>>();
    let mut md=format!("## 会议主线\n\n- {}\n\n## 主题脉络\n\n",doc.purpose.trim());
    for topic in &doc.topics {
        md.push_str(&format!("### {}\n\n",topic.title.trim()));
        for p in &topic.points{md.push_str(&format!("- {}：{}\n",p.kind.label(),p.text.trim()));}
        for p in &topic.details{md.push_str(&format!("- 补充：{}\n",p.text.trim()));}
        md.push('\n');
    }
    if !doc.decisions.is_empty(){md.push_str("## Decisions\n\n");for p in &doc.decisions{md.push_str(&format!("- {}\n",p.text));}md.push('\n');}
    if !doc.action_items.is_empty(){md.push_str("## Action Items\n\n");for a in &doc.action_items {
        md.push_str(&format!("- {}",a.text));let mut meta=Vec::new();
        if let Some(v)=&a.owner{meta.push(format!("owner: {v}"));}if let Some(v)=&a.due{meta.push(format!("due: {v}"));}
        if !meta.is_empty(){md.push_str(&format!(" ({})",meta.join(", ")));}md.push('\n');
    }md.push('\n');}
    if !doc.questions.is_empty(){md.push_str("## Questions\n\n");for p in &doc.questions{md.push_str(&format!("- {}\n",p.text));}md.push('\n');}
    if let Some(section)=speaker{md.push_str(section);md.push_str("\n\n");}
    md.push_str("## 主题原话\n\n");
    for topic in &doc.topics {
        md.push_str(&format!("### {} · 原话\n\n",topic.title));let mut seen=HashSet::new();
        for ids in topic.points.iter().map(|p|&p.sources).chain(topic.details.iter().map(|p|&p.sources)) {
            for id in ids{if seen.insert(id){md.push_str(&format!("- {}\n\n",known[id.as_str()].replace(['\r','\n']," ")));}}
        }
    }
    md
}
pub(in crate::backend::minutes) fn source_first_input(input:&Value)->String {
    let Some(object)=input.as_object()else{return input.to_string();};
    let priority=["sourceUnits","sourceConstraints","readingBudget","previousDocument","document","draft","checkClaims","summaryUnits","questions","pairs","auditProblems","deletionOnlyPaths"];
    let mut fields=Vec::new();
    for key in priority {if let Some(value)=object.get(key){fields.push(format!("{}:{}",json!(key),value));}}
    for(key,value)in object {if !priority.contains(&key.as_str()){fields.push(format!("{}:{}",json!(key),value));}}
    format!("{{{}}}",fields.join(","))
}
