import {useEffect,useRef,useState} from 'react';
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

export function ActionListEditor({value,onChange,disabled,onCalendarPending}:{value:string;onChange:(value:string)=>void;disabled:boolean;onCalendarPending?:(delta:1|-1)=>void}){
  const nextId=useRef(0),sent=useRef(value);
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
  return <div className="ct-action-list-editor">
    <p className="ct-step-meta">时间说明先按文字保存；需要导入日历时，再确认日期与时刻。</p>
    {rows.map((row,index)=><div key={row.id} className="ct-action-edit-row" style={{marginBottom:12}}>
      <div style={{display:'flex',gap:8,alignItems:'start'}}>
        <label style={{flex:1}}><span className="ct-step-meta">待办 {index+1}</span>
          <input style={{width:'100%',boxSizing:'border-box'}} aria-label={`待办 ${index+1} 内容`} value={row.text} disabled={disabled}
            placeholder="一件要做的事" onChange={event=>change(row.id,{text:event.target.value})}/></label>
        <button type="button" className="ct-text-button" disabled={disabled} aria-label={`删除待办 ${index+1}`}
          onClick={()=>update(rows.filter(item=>item.id!==row.id))}>删除</button>
      </div>
      <details open={row.metadata.some(field=>field.value.trim())||undefined}>
        <summary className="ct-step-meta">时间与负责人</summary>
        {row.metadata.some(field=>field.key==='due'&&readableCalendarTime(field.value)!==field.value)?<div>
          <span className="ct-step-meta">日历时间</span>
          <p>{readableCalendarTime(row.metadata.find(field=>field.key==='due')!.value)}</p>
          <button type="button" className="ct-text-button" disabled={disabled}
            aria-label={`待办 ${index+1} 清除日历时间，改用文字说明`}
            onClick={()=>metadata(row,'due','')}>清除日历时间，改用文字说明</button>
        </div>:<label><span className="ct-step-meta">时间说明（文字）</span>
          <input style={{width:'100%',boxSizing:'border-box'}} aria-label={`待办 ${index+1} 时间`} value={row.metadata.find(field=>field.key==='due')?.value??''}
            disabled={disabled} placeholder="未注明" onChange={event=>metadata(row,'due',event.target.value)}/></label>}
        <CalendarTimeEditor label={`待办 ${index+1}`} value={row.metadata.find(field=>field.key==='due')?.value??''}
          disabled={disabled} onConfirm={value=>metadata(row,'due',value)} onPending={onCalendarPending}/>
        <label><span className="ct-step-meta">负责人</span>
          <input style={{width:'100%',boxSizing:'border-box'}} aria-label={`待办 ${index+1} 负责人`} value={row.metadata.find(field=>field.key==='owner')?.value??''}
            disabled={disabled} placeholder="未注明" onChange={event=>metadata(row,'owner',event.target.value)}/></label>
      </details>
    </div>)}
    <button type="button" className="ct-text-button" disabled={disabled}
      onClick={()=>setRows([...rows,readRow('',nextId.current++)])}>添加一项</button>
  </div>;
}
