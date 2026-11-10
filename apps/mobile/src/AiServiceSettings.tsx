import {useEffect,useState} from 'react';
import {ArrowLeft,Check,ChevronDown,KeyRound,ShieldCheck} from 'lucide-react';
export type AiServiceStatus={configured:boolean;saved:boolean;verified?:boolean;endpoint?:string;model?:string;error?:string};
export function AiServiceSettings({status,busy,onSave,onClear,onReturn,onDirtyChange,returnLabel='返回会议'}:{status:AiServiceStatus;busy:boolean;onSave:(value:{endpoint:string;model:string;apiKey:string;remember:boolean})=>Promise<void>;onClear:()=>Promise<void>;onReturn:()=>void;onDirtyChange?:(dirty:boolean)=>void;returnLabel?:string}){
 const [endpoint,setEndpoint]=useState(status.endpoint||'https://api.deepseek.com/chat/completions'),[model,setModel]=useState(status.model||'deepseek-chat'),[secret,setSecret]=useState(''),[remember,setRemember]=useState(status.configured?status.saved:true),[dirty,setDirty]=useState(false);
 useEffect(()=>{onDirtyChange?.(dirty);},[dirty,onDirtyChange]);
 useEffect(()=>()=>onDirtyChange?.(false),[onDirtyChange]);
 return <section className="service-card ai-service-settings" aria-label="AI服务设置"><div className="service-card-heading"><div><span className="service-kicker">AI 服务</span><strong>配置一次，回到会议直接使用</strong></div><ShieldCheck size={20}/></div>
  <p className="service-intro">纪要、问答和翻译共用这里的服务。当前使用你自备的第三方服务密钥，费用以服务商为准。</p>
  <p className="ai-service-state" role="status">{status.configured?<><Check size={14}/>{status.saved?'已在这台手机安全保存':'本次运行已配置'} · {status.verified?'上次文字请求成功':'首次生成时验证连接'}</>:'尚未配置 AI 服务'}</p>{status.error&&<p role="alert">{status.error}</p>}
  <label>服务密钥<input aria-label="AI服务密钥" type="password" autoComplete="off" placeholder={status.configured?'已保存；留空继续使用':'填写你的服务密钥'} value={secret} disabled={busy} onChange={e=>{setSecret(e.target.value);setDirty(true);}}/></label>
  <details className="advanced-service"><summary><span className="advanced-title">服务地址与模型</span><span className="advanced-meta">高级设置 <ChevronDown size={15}/></span></summary><label>服务地址<input aria-label="AI服务地址" type="url" value={endpoint} disabled={busy} onChange={e=>{setEndpoint(e.target.value);setDirty(true);}}/></label><label>模型<input aria-label="AI服务模型" value={model} disabled={busy} onChange={e=>{setModel(e.target.value);setDirty(true);}}/></label></details>
  <label className="service-remember"><input type="checkbox" checked={remember} disabled={busy} onChange={e=>{setRemember(e.target.checked);setDirty(true);}}/>在这台手机安全保存，下次直接使用</label><p className="hint">密钥由手机系统保护，不放入录音备份；取消保存则只在本次运行中使用。生成时会把所选会议文字发给该服务。</p>
  <div className="buttons"><button type="button" className="primary" disabled={busy||(!secret&&!status.configured)||!endpoint.trim()||!model.trim()||(status.configured&&!dirty)} onClick={()=>void onSave({endpoint,model,apiKey:secret,remember}).then(()=>{setSecret('');setDirty(false);}).catch(()=>{})}><KeyRound size={15}/>{busy?'正在保存…':'保存服务配置'}</button><button type="button" className="secondary" disabled={busy} onClick={onReturn}><ArrowLeft size={15}/>{returnLabel}</button></div>
  {(status.configured||status.saved)&&<button type="button" className="text-button" disabled={busy} onClick={()=>{if(window.confirm('清除这台手机保存的AI服务配置？录音、转写和已生成内容会保留。'))void onClear().catch(()=>{});}}>清除本机服务配置</button>}
 </section>;
}
