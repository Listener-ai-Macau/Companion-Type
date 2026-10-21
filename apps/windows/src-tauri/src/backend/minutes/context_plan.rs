//! Short personal plans with explicitly selected supplements.
//! The existing provider judges intent across the complete material. The local
//! boundary accepts only complete declared clauses, never invented words or
//! resolved dates/owners. Related conditions remain explicit source clauses.
use crate::companion_v1::{CompanionV1ActionItem,CompanionV1HostSession};
use serde_json::Value;

pub(super) fn eligible(session:&CompanionV1HostSession)->bool {
    !session.meeting_notes.is_empty() && super::short_memo::actions(session).is_some()
}

struct SourceUnit { id:String, text:String, supplemental:bool }

fn clauses(text:&str)->Vec<&str> {
    text.split(['，',',','；',';','。','.','！','!','\n']).map(str::trim)
        .filter(|part|!part.is_empty()).collect()
}

fn source_units(session:&CompanionV1HostSession)->Vec<SourceUnit> {
    let mut result=super::short_memo::actions(session).unwrap_or_default().into_iter().enumerate()
        .map(|(index,item)|SourceUnit{id:format!("original:{}",index+1),text:item.text,supplemental:false})
        .collect::<Vec<_>>();
    // The provider receives the complete note with numbered literal clauses.
    // It can group one outcome with its preparation and related condition,
    // while the original full note remains in the saved source snapshot.
    result.extend(session.meeting_notes.iter().enumerate().map(|(index,note)|SourceUnit{
        id:format!("supplement:{}",index+1),text:note.text.clone(),supplemental:true}));
    result
}

pub(super) fn instruction(session:&CompanionV1HostSession)->String {
    if !eligible(session) {return String::new();}
    let units=source_units(session).into_iter().map(|unit|serde_json::json!({
        "sourceId":unit.id,"text":unit.text,
        "clauses":clauses(&unit.text).iter().enumerate().map(|(index,text)|serde_json::json!({"id":index+1,"text":text})).collect::<Vec<_>>(),
        "source":if unit.supplemental {"用户明确选择的后补内容，不是录音事实"}else{"录音原话中的明确计划"}
    })).collect::<Vec<_>>();
    format!("\n\n本次是用户要求整理一条短个人备忘，并明确授权参考以上补充。请结合全部原话和补充判断当前计划，保留条件、更改或取消，不能把过期原计划复活。个人计划不需要另有负责人或截止时间才算待办；不填owner/due。新增计划标为用户补充来源，不声称来自录音。不要因为存在条件句就清空其它明确安排；取消、已完成、普通描述或疑问本身不是待办，可选念头可放摘要而不强行变成必须完成的任务。\n本次actionItems来源契约：一个勾选项对应一件独立要完成的事或结果，不按每个动词拆项。同一件事的准备、检查、选择、携带物品和条件保留在对应事项里；不要把“先检查再决定规格再购买”变成三个勾选项。明确不同时间、需独立完成的安排才另列，例如周五查天气与周六出门；不要漏掉独立事项，也不强行限定清单数量。仍有text简短说明，另填sourceId、clauseIds（任务原句id整数数组）、conditionClauseIds（同来源的相关条件原句id整数数组，无则空数组）。这些id来自该sourceId下的clauses。若原话事项另有后补的准备或条件，给该事项填supplementRefs数组，每个元素为sourceId（supplement来源）及clauseIds（该补充下的完整原句id）；相关补充附在原事项内，不再重复列成独立任务。没有关联补充时用空数组。清单按材料明确表达的实际执行先后排列，无明确关系时保持材料顺序，不猜日期或额外步骤。条件只附属于受它约束的事项，不能把条件句单独伪装成无条件任务。不得只抽原句内部几个词删掉否定或条件。本地将按id保留完整任务原句及补充原句，并标明补充来源，text不能代替来源引用。同一来源可以有多个独立事项；没有任务可返回空数组。摘要仍保留全部材料中的相关条件。其它JSON字段与既有规则相同。\n完整来源与可引用原句：\n{}",serde_json::to_string(&units).expect("source units serialize"))
}

fn selected_clauses(item:&Value,key:&str,parts:&[&str],required:bool)->Result<(Vec<usize>,String),String> {
    let Some(value)=item.get(key) else {return if required {Err("缺少任务原句引用".into())}else{Ok((Vec::new(),String::new()))};};
    let ids=value.as_array().ok_or_else(||"原句引用不是数组".to_string())?;
    if ids.len()>8 || (required && ids.is_empty()) {return Err("原句引用数量不适用".into());}
    let mut indexes=Vec::new();
    for id in ids {
        let id=id.as_u64().and_then(|id|usize::try_from(id).ok())
            .filter(|id|*id>0 && *id<=parts.len()).ok_or_else(||"原句引用不在本次来源内".to_string())?;
        if !indexes.contains(&id) {indexes.push(id);}
    }
    indexes.sort_unstable();
    let text=indexes.iter().map(|id|parts[*id-1]).collect::<Vec<_>>().join("；");
    Ok((indexes,text))
}

pub(super) fn validate(object:&Value,session:&CompanionV1HostSession)->Result<Vec<CompanionV1ActionItem>,String> {
    let units=source_units(session);
    let items=object.get("actionItems").and_then(Value::as_array)
        .ok_or_else(||"短备忘整理缺少行动项结构；原话和补充仍保留。".to_string())?;
    let mut result=Vec::new();let mut seen=std::collections::HashSet::new();
    for item in items {
        let explicit=item.get("sourceId").and_then(Value::as_str);
        let failure=||"短备忘整理的待办未能对应原话及条件；原文与补充已保留，请稍后重试或直接使用原文。".to_string();
        let (source,mut text,mut key)=if item.get("clauseIds").is_some() {
            let source=units.iter().find(|unit|Some(unit.id.as_str())==explicit).ok_or_else(failure)?;
            let parts=clauses(&source.text);
            let (task_ids,task)=selected_clauses(item,"clauseIds",&parts,true).map_err(|_|failure())?;
            let (condition_ids,condition)=selected_clauses(item,"conditionClauseIds",&parts,false).map_err(|_|failure())?;
            if task_ids.iter().any(|id|condition_ids.contains(id)){return Err(failure());}
            let text=if condition.is_empty(){task}else{format!("{task}（{condition}）")};
            (source,text,format!("{}:{task_ids:?}:{condition_ids:?}",source.id))
        } else {
            // Compatibility for an exactly quoted whole unit; no paraphrase
            // or similarity matching is accepted when clause refs are absent.
            let text=item.get("text").and_then(Value::as_str).unwrap_or("");
            let matched=units.iter().filter(|unit|unit.text==text && explicit.is_none_or(|id|id==unit.id)).collect::<Vec<_>>();
            if matched.len()!=1{return Err(failure());}
            (matched[0],text.to_string(),format!("{}:whole",matched[0].id))
        };
        if let Some(refs)=item.get("supplementRefs") {
            let refs=refs.as_array().filter(|refs|refs.len()<=16).ok_or_else(failure)?;
            let mut attached=Vec::new();
            let mut attached_keys=std::collections::HashSet::new();
            for reference in refs {
                let id=reference.get("sourceId").and_then(Value::as_str).ok_or_else(failure)?;
                let note=units.iter().find(|unit|unit.supplemental && unit.id==id && unit.id!=source.id).ok_or_else(failure)?;
                let (ids,words)=selected_clauses(reference,"clauseIds",&clauses(&note.text),true).map_err(|_|failure())?;
                let ref_key=format!("{}:{ids:?}",note.id);
                if attached_keys.insert(ref_key.clone()) {
                    attached.push(words);
                    key.push_str(&format!(":supplement:{ref_key}"));
                }
            }
            if !attached.is_empty() {text.push_str(&format!("（补充：{}）",attached.join("；")));}
        }
        // A personal source quote needs no inferred assignee/deadline. Ignore
        // any provider metadata; only the unchanged source text is retained.
        if seen.insert(key) {
            result.push(CompanionV1ActionItem{text:if source.supplemental {format!("用户补充：{text}")}else{text},owner:None,due:None});
        }
    }
    Ok(result)
}
