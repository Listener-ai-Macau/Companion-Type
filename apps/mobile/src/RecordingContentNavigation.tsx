import {useRef} from 'react';
export type RecordingContentView='minutes'|'transcript'|'notes'|'mindmap'|'translation';
const mainViews=[{id:'minutes',label:'纪要'},{id:'transcript',label:'文字'},{id:'notes',label:'补充'}] as const;

/** Stable reading choices, with occasional transforms kept in a separate disclosure. */
export function RecordingContentNavigation({value,onChange,preview=false}:{value:RecordingContentView;onChange:(view:RecordingContentView)=>void;preview?:boolean}){
 const menu=useRef<HTMLDetailsElement>(null);
 const tabs=mainViews.filter(tab=>!preview||tab.id!=='notes');
 return <nav className="recording-content-navigation" aria-label="录音内容导航">
  <div className="detail-tabs" role="tablist" aria-label="录音内容" onKeyDown={event=>{
   const index=tabs.findIndex(tab=>tab.id===value);let next=index;
   if(event.key==='ArrowRight')next=(index+1)%tabs.length;
   else if(event.key==='ArrowLeft')next=(index+tabs.length-1)%tabs.length;
   else if(event.key==='Home')next=0;else if(event.key==='End')next=tabs.length-1;else return;
   event.preventDefault();onChange(tabs[next].id);event.currentTarget.querySelectorAll<HTMLButtonElement>('[role=tab]')[next]?.focus();
  }}>{tabs.map(tab=><button key={tab.id} type="button" id={'detail-tab-'+tab.id} role="tab" aria-controls={'detail-panel-'+tab.id} aria-selected={value===tab.id} tabIndex={value===tab.id?0:-1} onClick={()=>onChange(tab.id)}>{tab.label}</button>)}</div>
  <details ref={menu} className="recording-content-more"><summary>{value==='mindmap'?'思维导图':value==='translation'?'翻译':'更多'}</summary>
   <div><button type="button" id="detail-tab-mindmap" aria-controls="detail-panel-mindmap" aria-pressed={value==='mindmap'} onClick={()=>{onChange('mindmap');if(menu.current)menu.current.open=false;}}>思维导图</button>
   {!preview&&<button type="button" id="detail-tab-translation" aria-controls="detail-panel-translation" aria-pressed={value==='translation'} onClick={()=>{onChange('translation');if(menu.current)menu.current.open=false;}}>翻译</button>}</div>
  </details>
 </nav>;
}
