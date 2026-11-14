import React,{useState} from 'react';
import {createRoot} from 'react-dom/client';
import {MeetingAiWorkbench,type AiMaterial,type AiSave} from 'ROOT/packages/ui/src/MeetingAiWorkbench';
import {MinutesTemplatePreview} from 'ROOT/packages/ui/src/MinutesTemplatePreview';
import {materialNote,readMaterialNote} from 'ROOT/packages/ui/src/aiMaterialNote';
PLATFORM_IMPORT
THEME_IMPORTS

const audit=(window as any).__audit={calls:[],exports:[],dirty:false,confirmations:[],failSave:false};
const sourceText='公开虚构界面资料：周四核对演示材料，负责人尚未确认。';
function App(){
 const [context,setContext]=useState('one'),[view,setView]=useState('result'),[theme,setTheme]=useState('light'),[dirty,setDirty]=useState(false);
 const [materials,setMaterials]=useState<Record<string,AiMaterial[]>>({one:[],two:[]});
 audit.dirty=dirty;audit.context=context;audit.materials=materials;
 const scopes=[{id:context,title:'当前演示会议',binding:context+':r1'},...Array.from({length:12},(_,i)=>({id:'other-'+i,title:'演示会议 '+(i+1),binding:'fixed:'+i})),{id:'document:'+context+':agenda',title:'人工补充 · 演示议程',binding:'agenda:r1',kind:'supplement' as const}];
 return <div className={PLATFORM_CLASS} data-theme={theme}>
  <div className="fixture-controls"><span>工程界面检查 · 虚构服务回包</span><button onClick={()=>setTheme(theme==='light'?'dark':'light')}>切换测试主题</button><button onClick={()=>{if(dirty&&!window.confirm('放弃未保存材料？'))return;setContext(context==='one'?'two':'one');}}>切换演示会议</button></div>
  <main style={{maxWidth:850,margin:'0 auto',padding:20}}>
   PLATFORM_NAV
   <div hidden={view!=='materials'}><MeetingAiWorkbench key={context} contextId={context} contextVersion="r1" title="公开虚构演示会议" scopes={scopes} serviceReady onUnsavedChange={setDirty}
    onAsk={async(question,ids,jobId)=>{audit.calls.push({question,ids,jobId});return {items:[{text:sourceText,citation:{sessionId:context,title:'公开虚构演示会议',quote:sourceText}}],totalChunks:1,completedChunks:1,incomplete:false,cancelled:false};}}
    onSetup={()=>{throw Error('Unexpected setup');}} onOpenSource={(id,quote)=>audit.source={id,quote}}
    onLoadSaved={async()=>materials[context]||[]}
    onSave={async(value:AiSave)=>{if(audit.failSave){audit.failSave=false;throw Error('演示保存失败，输入保留');}const saved=IS_WINDOWS?readMaterialNote({id:value.id,text:materialNote(value),createdAt:'1'})!:{...value,createdAt:1,sources:scopes.filter(s=>value.sessionIds.includes(s.id))};setMaterials(old=>({...old,[context]:[saved,...(old[context]||[]).filter(m=>m.id!==saved.id)]}));return saved;}}
    onExportSaved={id=>{if(!materials[context]?.some(m=>m.id===id))throw Error('Export must identify a confirmed current saved material');audit.exports.push({context,id});}}
   /></div>
   <MinutesTemplatePreview template={{id:'interview'}}/>
  </main>
 </div>;
}
createRoot(document.getElementById('root')!).render(<App/>);
