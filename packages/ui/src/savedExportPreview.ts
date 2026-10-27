/** Waiting may be stopped only for the read-only native preview. A late
 * response must never open a file dialog or start an export after cancellation. */
export class SavedPreviewInterrupted extends Error {}
export function savedExportPreview<T>(read:()=>Promise<T>,timeoutMs=10000):{result:Promise<T>;cancel:()=>void}{
  let cancel=()=>{};
  const result=new Promise<T>((resolve,reject)=>{
    let settled=false;
    const finish=(deliver:()=>void)=>{if(settled)return;settled=true;clearTimeout(timer);deliver();};
    const timer=setTimeout(()=>finish(()=>reject(new SavedPreviewInterrupted('核对等待已结束，尚未开始保存或复制。已保存内容仍在，可重试或先查看清单。'))),timeoutMs);
    cancel=()=>finish(()=>reject(new SavedPreviewInterrupted('已停止等待，尚未开始保存或复制。已保存内容保留。')));
    try{read().then(value=>finish(()=>resolve(value)),error=>finish(()=>reject(error)));}
    catch(error){finish(()=>reject(error));}
  });
  return{result,cancel:()=>cancel()};
}
