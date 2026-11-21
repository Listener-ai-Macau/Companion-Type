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
struct Claim {path:String,status:String,reason:String,evidence:Vec<String>,clarity:Option<String>,#[serde(rename="unclearText")]unclear_text:Option<String>,#[serde(rename="placementUnsupported")]placement_unsupported:Option<bool>,#[serde(flatten)]echoed:HashMap<String,Value>}

fn source_wording_unclear(claim: &Claim) -> bool {
    if super::source_items::enabled() {
        // Clarity flags can identify a missing subject or a misleading title.
        // Only source uncertainty forbids reusing the exact words.
        return claim.status == "unclear";
    }
    claim.clarity.as_deref() == Some("unclear")
}

fn independent_path(path:&str)->bool {
    ["decisions[","actionItems[","questions["].iter().any(|prefix|path.starts_with(prefix))
}

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
pub(in crate::backend::minutes) fn evidence_sentences(units:&[Unit])->Vec<Value> {
    sentences(units).iter().map(|s|json!({"id":s.id,"source":s.source,"text":s.text})).collect()
}
pub(super) fn claims(doc:&Document)->Vec<Value> {
    let mut out=vec![json!({"path":"purpose","text":doc.purpose})];
    for (i,t) in doc.topics.iter().enumerate() {
        out.push(json!({"path":format!("topics[{i}].title"),"text":t.title}));
        for (j,p) in t.points.iter().enumerate(){out.push(json!({"path":format!("topics[{i}].points[{j}]"),"kind":p.kind,"text":p.text,"sources":p.sources}));}
        for (j,p) in t.details.iter().enumerate(){out.push(json!({"path":format!("topics[{i}].details[{j}]"),"text":p.text,"sources":p.sources}));}
    }
    for (name,items) in [("decisions",&doc.decisions),("questions",&doc.questions)] {
        for (i,p) in items.iter().enumerate(){
            let mut item=json!({"path":format!("{name}[{i}]"),"text":p.text,"sources":p.sources});
            if super::source_items::enabled(){item["kind"]=json!(if name=="decisions"{"decision"}else{"unresolved"});}
            out.push(item);
        }
    }
    for (i,p) in doc.action_items.iter().enumerate(){
        let mut item=json!({"path":format!("actionItems[{i}]"),"text":p.text,"owner":p.owner,"due":p.due,"sources":p.sources});
        if super::source_items::enabled(){item["kind"]=json!("action");}
        out.push(item);
    }
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
    let audit = decode_contract(raw,expected,source,super::coverage::enabled())?;
    if super::source_items::enabled() && audit.claim_audit.iter().any(|claim| {
        independent_path(&claim.path) && claim.placement_unsupported.is_none()
    }) {
        return Err("纪要审查缺少决定、交办或未决栏目的独立判定，已有结果保留。".into());
    }
    Ok(audit)
}
pub(super) fn canonical_sentence_reference(id:&str,known:&HashSet<&str>)->Option<String>{
    if known.contains(id){return Some(id.into());}
    // Provider output sometimes drops padding from a generated e0004 label.
    // Resolve only that representation to an actually supplied sentence; never
    // invent a source, choose a nearby ID, or interpret a positional reference.
    let digits=id.strip_prefix('e')?;
    if digits.is_empty()||digits.len()>=4||!digits.bytes().all(|c|c.is_ascii_digit()){return None;}
    let number=digits.parse::<u16>().ok()?;let canonical=format!("e{number:04}");
    known.contains(canonical.as_str()).then_some(canonical)
}
fn cited_unclear_phrase(phrase: &str, original: &Value) -> Option<String> {
    if phrase.chars().count() > 180 {
        return None;
    }
    if ["text", "owner", "due"].into_iter().any(|key| {
        original[key].as_str().is_some_and(|text| text.contains(phrase))
    }) {
        return Some(phrase.to_owned());
    }
    // Reviewers occasionally use the source's noun phrase, while the draft
    // spells it with a possessive particle. Bind only a unique exact phrase
    // in prose. Names and due dates must still match their actual fields.
    let text = original["text"].as_str()?;
    if phrase.chars().count() < 4 {
        return None;
    }
    let mut matches = phrase.char_indices().skip(1)
        .map(|(index, _)| format!("{}的{}", &phrase[..index], &phrase[index..]))
        .filter(|candidate| text.match_indices(candidate.as_str()).count() == 1);
    let candidate = matches.next()?;
    matches.all(|other| other == candidate).then_some(candidate)
}

#[cfg(test)]
#[test]
fn unclear_prose_can_bind_one_possessive_particle_but_due_cannot() {
    assert_eq!(cited_unclear_phrase("发展背景", &json!({"text":"作为以后发展的背景。"})).as_deref(), Some("发展的背景"));
    assert!(cited_unclear_phrase("具体时间", &json!({"text":"开会","due":"具体的时间"})).is_none());
    assert!(cited_unclear_phrase("发展背景", &json!({"text":"发展的背景和发展的背景"})).is_none());
    assert!(cited_unclear_phrase("发展背景", &json!({"text":"发展潜力"})).is_none());
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
        if claim.placement_unsupported==Some(true)
            && (!independent_path(&claim.path)||claim.status=="supported") {
            return Err("纪要审查的栏目判定与事实判定不一致，已有结果保留。".into());
        }
        if require_clarity{for id in &mut claim.evidence{if let Some(canonical)=canonical_sentence_reference(id,&evidence){*id=canonical;}}}
        if !seen.insert(&claim.path)||claim.reason.trim().is_empty()||claim.reason.chars().count()>300
            ||!matches!(claim.status.as_str(),"supported"|"overstated"|"unsupported"|"unclear")
            ||claim.evidence.len()>8||claim.evidence.iter().collect::<HashSet<_>>().len()!=claim.evidence.len()
            ||claim.evidence.iter().any(|s|!evidence.contains(s.as_str()))
            ||(claim.status!="unsupported"&&claim.evidence.is_empty()) {
            return Err("纪要内容审核的依据不完整，已有结果保留。".into());
        }
        // A reviewer may echo supplied claim metadata. Accept only exact
        // echoes, including null owner/due; unknown or changed fields fail.
        if claim.echoed.iter().any(|(key,value)|!matches!(key.as_str(),"kind"|"text"|"sources"|"owner"|"due"|"sourceScopeEvidence"|"relatedUncertainty")||original.get(key)!=Some(value)) {
            return Err("纪要审核的陈述元数据不匹配，已有结果保留。".into());
        }
        match claim.clarity.as_deref(){
            Some("unclear")=>{
                let phrase=claim.unclear_text.as_deref().filter(|s|!s.trim().is_empty()).ok_or("纪要审核未定位含混表达，已有结果保留。")?;
                claim.unclear_text = Some(cited_unclear_phrase(phrase, original)
                    .ok_or("纪要审核的含混表达不属于本条陈述，已有结果保留。")?);
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
    super::check_current()
}
fn bind_supported_sources(doc:&Document,audit:&Audit,source:&[Sentence],units:&[Unit])->Result<Document,String>{
    let fail=||"纪要原话关联未完成，已有结果保留。".to_string();
    let known=source.iter().map(|s|(s.id.as_str(),s.source.as_str())).collect::<HashMap<_,_>>();
    let unit_text = units.iter().map(|unit| (unit.id.as_str(), super::normalized(&unit.text)))
        .collect::<HashMap<_, _>>();
    let mut value=serde_json::to_value(doc).map_err(|_|fail())?;
    for claim in audit.claim_audit.iter().filter(|c|c.status=="supported"){
        let pointer=format!("/{}",claim.path.replace('[',"/").replace(']',"").replace('.',"/"));
        let target=value.pointer_mut(&pointer).ok_or_else(fail)?;
        if target.get("sources").is_none(){continue;}
        let mut refs=Vec::new();
        for id in &claim.evidence{let source=known.get(id.as_str()).ok_or_else(fail)?;if !refs.contains(source){refs.push(*source);}}
        if claim.path.starts_with("actionItems[") {
            // A factual verdict can cite the execution phrase alone. A
            // different source unit may already bind its owner or deadline.
            for field in ["owner", "due"].into_iter().filter_map(|key| target[key].as_str()) {
                let field = super::normalized(field);
                let supports = |id: &str| unit_text.get(id).is_some_and(|text| text.contains(&field));
                if refs.iter().any(|id| supports(id)) {
                    continue;
                }
                let anchor = target["sources"].as_array().ok_or_else(fail)?.iter()
                    .filter_map(Value::as_str).find(|id| supports(id)).ok_or_else(fail)?;
                refs.push(anchor);
            }
        }
        if refs.is_empty()||refs.len()>8{return Err(fail());}
        let bound_refs = json!(refs);
        target.as_object_mut().ok_or_else(fail)?.insert("sources".into(),bound_refs);
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

fn batch_audit_reply<'a>(raw: &'a str, expected: &[Value]) -> (std::borrow::Cow<'a, str>, usize) {
    let Ok(mut result) = serde_json::from_str::<Value>(super::super::strip_code_fences(raw).trim()) else {
        return (raw.into(), 0);
    };
    let Some(rows) = result["claimAudit"].as_array_mut() else { return (raw.into(), 0); };
    let paths: HashSet<_> = expected.iter().filter_map(|claim| claim["path"].as_str()).collect();
    let before = rows.len();
    // Only this request's verdicts can influence this batch. Missing,
    // duplicate and invalid requested rows still go through the strict decoder.
    rows.retain(|row| row["path"].as_str().is_none_or(|path| paths.contains(path)));
    let ignored = before - rows.len();
    if ignored == 0 { (raw.into(), 0) } else { (result.to_string().into(), ignored) }
}

#[cfg(test)]
#[test]
fn batch_projection_keeps_required_duplicates_visible_to_the_decoder() {
    let raw = r#"{"claimAudit":[{"path":"purpose"},{"path":"decisions[0]"},{"path":"purpose"}]}"#;
    let (scoped, ignored) = batch_audit_reply(raw, &[json!({"path":"purpose"})]);
    assert_eq!(ignored, 1);
    let scoped: Value = serde_json::from_str(&scoped).unwrap();
    assert_eq!(scoped["claimAudit"], json!([{"path":"purpose"},{"path":"purpose"}]));
}

fn partitioned_audit(endpoint:&str,model:&str,key:&str,client:&reqwest::blocking::Client,doc:&Document,wire:&Value,expected:&[Value],source:&[Sentence],stage:&str,start:Instant,trace:&mut Vec<Value>,recovered_format:&AtomicBool)->Result<Audit,String>{
    // Each independent batch still sees the complete immutable source and
    // document. Bound concurrency to three; every claim needs a verdict.
    if expected.is_empty(){return Ok(Audit{claim_audit:Vec::new(),format_kind:None});}
    let mut role_prompt;
    let prompt = if super::source_items::enabled() {
        role_prompt = format!("{PROMPT}\n栏目本身也是需要单独核对的主张。对decisions、actionItems、questions的每一条，另外返回placementUnsupported布尔值。真有本场定案、会后承诺或指派、尚未解决的问题时填false；当其实只是开场目的、个人设想、举例、建议、现场已经回答的疑问或散会提示时填true，并将status判为overstated、unsupported或unclear。文字有原话不代表栏目正确。只写错截止日期、责任人或数值但栏目确实成立时填false，按独立事实问题判status。其他栏目无须此字段。");
        if expected.iter().any(|claim| claim.get("relatedUncertainty").is_some()) {
            role_prompt.push_str("\nrelatedUncertainty 指向同一数值在另一条陈述中已发现的原文疑点。核对这一条表达的是较早的明确建议还是已确定的结果。可保留独立原话支持的建议及其归属、时序。若本条仍把同一含混数值写为已定案，判unclear，unclearText填本条实际出现的数值，引用原话。");
        }
        if expected.iter().any(|claim| claim.get("competingSourceIds").is_some()) {
            role_prompt.push_str("\ncompetingSourceIds 是从原文反查提出的候选冲突。逐个看这些原话及邻句，并对照当前条目出处。能分清早期提议和后来明确否定时保留先后。原话确实冲突而无法确定时标为含混；不能原样保留一个无条件版本。候选提示本身也要核实。");
        }
        if expected.iter().any(|claim| claim["text"].as_str().is_some_and(|text| {
            text.starts_with("会上提到「") && text.ends_with("」，具体所指待核实。")
        })) {
            role_prompt.push_str("\n主题中「会上提到……具体所指待核实」只报告原话及记录上的疑点。核对引语是否原文、所指是否确实没有确证。若引语是原文且原话所指未明，可以 supported；不要求会议发言者当时明确提问。若上下文已清楚说明所指或引语偏离原话，正常判错。");
        }
        role_prompt.as_str()
    } else {
        PROMPT
    };
    let batches = if super::source_items::enabled() {
        // With a fuller brief, sending all claim rows duplicates enough text
        // to cross the native request ceiling. Split only the claim list,
        // keeping the same complete source and document in every request.
        // The provider's output ceiling includes reasoning tokens. A request
        // fitting the input budget can still truncate a long verdict list.
        let first = expected.len().div_ceil(32).clamp(1, 3);
        (first..=3).find(|count| {
            expected.chunks(expected.len().div_ceil(*count)).all(|claims| {
                let payload = json!({"sourceUnits":wire,"document":doc,"checkClaims":claims});
                prompt.len() + payload.to_string().len() <= super::MAX_REQUEST_BYTES
            })
        }).ok_or("本场完整原文和逐项审核超出上下文预算，已有纪要保留。")?
    } else if super::coverage::enabled() {
        expected.len().div_ceil(4).clamp(1,3)
    } else {
        1
    };
    let size=expected.len().div_ceil(batches);
    let token=super::current_cancellation();check_cancellation(token.as_ref())?;
    let results=std::thread::scope(|scope|{
        let workers=expected.chunks(size).enumerate().map(|(i,claims)|{
            let token=token.clone();let stage=if batches==1{stage.to_string()}else{format!("{stage}-batch-{i}")};
            scope.spawn(move||{
                let mut calls=Vec::new();
                let result=(||{
                    check_cancellation(token.as_ref())?;
                    let payload=json!({"sourceUnits":wire,"document":doc,"checkClaims":claims});
                    let raw=super::request(endpoint,model,key,client,prompt,payload.clone(),true,start,&mut calls,&stage)?;
                    check_cancellation(token.as_ref())?;
                    let (raw, ignored) = if super::source_items::enabled() {
                        batch_audit_reply(&raw, claims)
                    } else { (raw.as_str().into(), 0) };
                    if ignored > 0 {
                        if let Some(call) = calls.last_mut() {
                            call["ignoredOutOfBatchVerdicts"] = json!(ignored);
                        }
                    }
                    let incomplete=super::coverage::enabled().then(||incomplete_audit(&raw,claims,source)).flatten();
                    match decode(&raw,claims,source){
                        Ok(audit)=>Ok(audit),
                        Err(_) if incomplete.is_some()&&recovered_format.compare_exchange(false,true,Ordering::AcqRel,Ordering::Acquire).is_ok()=>{
                            let(mut audit,missing)=incomplete.unwrap();
                            let payload=json!({"sourceUnits":wire,"document":doc,"checkClaims":missing});
                            let fixed=super::request(endpoint,model,key,client,prompt,payload,true,start,&mut calls,&format!("{stage}-missing-recovery"))?;
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
                            let fixed=super::request(endpoint,model,key,client,prompt,payload,true,start,&mut calls,&format!("{stage}-format-recovery"))?;
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
    let uncertain=claims.iter().filter(|c|source_wording_unclear(c)).flat_map(|c|{
        let phrase=c.unclear_text.as_deref().unwrap_or("");
        source.iter().filter(move|s|!phrase.is_empty()&&c.evidence.contains(&s.id)&&s.text.contains(phrase))
            .map(move|s|json!({"source":s.source,"sentenceId":s.id,"text":phrase}))
    }).collect::<Vec<_>>();
    let history=claims.iter().filter(|c|source_wording_unclear(c)).map(|c|{
        let mut ids=c.evidence.iter().filter_map(|id|source.iter().find(|s|&s.id==id).map(|s|s.source.clone())).collect::<HashSet<_>>();
        let original = expected.iter().find(|claim|claim["path"].as_str()==Some(c.path.as_str()));
        if let Some(refs) = original.and_then(|claim| claim["sources"].as_array()) {
            ids.extend(refs.iter().filter_map(Value::as_str).map(str::to_string));
        }
        let mut record = json!({"path":c.path,"phrase":c.unclear_text,"sourceIds":ids});
        if super::source_items::enabled() && c.evidence.len() == 2 && disputed_relation(&c.reason) {
            if let Some(tail) = c.unclear_text.as_deref().filter(|phrase| !phrase.is_empty())
                .and_then(|phrase| original?.get("text")?.as_str()?.split_once(phrase))
                .map(|(_, tail)| tail).filter(|tail| tail.chars().count() >= 6)
            {
                record["relationTail"] = json!(tail);
            }
        }
        record
    }).collect::<Vec<_>>();
    // An uncertain interpretation can differ from the raw ASR wording (for
    // example a guessed condition). Carry its exact source sentences as well,
    // so a coverage reviewer cannot demand that same guess as a missing fact.
    let interpretations=claims.iter().filter(|c|source_wording_unclear(c)).map(|c|{
        let evidence=c.evidence.iter().filter_map(|id|source.iter().find(|s|&s.id==id))
            .map(|s|json!({"source":s.source,"sentenceId":s.id,"quote":s.text})).collect::<Vec<_>>();
        json!({"interpretation":c.unclear_text,"reason":c.reason,"sourceEvidence":evidence})
    }).collect::<Vec<_>>();
    if let Some(call)=trace.last_mut(){if !uncertain.is_empty(){call["sourceUncertainties"]=json!(uncertain);}if !history.is_empty(){call["unclearClaimHistory"]=json!(history);}if !interpretations.is_empty(){call["sourceInterpretationUncertainties"]=json!(interpretations);}}
    Ok(Audit{claim_audit:claims,format_kind:None})
}
const PENDING_PROPOSAL_PREFIX: &str = "会上讨论「";
const PENDING_PROPOSAL_SUFFIX: &str = "」。其中具体用语待核实。";

fn verified_pending_proposal(text: &str, phrase: &str, verdict: &Claim, source: &[Sentence]) -> bool {
    if verdict.status != "supported" || !verdict.path.starts_with("topics[") {
        return false;
    }
    let Some(quote) = text.strip_prefix(PENDING_PROPOSAL_PREFIX)
        .and_then(|text| text.strip_suffix(PENDING_PROPOSAL_SUFFIX))
    else { return false; };
    quote.contains(phrase) && source.iter().any(|sentence| {
        verdict.evidence.contains(&sentence.id)
            && super::super::source_resolution::split_turn_label(&sentence.text)
                .map_or(sentence.text.as_str(), |(_, speech)| speech).trim() == quote
    })
}

#[cfg(test)]
#[test]
fn historical_veto_distinguishes_a_verbatim_pending_quote_from_an_assertion() {
    let path = "topics[2].details[6]";
    let source = [Sentence{id:"e0107".into(),source:"u005".into(),
        text:"说话人2: 设备工程部可以向财务部申请报表儿，可以加装几个抽水泵。".into()}];
    let history = [json!({"phrase":"申请报表","sourceIds":["u005"]})];
    let verdict = json!({"claimAudit":[{"path":path,"status":"supported","reason":"引用了原话","evidence":["e0107"],"clarity":"clear"}]});
    for (text, vetoed) in [
        ("会上讨论「设备工程部可以向财务部申请报表儿，可以加装几个抽水泵。」。其中具体用语待核实。", false),
        ("设备工程部应当申请报表。", true),
        ("会上讨论「设备工程部应立即申请报表儿」。其中具体用语待核实。", true),
        ("会上讨论「设备工程部可以向财务部申请报表儿，可以加装几个抽水泵。」。报名手续已确认。", true),
    ] {
        let mut audit: Audit = serde_json::from_value(verdict.clone()).unwrap();
        let claim = json!({"path":path,"text":text,"sources":["u005"]});
        assert_eq!(!apply_historical_veto(&mut audit, &[claim], &history, &source).is_empty(), vetoed);
    }
}

fn apply_historical_veto(audit:&mut Audit,expected:&[Value],history:&[Value],source:&[Sentence])->Vec<String>{
    let mut vetoed=Vec::new();
    for verdict in &mut audit.claim_audit{
        let Some(claim)=expected.iter().find(|c|c["path"].as_str()==Some(verdict.path.as_str()))else{continue;};
        let mut context=verdict.evidence.iter().filter_map(|id|source.iter().find(|s|&s.id==id).map(|s|s.source.as_str())).collect::<HashSet<_>>();
        if let Some(refs)=claim["sources"].as_array(){context.extend(refs.iter().filter_map(Value::as_str));}
        let found=history.iter().find_map(|record|{
            let phrase=record["phrase"].as_str().filter(|s|!s.is_empty())?;let ids=record["sourceIds"].as_array()?;
            (ids.is_empty()||ids.iter().filter_map(Value::as_str).any(|id|context.contains(id))).then_some(())?;
            if let Some(relation) = record["relationTail"].as_str() {
                // A separately supported mention does not repeat a disputed
                // relationship. Keep the veto on the old predicate, and let
                // the independent verdict handle other claims about the term.
                let text = claim["text"].as_str()?;
                let tail: Vec<_> = relation.chars().collect();
                if !tail.windows(4).any(|part| part.iter().all(|ch| matches!(*ch, '\u{3400}'..='\u{9fff}'))
                    && text.contains(&part.iter().collect::<String>()))
                {
                    return None;
                }
            }
            let asserted = claim["text"].as_str().is_some_and(|text| {
                text.contains(phrase) && !verified_pending_proposal(text, phrase, verdict, source)
            });
            (asserted || ["owner", "due"].iter().any(|field| {
                claim[*field].as_str().is_some_and(|text| text.contains(phrase))
            })).then_some(phrase)
        });
        if let Some(phrase)=found{
            if verdict.clarity.as_deref()==Some("unclear")&&verdict.unclear_text.as_deref()==Some(phrase){continue;}
            if verdict.status=="supported"{verdict.status="unclear".into();}
            verdict.clarity=Some("unclear".into());verdict.unclear_text=Some(phrase.into());
            verdict.reason=format!("本次同一原文此前已否决此含混表达，不能在新增或修改内容中重新当作确定信息；{}",verdict.reason).chars().take(300).collect();vetoed.push(verdict.path.clone());
        }
    }
    vetoed
}
#[cfg(test)]
fn apply_changes(raw:&str,doc:&Document,allowed:&HashSet<String>,unclear:&HashSet<String>,units:&[Unit])->Result<Document,String> {
    apply_changes_with_policy(raw,doc,allowed,unclear,&HashMap::new(),&HashSet::new(),units)
}

fn mask_unclear_quote(corrected: &str, phrases: &[String]) -> String {
    let mut result = corrected.to_owned();
    for phrase in phrases.iter().filter(|phrase| !phrase.is_empty()) {
        if corrected.trim_end_matches(['。', '.']).ends_with("含义待核对") {
            result = result.replace(&format!("“{phrase}”"), "一处含混表述");
        }
        let quoted = format!("“{phrase}”");
        if let Some((_, qualification)) = result.split_once(&quoted) {
            let qualification = qualification.trim_end_matches(['。', '.']);
            let explicitly_unresolved = ["，但未明确", "，但无法确认", "，但不能确定"]
                .iter().any(|start| qualification.starts_with(start))
                && ["待核实", "待核对"].iter().any(|end| qualification.ends_with(end))
                && !qualification.contains(['。', '；', ';'])
                && !["不待", "不必", "无需", "已明确", "已确认"]
                    .iter().any(|term| qualification.contains(term));
            if explicitly_unresolved && result.matches(&quoted).count() == 1 {
                result = result.replacen(&quoted, "一处含混表述", 1);
            }
        }
        for qualified in [format!("{phrase}，具体所指待核对"), format!("{phrase}，具体所指待核实")] {
            let sentence = result.trim_end_matches(['。', '.']);
            if sentence.ends_with(&qualified) && result.matches(phrase.as_str()).count() == 1 {
                result = result.replacen(phrase.as_str(), "含混表述", 1);
            }
        }
        for quoted in [phrase.clone(), format!("“{phrase}”")] {
            let positions = result.match_indices(&quoted).filter_map(|(start, token)| {
                let end = start + token.len();
                let suffix = &result[end..];
                let (open, close) = match suffix.chars().next()? {
                    '（' => ('（', '）'),
                    '(' => ('(', ')'),
                    _ => return None,
                };
                let (marker, _) = suffix.strip_prefix(open)?.split_once(close)?;
                let valid = super::line(marker, 48) && !marker.contains(['（', '）', '(', ')'])
                    && !["无需", "不必", "不待", "不是", "不再"].iter().any(|word| marker.contains(word))
                    && (marker.ends_with("待核对") || marker.ends_with("待核实"));
                valid.then_some(start..end)
            }).collect::<Vec<_>>();
            for range in positions.into_iter().rev() {
                result.replace_range(range, "含混表述");
            }
        }
    }
    result
}

#[cfg(test)]
#[test]
fn review_masks_only_an_exact_quote_marked_as_unresolved() {
    let ambiguous_due = vec!["可以这两天".to_owned()];
    assert_eq!(mask_unclear_quote("说话人回应“可以这两天”，但未明确时间，具体待核对。", &ambiguous_due),
        "说话人回应一处含混表述，但未明确时间，具体待核对。");
    assert_eq!(mask_unclear_quote("说话人回应“可以这两天”，但未明确时间。另一个话题待核对。", &ambiguous_due),
        "说话人回应“可以这两天”，但未明确时间。另一个话题待核对。");
    let phrases = vec!["租赁城市".to_owned()];
    assert_eq!(mask_unclear_quote("门店只能租，并提到“租赁城市”，该说法含义待核对。", &phrases),
        "门店只能租，并提到一处含混表述，该说法含义待核对。");
    assert_eq!(mask_unclear_quote("已确定“租赁城市”。", &phrases), "已确定“租赁城市”。");
    assert_eq!(mask_unclear_quote("说话人只提到租赁城市，具体所指待核对。", &phrases),
        "说话人只提到含混表述，具体所指待核对。");
    assert_eq!(mask_unclear_quote("租赁城市已定，另一处租赁城市，具体所指待核对。", &phrases),
        "租赁城市已定，另一处租赁城市，具体所指待核对。");
    assert_eq!(mask_unclear_quote("不带引号的租赁城市，含义待核对。", &phrases),
        "不带引号的租赁城市，含义待核对。");
    assert_eq!(mask_unclear_quote("门店只能租，并提到租赁城市（具体所指待核对）。", &phrases),
        "门店只能租，并提到含混表述（具体所指待核对）。");
    assert_eq!(mask_unclear_quote("租赁城市已定，门店名称（具体所指待核对）。", &phrases),
        "租赁城市已定，门店名称（具体所指待核对）。");
    assert_eq!(mask_unclear_quote("说话人4回应称租赁城市（该表述原话含混，具体含义待核对）。", &phrases),
        "说话人4回应称含混表述（该表述原话含混，具体含义待核对）。");
    assert_eq!(mask_unclear_quote("租赁城市（已确认，不待核对）。", &phrases),
        "租赁城市（已确认，不待核对）。");
}

fn demote_item(value: &mut Value, pointer: &str, units: &[Unit], preferred: Option<usize>, source_first: bool) -> Option<()> {
    let item = value.pointer(pointer)?;
    let text = item["text"].as_str()?.to_owned();
    if !super::line(&text, 120) {
        return None;
    }
    let sources = item["sources"].as_array()?.clone();
    let offsets: HashMap<_, _> = units.iter().enumerate().map(|(index, unit)|(unit.id.as_str(),index)).collect();
    let anchors: Vec<_> = sources.iter().filter_map(|id| offsets.get(id.as_str()?)).copied().collect();
    let topics = value["topics"].as_array_mut()?;
    if preferred.is_some_and(|index| index >= topics.len()) {
        return None;
    }
    let (_, target) = topics.iter_mut().enumerate().filter(|(_, topic)| topic["details"].as_array()
        .is_some_and(|details| details.len() < super::topic_details_limit())).min_by_key(|(index, topic)| {
        let distance = topic["points"].as_array().into_iter().flatten().chain(topic["details"].as_array().into_iter().flatten())
            .flat_map(|entry| entry["sources"].as_array().into_iter().flatten())
            .filter_map(|id| offsets.get(id.as_str()?))
            .flat_map(|offset| anchors.iter().map(move |anchor| offset.abs_diff(*anchor)))
            .min().unwrap_or(usize::MAX);
        let differs = usize::from(Some(*index) != preferred);
        if source_first { (distance, differs) } else { (differs, distance) }
    })?;
    target["details"].as_array_mut()?.push(json!({"text":text,"sources":sources}));
    Some(())
}

fn unique_repair_rows(edits: &[Value], allow_equal_echoes: bool) -> Option<Vec<&Value>> {
    let mut previous = HashMap::new();
    let mut unique = Vec::new();
    for edit in edits {
        let path = edit["path"].as_str()?;
        match previous.get(path) {
            Some(prior) if allow_equal_echoes && *prior == edit => continue,
            Some(_) => return None,
            None => {
                previous.insert(path, edit);
                unique.push(edit);
            }
        }
    }
    Some(unique)
}

#[cfg(test)]
fn apply_changes_with_policy(raw:&str,doc:&Document,allowed:&HashSet<String>,unclear:&HashSet<String>,
    conservative:&HashMap<String,Vec<String>>,misplaced:&HashSet<String>,units:&[Unit])->Result<Document,String> {
    apply_repair(raw,doc,allowed,unclear,conservative,misplaced,units,false).map(|repair| repair.document)
}

struct AppliedRepair {
    document: Document,
    corrected_statements: HashMap<String, String>,
}

fn statement_identity(path: &str, claim: &Value) -> String {
    let section = if path == "purpose" { "purpose" }
        else if path.ends_with(".title") { "title" }
        else if path.contains(".points[") { "points" }
        else if path.contains(".details[") { "details" }
        else { path.split('[').next().unwrap_or(path) };
    let text = claim.as_str().or_else(|| claim["text"].as_str());
    let kind = (section == "points").then(|| claim["kind"].as_str()).flatten();
    json!([section, text, claim["owner"].as_str(), claim["due"].as_str(), kind]).to_string()
}

fn unresolved_action_fields(target: &Value, text: &str, rejected: &[String]) -> Vec<&'static str> {
    [
        ("owner", &["负责人待核实", "负责人待核对", "承接人待核实", "承接人待核对"][..]),
        ("due", &["截止时间待核实", "截止时间待核对", "完成期限待核实", "完成期限待核对"][..]),
    ].into_iter().filter_map(|(field, cues)| {
        let previous = target[field].as_str()?;
        (rejected.iter().any(|phrase| phrase == previous) && cues.iter().any(|cue| text.contains(cue))).then_some(field)
    }).collect()
}

fn disputed_relation(reason: &str) -> bool {
    reason.contains("未明确") && reason.contains("则")
        && ["关系", "也可", "同时", "也能"].iter().any(|cue| reason.contains(cue))
}

fn remove_fused_example(text: &str, issue: &Value, source: &[Sentence]) -> Option<String> {
    use std::sync::LazyLock;
    static EXAMPLE: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:比如|例如|如)(?P<link>(?P<example>[\p{Han}]{2,8})等(?P<category>[\p{Han}]{2,8}?)(?P<place>城市|地区|省份|口岸|区县))"
    ).unwrap());
    if issue["status"] != "overstated" {
        return None;
    }
    let matched = EXAMPLE.captures(text)?;
    let link = matched.name("link")?.as_str();
    let reason = issue["reason"].as_str()?;
    if !reason.contains(link) || !["另说", "分别", "混为", "误归"].iter().any(|cue| reason.contains(cue)) {
        return None;
    }
    let example = matched.name("example")?.as_str();
    let category = matched.name("category")?.as_str();
    let place = matched.name("place")?.as_str();
    let category_phrase = regex::Regex::new(&format!(
        r"{}[\p{{Han}}]{{0,6}}{}", regex::escape(category), regex::escape(place)
    )).ok()?;
    let evidence: Vec<_> = issue["evidence"].as_array()?.iter().filter_map(|id| {
        source.iter().find(|sentence| id == sentence.id.as_str()).map(|sentence| sentence.text.as_str())
    }).collect();
    let example_witness = evidence.iter().any(|excerpt| excerpt.contains(example));
    let category_witness = evidence.iter().any(|excerpt| category_phrase.is_match(excerpt));
    let linked = evidence.iter().any(|excerpt| excerpt.contains(example) && category_phrase.is_match(excerpt));
    (example_witness && category_witness && !linked)
        .then(|| text.replacen(matched.get(0).unwrap().as_str(), "", 1))
}

fn repair_separately_cited_examples(issues: &[Value], claims: &[Value], source: &[Sentence]) -> Option<String> {
    let changes = issues.iter().map(|issue| {
        let path = issue["path"].as_str()?;
        if !path.contains(".details[") && !path.contains(".points[") {
            return None;
        }
        let claim = claims.iter().find(|claim| claim["path"] == path)?;
        let text = remove_fused_example(claim["text"].as_str()?, issue, source)?;
        Some(json!({"path":path,"text":text}))
    }).collect::<Option<Vec<_>>>()?;
    Some(json!({"changes":changes}).to_string())
}

#[cfg(test)]
#[test]
fn separate_example_citations_are_required_to_remove_a_false_link() {
    let source = ["未去例如甲城等地方", "靠近边境的这些城市举例"]
        .into_iter().enumerate().map(|(index, text)| Sentence {
            id: format!("e{index:04}"), source: "u000".into(), text: text.into(),
        }).collect::<Vec<_>>();
    let claim = json!({"path":"topics[0].details[0]","text":"未去高风险地区如甲城等边境城市。"});
    let mut issue = json!({"path":claim["path"],"status":"overstated",
        "reason":"甲城作为高风险地区举例，另说边境城市，合并成甲城等边境城市有误归。",
        "evidence":["e0000","e0001"]});
    let fix = repair_separately_cited_examples(&[issue.clone()], &[claim.clone()], &source).unwrap();
    assert_eq!(serde_json::from_str::<Value>(&fix).unwrap()["changes"][0]["text"], "未去高风险地区。");
    issue["evidence"] = json!(["e0000"]);
    assert!(repair_separately_cited_examples(&[issue], &[claim], &source).is_none());
}

fn verified_owner_from_repair(issue: &Value, text: &str, source: &[Sentence]) -> Option<String> {
    use std::sync::LazyLock;
    static ASSIGNED: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r#"(?:执行主体|承接方|负责人)(?:应为|为|是)[“「"](?P<owner>[\p{Han}]{2,18})[”」"]"#
    ).unwrap());
    if issue["status"] != "unsupported" || issue["placementUnsupported"] != false
        || !issue["path"].as_str()?.starts_with("actionItems[")
    {
        return None;
    }
    let captured = ASSIGNED.captures(issue["reason"].as_str()?)?;
    let owner = captured.name("owner")?.as_str();
    let owner = owner.strip_suffix('儿').unwrap_or(owner);
    if !text.contains(owner) {
        return None;
    }
    let witnesses = issue["evidence"].as_array()?;
    source.iter().any(|sentence| witnesses.iter().any(|id| id == sentence.id.as_str())
        && sentence.text.match_indices(owner).any(|(start, label)| {
            let instruction = sentence.text[start + label.len()..].trim_start_matches('儿').trim_start();
            let prefix = sentence.text[..start].trim_end();
            let explicit = ["要", "得", "需要", "负责"].iter().any(|word| instruction.starts_with(word));
            let collective = ["咱们", "我们"].iter().any(|word| prefix.ends_with(word));
            let predicate: String = instruction.chars().take(3).collect();
            explicit || (collective && predicate.chars().count() == 3
                && predicate.chars().all(|ch| ('㐀'..='鿿').contains(&ch))
                && text.contains(&predicate))
        }))
        .then(|| owner.to_owned())
}

fn retain_misplaced_statement(issue: &Value, claim: &Value) -> Option<String> {
    if issue["placementUnsupported"] != true || issue["status"] != "unsupported"
        || issue["clarity"] != "clear" || claim["kind"] != "action"
    {
        return None;
    }
    let reason = issue["reason"].as_str()?;
    let witness = reason.starts_with("原话是")
        && ["的现状", "已完成事项", "方向性总结"].iter().any(|cue| reason.contains(cue))
        && ["不是会后", "而非会后", "而非具体行动"].iter().any(|cue| reason.contains(cue));
    let text = claim["text"].as_str()?;
    (witness && super::line(text, 120)).then(|| text.to_owned())
}

fn unsettled_assignment_quote(issue: &Value, claim: &Value, source: &[Sentence]) -> Option<String> {
    let reason = issue["reason"].as_str()?;
    if issue["placementUnsupported"] != true || issue["status"] != "overstated"
        || issue["clarity"] != "clear" || claim["kind"] != "action"
        || !reason.contains("未形成") || !reason.contains("会后")
        || !["指派", "承诺", "交办"].iter().any(|cue| reason.contains(cue)) {
        return None;
    }
    let owner = claim["owner"].as_str()?;
    let cited = issue["evidence"].as_array()?;
    let mut found = source.iter().filter(|sentence| cited.iter().any(|id| id == sentence.id.as_str()))
        .filter_map(|sentence| {
            let (speaker, utterance) = super::super::source_resolution::split_turn_label(&sentence.text)?;
            let (aspect, phrase) = super::source_items::ordinary_source_aspect(utterance)?;
            if aspect != "交办后又提问" {
                return None;
            }
            let (before, _) = utterance.split_once(phrase)?;
            let direction = before.rfind(owner)?;
            let after_owner = before[direction+owner.len()..].trim_start();
            if !["这边", "这块", "这一块", "这里"].iter().any(|cue| after_owner.starts_with(cue))
                || after_owner.chars().count() > 55 {
                return None;
            }
            let first = before[..direction].char_indices().rev()
                .find(|(_, ch)| matches!(ch, '。' | '；' | '，' | ' '))
                .map_or(0, |(offset, ch)| offset + ch.len_utf8());
            let excerpt = utterance[first..before.len()+phrase.len()].trim();
            let text = format!("{speaker}提到「{excerpt}」，是否形成会后交办待核实。");
            (super::line(&text, 120) && !excerpt.contains(['「', '」'])).then_some(text)
        });
    let one = found.next()?;
    found.next().is_none().then_some(one)
}

fn explicit_response_speaker(text: &str, issue: &Value, source: &[Sentence]) -> Option<String> {
    use std::sync::LazyLock;
    static HANDOFF: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"^(?P<speaker>说话人[0-9]+)[^；;。]+[；;]\s*(?:随后|接着|然后)?(?P<request>请)(?P<group>[^，。；;！？]{2,24}?)(?:发表看法|给出意见|作出回应|回应|回答)[。！？]?$"
    ).unwrap());
    if issue["status"] != "unsupported" || !issue["path"].as_str()?.contains(".details[") {
        return None;
    }
    if !["归属", "归错", "误归", "转请"].iter().any(|term| issue["reason"].as_str().unwrap_or("").contains(term)) {
        return None;
    }
    let handoff = HANDOFF.captures(text)?;
    let initial_speaker = handoff.name("speaker")?.as_str();
    let destination = handoff.name("group")?.as_str();
    let request = handoff.name("request")?;
    let evidence = issue["evidence"].as_array()?;
    let turns: Vec<_> = source.iter().enumerate()
        .filter(|(_, sentence)| evidence.iter().any(|id| id == sentence.id.as_str()))
        .filter_map(|(index, sentence)| {
            super::super::source_resolution::split_turn_label(sentence.text.trim())
                .map(|(label, content)| (index, label, content))
        }).collect();
    let first = turns.iter().position(|(_, label, _)| *label == initial_speaker)?;
    let mut responders = turns.into_iter().skip(first + 1).filter_map(|(_, label, content)| {
        let (_, request) = content.split_once(destination)?;
        (label != initial_speaker && ["有什么看法", "怎么看", "请回应", "请回答", "发表看法", "有什么意见"]
            .iter().any(|cue| request.contains(cue))).then_some(label)
    });
    let responder = responders.next()?;
    if responders.any(|label| label != responder) { return None; }
    let mut revised = text.to_owned();
    revised.insert_str(request.start(), responder);
    Some(revised)
}

#[cfg(test)]
#[test]
fn response_speaker_comes_from_a_different_cited_turn() {
    let mut issue = json!({"path":"topics[0].details[0]","status":"unsupported",
        "reason":"前者发问，后者只是转请两个小组发言，归属错误。","evidence":["e0000","e0002"]});
    let oral = [
        "说话人7：希望只考虑个人经验，该怎么选？",
        "说话人3：运营组和售后组你们怎么看？",
        "说话人2：刚才说了管理组的看法，那运营组和售后组有什么看法吗？",
    ];
    let source: Vec<_> = oral.into_iter().enumerate().map(|(i, text)| Sentence {
        id:format!("e{i:04}"),source:"u000".into(),text:text.into(),
    }).collect();
    let text = "说话人7询问只考虑个人经验时该怎么选；随后请运营组和售后组发表看法。";
    assert_eq!(explicit_response_speaker(text, &issue, &source).as_deref(),
        Some("说话人7询问只考虑个人经验时该怎么选；随后说话人2请运营组和售后组发表看法。"));
    issue["evidence"] = json!(["e0000","e0001","e0002"]);
    assert!(explicit_response_speaker(text, &issue, &source).is_none());
    issue["evidence"] = json!(["e0002"]);
    assert!(explicit_response_speaker(text, &issue, &source).is_none());
}

fn normalize_repair_reply(raw: &str, issues: &[Value], source: &[Sentence], claims: &[Value]) -> (String, usize) {
    let original = || (raw.to_owned(), 0);
    let Ok(mut reply) = serde_json::from_str::<Value>(super::super::strip_code_fences(raw).trim()) else {
        return original();
    };
    let Some(rows) = reply["changes"].as_array_mut() else { return original(); };
    let mut count = 0;
    for row in rows {
        let Some(body) = row.as_object_mut() else { continue; };
        let Some(path) = body.get("path").and_then(Value::as_str) else { continue; };
        let Some(issue) = issues.iter().find(|issue| issue["path"] == path) else { continue; };
        let Some(text) = body.get("text").and_then(Value::as_str) else { continue; };
        if body.len() == 3 && body.get("remove").and_then(Value::as_bool) == Some(true)
            && issue["placementUnsupported"] == true && issue["clarity"] == "clear"
            && issue["status"] == "overstated" && independent_path(path) && super::line(text, 120)
        {
            // The original role is unsupported, while the replacement can
            // still describe a real discussion. The usual demotion and
            // independent factual recheck apply before it is publishable.
            body.remove("remove");
            count += 1;
            continue;
        }
        let text_patch = body.len() == 2 || (body.len() == 3 && body.get("moveToTopic").is_some_and(Value::is_u64));
        let sourced = claims.iter().find(|claim| text_patch && claim["path"] == path)
            .and_then(|claim| unsettled_assignment_quote(issue, claim, source));
        if let Some(sourced) = sourced {
            body.insert("text".into(), json!(sourced));
            count += 1;
            continue;
        }
        if body.len() != 2 { continue; }
        if let Some(revised) = explicit_response_speaker(text, issue, source) {
            body.insert("text".into(), json!(revised));
            count += 1;
            continue;
        }
        if let Some(owner) = verified_owner_from_repair(issue, text, source) {
            body.insert("owner".into(), json!(owner));
            count += 1;
            continue;
        }
        let fix = if text.trim() == "remove" && issue["placementUnsupported"] == true && independent_path(path) {
            let found = claims.iter().find(|claim| claim["path"] == path)
                .and_then(|claim| retain_misplaced_statement(issue, claim));
            if let Some(text) = found { Some(("text", json!(text))) }
            else { Some(("remove", json!(true))) }
        } else if let Some(deletions) = text.trim().strip_prefix("delete:").filter(|_| issue["status"] == "unclear") {
            serde_json::from_str::<Vec<String>>(deletions.trim()).ok().map(|parts| ("delete", json!(parts)))
        } else {
            let term = issue["unclearText"].as_str();
            let explanation = issue["reason"].as_str().unwrap_or_default();
            if issue["status"] != "unclear" || !term.is_some_and(|term| text.contains(term))
                || !disputed_relation(explanation)
            {
                continue;
            }
            let evidence: Vec<_> = issue["evidence"].as_array().into_iter().flatten().filter_map(|id| {
                let sentence = source.iter().find(|sentence| id == sentence.id.as_str())?;
                let excerpt = super::super::source_resolution::split_turn_label(sentence.text.trim())
                    .map_or(sentence.text.trim(), |(_, value)| value.trim());
                (super::line(excerpt, 34) && !excerpt.contains(term.unwrap())
                    && !excerpt.contains(['「', '」'])).then_some(excerpt)
            }).collect();
            match evidence.as_slice() {
                [first, second] if first != second => {
                    Some(("text", json!(format!("会上分别提到「{first}」和「{second}」。两处说法之间的关系待核实。"))))
                }
                _ => None,
            }
        };
        if let Some((key, value)) = fix {
            body.remove("text");
            body.insert(key.into(), value);
            count += 1;
        }
    }
    if count > 0 { (reply.to_string(), count) } else { original() }
}

#[cfg(test)]
#[test]
fn repair_with_replacement_and_remove_keeps_audited_role_correction_without_panicking() {
    let reply = json!({"changes":[
        {"path":"actionItems[0]","text":"讨论是否投资。","remove":true},
        {"path":"actionItems[1]","text":"确认投资。","remove":true},
    ]});
    let issues = [
        json!({"path":"actionItems[0]","placementUnsupported":true,"status":"overstated","clarity":"clear"}),
        json!({"path":"actionItems[1]","status":"unsupported","clarity":"clear"}),
    ];
    let (normalized, count) = normalize_repair_reply(&reply.to_string(), &issues, &[], &[]);
    let normalized: Value = serde_json::from_str(&normalized).unwrap();
    assert_eq!(count, 1);
    assert_eq!(normalized["changes"][0], json!({"path":"actionItems[0]","text":"讨论是否投资。"}));
    assert_eq!(normalized["changes"][1], reply["changes"][1]);
}

#[cfg(test)]
#[test]
fn repair_reply_keeps_typed_deletions_inside_the_audited_scope() {
    let reply = json!({"changes":[
        {"path":"decisions[0]","text":"remove"},
        {"path":"questions[0]","text":"delete:[\"可疑表述\"]"},
        {"path":"topics[0].details[1]","text":"remove"},
    ]});
    let issues = [
        json!({"path":"decisions[0]","placementUnsupported":true}),
        json!({"path":"questions[0]","status":"unclear"}),
    ];
    let (normalized, count) = normalize_repair_reply(&reply.to_string(), &issues, &[], &[]);
    let normalized: Value = serde_json::from_str(&normalized).unwrap();
    assert_eq!(count, 2);
    assert_eq!(normalized["changes"][0], json!({"path":"decisions[0]","remove":true}));
    assert_eq!(normalized["changes"][1], json!({"path":"questions[0]","delete":["可疑表述"]}));
    assert_eq!(normalized["changes"][2], reply["changes"][2]);
}

#[cfg(test)]
#[test]
fn a_reported_status_survives_deletion_from_the_wrong_column() {
    let path = "actionItems[0]";
    let issue = json!({"path":path,"status":"unsupported","clarity":"clear","placementUnsupported":true,
        "reason":"原话是负责人汇报培训和手册的现状，不是会后新指派。"});
    let claim = json!({"path":path,"kind":"action","text":"人事正在培训和编制员工手册。"});
    let raw = json!({"changes":[{"path":path,"text":"remove"}]}).to_string();
    let (repaired, count) = normalize_repair_reply(&raw, &[issue], &[], &[claim.clone()]);
    assert_eq!(count, 1);
    assert_eq!(serde_json::from_str::<Value>(&repaired).unwrap()["changes"][0]["text"], claim["text"]);
}

#[cfg(test)]
#[test]
fn an_audited_assignee_is_applied_to_the_action_owner_field() {
    let path = "actionItems[1]";
    let report = json!({"path":path, "status":"unsupported", "placementUnsupported":false,
        "reason":"任务有据，但要求者与执行主体为“质检这边儿”不符。","evidence":["e0003"]});
    let text = "主持人要求质检这边完成入库检查。";
    let source = [Sentence {id:"e0003".into(),source:"u000".into(),
        text:"主持人：质检这边儿要完成入库检查。".into()}];
    assert_eq!(verified_owner_from_repair(&report, text, &source).as_deref(), Some("质检这边"));
    assert_eq!(verified_owner_from_repair(&report, "主持人要求完成入库检查。", &source), None);
    let collective = [Sentence {id:"e0003".into(),source:"u000".into(),
        text:"主持人：近期咱们质检这边儿完成入库检查。".into()}];
    assert_eq!(verified_owner_from_repair(&report, text, &collective).as_deref(), Some("质检这边"));
    let raw = json!({"changes":[{"path":path,"text":text}]}).to_string();
    let (normalized, count) = normalize_repair_reply(&raw, &[report], &source, &[]);
    assert_eq!(count, 1);
    assert_eq!(serde_json::from_str::<Value>(&normalized).unwrap()["changes"][0]["owner"], "质检这边");
}

#[cfg(test)]
#[test]
#[ignore = "requires previously paid, frozen audit and repair responses"]
fn qm06_replay_candidate_keeps_original_facts_during_role_removal() {
    let input = std::env::var_os("COMPANION_TEST_QM06_SPORTS_REPAIR_INPUT").unwrap();
    let trace = std::env::var_os("COMPANION_TEST_QM06_SPORTS_REPAIR_TRACE").unwrap();
    let read = |path| -> Value { serde_json::from_slice(&std::fs::read(path).unwrap()).unwrap() };
    let input = read(input);
    let trace = read(trace);
    let raw = trace["calls"].as_array().unwrap().iter()
        .find(|row| row["stage"] == "source-factual-repair").unwrap()["response"].as_str().unwrap();
    let mut original = Vec::new();
    for (index, source) in input["previousDocument"]["actionItems"].as_array().unwrap().iter().enumerate() {
        original.push(json!({"path":format!("actionItems[{index}]"),"kind":"action","text":source["text"]}));
    }
    let source: Vec<_> = input["sourceUnits"].as_array().unwrap().iter().flat_map(|unit| {
        unit["sentences"].as_array().unwrap().iter().map(|sentence| Sentence {
            id: sentence["id"].as_str().unwrap().into(),
            source: unit["id"].as_str().unwrap().into(),
            text: sentence["text"].as_str().unwrap().into(),
        })
    }).collect();
    let reply = normalize_repair_reply(raw, input["auditProblems"].as_array().unwrap(), &source, &original).0;
    let output: Value = serde_json::from_str(&reply).unwrap();
    let rows = output["changes"].as_array().unwrap();
    for (path, literal) in [("actionItems[9]", "员工手册"), ("actionItems[13]", "正常运行")] {
        let fix = rows.iter().find(|row| row["path"] == path).unwrap();
        assert!(fix["text"].as_str().unwrap().contains(literal), "{fix}");
        assert!(fix.get("remove").is_none());
    }
    println!("sports: actual archived corrections retained the staffing and closing statements");
}

#[cfg(test)]
#[test]
fn a_disputed_location_does_not_invalidate_the_original_device_mention() {
    let claims = [
        json!({"path":"topics[0].details[0]","text":"提到了自动售卖设备。","sources":["u000"]}),
        json!({"path":"topics[0].details[1]","text":"把自动售卖设备放在前台结账处。","sources":["u000"]}),
    ];
    let history = [json!({"phrase":"自动售卖设备","relationTail":"也可放在前台结账处","sourceIds":["u000"]})];
    let mut audit: Audit = serde_json::from_value(json!({"claimAudit": [
        {"path":"topics[0].details[0]","status":"supported","reason":"已有对应原话。","evidence":[]},
        {"path":"topics[0].details[1]","status":"supported","reason":"接收了援引。","evidence":[]},
    ]})).unwrap();
    assert_eq!(apply_historical_veto(&mut audit, &claims, &history, &[]), ["topics[0].details[1]"]);
    assert_eq!(audit.claim_audit[0].status, "supported");
    assert_eq!(audit.claim_audit[1].status, "unclear");
}

fn apply_repair(raw:&str,doc:&Document,allowed:&HashSet<String>,unclear:&HashSet<String>,
    conservative:&HashMap<String,Vec<String>>,misplaced:&HashSet<String>,units:&[Unit],source_first:bool)->Result<AppliedRepair,String> {
    let fail=||"纪要修正没有遵守受影响范围，已有结果保留。".to_string();
    let changes:Value=serde_json::from_str(super::super::strip_code_fences(raw).trim()).map_err(|_|fail())?;
    let root=changes.as_object().ok_or_else(fail)?;
    if root.len()!=1{return Err(fail());}
    let edits=root.get("changes").and_then(Value::as_array)
        .and_then(|edits| unique_repair_rows(edits,super::source_items::enabled())).ok_or_else(fail)?;
    if edits.is_empty()||edits.len()>allowed.len(){return Err(fail());}
    let mut value=serde_json::to_value(doc).map_err(|_|fail())?;let mut seen=HashSet::new();let mut removals=Vec::new();
    for edit in edits {
        let row=edit.as_object().ok_or_else(fail)?;
        if row.keys().any(|k|!matches!(k.as_str(),"path"|"text"|"remove"|"kind"|"owner"|"due"|"delete"|"moveToTopic")){return Err(fail());}
        let path=row.get("path").and_then(Value::as_str).ok_or_else(fail)?;
        if !allowed.contains(path)||!seen.insert(path.to_string()){return Err(fail());}
        let pointer=format!("/{}",path.replace('[',"/").replace(']',"").replace('.',"/"));
        if let Some(topic)=row.get("moveToTopic") {
            if !super::source_items::enabled()||!misplaced.contains(path)||unclear.contains(path)||row.len()!=3
                ||!independent_path(path){return Err(fail());}
            let index=topic.as_u64().and_then(|index|usize::try_from(index).ok()).ok_or_else(fail)?;
            let text=row.get("text").and_then(Value::as_str).filter(|text|super::line(text,120)).ok_or_else(fail)?;
            let item=value.pointer_mut(&pointer).and_then(Value::as_object_mut).ok_or_else(fail)?;
            item.insert("text".into(), json!(text));
            demote_item(&mut value, &pointer, units, Some(index), source_first).ok_or_else(fail)?;
            removals.push(pointer);
            continue;
        }
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
        let mut replacement = row.get("text").cloned();
        let mut clear_fields = Vec::new();
        if unclear.contains(path)&&replacement.is_some() {
            let phrases=conservative.get(path).filter(|phrases|!phrases.is_empty()).ok_or_else(fail)?;
            let text=row["text"].as_str().filter(|s|!s.trim().is_empty()).ok_or_else(fail)?;
            let original=if path=="purpose"||path.ends_with(".title"){target.as_str()}else{target.get("text").and_then(Value::as_str)}.ok_or_else(fail)?;
            let text = if super::source_items::enabled() {
                if path.starts_with("actionItems[") { clear_fields = unresolved_action_fields(target, text, phrases); }
                mask_unclear_quote(text, phrases)
            } else {
                text.to_owned()
            };
            let explicit_nulls = clear_fields.iter().filter(|field| row.get(**field).is_some_and(Value::is_null)).count();
            if row.len()!=2+explicit_nulls||phrases.iter().any(|phrase|phrase.is_empty()||!original.contains(phrase)||text.contains(phrase)){return Err(fail());}
            replacement = Some(json!(text));
        }
        if let Some(text)=replacement {
            if !text.is_string(){return Err(fail());}
            if path=="purpose"||path.ends_with(".title"){*target=text;}else{target.as_object_mut().ok_or_else(fail)?.insert("text".into(),text);}
        }
        for field in clear_fields {
            target.as_object_mut().ok_or_else(fail)?.insert(field.into(),Value::Null);
        }
        for field in ["kind","owner","due"] {
            if let Some(v)=row.get(field) {
                if field=="kind"&&!path.contains(".points[")||field!="kind"&&!path.starts_with("actionItems["){return Err(fail());}
                target.as_object_mut().ok_or_else(fail)?.insert(field.into(),v.clone());
            }
        }
        if !row.contains_key("text")&&!row.contains_key("kind")&&!row.contains_key("owner")&&!row.contains_key("due"){return Err(fail());}
    }
    // The audit certifies that the original column is wrong. Text-only
    // repairs at those paths cannot keep the old decision/task/question role.
    let mut relocations: Vec<_> = misplaced.iter().collect();
    relocations.sort();
    for path in relocations {
        let pointer = format!("/{}",path.replace('[',"/").replace(']',"").replace('.',"/"));
        if removals.contains(&pointer) {
            continue;
        }
        if !seen.contains(path.as_str()) || !independent_path(path) || demote_item(&mut value,&pointer,units,None,source_first).is_none() {
            return Err(fail());
        }
        removals.push(pointer);
    }
    // Array indices are addresses in this reply, not identities across
    // repairs. Keep identities of amended statements that remain in place.
    let mut corrected_statements = HashMap::new();
    if super::source_items::enabled() {
        for path in seen {
            let pointer = format!("/{}",path.replace('[',"/").replace(']',"").replace('.',"/"));
            if !removals.contains(&pointer) {
                if let Some(item) = value.pointer(&pointer) {
                    corrected_statements.insert(path.clone(), statement_identity(&path, item));
                }
            }
        }
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
    let repaired:Document=serde_json::from_value(value).map_err(|_|fail())?;
    super::validate(&repaired,units)?;
    Ok(AppliedRepair {document:repaired, corrected_statements})
}

#[cfg(test)]
#[test]
fn repair_reply_coalesces_only_identical_repeated_edits() {
    let patch = json!({"path":"topics[0].details[3]","text":"A同学提到大学生每年有三个月的假期。"});
    let repeated = vec![patch.clone(), patch.clone()];
    assert_eq!(unique_repair_rows(&repeated, true), Some(vec![&repeated[0]]));
    assert!(unique_repair_rows(&repeated, false).is_none());
    let conflicting = vec![patch, json!({"path":"topics[0].details[3]","text":"每年有六个月假期。"})];
    assert!(unique_repair_rows(&conflicting, true).is_none());
}

#[cfg(test)]
#[test]
fn statement_identity_survives_array_compaction_without_matching_a_different_question() {
    let issue = json!({"text":"交通安排尚未决定。"});
    assert_eq!(statement_identity("questions[3]", &issue), statement_identity("questions[1]", &issue));
    assert_ne!(statement_identity("questions[1]", &issue),
               statement_identity("questions[1]", &json!({"text":"会议日期尚未决定。"})));
    assert_ne!(statement_identity("questions[1]", &issue), statement_identity("decisions[1]", &issue));
}
pub(super) fn review_and_repair(endpoint:&str,model:&str,key:&str,client:&reqwest::blocking::Client,doc:&Document,units:&[Unit],start:Instant,trace:&mut Vec<Value>)->Result<Document,String> {
    review_and_repair_since(endpoint,model,key,client,doc,units,None,start,trace)
}
fn changed_failure_axis(previous:&(String,bool),status:&str,unclear:bool)->bool{
    // One existing repair opportunity may address a newly exposed ambiguity,
    // or a distinct scope error after ambiguity was actually removed. Repeated
    // ambiguity/scope and newly unsupported claims still stop immediately.
    (!previous.1&&unclear)||(previous.1&&!unclear&&status=="overstated")
}
fn newly_exposed_ambiguity(previous:Option<&str>,next:Option<&str>,claim:&Value)->bool{
    // A path may contain several independently unclear expressions. Progress
    // is the exact earlier offending span disappearing, not a different path
    // or a reviewer changing its reason. The original two-repair cap applies.
    let(Some(old),Some(new))=(previous,next)else{return false;};
    !old.is_empty()&&!new.is_empty()&&old!=new
        &&["text","owner","due"].into_iter().filter_map(|field|claim.get(field).and_then(Value::as_str)).all(|text|!text.contains(old))
}
fn repair_text_limit(path:&str)->usize{
    if path=="purpose"{80}else if path.ends_with(".title"){26}else if path.contains(".points["){90}else if path.contains(".details["){120}else{180}
}
fn oversized_repair_texts(raw:&str)->HashSet<String>{
    let Ok(value)=serde_json::from_str::<Value>(super::super::strip_code_fences(raw).trim())else{return HashSet::new();};
    value.get("changes").and_then(Value::as_array).into_iter().flatten().filter_map(|row|{
        let path=row.get("path")?.as_str()?;let text=row.get("text")?.as_str()?;
        (text.chars().count()>repair_text_limit(path)).then(||path.to_string())
    }).collect()
}
fn merge_shorter_repair_texts(original:&str,shortened:&str,paths:&HashSet<String>)->Result<String,String>{
    let fail=||"纪要字数恢复没有遵守原修正范围，已有结果保留。".to_string();
    let mut original:Value=serde_json::from_str(super::super::strip_code_fences(original).trim()).map_err(|_|fail())?;
    let shortened:Value=serde_json::from_str(super::super::strip_code_fences(shortened).trim()).map_err(|_|fail())?;
    let root=shortened.as_object().filter(|root|root.len()==1).ok_or_else(fail)?;
    let rows=root.get("changes").and_then(Value::as_array).filter(|rows|rows.len()==paths.len()).ok_or_else(fail)?;
    let edits=original.get_mut("changes").and_then(Value::as_array_mut).ok_or_else(fail)?;let mut seen=HashSet::new();
    for row in rows{
        let row=row.as_object().filter(|row|row.len()==2&&row.contains_key("path")&&row.contains_key("text")).ok_or_else(fail)?;
        let path=row["path"].as_str().filter(|path|paths.contains(*path)&&seen.insert(path.to_string())).ok_or_else(fail)?;
        let text=row["text"].as_str().filter(|text|super::line(text,repair_text_limit(path))).ok_or_else(fail)?;
        let edit=edits.iter_mut().find(|edit|edit["path"].as_str()==Some(path)).and_then(Value::as_object_mut).ok_or_else(fail)?;
        // Kind, owner, due, all other patches and original evidence stay exact.
        edit.insert("text".into(),json!(text));
    }
    Ok(original.to_string())
}
fn ranged_field(text: &str) -> impl Iterator<Item = (&str, (String, String, &str))> {
    static RANGE: std::sync::LazyLock<regex::Regex> = std::sync::LazyLock::new(|| {
        regex::Regex::new(r"([0-9０-９]{1,9}(?:[.．][0-9０-９]+)?)\s*(?:到|至|[-~～—－])\s*([0-9０-９]{1,9}(?:[.．][0-9０-９]+)?)\s*(岁|万元|美元|元|小时|分钟|工作日|周|天|个月|年|%|％|人|台|件)")
            .expect("numeric range pattern")
    });
    let digits = |value: &str| value.chars().map(|c| match c {
        '０'..='９' => char::from(b'0' + (c as u32 - '０' as u32) as u8),
        '．' => '.',
        _ => c,
    }).collect::<String>();
    RANGE.captures_iter(text).map(move |hit| {
        let part = |index| hit.get(index).unwrap().as_str();
        let unit = part(3);
        (part(0), (digits(part(1)), digits(part(2)), if unit == "％" { "%" } else { unit }))
    })
}

fn related_numeric_uncertainty(audit: &Audit, claims: &[Value], source: &[Sentence]) -> HashMap<String, Value> {
    let supported = |path: &str| audit.claim_audit.iter().find(|claim| claim.path == path)
        .is_none_or(|claim| claim.status == "supported");
    let mut related = HashMap::new();
    for issue in audit.claim_audit.iter().filter(|claim| source_wording_unclear(claim)) {
        let Some((_, quantity)) = issue.unclear_text.as_deref().and_then(|text| ranged_field(text).next()) else { continue; };
        let units: HashSet<_> = source.iter().filter(|row| issue.evidence.contains(&row.id))
            .map(|row| row.source.as_str()).collect();
        for peer in claims {
            let path = peer["path"].as_str().unwrap();
            let Some((span, _)) = peer["text"].as_str().and_then(|text|
                ranged_field(text).find(|(_, key)| key == &quantity)) else { continue; };
            if path == issue.path || !supported(path) || !peer["sources"].as_array().is_some_and(|ids|
                ids.iter().filter_map(Value::as_str).any(|id| units.contains(id)))
            { continue; }
            related.entry(statement_identity(path, peer)).or_insert_with(|| json!({
                "priorPath":issue.path, "uncertainValue":span,
                "evidence":issue.evidence, "reason":issue.reason
            }));
        }
    }
    related
}

fn reject_unresolved_settlement(audit: &mut Audit, expected: &[Value]) {
    for verdict in audit.claim_audit.iter_mut().filter(|claim| claim.status == "supported") {
        let Some(field) = expected.iter().find(|claim| claim["path"] == verdict.path) else { continue; };
        let context = &field["relatedUncertainty"];
        let Some(quantity) = context["uncertainValue"].as_str() else { continue; };
        let text = field["text"].as_str().unwrap();
        let settlement = ["达成共识", "形成共识", "已达成", "已定下", "已定案", "已敲定", "已确定", "决定为"]
            .iter().any(|term| text.contains(term))
            || text.split(['。', '；', ';']).any(|part| part.contains("形成") && part.contains("共识") && part.contains(quantity));
        if !settlement {
            continue;
        }
        let Some(disputed) = context["evidence"].as_array() else { continue; };
        if !verdict.evidence.iter().all(|id| disputed.iter().any(|earlier| earlier == id.as_str())) {
            continue;
        }
        verdict.status = "unclear".into();
        verdict.clarity = Some("unclear".into());
        verdict.unclear_text = Some(quantity.to_owned());
        verdict.reason = "本条仍写成已定，引用的是先前无法确认同一数值的原话，未有独立定案依据。".into();
    }
}

fn unsupported_confirmation(issues: &[Value], claims: &[Value], source: &[Sentence]) -> Option<String> {
    let changes = issues.iter().map(|issue| {
        let reason = issue["reason"].as_str()?;
        let original = claims.iter().find(|claim| claim["path"] == issue["path"])?["text"].as_str()?;
        let (before, rest) = original.split_once("询问并确认")?;
        let first = rest.split(['。', '；', ';', '！']).next()?;
        let questions = issue["evidence"].as_array()?;
        if issue["status"] != "overstated"
            || !["没有明确回答", "没有回答", "未有明确回应", "没有得到确认"].iter().any(|term| reason.contains(term))
            || !["是否", "能否", "有没有", "怎么", "何时"].iter().any(|cue| first.contains(cue))
            || !source.iter().any(|row| questions.iter().any(|id| id == row.id.as_str())
                && ["是否", "是吧", "吗", "么", "？", "?"].iter().any(|cue| row.text.contains(cue)))
        {
            return None;
        }
        Some(json!({"path":issue["path"],"text":format!("{before}询问{rest}")}))
    }).collect::<Option<Vec<_>>>()?;
    (!changes.is_empty()).then(|| json!({"changes":changes}).to_string())
}

fn retain_mentioned_comparison(
    issues: &[Value], claims: &[Value], source: &[Sentence], attempted: &HashMap<String, (String, bool)>,
) -> Option<String> {
    const QUALIFIERS: &[&str] = &["也高", "也低", "也很高", "也很低", "同样高", "同样低"];
    let changes = issues.iter().map(|issue| {
        let path = issue["path"].as_str()?;
        if issue["status"] != "overstated" || issue["clarity"] != "unclear"
            || !path.starts_with("topics[") || path.ends_with(".title")
        {
            return None;
        }
        let claim = claims.iter().find(|claim| claim["path"] == path)?;
        let (previous, unclear) = attempted.get(&statement_identity(path, claim))?;
        if previous != "overstated" || *unclear { return None; }
        let original = claim["text"].as_str()?;
        let unclear = issue["unclearText"].as_str()?;
        let name = QUALIFIERS.iter().find_map(|suffix| unclear.strip_suffix(suffix))?;
        if !(2..=14).contains(&name.chars().count()) || !name.chars().all(char::is_alphanumeric)
            || original.matches(unclear).count() != 1
        {
            return None;
        }
        let (before, after) = original.split_once(unclear)?;
        if !before.ends_with(['、','，',',','；']) || !after.starts_with(['。','，','；',',',';']) {
            return None;
        }
        let previous_clause = before.trim_end_matches(['、','，',',','；']);
        let reason = issue["reason"].as_str()?;
        let reported = issue["evidence"].as_array()?;
        if !["未明确", "未说明", "没有说明", "没有确认"].iter().any(|cue| reason.contains(cue))
            || !["可能", "或许", "大约"].iter().any(|cue| previous_clause.contains(cue))
            || !source.iter().any(|sentence| reported.iter().any(|id| id == sentence.id.as_str())
                && sentence.text.contains(name))
            || source.iter().any(|sentence| reported.iter().any(|id| id == sentence.id.as_str())
                && (sentence.text.contains(unclear) || sentence.text.match_indices(name).any(|(at, _)| {
                    let rest = &sentence.text[at + name.len()..];
                    let clause = rest.split(['，','。','；','\n']).next().unwrap_or_default();
                    QUALIFIERS.iter().any(|cue| clause.contains(cue))
                })))
        {
            return None;
        }
        let edited = format!("{previous_clause}，另提到「{name}」（具体情况待核实）{after}");
        super::line(&edited, repair_text_limit(path)).then(|| json!({"path":path,"text":edited}))
    }).collect::<Option<Vec<_>>>()?;
    (!changes.is_empty()).then(|| json!({"changes":changes}).to_string())
}

#[cfg(test)]
#[test]
fn a_second_review_can_qualify_one_independent_comparison() {
    let path = "topics[2].details[2]";
    let claim = json!({"path":path,"text":"建议按每日活跃人数选平台，提到甲站日活可能超过3亿、乙站也高。"});
    let issue = json!({"path":path,"status":"overstated","clarity":"unclear","unclearText":"乙站也高",
        "reason":"原话提到乙站日活，未明确说乙站也高。","evidence":["e0001","e0002"]});
    let mut source = vec![Sentence{id:"e0001".into(),source:"u000".into(),text:"按每日活跃人数，甲站可能有".into()},
        Sentence{id:"e0002".into(),source:"u000".into(),text:"超过3亿嘛，还有乙站这种日活。".into()}];
    let prior = HashMap::from([(statement_identity(path,&claim),("overstated".into(),false))]);
    let actual = retain_mentioned_comparison(&[issue.clone()],&[claim.clone()],&source,&prior).unwrap();
    assert_eq!(serde_json::from_str::<Value>(&actual).unwrap()["changes"][0]["text"],
        "建议按每日活跃人数选平台，提到甲站日活可能超过3亿，另提到「乙站」（具体情况待核实）。");
    assert!(retain_mentioned_comparison(&[issue.clone()],&[claim.clone()],&source,&HashMap::new()).is_none());
    source[1].text = "超过3亿嘛；乙站日活也很高。".into();
    assert!(retain_mentioned_comparison(&[issue],&[claim],&source,&prior).is_none());
}

fn unclear_optional_action_as_quote(issues: &[Value], claims: &[Value], source: &[Sentence]) -> Option<String> {
    let changes = issues.iter().map(|issue| {
        let path = issue["path"].as_str()?;
        if !path.starts_with("actionItems[") || issue["status"] != "unclear" || issue["placementUnsupported"] != true {
            return None;
        }
        let claim = claims.iter().find(|claim| claim["path"] == path)?;
        if !claim["due"].is_null() { return None; }
        let owner = claim["owner"].as_str()?.trim();
        let term = issue["unclearText"].as_str()?.trim();
        let current = claim["text"].as_str()?;
        if owner.is_empty() || term.is_empty() || !current.contains(term)
            || !current.strip_prefix(owner)?.trim_start_matches([' ', '，', '：']).starts_with("可以")
        {
            return None;
        }
        let [anchor] = issue["evidence"].as_array()?.as_slice() else { return None; };
        let unit = source.iter().find(|sentence| anchor == sentence.id.as_str()
            && claim["sources"].as_array().is_some_and(|sources| sources.iter().any(|id| id == sentence.source.as_str())))?;
        let quote = super::super::source_resolution::split_turn_label(&unit.text)
            .map_or(unit.text.as_str(), |(_, speech)| speech).trim();
        let (lead, action) = quote.split_once(owner)?;
        if !action.trim_start_matches([' ', '儿']).starts_with("可以")
            || ["不是", "不能", "不要", "不得"].iter().any(|marker| lead.contains(marker))
            || !super::line(quote, 96) || quote.contains(term) || quote.contains(['「', '」'])
        {
            return None;
        }
        // Independent re-audit rejected the task role and the replacement
        // term. Keep the complete source proposal and its pending status.
        Some(json!({"path":path,"text":format!("{PENDING_PROPOSAL_PREFIX}{quote}{PENDING_PROPOSAL_SUFFIX}")}))
    }).collect::<Option<Vec<_>>>()?;
    (!changes.is_empty()).then(|| json!({"changes":changes}).to_string())
}

#[cfg(test)]
#[test]
fn rejected_optional_actions_keep_exact_wording_and_pending_status() {
    let claim = json!({"path":"actionItems[0]","owner":"保安部","due":null,
        "text":"保安部可以向财务部申请报批，把盲区补上。","sources":["u002"]});
    let issue = json!({"path":"actionItems[0]","status":"unclear","placementUnsupported":true,
        "unclearText":"申请报批","evidence":["e0051"]});
    let source = [Sentence{id:"e0051".into(),source:"u002".into(),
        text:"说话人2: 那保安部儿可以向财务部申请一个报表儿把盲区补上".into()}];
    let repair = unclear_optional_action_as_quote(&[issue.clone()], &[claim.clone()], &source).unwrap();
    let repair: Value = serde_json::from_str(&repair).unwrap();
    assert_eq!(repair["changes"][0]["text"], "会上讨论「那保安部儿可以向财务部申请一个报表儿把盲区补上」。其中具体用语待核实。");
    let mut confirmed = issue;
    confirmed["placementUnsupported"] = json!(false);
    assert!(unclear_optional_action_as_quote(&[confirmed], &[claim], &source).is_none());
}

fn preserves_unclear_history(doc:&Document,history:&HashMap<String,Vec<String>>)->Result<(),String>{
    let value=serde_json::to_value(doc).map_err(|_|"纪要含混表达历史核对未完成，已有结果保留。")?;
    for(path,phrases)in history{
        let pointer=format!("/{}",path.replace('[',"/").replace(']',"").replace('.',"/"));
        if let Some(target)=value.pointer(&pointer){
            let texts=if let Some(text)=target.as_str(){vec![text]}else{["text","owner","due"].into_iter().filter_map(|field|target.get(field).and_then(Value::as_str)).collect()};
            if phrases.iter().any(|phrase|texts.iter().any(|text|text.contains(phrase))){return Err("纪要修正重新引入了已否决的含混表达，已有结果保留。".into());}
        }
    }
    Ok(())
}

fn vague_assignment_quote(issue: &Value, claim: &Value, text: &str, source: &[Sentence]) -> Option<String> {
    if issue["placementUnsupported"] != true || claim["kind"] != "action" || !claim["due"].is_null() {
        return None;
    }
    let term = issue["unclearText"].as_str()?.trim();
    let owner = claim["owner"].as_str()?.trim();
    let original = claim["text"].as_str()?.trim();
    let inserted = text.trim().trim_end_matches(['。', '！', '？', '.']);
    if term.is_empty() || owner.is_empty() || !inserted.contains(term)
        || !["待核对", "待核实"].iter().any(|suffix| inserted.ends_with(suffix))
        || original.strip_prefix(owner)?.trim_start_matches([' ', '：', ':', '，', ','])
            .trim_end_matches(['。', '！', '？', '.']) != term
    {
        return None;
    }
    let cited = issue["evidence"].as_array()?;
    let units = claim["sources"].as_array()?;
    let mut quotes = source.iter().filter(|sentence| {
        cited.iter().any(|id| id == sentence.id.as_str())
            && units.iter().any(|unit| unit == sentence.source.as_str())
    }).map(|sentence| sentence.text.trim()).filter(|quote| {
        super::line(quote, 180) && quote.contains(owner)
    });
    let quote = quotes.next()?;
    quotes.next().is_none().then(|| quote.to_owned())
}

fn hold_unresolved_source(
    raw: &str, issues: &[Value], claims: &[Value], source: &[Sentence],
    history: &HashMap<String, Vec<String>>, allow_repeated_detail: bool,
) -> Option<(String, Vec<String>)> {
    let mut reply: Value = serde_json::from_str(super::super::strip_code_fences(raw).trim()).ok()?;
    let rows = reply.get_mut("changes")?.as_array_mut()?;
    unique_repair_rows(rows, true)?;
    let mut pending = Vec::new();
    for row in rows {
        let Some(text) = row["text"].as_str().filter(|_| row.as_object().is_some_and(|edit| edit.len() == 2))
        else { continue; };
        let Some(path) = row["path"].as_str() else { continue; };
        let Some(issue) = issues.iter().find(|issue| issue["path"] == path && issue["status"] == "unclear")
        else { continue; };
        if path.starts_with("actionItems[") {
            if let Some(quote) = claims.iter().find(|claim| claim["path"] == path)
                .and_then(|claim| vague_assignment_quote(issue, claim, text, source))
            {
                pending.push(quote);
                *row = json!({"path":path,"remove":true});
            }
            continue;
        }
        if !allow_repeated_detail || !path.starts_with("topics[") || !path.contains(".details[") {
            continue;
        }
        // The opaque placeholder was introduced by the earlier conservative edit.
        // Only a continued failure of this detail can fall back to a literal quote.
        let Some(phrase) = issue["unclearText"].as_str().filter(|term| *term == "含混表述")
        else { continue; };
        let Some(claim) = claims.iter().find(|claim| claim["path"] == path
            && claim["text"].as_str().is_some_and(|text| text.contains(phrase)))
        else { continue; };
        if !history.get(path).is_some_and(|terms| terms.iter().any(|term| term == phrase)
            && terms.iter().any(|term| term != phrase && text.contains(term)))
        {
            continue;
        }
        let Some([id]) = issue["evidence"].as_array().map(Vec::as_slice) else { continue; };
        let Some(sentence) = source.iter().find(|sentence| id == sentence.id.as_str()
            && claim["sources"].as_array().is_some_and(|sources| sources.iter().any(|value| value == &sentence.source)))
        else { continue; };
        let quote = sentence.text.trim();
        if !super::line(quote, 180) { continue; }
        pending.push(quote.to_owned());
        *row = json!({"path":path,"remove":true});
    }
    (!pending.is_empty()).then(|| (reply.to_string(), pending))
}

#[cfg(test)]
#[test]
fn known_unclear_detail_is_held_without_rewriting_an_independent_edit() {
    let path = "topics[0].details[0]";
    let peer = json!({"path":"topics[0].details[1]","text":"由区域经理发问。"});
    let proposal = json!({"changes":[{"path":path,"text":"确定转到老站交接，具体所指待核实。"},peer]});
    let issues = [json!({"path":path,"status":"unclear","unclearText":"含混表述","evidence":["e0001"]})];
    let claim = json!({"path":path,"text":"提到含混表述，具体所指待核对。","sources":["u001"]});
    let history = HashMap::from([(path.to_owned(),vec!["老站交接".into(),"含混表述".into()])]);
    let source = [Sentence {id:"e0001".into(),source:"u001".into(),text:"原话提到那个站的交接。".into()}];
    let (patch, quotes) = hold_unresolved_source(&proposal.to_string(), &issues, &[claim.clone()], &source, &history, true).unwrap();
    assert_eq!(serde_json::from_str::<Value>(&patch).unwrap(),
        json!({"changes":[{"path":path,"remove":true},peer]}));
    assert_eq!(quotes, ["原话提到那个站的交接。"]);

    let wrong_source = [Sentence {source:"u002".into(),..source[0].clone()}];
    assert!(hold_unresolved_source(&proposal.to_string(), &issues, &[claim.clone()], &wrong_source, &history, true).is_none());
    assert!(hold_unresolved_source(&proposal.to_string(), &issues, &[claim], &source, &HashMap::new(), true).is_none());
}

#[cfg(test)]
#[test]
fn wholly_vague_action_is_kept_as_a_source_quote_without_removing_a_concrete_task() {
    let path = "actionItems[0]";
    let issue = json!({"path":path,"status":"unclear","placementUnsupported":true,
        "unclearText":"做好相关安排","evidence":["e0001","e0002"]});
    let claim = json!({"path":path,"kind":"action","owner":"负责人","due":null,
        "text":"负责人做好相关安排。","sources":["u001"]});
    let patch = json!({"changes":[{"path":path,"text":"提醒负责人做好相关安排，具体任务待核对。"}]}).to_string();
    let source = [
        Sentence{id:"e0001".into(),source:"u001".into(),text:"负责人这边做好这个相关的安排。".into()},
        Sentence{id:"e0002".into(),source:"u001".into(),text:"然后就散会。".into()},
    ];
    let (repair, pending) = hold_unresolved_source(&patch, &[issue.clone()], &[claim.clone()], &source, &HashMap::new(), false).unwrap();
    assert_eq!(serde_json::from_str::<Value>(&repair).unwrap()["changes"][0], json!({"path":path,"remove":true}));
    assert_eq!(pending, [source[0].text.as_str()]);
    let mut concrete = claim;
    concrete["text"] = json!("负责人送出验收报告并做好相关安排。");
    assert!(hold_unresolved_source(&patch, &[issue], &[concrete], &source, &HashMap::new(), false).is_none());
}

fn unverified_claims(doc:&Document,verified:Option<&Document>)->Vec<Value> {
    let previous=verified.map(claims).unwrap_or_default().into_iter().map(|claim|(claim["path"].as_str().unwrap().to_string(),claim)).collect::<HashMap<_,_>>();
    claims(doc).into_iter().filter(|claim|previous.get(claim["path"].as_str().unwrap())!=Some(claim)).collect()
}

fn source_assertion_identity(doc: &Document, claim: &Value) -> String {
    let path = claim["path"].as_str().unwrap();
    let topic = path.strip_prefix("topics[").and_then(|path| path.split_once(']'))
        .and_then(|(index, _)| index.parse::<usize>().ok()).and_then(|index| doc.topics.get(index));
    json!([statement_identity(path, claim), topic.map(|topic| &topic.title), claim["sources"]]).to_string()
}

fn unchanged_source_assertions(doc: &Document, verified: &Document) -> HashMap<String, Value> {
    let previous: HashSet<_> = claims(verified).iter().map(|claim| source_assertion_identity(verified, claim)).collect();
    claims(doc).into_iter().filter(|claim| previous.contains(&source_assertion_identity(doc, claim)))
        .map(|claim| (claim["path"].as_str().unwrap().to_owned(), claim)).collect()
}

fn carry_verified_after_scoped_repair(next: &Document, current: &Document,
    verified: &mut HashMap<String, Value>, evidence: &mut HashMap<String, Vec<String>>,
) {
    let mut by_assertion = HashMap::new();
    for claim in claims(current) {
        let path = claim["path"].as_str().unwrap();
        if verified.get(path) == Some(&claim) {
            let bound = evidence.get(path).cloned();
            by_assertion.insert(source_assertion_identity(current, &claim), bound);
        }
    }
    verified.clear();
    evidence.clear();
    for claim in claims(next) {
        if let Some(bound) = by_assertion.get(&source_assertion_identity(next, &claim)) {
            let path = claim["path"].as_str().unwrap().to_owned();
            if let Some(bound) = bound { evidence.insert(path.clone(), bound.clone()); }
            verified.insert(path, claim);
        }
    }
}

// A disputed speaker label can be removed without guessing a new actor.
// The independent verdict must already accept the task's placement, and the
// exact unclear label must be the beginning of the existing task text.
fn undisputed_action_text(issues: &[Value], claims: &[Value]) -> Option<String> {
    let changes = issues.iter().map(|issue| {
        let path = issue["path"].as_str()?.strip_prefix("actionItems[")?;
        if issue["placementUnsupported"] != false || path.is_empty() {
            return None;
        }
        let claim = claims.iter().find(|claim| claim["path"] == issue["path"])?;
        let owner = claim["owner"].as_str()?;
        if owner.is_empty() {
            return None;
        }
        let body = claim["text"].as_str()?.strip_prefix(owner)?
            .trim_start_matches([' ', '，', ',', '：', ':']);
        if body.chars().count() < 8 || body.contains(owner) || body.starts_with(|ch: char| ch.is_ascii_digit()) {
            return None;
        }
        let body = body.trim_end_matches(['。', '！', '；', '.', ';']);
        let text = format!("{body}。负责人待核实。");
        if !super::line(&text, 180) { return None; }
        if issue["status"] == "unclear" && issue["unclearText"] == owner {
            return Some(json!({"path":issue["path"],"text":text}));
        }
        // A sourced verdict can also reject a named assignee explicitly while
        // restating the task as a real request. Keep the task, and independently
        // re-audit it with no substituted assignee.
        let reason = issue["reason"].as_str()?;
        let (confirmed_task, after_owner) = reason.split_once(&format!("不是{owner}"))?;
        let shares_task: Vec<_> = body.chars().collect();
        let same_task = shares_task.windows(4).any(|span| confirmed_task.contains(&span.iter().collect::<String>()));
        (issue["status"] == "unsupported" && confirmed_task.contains("原文") && confirmed_task.contains("要求")
            && same_task && after_owner.starts_with(['，','；','。',',',';','。']))
            .then(|| json!({"path":issue["path"],"text":text,"owner":null}))
    }).collect::<Option<Vec<_>>>()?;
    (!changes.is_empty()).then(|| json!({"changes":changes}).to_string())
}

fn relocate_ownerless_requirements(issues: &[Value], claims: &[Value]) -> Option<String> {
    let changes = issues.iter().map(|issue| {
        let path = issue["path"].as_str()?;
        if !path.starts_with("actionItems[") || issue["status"] != "overstated"
            || issue["clarity"] != "clear" || issue["placementUnsupported"] != true {
            return None;
        }
        let claim = claims.iter().find(|claim| claim["path"] == issue["path"])?;
        let text = claim["text"].as_str()?;
        (claim["owner"].is_null() && claim["due"].is_null() && super::line(text, 120))
            .then(|| json!({"path":path,"text":text}))
    }).collect::<Option<Vec<_>>>()?;
    (!changes.is_empty()).then(|| json!({"changes":changes}).to_string())
}

#[cfg(test)]
#[test]
fn unchanged_source_assertion_keeps_evidence_after_a_neighbor_is_removed() {
    let previous: Document = serde_json::from_value(json!({
        "purpose":"协调采购",
        "topics":[{"title":"物流","points":[{"kind":"status","text":"物流已联系。","sources":["u000"]}]}],
        "actionItems":[{"text":"讨论运输。","sources":["u000"]},{"text":"张敏提交报价。","owner":"张敏","sources":["u001"]}],
        "decisions":[],"questions":[]
    })).unwrap();
    let mut next = previous.clone();
    next.action_items.remove(0);
    assert!(unchanged_source_assertions(&next, &previous).contains_key("actionItems[0]"));
    next.action_items[0].sources = vec!["u000".into()];
    assert!(!unchanged_source_assertions(&next, &previous).contains_key("actionItems[0]"));
}
// The caller keeps the same immutable source and a document just verified in
// this invocation. Unchanged claims retain that evidence; new/changed claims
// still see the complete original source, never a model inventory.
pub(super) fn review_and_repair_since(endpoint:&str,model:&str,key:&str,client:&reqwest::blocking::Client,doc:&Document,units:&[Unit],verified:Option<&Document>,start:Instant,trace:&mut Vec<Value>)->Result<Document,String> {
    let mut draft = FactualDraft { document: doc.clone(), pending_quotes: Vec::new() };
    review(endpoint,model,key,client,&mut draft,units,verified,&[],start,trace).map(|result| result.document)
}

fn same_assertion(left: &Value, right: &Value) -> bool {
    ["text", "owner", "due"].iter().all(|field| left[*field] == right[*field])
}

pub(super) struct VerifiedBrief {
    pub(super) document: Document,
    pub(super) evidence: HashMap<String, Vec<String>>,
    pub(super) pending_quotes: Vec<String>,
}

pub(super) struct FactualDraft {
    pub(super) document: Document,
    pub(super) pending_quotes: Vec<String>,
}

pub(super) fn review_and_repair_with_conflicts(endpoint:&str,model:&str,key:&str,client:&reqwest::blocking::Client,draft:&mut FactualDraft,units:&[Unit],conflicts:&[Value],start:Instant,trace:&mut Vec<Value>)->Result<VerifiedBrief,String> {
    review(endpoint,model,key,client,draft,units,None,conflicts,start,trace)
}

fn finish_conflicts(doc: Document, conflicts: &[Value], supported: &HashSet<usize>) -> Result<Document,String> {
    if conflicts.is_empty() {
        return Ok(doc);
    }
    let final_claims = claims(&doc);
    if conflicts.iter().enumerate().any(|(index, conflict)| !supported.contains(&index)
        && final_claims.iter().any(|claim| same_assertion(claim, &conflict["claim"]))) {
        return Err("纪要中仍有原话与正文冲突，已有结果保留。".into());
    }
    Ok(doc)
}

#[cfg(test)]
#[test]
fn a_requested_move_respects_the_topic_detail_limit() {
    let units = vec![Unit {id: "u000".into(), text: "讨论交付方法。".into()}];
    let full = (0..super::topic_details_limit()).map(|index| {
        json!({"text":format!("说明{index}。"),"sources":["u000"]})
    }).collect::<Vec<_>>();
    let mut doc = json!({"decisions":[{"text":"备选的交付方式。","sources":["u000"]}],
        "topics":[{"points":[{"text":"原议题","sources":["u000"]}],"details":full},
                  {"points":[{"text":"提交方案","sources":["u000"]}],"details":[]}]});
    assert!(demote_item(&mut doc, "/decisions/0", &units, Some(0), true).is_some());
    assert_eq!(doc["topics"][0]["details"].as_array().unwrap().len(), super::topic_details_limit());
    assert_eq!(doc["topics"][1]["details"][0]["text"], "备选的交付方式。");
}

fn review(endpoint:&str,model:&str,key:&str,client:&reqwest::blocking::Client,draft:&mut FactualDraft,units:&[Unit],verified:Option<&Document>,conflicts:&[Value],start:Instant,trace:&mut Vec<Value>)->Result<VerifiedBrief,String> {
    let source=sentences(units);
    let wire=json!(units.iter().map(|u|json!({"id":u.id,"sentences":source.iter().filter(|s|s.source==u.id).map(|s|json!({"id":s.id,"text":s.text})).collect::<Vec<_>>()})).collect::<Vec<_>>());
    let FactualDraft { document: current, pending_quotes } = draft;
    let mut attempted:HashMap<String,(String,bool)>=HashMap::new();let mut attempted_phrases:HashMap<String,String>=HashMap::new();let recovered_format=AtomicBool::new(false);
    let mut attribution_repairs = HashSet::new();
    let mut unclear_history:HashMap<String,Vec<String>>=HashMap::new();let mut recovered_display=false;
    let mut verified_claims = match verified {
        Some(verified) if super::source_items::enabled() => unchanged_source_assertions(current, verified),
        _ => verified.map(claims).unwrap_or_default().into_iter()
            .map(|claim| (claim["path"].as_str().unwrap().to_owned(), claim)).collect(),
    };
    let mut evidence = HashMap::new();
    let mut supported_conflicts = HashSet::new();
    let mut related = HashMap::new();
    for round in 0..=2 {
        let mut expected=claims(&current).into_iter().filter(|c|verified_claims.get(c["path"].as_str().unwrap())!=Some(c)).collect::<Vec<_>>();
        if expected.is_empty(){
            let document=finish_conflicts(current.clone(),conflicts,&supported_conflicts)?;
            return Ok(VerifiedBrief {document,evidence,pending_quotes: std::mem::take(pending_quotes)});
        }
        // Late review gets the full immutable source and the changed statements.
        // Whole-unit qualifier matches can highlight unrelated nearby content.
        if !super::source_items::enabled() || verified.is_none() {
            emphasize_source_scope(&mut expected,&source);
        }
        for claim in &mut expected {
            if let Some(context) = related.remove(&statement_identity(claim["path"].as_str().unwrap(), claim)) {
                claim["relatedUncertainty"] = context;
            }
            let competing: Vec<_> = conflicts.iter().filter(|conflict| same_assertion(claim, &conflict["claim"]))
                .map(|conflict| &conflict["evidence"]).collect();
            if !competing.is_empty() {
                claim["competingSourceIds"] = json!(competing);
            }
        }
        let stage=match round{0=>"source-factual-audit",1=>"source-factual-reaudit",_=>"source-factual-reaudit-2"};
        // Only earlier completed verdicts constrain new/changed claims. Do not
        // retroactively rewrite other claims in this same independent batch.
        let history=trace.iter().filter_map(|c|c.get("unclearClaimHistory").and_then(Value::as_array)).flatten().cloned().collect::<Vec<_>>();
        let mut audit=partitioned_audit(endpoint,model,key,client,&current,&wire,&expected,&source,stage,start,trace,&recovered_format)?;
        if super::source_items::enabled() {
            reject_unresolved_settlement(&mut audit, &expected);
        }
        let vetoed=apply_historical_veto(&mut audit,&expected,&history,&source);
        if !vetoed.is_empty(){if let Some(call)=trace.last_mut(){call["historicalUnclearVetoes"]=json!(vetoed);}}
        // Bind original jumps to the exact immutable evidence actually checked,
        // rather than retaining an earlier writer's incomplete source list.
        *current=bind_supported_sources(current,&audit,&source,units)?;
        let audited_claims=claims(&current);
        // Retain only exact in-call positive claims. Changed text, kind,
        // refs, owner/due, or shifted array positions are automatically audited.
        for verdict in audit.claim_audit.iter().filter(|c|c.status=="supported") {
            if let Some(claim)=audited_claims.iter().find(|c|c["path"].as_str()==Some(verdict.path.as_str())){
                verified_claims.insert(verdict.path.clone(),claim.clone());
                evidence.insert(verdict.path.clone(),verdict.evidence.clone());
                for (index, conflict) in conflicts.iter().enumerate().filter(|(_, conflict)| same_assertion(claim, &conflict["claim"])) {
                    if verdict.evidence.iter().any(|id| conflict["evidence"].as_str() == Some(id.as_str())) {
                        supported_conflicts.insert(index);
                    } else {
                        supported_conflicts.remove(&index);
                    }
                }
            }
        }
        let issues=audit.claim_audit.iter().filter(|c|c.status!="supported").map(|c|{
            let mut issue=json!({"path":c.path,"status":c.status,"clarity":c.clarity,"unclearText":c.unclear_text,"reason":c.reason,"evidence":c.evidence});
            if let Some(misplaced)=c.placement_unsupported{issue["placementUnsupported"]=json!(misplaced);}
            issue
        }).collect::<Vec<_>>();
        if issues.is_empty(){
            let document=finish_conflicts(current.clone(),conflicts,&supported_conflicts)?;
            return Ok(VerifiedBrief {document,evidence,pending_quotes: std::mem::take(pending_quotes)});
        }
        let allowed=audit.claim_audit.iter().filter(|c|c.status!="supported").map(|c|c.path.clone()).collect::<HashSet<_>>();
        let misplaced=audit.claim_audit.iter().filter(|c|super::source_items::enabled()&&c.placement_unsupported==Some(true))
            .map(|c|c.path.clone()).collect::<HashSet<_>>();
        let allow_conservative = super::coverage::enabled() || super::source_items::enabled();
        // Repeated feedback stops. A changed failure axis, or a different
        // unclear span after the earlier span was actually removed, can use
        // the remaining second repair. Neither the cap nor history resets.
        let repeated=audit.claim_audit.iter().filter(|c|c.status!="supported").any(|c|{
            let Some(claim)=audited_claims.iter().find(|claim|claim["path"].as_str()==Some(c.path.as_str())) else {return false;};
            let key = if super::source_items::enabled() { statement_identity(&c.path, claim) } else { c.path.clone() };
            let distinct_ambiguity=source_wording_unclear(c)&&newly_exposed_ambiguity(
                attempted_phrases.get(&key).map(String::as_str),c.unclear_text.as_deref(),claim);
            attempted.get(&key).is_some_and(|old|{
                let sourced_new_issue = super::source_items::enabled() && old.1 && c.status == "unsupported"
                    && !source_wording_unclear(c) && !c.evidence.is_empty();
                let modality_after_attribution = super::source_items::enabled()
                    && attribution_repairs.contains(&key) && c.status == "overstated"
                    && ["疑问", "试探", "推测"].iter().any(|term| c.reason.contains(term))
                    && source.iter().any(|sentence| c.evidence.contains(&sentence.id)
                        && ["会不会", "是不是", "能不能", "是否", "可能"]
                            .iter().any(|term| sentence.text.contains(term)));
                !(allow_conservative&&(changed_failure_axis(old,&c.status,c.status=="unclear"||source_wording_unclear(c))
                    ||distinct_ambiguity||sourced_new_issue||modality_after_attribution))
            })
        });
        // A re-audit can identify a different defect after attribution was fixed.
        // Remove only the explicit false link, with its two separately cited witnesses.
        let bounded_repair = if round == 1 && super::source_items::enabled() {
            repair_separately_cited_examples(&issues, &audited_claims, &source)
                .map(|raw| (raw, "localSeparateExampleRepair"))
                .or_else(|| unsupported_confirmation(&issues, &audited_claims, &source)
                    .map(|raw| (raw, "localQuestionModalityRepair")))
                .or_else(|| retain_mentioned_comparison(&issues, &audited_claims, &source, &attempted)
                    .map(|raw| (raw, "localMentionedComparisonRepair")))
        } else { None };
        if round==2||(repeated && bounded_repair.is_none()) {
            return Err(format!("纪要复审仍有{}处未解决表述，已有结果保留。",issues.len()));
        }
        let unclear=audit.claim_audit.iter().filter(|c|c.status=="unclear"||source_wording_unclear(c)).map(|c|c.path.clone()).collect::<HashSet<_>>();
        if allow_conservative{for issue in audit.claim_audit.iter().filter(|c|source_wording_unclear(c)){
            if let Some(phrase)=&issue.unclear_text{let terms=unclear_history.entry(issue.path.clone()).or_default();if !terms.contains(phrase){terms.push(phrase.clone());}}
        }}
        let conservative=if allow_conservative{audit.claim_audit.iter().filter(|c|source_wording_unclear(c)).filter_map(|c|{
            let phrase=c.unclear_text.as_ref()?;
            audited_claims.iter().find(|claim|claim["path"].as_str()==Some(c.path.as_str()))?
                .get("text")?.as_str()?.contains(phrase).then(||(c.path.clone(),vec![phrase.clone()]))
        }).collect::<HashMap<_,_>>()}else{HashMap::new()};
        let deletion_only=unclear.iter().filter(|path|!conservative.contains_key(*path)).cloned().collect::<HashSet<_>>();
        // Keep semantically identical scoped requests byte-identical for
        // receipt reuse. Hash-backed membership checks do not define wire order.
        let mut repair_paths: Vec<_> = allowed.iter().collect();
        repair_paths.sort_unstable();
        let repair_contracts=repair_paths.into_iter().map(|path|
            json!({"path":path,"maxCharacters":if misplaced.contains(path){120}else{repair_text_limit(path)},
            "textOnlyConservative":conservative.contains_key(path)})).collect::<Vec<_>>();
        let mut deletion_paths: Vec<_> = deletion_only.iter().collect();
        deletion_paths.sort_unstable();
        let stage=if round==0{"source-factual-repair"}else{"source-factual-repair-2"};
        let mut payload=json!({"sourceUnits":wire,"previousDocument":current,"auditProblems":issues,
            "deletionOnlyPaths":deletion_paths,"conservativeRewritePaths":conservative.iter().collect::<std::collections::BTreeMap<_,_>>(),
            "knownUnclearPhrases":unclear_history.iter().collect::<std::collections::BTreeMap<_,_>>(),"repairContracts":repair_contracts});
        if super::source_items::enabled() {
            payload["roleCorrectionContract"]=json!("placementUnsupported为true的决定、交办或未决条目将由程序移出原栏目。仍有用的内容只返回path和120字内text，写清实际是意见、现状、设想或已回答的提问；程序保留出处并放入相关主题，之后独立复审。完全无依据、散会或重复无用条目可remove:true。不要在text内继续称已定案。只有需要指定补充主题且不含糊时，才附moveToTopic的已有主题下标。");
        }
        let scoped = super::source_items::enabled() && verified.is_some();
        let local = if bounded_repair.is_some() {
            bounded_repair
        } else if scoped {
            unclear_optional_action_as_quote(&issues, &audited_claims, &source)
                .map(|raw| (raw, "localUnclearProposalQuote"))
                .or_else(|| undisputed_action_text(&issues, &audited_claims).map(|raw| (raw, "localUnclearActionRepair")))
                .or_else(|| relocate_ownerless_requirements(&issues, &audited_claims)
                    .map(|raw| (raw, "localOwnerlessRequirementMove")))
        } else { None };
        let raw = match local {
            Some((raw, operation)) => {
                if let Some(call) = trace.last_mut() { call[operation] = json!(true); }
                raw
            },
            None => super::request(endpoint,model,key,client,REPAIR,payload.clone(),super::coverage::enabled(),start,trace,stage)?,
        };
        let (raw, normalized) = if super::source_items::enabled() {
            normalize_repair_reply(&raw, &issues, &source, &audited_claims)
        } else { (raw, 0) };
        if normalized > 0 {
            if let Some(call) = trace.last_mut() {
                call["sourceBoundRepairNormalization"] = json!(normalized);
            }
        }
        let (raw, newly_pending) = if super::source_items::enabled() {
            hold_unresolved_source(&raw, &issues, &audited_claims, &source, &unclear_history, round == 1)
                .unwrap_or((raw, Vec::new()))
        } else {
            (raw, Vec::new())
        };
        let next=match apply_repair(&raw,&current,&allowed,&unclear,&conservative,&misplaced,units,scoped){
            Ok(doc)=>doc,
            Err(reason)if super::coverage::enabled()&&!recovered_display&&reason.contains("须为")&&!oversized_repair_texts(&raw).is_empty()=>{
                // An oversized patch has not been applied. Recover only its
                // text once, keep valid patches exact, then use every original
                // scope/history/shape guard and independently audit all changes.
                recovered_display=true;let paths=oversized_repair_texts(&raw);
                payload["previousResult"]=json!(raw);payload["formatOnlyTextPaths"]=json!(paths);payload["formatProblems"]=json!([reason]);
                payload["instruction"]=json!("本次只缩短formatOnlyTextPaths列出的超长text，按repairContracts保留必要条件、否定、范围、人物及不确定性，不改kind/owner/due，不补事实、不截断原句。其它有效patch由程序原样保留，不要返回。只返回changes，每项仅path和text，列出的每个path恰好一次。随后仍会完整复审。");
                let fixed=super::request(endpoint,model,key,client,REPAIR,payload,true,start,trace,&format!("{stage}-length-recovery"))?;
                let merged=merge_shorter_repair_texts(&raw,&fixed,&paths)?;
                apply_repair(&merged,&current,&allowed,&unclear,&conservative,&misplaced,units,scoped)?
            },
            Err(reason)=>return Err(reason),
        };
        preserves_unclear_history(&next.document,&unclear_history)?;
        if !newly_pending.is_empty() {
            if let Some(call) = trace.last_mut() { call["sourceWordingPending"] = json!(&newly_pending); }
            pending_quotes.extend(newly_pending);
        }
        if super::source_items::enabled() {
            related.extend(related_numeric_uncertainty(&audit, &audited_claims, &source));
            if !related.is_empty() {
                verified_claims.retain(|path, claim| !related.contains_key(&statement_identity(path, claim)));
            }
            carry_verified_after_scoped_repair(&next.document, &current, &mut verified_claims, &mut evidence);
        }
        *current=next.document;
        for issue in audit.claim_audit.iter().filter(|c|c.status!="supported"){
            let key = if super::source_items::enabled() {
                let Some(key) = next.corrected_statements.get(&issue.path) else {continue;};
                key.clone()
            } else { issue.path.clone() };
            if ["不能归", "不能并入", "不能整体归", "归属错误", "归错"].iter().any(|term| issue.reason.contains(term)) {
                attribution_repairs.insert(key.clone());
            }
            attempted.insert(key.clone(),(issue.status.clone(),issue.status=="unclear"||source_wording_unclear(issue)));
            if let Some(phrase)=&issue.unclear_text{attempted_phrases.insert(key,phrase.clone());}
        }
    }
    Err("纪要复审未完成，已有结果保留。".into())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn audited_wrong_columns_cannot_survive_a_text_only_correction() {
        let units=vec![Unit{id:"u000".into(),text:"建议延后采购，现场已答复。".into()}];
        let doc:Document=serde_json::from_value(json!({"purpose":"讨论采购",
            "topics":[{"title":"采购","points":[{"kind":"status","text":"讨论采购","sources":["u000"]}],"details":[]}],
            "decisions":[{"text":"确定延后采购。","sources":["u000"]}],"actionItems":[],
            "questions":[{"text":"采购何时开始？","sources":["u000"]}]})).unwrap();
        let misplaced=HashSet::from(["decisions[0]".to_owned(),"questions[0]".to_owned()]);
        let patch=json!({"changes":[{"path":"decisions[0]","text":"有人建议延后采购。"},{"path":"questions[0]","remove":true}]});
        let repaired=apply_changes_with_policy(&patch.to_string(),&doc,&misplaced,&HashSet::new(),&HashMap::new(),&misplaced,&units).unwrap();
        assert!(repaired.decisions.is_empty()&&repaired.questions.is_empty());
        assert_eq!(repaired.topics[0].details[0].text,"有人建议延后采购。");
        assert_eq!(repaired.topics[0].details[0].sources,["u000"]);
    }

    #[test]
    fn automatic_brief_evidence_padding_aliases_resolve_only_real_unique_ids(){
        let source=vec![Sentence{id:"e0001".into(),source:"u000".into(),text:"预算未审批。".into()}];let expected=vec![json!({"path":"purpose","text":"预算未审批"})];
        let good=json!({"claimAudit":[{"path":"purpose","status":"supported","clarity":"clear","unclearText":null,"reason":"原话说明预算未审批","evidence":["e1"]}]});
        assert_eq!(decode_contract(&good.to_string(),&expected,&source,true).unwrap().claim_audit[0].evidence,vec!["e0001"]);
        assert!(decode_contract(&good.to_string(),&expected,&source,false).is_err());
        for id in ["e99","u1","e01x","e00001"]{let mut bad=good.clone();bad["claimAudit"][0]["evidence"]=json!([id]);assert!(decode_contract(&bad.to_string(),&expected,&source,true).is_err());}
        let mut duplicate=good;duplicate["claimAudit"][0]["evidence"]=json!(["e1","e0001"]);assert!(decode_contract(&duplicate.to_string(),&expected,&source,true).is_err());
    }
    #[test]
    fn automatic_brief_length_recovery_preserves_valid_patches_and_metadata(){
        let raw=json!({"changes":[{"path":"topics[0].points[0]","text":"长".repeat(91),"kind":"opinion"},{"path":"actionItems[0]","text":"保留条件后提交报告。","owner":"王梅","due":"周五"}]}).to_string();
        let paths=oversized_repair_texts(&raw);assert_eq!(paths,HashSet::from(["topics[0].points[0]".to_string()]));
        let good=json!({"changes":[{"path":"topics[0].points[0]","text":"若条件满足，可提交报告。"}]});
        let merged:Value=serde_json::from_str(&merge_shorter_repair_texts(&raw,&good.to_string(),&paths).unwrap()).unwrap();let original:Value=serde_json::from_str(&raw).unwrap();
        assert_eq!(merged["changes"][1],original["changes"][1]);assert_eq!(merged["changes"][0]["kind"],"opinion");
        for bad in [json!({"changes":[]}),json!({"changes":[{"path":"actionItems[0]","text":"改负责人。"}]}),json!({"changes":[{"path":"topics[0].points[0]","text":"短句。","kind":"decision"}]}),json!({"changes":[{"path":"topics[0].points[0]","text":"长".repeat(91)}]})]{assert!(merge_shorter_repair_texts(&raw,&bad.to_string(),&paths).is_err());}
    }
    #[test]
    fn automatic_brief_second_ambiguity_requires_actual_removal_of_the_first(){
        let claim=json!({"text":"保留明确做法，另一个含混词。","owner":null,"due":null});
        assert!(newly_exposed_ambiguity(Some("原含混词"),Some("另一个含混词"),&claim));
        assert!(!newly_exposed_ambiguity(Some("另一个含混词"),Some("另一个含混词"),&claim));
        assert!(!newly_exposed_ambiguity(Some("明确做法"),Some("另一个含混词"),&claim));
        assert!(!newly_exposed_ambiguity(None,Some("另一个含混词"),&claim));
        let owner=json!({"text":"另一个含混词。","owner":"原含混词"});
        assert!(!newly_exposed_ambiguity(Some("原含混词"),Some("另一个含混词"),&owner));
    }
    #[test]
    fn automatic_brief_second_repair_requires_a_distinct_failure_axis(){
        assert!(changed_failure_axis(&("overstated".into(),false),"unclear",true));
        assert!(changed_failure_axis(&("unclear".into(),true),"overstated",false));
        assert!(changed_failure_axis(&("overstated".into(),true),"overstated",false));
        assert!(!changed_failure_axis(&("unclear".into(),true),"unclear",true));
        assert!(!changed_failure_axis(&("overstated".into(),false),"overstated",false));
        assert!(!changed_failure_axis(&("unclear".into(),true),"unsupported",false));
    }
    #[test]
    fn automatic_brief_scope_repair_cannot_revive_previously_rejected_unclear_terms(){
        let mut doc:Document=serde_json::from_value(json!({"purpose":"讨论组织方案","topics":[{"title":"组织协作","points":[{"kind":"recommendation","text":"由产业联盟整合资源，具体机构名称待核对。","sources":["u000"]}],"details":[]}],"decisions":[],"actionItems":[],"questions":[]})).unwrap();
        let history=HashMap::from([("topics[0].points[0]".to_string(),vec!["牵头单位".to_string()])]);
        assert!(preserves_unclear_history(&doc,&history).is_ok());doc.topics[0].points[0].text="由牵头单位整合资源。".into();assert!(preserves_unclear_history(&doc,&history).is_err());
    }
    #[test]
    fn automatic_brief_append_cannot_override_a_prior_source_bound_unclear_verdict(){
        let source=vec![Sentence{id:"e0000".into(),source:"u000".into(),text:"原话含混称谓".into()},Sentence{id:"e0001".into(),source:"u001".into(),text:"另一明确上下文".into()}];
        let expected=vec![json!({"path":"topics[1].points[0]","text":"由牵头单位组织。","sources":["u000"]})];
        let history=vec![json!({"path":"topics[0].details[0]","phrase":"牵头单位","sourceIds":["u000"]})];
        let mut audit:Audit=serde_json::from_value(json!({"claimAudit":[{"path":"topics[1].points[0]","status":"supported","clarity":"clear","unclearText":null,"reason":"新一轮模型改判支持","evidence":["e0000"]}]})).unwrap();
        assert_eq!(apply_historical_veto(&mut audit,&expected,&history,&source),vec!["topics[1].points[0]"]);assert_eq!(audit.claim_audit[0].status,"unclear");
        audit.claim_audit[0].status="unsupported".into();audit.claim_audit[0].clarity=Some("clear".into());apply_historical_veto(&mut audit,&expected,&history,&source);assert_eq!(audit.claim_audit[0].status,"unsupported");
        let mut other=expected.clone();other[0]["sources"]=json!(["u001"]);audit.claim_audit[0].evidence=vec!["e0001".into()];audit.claim_audit[0].clarity=Some("clear".into());assert!(apply_historical_veto(&mut audit,&other,&history,&source).is_empty());
    }
    #[test]
    fn automatic_brief_parallel_audit_keeps_parent_job_cancellation(){
        use super::super::super::super::meeting_processing_job as job;
        let result=job::run("factual-parallel-test","factual-parallel-job",job::Kind::Minutes,||{
            let token=job::current().unwrap();let(ready_tx,ready_rx)=std::sync::mpsc::channel();let(release_tx,release_rx)=std::sync::mpsc::channel();
            let worker=std::thread::spawn(move||super::super::with_parent_job(Some(token),||{assert!(super::super::current_cancellation().is_some());super::super::check_current()?;ready_tx.send(()).unwrap();release_rx.recv().unwrap();super::super::check_current()}));
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
    fn an_audited_task_keeps_the_distinct_source_for_its_owner_and_due_date() {
        let units = vec![
            Unit{id:"u000".into(),text:"说话人1：我是质检组。".into()},
            Unit{id:"u001".into(),text:"我们会安排入库检查。".into()},
            Unit{id:"u002".into(),text:"检查周五前完成。".into()},
        ];
        let doc: Document = serde_json::from_value(json!({"purpose":"落实入库检查",
            "topics":[{"title":"入库检查","points":[{"kind":"status","text":"安排入库检查。","sources":["u001"]}],"details":[]}],
            "decisions":[],"questions":[],"actionItems":[{"text":"安排入库检查。","owner":"质检组","due":"周五前",
                "sources":["u000","u001","u002"]}]})).unwrap();
        let audit: Audit = serde_json::from_value(json!({"claimAudit":[{"path":"actionItems[0]",
            "status":"supported","reason":"入库检查安排已经确认","evidence":["e0001"]}]})).unwrap();
        let actual = bind_supported_sources(&doc,&audit,&sentences(&units),&units).unwrap();
        let task = &actual.action_items[0];
        assert_eq!(task.sources,["u001","u000","u002"]);
        assert_eq!(task.owner.as_deref(),Some("质检组"));
        assert_eq!(task.due.as_deref(),Some("周五前"));
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
    fn related_numeric_veto_checks_shared_source_and_leaves_an_earlier_supported_proposal() {
        let source = [Sentence {id:"e0010".into(),source:"u002".into(),text:"十八到三十五还是四十五岁再说。".into()}];
        let affected = json!({"path":"topics[0].details[0]","text":"已形成共识，年龄范围为１８到４５岁。","sources":["u002"]});
        let unrelated = json!({"path":"topics[2].details[0]","text":"另一组以18到45岁为准。","sources":["u009"]});
        let earlier = json!({"path":"topics[0].points[0]","text":"营销建议年龄18到45岁。","sources":["u002"]});
        let original = json!({"path":"actionItems[0]","text":"18至45岁确定色彩。","sources":["u002"]});
        let mut first = serde_json::from_value::<Audit>(json!({"claimAudit":[{"path":"actionItems[0]",
            "status":"unclear","clarity":"unclear","unclearText":"18至45岁","reason":"两种上限都出现","evidence":["e0010"]}]})).unwrap();
        let set = related_numeric_uncertainty(&first, &[original,affected.clone(),unrelated,earlier.clone()], &source);
        assert_eq!(set.len(),2);
        let mut expected = vec![affected,earlier];
        for item in &mut expected {
            item["relatedUncertainty"] = set[&statement_identity(item["path"].as_str().unwrap(), item)].clone();
        }
        first.claim_audit = expected.iter().map(|item| serde_json::from_value(json!({"path":item["path"],"status":"supported",
            "reason":"读作年龄范围","evidence":["e0010"]})).unwrap()).collect();
        reject_unresolved_settlement(&mut first,&expected);
        assert_eq!(first.claim_audit[0].status,"unclear");
        assert_eq!(first.claim_audit[1].status,"supported");
    }

    #[test]
    fn a_question_without_a_reply_drops_only_the_unsupported_confirmation() {
        let source = [Sentence {id:"e0010".into(),source:"u002".into(),text:"两种设备是分开存放吧？".into()}];
        let claims = [json!({"path":"topics[0].points[0]","text":"会上询问并确认两类设备是否分开存放；备用设备单独存。","sources":["u002"]})];
        let issue = json!({"path":"topics[0].points[0]","status":"overstated","reason":"没有明确回答或确认","evidence":["e0010"]});
        let repair = unsupported_confirmation(&[issue.clone()], &claims, &source).unwrap();
        assert!(repair.contains("会上询问两类设备是否分开存放；备用设备单独存。"));
        let mut genuine = issue;
        genuine["reason"] = json!("会中明确回答并确认");
        assert!(unsupported_confirmation(&[genuine], &claims, &source).is_none());
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
        let scope=json!([{"id":"e0000","text":"李敏：预算尚未审批。"}]);
        let expected=vec![json!({"path":"actionItems[0]","text":"提交报告。","owner":"李敏","due":null,"sources":["u000"],"sourceScopeEvidence":scope})];
        let good=json!({"claimAudit":[{"path":"actionItems[0]","status":"supported","reason":"受控协议响应","evidence":["e0000"],"text":"提交报告。","owner":"李敏","due":null,"sources":["u000"],"sourceScopeEvidence":scope}]});
        let source=sentences(&source());assert!(decode(&good.to_string(),&expected,&source).is_ok());
        for(key,value)in[("owner",json!("李明")),("owner",Value::Null),("due",json!("周五")),("text",json!("批准报告。")),("sources",json!(["u999"])),("sourceScopeEvidence",json!([{"id":"e0000","text":"预算已审批。"}])),("passed",json!(true))]{
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
        let fixed=apply_changes_with_policy(&patch.to_string(),&doc,&allowed,&allowed,&policy,&HashSet::new(),&units).unwrap();
        let mut expected=doc.clone();expected.topics[0].points[0].text=fixed.topics[0].points[0].text.clone();
        assert_eq!(serde_json::to_value(fixed).unwrap(),serde_json::to_value(expected).unwrap());
        assert!(apply_changes(&patch.to_string(),&doc,&allowed,&allowed,&units).is_err());
        for bad in [json!({"changes":[{"path":path,"text":"牵牛单位仍负责协作。"}]}),json!({"changes":[{"path":path,"text":"开展协作。","kind":"decision"}]}),json!({"changes":[{"path":"purpose","text":"改整场主题"}]})]{
            assert!(apply_changes_with_policy(&bad.to_string(),&doc,&allowed,&allowed,&policy,&HashSet::new(),&units).is_err());
        }
        let invalid_policy=HashMap::from([(path.to_string(),vec!["原句里没有".to_string()])]);
        assert!(apply_changes_with_policy(&patch.to_string(),&doc,&allowed,&allowed,&invalid_policy,&HashSet::new(),&units).is_err());
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
