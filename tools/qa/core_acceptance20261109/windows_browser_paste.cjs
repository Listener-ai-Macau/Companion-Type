// Real headed Edge receives the native Windows file clipboard via Ctrl+V.
// Only the disposable hosted runner may run this; never the owner's desktop.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {chromium}=require('@playwright/test');
assert.equal(process.env.GITHUB_ACTIONS,'true');assert.equal(process.platform,'win32');
const [root,out]=process.argv.slice(2),token=crypto.randomBytes(24).toString('hex');
const inbox=path.join(root,'browser-received-files');fs.mkdirSync(inbox);let context,server,active,stopping=false;
const save=(p,value)=>{fs.writeFileSync(p+'.tmp',JSON.stringify(value,null,2));fs.renameSync(p+'.tmp',p);};
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const html=`<!doctype html><meta charset="utf-8"><title>Public local attachment receiver</title><h1>Public local attachment receiver</h1><p>Paste a file into the composer. This page has no contacts or sending service.</p><textarea aria-label="Attachment composer" autofocus></textarea><ul id="files"></ul><p id="status">Ready</p><script>
document.querySelector('textarea').addEventListener('paste',async event=>{
 const files=Array.from(event.clipboardData.files);window.lastPaste={trusted:event.isTrusted,types:Array.from(event.clipboardData.types),files:files.map(file=>({name:file.name,size:file.size,type:file.type}))};
 if(!files.length)return;event.preventDefault();
 try{if(files.length!==1)throw Error('Expected one file');const body=new FormData();body.append('attachment',files[0]);body.append('trusted',String(event.isTrusted));body.append('types',JSON.stringify(window.lastPaste.types));const response=await fetch('/${token}/upload',{method:'POST',body});if(!response.ok)throw Error(await response.text());const result=await response.json();const item=document.createElement('li');item.textContent=result.fileName+' · '+result.bytes+' bytes';document.querySelector('#files').append(item);window.lastReceived=result;document.querySelector('#status').textContent='Attached '+result.fileName;}catch(error){window.pasteError=String(error);document.querySelector('#status').textContent=String(error);}
});</script>`;
(async()=>{
 server=http.createServer(async(req,res)=>{try{
  if(req.method==='GET'){
   if(req.url==='/'+token){res.writeHead(200,{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'});res.end(html);}else{res.statusCode=404;res.end();}return;
  }
  assert.equal(req.method,'POST');assert.equal(req.url,'/'+token+'/upload');assert.ok(active,'No pending attachment action');
  const chunks=[];let bytes=0;for await(const chunk of req){bytes+=chunk.length;assert.ok(bytes<100*1024**2);chunks.push(chunk);}
  const request=new Request('http://127.0.0.1/'+token+'/upload',{method:'POST',headers:req.headers,body:Buffer.concat(chunks)});
  const form=await request.formData(),file=form.get('attachment');assert.ok(file&&typeof file.arrayBuffer==='function');
  assert.equal(form.get('trusted'),'true');assert.equal(file.name,path.basename(file.name));assert.equal(file.name,active.fileName);
  const payload=Buffer.from(await file.arrayBuffer()),slot=path.join(inbox,active.id);fs.mkdirSync(slot);const destination=path.join(slot,file.name);fs.writeFileSync(destination,payload,{flag:'wx'});
  // Keep the actual small public attachment for diagnostic replay. Audio stays
  // only in the disposable runner; its independent byte hash is retained.
  if(payload.length<5*1024**2&&['.pdf','.txt','.docx'].includes(path.extname(file.name)))fs.writeFileSync(path.join(out,'received-'+active.id+path.extname(file.name)),payload,{flag:'wx'});
  const result={receiver:'Microsoft Edge native clipboard paste into a browser attachment composer',operation:'Trusted Ctrl+V paste -> browser File -> multipart FormData -> loopback-only receiver',fileName:file.name,bytes:payload.length,sha256:crypto.createHash('sha256').update(payload).digest('hex'),receivedPath:destination,clipboardTypes:JSON.parse(form.get('types')),trustedNativePaste:true,sourcePathOrBytesSuppliedToReceiver:false,actualFileReceived:true,thirdPartyMessengerOrSendQualified:false};
  active.result=result;res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify(result));
 }catch(error){res.statusCode=400;res.end(String(error));if(active)active.error=String(error);}});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const port=server.address().port;
 context=await chromium.launchPersistentContext(path.join(root,'edge-attachment-profile'),{channel:'msedge',headless:false,viewport:{width:1100,height:700},args:['--no-first-run','--mute-audio','--disable-gpu']});
 const page=context.pages()[0]||await context.newPage();await page.goto('http://127.0.0.1:'+port+'/'+token);await page.getByRole('textbox',{name:'Attachment composer'}).waitFor();
 save(path.join(out,'browser-receiver-ready.json'),{ready:true,browserVersion:context.browser()?.version(),receiverUrlOrigin:'http://127.0.0.1:'+port,profile:path.join(root,'edge-attachment-profile'),headless:false,externalNetworkDestinationUsed:false});
 const handled=new Set();while(!fs.existsSync(path.join(out,'browser-receiver-stop'))){
  for(const name of fs.readdirSync(out).filter(n=>/^browser-request-\d+\.json$/.test(n)&&!handled.has(n))){
   const input=JSON.parse(fs.readFileSync(path.join(out,name),'utf8'));assert.deepEqual(Object.keys(input).sort(),['fileName','id']);assert.match(input.id,/^attachment-\d+$/);
   active={...input};await page.evaluate(()=>{delete window.lastReceived;delete window.pasteError;delete window.lastPaste;});
   await page.bringToFront();await page.getByRole('textbox',{name:'Attachment composer'}).focus();await page.keyboard.press('Control+V');
   try{await page.waitForFunction(()=>window.lastReceived||window.pasteError,{},{timeout:30000});assert.ok(active.result&&!active.error,JSON.stringify(await page.evaluate(()=>({lastPaste:window.lastPaste,error:window.pasteError}))));
    save(path.join(out,name.replace('browser-request-','browser-reply-')),active.result);await page.screenshot({path:path.join(out,'browser-attachments-received.png')});
   }catch(error){save(path.join(out,name.replace('browser-request-','browser-reply-')),{error:String(error),observed:await page.evaluate(()=>({lastPaste:window.lastPaste,error:window.pasteError}))});throw error;}
   handled.add(name);active=null;
  }
  await wait(100);
 }
})().catch(error=>{save(path.join(out,'browser-receiver-failure.json'),{error:String(error),stack:error.stack});console.error(error);process.exitCode=1;}).finally(async()=>{stopping=true;if(context)await context.close();if(server)server.close();});
