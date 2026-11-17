//! Question coverage uses disjoint source evidence and summary-only retrieval.
//! It cannot certify all meaning; malformed evidence and unresolved gaps fail closed.
use std::{collections::{HashMap,HashSet},time::Instant};
use serde::{Deserialize,Serialize};
use serde_json::{json,Value};
use super::{Document,Unit};

const SOURCE:&str=include_str!("automatic_brief_coverage_source.txt");
const RETRIEVE:&str=include_str!("automatic_brief_coverage_retrieve.txt");
const COMPARE:&str=include_str!("automatic_brief_coverage_compare.txt");
const APPEND:&str=include_str!("automatic_brief_coverage_append.txt");
const OMISSIONS:&str=include_str!("automatic_brief_coverage_omissions.txt");
const FAILURE:&str="纪要的重要内容核对尚未完成，原文和已有纪要保留。";

pub(super) fn enabled()->bool {
    // Enable only in the isolated candidate until content qualification finishes.
    std::env::var("COMPANION_TYPE_MINUTES_COVERAGE").as_deref()==Ok("1")
}
fn fail()->String{FAILURE.into()}
fn parse<T:serde::de::DeserializeOwned>(raw:&str)->Result<T,String>{
    serde_json::from_str(super::super::strip_code_fences(raw).trim()).map_err(|_|fail())
}
#[derive(Debug,Clone,Deserialize,Serialize,PartialEq,Eq)]
#[serde(deny_unknown_fields)]
struct Evidence {source:String,quote:String}
#[derive(Debug,Clone,Deserialize,Serialize)]
#[serde(deny_unknown_fields)]
struct Question {id:String,question:String,importance:String,evidence:Vec<Evidence>}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Questions {questions:Vec<RawQuestion>}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct RawQuestion {id:String,question:String,importance:String,evidence:Vec<String>}
#[derive(Debug,Clone,Serialize)]
struct SummaryUnit {id:String,path:String,text:String,#[serde(skip_serializing_if="Option::is_none")]kind:Option<String>}
#[derive(Deserialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
struct Retrieval {id:String,summary_ids:Vec<String>}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Retrieved {answers:Vec<Retrieval>}
#[derive(Debug,Deserialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
struct Check {id:String,result:String,material:bool,difference:String,summary_ids:Vec<String>}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Compared {checks:Vec<Check>}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Omission {question:String,difference:String,importance:String,evidence:Vec<String>}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct OmissionAudit {omissions:Vec<Omission>}
pub(super) struct Omissions(Vec<Question>);

fn decode_omissions(raw:&str,source:&[Value])->Result<Omissions,String>{
    let data:OmissionAudit=parse(raw)?;if data.omissions.len()>4{return Err(fail());}
    let known=source.iter().map(|s|(s["id"].as_str().unwrap(),s)).collect::<HashMap<_,_>>();let mut out=Vec::new();
    for item in data.omissions{
        // This question is internal audit data, never the rendered minutes.
        // Keep the writer's 50-character target, but tolerate bounded wording
        // overhead instead of rejecting an otherwise grounded review at 51.
        if item.importance!="essential"||!super::line(&item.question,100)||item.question.chars().filter(|c|matches!(c,'?'|'？')).count()>1
            ||!super::line(&item.difference,100)||item.evidence.is_empty()||item.evidence.len()>8{return Err(fail());}
        let mut evidence=Vec::new();
        for id in item.evidence{
            let s=known.get(id.as_str()).ok_or_else(fail)?;let quote=s["text"].as_str().ok_or_else(fail)?;if quote.trim().is_empty(){return Err(fail());}
            let exact=Evidence{source:s["source"].as_str().unwrap().into(),quote:quote.into()};if !evidence.contains(&exact){evidence.push(exact);}
        }
        out.push(Question{id:String::new(),question:item.question,importance:item.importance,evidence});
    }
    Ok(Omissions(out))
}
pub(super) fn audit_omissions(endpoint:&str,model:&str,key:&str,client:&reqwest::blocking::Client,doc:&Document,units:&[Unit],start:Instant,trace:&mut Vec<Value>)->Result<Omissions,String>{
    audit_omissions_at(endpoint,model,key,client,doc,units,start,trace,"coverage-source-to-document")
}
fn audit_omissions_at(endpoint:&str,model:&str,key:&str,client:&reqwest::blocking::Client,doc:&Document,units:&[Unit],start:Instant,trace:&mut Vec<Value>,stage:&str)->Result<Omissions,String>{
    let source=super::factual_audit::evidence_sentences(units);
    let wire=units.iter().map(|u|json!({"id":u.id,"sentences":source.iter().filter(|s|s["source"].as_str()==Some(u.id.as_str())).map(|s|json!({"id":s["id"],"text":s["text"]})).collect::<Vec<_>>()})).collect::<Vec<_>>();
    // This independent source-to-document check sees the actual document,
    // never the writer's question bank or any expected omission labels.
    let raw=super::request(endpoint,model,key,client,OMISSIONS,json!({"sourceUnits":wire,"document":doc}),true,start,trace,stage)?;
    decode_omissions(&raw,&source)
}

// Model returns only existing sentence IDs. The program retrieves original
// text; the model never has to transcribe or normalize an evidence quotation.
fn grounded_evidence(ids:Vec<String>,all:&[Value],allowed:&HashSet<&str>)->Result<Vec<Evidence>,String>{
    // The budget is eight exact source spans. Adjacent short ASR sentences can
    // form one span without dropping any roles, branches or conditions.
    if ids.is_empty()||ids.len()>32{return Err(fail());}
    let known=all.iter().enumerate().filter(|(_,s)|allowed.contains(s["source"].as_str().unwrap())).map(|(i,s)|(s["id"].as_str().unwrap(),(i,s))).collect::<HashMap<_,_>>();
    let mut selected=Vec::new();
    for id in ids{let &(i,s)=known.get(id.as_str()).ok_or_else(fail)?;if s["text"].as_str().is_none_or(|text|text.trim().is_empty()){return Err(fail());}if !selected.iter().any(|(old,_)|*old==i){selected.push((i,s));}}
    selected.sort_by_key(|(i,_)|*i);let mut out:Vec<Evidence>=Vec::new();let mut previous=None;
    for(i,s)in selected{
        let source=s["source"].as_str().unwrap();let quote=s["text"].as_str().unwrap();
        if previous==Some(i.saturating_sub(1))&&out.last().is_some_and(|e|e.source==source){out.last_mut().unwrap().quote.push_str(quote);}
        else{out.push(Evidence{source:source.into(),quote:quote.into()});}previous=Some(i);
    }
    if out.len()>8{return Err(fail());}Ok(out)
}
fn decode_questions(raw:&str,all:&[Value],window:&[&Unit],primary:&HashSet<&str>)->Result<Vec<Question>,String>{
    let parsed:Questions=parse(raw)?;if parsed.questions.len()>4{return Err(fail());}
    let local=window.iter().map(|u|u.id.as_str()).collect::<HashSet<_>>();
    let mut out=Vec::new();
    for q in parsed.questions {
        if !super::line(&q.question,50)||q.question.chars().filter(|c|matches!(c,'?'|'？')).count()>1
            ||!matches!(q.importance.as_str(),"essential"|"supporting"){return Err(fail());}
        let evidence=grounded_evidence(q.evidence,all,&local)?;
        // Context-only questions belong to another window. They do not make
        // this complete primary window fail or consume its format recovery.
        if !evidence.iter().any(|e|primary.contains(e.source.as_str())){continue;}
        out.push(Question{id:q.id,question:q.question,importance:q.importance,evidence});
    }
    Ok(out)
}

fn extract(endpoint:&str,model:&str,key:&str,client:&reqwest::blocking::Client,units:&[Unit],start:Instant,trace:&mut Vec<Value>)->Result<Vec<Question>,String>{
    let source=super::factual_audit::evidence_sentences(units);
    let mut ranges=Vec::new();let mut begin=0;let mut size=0;
    for(i,unit)in units.iter().enumerate(){let n=unit.text.chars().count();if i>begin&&size+n>1200{ranges.push((begin,i));begin=i;size=0;}size+=n;}
    if begin<units.len(){ranges.push((begin,units.len()));}
    let mut out:Vec<Question>=Vec::new();let mut recovered=false;
    for(index,(begin,end))in ranges.into_iter().enumerate(){
        let window=units[begin.saturating_sub(1)..(end+1).min(units.len())].iter().collect::<Vec<_>>();
        let primary=units[begin..end].iter().map(|u|u.id.as_str()).collect::<HashSet<_>>();
        let primary_ids=units[begin..end].iter().map(|u|u.id.as_str()).collect::<Vec<_>>();
        let wire=window.iter().map(|u|json!({"id":u.id,"sentences":source.iter().filter(|s|s["source"].as_str()==Some(u.id.as_str())).map(|s|json!({"id":s["id"],"text":s["text"]})).collect::<Vec<_>>()})).collect::<Vec<_>>();
        let mut input=json!({"sourceUnits":wire,"primarySourceIds":primary_ids});
        let stage=format!("coverage-source-{index}");
        let raw=super::request(endpoint,model,key,client,SOURCE,input.clone(),false,start,trace,&stage)?;
        let questions=match decode_questions(&raw,&source,&window,&primary){
            Ok(q)=>q,
            Err(_) if !recovered=>{
                recovered=true;input["previousResult"]=json!(raw);
                input["formatProblems"]=json!("仅修复JSON/机器合同：每窗0至4题，每题50字内、至多一个问号，只问primarySourceIds有实质内容的一个核心问题；evidence只能是本窗口现有e编号，最多32个，程序将同单位实际相邻句子原样合为连续证据，最终最多8段，至少一处涉及primary；不能为数量删去分类分支/条件，不抄句子、编编号或跨未引用句子拼接。不要添加新主题或自称通过。");
                let raw=super::request(endpoint,model,key,client,SOURCE,input,false,start,trace,&format!("{stage}-format-recovery"))?;
                decode_questions(&raw,&source,&window,&primary)?
            },
            Err(e)=>return Err(e),
        };
        for mut q in questions {
            if out.iter().any(|old|old.question==q.question&&old.evidence==q.evidence){continue;}
            q.id=format!("q{:02}",out.len());out.push(q);
        }
        if out.len()>40{return Err(fail());}
    }
    if out.is_empty()||!out.iter().any(|q|q.importance=="essential"){return Err(fail());}
    if let Some(last)=trace.last_mut(){last["groundedCoverageQuestions"]=json!(&out);}
    Ok(out)
}

fn summary_units(doc:&Document)->Vec<SummaryUnit>{
    let mut out=Vec::new();
    let mut add=|path:String,text:String,kind:Option<String>|{out.push(SummaryUnit{id:format!("s{:03}",out.len()),path,text,kind});};
    add("purpose".into(),doc.purpose.clone(),None);
    for(i,t)in doc.topics.iter().enumerate(){
        add(format!("topics[{i}].title"),t.title.clone(),None);
        for(j,p)in t.points.iter().enumerate(){add(format!("topics[{i}].points[{j}]"),p.text.clone(),serde_json::to_value(&p.kind).ok().and_then(|v|v.as_str().map(str::to_owned)));}
        for(j,p)in t.details.iter().enumerate(){add(format!("topics[{i}].details[{j}]"),p.text.clone(),None);}
    }
    for(name,rows)in[("decisions",&doc.decisions),("questions",&doc.questions)]{for(i,p)in rows.iter().enumerate(){add(format!("{name}[{i}]"),p.text.clone(),None);}}
    for(i,p)in doc.action_items.iter().enumerate(){
        let mut text=p.text.clone();if let Some(owner)=&p.owner{text.push_str(&format!("；owner：{owner}"));}if let Some(due)=&p.due{text.push_str(&format!("；due：{due}"));}
        add(format!("actionItems[{i}]"),text,None);
    }
    out
}

fn retrieval_parts(raw:&str,questions:&[Question],summary:&[SummaryUnit])->Result<(Vec<Retrieval>,Vec<Question>),String>{
    let data:Retrieved=parse(raw)?;if data.answers.len()>questions.len(){return Err(fail());}
    let expected=questions.iter().map(|q|q.id.as_str()).collect::<HashSet<_>>();let known=summary.iter().map(|s|s.id.as_str()).collect::<HashSet<_>>();let mut seen=HashSet::new();
    let mut valid=Vec::new();let mut invalid=HashSet::new();
    for answer in data.answers {
        if !expected.contains(answer.id.as_str())||!seen.insert(answer.id.clone()){return Err(fail());}
        if answer.summary_ids.len()>8||answer.summary_ids.iter().collect::<HashSet<_>>().len()!=answer.summary_ids.len()
            ||answer.summary_ids.iter().any(|id|!known.contains(id.as_str())){invalid.insert(answer.id);}else{valid.push(answer);}
    }
    let missing=questions.iter().filter(|q|!seen.contains(&q.id)||invalid.contains(&q.id)).cloned().collect();Ok((valid,missing))
}
fn decode_retrieval(raw:&str,questions:&[Question],summary:&[SummaryUnit])->Result<Vec<Retrieval>,String>{
    let(valid,missing)=retrieval_parts(raw,questions,summary)?;if missing.is_empty(){Ok(valid)}else{Err(fail())}
}

fn decode_comparison(raw:&str,questions:&[Question],retrieved:&[Retrieval])->Result<Vec<Check>,String>{
    let data:Compared=parse(raw)?;if data.checks.len()!=questions.len(){return Err(fail());}
    let expected=questions.iter().map(|q|q.id.as_str()).collect::<HashSet<_>>();let witnesses=retrieved.iter().map(|r|(r.id.as_str(),r)).collect::<HashMap<_,_>>();let mut seen=HashSet::new();
    for check in &data.checks {
        let Some(answer)=witnesses.get(check.id.as_str())else{return Err(fail());};
        if !expected.contains(check.id.as_str())||!seen.insert(check.id.as_str())||!matches!(check.result.as_str(),"covered"|"partial"|"missing"|"contradicted")
            ||check.difference.chars().count()>100||check.summary_ids.len()>8||check.summary_ids.iter().any(|id|!answer.summary_ids.contains(id))
            ||check.summary_ids.iter().collect::<HashSet<_>>().len()!=check.summary_ids.len()
            ||check.result=="covered"&&(check.material||check.summary_ids.is_empty())||check.result=="contradicted"&&!check.material{return Err(fail());}
    }
    Ok(data.checks)
}

fn uncertain_source_spans(trace:&[Value],evidence:&[Evidence])->Vec<Value>{
    let mut spans=Vec::new();
    for span in trace.iter().filter_map(|call|call.get("sourceUncertainties").and_then(Value::as_array)).flatten(){
        let Some(text)=span["text"].as_str().filter(|s|!s.trim().is_empty())else{continue;};
        if evidence.iter().any(|e|span["source"].as_str()==Some(e.source.as_str())&&e.quote.contains(text))&&!spans.contains(span){spans.push(span.clone());}
    }
    spans
}
fn evaluate(endpoint:&str,model:&str,key:&str,client:&reqwest::blocking::Client,doc:&Document,questions:&[Question],start:Instant,trace:&mut Vec<Value>,stage:&str,recovered_references:&mut bool)->Result<(Vec<Check>,Vec<SummaryUnit>),String>{
    let summary=summary_units(doc);let asked=questions.iter().map(|q|json!({"id":q.id,"question":q.question})).collect::<Vec<_>>();
    // Neither transcript nor source answers reach this request.
    let raw=super::request(endpoint,model,key,client,RETRIEVE,json!({"summaryUnits":summary,"questions":asked}),false,start,trace,&format!("coverage-retrieve-{stage}"))?;
    let retrieved=match decode_retrieval(&raw,questions,&summary){
        Ok(data)=>data,
        Err(reason)=>{
            let(mut valid,missing)=retrieval_parts(&raw,questions,&summary)?;
            if *recovered_references||missing.is_empty(){return Err(reason);}
            *recovered_references=true;
            // Retrieval is a reference lookup, not a semantic judgment. Keep
            // valid rows immutable and re-query only absent/invalid references
            // once. Unknown IDs never become evidence or a completed answer.
            let asked=missing.iter().map(|q|json!({"id":q.id,"question":q.question})).collect::<Vec<_>>();
            let fixed=super::request(endpoint,model,key,client,RETRIEVE,json!({"summaryUnits":summary,"questions":asked}),false,start,trace,&format!("coverage-retrieve-{stage}-reference-recovery"))?;
            valid.extend(decode_retrieval(&fixed,&missing,&summary)?);valid
        }
    };let known=summary.iter().map(|s|(s.id.as_str(),s)).collect::<HashMap<_,_>>();
    let indexed=retrieved.iter().map(|r|(r.id.as_str(),r)).collect::<HashMap<_,_>>();
    let pairs=questions.iter().map(|q|json!({"id":q.id,"question":q.question,"importance":q.importance,"sourceEvidence":q.evidence,"uncertainSourceSpans":uncertain_source_spans(trace,&q.evidence),"summaryEvidence":indexed[q.id.as_str()].summary_ids.iter().map(|id|known[id.as_str()]).collect::<Vec<_>>()})).collect::<Vec<_>>();
    let raw=super::request(endpoint,model,key,client,COMPARE,json!({"pairs":pairs}),true,start,trace,&format!("coverage-compare-{stage}"))?;
    Ok((decode_comparison(&raw,questions,&retrieved)?,summary))
}

#[derive(Debug,Serialize)]
#[serde(rename_all="camelCase")]
struct AppendSlot {id:String,path:String,label:String,max_characters:usize}
fn append_slots(doc:&Document)->Vec<AppendSlot>{
    let used=doc.topics.iter().flat_map(|t|&t.points).map(|p|p.text.chars().count()).sum::<usize>();
    let main_free=1000usize.saturating_sub(used);let mut slots=Vec::new();
    for(i,t)in doc.topics.iter().enumerate(){
        if main_free>0{for j in t.points.len()..3{slots.push(AppendSlot{id:format!("t{i}p{j}"),path:format!("topics[{i}].points"),label:format!("{} · 主要观点",t.title),max_characters:90.min(main_free)});}}
        for j in t.details.len()..3{slots.push(AppendSlot{id:format!("t{i}d{j}"),path:format!("topics[{i}].details"),label:format!("{} · 补充",t.title),max_characters:120});}
    }
    for(name,n,label)in[("decisions",doc.decisions.len(),"明确共同决定"),("actionItems",doc.action_items.len(),"明确会后任务"),("questions",doc.questions.len(),"明确未决问题")]{
        for j in n..(n+8).min(20){slots.push(AppendSlot{id:format!("{name}{j}"),path:name.into(),label:label.into(),max_characters:180});}
    }
    slots
}

fn append(raw:&str,doc:&Document,allowed:&HashSet<String>,units:&[Unit])->Result<Document,String>{
    let value:Value=parse(raw)?;let root=value.as_object().ok_or_else(fail)?;
    if root.len()!=1{return Err(fail());}let rows=root.get("changes").and_then(Value::as_array).ok_or_else(fail)?;
    if rows.is_empty()||rows.len()>8{return Err(fail());}
    let slots=append_slots(doc);let known=slots.iter().map(|s|(s.id.as_str(),s)).collect::<HashMap<_,_>>();let mut used_slots=HashSet::new();
    let mut value=serde_json::to_value(doc).map_err(|_|fail())?;
    for row in rows {
        let row=row.as_object().ok_or_else(fail)?;
        if row.len()!=3||row.keys().any(|k|!matches!(k.as_str(),"slot"|"questionIds"|"append")){return Err(fail());}
        let ids=row.get("questionIds").and_then(Value::as_array).ok_or_else(fail)?;
        if ids.is_empty()||ids.len()>40||ids.iter().any(|id|id.as_str().map_or(true,|s|!allowed.contains(s))){return Err(fail());}
        let id=row.get("slot").and_then(Value::as_str).ok_or_else(fail)?;
        let slot=known.get(id).ok_or_else(||"追加显示容量：只能选择availableAppendSlots中实际存在的空位".to_string())?;
        if !used_slots.insert(id){return Err("追加显示容量：每个空位编号只能使用一次".into());}
        let path=slot.path.as_str();
        let pointer=if let Some(tail)=path.strip_prefix("topics[") {
            let(index,field)=tail.split_once("].").ok_or_else(fail)?;let index=index.parse::<usize>().map_err(|_|fail())?;
            if index>=doc.topics.len()||!matches!(field,"points"|"details"){return Err(fail());}
            format!("/topics/{index}/{field}")
        }else if matches!(path,"decisions"|"actionItems"|"questions"){format!("/{path}")}else{return Err(fail());};
        let item=row.get("append").and_then(Value::as_object).ok_or_else(fail)?;
        let text=item.get("text").and_then(Value::as_str).ok_or_else(fail)?.trim();
        if text.starts_with('他')||text.starts_with('她'){return Err("新增纪要需使用可确认的人物归属，已有结果保留。".into());}
        if text.chars().count()>slot.max_characters{return Err(format!("追加显示容量：空位{id}每条最多{}字",slot.max_characters));}
        value.pointer_mut(&pointer).and_then(Value::as_array_mut).ok_or_else(fail)?.push(Value::Object(item.clone()));
    }
    let repaired:Document=serde_json::from_value(value).map_err(|_|fail())?;
    let mut capacity=Vec::new();
    for(i,t)in repaired.topics.iter().enumerate(){
        if t.points.len()>3||t.details.len()>3{capacity.push(format!("topics[{i}]最多3条points和3条details，不能向已满数组追加"));}
        if t.points.iter().any(|p|p.text.chars().count()>90)||t.details.iter().any(|p|p.text.chars().count()>120){capacity.push(format!("topics[{i}]的points每条最多90字、details每条最多120字"));}
    }
    if repaired.topics.iter().flat_map(|t|&t.points).map(|p|p.text.chars().count()).sum::<usize>()>1000{capacity.push("全部points总共最多1000字，可把非核心解释放入有空位的details".into());}
    if repaired.decisions.len()>20||repaired.action_items.len()>20||repaired.questions.len()>20
        ||repaired.decisions.iter().chain(&repaired.questions).any(|p|p.text.chars().count()>180)
        ||repaired.action_items.iter().any(|p|p.text.chars().count()>180){capacity.push("决定/任务/未决每数组最多20条、每条180字".into());}
    if !capacity.is_empty(){return Err(format!("追加显示容量：{}",capacity.join("；")));}
    super::validate(&repaired,units)?;
    // Mutation is append-only, including original kind/refs/owner/due metadata.
    let before=serde_json::to_value(doc).map_err(|_|fail())?;let after=serde_json::to_value(&repaired).map_err(|_|fail())?;
    if before["purpose"]!=after["purpose"]||before["topics"].as_array().unwrap().len()!=after["topics"].as_array().unwrap().len(){return Err(fail());}
    for(i,topic)in doc.topics.iter().enumerate(){
        if before["topics"][i]["title"]!=after["topics"][i]["title"]{return Err(fail());}
        for(field,n)in[("points",topic.points.len()),("details",topic.details.len())]{if before["topics"][i][field].as_array().unwrap().as_slice()!=&after["topics"][i][field].as_array().unwrap()[..n]{return Err(fail());}}
    }
    for field in ["decisions","actionItems","questions"]{let original=before[field].as_array().unwrap();if original.as_slice()!=&after[field].as_array().unwrap()[..original.len()]{return Err(fail());}}
    Ok(repaired)
}

#[derive(Debug)]
struct Certificate {witnesses:Vec<(String,Value)>}
fn signature(unit:&SummaryUnit)->Value{json!({"text":unit.text,"kind":unit.kind})}
impl Certificate {
    fn valid(&self,summary:&[SummaryUnit])->bool{self.witnesses.iter().all(|(path,value)|summary.iter().any(|s|&s.path==path&&signature(s)==*value))}
}

pub(super) struct Prepared {questions:Vec<Question>,checks:Vec<Check>,summary:Vec<SummaryUnit>,recovered_references:bool,omission_signature:Option<Value>}
pub(super) fn combine_omissions(mut prepared:Prepared,omissions:Omissions)->Result<Prepared,String>{
    for mut q in omissions.0{
        if prepared.questions.iter().any(|old|old.question==q.question&&old.evidence==q.evidence){continue;}
        if prepared.questions.len()>=40{return Err(fail());}
        q.id=format!("q{:02}",prepared.questions.len());prepared.questions.push(q);
    }
    // Both initial reviewers received this same immutable document. A later
    // factual correction or append invalidates this whole-source certificate.
    prepared.omission_signature=Some(semantic_signature(&prepared.summary));
    Ok(prepared)
}
pub(super) fn prepare(endpoint:&str,model:&str,key:&str,client:&reqwest::blocking::Client,doc:&Document,units:&[Unit],start:Instant,trace:&mut Vec<Value>)->Result<Prepared,String>{
    let questions=extract(endpoint,model,key,client,units,start,trace)?;
    let essential=questions.iter().filter(|q|q.importance=="essential").cloned().collect::<Vec<_>>();
    let mut recovered_references=false;
    let(checks,summary)=evaluate(endpoint,model,key,client,doc,&essential,start,trace,"precheck",&mut recovered_references)?;Ok(Prepared{questions,checks,summary,recovered_references,omission_signature:None})
}
fn semantic_signature(summary:&[SummaryUnit])->Value{json!(summary.iter().map(|s|json!({"path":s.path,"claim":signature(s)})).collect::<Vec<_>>())}
fn seed_certificates(checks:&[Check],summary:&[SummaryUnit])->HashMap<String,Certificate>{
    let known=summary.iter().map(|s|(s.id.as_str(),s)).collect::<HashMap<_,_>>();
    checks.iter().filter(|c|!c.material).map(|c|(c.id.clone(),Certificate{witnesses:c.summary_ids.iter().map(|id|{let s=known[id.as_str()];(s.path.clone(),signature(s))}).collect()})).collect()
}
fn has_complete_seed(questions:&[Question],checks:&[Check])->bool{questions.iter().filter(|q|q.importance=="essential").all(|q|checks.iter().any(|c|c.id==q.id))}
pub(super) fn complete_prepared(endpoint:&str,model:&str,key:&str,client:&reqwest::blocking::Client,doc:&Document,units:&[Unit],prepared:Prepared,start:Instant,trace:&mut Vec<Value>)->Result<Document,String>{
    let Prepared{mut questions,checks,summary,mut recovered_references,mut omission_signature}=prepared;
    let mut certificates=seed_certificates(&checks,&summary);
    // Reuse whole prior comparison only when every semantic claim is identical.
    // Otherwise retain just exact positive witnesses; changed paths and gaps
    // must be compared again after the independent factual correction.
    let complete_seed=has_complete_seed(&questions,&checks);
    let mut initial=(complete_seed&&semantic_signature(&summary)==semantic_signature(&summary_units(doc))).then_some((checks,summary));
    let mut current=doc.clone();let mut attempted=HashSet::new();let mut recovered_capacity=false;
    for round in 0..=2 {
        let current_summary=summary_units(&current);
        let pending=questions.iter().filter(|q|q.importance=="essential"&&!certificates.get(&q.id).is_some_and(|c|c.valid(&current_summary))).cloned().collect::<Vec<_>>();
        let current_signature=semantic_signature(&current_summary);
        let needs_omissions=omission_signature.as_ref()!=Some(&current_signature);
        if pending.is_empty()&&!needs_omissions{return Ok(current);}
        // Check the actual revised body against the complete source while
        // checking the outstanding questions. Neither branch receives the
        // other's answers, and both inherit this job's cancellation/deadline.
        let ready=if round==0{initial.take()}else{None};
        let token=super::current_cancellation();
        // Only validated source uncertainty metadata is context for question
        // comparison. Preserve it across the worker boundary without exposing
        // another reviewer's answers or recording the old calls a second time.
        let uncertainty_context=trace.iter().filter_map(|call|call.get("sourceUncertainties").map(|spans|json!({"sourceUncertainties":spans}))).collect::<Vec<_>>();
        let(compared,omissions)=std::thread::scope(|scope|{
            let compare_token=token.clone();let omissions_token=token;
            let current=&current;let pending=&pending;
            let comparison=scope.spawn(move||{
                let mut calls=uncertainty_context;let context_len=calls.len();let mut recovered=recovered_references;
                let result=if let Some(seed)=ready{Ok(seed)}else if pending.is_empty(){Ok((Vec::new(),summary_units(current)))}else{
                    super::with_parent_job(compare_token,||evaluate(endpoint,model,key,client,current,pending,start,&mut calls,&round.to_string(),&mut recovered))
                };(result,calls.split_off(context_len),recovered)
            });
            let omissions=scope.spawn(move||{
                let mut calls=Vec::new();let result=if needs_omissions{
                    super::with_parent_job(omissions_token,||audit_omissions_at(endpoint,model,key,client,current,units,start,&mut calls,&format!("coverage-source-to-document-final-{round}")))
                }else{Ok(Omissions(Vec::new()))};(result,calls)
            });
            let mut stopped=false;
            while !comparison.is_finished()||!omissions.is_finished(){
                if !stopped&&super::check_current().is_err(){stopped=true;}
                std::thread::sleep(std::time::Duration::from_millis(100));
            }
            (comparison.join().unwrap_or_else(|_|(Err(fail()),Vec::new(),recovered_references)),omissions.join().unwrap_or_else(|_|(Err(fail()),Vec::new())))
        });
        let(compared,calls,recovered)=compared;trace.extend(calls);recovered_references=recovered;
        let(omissions,calls)=omissions;trace.extend(calls);super::check_current()?;
        let(checks,summary)=compared?;let omissions=omissions?;
        if needs_omissions{omission_signature=Some(current_signature);}
        let known=summary.iter().map(|s|(s.id.as_str(),s)).collect::<HashMap<_,_>>();
        let indexed=pending.iter().map(|q|(q.id.as_str(),q)).collect::<HashMap<_,_>>();let mut issues=Vec::new();let mut allowed=HashSet::new();
        for check in checks {
            if !check.material {
                certificates.insert(check.id.clone(),Certificate{witnesses:check.summary_ids.iter().map(|id|{let s=known[id.as_str()];(s.path.clone(),signature(s))}).collect()});
            }else{
                let q=indexed[check.id.as_str()];allowed.insert(q.id.clone());
                issues.push(json!({"id":q.id,"question":q.question,"difference":check.difference,"sourceEvidence":q.evidence,"uncertainSourceSpans":uncertain_source_spans(trace,&q.evidence)}));
            }
        }
        // The full-source reviewer can find a relationship that never entered
        // the question bank. Retain it as an additional grounded question;
        // existing questions and their evidence are never deleted or regraded.
        for mut q in omissions.0{
            let id=if let Some(old)=questions.iter().find(|old|old.question==q.question&&old.evidence==q.evidence){old.id.clone()}else{
                if questions.len()>=40{return Err(fail());}
                q.id=format!("q{:02}",questions.len());let id=q.id.clone();questions.push(q);id
            };
            if allowed.insert(id.clone()){
                let q=questions.iter().find(|q|q.id==id).unwrap();
                issues.push(json!({"id":q.id,"question":q.question,"difference":"完整原文对当前正文的复核发现此具体关系尚未保留","sourceEvidence":q.evidence,"uncertainSourceSpans":uncertain_source_spans(trace,&q.evidence)}));
            }
        }
        if issues.is_empty(){return Ok(current);}
        if round==2||allowed.iter().any(|q|attempted.contains(q)){return Err(fail());}
        let used=current.topics.iter().flat_map(|t|&t.points).map(|p|p.text.chars().count()).sum::<usize>();
        let mut payload=json!({"sourceUnits":units,"previousDocument":current,"coverageProblems":issues,"availableAppendSlots":append_slots(&current),"mainCharactersAvailable":1000usize.saturating_sub(used)});
        let raw=super::request(endpoint,model,key,client,APPEND,payload.clone(),true,start,trace,&format!("coverage-append-{round}"))?;
        let before=current.clone();
        let added=match append(&raw,&current,&allowed,units){
            Ok(doc)=>doc,
            Err(reason) if !recovered_capacity&&reason.starts_with("追加显示容量：")=>{
                // A rejected oversized patch has not changed the document.
                // Recover its machine layout once; all facts still need audit.
                recovered_capacity=true;payload["previousResult"]=json!(raw);payload["formatProblems"]=json!([reason]);
                payload["instruction"]=json!("只修复追加条目的空位/字数容量合同。每项slot必须从availableAppendSlots选一个实际编号，不能自行写path，同一slot不可重复。已有纪要逐字保留；可合并相关遗漏、选择仍有空位的相关主题补充。按mainCharactersAvailable分配主要观点，优先实用核心，不为背景扩写。不得截断条件/否定/自愿，不得编事实；仍只返回changes。");
                let fixed=super::request(endpoint,model,key,client,APPEND,payload,true,start,trace,&format!("coverage-append-{round}-capacity-recovery"))?;
                append(&fixed,&current,&allowed,units)?
            },
            Err(reason)=>return Err(reason),
        };
        // Only changed/new claims need new verdicts; they still see the entire
        // immutable source. Unchanged prior positive evidence is not rerolled.
        current=super::factual_audit::review_and_repair_since(endpoint,model,key,client,&added,units,Some(&before),start,trace)?;
        attempted.extend(allowed);
    }
    Err(fail())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn automatic_brief_internal_audit_question_length_does_not_change_display_or_evidence_limits(){
        let source=super::super::factual_audit::evidence_sentences(&units());
        let question="是否缺校长除教书外需懂管理、财务、人心、心理、营养，具未来/全球/全局观和总设计师职责并整合社会资源？";
        assert_eq!(question.chars().count(),51);
        let raw=json!({"omissions":[{"question":question,"difference":"缺具体角色与资源关系","importance":"essential","evidence":["e0000"]}]});
        assert!(decode_omissions(&raw.to_string(),&source).is_ok());
        let mut bad=raw.clone();bad["omissions"][0]["evidence"]=json!(["e9999"]);assert!(decode_omissions(&bad.to_string(),&source).is_err());
        bad=raw.clone();bad["omissions"][0]["question"]=json!("长".repeat(101));assert!(decode_omissions(&bad.to_string(),&source).is_err());
        bad=raw;bad["omissions"][0]["question"]=json!("谁负责？什么时候完成？");assert!(decode_omissions(&bad.to_string(),&source).is_err());
    }
    fn units()->Vec<Unit>{vec![Unit{id:"u000".into(),text:"预算尚未审批。\n不得先采购。".into()},Unit{id:"u001".into(),text:"王梅承诺周五提交报告。".into()}]}
    fn doc()->Document{serde_json::from_value(json!({"purpose":"确认采购前提","topics":[{"title":"采购","points":[{"kind":"status","text":"预算尚未审批。","sources":["u000"]}],"details":[]}],"decisions":[],"actionItems":[],"questions":[]})).unwrap()}
    #[test]
    fn automatic_brief_reference_recovery_never_accepts_the_invalid_id_or_requeries_valid_rows(){
        let summary=summary_units(&doc());let mut q=Question{id:"q00".into(),question:"预算状态？".into(),importance:"essential".into(),evidence:vec![]};let first=q.clone();q.id="q01".into();q.question="采购条件？".into();let questions=vec![first,q];
        let raw=json!({"answers":[{"id":"q00","summaryIds":["s002"]},{"id":"q01","summaryIds":["s999"]}]});
        let(valid,missing)=retrieval_parts(&raw.to_string(),&questions,&summary).unwrap();assert_eq!(valid.len(),1);assert_eq!(valid[0].id,"q00");assert_eq!(missing.len(),1);assert_eq!(missing[0].id,"q01");assert!(decode_retrieval(&raw.to_string(),&questions,&summary).is_err());
        let missing_raw=json!({"answers":[{"id":"q00","summaryIds":["s002"]}]});assert_eq!(retrieval_parts(&missing_raw.to_string(),&questions,&summary).unwrap().1[0].id,"q01");
        for bad in [json!({"answers":[{"id":"q99","summaryIds":["s002"]}]}),json!({"answers":[],"passed":true})]{assert!(retrieval_parts(&bad.to_string(),&questions,&summary).is_err());}
    }
    #[test]
    fn automatic_brief_source_evidence_coalesces_only_selected_adjacent_exact_sentences(){
        let text=(0..18).map(|i|format!("分类分支{i}的条件。\n")).collect::<String>();
        let u=vec![Unit{id:"u000".into(),text:text.clone()}];let all=super::super::factual_audit::evidence_sentences(&u);let allowed=HashSet::from(["u000"]);
        let ids=all.iter().take(13).map(|s|s["id"].as_str().unwrap().to_string()).collect::<Vec<_>>();let evidence=grounded_evidence(ids.clone(),&all,&allowed).unwrap();
        assert_eq!(evidence.len(),1);assert_eq!(evidence[0].quote,all.iter().take(13).map(|s|s["text"].as_str().unwrap()).collect::<String>());assert!(text.contains(&evidence[0].quote));
        let mut gap=ids;gap.remove(6);let split=grounded_evidence(gap,&all,&allowed).unwrap();assert_eq!(split.len(),2);assert!(!split.iter().any(|e|e.quote.contains("分类分支6的条件")));
        let disjoint=all.iter().step_by(2).map(|s|s["id"].as_str().unwrap().to_string()).collect();assert!(grounded_evidence(disjoint,&all,&allowed).is_err());
        assert!(grounded_evidence(vec!["e9999".into()],&all,&allowed).is_err());
        let other=vec![Unit{id:"u000".into(),text:"第一。第二。".into()},Unit{id:"u001".into(),text:"第三。第四。".into()}];let all=super::super::factual_audit::evidence_sentences(&other);let ids=all.iter().map(|s|s["id"].as_str().unwrap().to_string()).collect();assert_eq!(grounded_evidence(ids,&all,&HashSet::from(["u000","u001"])).unwrap().len(),2);
    }
    #[test]
    fn automatic_brief_precheck_reuses_only_unchanged_positive_semantics(){
        let original=doc();let summary=summary_units(&original);let point=summary.iter().find(|s|s.path=="topics[0].points[0]").unwrap();
        let checks=vec![Check{id:"q00".into(),result:"covered".into(),material:false,difference:String::new(),summary_ids:vec![point.id.clone()]},Check{id:"q01".into(),result:"missing".into(),material:true,difference:"缺采购条件".into(),summary_ids:vec![]}];
        let cached=seed_certificates(&checks,&summary);assert!(cached.contains_key("q00")&&!cached.contains_key("q01"));
        let mut cited=original.clone();cited.topics[0].points[0].sources=vec!["u001".into()];assert_eq!(semantic_signature(&summary),semantic_signature(&summary_units(&cited)));
        let mut changed=original.clone();changed.topics[0].points[0].text="预算已审批。".into();assert!(!cached["q00"].valid(&summary_units(&changed)));assert_ne!(semantic_signature(&summary),semantic_signature(&summary_units(&changed)));
        changed=original.clone();changed.action_items.push(serde_json::from_value(json!({"text":"提交报告","owner":"王梅","due":"周五","sources":["u001"]})).unwrap());assert_ne!(semantic_signature(&summary),semantic_signature(&summary_units(&changed)));
    }
    #[test]
    fn automatic_brief_direct_omissions_preserve_old_questions_and_cannot_be_cached_unchecked(){
        let source=super::super::factual_audit::evidence_sentences(&units());
        let raw=json!({"omissions":[{"question":"采购限制是什么？","difference":"缺不得采购条件","importance":"essential","evidence":["e0001"]}]});
        let omissions=decode_omissions(&raw.to_string(),&source).unwrap();assert_eq!(omissions.0[0].evidence[0].quote,source[1]["text"].as_str().unwrap());
        let old=Question{id:"q00".into(),question:"原背景题？".into(),importance:"supporting".into(),evidence:vec![Evidence{source:"u000".into(),quote:"预算尚未审批。".into()}]};
        let before=serde_json::to_value(&old).unwrap();let prepared=Prepared{questions:vec![old.clone()],checks:vec![],summary:summary_units(&doc()),recovered_references:false,omission_signature:None};
        let combined=combine_omissions(prepared,omissions).unwrap();assert_eq!(serde_json::to_value(&combined.questions[0]).unwrap(),before);assert_eq!(combined.questions[1].id,"q01");assert!(!has_complete_seed(&combined.questions,&combined.checks));
        assert_eq!(combined.omission_signature,Some(semantic_signature(&summary_units(&doc()))));
        let mut changed=doc();changed.topics[0].points[0].text="预算已经批准。".into();
        assert_ne!(combined.omission_signature,Some(semantic_signature(&summary_units(&changed))));
        for bad in [json!({"omissions":[],"passed":true}),json!({"omissions":[{"question":"采购？","difference":"缺条件","importance":"essential","evidence":["e9999"]}]}),json!({"omissions":[{"question":"采购？","difference":"缺条件","importance":"supporting","evidence":["e0001"]}]})]{assert!(decode_omissions(&bad.to_string(),&source).is_err());}
        let full=Prepared{questions:(0..40).map(|i|{let mut q=old.clone();q.id=format!("q{i:02}");q}).collect(),checks:vec![],summary:vec![],recovered_references:false,omission_signature:None};
        assert!(combine_omissions(full,decode_omissions(&raw.to_string(),&source).unwrap()).is_err());
    }
    #[test]
    fn automatic_brief_coverage_uncertainty_is_an_exact_span_not_a_question_waiver(){
        let evidence=vec![Evidence{source:"u000".into(),quote:"某个含混称谓。预算尚未审批，不能采购。".into()}];
        let span=json!({"source":"u000","sentenceId":"e0000","text":"某个含混称谓"});
        let trace=vec![json!({"sourceUncertainties":[span.clone(),span.clone(),{"source":"u001","text":"预算尚未审批"},{"source":"u000","text":"无此原话"}]})];
        assert_eq!(uncertain_source_spans(&trace,&evidence),vec![span]);
        let q=Question{id:"q00".into(),question:"采购前提？".into(),importance:"essential".into(),evidence};
        let retrieval=vec![Retrieval{id:"q00".into(),summary_ids:vec![]}];
        let missing=json!({"checks":[{"id":"q00","result":"missing","material":true,"difference":"仍须保留未审批不能采购的清楚条件","summaryIds":[]}]});
        let decoded=decode_comparison(&missing.to_string(),&[q],&retrieval).unwrap();assert!(decoded[0].material);
    }
    #[test]
    fn automatic_brief_coverage_evidence_uses_only_existing_original_sentence_ids(){
        let u=units();let source=super::super::factual_audit::evidence_sentences(&u);let window=u.iter().collect::<Vec<_>>();let primary=HashSet::from(["u000"]);
        let good=json!({"questions":[{"id":"q00","question":"预算状态？","importance":"essential","evidence":[source[0]["id"]]}]});
        let decoded=decode_questions(&good.to_string(),&source,&window,&primary).unwrap();assert_eq!(decoded[0].evidence[0].quote,source[0]["text"].as_str().unwrap());
        let mut bad=good.clone();bad["questions"][0]["evidence"]=json!(["e9999"]);assert!(decode_questions(&bad.to_string(),&source,&window,&primary).is_err());
        let mut bad=good.clone();bad["questions"][0]["question"]=json!("预算状态？采购状态？");assert!(decode_questions(&bad.to_string(),&source,&window,&primary).is_err());
        let mut context=good;context["questions"][0]["evidence"]=json!([source.last().unwrap()["id"]]);assert!(decode_questions(&context.to_string(),&source,&window,&primary).unwrap().is_empty());
    }
    #[test]
    fn automatic_brief_coverage_append_cannot_rewrite_old_text_or_guess_pronouns(){
        let allowed=HashSet::from(["q00".to_string()]);let old=doc();
        let ok=json!({"changes":[{"questionIds":["q00"],"slot":"t0p1","append":{"kind":"status","text":"原文明确不得先采购。","sources":["u000"]}}]}).to_string();
        let new=append(&ok,&old,&allowed,&units()).unwrap();assert_eq!(new.topics[0].points[0].text,old.topics[0].points[0].text);assert_eq!(new.topics[0].points.len(),2);
        for bad in [json!({"changes":[{"questionIds":["q00"],"path":"topics[0].points[0]","text":"已经审批。"}]}),json!({"changes":[{"questionIds":["q00"],"slot":"t0d0","append":{"text":"她已审批。","sources":["u000"]}}]}),json!({"changes":[{"questionIds":["q99"],"slot":"t0d0","append":{"text":"不可采购。","sources":["u000"]}}]})]{assert!(append(&bad.to_string(),&old,&allowed,&units()).is_err());}
    }
    #[test]
    fn automatic_brief_coverage_slots_exclude_full_arrays_and_cannot_be_reused(){
        let allowed=HashSet::from(["q00".to_string()]);let mut full=doc();
        for text in ["先核对采购前提。","采购有待核对。"]{let mut p=full.topics[0].points[0].clone();p.text=text.into();full.topics[0].points.push(p);}
        assert!(!append_slots(&full).iter().any(|s|s.path=="topics[0].points"));
        let row=json!({"questionIds":["q00"],"slot":"t0d0","append":{"text":"不得先采购。","sources":["u000"]}});
        let duplicate=json!({"changes":[row.clone(),row.clone()]});assert!(append(&duplicate.to_string(),&full,&allowed,&units()).is_err());
        let mut occupied=row.clone();occupied["slot"]=json!("t0p0");assert!(append(&json!({"changes":[occupied]}).to_string(),&full,&allowed,&units()).is_err());
        let changed=append(&json!({"changes":[row]}).to_string(),&full,&allowed,&units()).unwrap();
        assert_eq!(serde_json::to_value(&changed.topics[0].points).unwrap(),serde_json::to_value(&full.topics[0].points).unwrap());assert_eq!(changed.topics[0].details.len(),1);
    }
    #[test]
    fn automatic_brief_coverage_requires_real_summary_witness_and_matching_kind(){
        let summary=summary_units(&doc());let s=summary.iter().find(|s|s.path=="topics[0].points[0]").unwrap();
        let proof=Certificate{witnesses:vec![(s.path.clone(),signature(s))]};assert!(proof.valid(&summary));
        let mut changed=doc();changed.topics[0].points[0].text="预算已经审批。".into();assert!(!proof.valid(&summary_units(&changed)));
        changed=doc();changed.topics[0].points[0].kind=serde_json::from_value(json!("decision")).unwrap();assert!(!proof.valid(&summary_units(&changed)));
        let q=Question{id:"q00".into(),question:"预算状态？".into(),importance:"essential".into(),evidence:vec![]};
        let r=vec![Retrieval{id:"q00".into(),summary_ids:vec![s.id.clone()]}];
        let fake=json!({"checks":[{"id":"q00","result":"covered","material":false,"difference":"","summaryIds":["s999"]}]}).to_string();assert!(decode_comparison(&fake,&[q],&r).is_err());
    }
}
