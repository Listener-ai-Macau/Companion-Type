//! A separate source-only verdict. Neither inventory nor prior review reaches it.
use std::{collections::{HashMap,HashSet},sync::atomic::{AtomicBool,Ordering},time::Instant};
use serde::Deserialize;
use serde_json::{json,Value};
use super::{Document,Unit};

const PROMPT:&str=include_str!("automatic_brief_factual_audit.txt");
const REPAIR:&str=include_str!("automatic_brief_factual_repair.txt");
#[derive(Debug,Clone)]
struct Sentence {id:String,source:String,text:String}
#[derive(Debug,Deserialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
struct Audit {claim_audit:Vec<Claim>,#[serde(rename="type")]format_kind:Option<String>}
#[derive(Debug,Deserialize)]
struct Claim {path:String,status:String,reason:String,evidence:Vec<String>,clarity:Option<String>,#[serde(rename="unclearText")]unclear_text:Option<String>,#[serde(flatten)]echoed:HashMap<String,Value>}

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
pub(super) fn evidence_sentences(units:&[Unit])->Vec<Value> {
    sentences(units).iter().map(|s|json!({"id":s.id,"source":s.source,"text":s.text})).collect()
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
fn emphasize_source_scope(claims:&mut[Value],source:&[Sentence]) {
    let partial=["一些","有些","部分","某些"];
    let qualifiers=["一些","有些","部分","某些","只有","如果","前提","不一定"];
    for claim in claims {
        let Some(ids)=claim.get("sources").and_then(Value::as_array)else{continue;};
        let mut found=source.iter().filter(|s|ids.iter().any(|id|id.as_str()==Some(s.source.as_str()))&&qualifiers.iter().any(|w|s.text.contains(w))).collect::<Vec<_>>();
        found.sort_by_key(|s|(!partial.iter().any(|w|s.text.contains(w)),s.id.as_str()));
        let excerpts=found.into_iter().take(2).map(|s|{
            let chars=s.text.chars().collect::<Vec<_>>();
            let marker=qualifiers.iter().filter_map(|w|s.text.find(w)).min().unwrap_or(0);
            let offset=s.text[..marker].chars().count().saturating_sub(30);
            let text=if chars.len()>100{chars.into_iter().skip(offset).take(100).collect::<String>()}else{s.text.clone()};
            json!({"id":s.id,"text":text})
        }).collect::<Vec<_>>();
        claim["sourceScopeEvidence"]=json!(excerpts);
    }
}
fn decode(raw:&str,expected:&[Value],source:&[Sentence])->Result<Audit,String> {
    decode_contract(raw,expected,source,super::coverage::enabled())
}
fn decode_contract(raw:&str,expected:&[Value],source:&[Sentence],require_clarity:bool)->Result<Audit,String> {
    let mut audit:Audit=serde_json::from_str(super::super::strip_code_fences(raw).trim()).map_err(|_|"纪要内容审核没有返回完整结果，已有结果保留。".to_string())?;
    // Some providers echo the requested JSON format descriptor. It has no
    // semantic authority; any other root field/value still fails closed.
    if audit.format_kind.as_deref().is_some_and(|v|v!="json_object"){return Err("纪要审核格式标记无效，已有结果保留。".into());}
    if audit.claim_audit.len()!=expected.len()||audit.claim_audit.len()>160{return Err("纪要内容审核未覆盖全部陈述，已有结果保留。".into());}
    let paths=expected.iter().map(|v|(v["path"].as_str().unwrap(),v)).collect::<HashMap<_,_>>();
    let evidence=source.iter().filter(|s|!s.text.trim().is_empty()).map(|s|s.id.as_str()).collect::<HashSet<_>>();
    let mut seen=HashSet::new();let mut issues=0;
    for claim in &mut audit.claim_audit {
        let Some(original)=paths.get(claim.path.as_str())else{return Err("纪要审核引用了不存在的陈述，已有结果保留。".into());};
        if !seen.insert(&claim.path)||claim.reason.trim().is_empty()||claim.reason.chars().count()>300
            ||!matches!(claim.status.as_str(),"supported"|"overstated"|"unsupported"|"unclear")
            ||claim.evidence.len()>8||claim.evidence.iter().collect::<HashSet<_>>().len()!=claim.evidence.len()
            ||claim.evidence.iter().any(|s|!evidence.contains(s.as_str()))
            ||(claim.status!="unsupported"&&claim.evidence.is_empty()) {
            return Err("纪要内容审核的依据不完整，已有结果保留。".into());
        }
        // A reviewer may echo supplied claim metadata. Accept only exact
        // echoes, including null owner/due; unknown or changed fields fail.
        if claim.echoed.iter().any(|(key,value)|!matches!(key.as_str(),"kind"|"text"|"sources"|"owner"|"due")||original.get(key)!=Some(value)) {
            return Err("纪要审核的陈述元数据不匹配，已有结果保留。".into());
        }
        match claim.clarity.as_deref(){
            Some("unclear")=>{
                let phrase=claim.unclear_text.as_deref().filter(|s|!s.trim().is_empty()).ok_or("纪要审核未定位含混表达，已有结果保留。")?;
                if phrase.chars().count()>180||!["text","owner","due"].iter().any(|key|original.get(*key).and_then(Value::as_str).is_some_and(|text|text.contains(phrase))){return Err("纪要审核的含混表达不属于本条陈述，已有结果保留。".into());}
                // Literal source support cannot certify a readable meaning.
                // Preserve every existing negative verdict; only veto a pass.
                if claim.status=="supported"{claim.status="unclear".into();}
            },
            Some("clear")=>if claim.unclear_text.as_ref().is_some_and(|s|!s.is_empty()){return Err("纪要审核的清晰性结论不一致，已有结果保留。".into());},
            None if !require_clarity=>if claim.unclear_text.as_ref().is_some_and(|s|!s.is_empty()){return Err("纪要审核缺少清晰性结论，已有结果保留。".into());},
            _=>return Err("纪要审核未分别核对出处和含义，已有结果保留。".into()),
        }
        if claim.status!="supported"{issues+=1;}
    }
    let _=issues;
    Ok(audit)
}
fn readable_negative_paths(raw:&str)->HashSet<String> {
    raw.char_indices().filter(|(_,c)|*c=='{').filter_map(|(i,_)|
        serde_json::Deserializer::from_str(&raw[i..]).into_iter::<Claim>().next().and_then(Result::ok)
    ).filter(|c|matches!(c.status.as_str(),"overstated"|"unsupported"|"unclear")||c.clarity.as_deref()==Some("unclear")).map(|c|c.path).collect()
}
fn preserves_negative_paths(audit:&Audit,negative:&HashSet<String>)->bool {
    negative.iter().all(|path|audit.claim_audit.iter().any(|c|&c.path==path&&c.status!="supported"))
}
fn validate(raw:&str,expected:&[Value],source:&[Sentence])->Result<(),String> {
    let audit=decode(raw,expected,source)?;let issues=audit.claim_audit.iter().filter(|c|c.status!="supported").count();
    if issues>0{Err(format!("纪要仍有{issues}处表述需要核对，本次未发布为完成结果；原文和已有纪要保留。"))}else{Ok(())}
}
fn check_cancellation(token:Option<&super::super::super::meeting_processing_job::Cancellation>)->Result<(),String>{
    if token.is_some_and(|t|t.requested()){return Err(super::super::super::meeting_processing_job::MINUTES_CANCELLED.into());}
    super::super::super::meeting_processing_job::check_current()
}
fn bind_supported_sources(doc:&Document,audit:&Audit,source:&[Sentence],units:&[Unit])->Result<Document,String>{
    let fail=||"纪要原话关联未完成，已有结果保留。".to_string();
    let known=source.iter().map(|s|(s.id.as_str(),s.source.as_str())).collect::<HashMap<_,_>>();
    let mut value=serde_json::to_value(doc).map_err(|_|fail())?;
    for claim in audit.claim_audit.iter().filter(|c|c.status=="supported"){
        let pointer=format!("/{}",claim.path.replace('[',"/").replace(']',"").replace('.',"/"));
        let target=value.pointer_mut(&pointer).ok_or_else(fail)?;
        if target.get("sources").is_none(){continue;}
        let mut refs=Vec::new();
        for id in &claim.evidence{let source=known.get(id.as_str()).ok_or_else(fail)?;if !refs.contains(source){refs.push(*source);}}
        if refs.is_empty()||refs.len()>8{return Err(fail());}
        target.as_object_mut().ok_or_else(fail)?.insert("sources".into(),json!(refs));
    }
    let bound:Document=serde_json::from_value(value).map_err(|_|fail())?;super::validate(&bound,units)?;Ok(bound)
}
fn incomplete_audit(raw:&str,expected:&[Value],source:&[Sentence])->Option<(Audit,Vec<Value>)>{
    let parsed:Audit=serde_json::from_str(super::super::strip_code_fences(raw).trim()).ok()?;
    if parsed.claim_audit.len()>=expected.len(){return None;}
    let paths=parsed.claim_audit.iter().map(|c|c.path.as_str()).collect::<HashSet<_>>();
    let present=expected.iter().filter(|c|paths.contains(c["path"].as_str().unwrap())).cloned().collect::<Vec<_>>();
    // Validate every supplied verdict with the original strict contract. Extra,
    // duplicate, altered or unknown rows cannot enter missing-only recovery.
    let audit=decode(raw,&present,source).ok()?;
    let missing=expected.iter().filter(|c|!paths.contains(c["path"].as_str().unwrap())).cloned().collect::<Vec<_>>();
    Some((audit,missing))
}
fn partitioned_audit(endpoint:&str,model:&str,key:&str,client:&reqwest::blocking::Client,doc:&Document,wire:&Value,expected:&[Value],source:&[Sentence],stage:&str,start:Instant,trace:&mut Vec<Value>,recovered_format:&AtomicBool)->Result<Audit,String>{
    // Each independent batch still sees the complete immutable source and
    // document. Bound concurrency to three; every claim needs a verdict.
    if expected.is_empty(){return Ok(Audit{claim_audit:Vec::new(),format_kind:None});}
    let batches=if super::coverage::enabled(){expected.len().div_ceil(4).clamp(1,3)}else{1};let size=expected.len().div_ceil(batches);
    let token=super::super::super::meeting_processing_job::current();check_cancellation(token.as_ref())?;
    let results=std::thread::scope(|scope|{
        let workers=expected.chunks(size).enumerate().map(|(i,claims)|{
            let token=token.clone();let stage=if batches==1{stage.to_string()}else{format!("{stage}-batch-{i}")};
            scope.spawn(move||{
                let mut calls=Vec::new();
                let result=(||{
                    check_cancellation(token.as_ref())?;
                    let payload=json!({"sourceUnits":wire,"document":doc,"checkClaims":claims});
                    let raw=super::request(endpoint,model,key,client,PROMPT,payload.clone(),true,start,&mut calls,&stage)?;
                    check_cancellation(token.as_ref())?;
                    let incomplete=super::coverage::enabled().then(||incomplete_audit(&raw,claims,source)).flatten();
                    match decode(&raw,claims,source){
                        Ok(audit)=>Ok(audit),
                        Err(_) if incomplete.is_some()&&recovered_format.compare_exchange(false,true,Ordering::AcqRel,Ordering::Acquire).is_ok()=>{
                            let(mut audit,missing)=incomplete.unwrap();
                            let payload=json!({"sourceUnits":wire,"document":doc,"checkClaims":missing});
                            let fixed=super::request(endpoint,model,key,client,PROMPT,payload,true,start,&mut calls,&format!("{stage}-missing-recovery"))?;
                            check_cancellation(token.as_ref())?;
                            // Previously returned positive and negative verdicts
                            // are immutable; only absent paths are requested.
                            audit.claim_audit.extend(decode(&fixed,&missing,source)?.claim_audit);Ok(audit)
                        },
                        Err(_) if serde_json::from_str::<Value>(super::super::strip_code_fences(&raw).trim()).is_err()
                            &&recovered_format.compare_exchange(false,true,Ordering::AcqRel,Ordering::Acquire).is_ok()=>{
                            let negative=readable_negative_paths(&raw);let mut payload=payload;
                            payload["previousMalformedAudit"]=json!(raw);payload["formatProblem"]=json!("上次JSON语法损坏。按相同完整原文和本批陈述修复JSON，不删除已指出的负面结论；仍须逐项核对本批全部陈述，不能只给passed。");
                            check_cancellation(token.as_ref())?;
                            let fixed=super::request(endpoint,model,key,client,PROMPT,payload,true,start,&mut calls,&format!("{stage}-format-recovery"))?;
                            check_cancellation(token.as_ref())?;let audit=decode(&fixed,claims,source)?;
                            if !preserves_negative_paths(&audit,&negative){return Err("纪要审核格式恢复改变了已指出的问题，已有结果保留。".into());}Ok(audit)
                        },
                        Err(error)=>Err(error),
                    }
                })();
                for call in &mut calls{call["parallelAuditBatchCount"]=json!(batches);}
                (result,calls)
            })
        }).collect::<Vec<_>>();
        // Keep the parent callback alive on mobile; JNI callbacks stay on the
        // originating thread while children receive only the atomic token.
        let mut stopped=false;
        while workers.iter().any(|worker|!worker.is_finished()) {
            if !stopped&&check_cancellation(token.as_ref()).is_err(){stopped=true;}
            std::thread::sleep(std::time::Duration::from_millis(100));
        }
        // Join every worker even when one failed; no detached service calls.
        workers.into_iter().map(|worker|worker.join().unwrap_or_else(|_|(Err("纪要审核作业未正常完成，已有结果保留。".into()),Vec::new()))).collect::<Vec<_>>()
    });
    let mut claims=Vec::new();let mut error=None;
    for(result,calls)in results{trace.extend(calls);match result{Ok(audit)=>claims.extend(audit.claim_audit),Err(e)=>if error.is_none(){error=Some(e);}}}
    check_cancellation(token.as_ref())?;
    if let Some(error)=error{return Err(error);}
    if claims.len()!=expected.len(){return Err("纪要审核未覆盖全部陈述，已有结果保留。".into());}
    // Carry only exact, source-bound ambiguous spans into later coverage
    // comparison. They cannot certify an answer or suppress a whole question.
    let uncertain=claims.iter().filter(|c|c.clarity.as_deref()==Some("unclear")).flat_map(|c|{
        let phrase=c.unclear_text.as_deref().unwrap_or("");
        source.iter().filter(move|s|!phrase.is_empty()&&c.evidence.contains(&s.id)&&s.text.contains(phrase))
            .map(move|s|json!({"source":s.source,"sentenceId":s.id,"text":phrase}))
    }).collect::<Vec<_>>();
    if !uncertain.is_empty(){if let Some(call)=trace.last_mut(){call["sourceUncertainties"]=json!(uncertain);}}
    Ok(Audit{claim_audit:claims,format_kind:None})
}
#[cfg(test)]
fn apply_changes(raw:&str,doc:&Document,allowed:&HashSet<String>,unclear:&HashSet<String>,units:&[Unit])->Result<Document,String> {
    apply_changes_with_policy(raw,doc,allowed,unclear,&HashMap::new(),units)
}
fn apply_changes_with_policy(raw:&str,doc:&Document,allowed:&HashSet<String>,unclear:&HashSet<String>,conservative:&HashMap<String,Vec<String>>,units:&[Unit])->Result<Document,String> {
    let fail=||"纪要修正没有遵守受影响范围，已有结果保留。".to_string();
    let changes:Value=serde_json::from_str(super::super::strip_code_fences(raw).trim()).map_err(|_|fail())?;
    let root=changes.as_object().ok_or_else(fail)?;
    if root.len()!=1{return Err(fail());}
    let edits=root.get("changes").and_then(Value::as_array).ok_or_else(fail)?;
    if edits.is_empty()||edits.len()>allowed.len(){return Err(fail());}
    let mut value=serde_json::to_value(doc).map_err(|_|fail())?;let mut seen=HashSet::new();let mut removals=Vec::new();
    for edit in edits {
        let row=edit.as_object().ok_or_else(fail)?;
        if row.keys().any(|k|!matches!(k.as_str(),"path"|"text"|"remove"|"kind"|"owner"|"due"|"delete")){return Err(fail());}
        let path=row.get("path").and_then(Value::as_str).ok_or_else(fail)?;
        if !allowed.contains(path)||!seen.insert(path.to_string()){return Err(fail());}
        let pointer=format!("/{}",path.replace('[',"/").replace(']',"").replace('.',"/"));
        if row.get("remove")==Some(&json!(true)) {
            if row.len()!=2||path=="purpose"||path.ends_with(".title")||value.pointer(&pointer).is_none(){return Err(fail());}
            removals.push(pointer);continue;
        }
        if row.get("remove").is_some_and(|v|v!=&json!(false)){return Err(fail());}
        let target=value.pointer_mut(&pointer).ok_or_else(fail)?;
        if let Some(parts)=row.get("delete") {
            if !unclear.contains(path)||row.len()!=2{return Err(fail());}
            let parts=parts.as_array().ok_or_else(fail)?;if parts.is_empty()||parts.len()>12{return Err(fail());}
            let original=if path=="purpose"||path.ends_with(".title"){target.as_str()}else{target.get("text").and_then(Value::as_str)}.ok_or_else(fail)?;
            let mut shortened=original.to_string();
            for part in parts {let fragment=part.as_str().ok_or_else(fail)?;if fragment.is_empty()||shortened.matches(fragment).count()!=1{return Err(fail());}shortened=shortened.replacen(fragment,"",1);}
            // Deleting all text from an allowed entry has the same meaning as
            // remove:true. Required purpose/title still cannot be removed.
            if shortened.trim().is_empty()&&path!="purpose"&&!path.ends_with(".title"){removals.push(pointer);continue;}
            if path=="purpose"||path.ends_with(".title"){*target=json!(shortened);}else{target.as_object_mut().ok_or_else(fail)?.insert("text".into(),json!(shortened));}
            continue;
        }
        if unclear.contains(path)&&row.contains_key("text") {
            let phrases=conservative.get(path).filter(|phrases|!phrases.is_empty()).ok_or_else(fail)?;
            let text=row["text"].as_str().filter(|s|!s.trim().is_empty()).ok_or_else(fail)?;
            let original=if path=="purpose"||path.ends_with(".title"){target.as_str()}else{target.get("text").and_then(Value::as_str)}.ok_or_else(fail)?;
            if row.len()!=2||phrases.iter().any(|phrase|phrase.is_empty()||!original.contains(phrase)||text.contains(phrase)){return Err(fail());}
        }
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
    review_and_repair_since(endpoint,model,key,client,doc,units,None,start,trace)
}
fn unverified_claims(doc:&Document,verified:Option<&Document>)->Vec<Value> {
    let previous=verified.map(claims).unwrap_or_default().into_iter().map(|claim|(claim["path"].as_str().unwrap().to_string(),claim)).collect::<HashMap<_,_>>();
    claims(doc).into_iter().filter(|claim|previous.get(claim["path"].as_str().unwrap())!=Some(claim)).collect()
}
// The caller keeps the same immutable source and a document just verified in
// this invocation. Unchanged claims retain that evidence; new/changed claims
// still see the complete original source, never a model inventory.
pub(super) fn review_and_repair_since(endpoint:&str,model:&str,key:&str,client:&reqwest::blocking::Client,doc:&Document,units:&[Unit],verified:Option<&Document>,start:Instant,trace:&mut Vec<Value>)->Result<Document,String> {
    let source=sentences(units);
    let wire=json!(units.iter().map(|u|json!({"id":u.id,"sentences":source.iter().filter(|s|s.source==u.id).map(|s|json!({"id":s.id,"text":s.text})).collect::<Vec<_>>()})).collect::<Vec<_>>());
    let mut current=doc.clone();let mut attempted:HashMap<String,String>=HashMap::new();let recovered_format=AtomicBool::new(false);
    let mut verified_claims=verified.map(claims).unwrap_or_default().into_iter().map(|c|(c["path"].as_str().unwrap().to_string(),c)).collect::<HashMap<_,_>>();
    for round in 0..=2 {
        let mut expected=claims(&current).into_iter().filter(|c|verified_claims.get(c["path"].as_str().unwrap())!=Some(c)).collect::<Vec<_>>();
        if expected.is_empty(){return Ok(current);}
        emphasize_source_scope(&mut expected,&source);
        let stage=match round{0=>"source-factual-audit",1=>"source-factual-reaudit",_=>"source-factual-reaudit-2"};
        let audit=partitioned_audit(endpoint,model,key,client,&current,&wire,&expected,&source,stage,start,trace,&recovered_format)?;
        // Bind original jumps to the exact immutable evidence actually checked,
        // rather than retaining an earlier writer's incomplete source list.
        current=bind_supported_sources(&current,&audit,&source,units)?;
        let audited_claims=claims(&current);
        // Retain only exact in-call positive claims. Changed text, kind,
        // refs, owner/due, or shifted array positions are automatically audited.
        for verdict in audit.claim_audit.iter().filter(|c|c.status=="supported") {
            if let Some(claim)=audited_claims.iter().find(|c|c["path"].as_str()==Some(verdict.path.as_str())){verified_claims.insert(verdict.path.clone(),claim.clone());}
        }
        let issues=audit.claim_audit.iter().filter(|c|c.status!="supported").map(|c|json!({"path":c.path,"status":c.status,"clarity":c.clarity,"unclearText":c.unclear_text,"reason":c.reason,"evidence":c.evidence})).collect::<Vec<_>>();
        if issues.is_empty(){return Ok(current);}
        let allowed=audit.claim_audit.iter().filter(|c|c.status!="supported").map(|c|c.path.clone()).collect::<HashSet<_>>();
        // Repeated feedback stops. In the gated coverage candidate, a rewrite
        // that introduced an unclear ASR term gets one conservative repair;
        // it cannot receive another paraphrase or reset the two-repair bound.
        let repeated=audit.claim_audit.iter().filter(|c|c.status!="supported").any(|c|{
            attempted.get(&c.path).is_some_and(|old|!(super::coverage::enabled()&&old!="unclear"&&c.status=="unclear"))
        });
        if round==2||repeated {
            return Err(format!("纪要复审仍有{}处未解决表述，已有结果保留。",issues.len()));
        }
        let unclear=audit.claim_audit.iter().filter(|c|c.status=="unclear"||c.clarity.as_deref()==Some("unclear")).map(|c|c.path.clone()).collect::<HashSet<_>>();
        let conservative=if super::coverage::enabled(){audit.claim_audit.iter().filter(|c|c.clarity.as_deref()==Some("unclear")).filter_map(|c|{
            let phrase=c.unclear_text.as_ref()?;
            audited_claims.iter().find(|claim|claim["path"].as_str()==Some(c.path.as_str()))?
                .get("text")?.as_str()?.contains(phrase).then(||(c.path.clone(),vec![phrase.clone()]))
        }).collect::<HashMap<_,_>>()}else{HashMap::new()};
        let deletion_only=unclear.iter().filter(|path|!conservative.contains_key(*path)).cloned().collect::<HashSet<_>>();
        let repair_contracts=allowed.iter().map(|path|json!({"path":path,"maxCharacters":if path=="purpose"{80}else if path.ends_with(".title"){26}else if path.contains(".points["){90}else if path.contains(".details["){120}else{180},"textOnlyConservative":conservative.contains_key(path)})).collect::<Vec<_>>();
        let stage=if round==0{"source-factual-repair"}else{"source-factual-repair-2"};
        let raw=super::request(endpoint,model,key,client,REPAIR,json!({"sourceUnits":wire,"previousDocument":current,"auditProblems":issues,"deletionOnlyPaths":deletion_only,"conservativeRewritePaths":conservative,"repairContracts":repair_contracts}),super::coverage::enabled(),start,trace,stage)?;
        current=apply_changes_with_policy(&raw,&current,&allowed,&unclear,&conservative,units)?;
        for issue in audit.claim_audit.iter().filter(|c|c.status!="supported"){attempted.insert(issue.path.clone(),issue.status.clone());}
    }
    Err("纪要复审未完成，已有结果保留。".into())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn automatic_brief_parallel_audit_keeps_parent_job_cancellation(){
        use super::super::super::super::meeting_processing_job as job;
        let result=job::run("factual-parallel-test","factual-parallel-job",job::Kind::Minutes,||{
            let token=job::current().unwrap();let(ready_tx,ready_rx)=std::sync::mpsc::channel();let(release_tx,release_rx)=std::sync::mpsc::channel();
            let worker=std::thread::spawn(move||{assert!(check_cancellation(Some(&token)).is_ok());ready_tx.send(()).unwrap();release_rx.recv().unwrap();check_cancellation(Some(&token))});
            ready_rx.recv().unwrap();assert!(job::cancel("factual-parallel-test","factual-parallel-job").unwrap());release_tx.send(()).unwrap();
            assert_eq!(worker.join().unwrap().unwrap_err(),job::MINUTES_CANCELLED);Ok(())
        });
        assert_eq!(result.unwrap_err(),job::MINUTES_CANCELLED);
    }
    #[test]
    fn automatic_brief_original_jump_uses_audited_evidence_without_rewriting_claim(){
        let units=vec![Unit{id:"u000".into(),text:"预算尚未审批。".into()},Unit{id:"u001".into(),text:"校长是学校的总设计师。".into()}];
        let doc:Document=serde_json::from_value(json!({"purpose":"讨论学校治理","topics":[{"title":"校长职责","points":[{"kind":"opinion","text":"校长是学校的总设计师。","sources":["u000"]}],"details":[]}],"decisions":[],"actionItems":[],"questions":[]})).unwrap();
        let mut raw=json!({"claimAudit":[{"path":"topics[0].points[0]","status":"supported","reason":"完整原文第二单位有直接依据","evidence":["e0001"]}]});
        let audit:Audit=serde_json::from_value(raw.clone()).unwrap();let fixed=bind_supported_sources(&doc,&audit,&sentences(&units),&units).unwrap();
        assert_eq!(fixed.topics[0].points[0].sources,vec!["u001"]);assert_eq!(fixed.topics[0].points[0].text,doc.topics[0].points[0].text);assert_eq!(serde_json::to_value(&fixed.topics[0].points[0].kind).unwrap(),serde_json::to_value(&doc.topics[0].points[0].kind).unwrap());
        raw["claimAudit"][0]["status"]=json!("unclear");let negative:Audit=serde_json::from_value(raw).unwrap();
        assert_eq!(bind_supported_sources(&doc,&negative,&sentences(&units),&units).unwrap().topics[0].points[0].sources,doc.topics[0].points[0].sources);
    }
    #[test]
    fn automatic_brief_literal_support_cannot_override_an_unclear_meaning(){
        let units=vec![Unit{id:"u000".into(),text:"希望有一个牵牛单位或联盟来组织。".into()}];
        let expected=vec![json!({"path":"topics[0].points[0]","text":"建议设牵牛单位或联盟。","sources":["u000"]})];
        let good=json!({"type":"json_object","claimAudit":[{"path":"topics[0].points[0]","status":"supported","clarity":"unclear","unclearText":"牵牛单位","reason":"字面出现但具体称谓含混","evidence":["e0000"]}]});
        let source=sentences(&units);let audit=decode_contract(&good.to_string(),&expected,&source,true).unwrap();assert_eq!(audit.claim_audit[0].status,"unclear");
        for bad in [good.clone(),good.clone(),good.clone(),good.clone()].into_iter().enumerate().map(|(i,mut v)|{match i{0=>{v["claimAudit"][0].as_object_mut().unwrap().remove("clarity");},1=>v["claimAudit"][0]["unclearText"]=json!("原文没有这段"),2=>v["type"]=json!("approved"),_=>v["passed"]=json!(true)};v}){assert!(decode_contract(&bad.to_string(),&expected,&source,true).is_err());}
        let malformed=format!("{{\"claimAudit\":[{},",good["claimAudit"][0]);let negative=readable_negative_paths(&malformed);assert!(negative.contains("topics[0].points[0]"));
        let mut erased=good;erased["claimAudit"][0]["clarity"]=json!("clear");erased["claimAudit"][0]["unclearText"]=Value::Null;
        assert!(!preserves_negative_paths(&decode_contract(&erased.to_string(),&expected,&source,true).unwrap(),&negative));
    }
    #[test]
    fn automatic_brief_fact_keeps_only_unchanged_in_call_claims_verified(){
        let original:Document=serde_json::from_value(json!({"purpose":"采购前提","topics":[{"title":"预算","points":[{"kind":"status","text":"预算尚未审批。","sources":["u000"]}],"details":[]}],"decisions":[],"actionItems":[],"questions":[]})).unwrap();
        assert!(unverified_claims(&original,Some(&original)).is_empty());
        let mut next=original.clone();next.topics[0].details.push(serde_json::from_value(json!({"text":"不得先采购。","sources":["u000"]})).unwrap());
        let pending=unverified_claims(&next,Some(&original));assert_eq!(pending.len(),1);assert_eq!(pending[0]["path"],"topics[0].details[0]");
        next.topics[0].points[0].kind=serde_json::from_value(json!("decision")).unwrap();
        let pending=unverified_claims(&next,Some(&original));assert_eq!(pending.len(),2);assert!(pending.iter().any(|p|p["path"]=="topics[0].points[0]"));
    }
    fn source()->Vec<Unit>{vec![Unit{id:"u000".into(),text:"李敏：预算尚未审批。\n\n权限测试未完成，暂不上线。".into()}]}
    fn expected()->Vec<Value>{vec![json!({"path":"purpose","text":"验证后再评估上线"}),json!({"path":"topics[0].points[0]","kind":"status","text":"预算尚未审批"})]}
    fn audit()->Value{json!({"claimAudit":[{"path":"purpose","status":"supported","reason":"原文明确未通过前不上线","evidence":["e0001"]},{"path":"topics[0].points[0]","status":"supported","reason":"原文明确尚未审批","evidence":["e0000"]}]})}
    #[test]
    fn automatic_brief_scope_attention_uses_only_bounded_original_cited_text(){
        let units=vec![Unit{id:"u000".into(),text:"部分常规产品精度已足够，新研发设备仍有差距。如果条件满足再评估。".into()},Unit{id:"u001".into(),text:"另一些无关产品的报告。".into()}];
        let source=sentences(&units);let mut checks=vec![json!({"path":"topics[0].points[0]","text":"产品精度已足够","sources":["u000"]})];
        emphasize_source_scope(&mut checks,&source);
        let quoted=checks[0]["sourceScopeEvidence"].as_array().unwrap();assert_eq!(quoted.len(),2);
        assert!(quoted[0]["text"].as_str().unwrap().contains("部分"));
        for q in quoted {let original=source.iter().find(|s|s.id==q["id"].as_str().unwrap()).unwrap();assert_eq!(original.source,"u000");assert!(original.text.contains(q["text"].as_str().unwrap()));assert!(q["text"].as_str().unwrap().chars().count()<=100);}
    }
    #[test]
    fn automatic_brief_broken_json_recovery_cannot_erase_a_readable_rejection(){
        let mut bad=audit();bad["claimAudit"][0]["status"]=json!("overstated");
        let broken=format!("{{\"claimAudit\":[{},{{\"path\":\"broken",bad["claimAudit"][0]);
        let negative=readable_negative_paths(&broken);assert!(negative.contains("purpose"));
        let accepted=decode(&audit().to_string(),&expected(),&sentences(&source())).unwrap();
        assert!(!preserves_negative_paths(&accepted,&negative));
        let rejected=decode(&bad.to_string(),&expected(),&sentences(&source())).unwrap();
        assert!(preserves_negative_paths(&rejected,&negative));
    }
    #[test]
    fn automatic_brief_missing_audit_recovery_keeps_existing_verdicts(){
        let source=sentences(&source());let expected=expected();let mut partial=audit();partial["claimAudit"].as_array_mut().unwrap().pop();
        partial["claimAudit"][0]["status"]=json!("overstated");
        let(accepted,missing)=incomplete_audit(&partial.to_string(),&expected,&source).unwrap();
        assert_eq!(accepted.claim_audit[0].status,"overstated");assert_eq!(missing,vec![expected[1].clone()]);
        for bad in [json!({"claimAudit":[{"path":"unknown","status":"supported","reason":"假路径","evidence":["e0000"]}]}),json!({"claimAudit":[],"passed":true})]{assert!(incomplete_audit(&bad.to_string(),&expected,&source).is_none());}
    }
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
    fn automatic_brief_fact_echo_keeps_action_owner_due_and_unknown_fields_strict(){
        let expected=vec![json!({"path":"actionItems[0]","text":"提交报告。","owner":"李敏","due":null,"sources":["u000"]})];
        let good=json!({"claimAudit":[{"path":"actionItems[0]","status":"supported","reason":"受控协议响应","evidence":["e0000"],"text":"提交报告。","owner":"李敏","due":null,"sources":["u000"]}]});
        let source=sentences(&source());assert!(decode(&good.to_string(),&expected,&source).is_ok());
        for(key,value)in[("owner",json!("李明")),("owner",Value::Null),("due",json!("周五")),("text",json!("批准报告。")),("sources",json!(["u999"])),("passed",json!(true))]{
            let mut bad=good.clone();bad["claimAudit"][0][key]=value;assert!(decode(&bad.to_string(),&expected,&source).is_err());
        }
    }
    #[test]
    fn automatic_brief_unclear_repair_cannot_invent_a_new_paraphrase(){
        let doc:Document=serde_json::from_value(json!({"purpose":"确认采购前提","topics":[{"title":"审批","points":[{"kind":"status","text":"方案趋势严重，预算尚未审批，不能先采购。","sources":["u000"]}],"details":[]}],"decisions":[],"actionItems":[],"questions":[]})).unwrap();
        let units=vec![Unit{id:"u000".into(),text:"方案那个趋势，预算还没批，不要先采购。".into()}];
        let allowed=HashSet::from(["topics[0].points[0]".to_string()]);
        let fixed=json!({"changes":[{"path":"topics[0].points[0]","delete":["方案趋势严重，"]}]}).to_string();
        assert!(apply_changes(&fixed,&doc,&allowed,&allowed,&units).is_ok());
        let invented=json!({"changes":[{"path":"topics[0].points[0]","text":"方案在趋势上问题严重，预算尚未审批，不能先采购。"}]}).to_string();
        assert!(apply_changes(&invented,&doc,&allowed,&allowed,&units).is_err());
    }
    #[test]
    fn automatic_brief_conservative_repair_requires_an_exact_flagged_phrase_and_text_only(){
        let units=vec![Unit{id:"u000".into(),text:"希望有一个牵牛单位，或者产业联盟来组织。现在仍只是建议。".into()}];
        let doc:Document=serde_json::from_value(json!({"purpose":"讨论协作组织","topics":[{"title":"组织建议","points":[{"kind":"recommendation","text":"建议设牵牛单位或产业联盟来组织。","sources":["u000"]}],"details":[]}],"decisions":[],"actionItems":[],"questions":[]})).unwrap();
        let path="topics[0].points[0]";let allowed=HashSet::from([path.to_string()]);
        let policy=HashMap::from([(path.to_string(),vec!["牵牛单位".to_string()])]);
        let patch=json!({"changes":[{"path":path,"text":"有发言建议由一个组织或产业联盟开展协作。"}]});
        let fixed=apply_changes_with_policy(&patch.to_string(),&doc,&allowed,&allowed,&policy,&units).unwrap();
        let mut expected=doc.clone();expected.topics[0].points[0].text=fixed.topics[0].points[0].text.clone();
        assert_eq!(serde_json::to_value(fixed).unwrap(),serde_json::to_value(expected).unwrap());
        assert!(apply_changes(&patch.to_string(),&doc,&allowed,&allowed,&units).is_err());
        for bad in [json!({"changes":[{"path":path,"text":"牵牛单位仍负责协作。"}]}),json!({"changes":[{"path":path,"text":"开展协作。","kind":"decision"}]}),json!({"changes":[{"path":"purpose","text":"改整场主题"}]})]{
            assert!(apply_changes_with_policy(&bad.to_string(),&doc,&allowed,&allowed,&policy,&units).is_err());
        }
        let invalid_policy=HashMap::from([(path.to_string(),vec!["原句里没有".to_string()])]);
        assert!(apply_changes_with_policy(&patch.to_string(),&doc,&allowed,&allowed,&invalid_policy,&units).is_err());
    }
    #[test]
    fn automatic_brief_exact_deletion_can_remove_an_empty_optional_detail(){
        let doc:Document=serde_json::from_value(json!({"purpose":"采购条件","topics":[{"title":"预算","points":[{"kind":"status","text":"预算未批。","sources":["u000"]}],"details":[{"text":"含糊例子待核对。","sources":["u000"]}]}],"decisions":[],"actionItems":[],"questions":[]})).unwrap();
        let units=vec![Unit{id:"u000".into(),text:"预算还没批。那个例子听不清。".into()}];let allowed=HashSet::from(["topics[0].details[0]".to_string()]);
        let patch=json!({"changes":[{"path":"topics[0].details[0]","delete":["含糊例子待核对。"]}]}).to_string();
        let fixed=apply_changes(&patch,&doc,&allowed,&allowed,&units).unwrap();assert!(fixed.topics[0].details.is_empty());assert_eq!(fixed.topics[0].points[0].text,doc.topics[0].points[0].text);
    }
    #[test]
    fn automatic_brief_exact_whole_entry_deletion_matches_explicit_removal(){
        let doc:Document=serde_json::from_value(json!({"purpose":"采购条件","topics":[{"title":"预算","points":[{"kind":"status","text":"预算未批。","sources":["u000"]},{"kind":"opinion","text":"含糊例子待核对。","sources":["u000"]}],"details":[]}],"decisions":[],"actionItems":[],"questions":[]})).unwrap();
        let units=vec![Unit{id:"u000".into(),text:"预算还没批。那个例子听不清。".into()}];let allowed=HashSet::from(["topics[0].points[1]".to_string()]);
        let exact=json!({"changes":[{"path":"topics[0].points[1]","delete":["含糊例子待核对。"]}]}).to_string();
        let remove=json!({"changes":[{"path":"topics[0].points[1]","remove":true}]}).to_string();
        let a=apply_changes(&exact,&doc,&allowed,&allowed,&units).unwrap();let b=apply_changes(&remove,&doc,&allowed,&allowed,&units).unwrap();
        assert_eq!(serde_json::to_value(&a).unwrap(),serde_json::to_value(&b).unwrap());assert_eq!(a.topics[0].points[0].text,doc.topics[0].points[0].text);
    }
    #[test]
    fn automatic_brief_fact_repair_changes_only_audited_fields(){
        let doc:Document=serde_json::from_value(json!({"purpose":"校长与学校发展","topics":[{"title":"校长作用","points":[{"kind":"opinion","text":"校长影响地方教育。","sources":["u000"]}],"details":[]}],"decisions":[],"actionItems":[],"questions":[]})).unwrap();
        let units=vec![Unit{id:"u000".into(),text:"有嘉宾认为，一位优秀校长会影响当地教育水平。".into()}];
        let allowed=HashSet::from(["topics[0].points[0]".to_string()]);
        let raw=json!({"changes":[{"path":"topics[0].points[0]","text":"有嘉宾认为，一位优秀校长影响地方教育。"}]}).to_string();
        let fixed=apply_changes(&raw,&doc,&allowed,&HashSet::new(),&units).unwrap();assert_eq!(fixed.purpose,doc.purpose);assert_eq!(fixed.topics.len(),1);assert_eq!(fixed.topics[0].points.len(),1);
        assert!(fixed.topics[0].points[0].text.contains("优秀"));
        for patch in [json!({"changes":[{"path":"purpose","text":"改整场主题"}]}),json!({"changes":[{"path":"topics[0].points[0]","sources":["u999"]}]}),json!({"changes":[{"path":"topics[0].points[0]","remove":true}]})] {
            assert!(apply_changes(&patch.to_string(),&doc,&allowed,&HashSet::new(),&units).is_err());
        }
    }
}
