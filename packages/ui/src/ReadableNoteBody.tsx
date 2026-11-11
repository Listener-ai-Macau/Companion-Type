import {useEffect,useId,useState,type ReactNode} from 'react';
import {notePreview} from './noteReading';
import './noteReading.css';

export function ReadableNoteBody({text,className,defaultExpanded=false,forceExpanded=false,renderText=(text:string)=>text}:{text:string;className:string;defaultExpanded?:boolean;forceExpanded?:boolean;renderText?:(text:string)=>ReactNode}){
 const [choice,setChoice]=useState<boolean>();const id=useId(),preview=notePreview(text),long=preview.length<text.length;
 useEffect(()=>setChoice(undefined),[text]);
 const expanded=!long||forceExpanded||(choice??defaultExpanded);
 return <div className="note-reading-body"><p id={id} className={className}>{renderText(expanded?text:preview)}{!expanded&&'…'}</p>{long&&(forceExpanded?<small className="note-reading-match">搜索命中 · 全文已展开</small>:<button type="button" className="note-reading-toggle" aria-controls={id} aria-expanded={expanded} onClick={()=>setChoice(!expanded)}>{expanded?'收起长备注':'展开全文'}</button>)}</div>;
}
