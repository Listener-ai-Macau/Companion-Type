const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../../..'),{build}=require(root+'/node_modules/esbuild'),{chromium}=require(root+'/node_modules/@playwright/test');
const out=process.argv[2];assert(out);fs.mkdirSync(out,{recursive:false});let server,browser,page;const result={state:'CHECKING_REAL_READER_LAYOUT',modelsRun:false,nativeQualified:false,checks:[]};
(async()=>{try{
 await build({entryPoints:[__dirname+'/meeting_workspace_harness.tsx'],outfile:out+'/workspace.js',bundle:true,platform:'browser',format:'iife',jsx:'automatic',tsconfig:root+'/apps/windows/tsconfig.json'});
 server=http.createServer((req,res)=>{const name=path.basename(new URL(req.url,'http://localhost').pathname);if(['workspace.js','workspace.css'].includes(name)){res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':'text/css');res.end(fs.readFileSync(out+'/'+name));return;}res.setHeader('Content-Type','text/html;charset=utf-8');res.end('<!doctype html><html lang="zh-CN"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/workspace.css"><div id="app"></div><script src="/workspace.js"></script></html>');});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+server.address().port;
 browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});page=await browser.newPage({viewport:{width:1360,height:900},locale:'zh-CN'});const errors=[];page.on('pageerror',e=>errors.push(String(e)));await page.route('**/*',r=>r.request().url().startsWith(origin)?r.continue():r.abort());
 for(const [label,query]of [['multiple','?notebook-library=1'],['actual-public019f','?actual-public-019f=1'],['empty','?empty-library=1']]){
  await page.goto(origin+query);await page.locator('.ct-shell').waitFor();if(label!=='empty')await page.locator('#ct-saved-recording-workspace:not([hidden])').waitFor();else await page.getByRole('heading',{name:'把声音留在这里',exact:true}).waitFor();
  await page.locator('#fixture-failure').evaluate(el=>el.remove());
  for(const theme of ['light','dark']){
   await page.locator('.ct-shell').evaluate((el,t)=>el.classList.toggle('ct-theme-dark',t==='dark'),theme);
   for(const width of [1360,1056,760,390,320]){
    await page.setViewportSize({width,height:900});await page.evaluate(()=>scrollTo(0,0));assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No horizontal overflow '+label+'/'+theme+'/'+width);
    if(width>900&&label!=='empty'){
     const card=await page.locator('.ct-library-card').first().boundingBox();assert(card.width>=200,'Row must fill library rather than inherit former grid columns');
     const primary=page.locator('.ct-reader-export');assert(await primary.isVisible());assert((await primary.boundingBox()).y<180);
     if(label==='actual-public019f'){
      const content=page.locator('.ct-minutes-item').first();assert((await content.boundingBox()).y<650,'Actual public result must begin within first screen');
      assert(await page.locator('#ct-meeting-result-pane').innerText().then(text=>text.includes('超市')));assert.equal(await page.locator('.meeting-outline-card').count(),0);
     }
    }
    if(width===1360||width===390)await page.screenshot({path:out+'/'+label+'-'+theme+'-'+width+'.png'});
    result.checks.push({label,theme,width,passed:true});
   }
   await page.setViewportSize({width:1360,height:900});
  }
 }
 for(const state of ['connecting','reconnecting','pairing','connected','stale','storage','failed']){
  await page.goto(origin+'?connection='+state);await page.getByRole('button',{name:/^录音卡 ·/}).click();await page.locator('#ct-device-recording-page').waitFor();assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:out+'/device-'+state+'.png'});
 }
 assert.deepEqual(errors,[]);result.state='READER_SOURCE_EMPTY_MULTIPLE_REAL_PUBLIC_AND_DEVICE_LAYOUTS_CHECKED';result.pageErrors=errors;
}catch(e){result.error=String(e);if(page){await page.screenshot({path:out+'/failure.png',fullPage:true});fs.writeFileSync(out+'/failure-body.txt',await page.locator('body').innerText());}throw e;}
finally{if(browser)await browser.close();if(server)await new Promise(r=>server.close(r));fs.writeFileSync(out+'/result.json',JSON.stringify(result,null,2));}})().catch(e=>{console.error(e);process.exitCode=1});
