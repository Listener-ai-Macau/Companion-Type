const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const root='C:/Users/Billy/Desktop/Denzic/Companion/companion-core-android20261109';
const {chromium}=require(root+'/node_modules/@playwright/test');
const out='E:/CodexData/Companion/.build-cache/product-closure20261112/mobile143-source-r5';fs.mkdirSync(out,{recursive:false});
const dist=path.join(root,'apps/mobile/dist');let browser,server,page;const result={state:'CHECKING_MOBILE_RECORDING_LIBRARY',nativeQualified:false,modelsRun:false,hardwareQualified:false};
(async()=>{try{
 server=http.createServer((req,res)=>{const file=path.resolve(dist,'.'+new URL(req.url,'http://localhost').pathname);if(!file.startsWith(dist+path.sep)||!fs.existsSync(file)){res.writeHead(404);res.end();return;}res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html; charset=utf-8');res.end(fs.readFileSync(file));});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin='http://127.0.0.1:'+server.address().port;
 browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});page=await browser.newPage({viewport:{width:393,height:852},locale:'zh-CN'});const errors=[];result.pageErrors=errors;page.on('pageerror',error=>errors.push(String(error)));
 const retained=fs.readFileSync(root+'/tools/mobile-bridge-smoke.cjs','utf8');
 const begin=retained.indexOf('await page.addInitScript(()=>{'),end=retained.indexOf('\n  await page.goto',begin);assert(begin>=0&&end>begin);
 const fixture=retained.slice(begin,end).replaceAll("state:'COMPLETE',segments:1","state:'COMPLETE',segments:1,recordedAtUnixSeconds:1794474000,durationMs:23000");
 await new Function('page','return (async()=>{'+fixture+'})();')(page);
 await page.addInitScript(()=>{
  const original=window.CompanionNative.call.bind(window.CompanionNative);window.fixtureMethods=[];
  const currentContracts={incomingFiles:{rows:[]},audioImportStatus:{running:false,state:'idle'},libraryStatus:{version:1,activeId:'original',token:'public-source-fixture',libraries:[{id:'original',restoredAt:0}]},appPreferences:{defaultPlaybackSpeed:1,resumePlayback:true,systemDark:false,bluetoothAllowed:true,notificationsAllowed:true,version:'0.1.143'},aiServiceStatus:{configured:false,saved:false}};
  window.CompanionNative.call=(id,method,args)=>{window.fixtureMethods.push(method);if(Object.hasOwn(currentContracts,method))queueMicrotask(()=>window.companionReply({id,result:currentContracts[method],error:null}));else original(id,method,args);};
 });
 await page.route('**/*',route=>route.request().url().startsWith(origin)?route.continue():route.abort());
 await page.goto(origin+'/index.html');await page.locator('.row').first().waitFor();
 assert(await page.getByRole('heading',{name:'我的记录',exact:true}).isVisible());
 assert.equal(await page.locator('.library-filter-details').evaluate(node=>node.open),false);
 assert.equal(await page.getByRole('group',{name:'录音查找范围',exact:true}).isVisible(),false);
 assert((await page.locator('.row').first().innerText()).includes('2026/11/12'));
 for(const width of [360,393,430]){await page.setViewportSize({width,height:852});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
 await page.setViewportSize({width:393,height:852});await page.screenshot({path:out+'/library-light.png',fullPage:true});
 await page.getByRole('button',{name:'切换深色模式',exact:true}).click();await page.screenshot({path:out+'/library-dark.png',fullPage:true});
 await page.locator('.row').filter({hasText:'未转写示例'}).click();await page.waitForTimeout(250);result.fixtureMethods=await page.evaluate(()=>window.fixtureMethods);assert.deepEqual(errors,[]);await page.locator('.mobile-detail-heading').getByText('未转写示例',{exact:true}).waitFor();
 assert(await page.getByRole('button',{name:'本地转写',exact:true}).isVisible());
 await page.screenshot({path:out+'/no-text-detail.png',fullPage:true});
 assert.deepEqual(errors,[]);result.state='MOBILE_SOURCE_LIBRARY_NAMES_DATES_THEME_WIDTH_AND_OPEN_PASSED';result.covered=['Actual143 source-built web assets with synthetic native bridge','Generated recording name uses real supplied date','Library light and dark at360/393/430','Open an untranscribed recording without forcing an empty minutes page'];
}catch(error){result.error=String(error);if(page){await page.screenshot({path:out+'/failure.png',fullPage:true});fs.writeFileSync(out+'/failure-body.txt',await page.locator('body').innerText());}throw error;}
finally{if(browser)await browser.close();if(server)await new Promise(resolve=>server.close(resolve));fs.writeFileSync(out+'/result.json',JSON.stringify(result,null,2));}})().catch(error=>{console.error(error);process.exitCode=1});
