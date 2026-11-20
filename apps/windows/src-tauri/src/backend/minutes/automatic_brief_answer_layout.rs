//! Candidate ID-only assembly. Model grouping cannot rewrite a fact or its task.
//! The assembled result still requires independent source/factual/coverage review.
use std::collections::{HashMap,HashSet};
use serde::{Deserialize,Serialize};
use super::{Action,Document,Entry,Kind,Point,Topic,Unit};

#[derive(Debug,Clone,Copy,Deserialize,Serialize,PartialEq,Eq,Hash)]
#[serde(rename_all="lowercase")]
pub(in crate::backend::minutes) enum Placement {Topic,Decision,Action,Question}

#[derive(Debug,Clone,Deserialize,Serialize)]
#[serde(deny_unknown_fields)]
pub(in crate::backend::minutes) struct Fact {
    pub id:String,pub kind:Kind,pub placement:Placement,pub text:String,
    pub owner:Option<String>,pub due:Option<String>,pub evidence:Vec<String>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct TopicIds {title:String,points:Vec<Vec<String>>,details:Vec<Vec<String>>}
#[derive(Debug,Deserialize,Serialize)]
#[serde(rename_all="lowercase")]
pub(in crate::backend::minutes) enum ExclusionReason {Duplicate,Illustration,Background}
#[derive(Debug,Deserialize,Serialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
pub(in crate::backend::minutes) struct Exclusion {pub id:String,pub reason:ExclusionReason,pub covered_by:Vec<String>}
#[derive(Deserialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
struct Layout {
    #[serde(default,rename="type")]_response_type:super::ResponseFormatMarker,
    purpose:String,topics:Vec<TopicIds>,decisions:Vec<Vec<String>>,
    action_items:Vec<Vec<String>>,questions:Vec<Vec<String>>,excluded:Vec<Exclusion>,
}
pub(in crate::backend::minutes) struct Assembled {
    pub document:Document,pub retained_ids:Vec<String>,pub excluded:Vec<Exclusion>,
    pub bindings:Vec<(String,String)>,
}
fn fail()->String{"纪要分组尚未完整保留已核内容，原文和已有纪要保留。".into()}

struct Bound<'a>{fact:&'a Fact,sources:Vec<String>}
fn bind_facts<'a>(facts:&'a[Fact],units:&[Unit],fact_limit:usize)->Result<HashMap<&'a str,Bound<'a>>,String>{
    if facts.is_empty()||facts.len()>fact_limit{return Err(fail());}
    let sentences=super::factual_audit::evidence_sentences(units);
    let known=sentences.iter().map(|s|(s["id"].as_str().unwrap(),s)).collect::<HashMap<_,_>>();
    let supplied=known.keys().copied().collect::<HashSet<_>>();let mut bound=HashMap::new();
    for fact in facts{
        if !super::line(&fact.id,32)||!super::line(&fact.text,90)||fact.evidence.is_empty()||fact.evidence.len()>8{return Err(fail());}
        if matches!(fact.placement,Placement::Action|Placement::Decision)&&!matches!(fact.kind,Kind::Decision){return Err(fail());}
        if fact.placement!=Placement::Action&&(fact.owner.is_some()||fact.due.is_some()){return Err(fail());}
        let mut selected=HashSet::new();let mut sources=Vec::new();let mut original=String::new();
        for id in &fact.evidence{
            let id=super::factual_audit::canonical_sentence_reference(id,&supplied).ok_or_else(fail)?;
            if !selected.insert(id.clone()){return Err(fail());}
            let sentence=known[id.as_str()];let source=sentence["source"].as_str().unwrap();
            if !sources.iter().any(|s|s==source){sources.push(source.to_string());}
            original.push_str(sentence["text"].as_str().unwrap());
        }
        let original=super::normalized(&original);
        for value in [&fact.owner,&fact.due].into_iter().flatten(){
            if !super::line(value,80)||!original.contains(&super::normalized(value)){return Err(fail());}
        }
        if bound.insert(fact.id.as_str(),Bound{fact,sources}).is_some(){return Err(fail());}
    }
    Ok(bound)
}
pub(in crate::backend::minutes) fn validate_facts(facts:&[Fact],units:&[Unit],fact_limit:usize)->Result<(),String>{bind_facts(facts,units,fact_limit).map(|_|())}

fn take<'a>(ids:&[String],placement:Placement,known:&'a HashMap<&str,Bound<'a>>,used:&mut HashSet<String>)->Result<&'a Bound<'a>,String>{
    // Separate actors and independent facts stay separate reader rows. No
    // concatenation, truncation, rewriting, or task-owner/date reassignment.
    if ids.len()!=1{return Err(fail());}
    let id=&ids[0];let bound=known.get(id.as_str()).ok_or_else(fail)?;
    if bound.fact.placement!=placement||!used.insert(id.clone()){return Err(fail());}Ok(bound)
}
fn entry(bound:&Bound<'_>)->Entry{Entry{text:bound.fact.text.clone(),sources:bound.sources.clone(),quantity_needs_review:false}}

pub(in crate::backend::minutes) fn assemble(raw:&str,facts:&[Fact],units:&[Unit])->Result<Assembled,String>{
    assemble_with_details_limit(raw,facts,units,8,128)
}

pub(in crate::backend::minutes) fn assemble_with_details_limit(raw:&str,facts:&[Fact],units:&[Unit],details_limit:usize,fact_limit:usize)->Result<Assembled,String>{
    let layout:Layout=serde_json::from_str(super::super::strip_code_fences(raw).trim()).map_err(|_|fail())?;
    let known=bind_facts(facts,units,fact_limit)?;let mut used=HashSet::new();
    if layout.topics.is_empty()||layout.topics.len()>8||layout.decisions.len()>20||layout.action_items.len()>20
        || layout.questions.len()>super::question_limit(details_limit){return Err(fail());}
    let mut document=Document{purpose:layout.purpose,topics:Vec::new(),decisions:Vec::new(),action_items:Vec::new(),questions:Vec::new()};
    let mut bindings=Vec::new();
    for (i,topic) in layout.topics.into_iter().enumerate(){
        if topic.points.is_empty()||topic.points.len()>3||topic.details.len()>details_limit{return Err(fail());}
        let mut points=Vec::new();let mut details=Vec::new();
        for (j,ids) in topic.points.into_iter().enumerate(){
            let bound=take(&ids,Placement::Topic,&known,&mut used)?;
            bindings.push((format!("/topics/{i}/points/{j}"),bound.fact.id.clone()));
            points.push(Point{kind:bound.fact.kind.clone(),text:bound.fact.text.clone(),sources:bound.sources.clone(),quantity_needs_review:false});
        }
        for (j,ids) in topic.details.into_iter().enumerate(){let bound=take(&ids,Placement::Topic,&known,&mut used)?;bindings.push((format!("/topics/{i}/details/{j}"),bound.fact.id.clone()));details.push(entry(bound));}
        document.topics.push(Topic{title:topic.title,points,details});
    }
    for (i,ids) in layout.decisions.into_iter().enumerate(){let bound=take(&ids,Placement::Decision,&known,&mut used)?;bindings.push((format!("/decisions/{i}"),bound.fact.id.clone()));document.decisions.push(entry(bound));}
    for (i,ids) in layout.questions.into_iter().enumerate(){let bound=take(&ids,Placement::Question,&known,&mut used)?;bindings.push((format!("/questions/{i}"),bound.fact.id.clone()));document.questions.push(entry(bound));}
    for (i,ids) in layout.action_items.into_iter().enumerate(){
        let bound=take(&ids,Placement::Action,&known,&mut used)?;
        bindings.push((format!("/actionItems/{i}"),bound.fact.id.clone()));
        document.action_items.push(Action{text:bound.fact.text.clone(),owner:bound.fact.owner.clone(),due:bound.fact.due.clone(),sources:bound.sources.clone()});
    }
    let retained=used.clone();
    for exclusion in &layout.excluded{
        if !known.contains_key(exclusion.id.as_str())||!used.insert(exclusion.id.clone())
            ||exclusion.covered_by.iter().collect::<HashSet<_>>().len()!=exclusion.covered_by.len()
            ||exclusion.covered_by.iter().any(|id|!retained.contains(id)){return Err(fail());}
        match exclusion.reason{
            ExclusionReason::Duplicate if exclusion.covered_by.is_empty()=>return Err(fail()),
            ExclusionReason::Illustration|ExclusionReason::Background if !exclusion.covered_by.is_empty()=>return Err(fail()),
            _=>{},
        }
    }
    if used.len()!=known.len(){return Err(fail());}
    super::validate_with_details_limit(&document,units,details_limit)?;
    let retained_ids=facts.iter().filter(|f|retained.contains(&f.id)).map(|f|f.id.clone()).collect();
    Ok(Assembled{document,retained_ids,excluded:layout.excluded,bindings})
}

#[cfg(test)]
mod tests{
    use super::*;
    use serde_json::{json,Value};
    fn units()->Vec<Unit>{vec![Unit{id:"u000".into(),text:"李敏周五完成权限测试并发报告。预算尚未审批，不能先采购。".into()}]}
    fn facts()->Vec<Fact>{vec![
        Fact{id:"a000".into(),kind:Kind::Status,placement:Placement::Topic,text:"预算尚未审批，不能先采购。".into(),owner:None,due:None,evidence:vec!["e0001".into()]},
        Fact{id:"a001".into(),kind:Kind::Decision,placement:Placement::Action,text:"李敏周五完成权限测试并发报告。".into(),owner:Some("李敏".into()),due:Some("周五".into()),evidence:vec!["e0000".into()]},
    ]}
    fn layout()->Value{json!({"purpose":"确认采购限制与测试安排","topics":[{"title":"采购限制","points":[["a000"]],"details":[]}],"decisions":[],"actionItems":[["a001"]],"questions":[],"excluded":[]})}
    #[test]
    fn automatic_brief_id_layout_preserves_exact_text_and_literal_task(){
        let actual=assemble(&layout().to_string(),&facts(),&units()).unwrap();
        assert_eq!(actual.document.topics[0].points[0].text,facts()[0].text);
        assert_eq!(actual.document.action_items[0].text,facts()[1].text);
        assert_eq!(actual.document.action_items[0].owner,Some("李敏".into()));
        assert_eq!(actual.document.action_items[0].due,Some("周五".into()));
        assert_eq!(actual.retained_ids,vec!["a000","a001"]);assert!(actual.excluded.is_empty());
    }
    #[test]
    fn automatic_brief_id_layout_rejects_omitted_invented_repeated_or_rewritten_facts(){
        let mut omitted=layout();omitted["actionItems"]=json!([]);assert!(assemble(&omitted.to_string(),&facts(),&units()).is_err());
        let mut invented=layout();invented["topics"][0]["points"]=json!([["a999"]]);assert!(assemble(&invented.to_string(),&facts(),&units()).is_err());
        let mut repeated=layout();repeated["topics"][0]["details"]=json!([["a000"]]);assert!(assemble(&repeated.to_string(),&facts(),&units()).is_err());
        let mut rewritten=layout();rewritten["topics"][0]["text"]=json!("预算已审批。");assert!(assemble(&rewritten.to_string(),&facts(),&units()).is_err());
        let raw=layout().to_string().replacen("\"purpose\":", "\"purpose\":\"假的\",\"purpose\":",1);assert!(assemble(&raw,&facts(),&units()).is_err());
    }
    #[test]
    fn automatic_brief_id_layout_cannot_merge_roles_or_move_action_into_decision(){
        let mut merged=layout();merged["topics"][0]["points"]=json!([["a000","a001"]]);assert!(assemble(&merged.to_string(),&facts(),&units()).is_err());
        let mut moved=layout();moved["actionItems"]=json!([]);moved["decisions"]=json!([["a001"]]);assert!(assemble(&moved.to_string(),&facts(),&units()).is_err());
        let mut unknown_owner=facts();unknown_owner[1].owner=Some("王强".into());assert!(assemble(&layout().to_string(),&unknown_owner,&units()).is_err());
        let mut unknown_reference=facts();unknown_reference[0].evidence=vec!["e9999".into()];assert!(assemble(&layout().to_string(),&unknown_reference,&units()).is_err());
    }
    #[test]
    fn automatic_brief_id_layout_exclusion_must_reference_an_actually_retained_fact(){
        let mut expanded=facts();let mut duplicate=expanded[0].clone();duplicate.id="a002".into();expanded.push(duplicate);
        let mut valid=layout();valid["excluded"]=json!([{"id":"a002","reason":"duplicate","coveredBy":["a000"]}]);
        let actual=assemble(&valid.to_string(),&expanded,&units()).unwrap();assert_eq!(actual.retained_ids.len(),2);
        for reference in ["a002","a999"]{let mut bad=valid.clone();bad["excluded"][0]["coveredBy"]=json!([reference]);assert!(assemble(&bad.to_string(),&expanded,&units()).is_err());}
    }
}
