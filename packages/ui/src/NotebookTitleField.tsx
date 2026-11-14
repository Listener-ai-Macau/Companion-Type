import {useLayoutEffect,useRef,type TextareaHTMLAttributes} from 'react';
import './notebookTitleField.css';

/** The same single-line title value, allowed to wrap visually like a document. */
export function NotebookTitleField({value,onValueChange,...props}:Omit<TextareaHTMLAttributes<HTMLTextAreaElement>,'value'|'onChange'|'rows'>&{value:string;onValueChange:(value:string)=>void}){
 const field=useRef<HTMLTextAreaElement>(null);
 const fit=()=>{const node=field.current;if(!node)return;node.style.height='auto';node.style.height=`${node.scrollHeight+node.offsetHeight-node.clientHeight}px`;};
 useLayoutEffect(fit,[value]);
 useLayoutEffect(()=>{const node=field.current;if(!node)return;let width=node.getBoundingClientRect().width;const observer=new ResizeObserver(()=>{const next=node.getBoundingClientRect().width;if(Math.abs(next-width)<.5)return;width=next;fit();});observer.observe(node);return()=>observer.disconnect();},[]);
 return <textarea {...props} ref={field} rows={1} className={`notebook-title-field ${props.className||''}`.trim()} value={value} onChange={event=>onValueChange(event.currentTarget.value.replace(/[\r\n]/g,''))} onKeyDown={event=>{if(event.key==='Enter')event.preventDefault();props.onKeyDown?.(event);}}/>;
}
