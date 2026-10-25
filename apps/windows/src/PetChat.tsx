import {useEffect,useRef,useState} from 'react';
import {invoke} from '@tauri-apps/api/core';
import {PetProfile} from './PetProfile';

type ChatStatus={requestId:number;phase:string;transcript:string;reply:string;error?:string|null;
  screenVisible:boolean;canStart:boolean;wakeSupported:boolean;recordPhrase:string;chatPhrase:string};
const labels:Record<string,string>={idle:'点一下，和宠物聊一句',preparing:'正在准备',listening:'对着宠物说吧',
  transcribing:'正在听懂这句话',thinking:'想一想',replyReady:'回复已准备好',displaying:'正在送到屏幕',
  replied:'已显示在宠物屏幕',displayFailed:'回复保留，暂未上屏',failed:'这次没聊成',cancelled:'已取消'};
function raster(text:string):number[]{
  const canvas=document.createElement('canvas');canvas.width=200;canvas.height=13;
  const ctx=canvas.getContext('2d');if(!ctx)throw new Error('字幕绘制暂时不可用。');
  ctx.fillStyle='white';ctx.fillRect(0,0,200,13);
  ctx.font='12px "Microsoft YaHei", sans-serif';ctx.textAlign='left';ctx.textBaseline='alphabetic';
  const measure=ctx.measureText(text);
  const width=measure.actualBoundingBoxLeft+measure.actualBoundingBoxRight;
  const height=measure.actualBoundingBoxAscent+measure.actualBoundingBoxDescent;
  if(Math.max(width,measure.width)>176||height>13)throw new Error('这句回复超过一行，已保留原句。');
  ctx.fillStyle='black';ctx.fillText(text,(200-width)/2+measure.actualBoundingBoxLeft,
    (13-height)/2+measure.actualBoundingBoxAscent);
  const pixels=ctx.getImageData(0,0,200,13).data;const result=new Array<number>(325).fill(255);
  for(let y=0;y<13;y++)for(let x=12;x<188;x++){
    const i=(y*200+x)*4;
    if((pixels[i]+pixels[i+1]+pixels[i+2])/3<160)result[y*25+(x>>3)]&=~(128>>(x&7));
  }
  return result;
}
export function PetChat({disabled,deviceUid}:{disabled:boolean;deviceUid?:string|null}){
  const [state,setState]=useState<ChatStatus|null>(null),[error,setError]=useState<string|null>(null);
  const [busy,setBusy]=useState(false);
  const action=useRef(false),sent=useRef(0),cancelling=useRef(false),cancelledRequest=useRef(0);
  const active=!!state&&['preparing','listening','transcribing','thinking','replyReady','displaying'].includes(state.phase);
  useEffect(()=>{
    let stopped=false;let timer:ReturnType<typeof setTimeout>|undefined;
    const poll=async()=>{
      try{const next=await invoke<ChatStatus>('get_companion_pet_chat');
        if(!stopped&&(!cancelledRequest.current||next.requestId!==cancelledRequest.current||next.phase==='cancelled'||next.phase==='failed'))setState(next);}
      catch{ /* Preserve the last reply; a host status read does not open BLE. */ }
      if(!stopped)timer=setTimeout(poll,active?500:2500);
    };void poll();return()=>{stopped=true;if(timer)clearTimeout(timer);};
  },[active]);
  const display=async(current:ChatStatus)=>{
    if(action.current)return;action.current=true;setBusy(true);setError(null);
    try{const next=await invoke<ChatStatus>('display_companion_pet_chat',{requestId:current.requestId,pixels:raster(current.reply)});
      if(cancelledRequest.current!==current.requestId)setState(next);}
    catch(e){if(cancelledRequest.current!==current.requestId)setError(String(e));}
    finally{action.current=false;setBusy(false);}
  };
  useEffect(()=>{
    if(!busy&&state?.phase==='replyReady'&&sent.current!==state.requestId&&cancelledRequest.current!==state.requestId){
      sent.current=state.requestId;void display(state);
    }
  },[state,busy]);
  const control=async(command:string,args?:Record<string,unknown>)=>{
    if(action.current)return;action.current=true;setBusy(true);setError(null);
    try{setState(await invoke<ChatStatus>(command,args));}catch(e){setError(String(e));}finally{action.current=false;setBusy(false);}
  };
  const cancel=async(current:ChatStatus)=>{
    // Cancellation must not queue behind a seven-second native display wait.
    if(cancelling.current)return;cancelling.current=true;cancelledRequest.current=current.requestId;setError(null);
    try{setState(await invoke<ChatStatus>('finish_companion_pet_chat',{requestId:current.requestId,cancel:true}));}
    catch(e){cancelledRequest.current=0;setError(String(e));}finally{cancelling.current=false;}
  };
  return <section aria-label="宠物聊天" style={{maxWidth:920,margin:'12px auto',padding:'16px 20px',border:'1px solid #d8ded8',borderRadius:12}}>
    <h2 style={{fontSize:16,margin:'0 0 8px'}}>和宠物聊聊</h2>
    <p style={{margin:'4px 0 10px'}} aria-live="polite">{state?.phase==='cancelled'&&!state.canStart?'正在结束这句聊天':labels[state?.phase??'idle']??'宠物聊天'}</p>
    <p style={{fontSize:12,opacity:.7}}>第一版连接电脑使用；每句最长12秒，可提前说完。只用宠物麦克风，短回复显示在屏幕底部。</p>
    {!state?.wakeSupported?<p style={{fontSize:12,opacity:.7}}>语音唤醒尚未接入。预留“开始录音”录音、“聊聊天”聊天；目前轻点开聊。</p>:null}
    {state?.transcript?<p>你：{state.transcript}</p>:null}
    {state?.reply?<p>宠物：{state.reply}</p>:null}
    {error||state?.error?<p role="alert">{error??state?.error}</p>:null}
    <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
      <button disabled={disabled||busy||active||(!!state&&!state.canStart)||state?.phase==='displayFailed'} onClick={()=>void control('start_companion_pet_chat')}>开聊</button>
      {state?.phase==='listening'?<button disabled={busy} onClick={()=>void control('finish_companion_pet_chat',{requestId:state.requestId,cancel:false})}>说完了</button>:null}
      {state?.phase==='displayFailed'||(state?.phase==='replyReady'&&error)?<button disabled={disabled||busy} onClick={()=>void display(state!)}>重试上屏</button>:null}
      {active||state?.phase==='displayFailed'?<button onClick={()=>void cancel(state!)}>取消</button>:null}
      {!active&&state?.phase!=='displayFailed'?<button disabled={busy||(!!state&&!state.canStart)} onClick={()=>void control('clear_companion_pet_chat')}>清空本次对话</button>:null}
    </div>
    <PetProfile disabled={disabled||busy||active||!!state&&!state.canStart} deviceUid={deviceUid} transcript={state?.transcript}/>
  </section>;
}
