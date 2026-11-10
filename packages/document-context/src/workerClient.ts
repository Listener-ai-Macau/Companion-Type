import {DOCUMENT_LIMITS,DocumentReadError,type DocumentExtraction,type DocumentFailureCode,type DocumentReadOptions} from './types';
/** Caller supplies a disposable copy of the durable original; transfer frees it. */
export function extractInWorker(original:ArrayBuffer,filename:string,sha256:string,options:DocumentReadOptions={}):Promise<DocumentExtraction>{
 return new Promise((resolve,reject)=>{
  if(options.signal?.aborted){reject(new DocumentReadError('cancelled','已停止提取文字，已保存的原件仍保留。'));return;}
  if(!original.byteLength||original.byteLength>DOCUMENT_LIMITS.fileBytes){reject(new DocumentReadError('capacity','请选择20MB以内的非空文档。'));return;}
  let worker:Worker;
  try{worker=new Worker(new URL('./reader.worker.ts',import.meta.url));}catch{reject(new DocumentReadError('environment','当前系统组件暂不能读取文档，请更新应用或系统WebView，原件仍保留。'));return;}
  let done=false;
  const finish=(error?:DocumentReadError,result?:DocumentExtraction)=>{
   if(done)return;done=true;clearTimeout(timer);options.signal?.removeEventListener('abort',abort);worker.terminate();
   if(error)reject(error);else resolve(result!);
  };
  const abort=()=>finish(new DocumentReadError('cancelled','已停止提取文字，已保存的原件仍保留。'));
  const timer=setTimeout(()=>finish(new DocumentReadError('capacity','文档读取时间过长，已停止本次提取；原件保留，可拆分或另存后重试。')),DOCUMENT_LIMITS.deadlineMs);
  options.signal?.addEventListener('abort',abort,{once:true});
  worker.onerror=event=>{event.preventDefault();finish(new DocumentReadError('environment','文档读取组件未能完成，原件仍保留；请更新应用或另存文件后重试。'));};
  worker.onmessage=event=>{
   const value=event.data;
   if(value?.type==='progress'&&typeof value.message==='string')options.onProgress?.(value.message);
   else if(value?.type==='error')finish(new DocumentReadError(value.code as DocumentFailureCode,String(value.message)));
   else if(value?.type==='result'){
    const result=value.result as DocumentExtraction;
    if(result?.schema!==1||result.sourceSha256!==sha256||!Array.isArray(result.sections)||result.sections.length>DOCUMENT_LIMITS.sections||!Number.isSafeInteger(result.characters)||result.characters>DOCUMENT_LIMITS.textCharacters){finish(new DocumentReadError('invalid-file','提取结果的来源无法确认，原件仍保留。'));return;}
    finish(undefined,result);
   }
  };
  if(options.signal?.aborted){abort();return;}
  worker.postMessage({original,filename,sha256,options:{password:options.password,encoding:options.encoding,engineBaseUrl:options.engineBaseUrl??new URL('document-engine/',document.baseURI).href}},[original]);
 });
}
