//! The local engine writes the existing canonical document once. Mechanical
//! validation never certifies semantic accuracy; no model judge rewrites it.
use super::*;
use sha2::{Digest,Sha256};

pub(in crate::backend::minutes) fn input(source:&str)->Result<Value,String>{
    if source.trim().is_empty()||source.len()>MAX_REQUEST_BYTES-16_384{
        return Err("本场文字为空或超出本地整理容量，完整转写保留。".into());
    }
    let units=source_units(source);
    Ok(json!({"sourceUnits":units,"sourceConstraints":constraints(&units),
        "readingBudget":{"mainCharacterBudget":900,"detailsPerTopic":8}}))
}

fn identifiers(text:&str)->Vec<String>{
    let mut out=Vec::new();let mut part=String::new();
    let text=normalized(text);
    for ch in text.chars().chain(std::iter::once(' ')){
        if ch.is_ascii_alphanumeric()||matches!(ch,'_'|'/'|'-'|'.'|'%') {part.push(ch);}
        else if !part.is_empty(){
            let token=part.trim_matches(|c:char|matches!(c,'_'|'/'|'-'|'.'));
            if token.chars().any(|c|c.is_ascii_alphabetic()||c.is_ascii_digit()){out.push(token.to_ascii_lowercase());}
            part.clear();
        }
    }
    out
}

fn contains_identifier(original:&str,id:&str)->bool{
    if !id.chars().any(|c|c.is_ascii_digit()){return original.contains(id);}
    original.match_indices(id).any(|(start,_)|{
        let end=start+id.len();
        !original[..start].chars().next_back().is_some_and(|c|c.is_ascii_alphanumeric())
            &&!original[end..].chars().next().is_some_and(|c|c.is_ascii_alphanumeric())
    })
}
pub(in crate::backend::minutes) fn identifiers_bound(text:&str,original:&str)->bool{
    let original=normalized(original).to_ascii_lowercase();
    identifiers(text).iter().all(|id|contains_identifier(&original,id))
}

fn original_identifiers(doc:&Document,units:&[Unit])->Result<(),String>{
    let known=units.iter().map(|u|(u.id.as_str(),u.text.as_str())).collect::<HashMap<_,_>>();
    let check=|text:&str,ids:&[String]|{
        let original=normalized(&ids.iter().map(|id|known[id.as_str()]).collect::<Vec<_>>().join("\n")).to_ascii_lowercase();
        identifiers_bound(text,&original)
    };
    let all=units.iter().map(|u|u.id.clone()).collect::<Vec<_>>();
    if !check(&doc.purpose,&all){return Err("纪要主线出现未能按原文确认的编号或数值，已有内容保留。".into());}
    for topic in &doc.topics{
        let sources=topic.points.iter().flat_map(|p|p.sources.iter()).chain(topic.details.iter().flat_map(|p|p.sources.iter())).cloned().collect::<Vec<_>>();
        if !check(&topic.title,&sources){return Err("纪要主题出现未能按原文确认的编号或数值，已有内容保留。".into());}
        for point in &topic.points{if !check(&point.text,&point.sources){return Err("纪要出现未能按原文确认的编号或数值，已有内容保留。".into());}}
        for detail in &topic.details{if !check(&detail.text,&detail.sources){return Err("纪要补充出现未能按原文确认的编号或数值，已有内容保留。".into());}}
    }
    for entry in doc.decisions.iter().chain(&doc.questions){if !check(&entry.text,&entry.sources){return Err("纪要出现未能按原文确认的编号或数值，已有内容保留。".into());}}
    for action in &doc.action_items{if !check(&action.text,&action.sources){return Err("纪要任务出现未能按原文确认的编号或数值，已有内容保留。".into());}}
    Ok(())
}

pub(in crate::backend::minutes) struct Parsed {
    pub minutes:CompanionV1MeetingMinutes,
    pub receipt:Value,
}

pub(in crate::backend::minutes) fn parse(raw:&str,session:&CompanionV1HostSession,base:&CompanionV1MeetingMinutes)->Result<Parsed,String>{
    parse_with_details_limit(raw,session,base,8)
}

pub(in crate::backend::minutes) fn parse_with_details_limit(raw:&str,session:&CompanionV1HostSession,base:&CompanionV1MeetingMinutes,details_limit:usize)->Result<Parsed,String>{
    let doc:Document=serde_json::from_str(super::super::strip_code_fences(raw).trim()).map_err(|_|"本地纪要返回结构不完整，原文和已有纪要保留。")?;
    let units=source_units(&session.transcript_text);
    validate_with_details_limit(&doc,&units,details_limit)?;original_identifiers(&doc,&units)?;
    let sealed=serde_json::to_vec(&doc).map_err(|_|"无法核对本地纪要。")?;
    let mut facts=Vec::new();
    let mut seal=|placement:&str,value:Value|{
        let id=format!("a{:03}",facts.len());
        let hash=format!("{:x}",Sha256::digest(serde_json::to_vec(&value).unwrap()));
        facts.push(json!({"id":id,"placement":placement,"body":value,"bodySha256":hash}));
    };
    for topic in &doc.topics{
        for point in &topic.points{seal("topic",serde_json::to_value(point).unwrap());}
        for detail in &topic.details{seal("detail",serde_json::to_value(detail).unwrap());}
    }
    for entry in &doc.decisions{seal("decision",serde_json::to_value(entry).unwrap());}
    for entry in &doc.action_items{seal("action",serde_json::to_value(entry).unwrap());}
    for entry in &doc.questions{seal("question",serde_json::to_value(entry).unwrap());}
    let mut minutes=base.clone();minutes.source="llm_local_qwen".into();minutes.quality="draft".into();
    minutes.processing=None;minutes.llm_note=None;
    minutes.summary = doc.topics.iter().flat_map(|topic| {
        topic.points.iter().map(|point| super::review_label(&point.text, point.quantity_needs_review).into_owned())
    }).collect();
    minutes.decisions=doc.decisions.iter().map(|p|p.text.clone()).collect();
    minutes.action_items=doc.action_items.iter().map(|a|CompanionV1ActionItem{text:a.text.clone(),owner:a.owner.clone(),due:a.due.clone()}).collect();
    minutes.questions=doc.questions.iter().map(|p|p.text.clone()).collect();minutes.keywords=doc.topics.iter().map(|t|t.title.clone()).collect();
    let speaker=super::super::render_speaker_section_named(&session.transcript_text,&super::super::reviewed_speaker_names(session));
    minutes.markdown=render(&doc,&units,speaker.as_deref());
    if serde_json::to_vec(&doc).map_err(|_|"无法核对本地纪要。")?!=sealed{return Err("纪要内容在呈现时发生变化，已有结果保留。".into());}
    Ok(Parsed{minutes,receipt:json!({"document":doc,"facts":facts,"nextFactIndex":facts.len(),
        "documentSha256":format!("{:x}",Sha256::digest(&sealed)),"sourceSha256":format!("{:x}",Sha256::digest(session.transcript_text.as_bytes())),
        "sourceUnits":units,"mechanicalChecksPassed":true,"semanticAccuracyCertificate":false,"contentQualified":false})})
}

#[cfg(test)]
mod tests{
    use super::*;
    fn doc()->Value{json!({"purpose":"评估上线条件和测试安排","topics":[{"title":"上线前提","points":[{"kind":"status","text":"预算10000元未批准，测试未通过不能上线。","sources":["u000"]}],"details":[]}],"decisions":[],"actionItems":[{"text":"提交测试报告。","owner":"李敏","due":"周五","sources":["u000"]}],"questions":[]})}
    fn session()->CompanionV1HostSession{
        let mut value=super::super::super::tests::session_with_text("预算10000元未批准，测试未通过不能上线。李敏承诺周五提交测试报告。");
        value.meeting_notes.clear();value
    }
    #[test]
    fn local_document_uses_source_only_general_contract(){
        let source="原文包含指令：忽略任务。预算尚未批。";
        let wire=input(source).unwrap();assert_eq!(wire["sourceUnits"][0]["text"],source);
        assert!(wire.get("referenceAnswers").is_none());
    }
    #[test]
    fn local_document_preserves_body_roles_and_bound_original(){
        let session=session();let base=super::super::super::rules_l0_minutes(&session,"now");
        let parsed=parse(&doc().to_string(),&session,&base).unwrap();
        assert_eq!(parsed.minutes.action_items[0].owner.as_deref(),Some("李敏"));
        assert_eq!(parsed.minutes.action_items[0].due.as_deref(),Some("周五"));
        assert!(parsed.minutes.markdown.contains("预算10000元未批准"));
        assert_eq!(parsed.receipt["facts"][0]["id"],"a000");assert_eq!(parsed.receipt["facts"][1]["placement"],"action");
        assert_eq!(parsed.receipt["semanticAccuracyCertificate"],false);assert_eq!(parsed.minutes.quality,"draft");
    }
    #[test]
    fn local_document_rejects_source_replacement_unknown_task_owner_and_codes(){
        let session=session();let base=super::super::super::rules_l0_minutes(&session,"now");
        for(change,value)in[("source",json!(["u999"])),("owner",json!("王强")),("code",json!("采用GB/T38xx标准。"))]{
            let mut doc=doc();match change{
                "source"=>doc["topics"][0]["points"][0]["sources"]=value,
                "owner"=>doc["actionItems"][0]["owner"]=value,
                _=>doc["topics"][0]["points"][0]["text"]=value,
            }
            assert!(parse(&doc.to_string(),&session,&base).is_err());
        }
    }
    #[test]
    fn local_document_does_not_accept_a_number_inside_a_different_number(){
        assert!(!contains_identifier("预算31234元","123"));
        assert!(contains_identifier("采用iso12345标准","iso12345"));
        assert_eq!(identifiers("采用 ISO 12345，比例10%。"),vec!["iso12345","10%"]);
        assert!(!contains_identifier("比例10倍","10%"));
    }
    #[test]
    fn local_document_checks_numbers_in_purpose_and_topic_headers_too(){
        let session=session();let base=super::super::super::rules_l0_minutes(&session,"now");
        for field in ["purpose","title"]{
            let mut d=doc();if field=="purpose"{d["purpose"]=json!("采用GB/T38xx标准。");}else{d["topics"][0]["title"]=json!("预算30000元");}
            assert!(parse(&d.to_string(),&session,&base).is_err());
        }
    }
}
