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

// Model returns only existing sentence IDs. The program retrieves original
// text; the model never has to transcribe or normalize an evidence quotation.
fn decode_questions(raw:&str,all:&[Value],window:&[&Unit],primary:&HashSet<&str>)->Result<Vec<Question>,String>{
    let parsed:Questions=parse(raw)?;if parsed.questions.len()>6{return Err(fail());}
    let local=window.iter().map(|u|u.id.as_str()).collect::<HashSet<_>>();
    let known=all.iter().filter(|s|local.contains(s["source"].as_str().unwrap())).map(|s|(s["id"].as_str().unwrap(),s)).collect::<HashMap<_,_>>();
    let mut out=Vec::new();
    for q in parsed.questions {
        if !super::line(&q.question,50)||q.question.chars().filter(|c|matches!(c,'?'|'？')).count()>1
            ||!matches!(q.importance.as_str(),"essential"|"supporting")||q.evidence.is_empty()||q.evidence.len()>8{return Err(fail());}
        let mut evidence=Vec::new();
        for id in q.evidence {
            let sentence=known.get(id.as_str()).ok_or_else(fail)?;
            let quote=sentence["text"].as_str().ok_or_else(fail)?;if quote.trim().is_empty(){return Err(fail());}
            let exact=Evidence{source:sentence["source"].as_str().unwrap().to_string(),quote:quote.to_string()};
            if !evidence.contains(&exact){evidence.push(exact);}
        }
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
    for(i,unit)in units.iter().enumerate(){let n=unit.text.chars().count();if i>begin&&size+n>2400{ranges.push((begin,i));begin=i;size=0;}size+=n;}
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
                input["formatProblems"]=json!("仅修复JSON/机器合同：每窗0至6题，每题50字内、至多一个问号，只问primarySourceIds有实质内容的一个核心问题；evidence只能是本窗口存在的句子e编号字符串，至少一处涉及primary，不能抄句子、编编号或拼接。不要添加新主题或自称通过。");
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

pub(super) fn complete(endpoint:&str,model:&str,key:&str,client:&reqwest::blocking::Client,doc:&Document,units:&[Unit],start:Instant,trace:&mut Vec<Value>)->Result<Document,String>{
    let questions=extract(endpoint,model,key,client,units,start,trace)?.into_iter().filter(|q|q.importance=="essential").collect::<Vec<_>>();
    let mut current=doc.clone();let mut certificates:HashMap<String,Certificate>=HashMap::new();let mut attempted=HashSet::new();let mut recovered_capacity=false;
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
        let used=current.topics.iter().flat_map(|t|&t.points).map(|p|p.text.chars().count()).sum::<usize>();
        let mut payload=json!({"sourceUnits":units,"previousDocument":current,"coverageProblems":issues,"appendCapacity":capacity,"mainCharactersAvailable":1000usize.saturating_sub(used),"entryCharacterLimits":{"points":90,"details":120,"decisions":180,"actionItems":180,"questions":180}});
        let raw=super::request(endpoint,model,key,client,APPEND,payload.clone(),false,start,trace,&format!("coverage-append-{round}"))?;
        let before=current.clone();
        let added=match append(&raw,&current,&allowed,units){
            Ok(doc)=>doc,
            Err(reason) if !recovered_capacity&&reason.starts_with("追加显示容量：")=>{
                // A rejected oversized patch has not changed the document.
                // Recover its machine layout once; all facts still need audit.
                recovered_capacity=true;payload["previousResult"]=json!(raw);payload["formatProblems"]=json!([reason]);
                payload["instruction"]=json!("只修复追加条目的条数/字数容量合同。已有纪要逐字保留，不追加到容量为0的数组；可合并相关遗漏、用仍有空位的相关主题details。按mainCharactersAvailable分配points，优先保留实用核心，不以补背景凑数。不得截断条件/否定/自愿，不得编事实；仍只返回changes。");
                let fixed=super::request(endpoint,model,key,client,APPEND,payload,false,start,trace,&format!("coverage-append-{round}-capacity-recovery"))?;
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
    fn units()->Vec<Unit>{vec![Unit{id:"u000".into(),text:"预算尚未审批。\n不得先采购。".into()},Unit{id:"u001".into(),text:"王梅承诺周五提交报告。".into()}]}
    fn doc()->Document{serde_json::from_value(json!({"purpose":"确认采购前提","topics":[{"title":"采购","points":[{"kind":"status","text":"预算尚未审批。","sources":["u000"]}],"details":[]}],"decisions":[],"actionItems":[],"questions":[]})).unwrap()}
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
