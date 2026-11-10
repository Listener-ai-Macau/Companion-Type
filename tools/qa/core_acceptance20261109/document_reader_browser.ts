import {build} from 'vite';
import {chromium} from '@playwright/test';
import {createServer} from 'node:http';
import {readFileSync,writeFileSync,existsSync} from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {documentEngineAssets} from '../../../packages/document-context/viteAssets';
const source=process.cwd(),fixtures=path.resolve(process.argv[2]),out=path.resolve(process.argv[3]),receipt=path.resolve(process.argv[4]);
const manifest=JSON.parse(readFileSync(path.join(fixtures,'manifest.json'),'utf8'));
await build({configFile:false,logLevel:'warn',root:path.join(source,'tools/qa/core_acceptance20261109'),plugins:[documentEngineAssets(path.join(source,'packages/document-context/ThirdPartyNotices.txt'))],build:{target:'chrome64',outDir:out,emptyOutDir:true,rollupOptions:{input:path.join(source,'tools/qa/core_acceptance20261109/document_reader_harness.html')}}});
const serverRequests:Array<{name:string;status:number}>=[];
const server=createServer((request,response)=>{
 const name=decodeURIComponent(new URL(request.url!,'http://localhost').pathname),fixture=name.startsWith('/fixtures/')?name.slice(10):null;
 let file:string|undefined;
 if(fixture&&Object.hasOwn(manifest,fixture))file=path.join(fixtures,fixture);
 else if(!fixture){const resolved=path.resolve(out,'.'+name);if(resolved.startsWith(out+path.sep))file=resolved;}
 if(!file||!existsSync(file)){serverRequests.push({name,status:404});response.statusCode=404;response.end();return;}serverRequests.push({name,status:200});
 const ext=path.extname(file);response.setHeader('Content-Type',ext==='.mjs'||ext==='.js'?'text/javascript':ext==='.html'?'text/html':'application/octet-stream');response.end(readFileSync(file));
});
await new Promise<void>(resolve=>server.listen(0,'127.0.0.1',resolve));const address=server.address() as {port:number},origin='http://127.0.0.1:'+address.port;
let browser;const requests:string[]=[],results:Record<string,unknown>={};
try{
 browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});const context=await browser.newContext({serviceWorkers:'block'});const page=await context.newPage();
 await context.route('**/*',route=>{const url=route.request().url();if(url.startsWith(origin+'/')||url.startsWith('blob:')){requests.push(new URL(url).pathname);return route.continue();}return route.abort();});
 page.on('pageerror',error=>console.error('browser',error.message));
 await page.goto(origin+'/document_reader_harness.html');await page.waitForFunction(()=>typeof(window as any).readDocument==='function');
 const read=async(name:string,password?:string,cancel=false)=>{const value=await page.evaluate(async({name,sha,password,cancel})=>(window as any).readDocument(name,sha,password,cancel),{name,sha:manifest[name].sha256,password,cancel});writeFileSync(receipt+'.last.json',JSON.stringify({name,ok:value.ok,code:value.code,message:value.message,localResources:requests.filter(x=>/document-engine/.test(x))},null,2));return value;};
 for(const name of ['material.docx','material.xlsx','material.pptx','material.txt','material.pdf']){
  const value=await read(name);assert(value.ok,name+': '+JSON.stringify(value));assert(value.result.sections.length);results[name]={characters:value.result.characters,sections:value.result.sections.length,warnings:value.result.warnings};
  if(name==='material.pdf'){assert.equal(value.result.sections.length,2);assert(value.result.sections[0].text.includes('12000, Alex, Tuesday'));}
 }
 const password=await read('protected.pdf');assert.equal(password.code,'password-required');results.passwordRequired=password;
 const wrong=await read('protected.pdf','wrong');assert.equal(wrong.code,'wrong-password');results.wrongPassword=wrong;
 const opened=await read('protected.pdf','local-password');assert(opened.ok);results.passwordOpened={sections:opened.result.sections.length};
 const restricted=await read('restricted.pdf','local-password');assert.equal(restricted.code,'unsupported-format');results.restricted=restricted;
 const chinese=await read('chinese.pdf');assert(chinese.ok,JSON.stringify(chinese));assert(chinese.result.sections[0].text.includes('公开补充材料：预算12000元，周二核对，不是录音转写。'));results.chinesePdf={text:chinese.result.sections[0].text};
 const noText=await read('no-text.pdf');assert.equal(noText.code,'no-text');results.noText=noText;
 const cancelled=await read('material.docx',undefined,true);assert.equal(cancelled.code,'cancelled');results.cancelled=cancelled;
 const afterCancel=await read('material.pdf');assert(afterCancel.ok);results.afterCancel={sections:afterCancel.result.sections.length};
 assert(!serverRequests.some(r=>r.name.startsWith('/document-engine/')&&r.status!==200),'Reader requested a missing local engine resource');
 writeFileSync(receipt,JSON.stringify({at:new Date().toISOString(),state:'SHARED_DOCUMENT_READER_PRODUCTION_WORKER_OFFLINE_FIXTURES_PASS',appDelivered:false,externalRequestsAllowed:false,workerResources:requests.filter(x=>/worker|document-engine/.test(x)),serverRequests,results},null,2)+'\n');
 console.log('PASS production Chrome64-target build, real disposable workers, local-only PDF engine, Office fixtures, passwords, cancel and subsequent successful read.');
}finally{await browser?.close();await new Promise<void>(resolve=>server.close(()=>resolve()));}
