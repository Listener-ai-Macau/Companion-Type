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
struct Questions {questions:Vec<Question>}
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

fn normalized(text:&str)->String{text.chars().filter(|c|!c.is_whitespace()).collect()}

// Recover only original whitespace and exact source spans. A quotation with
// changed characters or an ambiguous occurrence is never silently repaired.
fn ground_quote(quote:&str,units:&[Unit])->Result<Vec<Evidence>,String>{
    if quote.is_empty()||quote.chars().count()>180{return Err(fail());}
    let full=units.iter().map(|u|u.text.as_str()).collect::<String>();
    let mut plain=String::new();let mut starts=HashMap::new();let mut ends=HashMap::new();
    for(i,c)in full.char_indices(){if !c.is_whitespace(){starts.insert(plain.len(),i);plain.push(c);ends.insert(plain.len(),i+c.len_utf8());}}
    let needle=normalized(quote);if needle.is_empty(){return Err(fail());}
    let first=plain.find(&needle).ok_or_else(fail)?;
    let after_first=first+needle.chars().next().unwrap().len_utf8();
    if plain[after_first..].contains(&needle){return Err(fail());}
    let left=*starts.get(&first).ok_or_else(fail)?;let right=*ends.get(&(first+needle.len())).ok_or_else(fail)?;
    let mut offset=0;let mut out=Vec::new();
    for unit in units {
        let end=offset+unit.text.len();let begin=left.max(offset);let stop=right.min(end);
        if begin<stop {out.push(Evidence{source:unit.id.clone(),quote:full[begin..stop].to_string()});}
        offset=end;
    }
    if out.is_empty()||out.iter().any(|e|e.quote.chars().count()>240){return Err(fail());}Ok(out)
}

fn decode_questions(raw:&str,all:&[Unit],window:&[&Unit],primary:&HashSet<&str>)->Result<Vec<Question>,String>{
    let parsed:Questions=parse(raw)?;if parsed.questions.len()>6{return Err(fail());}
    let known=window.iter().map(|u|u.id.as_str()).collect::<HashSet<_>>();
    let local=window.iter().map(|u|u.text.as_str()).collect::<String>();let local=normalized(&local);
    let mut out=Vec::new();
    for mut q in parsed.questions {
        if !super::line(&q.question,50)||q.question.chars().filter(|c|matches!(c,'?'|'？')).count()>1
            ||!matches!(q.importance.as_str(),"essential"|"supporting")||q.evidence.is_empty()||q.evidence.len()>3{return Err(fail());}
        let mut grounded=Vec::new();
        for e in &q.evidence {
            if !known.contains(e.source.as_str())||!local.contains(&normalized(&e.quote)){return Err(fail());}
            for exact in ground_quote(&e.quote,all)?{if !grounded.contains(&exact){grounded.push(exact);}}
        }
        if grounded.len()>6||!grounded.iter().any(|e|primary.contains(e.source.as_str())){return Err(fail());}
        q.evidence=grounded;out.push(q);
    }
    Ok(out)
}

fn extract(endpoint:&str,model:&str,key:&str,client:&reqwest::blocking::Client,units:&[Unit],start:Instant,trace:&mut Vec<Value>)->Result<Vec<Question>,String>{
    let mut ranges=Vec::new();let mut begin=0;let mut size=0;
    for(i,unit)in units.iter().enumerate(){let n=unit.text.chars().count();if i>begin&&size+n>2400{ranges.push((begin,i));begin=i;size=0;}size+=n;}
    if begin<units.len(){ranges.push((begin,units.len()));}
    let mut out:Vec<Question>=Vec::new();let mut recovered=false;
    for(index,(begin,end))in ranges.into_iter().enumerate(){
        let window=units[begin.saturating_sub(1)..(end+1).min(units.len())].iter().collect::<Vec<_>>();
        let primary=units[begin..end].iter().map(|u|u.id.as_str()).collect::<HashSet<_>>();
        let primary_ids=units[begin..end].iter().map(|u|u.id.as_str()).collect::<Vec<_>>();
        let mut input=json!({"sourceUnits":window,"primarySourceIds":primary_ids});
        let stage=format!("coverage-source-{index}");
        let raw=super::request(endpoint,model,key,client,SOURCE,input.clone(),false,start,trace,&stage)?;
        let questions=match decode_questions(&raw,units,&window,&primary){
            Ok(q)=>q,
            Err(_) if !recovered=>{
                recovered=true;input["previousResult"]=json!(raw);
                input["formatProblems"]=json!("仅修复JSON/机器合同：每窗0至6题，每题50字内、至多一个问号，只问primarySourceIds有实质内容的一个核心问题；逐字依据必须在本窗口且至少一处涉及primary，不能换字拼接。不要添加新主题或自称通过。");
                let raw=super::request(endpoint,model,key,client,SOURCE,input,false,start,trace,&format!("{stage}-format-recovery"))?;
                decode_questions(&raw,units,&window,&primary)?
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

fn decode_retrieval(raw:&str,questions:&[Question],summary:&[SummaryUnit])->Result<Vec<Retrieval>,String>{
    let data:Retrieved=parse(raw)?;if data.answers.len()!=questions.len(){return Err(fail());}
    let expected=questions.iter().map(|q|q.id.as_str()).collect::<HashSet<_>>();let known=summary.iter().map(|s|s.id.as_str()).collect::<HashSet<_>>();let mut seen=HashSet::new();
    for answer in &data.answers {
        if !expected.contains(answer.id.as_str())||!seen.insert(answer.id.as_str())||answer.summary_ids.len()>8
            ||answer.summary_ids.iter().collect::<HashSet<_>>().len()!=answer.summary_ids.len()
            ||answer.summary_ids.iter().any(|id|!known.contains(id.as_str())){return Err(fail());}
    }
    Ok(data.answers)
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

fn evaluate(endpoint:&str,model:&str,key:&str,client:&reqwest::blocking::Client,doc:&Document,questions:&[Question],start:Instant,trace:&mut Vec<Value>,round:usize)->Result<(Vec<Check>,Vec<SummaryUnit>),String>{
    let summary=summary_units(doc);let asked=questions.iter().map(|q|json!({"id":q.id,"question":q.question})).collect::<Vec<_>>();
    // Neither transcript nor source answers reach this request.
    let raw=super::request(endpoint,model,key,client,RETRIEVE,json!({"summaryUnits":summary,"questions":asked}),false,start,trace,&format!("coverage-retrieve-{round}"))?;
    let retrieved=decode_retrieval(&raw,questions,&summary)?;let known=summary.iter().map(|s|(s.id.as_str(),s)).collect::<HashMap<_,_>>();
    let indexed=retrieved.iter().map(|r|(r.id.as_str(),r)).collect::<HashMap<_,_>>();
    let pairs=questions.iter().map(|q|json!({"id":q.id,"question":q.question,"importance":q.importance,"sourceEvidence":q.evidence,"summaryEvidence":indexed[q.id.as_str()].summary_ids.iter().map(|id|known[id.as_str()]).collect::<Vec<_>>()})).collect::<Vec<_>>();
    let raw=super::request(endpoint,model,key,client,COMPARE,json!({"pairs":pairs}),true,start,trace,&format!("coverage-compare-{round}"))?;
    Ok((decode_comparison(&raw,questions,&retrieved)?,summary))
}

fn append(raw:&str,doc:&Document,allowed:&HashSet<String>,units:&[Unit])->Result<Document,String>{
    let value:Value=parse(raw)?;let root=value.as_object().ok_or_else(fail)?;
    if root.len()!=1{return Err(fail());}let rows=root.get("changes").and_then(Value::as_array).ok_or_else(fail)?;
    if rows.is_empty()||rows.len()>8{return Err(fail());}
    let mut value=serde_json::to_value(doc).map_err(|_|fail())?;
    for row in rows {
        let row=row.as_object().ok_or_else(fail)?;
        if row.len()!=3||row.keys().any(|k|!matches!(k.as_str(),"path"|"questionIds"|"append")){return Err(fail());}
        let ids=row.get("questionIds").and_then(Value::as_array).ok_or_else(fail)?;
        if ids.is_empty()||ids.len()>40||ids.iter().any(|id|id.as_str().map_or(true,|s|!allowed.contains(s))){return Err(fail());}
        let path=row.get("path").and_then(Value::as_str).ok_or_else(fail)?;
        let pointer=if let Some(tail)=path.strip_prefix("topics[") {
            let(index,field)=tail.split_once("].").ok_or_else(fail)?;let index=index.parse::<usize>().map_err(|_|fail())?;
            if index>=doc.topics.len()||!matches!(field,"points"|"details"){return Err(fail());}
            format!("/topics/{index}/{field}")
        }else if matches!(path,"decisions"|"actionItems"|"questions"){format!("/{path}")}else{return Err(fail());};
        let item=row.get("append").and_then(Value::as_object).ok_or_else(fail)?;
        let text=item.get("text").and_then(Value::as_str).ok_or_else(fail)?.trim();
        if text.starts_with('他')||text.starts_with('她'){return Err("新增纪要需使用可确认的人物归属，已有结果保留。".into());}
        value.pointer_mut(&pointer).and_then(Value::as_array_mut).ok_or_else(fail)?.push(Value::Object(item.clone()));
    }
    let repaired:Document=serde_json::from_value(value).map_err(|_|fail())?;super::validate(&repaired,units)?;
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

pub(super) fn complete(endpoint:&str,model:&str,key:&str,client:&reqwest::blocking::Client,doc:&Document,units:&[Unit],start:Instant,trace:&mut Vec<Value>)->Result<Document,String>{
    let questions=extract(endpoint,model,key,client,units,start,trace)?.into_iter().filter(|q|q.importance=="essential").collect::<Vec<_>>();
    let mut current=doc.clone();let mut certificates:HashMap<String,Certificate>=HashMap::new();let mut attempted=HashSet::new();
    for round in 0..=2 {
        let current_summary=summary_units(&current);
        let pending=questions.iter().filter(|q|!certificates.get(&q.id).is_some_and(|c|c.valid(&current_summary))).cloned().collect::<Vec<_>>();
        if pending.is_empty(){return Ok(current);}
        let(checks,summary)=evaluate(endpoint,model,key,client,&current,&pending,start,trace,round)?;
        let known=summary.iter().map(|s|(s.id.as_str(),s)).collect::<HashMap<_,_>>();
        let indexed=pending.iter().map(|q|(q.id.as_str(),q)).collect::<HashMap<_,_>>();let mut issues=Vec::new();let mut allowed=HashSet::new();
        for check in checks {
            if !check.material {
                certificates.insert(check.id.clone(),Certificate{witnesses:check.summary_ids.iter().map(|id|{let s=known[id.as_str()];(s.path.clone(),signature(s))}).collect()});
            }else{
                let q=indexed[check.id.as_str()];allowed.insert(q.id.clone());
                issues.push(json!({"id":q.id,"question":q.question,"difference":check.difference,"sourceEvidence":q.evidence}));
            }
        }
        if issues.is_empty(){return Ok(current);}
        if round==2||allowed.iter().any(|q|attempted.contains(q)){return Err(fail());}
        let capacity=current.topics.iter().enumerate().map(|(i,t)|json!({"topic":i,"title":t.title,"points":3usize.saturating_sub(t.points.len()),"details":3usize.saturating_sub(t.details.len())})).collect::<Vec<_>>();
        let payload=json!({"sourceUnits":units,"previousDocument":current,"coverageProblems":issues,"appendCapacity":capacity});
        let raw=super::request(endpoint,model,key,client,APPEND,payload,false,start,trace,&format!("coverage-append-{round}"))?;
        let before=current.clone();let added=append(&raw,&current,&allowed,units)?;
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
    fn units()->Vec<Unit>{vec![Unit{id:"u000".into(),text:"预算尚未审批。\n不得先采购。".into()},Unit{id:"u001".into(),text:"王梅承诺周五提交报告。".into()}]}
    fn doc()->Document{serde_json::from_value(json!({"purpose":"确认采购前提","topics":[{"title":"采购","points":[{"kind":"status","text":"预算尚未审批。","sources":["u000"]}],"details":[]}],"decisions":[],"actionItems":[],"questions":[]})).unwrap()}
    #[test]
    fn automatic_brief_coverage_quotes_recover_only_original_whitespace_and_spans(){
        let u=units();let e=ground_quote("预算尚未审批。不得先采购。",&u).unwrap();assert_eq!(e[0].quote,u[0].text);
        let e=ground_quote("不得先采购。王梅承诺周五提交报告。",&u).unwrap();assert_eq!(e.len(),2);assert_eq!(e[0].source,"u000");assert_eq!(e[1].source,"u001");
        assert!(ground_quote("预算已经审批。",&u).is_err());
        let repeated=vec![Unit{id:"u000".into(),text:"预算未批。预算未批。".into()}];assert!(ground_quote("预算未批。",&repeated).is_err());
    }
    #[test]
    fn automatic_brief_coverage_append_cannot_rewrite_old_text_or_guess_pronouns(){
        let allowed=HashSet::from(["q00".to_string()]);let old=doc();
        let ok=json!({"changes":[{"questionIds":["q00"],"path":"topics[0].points","append":{"kind":"status","text":"原文明确不得先采购。","sources":["u000"]}}]}).to_string();
        let new=append(&ok,&old,&allowed,&units()).unwrap();assert_eq!(new.topics[0].points[0].text,old.topics[0].points[0].text);assert_eq!(new.topics[0].points.len(),2);
        for bad in [json!({"changes":[{"questionIds":["q00"],"path":"topics[0].points[0]","text":"已经审批。"}]}),json!({"changes":[{"questionIds":["q00"],"path":"topics[0].details","append":{"text":"她已审批。","sources":["u000"]}}]}),json!({"changes":[{"questionIds":["q99"],"path":"topics[0].details","append":{"text":"不可采购。","sources":["u000"]}}]})]{assert!(append(&bad.to_string(),&old,&allowed,&units()).is_err());}
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
