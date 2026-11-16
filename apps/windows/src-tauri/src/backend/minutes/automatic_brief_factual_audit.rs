//! A separate source-only verdict. Neither inventory nor prior review reaches it.
use std::{collections::{HashMap,HashSet},time::Instant};
use serde::Deserialize;
use serde_json::{json,Value};
use super::{Document,Unit};

const PROMPT:&str=include_str!("automatic_brief_factual_audit.txt");
const REPAIR:&str=include_str!("automatic_brief_factual_repair.txt");
#[derive(Debug,Clone)]
struct Sentence {id:String,source:String,text:String}
#[derive(Debug,Deserialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
struct Audit {claim_audit:Vec<Claim>}
#[derive(Debug,Deserialize)]
#[serde(deny_unknown_fields)]
struct Claim {path:String,status:String,reason:String,evidence:Vec<String>,kind:Option<String>}

fn sentences(units:&[Unit])->Vec<Sentence> {
    let mut out:Vec<Sentence>=Vec::new();
    for unit in units {
        let mut part=String::new();
        for c in unit.text.chars() {
            part.push(c);
            if !matches!(c,'。'|'！'|'？'|'；'|'\n'){continue;}
            if part.trim().is_empty()&&out.last().is_some_and(|s|s.source==unit.id) {
                out.last_mut().unwrap().text.push_str(&part);
            }else{out.push(Sentence{id:format!("e{:04}",out.len()),source:unit.id.clone(),text:part.clone()});}
            part.clear();
        }
        if !part.is_empty(){out.push(Sentence{id:format!("e{:04}",out.len()),source:unit.id.clone(),text:part});}
    }
    out
}
fn claims(doc:&Document)->Vec<Value> {
    let mut out=vec![json!({"path":"purpose","text":doc.purpose})];
    for (i,t) in doc.topics.iter().enumerate() {
        out.push(json!({"path":format!("topics[{i}].title"),"text":t.title}));
        for (j,p) in t.points.iter().enumerate(){out.push(json!({"path":format!("topics[{i}].points[{j}]"),"kind":p.kind,"text":p.text,"sources":p.sources}));}
        for (j,p) in t.details.iter().enumerate(){out.push(json!({"path":format!("topics[{i}].details[{j}]"),"text":p.text,"sources":p.sources}));}
    }
    for (name,items) in [("decisions",&doc.decisions),("questions",&doc.questions)] {
        for (i,p) in items.iter().enumerate(){out.push(json!({"path":format!("{name}[{i}]"),"text":p.text,"sources":p.sources}));}
    }
    for (i,p) in doc.action_items.iter().enumerate(){out.push(json!({"path":format!("actionItems[{i}]"),"text":p.text,"owner":p.owner,"due":p.due,"sources":p.sources}));}
    out
}
fn decode(raw:&str,expected:&[Value],source:&[Sentence])->Result<Audit,String> {
    let audit:Audit=serde_json::from_str(super::super::strip_code_fences(raw).trim()).map_err(|_|"纪要内容审核没有返回完整结果，已有结果保留。".to_string())?;
    if audit.claim_audit.len()!=expected.len()||audit.claim_audit.len()>160{return Err("纪要内容审核未覆盖全部陈述，已有结果保留。".into());}
    let paths=expected.iter().map(|v|(v["path"].as_str().unwrap(),v)).collect::<HashMap<_,_>>();
    let evidence=source.iter().filter(|s|!s.text.trim().is_empty()).map(|s|s.id.as_str()).collect::<HashSet<_>>();
    let mut seen=HashSet::new();let mut issues=0;
    for claim in &audit.claim_audit {
        let Some(original)=paths.get(claim.path.as_str())else{return Err("纪要审核引用了不存在的陈述，已有结果保留。".into());};
        if !seen.insert(&claim.path)||claim.reason.trim().is_empty()||claim.reason.chars().count()>300
            ||!matches!(claim.status.as_str(),"supported"|"overstated"|"unsupported"|"unclear")
            ||claim.evidence.len()>8||claim.evidence.iter().collect::<HashSet<_>>().len()!=claim.evidence.len()
            ||claim.evidence.iter().any(|s|!evidence.contains(s.as_str()))
            ||(claim.status!="unsupported"&&claim.evidence.is_empty()) {
            return Err("纪要内容审核的依据不完整，已有结果保留。".into());
        }
        if claim.kind.as_ref().is_some_and(|k|original.get("kind").and_then(Value::as_str)!=Some(k.as_str())) {
            return Err("纪要审核的陈述类型不匹配，已有结果保留。".into());
        }
        if claim.status!="supported"{issues+=1;}
    }
    let _=issues;
    Ok(audit)
}
fn validate(raw:&str,expected:&[Value],source:&[Sentence])->Result<(),String> {
    let audit=decode(raw,expected,source)?;let issues=audit.claim_audit.iter().filter(|c|c.status!="supported").count();
    if issues>0{Err(format!("纪要仍有{issues}处表述需要核对，本次未发布为完成结果；原文和已有纪要保留。"))}else{Ok(())}
}
fn apply_changes(raw:&str,doc:&Document,allowed:&HashSet<String>,units:&[Unit])->Result<Document,String> {
    let fail=||"纪要修正没有遵守受影响范围，已有结果保留。".to_string();
    let changes:Value=serde_json::from_str(super::super::strip_code_fences(raw).trim()).map_err(|_|fail())?;
    let root=changes.as_object().ok_or_else(fail)?;
    if root.len()!=1{return Err(fail());}
    let edits=root.get("changes").and_then(Value::as_array).ok_or_else(fail)?;
    if edits.is_empty()||edits.len()>allowed.len(){return Err(fail());}
    let mut value=serde_json::to_value(doc).map_err(|_|fail())?;let mut seen=HashSet::new();let mut removals=Vec::new();
    for edit in edits {
        let row=edit.as_object().ok_or_else(fail)?;
        if row.keys().any(|k|!matches!(k.as_str(),"path"|"text"|"remove"|"kind"|"owner"|"due")){return Err(fail());}
        let path=row.get("path").and_then(Value::as_str).ok_or_else(fail)?;
        if !allowed.contains(path)||!seen.insert(path.to_string()){return Err(fail());}
        let pointer=format!("/{}",path.replace('[',"/").replace(']',"").replace('.',"/"));
        if row.get("remove")==Some(&json!(true)) {
            if row.len()!=2||path=="purpose"||path.ends_with(".title")||value.pointer(&pointer).is_none(){return Err(fail());}
            removals.push(pointer);continue;
        }
        if row.get("remove").is_some_and(|v|v!=&json!(false)){return Err(fail());}
        let target=value.pointer_mut(&pointer).ok_or_else(fail)?;
        if let Some(text)=row.get("text") {
            if !text.is_string(){return Err(fail());}
            if path=="purpose"||path.ends_with(".title"){*target=text.clone();}else{target.as_object_mut().ok_or_else(fail)?.insert("text".into(),text.clone());}
        }
        for field in ["kind","owner","due"] {
            if let Some(v)=row.get(field) {
                if field=="kind"&&!path.contains(".points[")||field!="kind"&&!path.starts_with("actionItems["){return Err(fail());}
                target.as_object_mut().ok_or_else(fail)?.insert(field.into(),v.clone());
            }
        }
        if !row.contains_key("text")&&!row.contains_key("kind")&&!row.contains_key("owner")&&!row.contains_key("due"){return Err(fail());}
    }
    // Apply deletions after replacements and in descending array-index order.
    removals.sort_by(|a,b|{
        let (ap,ai)=a.rsplit_once('/').unwrap();let (bp,bi)=b.rsplit_once('/').unwrap();
        bp.cmp(ap).then_with(||bi.parse::<usize>().unwrap_or(0).cmp(&ai.parse::<usize>().unwrap_or(0)))
    });
    for pointer in removals {
        let(parent,index)=pointer.rsplit_once('/').ok_or_else(fail)?;let i=index.parse::<usize>().map_err(|_|fail())?;
        let list=value.pointer_mut(parent).and_then(Value::as_array_mut).ok_or_else(fail)?;
        if i>=list.len(){return Err(fail());}list.remove(i);
    }
    if let Some(topics)=value.get_mut("topics").and_then(Value::as_array_mut){topics.retain(|t|t.get("points").and_then(Value::as_array).is_some_and(|p|!p.is_empty()));}
    let repaired:Document=serde_json::from_value(value).map_err(|_|fail())?;super::validate(&repaired,units)?;Ok(repaired)
}
pub(super) fn review_and_repair(endpoint:&str,model:&str,key:&str,client:&reqwest::blocking::Client,doc:&Document,units:&[Unit],start:Instant,trace:&mut Vec<Value>)->Result<Document,String> {
    let source=sentences(units);
    let wire=units.iter().map(|u|json!({"id":u.id,"sentences":source.iter().filter(|s|s.source==u.id).map(|s|json!({"id":s.id,"text":s.text})).collect::<Vec<_>>()})).collect::<Vec<_>>();
    let mut current=doc.clone();let mut attempted=HashSet::new();
    for round in 0..=2 {
        let expected=claims(&current);
        let stage=match round{0=>"source-factual-audit",1=>"source-factual-reaudit",_=>"source-factual-reaudit-2"};
        let raw=super::request(endpoint,model,key,client,PROMPT,json!({"sourceUnits":wire,"document":current,"checkClaims":expected}),true,start,trace,stage)?;
        let audit=decode(&raw,&expected,&source)?;
        let issues=audit.claim_audit.iter().filter(|c|c.status!="supported").map(|c|json!({"path":c.path,"status":c.status,"reason":c.reason,"evidence":c.evidence})).collect::<Vec<_>>();
        if issues.is_empty(){return Ok(current);}
        let allowed=audit.claim_audit.iter().filter(|c|c.status!="supported").map(|c|c.path.clone()).collect::<HashSet<_>>();
        // A second repair is allowed only for newly detected paths. Repeated
        // unresolved feedback stops immediately; never reroll until accepted.
        if round==2||allowed.iter().any(|p|attempted.contains(p)) {
            validate(&raw,&expected,&source)?;
            return Err("纪要复审仍有未解决表述，已有结果保留。".into());
        }
        let stage=if round==0{"source-factual-repair"}else{"source-factual-repair-2"};
        let raw=super::request(endpoint,model,key,client,REPAIR,json!({"sourceUnits":wire,"previousDocument":current,"auditProblems":issues}),false,start,trace,stage)?;
        current=apply_changes(&raw,&current,&allowed,units)?;attempted.extend(allowed);
    }
    Err("纪要复审未完成，已有结果保留。".into())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn source()->Vec<Unit>{vec![Unit{id:"u000".into(),text:"李敏：预算尚未审批。\n\n权限测试未完成，暂不上线。".into()}]}
    fn expected()->Vec<Value>{vec![json!({"path":"purpose","text":"验证后再评估上线"}),json!({"path":"topics[0].points[0]","kind":"status","text":"预算尚未审批"})]}
    fn audit()->Value{json!({"claimAudit":[{"path":"purpose","status":"supported","reason":"原文明确未通过前不上线","evidence":["e0001"]},{"path":"topics[0].points[0]","status":"supported","reason":"原文明确尚未审批","evidence":["e0000"]}]})}
    #[test]
    fn automatic_brief_fact_sentence_projection_keeps_all_source_bytes(){
        let units=source();let split=sentences(&units);assert_eq!(split.iter().map(|s|s.text.as_str()).collect::<String>(),units[0].text);
        assert_eq!(split[1].text,"权限测试未完成，暂不上线。");
    }
    #[test]
    fn automatic_brief_fact_requires_all_claims_and_real_evidence(){
        let mut v=audit();assert!(validate(&v.to_string(),&expected(),&sentences(&source())).is_ok());
        v["claimAudit"][0]["evidence"]=json!(["e9999"]);assert!(validate(&v.to_string(),&expected(),&sentences(&source())).is_err());
        let mut v=audit();v["claimAudit"][0]["path"]=json!("topics[0].points[0]");assert!(validate(&v.to_string(),&expected(),&sentences(&source())).is_err());
        let mut v=audit();v["claimAudit"].as_array_mut().unwrap().pop();assert!(validate(&v.to_string(),&expected(),&sentences(&source())).is_err());
    }
    #[test]
    fn automatic_brief_fact_blocks_semantic_issues_and_cannot_be_overridden_by_passed(){
        for verdict in ["overstated","unsupported","unclear"] {
            let mut v=audit();v["claimAudit"][0]["status"]=json!(verdict);assert!(validate(&v.to_string(),&expected(),&sentences(&source())).is_err());
        }
        let mut v=audit();v["passed"]=json!(true);assert!(validate(&v.to_string(),&expected(),&sentences(&source())).is_err());
        let mut v=audit();v["claimAudit"][0]["evidence"]=json!([]);assert!(validate(&v.to_string(),&expected(),&sentences(&source())).is_err());
    }
    #[test]
    fn automatic_brief_fact_only_accepts_a_matching_optional_kind_echo(){
        let mut v=audit();v["claimAudit"][1]["kind"]=json!("status");assert!(validate(&v.to_string(),&expected(),&sentences(&source())).is_ok());
        v["claimAudit"][1]["kind"]=json!("decision");assert!(validate(&v.to_string(),&expected(),&sentences(&source())).is_err());
    }
    #[test]
    fn automatic_brief_fact_repair_changes_only_audited_fields(){
        let doc:Document=serde_json::from_value(json!({"purpose":"校长与学校发展","topics":[{"title":"校长作用","points":[{"kind":"opinion","text":"校长影响地方教育。","sources":["u000"]}],"details":[]}],"decisions":[],"actionItems":[],"questions":[]})).unwrap();
        let units=vec![Unit{id:"u000".into(),text:"有嘉宾认为，一位优秀校长会影响当地教育水平。".into()}];
        let allowed=HashSet::from(["topics[0].points[0]".to_string()]);
        let raw=json!({"changes":[{"path":"topics[0].points[0]","text":"有嘉宾认为，一位优秀校长影响地方教育。"}]}).to_string();
        let fixed=apply_changes(&raw,&doc,&allowed,&units).unwrap();assert_eq!(fixed.purpose,doc.purpose);assert_eq!(fixed.topics.len(),1);assert_eq!(fixed.topics[0].points.len(),1);
        assert!(fixed.topics[0].points[0].text.contains("优秀"));
        for patch in [json!({"changes":[{"path":"purpose","text":"改整场主题"}]}),json!({"changes":[{"path":"topics[0].points[0]","sources":["u999"]}]}),json!({"changes":[{"path":"topics[0].points[0]","remove":true}]})] {
            assert!(apply_changes(&patch.to_string(),&doc,&allowed,&units).is_err());
        }
    }
}
