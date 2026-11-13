const fs=require('fs'),path=require('path'),http=require('http');
const S='C:/Users/Billy/Desktop/Denzic/Companion/companion-device-closure055',O='E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113';
const Q=path.join(O,'visual-polish-audit');fs.mkdirSync(Q,{recursive:false});
const {chromium}=require(S+'/node_modules/@playwright/test');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu','--mute-audio']});let server;
 const result={at:new Date().toISOString(),scope:'Visual research and existing132 component audit only. No native build/install/model/device/Owner desktop use.',officialReference:'https://www.granola.ai/',errors:[]};
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  try{
   await page.goto(result.officialReference,{waitUntil:'domcontentloaded',timeout:30000});
   await page.getByText('Q3 GTM sync',{exact:true}).first().waitFor({timeout:15000});
   await page.screenshot({path:Q+'/granola-official-viewport.png'});
   result.reference=await page.getByText('Q3 GTM sync',{exact:true}).first().evaluate(e=>{const rows=[];for(let p=e,i=0;p&&i<6;p=p.parentElement,i++){const c=getComputedStyle(p),b=p.getBoundingClientRect();rows.push({tag:p.tagName,className:p.className,width:b.width,height:b.height,font:c.fontFamily,fontSize:c.fontSize,lineHeight:c.lineHeight,padding:c.padding,background:c.backgroundColor});}return rows;});
   const box=result.reference.find(r=>r.width>300&&r.width<900&&r.height>250&&r.height<1400);
   if(box){const index=result.reference.indexOf(box);let widget=page.getByText('Q3 GTM sync',{exact:true}).first();for(let i=0;i<index;i++)widget=widget.locator('..');await widget.screenshot({path:Q+'/granola-official-note.png'});}
  }catch(error){result.errors.push({phase:'officialReference',message:error.message});}
  const old=O+'/note-readability-component-preview-r4';server=http.createServer((req,res)=>{const name=new URL(req.url,'http://localhost').pathname;if(name==='/windows.js'||name==='/windows.css'){res.setHeader('Content-Type',name.endsWith('css')?'text/css':'text/javascript');res.end(fs.readFileSync(old+name));}else{res.setHeader('Content-Type','text/html;charset=utf-8');res.end('<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="/windows.css"></head><body style="margin:0"><div id="root"></div><script src="/windows.js"></script></body></html>');}});await new Promise(r=>server.listen(0,'127.0.0.1',r));
  await page.goto('http://127.0.0.1:'+server.address().port);await page.locator('.ct-library-card').first().click();await page.locator('.ct-note-overview-point').first().waitFor();
  result.current=await page.evaluate(()=>Object.fromEntries(['.ct-shell','.ct-meeting-hero','.ct-recording-primary-actions','.ct-meeting-navigation','.ct-result-reading-toolbar','.meeting-reading-sidebar','.ct-note-overview-heading','.ct-note-overview-point'].map(selector=>{const e=document.querySelector(selector);if(!e)return[selector,null];const c=getComputedStyle(e),b=e.getBoundingClientRect();return[selector,{top:b.top,bottom:b.bottom,height:b.height,width:b.width,font:c.fontFamily,fontSize:c.fontSize,lineHeight:c.lineHeight,fontWeight:c.fontWeight,margin:c.margin,padding:c.padding,color:c.color}];})));
  const cdp=await page.context().newCDPSession(page);await cdp.send('DOM.enable');await cdp.send('CSS.enable');const dom=await cdp.send('DOM.getDocument');const {nodeId}=await cdp.send('DOM.querySelector',{nodeId:dom.root.nodeId,selector:'.ct-note-overview-point'});result.platformFonts=await cdp.send('CSS.getPlatformFontsForNode',{nodeId});await cdp.detach();
  await page.screenshot({path:Q+'/current132-1440.png'});
 }finally{fs.writeFileSync(Q+'/result.json',JSON.stringify(result,null,2));await browser.close();if(server)await new Promise(r=>server.close(r));}
 console.log(JSON.stringify(result));
})().catch(e=>{console.error(e);process.exitCode=1;});
