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
    let mut result=Vec::new();let mut start=0;
    for (index,ch) in text.char_indices() {
        // A label/request before ':' need not become part of the detail
        // after it. Keep numeric times such as 17:30 as a complete quote.
        let colon=matches!(ch,':'|'：');
        let numeric_colon=colon && text[..index].chars().next_back().is_some_and(|c|c.is_ascii_digit())
            && text[index+ch.len_utf8()..].chars().next().is_some_and(|c|c.is_ascii_digit());
        if matches!(ch,'，'|','|'；'|';'|'。'|'.'|'！'|'!'|'\n') || (colon && !numeric_colon) {
            let part=text[start..index].trim();if !part.is_empty(){result.push(part);}
            start=index+ch.len_utf8();
        }
    }
    let tail=text[start..].trim();if !tail.is_empty(){result.push(tail);}
    result
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
    if !eligible(session){return String::new();}
    let source_units=source_units(session);
    // Expose the same concrete subject addresses used by the local validator.
    // A condition/detail may name a plan again without becoming a new subject.
    // Do not ask the provider to reconstruct these addresses from note prose.
    let original_plan_targets=source_units.iter().filter(|unit|!unit.supplemental).map(|unit|
        serde_json::json!({"subject":unit.text,"targetRefs":[{"sourceId":unit.id,
            "clauseIds":(1..=clauses(&unit.text).len()).collect::<Vec<_>>()}]})).collect::<Vec<_>>();
    let units=source_units.into_iter().map(|unit|serde_json::json!({
        "sourceId":unit.id,"text":unit.text,
        "clauses":clauses(&unit.text).iter().enumerate().map(|(index,text)|serde_json::json!({"id":index+1,"text":text})).collect::<Vec<_>>(),
        "source":if unit.supplemental{"用户明确选择的后补，不是录音事实"}else{"原话里明确的原先计划，变更直接引用sourceId与原句clauseIds"}
    })).collect::<Vec<_>>();
    format!("这是短个人备忘。请判断完整材料的意思，再用原句编号表达关系。本地构造清单，不改写原句、不推算时间或负责人。返回标准JSON，并另给sourceRoles、originalReviews、newPlans、updates、attachments、orderings六个数组，无内容用[]。\n\n引用统一为{{sourceId,clauseIds:[整数]}}，只用下面给出的完整原句，不截断否定或条件。已有事项的目标地址已在originalPlanTargets给出；updates/attachments/orderings涉及已有事项时，复制对应targetRefs，不用补充里再次提到该事项的条件或准备原句代替目标地址。涉及新增事项时，目标必须引用本次newPlans已经声明的同一主体原句。basisRefs/whenRefs/refs才引用说明变更、条件、准备的补充原句；同一句提到猫粮等主体，不代表它自动成为新事项。sourceRoles每来源恰好一项：sourceId、contentClauseIds、instructionClauseIds、uncertainClauseIds。每句恰好归一组；生活的安排、准备、规格、背景、疑问、条件、取消均是content，只有指向整理工具的用途/格式要求是instruction，拿不准用uncertain。\n\n先分清已有目的、完成该目的的准备，以及真正新增的独立目的。original来源是原话中曾确定的原计划，本地保留主体，但当前是否仍决定执行必须结合后补逐项重新判断，不再写入newPlans。originalReviews每个original来源恰好一项：sourceId、intent(planned/tentative/cancelled)、basisRefs。它描述该事项现在的意愿，不是抄原先状态：planned为已决定做，tentative为现在仍要了解情况后才决定做不做，cancelled为已明确取消。没有后补改变意愿才保留planned且basisRefs可为空；tentative/cancelled必须引用本次后补中完整的未决定或取消依据。先确认情况、再决定做不做时，不得仅把它粘在确定事项的细节里；该事项应是tentative。已经决定做而只是有条件执行仍是planned，条件交给whenRefs/updates；不要把具体时间未定当成是否做未定。每项分别判断，不把一项待定覆盖整份清单。无条件defer/confirm/cancel若还写进updates，必须与同一原事项的originalReviews意愿一致；不要依赖缺省状态。为完成某原计划做的准备、查信息或规格，直接用attachments归到它下面，不要同时列成新增事项。只有独立的新结果才进入newPlans：sourceId、clauseIds、intent(planned或tentative)、basisRefs、supplementRefs、whenRefs。\nplanned表示已经决定；tentative仅表示原文明确尚未决定或只是留个想法。做事先后、未来安排、具体几点未定，不等于是否去做未决定。每个tentative必须用basisRefs引用表达未决定的原句（可以是事项主体同一句）；多个新想法共同受一句未决定影响时，各自引用它。不要根据整段标签覆盖每一项。supplementRefs为相关规格/准备，whenRefs为执行条件，无则[]。有条件的已定安排与尚未决定的想法分开。\n\nupdates只提取补充对安排的真实变更：kind、targetRefs、basisRefs、whenRefs。targetRefs引用事项主体，basisRefs引用补充中的变更原句；whenRefs引用该变更生效的完整条件，无条件填[]。kind为only/cancel/defer/require/confirm/revise。only另有scopeRefs：整个安排受限用字符串all，局部用事项主体引用数组。注意同一条件下后句“只做”的范围也须保留。原本已确定且在只做名单里的事项仍照常做；范围内其它事项才受该条件限制，本地会计算。require的basisRefs必须引用完整前置要求原句；要求始终适用时whenRefs可为空，这些前置准备仍归到所列事项，不另立任务。只有要求本身在某条件下才生效时，whenRefs再引用该条件。无条件cancel才彻底取消，有条件取消是执行限制；defer只表示尚未决定是否做，不能表示延期或改时间；confirm表示明确重新确定是否做。revise表示仍执行同一个原事项，只把时间、地点或规格等安排修订为补充中的完整当前原句。targetRefs仍引用原事项，basisRefs只引用一条包含事项和新安排的完整补充原句，不能只引用孤立时间片段；同一事项最多一个revise。revise不改变originalReviews的当前意愿，仍决定执行时保持planned，不要把它标为cancel/defer。当前只支持单一原事项的无条件revise；whenRefs非空、事项已取消或多个不同修订时不要强行覆盖，保留原话及完整条件/修订依据。不要用变更重复描述普通做事顺序。\n\norderings表达两个独立事项之间原文明确的先后：每项beforeRefs、afterRefs、basisRefs、whenRefs。beforeRefs引用先做事项主体，afterRefs引用后做事项主体，沿用同一sourceId/clauseIds引用，不另造ID。basisRefs须引用补充里完整的先后原句（含先与后两端）；没有明确先后就不填此关系。不因原清单排列顺序覆盖补充明确的先后。规格、准备或查看某物仍附属于其事项，不为排序另造任务。whenRefs只在该先后关系有生效条件时引用完整条件，无条件填[]；条件性先后不能冒充全局固定顺序。待定/取消事项的状态仍由已有字段保留，排序不代表已决定或恢复。\n\nattachments每项targetRefs和refs，前者引用原计划或新增事项主体，后者引用完整补充细节；同一细节不再重复作为独立新事项。未使用的生活原句由本地另留背景，来源快照完整保留。原文事实与后补来源必须分清；不需要在summary/markdown重复全文。\n\n完整来源：\n{}",serde_json::to_string(&serde_json::json!({"sources":units,"originalPlanTargets":original_plan_targets})).expect("source units serialize"))
}

// A paused result already persists its llm_note and the existing diagnostics
// span records it. Retain the exact failed rule there without copying material
// or the provider response. The primary recovery UI stays concise.
fn source_failure(rule:&str,detail:impl std::fmt::Display)->String {
    format!("短备忘整理未通过原句核对：{detail}。原话和补充仍保留，可直接使用或稍后整理。（来源校验 {rule}）")
}

fn source_content_roles(object:&Value,units:&[SourceUnit])->Result<std::collections::HashMap<String,std::collections::HashSet<usize>>,String> {
    let roles=object.get("sourceRoles").and_then(Value::as_array)
        .ok_or_else(||source_failure("ROLES_MISSING","缺少完整的内容与整理要求分类"))?;
    if roles.len()!=units.len(){return Err(source_failure("ROLES_COUNT","来源分类数量与本次材料不一致"));}
    let mut result=std::collections::HashMap::new();
    for role in roles {
        let id=role.get("sourceId").and_then(Value::as_str)
            .ok_or_else(||source_failure("ROLE_SOURCE_MISSING","来源分类缺少来源标识"))?;
        let unit=units.iter().find(|unit|unit.id==id)
            .ok_or_else(||source_failure("ROLE_SOURCE_UNKNOWN","分类引用了本次材料之外的来源"))?;
        let count=clauses(&unit.text).len();let mut seen=std::collections::HashSet::new();
        let mut content=std::collections::HashSet::new();
        for key in ["contentClauseIds","instructionClauseIds","uncertainClauseIds"] {
            let ids=role.get(key).and_then(Value::as_array)
                .ok_or_else(||source_failure("ROLE_IDS_STRUCTURE","来源分类缺少原句数组"))?;
            if ids.len()>count{return Err(source_failure("ROLE_IDS_COUNT","分类的原句数量超出本次来源"));}
            if key=="uncertainClauseIds" && !ids.is_empty(){return Err(source_failure("ROLE_UNCERTAIN","尚有原句不能确定是生活内容还是整理要求"));}
            for value in ids {
                let id=value.as_u64().and_then(|id|usize::try_from(id).ok())
                    .filter(|id|*id>0 && *id<=count)
                    .ok_or_else(||source_failure("ROLE_ID_RANGE","分类原句编号不在本次来源内"))?;
                if !seen.insert(id){return Err(source_failure("ROLE_ID_DUPLICATE","同一原句被重复分类"));}
                if key=="contentClauseIds" {content.insert(id);}
            }
        }
        if seen.len()!=count{return Err(source_failure("ROLE_ID_INCOMPLETE","有原句未完成分类"));}
        if result.insert(unit.id.clone(),content).is_some(){return Err(source_failure("ROLE_SOURCE_DUPLICATE","同一来源重复提交了分类"));}
    }
    Ok(result)
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

pub(super) struct ValidatedPlan {
    pub action_items:Vec<CompanionV1ActionItem>,
    pub pending:Vec<String>,
    pub cancelled:Vec<String>,
    pub background:Vec<String>,
}

struct Quote {source_id:String,ids:Vec<usize>,text:String,supplemental:bool}

fn references(item:&Value,key:&str,units:&[SourceUnit],content:&std::collections::HashMap<String,std::collections::HashSet<usize>>,
    )->Result<Vec<Quote>,String> {
    let Some(value)=item.get(key) else {return Ok(Vec::new());};
    let refs=value.as_array().filter(|refs|refs.len()<=16)
        .ok_or_else(||source_failure("PLAN_REFS_STRUCTURE","计划依据不是适用的引用数组"))?;
    let mut result=Vec::new();let mut seen=std::collections::HashSet::new();
    for reference in refs {
        let id=reference.get("sourceId").and_then(Value::as_str)
            .ok_or_else(||source_failure("PLAN_REF_SOURCE_MISSING","计划依据缺少来源标识"))?;
        let unit=units.iter().find(|unit|unit.id==id)
            .ok_or_else(||source_failure("PLAN_REF_SOURCE_UNKNOWN","计划依据不在本次来源内"))?;
        if key=="supplementRefs" && !unit.supplemental {
            return Err(source_failure("PLAN_SUPPLEMENT_SOURCE","事项规格或准备须引用本次补充里的原句"));
        }
        let parts=clauses(&unit.text);
        let (mut ids,_)=selected_clauses(reference,"clauseIds",&parts,true)
            .map_err(|reason|source_failure("PLAN_REF_CLAUSES",reason))?;
        let allowed=content.get(id).ok_or_else(||source_failure("PLAN_REF_ROLE","计划依据缺少内容分类"))?;
        ids.retain(|id|allowed.contains(id));
        if ids.is_empty(){continue;}
        let key=format!("{id}:{ids:?}");
        if seen.insert(key) {
            result.push(Quote{source_id:unit.id.clone(),text:ids.iter().map(|id|parts[*id-1]).collect::<Vec<_>>().join("；"),ids,supplemental:unit.supplemental});
        }
    }
    Ok(result)
}

struct Plan {
    source_id:String,main_ids:Vec<usize>,text:String,supplemental:bool,
    tentative:bool,conditional:bool,cancelled:bool,basis:Vec<Quote>,details:Vec<Quote>,revision:Option<Quote>,
}

// Resolve only already declared subjects. A source-valid non-subject is a
// separate outcome from an invented/out-of-range source reference.
fn declared_plan_targets(refs:&[Quote],plans:&[Plan])->Result<Vec<usize>,usize> {
    let mut result=Vec::new();
    for (ref_index,reference) in refs.iter().enumerate() {
        let matches=plans.iter().enumerate().filter(|(_,plan)|plan.source_id==reference.source_id
            && plan.main_ids.iter().any(|id|reference.ids.contains(id)))
            .map(|(index,_)|index).collect::<Vec<_>>();
        if reference.ids.iter().any(|id|!matches.iter().any(|index|plans[*index].main_ids.contains(id))) {
            return Err(ref_index);
        }
        for index in matches {if !result.contains(&index){result.push(index);}}
    }
    Ok(result)
}

fn plan_targets(item:&Value,key:&str,plans:&[Plan],units:&[SourceUnit],
    content:&std::collections::HashMap<String,std::collections::HashSet<usize>>)->Result<Vec<usize>,String> {
    let refs=references(item,key,units,content)?;
    if refs.is_empty(){return Err(source_failure("EFFECT_TARGETS_EMPTY","计划变更缺少有效事项原句引用"));}
    declared_plan_targets(&refs,plans).map_err(|index|{
        let reference=&refs[index];
        // IDs only, through the existing persisted diagnostic; no source text
        // or complete provider response is copied into the failure detail.
        let declared=plans.iter().map(|plan|serde_json::json!({"sourceId":plan.source_id,
            "clauseIds":plan.main_ids})).collect::<Vec<_>>();
        source_failure("EFFECT_TARGET_NOT_PLAN_CLAUSE",format!(
            "变更目标引用了未作为事项主体的原句，请区分事项与条件依据；字段={key}；引用={}:{}；已声明主体={}",
            reference.source_id,serde_json::json!(reference.ids),serde_json::json!(declared)))
    })
}


// Keep every complete cited clause when a relation needs clarification. This
// is source text, not an inferred deadline, task, prerequisite or polarity.
fn ordering_words(quotes:&[Quote],units:&[SourceUnit])->String {
    units.iter().filter_map(|unit|{
        let ids=quotes.iter().filter(|q|q.source_id==unit.id).flat_map(|q|q.ids.iter().copied())
            .collect::<std::collections::HashSet<_>>();
        let parts=clauses(&unit.text);
        let text=(1..=parts.len()).filter(|id|ids.contains(id)).map(|id|parts[id-1]).collect::<Vec<_>>().join("；");
        (!text.is_empty()).then_some(text)
    }).collect::<Vec<_>>().join("；")
}

// Every endpoint and basis must already belong to exactly one identical
// subject or complete attached detail. This is existing explicit source
// ownership, never keyword/name matching or a guessed new task/alias.
fn unique_detail_plan_owner(quotes:&[Quote],plans:&[Plan])->Option<usize> {
    let mut owner=None;
    for quote in quotes {
        for id in &quote.ids {
            let subjects=plans.iter().enumerate().filter(|(_,plan)|plan.source_id==quote.source_id
                && plan.main_ids.contains(id)).map(|(index,_)|index).collect::<Vec<_>>();
            let candidates=if !subjects.is_empty(){subjects}else{
                plans.iter().enumerate().filter(|(_,plan)|plan.details.iter().any(|detail|
                    detail.source_id==quote.source_id && detail.ids.contains(id)))
                    .map(|(index,_)|index).collect::<Vec<_>>()
            };
            if candidates.len()!=1{return None;}
            let candidate=candidates[0];
            if owner.is_some_and(|owner|owner!=candidate){return None;}
            owner=Some(candidate);
        }
    }
    owner
}

fn sequence_order(object:&Value,plans:&[Plan],subordinate:&std::collections::HashSet<usize>,
    units:&[SourceUnit],content:&std::collections::HashMap<String,std::collections::HashSet<usize>>)
    ->Result<(Vec<usize>,Vec<String>),String> {
    let original=(0..plans.len()).collect::<Vec<_>>();
    // Previously saved/older relation objects remain readable. A new request
    // explicitly asks for orderings, including an empty array when absent.
    let Some(value)=object.get("orderings") else{return Ok((original,Vec::new()));};
    let relations=value.as_array().filter(|items|items.len()<=64)
        .ok_or_else(||source_failure("ORDER_STRUCTURE","事项先后关系不是适用的数组"))?;
    let mut predecessors=vec![Vec::<usize>::new();plans.len()];let mut questions=Vec::new();let mut evidence=Vec::new();
    for relation in relations {
        let before_refs=references(relation,"beforeRefs",units,content)?;
        let after_refs=references(relation,"afterRefs",units,content)?;
        if before_refs.is_empty() || after_refs.is_empty(){
            return Err(source_failure("EFFECT_TARGETS_EMPTY","计划先后缺少有效事项原句引用"));
        }
        let mut basis=references(relation,"basisRefs",units,content)?;
        if !basis.iter().any(|q|q.supplemental){return Err(source_failure("ORDER_BASIS","先后关系未引用补充里的完整原句"));}
        let when=references(relation,"whenRefs",units,content)?;
        let conditional=!when.is_empty();basis.extend(when);
        let (Ok(before),Ok(after))=(declared_plan_targets(&before_refs,plans),declared_plan_targets(&after_refs,plans)) else {
            // This optional relation quotes real content, but one endpoint is
            // preparation or an otherwise undeclared subject. Do not create a
            // task, guess an alias, silently apply order, or discard the rest
            // of a valid plan. Keep every cited endpoint/basis as clarification;
            // existing standalone exports retain these questions too.
            let mut quotes=before_refs;quotes.extend(after_refs);quotes.extend(basis);
            if !conditional && unique_detail_plan_owner(&quotes,plans).is_some(){
                // A preparation-before-its-own-task relation is already kept
                // in that task's literal detail. It cannot order two separate
                // subjects, so do not ask the user to resolve it again. The
                // original pending/cancelled/conditional state stays intact.
                continue;
            }
            questions.push(format!("先后关系涉及未列为独立待办的原句，仍需确认：{}",ordering_words(&quotes,units)));
            continue;
        };
        let executable=before.iter().chain(&after).all(|index|!subordinate.contains(index)
            && !plans[*index].tentative && !plans[*index].cancelled);
        if conditional || !executable || before.iter().any(|index|after.contains(index)) {
            questions.push(format!("先后顺序仍需确认：{}",ordering_words(&basis,units)));
            continue;
        }
        for next in after {for previous in &before {
            if !predecessors[next].contains(previous){predecessors[next].push(*previous);}
        }}
        evidence.extend(basis);
    }
    for previous in &mut predecessors{previous.sort_unstable();}
    // Visit original positions in order, pulling only explicitly required
    // predecessors ahead of their dependent item. Unrelated items retain the
    // original traversal order where the declared dependencies permit it.
    fn visit(index:usize,predecessors:&[Vec<usize>],marks:&mut[u8],order:&mut Vec<usize>)->bool {
        if marks[index]==2{return true;}
        if marks[index]==1{return false;}
        marks[index]=1;
        for previous in &predecessors[index]{if !visit(*previous,predecessors,marks,order){return false;}}
        marks[index]=2;order.push(index);true
    }
    let mut order=Vec::new();let mut marks=vec![0u8;plans.len()];
    for index in 0..plans.len(){if !visit(index,&predecessors,&mut marks,&mut order){
        // Contradictory valid source relations cannot silently choose a side.
        // Keep all original items/states and expose the complete cited words
        // in the existing questions section, never promote a tentative task.
        questions.push(format!("先后顺序互相冲突，仍需确认：{}",ordering_words(&evidence,units)));
        return Ok((original,questions));
    }}
    Ok((order,questions))
}

pub(super) fn validate(object:&Value,session:&CompanionV1HostSession)->Result<ValidatedPlan,String> {
    let units=source_units(session);let content=source_content_roles(object,&units)?;
    let mut plans=Vec::new();
    // Review each original subject after considering the supplements. Missing
    // review must not silently turn an undecided purchase into a definite task.
    let reviews=object.get("originalReviews").and_then(Value::as_array)
        .filter(|items|items.len()<=64)
        .ok_or_else(||source_failure("ORIGINAL_REVIEWS_STRUCTURE","缺少原事项逐项当前意愿核对"))?;
    let original_count=units.iter().filter(|unit|!unit.supplemental).count();
    if reviews.len()!=original_count{return Err(source_failure("ORIGINAL_REVIEWS_COUNT","当前意愿核对未完整覆盖每个原事项"));}
    let mut reviewed=std::collections::HashSet::new();
    for review in reviews {
        let id=review.get("sourceId").and_then(Value::as_str)
            .ok_or_else(||source_failure("ORIGINAL_REVIEW_SOURCE","当前意愿核对缺少原事项来源"))?;
        if !units.iter().any(|unit|!unit.supplemental && unit.id==id) || !reviewed.insert(id){
            return Err(source_failure("ORIGINAL_REVIEW_SOURCE","当前意愿核对含未知或重复原事项"));
        }
    }
    for unit in units.iter().filter(|unit|!unit.supplemental) {
        let parts=clauses(&unit.text);let allowed=content.get(&unit.id).expect("complete roles");
        if allowed.len()!=parts.len(){return Err(source_failure("BASE_PLAN_ROLE","原话明确计划的原句未完整归为生活内容"));}
        let review=reviews.iter().find(|review|review.get("sourceId").and_then(Value::as_str)==Some(unit.id.as_str())).expect("complete original reviews");
        let intent=review.get("intent").and_then(Value::as_str)
            .filter(|intent|matches!(*intent,"planned"|"tentative"|"cancelled"))
            .ok_or_else(||source_failure("ORIGINAL_REVIEW_INTENT","原事项缺少有效的当前意愿"))?;
        let basis=references(review,"basisRefs",&units,&content)?;
        if intent!="planned" && !basis.iter().any(|quote|quote.supplemental){
            return Err(source_failure("ORIGINAL_REVIEW_BASIS","改变原事项意愿须引用完整后补依据"));
        }
        plans.push(Plan{source_id:unit.id.clone(),main_ids:(1..=parts.len()).collect(),
            text:unit.text.clone(),supplemental:false,tentative:intent=="tentative",conditional:false,cancelled:intent=="cancelled",basis,details:Vec::new(),revision:None});
    }
    let new_items=object.get("newPlans").and_then(Value::as_array).filter(|items|items.len()<=64)
        .ok_or_else(||source_failure("NEW_PLANS_STRUCTURE","新增计划结构尚未完整"))?;
    for item in new_items {
        let id=item.get("sourceId").and_then(Value::as_str)
            .ok_or_else(||source_failure("NEW_PLAN_SOURCE","新增事项缺少来源"))?;
        let source=units.iter().find(|unit|unit.supplemental && unit.id==id)
            .ok_or_else(||source_failure("NEW_PLAN_SOURCE_UNKNOWN","新增事项不在本次补充内"))?;
        let parts=clauses(&source.text);let (mut ids,_)=selected_clauses(item,"clauseIds",&parts,true)
            .map_err(|reason|source_failure("NEW_PLAN_CLAUSES",reason))?;
        let allowed=content.get(id).expect("complete roles");ids.retain(|id|allowed.contains(id));
        if ids.is_empty(){continue;}
        let intent=item.get("intent").and_then(Value::as_str).filter(|intent|matches!(*intent,"planned"|"tentative"))
            .ok_or_else(||source_failure("NEW_PLAN_INTENT","新增事项缺少是否已决定的意愿"))?;
        let mut basis=references(item,"basisRefs",&units,&content)?;
        if intent=="tentative" && basis.is_empty(){
            return Err(source_failure("TENTATIVE_BASIS","待定事项未引用表达尚未决定的原句"));
        }
        let when=references(item,"whenRefs",&units,&content)?;
        basis.extend(when.iter().map(|q|Quote{source_id:q.source_id.clone(),ids:q.ids.clone(),text:q.text.clone(),supplemental:q.supplemental}));
        plans.push(Plan{source_id:id.to_string(),text:ids.iter().map(|id|parts[*id-1]).collect::<Vec<_>>().join("；"),main_ids:ids,
            supplemental:true,tentative:intent=="tentative",conditional:!when.is_empty(),cancelled:false,
            basis,details:references(item,"supplementRefs",&units,&content)?,revision:None});
    }
    let mut shared_rule_sources:std::collections::HashMap<String,std::collections::HashSet<usize>>=std::collections::HashMap::new();
    let updates=object.get("updates").and_then(Value::as_array).filter(|items|items.len()<=64)
        .ok_or_else(||source_failure("EFFECTS_STRUCTURE","计划变更结构尚未完整"))?;
    for item in updates {
        let kind=item.get("kind").and_then(Value::as_str).filter(|kind|matches!(*kind,"only"|"cancel"|"defer"|"require"|"confirm"|"revise"))
            .ok_or_else(||source_failure("EFFECT_KIND","计划变更类型无效"))?;
        let targets=plan_targets(item,"targetRefs",&plans,&units,&content)?;
        let mut basis=references(item,"basisRefs",&units,&content)?;
        if !basis.iter().any(|q|q.supplemental){return Err(source_failure("EFFECT_BASIS","计划变更未引用补充原句"));}
        let when=references(item,"whenRefs",&units,&content)?;let conditional=!when.is_empty();
        if kind=="revise" {
            // Current commitment and the wording of its arrangement are separate.
            // Retain the original target identity for ordering/provenance, and
            // accept only one whole supplemental clause as the current wording.
            if conditional || targets.len()!=1 || basis.len()!=1 || !basis[0].supplemental || basis[0].ids.len()!=1 {
                return Err(source_failure("REVISION_SCOPE","事项修订须有单一原事项和一条无条件的完整后补依据"));
            }
            let plan=&mut plans[targets[0]];
            if plan.supplemental || plan.cancelled || plan.revision.is_some() {
                return Err(source_failure("REVISION_TARGET","已取消、新增或重复修订的事项不能被静默覆盖"));
            }
            plan.revision=Some(basis.remove(0));
            continue;
        }
        basis.extend(when);
        if kind=="require" && !conditional {
            // An always-applicable prerequisite is not missing a weather/time
            // predicate. Its already validated complete source clauses qualify
            // the existing plan as preparation, without inventing a condition,
            // promoting a tentative/cancelled item or creating another task.
            for index in targets {
                plans[index].details.extend(basis.iter().map(|q|Quote{source_id:q.source_id.clone(),
                    ids:q.ids.clone(),text:q.text.clone(),supplemental:q.supplemental}));
            }
            continue;
        }
        // A rule explicitly scoped to the complete plan belongs to the
        // complete checklist. Do not make it look like a preparation for each
        // excluded task. Its complete literal clauses remain visible once.
        let shared_rule=kind=="only" && item.get("scopeRefs").and_then(Value::as_str)==Some("all");
        if shared_rule {
            for quote in &basis {shared_rule_sources.entry(quote.source_id.clone()).or_default().extend(quote.ids.iter().copied());}
        }
        let affected=if kind=="only" {
            let scope=if item.get("scopeRefs").and_then(Value::as_str)==Some("all") {(0..plans.len()).collect::<Vec<_>>()}
                else{plan_targets(item,"scopeRefs",&plans,&units,&content)?};
            if targets.iter().any(|target|!scope.contains(target)){return Err(source_failure("EXCLUSIVE_SCOPE","只做名单超出声明范围"));}
            scope.into_iter().filter(|index|!targets.contains(index)).collect::<Vec<_>>()
        }else{targets};
        for index in affected {
            let plan=&mut plans[index];
            if !plan.supplemental && !conditional && matches!(kind,"confirm"|"defer"|"cancel") {
                let agrees=match kind {"confirm"=>!plan.tentative&&!plan.cancelled,"defer"=>plan.tentative&&!plan.cancelled,_=>plan.cancelled};
                if !agrees{return Err(source_failure("ORIGINAL_REVIEW_EFFECT_CONFLICT","原事项当前意愿与无条件变更互相矛盾"));}
                // One authority for current intent. Preserve the cited effect
                // as evidence instead of allowing array order to overwrite it.
            }else{match kind {
                "confirm" if !plan.supplemental=>plan.conditional|=conditional,
                "confirm"=>{plan.tentative=false;plan.cancelled=false;plan.conditional=conditional;plan.basis.clear();},
                "defer" if !conditional=>plan.tentative=true,
                "cancel"|"only" if !conditional=>{plan.cancelled=true;plan.basis.clear();},
                _=>plan.conditional=true,
            }}
            if !shared_rule {
                plan.basis.extend(basis.iter().map(|q|Quote{source_id:q.source_id.clone(),ids:q.ids.clone(),text:q.text.clone(),supplemental:q.supplemental}));
            }
        }
    }
    let attachments=object.get("attachments").and_then(Value::as_array).filter(|items|items.len()<=64)
        .ok_or_else(||source_failure("ATTACHMENTS_STRUCTURE","事项补充结构尚未完整"))?;
    for item in attachments {
        let targets=plan_targets(item,"targetRefs",&plans,&units,&content)?;let refs=references(item,"refs",&units,&content)?;
        if refs.iter().any(|q|!q.supplemental){return Err(source_failure("ATTACHMENT_SOURCE","事项补充不在后补原句内"));}
        for index in targets {plans[index].details.extend(refs.iter().map(|q|Quote{source_id:q.source_id.clone(),ids:q.ids.clone(),text:q.text.clone(),supplemental:q.supplemental}));}
    }
    // The provider may quote the same preparation both as a new action and
    // as a detail of an existing plan. A full literal ownership edge already
    // identifies that duplicate: render it once under the existing plan.
    // Only merge ordinary unqualified plans. A separate intention, condition
    // or cancellation retains its own state and cannot disappear here.
    let mut subordinate=std::collections::HashSet::new();
    for index in 0..plans.len() {
        let candidate=&plans[index];
        if !candidate.supplemental || candidate.tentative || candidate.conditional
            || candidate.cancelled || !candidate.basis.is_empty() {continue;}
        let parent=plans.iter().position(|plan|!plan.supplemental && !plan.tentative
            && !plan.conditional && !plan.cancelled
            && candidate.main_ids.iter().all(|id|plan.details.iter().any(|quote|
                quote.source_id==candidate.source_id && quote.ids.contains(id))));
        if let Some(parent)=parent {
            let details=plans[index].details.iter().map(|q|Quote{source_id:q.source_id.clone(),
                ids:q.ids.clone(),text:q.text.clone(),supplemental:q.supplemental}).collect::<Vec<_>>();
            plans[parent].details.extend(details);
            subordinate.insert(index);
        }
    }
    let (order,ordering_questions)=sequence_order(object,&plans,&subordinate,&units,&content)?;
    let mut positions=vec![0usize;plans.len()];
    for (position,index) in order.into_iter().enumerate(){positions[index]=position;}
    let mut ordered=plans.into_iter().enumerate().collect::<Vec<_>>();
    ordered.sort_by_key(|(index,_)|positions[*index]);
    let mut result=ValidatedPlan{action_items:Vec::new(),pending:ordering_questions.clone(),cancelled:Vec::new(),background:Vec::new()};
    let mut used=shared_rule_sources.clone();
    for (index,plan) in ordered {
        if subordinate.contains(&index){continue;}
        used.entry(plan.source_id.clone()).or_default().extend(plan.main_ids.iter().copied());
        let revision=plan.revision;
        if let Some(quote)=&revision {
            used.entry(quote.source_id.clone()).or_default().extend(quote.ids.iter().copied());
        }
        let mut text=revision.as_ref().map(|quote|format!("用户变更：{}",quote.text)).unwrap_or(plan.text);
        let mut extra=Vec::new();
        let mut attached:std::collections::HashMap<String,std::collections::HashSet<usize>>=std::collections::HashMap::new();
        for quote in plan.basis.iter().chain(&plan.details) {
            used.entry(quote.source_id.clone()).or_default().extend(quote.ids.iter().copied());
            // Two references can overlap without being identical. Preserve
            // each complete source clause once, in its original order, so
            // preparation is not moved behind an overlapping condition quote.
            attached.entry(quote.source_id.clone()).or_default().extend(quote.ids.iter().copied()
                .filter(|id|(quote.source_id!=plan.source_id || !plan.main_ids.contains(id))
                    && !revision.as_ref().is_some_and(|current|current.source_id==quote.source_id && current.ids.contains(id))));
        }
        for unit in &units {
            let Some(ids)=attached.get(&unit.id) else {continue;};let parts=clauses(&unit.text);
            let words=(1..=parts.len()).filter(|id|ids.contains(id)).map(|id|parts[id-1]).collect::<Vec<_>>().join("；");
            if !words.is_empty(){extra.push(if unit.supplemental{words}else{format!("原话：{words}")});}
        }
        if !extra.is_empty(){text.push_str(&format!("（补充：{}）",extra.join("；")));}
        if plan.supplemental{text=format!("用户补充：{text}");}
        if plan.cancelled{result.cancelled.push(format!("已取消的计划：{text}"));}
        else if plan.tentative{result.pending.push(format!("待定想法：{text}"));}
        else{result.action_items.push(CompanionV1ActionItem{text:if plan.conditional{format!("有条件：{text}")}else{text},owner:None,due:None});}
    }
    let shared=units.iter().filter_map(|unit|{
        let ids=shared_rule_sources.get(&unit.id)?;let parts=clauses(&unit.text);
        let words=(1..=parts.len()).filter(|id|ids.contains(id)).map(|id|parts[id-1]).collect::<Vec<_>>().join("；");
        (!words.is_empty()).then_some(if unit.supplemental{words}else{format!("原话：{words}")})
    }).collect::<Vec<_>>().join("；");
    let mut common=Vec::new();
    if !shared.is_empty(){common.push(format!("共同适用规则：{shared}"));}
    // An exported standalone task/list must not lose the unresolved sequence
    // merely because its questions section is outside the action export.
    // Keep the full clarification/source words attached to each existing task;
    // the existing literal fold displays/exports the shared notice once.
    if !ordering_questions.is_empty(){common.push(ordering_questions.join("；"));}
    let common=common.join("；");
    if !common.is_empty() {
        let multiple=result.action_items.len()>1;
        if result.action_items.is_empty(){result.background.push(common.clone());}
        for action in &mut result.action_items {
            // Existing literal shared-supplement UI/export folding presents
            // this once, with every independently exported task still carrying
            // the complete scope rule. A single task uses one balanced wrapper.
            if !multiple && action.text.ends_with('）') && action.text.contains("（补充：") {
                action.text.pop();action.text.push_str(&format!("；{common}）"));
            }else{action.text.push_str(&format!("（补充：{common}）"));}
        }
    }
    for unit in &units {
        let parts=clauses(&unit.text);let allowed=content.get(&unit.id).expect("complete roles");
        let remaining=(1..=parts.len()).filter(|id|allowed.contains(id) && !used.get(&unit.id).is_some_and(|used|used.contains(id)))
            .map(|id|parts[id-1]).collect::<Vec<_>>();
        if !remaining.is_empty(){result.background.push(format!("{}：{}",if unit.supplemental{"补充背景"}else{"原话背景"},remaining.join("；")));}
    }
    Ok(result)
}
