/// <reference lib="webworker" />
import {extractDocument} from './extract';
import {DocumentReadError,type DocumentReadOptions} from './types';
type Input={original:ArrayBuffer;filename:string;sha256:string;options:Pick<DocumentReadOptions,'password'|'encoding'|'engineBaseUrl'>};
// One disposable worker per document. Termination also interrupts synchronous
// Office parsing; a caller never waits for an untrusted parser to yield.
self.onmessage=async(event:MessageEvent<Input>)=>{
 const {original,filename,sha256,options}=event.data;
 try{const result=await extractDocument(original,filename,sha256,{...options,onProgress:message=>self.postMessage({type:'progress',message})});self.postMessage({type:'result',result});}
 catch(error){self.postMessage({type:'error',code:error instanceof DocumentReadError?error.code:'invalid-file',message:error instanceof DocumentReadError?error.message:'文字提取没有完成，原件仍保留；可重新读取或另存文件后重试。'});}
};
