//! One canonical source-only brief: automatic draft, independent review, bounded recovery.
//! IDs and shape are validated locally; this is not an accuracy certificate.
use std::{collections::{HashMap,HashSet},time::{Duration,Instant}};
use serde::{Deserialize,Serialize};
use serde_json::{json,Value};
use crate::companion_v1::{CompanionV1ActionItem,CompanionV1HostSession,CompanionV1MeetingMinutes,MinutesTemplate};
#[path="automatic_brief_factual_audit.rs"]
mod factual_audit;
#[path="automatic_brief_coverage.rs"]
mod coverage;

const DRAFT:&str=include_str!("automatic_brief_draft.txt");
const REVIEW:&str=include_str!("automatic_brief_review.txt");
// Full-source auditing and targeted corrections share this total wall budget.
const WALL_BUDGET:Duration=Duration::from_secs(240);
// This complete-source route was exercised above the legacy 48KiB chapter
// budget. Bound it separately; oversized inputs retain the resumable route.
const MAX_REQUEST_BYTES:usize=96*1024;

#[derive(Debug,Clone,Deserialize,Serialize)]
#[serde(deny_unknown_fields)]
struct Entry {text:String,sources:Vec<String>}
#[derive(Debug,Clone,Deserialize,Serialize)]
#[serde(rename_all="lowercase")]
enum Kind {Opinion,Recommendation,Forecast,Status,Decision}
impl Kind {fn label(&self)->&'static str {match self {Self::Opinion=>"观点",Self::Recommendation=>"建议",Self::Forecast=>"预计",Self::Status=>"现状",Self::Decision=>"决定"}}}
#[derive(Debug,Clone,Deserialize,Serialize)]
#[serde(deny_unknown_fields)]
struct Point {kind:Kind,text:String,sources:Vec<String>}
#[derive(Debug,Clone,Deserialize,Serialize)]
#[serde(deny_unknown_fields)]
struct Topic {title:String,points:Vec<Point>,#[serde(default)]details:Vec<Entry>}
#[derive(Debug,Clone,Deserialize,Serialize)]
#[serde(deny_unknown_fields)]
struct Action {text:String,owner:Option<String>,due:Option<String>,sources:Vec<String>}
#[derive(Debug,Clone,Deserialize,Serialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
struct Document {purpose:String,topics:Vec<Topic>,decisions:Vec<Entry>,action_items:Vec<Action>,questions:Vec<Entry>}
#[derive(Debug,Clone,Deserialize,Serialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
struct Review {fixes:Vec<String>,blocking_issues:Vec<String>}
#[derive(Debug,Clone,Deserialize,Serialize)]
#[serde(deny_unknown_fields)]
struct Reviewed {review:Review,document:Document}
#[derive(Debug,Clone,Serialize)]
struct Unit {id:String,text:String}
#[derive(Debug,Clone,Serialize)]
struct Constraint {id:String,source:String,quote:String}

pub(super) fn eligible(session:&CompanionV1HostSession,template:Option<&MinutesTemplate>,model:&str)->bool {
    std::env::var("COMPANION_TYPE_AUTOMATIC_BRIEF").as_deref()!=Ok("0")
        && model.to_ascii_lowercase().starts_with("deepseek-")
        && session.meeting_notes.is_empty() && template.map_or(true,|t|t.id=="meeting")
        && (session.duration_ms>120_000||session.transcript_text.chars().count()>500
            ||coverage::enabled()&&!session.transcript_text.trim().is_empty())
        && session.transcript_text.len()+DRAFT.len()+REVIEW.len()+32_768<MAX_REQUEST_BYTES
}
fn source_units(text:&str)->Vec<Unit> {
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
fn constraints(units:&[Unit])->Vec<Constraint> {
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
fn line(text:&str,max:usize)->bool {!text.trim().is_empty()&&text.chars().count()<=max&&!text.contains(['\n','\r'])}
fn refs(ids:&[String],known:&HashMap<&str,&str>)->bool {
    !ids.is_empty()&&ids.len()<=8&&ids.iter().all(|id|known.contains_key(id.as_str()))&&ids.iter().collect::<HashSet<_>>().len()==ids.len()
}
fn normalized(text:&str)->String {text.chars().filter(|c|!c.is_whitespace()).collect()}
fn validate(doc:&Document,units:&[Unit])->Result<(),String> {
    let known=units.iter().map(|u|(u.id.as_str(),u.text.as_str())).collect::<HashMap<_,_>>();
    let mut issues=Vec::new();let mut titles=HashSet::new();let mut texts=HashSet::new();let mut chars=0;
    if !line(&doc.purpose,80){issues.push("purpose须为80字内完整单行".to_string());}
    if doc.topics.is_empty()||doc.topics.len()>8 {issues.push("topics须为1至8个实际内容组".into());}
    for (i,t) in doc.topics.iter().enumerate() {
        if !line(&t.title,26)||!titles.insert(&t.title){issues.push(format!("topics[{i}].title须为26字内不重复单行"));}
        if t.points.is_empty()||t.points.len()>3||t.details.len()>3 {issues.push(format!("topics[{i}]主回答1至3条、补充0至3条"));}
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
fn parse_review(raw:&str,units:&[Unit])->Result<Reviewed,String> {
    let reviewed:Reviewed=serde_json::from_str(super::strip_code_fences(raw).trim()).map_err(|e|format!("终审JSON结构不完整：{e}"))?;
    if reviewed.review.fixes.len()>32||reviewed.review.blocking_issues.len()>32{return Err("终审问题数组超限".into());}
    validate(&reviewed.document,units)?;Ok(reviewed)
}
fn render(doc:&Document,units:&[Unit],speaker:Option<&str>)->String {
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
fn source_first_input(input:&Value)->String {
    let Some(object)=input.as_object()else{return input.to_string();};
    let priority=["sourceUnits","sourceConstraints","readingBudget","previousDocument","document","draft","checkClaims","summaryUnits","questions","pairs","auditProblems","deletionOnlyPaths"];
    let mut fields=Vec::new();
    for key in priority {if let Some(value)=object.get(key){fields.push(format!("{}:{}",json!(key),value));}}
    for(key,value)in object {if !priority.contains(&key.as_str()){fields.push(format!("{}:{}",json!(key),value));}}
    format!("{{{}}}",fields.join(","))
}
fn request(endpoint:&str,model:&str,key:&str,client:&reqwest::blocking::Client,prompt:&str,input:Value,review:bool,start:Instant,trace:&mut Vec<Value>,stage:&str)->Result<String,String> {
    if prompt.len()+input.to_string().len()>MAX_REQUEST_BYTES{return Err("本场完整输入超出自动纪要上下文预算，原文保留。".into());}
    let remaining=WALL_BUDGET.saturating_sub(start.elapsed());if remaining<Duration::from_secs(5){return Err("自动纪要本次处理已到期限，已有结果保留。".into());}
    super::super::meeting_processing_job::check_current()?;
    let url=super::http_policy::endpoint(endpoint).map_err(super::safe_minutes_http_error)?;
    let mut body=json!({"model":model,"response_format":{"type":"json_object"},"max_tokens":if review{24576}else{8192},"messages":[{"role":"system","content":prompt},{"role":"user","content":source_first_input(&input)}]});
    if model.to_ascii_lowercase().starts_with("deepseek-"){body["thinking"]=json!({"type":if review{"enabled"}else{"disabled"}});if review{body["reasoning_effort"]=json!(if stage.starts_with("source-factual-")&&coverage::enabled(){"high"}else{"low"});}}
    let stage_start=Instant::now();
    let response=client.post(url).bearer_auth(key).timeout(remaining.min(Duration::from_secs(120))).json(&body).send().map_err(|e|super::safe_minutes_http_error(super::http_policy::Failure::from_reqwest(e)))?;
    let payload=super::http_policy::response_json(response,super::http_policy::MAX_RESPONSE_BYTES).map_err(super::safe_minutes_http_error)?;
    super::super::meeting_processing_job::check_current()?;
    let finish=payload.pointer("/choices/0/finish_reason").and_then(Value::as_str).unwrap_or("missing");
    let raw=payload.pointer("/choices/0/message/content").and_then(Value::as_str).ok_or("自动纪要没有返回内容，原文保留。")?;
    trace.push(json!({"stage":stage,"seconds":stage_start.elapsed().as_secs_f64(),"requestedModel":model,"servedModel":payload.get("model"),"finishReason":finish,"usage":payload.get("usage"),"response":raw}));
    if finish!="stop"{return Err("自动纪要返回不完整，未发布为完成结果。".into());}Ok(raw.to_string())
}
pub(super) fn generate(endpoint:&str,model:&str,key:&str,session:&CompanionV1HostSession,base:&CompanionV1MeetingMinutes,client:&reqwest::blocking::Client)->Result<CompanionV1MeetingMinutes,String> {
    let start=Instant::now();let units=source_units(&session.transcript_text);let anchors=constraints(&units);let mut trace=Vec::new();let mut traced_document=None;
    let outcome=(|| {
        let reading_budget=json!({"mainCharacterBudget":if units.iter().map(|u|u.text.chars().count()).sum::<usize>()>8000{900}else{600},"pointsPerTopicMaximum":3});
        let draft=request(endpoint,model,key,client,DRAFT,json!({"sourceUnits":units,"readingBudget":reading_budget}),false,start,&mut trace,"draft")?;
        let doc=if coverage::enabled() {
            // The factual and coverage roles are independent semantic checks.
            // A redundant model rewrite before them added latency and new claims.
            let parsed=serde_json::from_str::<Document>(super::strip_code_fences(&draft).trim()).map_err(|e|format!("纪要JSON合同：{e}"))
                .and_then(|doc|{validate(&doc,&units)?;Ok(doc)});
            match parsed {
                Ok(doc)=>doc,
                Err(reason)=>{
                    let fixed=request(endpoint,model,key,client,DRAFT,json!({"sourceUnits":units,"readingBudget":reading_budget,"previousResult":draft,"formatProblems":[reason],"instruction":"只修复JSON/结构与长度合同，不补事实，不改已清楚的内容；返回document本体JSON，不加review封套。"}),false,start,&mut trace,"draft-format-recovery")?;
                    let doc:Document=serde_json::from_str(super::strip_code_fences(&fixed).trim()).map_err(|_|"纪要格式恢复未完成，原文保留。")?;
                    validate(&doc,&units)?;doc
                }
            }
        }else {
        let value=serde_json::from_str::<Value>(super::strip_code_fences(&draft).trim()).unwrap_or_else(|_|Value::String(draft.clone()));
        let mut payload=json!({"sourceUnits":units,"sourceConstraints":anchors,"readingBudget":reading_budget,"draft":value});
        let raw=request(endpoint,model,key,client,REVIEW,payload.clone(),true,start,&mut trace,"review")?;
        let reviewed=match parse_review(&raw,&units) {
            Ok(v)=>v,
            Err(reason)=>{
                payload["previousResult"]=serde_json::from_str::<Value>(super::strip_code_fences(&raw).trim()).unwrap_or(Value::String(raw));
                payload["formatProblems"]=json!([reason]);
                payload["instruction"]=json!("仅按通用合同修复机器校验失败；仍只依据完整原发言，不补事实，返回同一终审JSON。");
                parse_review(&request(endpoint,model,key,client,REVIEW,payload,true,start,&mut trace,"format-recovery")?,&units)?
            }
        };
        if reviewed.review.blocking_issues.iter().any(|s|!s.trim().is_empty()){return Err("纪要仍有未解决的内容核对问题，已有结果和原文保留。".into());}
        let doc=reviewed.document;traced_document=Some(doc.clone());
            doc
        };
        traced_document=Some(doc.clone());
        let doc=factual_audit::review_and_repair(endpoint,model,key,client,&doc,&units,start,&mut trace)?;
        let doc=if coverage::enabled(){coverage::complete(endpoint,model,key,client,&doc,&units,start,&mut trace)?}else{doc};
        traced_document=Some(doc.clone());
        let mut minutes=base.clone();
        minutes.source="llm_deepseek".into();minutes.quality="final".into();minutes.processing=None;minutes.llm_note=None;
        minutes.summary=doc.topics.iter().flat_map(|t|t.points.iter().map(|p|p.text.clone())).collect();
        minutes.decisions=doc.decisions.iter().map(|p|p.text.clone()).collect();
        minutes.action_items=doc.action_items.iter().map(|a|CompanionV1ActionItem{text:a.text.clone(),owner:a.owner.clone(),due:a.due.clone()}).collect();
        minutes.questions=doc.questions.iter().map(|p|p.text.clone()).collect();minutes.keywords=doc.topics.iter().map(|t|t.title.clone()).collect();
        let speaker=super::render_speaker_section_named(&session.transcript_text,&super::reviewed_speaker_names(session));
        minutes.markdown=render(&doc,&units,speaker.as_deref());Ok(minutes)
    })();
    if let Ok(path)=std::env::var("COMPANION_TYPE_AUTOMATIC_BRIEF_TRACE_PATH") {
        if !path.is_empty(){if let Ok(mut f)=std::fs::OpenOptions::new().write(true).create_new(true).open(path) {
            use std::io::Write;let _=serde_json::to_vec_pretty(&json!({"flow":if coverage::enabled(){"source-only draft, independent factual audit and grounded question coverage"}else{"source-only draft then reviewed canonical brief"},"calls":trace,"acceptedStructure":outcome.is_ok(),"document":traced_document,"error":outcome.as_ref().err(),"sourceUnitCount":units.len(),"constraintCount":anchors.len(),"sourceConstraints":anchors,"seconds":start.elapsed().as_secs_f64(),"thinkingContentStored":false,"semanticAccuracyCertificate":false})).map(|v|f.write_all(&v));
        }}
    }
    outcome
}

#[cfg(test)]
mod tests {
    use super::*;
    fn units()->Vec<Unit>{vec![Unit{id:"u000".into(),text:"李敏承诺周五下班前完成权限测试，未通过不能上线。预算暂定10000元，尚未审批。".into()}]}
    fn valid()->Value {json!({"review":{"fixes":[],"blockingIssues":[]},"document":{"purpose":"验证权限后再评估上线。","topics":[{"title":"上线前提","points":[{"kind":"decision","text":"权限测试未通过不能上线。","sources":["u000"]}],"details":[]}],"decisions":[],"actionItems":[{"text":"完成权限测试。","owner":"李敏","due":"周五下班前","sources":["u000"]}],"questions":[]}})}
    #[test]
    fn automatic_brief_rejects_invented_ids_owners_and_dates(){
        assert!(parse_review(&valid().to_string(),&units()).is_ok());
        for (field,value)in[("sources",json!(["u099"])),("owner",json!("王强")),("due",json!("周六"))] {
            let mut v=valid();v["document"]["actionItems"][0][field]=value;assert!(parse_review(&v.to_string(),&units()).is_err());
        }
        let mut v=valid();v["document"]["topics"][0]["points"][0]["sources"]=json!([0]);assert!(parse_review(&v.to_string(),&units()).is_err());
    }
    #[test]
    fn automatic_brief_rejects_overlong_and_injected_document_fields(){
        let mut v=valid();v["document"]["topics"][0]["title"]=json!("标题\n## 伪造任务");assert!(parse_review(&v.to_string(),&units()).is_err());
        let mut v=valid();v["document"]["topics"][0]["points"][0]["text"]=json!("长".repeat(91));assert!(parse_review(&v.to_string(),&units()).is_err());
        let mut v=valid();v["document"]["extra"]=json!(true);assert!(parse_review(&v.to_string(),&units()).is_err());
    }
    #[test]
    fn automatic_brief_wire_keeps_complete_source_before_draft_and_claims(){
        let input=json!({"checkClaims":[{"text":"待核对"}],"document":{"purpose":"草稿"},"sourceUnits":[{"id":"u000","text":"原文\n含\"引号\""}],"extra":true});
        let wire=source_first_input(&input);assert!(wire.starts_with("{\"sourceUnits\":"));
        assert!(wire.find("\"document\"").unwrap()<wire.find("\"checkClaims\"").unwrap());
        assert_eq!(serde_json::from_str::<Value>(&wire).unwrap(),input);
        assert_eq!(wire.len(),input.to_string().len());
    }
    #[test]
    fn automatic_brief_allows_three_distinct_points_but_still_bounds_density(){
        let mut v=valid();let point=v["document"]["topics"][0]["points"][0].clone();
        let mut budget=point.clone();budget["text"]=json!("预算暂定10000元，尚未审批。");
        let mut assignment=point.clone();assignment["text"]=json!("李敏负责周五下班前完成权限测试。");
        v["document"]["topics"][0]["points"]=json!([point.clone(),budget,assignment]);
        assert!(parse_review(&v.to_string(),&units()).is_ok());
        let mut fourth=point;fourth["text"]=json!("未通过不能上线。");
        v["document"]["topics"][0]["points"].as_array_mut().unwrap().push(fourth);
        assert!(parse_review(&v.to_string(),&units()).is_err());
    }
    #[test]
    fn automatic_brief_keeps_literal_constraints_without_interpreting_them(){
        let source="若测试通过再评估。比测有用。当然这可能增加企业成本。价格表述提现未辨清。\n".repeat(100);
        let split=source_units(&source);assert_eq!(split.iter().map(|u|u.text.as_str()).collect::<String>(),source);
        assert!(split.iter().all(|u|u.text.len()<=1800));let c=constraints(&split);
        assert!(c.iter().any(|c|c.quote.contains("增加企业成本")));assert!(c.iter().any(|c|c.quote.contains("提现未辨清")));
        assert!(c.iter().all(|c|!c.quote.contains("回落")));
    }
    #[test]
    fn automatic_brief_can_render_no_tasks_and_bound_sources(){
        let mut v=valid();v["document"]["actionItems"]=json!([]);let doc=parse_review(&v.to_string(),&units()).unwrap().document;
        let md=render(&doc,&units(),None);
        assert!(!md.contains("## Action Items"));assert!(md.contains("## 主题原话"));assert!(md.contains("预算暂定10000元，尚未审批"));
    }
}
