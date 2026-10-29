import {useEffect,useRef,useState} from 'react';
import {CalendarTimeEditor} from './CalendarTimeEditor';
import {readableCalendarTime} from './calendarTime';

type Fields={due:string;owner:string};
export type CommonActionRow=Fields & {eligible:boolean};

// Apply only authored, nonempty values. Empty common fields never clear a row.
export function commonFieldPatch(row:CommonActionRow, fields:Fields, replace:boolean):Partial<Fields>{
  if(!row.eligible)return {};
  const patch:Partial<Fields>={};
  for(const key of ['due','owner'] as const){
    const value=fields[key].trim();
    if(value && value!==row[key] && (replace || !row[key].trim()))patch[key]=value;
  }
  return patch;
}

export function ActionListCommonFields({rows,revision,disabled,onApply,onPending}:{
  rows:CommonActionRow[];revision:string;disabled:boolean;
  onApply:(fields:Fields,replace:boolean)=>void;onPending?:(delta:1|-1)=>void;
}){
  const [draft,setDraft]=useState<(Fields & {revision:string;replace:boolean})|null>(null);
  const dialog=useRef<HTMLDialogElement|null>(null),pending=useRef<typeof onPending>(undefined),applying=useRef(false);
  const finish=()=>{const callback=pending.current;pending.current=undefined;callback?.(-1);};
  useEffect(()=>()=>finish(),[]);
  useEffect(()=>{if(draft&&!dialog.current?.open)dialog.current?.showModal();},[!!draft]);
  const close=()=>{dialog.current?.close();setDraft(null);finish();};
  const eligible=rows.filter(row=>row.eligible);
  const begin=()=>{
    if(disabled||draft||eligible.length<2)return;
    const common=(key:keyof Fields)=>{const values=[...new Set(eligible.map(row=>row[key]).filter(value=>value.trim()))];return values.length===1?values[0]:'';};
    pending.current=onPending;onPending?.(1);applying.current=false;
    setDraft({due:common('due'),owner:common('owner'),revision,replace:false});
  };
  const changes=draft?eligible.map(row=>commonFieldPatch(row,draft,draft.replace)):[];
  const changed=changes.filter(fields=>Object.keys(fields).length).length;
  const replacements=draft?eligible.filter((row,index)=>Object.keys(changes[index]).some(key=>row[key as keyof Fields].trim())).length:0;
  const stale=!!draft&&draft.revision!==revision;
  return <>
    {eligible.length>=2?<button type="button" className="ct-text-button" disabled={disabled} onClick={begin}>设置共同时间与负责人</button>:null}
    {draft?<dialog ref={dialog} aria-label="共同时间与负责人" onCancel={event=>{event.preventDefault();close();}} onClose={()=>{setDraft(null);finish();}}
      style={{width:'min(92vw,30rem)',maxHeight:'85vh',overflow:'auto',boxSizing:'border-box',padding:24,border:'1px solid #c7d3c9',borderRadius:16}}>
      <h3>一次填写，多项使用</h3>
      <p className="ct-step-meta">只处理当前 {eligible.length} 条未完成事项；已完成事项不改。应用后仍可单独调整，最后点“保存清单”或“保存修改”才会保存。</p>
      {readableCalendarTime(draft.due)!==draft.due?<div style={{marginBottom:12}}>
        <p className="ct-step-meta">已确认的共同日历时间</p><p>{readableCalendarTime(draft.due)}</p>
        <button type="button" className="ct-text-button" disabled={disabled||stale} onClick={()=>setDraft({...draft,due:''})}>改用共同文字时间</button>
      </div>:<label style={{display:'block',marginBottom:12}}>共同时间说明（文字）
        <input aria-label="共同时间说明" value={draft.due} disabled={disabled} placeholder="例如：周六；留空不改时间"
          style={{display:'block',width:'100%',boxSizing:'border-box'}} onChange={event=>setDraft({...draft,due:event.target.value})}/></label>}
      <CalendarTimeEditor value={draft.due} label="共同时间" scope="common" disabled={disabled||stale} onPending={onPending}
        onConfirm={due=>setDraft(current=>current?{...current,due}:current)}/>
      <label style={{display:'block',marginBottom:12}}>共同负责人
        <input aria-label="共同负责人" value={draft.owner} disabled={disabled} placeholder="例如：我；留空不改负责人"
          style={{display:'block',width:'100%',boxSizing:'border-box'}} onChange={event=>setDraft({...draft,owner:event.target.value})}/></label>
      <p className="ct-step-meta">已有字段只有一个相同值时会预填供核对。“周六”等文字不会自动换算；需要日历时，可在上方明确确认日期。</p>
      <label><input type="checkbox" aria-label="同时替换已有时间或负责人" checked={draft.replace} disabled={disabled}
        onChange={event=>setDraft({...draft,replace:event.target.checked})}/> 同时替换已有值</label>
      <p className="ct-step-meta">默认只补空白字段，保留各项已有设置。勾选后，会将上面非空的字段应用到全部未完成事项。</p>
      <p role="status">{stale?'清单内容已变化，请取消后重新打开；本次输入尚未应用。'
        :changed?`将修改 ${changed} 条事项${replacements?`，其中 ${replacements} 条已有设置会被替换`:''}。`
          :'没有需要修改的字段。留空不会清除已有设置。'}</p>
      <div className="ct-button-row">
        <button type="button" className="ct-action ct-action-primary" disabled={disabled||stale||!changed}
          onClick={()=>{if(disabled||stale||!changed||applying.current)return;applying.current=true;onApply({due:draft.due,owner:draft.owner},draft.replace);close();}}>
          {draft.replace?'应用到全部未完成事项':'补充空白字段'}</button>
        <button type="button" className="ct-action" onClick={close}>取消</button>
      </div>
    </dialog>:null}
  </>;
}
