import {useEffect,useRef,useState} from 'react';
import {companionMinutesReferencedSources,type CompanionTranscriptSource} from '@companion-type/core';
import {ActionListCommonFields,commonFieldPatch} from './ActionListCommonFields';
import {CalendarTimeEditor} from './CalendarTimeEditor';
import {readableCalendarTime} from './calendarTime';
import {nativeActionParts,actionTaskBody,type ActionMetadata} from './actionMetadata';

type Metadata=ActionMetadata;
type Row={id:number;raw:string;text:string;prefix:string;metadata:Metadata[];changed:boolean};

// Only the existing, complete native suffix is structured. Unknown brackets or
// duplicate/unknown fields remain ordinary editable text; no dates are inferred.
function readRow(raw:string,id:number):Row{
  const prefix=raw.match(/^\[[ xX]\]\s+/)?.[0]??'';
  const {body,metadata}=nativeActionParts(raw.slice(prefix.length));
  return {id,raw,prefix,text:actionTaskBody(body,metadata),metadata,changed:false};
}
function writeRow(row:Row):string{
  if(!row.changed)return row.raw;
  const fields=row.metadata.filter(field=>field.value.trim());
  return row.prefix+row.text+(fields.length?' ('+fields.map(field=>`${field.key}: ${field.value}`).join(', ')+')':'');
}

export function ActionListEditor({value,onChange,disabled,onCalendarPending,calendarRequestKey,calendarRequestRow,calendarRequestTimed,calendarOnly=false,calendarAll=false,sourceSegments=[],recordingTime}:{value:string;onChange:(value:string)=>void;disabled:boolean;onCalendarPending?:(delta:1|-1)=>void;calendarRequestKey?:string;calendarRequestRow?:number;calendarRequestTimed?:boolean;calendarOnly?:boolean;calendarAll?:boolean;sourceSegments?:readonly CompanionTranscriptSource[];recordingTime?:string}){
  const nextId=useRef(0),sent=useRef(value);
  const calendarIntent=useRef<{key?:string;rowId?:number}>({});
  const parse=(text:string)=>text?text.split(/\r?\n/).map(raw=>readRow(raw,nextId.current++)):[readRow('',nextId.current++)];
  const [rows,setRows]=useState<Row[]>(()=>parse(value));
  useEffect(()=>{
    if(value!==sent.current){sent.current=value;setRows(parse(value));}
  },[value]);
  const update=(next:Row[])=>{
    setRows(next);
    // An added empty row has no authored content. Typed content is immediately
    // part of the existing parent draft, so its unsaved/conflict guards apply.
    const text=next.filter(row=>row.text.trim()).map(writeRow).join('\n');
    sent.current=text;onChange(text);
  };
  const change=(id:number,patch:Partial<Row>)=>update(rows.map(row=>row.id===id?{...row,...patch,changed:true}:row));
  const metadata=(row:Row,key:Metadata['key'],value:string)=>{
    const fields=[...row.metadata],index=fields.findIndex(field=>field.key===key);
    if(index<0){if(value)fields.push({key,value});}else fields[index]={key,value};
    change(row.id,{metadata:fields});
  };
  const pending=(row:Row)=>!!row.text.trim()&&!/^\[[xX]\]\s/.test(row.prefix);
  const due=(row:Row)=>row.metadata.find(field=>field.key==='due')?.value??'';
  // Start with an unresolved item, then a date-only item needing a clock.
  // Already confirmed earlier rows must not hide the one the user is fixing.
  const unresolved=rows.findIndex(row=>pending(row)&&readableCalendarTime(due(row))===due(row));
  const dateOnly=rows.findIndex(row=>pending(row)&&/^\d{4}-\d{2}-\d{2}(前)?$/.test(due(row)));
  const candidate=unresolved>=0?unresolved:dateOnly>=0?dateOnly:rows.findIndex(pending);
  // One explicit review request opens one stable row. Confirming it changes
  // its metadata, but must not automatically open another row and block Save.
  if(calendarIntent.current.key!==calendarRequestKey){
    calendarIntent.current={key:calendarRequestKey,rowId:rows[calendarRequestRow??candidate]?.id};
  }
  const calendarTarget=rows.findIndex(row=>row.id===calendarIntent.current.rowId);
  return <div className="ct-action-list-editor">
    {!calendarOnly?<p className="ct-step-meta" role={calendarRequestKey?"status":undefined}>{calendarRequestKey?"先确认要放入日历的日期或时刻；确认后保存修改，再导出。原时间说明仍在，未替你猜日期。":"时间说明先按文字保存；需要导入日历时，再确认日期与时刻。"}</p>:null}
    {!calendarOnly?<ActionListCommonFields revision={rows.map(writeRow).join('\n')} disabled={disabled} onPending={onCalendarPending}
      rows={rows.map(row=>({eligible:pending(row),due:due(row),owner:row.metadata.find(field=>field.key==='owner')?.value??''}))}
      onApply={(fields,replace)=>update(rows.map(row=>{
        const patch=commonFieldPatch({eligible:pending(row),due:due(row),owner:row.metadata.find(field=>field.key==='owner')?.value??''},fields,replace);
        if(!Object.keys(patch).length)return row;
        const metadata=[...row.metadata];
        for(const key of ['due','owner'] as const){const value=patch[key];if(value===undefined)continue;
          const index=metadata.findIndex(field=>field.key===key);if(index<0)metadata.push({key,value});else metadata[index]={key,value};}
        return {...row,metadata,changed:true};
      }))}/>:null}
    {rows.map((row,index)=>calendarOnly&&!calendarAll&&index!==calendarTarget?null:<div key={row.id} className="ct-action-edit-row" style={{marginBottom:12}}>
      {calendarOnly?<p><strong>{row.text}</strong></p>:<div style={{display:'flex',gap:8,alignItems:'start'}}>
        <label style={{flex:1}}><span className="ct-step-meta">待办 {index+1}</span>
          <input style={{width:'100%',boxSizing:'border-box'}} aria-label={`待办 ${index+1} 内容`} value={row.text} disabled={disabled}
            placeholder="一件要做的事" onChange={event=>change(row.id,{text:event.target.value})}/></label>
        <button type="button" className="ct-text-button" disabled={disabled} aria-label={`删除待办 ${index+1}`}
          onClick={()=>update(rows.filter(item=>item.id!==row.id))}>删除</button>
      </div>}
      <details open={calendarOnly||calendarRequestKey&&index===calendarTarget?true:undefined}>
        <summary className="ct-step-meta" aria-label={`待办 ${index+1} 时间与负责人`}>
          {calendarOnly?'截止时间':'时间与负责人'}
          {row.metadata.filter(field=>field.value.trim()).map(field=><span key={field.key} style={{marginLeft:10,overflowWrap:'anywhere'}}>
            {field.key==='due'?((field.value.endsWith('前')||readableCalendarTime(field.value)!==field.value)?'截止：':'时间：'):'负责人：'}{field.key==='due'?readableCalendarTime(field.value):field.value}
          </span>)}
        </summary>
        {calendarOnly?<p className="ct-step-meta">当前截止：{due(row)?readableCalendarTime(due(row)):'未注明'}</p>:row.metadata.some(field=>field.key==='due'&&readableCalendarTime(field.value)!==field.value)?<div>
          <span className="ct-step-meta">日历时间</span>
          <p>{readableCalendarTime(row.metadata.find(field=>field.key==='due')!.value)}</p>
          <button type="button" className="ct-text-button" disabled={disabled}
            aria-label={`待办 ${index+1} 清除日历时间，改用文字说明`}
            onClick={()=>metadata(row,'due','')}>清除日历时间，改用文字说明</button>
        </div>:<label><span className="ct-step-meta">时间说明（文字）</span>
          <input style={{width:'100%',boxSizing:'border-box'}} aria-label={`待办 ${index+1} 时间`} value={row.metadata.find(field=>field.key==='due')?.value??''}
            disabled={disabled} placeholder="未注明" onChange={event=>metadata(row,'due',event.target.value)}/></label>}
        <div style={{margin:'4px 0 8px'}}>
        <CalendarTimeEditor compact={calendarOnly} openWithTime={calendarRequestTimed} openRequestKey={index===calendarTarget?calendarRequestKey:undefined} label={`待办 ${index+1}`} value={row.metadata.find(field=>field.key==='due')?.value??''}
          disabled={disabled} sourceContext={(()=>{const matches=companionMinutesReferencedSources(sourceSegments,row.text);return matches.length===1?{text:matches[0].text,recordingTime}:undefined;})()} onConfirm={value=>metadata(row,'due',value)} onPending={onCalendarPending}/>
        </div>
        {!calendarOnly?<label style={{display:'block'}}><span className="ct-step-meta">负责人</span>
          <input style={{width:'100%',boxSizing:'border-box'}} aria-label={`待办 ${index+1} 负责人`} value={row.metadata.find(field=>field.key==='owner')?.value??''}
            disabled={disabled} placeholder="未注明" onChange={event=>metadata(row,'owner',event.target.value)}/></label>:null}
      </details>
    </div>)}
    {!calendarOnly?<button type="button" className="ct-text-button" disabled={disabled}
      onClick={()=>setRows([...rows,readRow('',nextId.current++)])}>添加一项</button>:null}
  </div>;
}
