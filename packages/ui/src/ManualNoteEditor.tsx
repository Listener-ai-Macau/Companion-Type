import {useEffect,useRef,useState} from 'react';
import {Plus,Trash2} from 'lucide-react';
import type {ManualNoteKind} from '../../core/src/manualNoteContext';
import './manualNoteContext.css';

export function hasIncompleteManualItems(kind:ManualNoteKind,text:string){return kind==='followup'&&text.split(/\r?\n/).some(line=>/^\s*[-*]\s+\[[ xX]\]\s*$/.test(line));}

type Props={kind:ManualNoteKind;text:string;onChange:(text:string)=>void;disabled?:boolean;label:string;placeholder?:string};
/** Editing is a projection of the existing note text; no second task store. */
export function ManualNoteEditor({kind,text,onChange,disabled=false,label,placeholder}:Props){
 const [raw,setRaw]=useState(false),[error,setError]=useState('');
 const nextItem=useRef<HTMLInputElement>(null);
 useEffect(()=>{setRaw(false);setError('');},[kind]);
 const lines=text?text.split('\n'):[];
 const body=(line:string)=>line.endsWith('\r')?line.slice(0,-1):line;
 const item=(line:string)=>/^(\s*[-*]\s+\[)([ xX])(\]\s+)(.*)$/.exec(body(line));
 const commit=(next:string)=>{if(next.length>4000){setError('这条备注最多4000字符；输入尚未替换，请缩短后再加。');return;}setError('');onChange(next);};
 const replace=(index:number,value:string)=>commit(lines.map((line,i)=>i===index?value+(line.endsWith('\r')?'\r':''):line).join('\n'));
 const numbered=lines.some(line=>/^\s*\d+[.、)）]\s*\S/.test(body(line))&&!item(line));
 const convertible=lines.some(line=>body(line).trim()&&!item(line));
 const convert=()=>commit(lines.map(line=>{
  if(item(line)||!body(line).trim())return line;
  const match=/^(\s*)\d+[.、)）]\s*(.+)$/.exec(body(line));
  if(numbered&&!match)return line;
  return (match?match[1]+'- [ ] '+match[2]:'- [ ] '+body(line))+(line.endsWith('\r')?'\r':'');
 }).join('\n'));
 const plain=<label className="manual-editor-text"><span>{kind==='followup'?'跟进内容':'备注内容'}</span><textarea aria-label={label} rows={4} maxLength={4000} value={text} onChange={event=>commit(event.target.value)} disabled={disabled} placeholder={placeholder}/></label>;
 if(kind!=='followup')return plain;
 return <div className="manual-note-editor">
  <div className="manual-editor-heading"><strong>跟进清单</strong><button type="button" disabled={disabled} onClick={()=>setRaw(!raw)}>{raw?'按事项编辑':'按原格式编辑'}</button></div>
  <p className="manual-editor-description">记录自己的跟进，保存后可逐项勾选；不代表会议已经作出决定。</p>
  {raw?plain:<div role="group" aria-label="跟进清单编辑">
   {lines.map((line,index)=>{
    const match=item(line);
    if(!match)return body(line)?<label className="manual-editor-text manual-editor-description-line" key={'row-'+index}><span className="visually-hidden">跟进说明 {index+1}</span><textarea aria-label={'跟进说明 '+(index+1)} rows={2} value={body(line)} disabled={disabled} onChange={event=>replace(index,event.target.value)}/></label>:<div className="manual-editor-gap" key={'row-'+index} aria-hidden="true"/>;
    return <div className="manual-edit-row" key={'row-'+index}>
     <input type="checkbox" aria-label={'完成跟进事项 '+(index+1)} checked={match[2].toLowerCase()==='x'} disabled={disabled} onChange={event=>replace(index,match[1]+(event.target.checked?'x':' ')+match[3]+match[4])}/>
     <input type="text" aria-label={'跟进事项 '+(index+1)} value={match[4]} disabled={disabled} placeholder="需要做什么…" onChange={event=>replace(index,match[1]+match[2]+match[3]+event.target.value)} onKeyDown={event=>{if(event.key==='Enter'&&!event.nativeEvent.isComposing){event.preventDefault();nextItem.current?.focus();}}}/>
     <button type="button" aria-label={'移除跟进事项 '+(index+1)} disabled={disabled} onClick={()=>commit(lines.filter((_,i)=>i!==index).join('\n'))}><Trash2 size={15}/></button>
    </div>;
   })}
   <div className="manual-edit-row manual-edit-new" key={'row-'+lines.length}>
    <Plus size={18} aria-hidden="true"/>
    <input type="text" ref={nextItem} aria-label="新增跟进事项" value="" disabled={disabled} placeholder="添加一项需要跟进的事…" onChange={event=>{if(event.target.value)commit(text+(text?'\n':'')+'- [ ] '+event.target.value);}}/>
   </div>
   {convertible&&<button type="button" className="manual-convert-lines" disabled={disabled} onClick={convert}>{numbered?'将编号列表转为待办':'将非空文字行转为待办'}</button>}
  </div>}
  {hasIncompleteManualItems(kind,text)&&<p role="status" className="manual-editor-description">有一项还没有内容，请填写或移除后保存。</p>}{error&&<p role="alert">{error}</p>}
 </div>;
}
