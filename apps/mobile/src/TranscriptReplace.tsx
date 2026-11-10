import {useState} from 'react';
import './transcriptReplace.css';

/** Literal changes to the current editor draft only; native correction owns saving. */
export function TranscriptReplace({text,disabled,onChange}:{text:string;disabled:boolean;onChange:(text:string)=>void}){
 const [find,setFind]=useState(''),[replacement,setReplacement]=useState(''),[notice,setNotice]=useState('');
 const [last,setLast]=useState<{before:string;after:string}|null>(null);
 const count=find?text.split(find).length-1:0;
 const nextLength=text.length+count*(replacement.length-find.length);
 const invalid=nextLength>2_000_000||nextLength===0;
 const canApply=!disabled&&!!count&&replacement!==find&&!invalid;
 function apply(){if(!canApply)return;const next=text.split(find).join(replacement);setLast({before:text,after:next});onChange(next);setNotice(`已替换 ${count} 处，尚未保存。请核对后保存转写修订。`);}
 function undo(){if(disabled||!last||text!==last.after)return;onChange(last.before);setLast(null);setNotice('已撤销这次替换，尚未保存。');}
 return <details className="transcript-replace"><summary>批量替换文字</summary><p>按输入文字原样匹配，区分大小写。只修改当前草稿，核对后再保存。</p>
  <div className="transcript-replace-fields"><label>查找<input aria-label="查找要替换的文字" value={find} maxLength={2000} disabled={disabled} onChange={e=>{setFind(e.target.value);setNotice('');}}/></label><label>替换为<input aria-label="替换成的文字" value={replacement} maxLength={2000} disabled={disabled} onChange={e=>{setReplacement(e.target.value);setNotice('');}}/></label></div>
  <div className="transcript-replace-actions"><span role="status">{find?`当前草稿有 ${count} 处匹配`:'输入需要统一修正的文字'}</span><button type="button" disabled={!canApply} onClick={apply}>替换 {count} 处</button>{last&&<button type="button" disabled={disabled||text!==last.after} onClick={undo}>撤销这次替换</button>}</div>
  {invalid&&count>0&&<p role="alert">{nextLength===0?'不能将整份转写替换为空白。':'替换后文字过长，请缩短替换文字。'}</p>}{notice&&<p role="status">{notice}</p>}
 </details>;
}
