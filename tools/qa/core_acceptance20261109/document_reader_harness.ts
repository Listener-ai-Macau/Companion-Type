import {extractInWorker} from '../../../packages/document-context/src/workerClient';
const harness=window as typeof window&{readDocument:unknown;progress:string[]};
harness.progress=[];
harness.readDocument=async(name:string,sha:string,password?:string,cancel=false)=>{
 const bytes=await(await fetch('/fixtures/'+encodeURIComponent(name))).arrayBuffer(),controller=new AbortController();
 try{
  const promise=extractInWorker(bytes,name,sha,{password,signal:controller.signal,onProgress:message=>harness.progress.push(message)});
  if(cancel)controller.abort();
  return {ok:true,result:await promise};
 }catch(error){return {ok:false,code:(error as {code?:string}).code,message:(error as Error).message};}
};
