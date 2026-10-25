import {useEffect,useRef,useState} from 'react';
import {DeleteConfirmation} from '../../../packages/ui/src/DeleteConfirmation';

export type CloseRequest={owner:number;token:number};
export type CloseClient={
  listen:(receive:(review:CloseRequest)=>void)=>Promise<()=>void>;
  register:()=>Promise<{owner:number;pending:CloseRequest|null}>;
  unregister:(owner:number)=>Promise<void>;
  respond:(review:CloseRequest,discard:boolean)=>Promise<boolean>;
};
const valid=(r:CloseRequest)=>Number.isSafeInteger(r?.owner)&&r.owner>0&&r.owner<=0xffffffff
  &&Number.isSafeInteger(r?.token)&&r.token>0&&r.token<=0xffffffff;
function ClosingIndicator(){
  const element=useRef<HTMLDialogElement>(null);
  useEffect(()=>{const e=element.current;e?.showModal();return()=>e?.close();},[]);
  return <dialog ref={element} className="ct-delete-confirm" aria-label="正在确认退出" onCancel={e=>e.preventDefault()}>
    <strong>正在确认退出</strong><p role="status">等待当前操作安全收尾。若窗口标题提示尚未结束，可以稍后再次关闭窗口重试。</p>
    <p>已保存的录音会保留；这里不会重新录音或开始处理。</p>
  </dialog>;
}
/** Native Close asks this mounted owner to inspect current UI-only drafts.
 * The native token is transient; no draft contents or secrets are sent. */
export function CloseReview({unsaved,client}:{unsaved:boolean;client:CloseClient}){
  const dirty=useRef(unsaved);dirty.current=unsaved;
  const current=useRef<CloseRequest|null>(null),generation=useRef(0),answering=useRef(false);
  const [pending,setPending]=useState<CloseRequest|null>(null),[closing,setClosing]=useState(false),[error,setError]=useState<string|null>(null);
  const answer=useRef<(review:CloseRequest,discard:boolean)=>Promise<void>>(async()=>{});
  useEffect(()=>{
    const epoch=++generation.current;let disposed=false,owner=0,release:(()=>void)|undefined,queued:CloseRequest|null=null;
    const alive=()=>!disposed&&epoch===generation.current;
    const detach=()=>{const callback=release;release=undefined;callback?.();};
    const same=(r:CloseRequest)=>alive()&&current.current?.owner===r.owner&&current.current?.token===r.token;
    answer.current=async(review,discard)=>{
      if(!same(review)||answering.current)return;
      if(!discard){
        // Let the user continue editing even if the keep acknowledgement fails.
        current.current=null;setPending(null);setError(null);
        try{await client.respond(review,false);}catch{if(alive())setError('保留窗口的回执尚未确认，当前编辑仍在；需要退出时请再次关闭窗口。');}
        return;
      }
      answering.current=true;setClosing(true);setError(null);
      try{
        const accepted=await client.respond(review,true);
        if(same(review)&&!accepted){setClosing(false);setPending(review);setError('关闭请求已更新，窗口仍保留；请继续编辑，或再次关闭窗口。');}
      }catch{
        if(same(review)){setClosing(false);setPending(review);setError('尚未确认退出，未保存的编辑仍在当前窗口。可以继续编辑，或重新确认退出。');}
      }finally{if(alive())answering.current=false;}
    };
    const receive=(review:CloseRequest)=>{
      if(!alive()||!valid(review))return;
      if(!owner){queued=review;return;}
      if(review.owner!==owner)return;
      if(current.current?.token===review.token&&current.current.owner===owner)return;
      current.current=review;setError(null);
      // Give an edit from this UI turn its normal React commit before deciding.
      window.requestAnimationFrame(()=>{
        if(!same(review))return;
        if(dirty.current)setPending(review);else void answer.current(review,true);
      });
    };
    void(async()=>{
      try{
        release=await client.listen(receive);
        if(!alive()){detach();return;}
        const registered=await client.register();
        if(!Number.isSafeInteger(registered.owner)||registered.owner<=0||registered.owner>0xffffffff)throw Error();
        owner=registered.owner;
        if(!alive()){void client.unregister(owner).catch(()=>{});detach();return;}
        if(registered.pending)receive(registered.pending);
        if(queued)receive(queued);
      }catch{if(alive())setError('退出保护尚未就绪；关闭窗口时会再确认未保存的编辑。');}
    })();
    return()=>{
      disposed=true;generation.current++;current.current=null;answering.current=false;detach();
      if(owner)void client.unregister(owner).catch(()=>{});
    };
  },[client]);
  return <>
    {closing?<ClosingIndicator/>:pending?<DeleteConfirmation title={unsaved?'还有未保存的修改':'关闭尚未确认'} detail={error??(unsaved?'标题、清单、备注、宠物档案或设置中仍有未保存或未确认的修改。继续编辑可以保留它们；退出会丢弃本机尚未保存的编辑，不会撤回已提交的写入。已保存的内容会保留。':'修改已保存或还原。可以继续使用，或关闭窗口。')} blocked={false}
      cancelLabel="继续编辑" confirmLabel={unsaved?'放弃修改并退出':'退出'} onCancel={()=>void answer.current(pending,false)} onConfirm={()=>void answer.current(pending,true)}/>:null}
    {error&&!pending&&!closing?<p className="ct-step-warn" role="status">{error}</p>:null}
  </>;
}
