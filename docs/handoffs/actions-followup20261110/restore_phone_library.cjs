const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),cp=require('node:child_process');
const {chromium}=require('C:/Users/Billy/Desktop/Denzic/Companion/companion-device-closure055/node_modules/@playwright/test');
const root='E:/CodexData/Companion/.build-cache/actions-followup20261110/phone116';
(async()=>{const session=JSON.parse(fs.readFileSync(path.join(root,'cdp.json'))),browser=await chromium.connectOverCDP('http://127.0.0.1:'+session.cdpPort);try{
 const targets=await(await fetch('http://127.0.0.1:'+session.cdpPort+'/json/list')).json();const attached=targets.filter(t=>JSON.parse(t.description).attached);assert.equal(attached.length,1);let page;
 for(const p of browser.contexts()[0].pages()){const c=await browser.contexts()[0].newCDPSession(p);const info=await c.send('Target.getTargetInfo');await c.detach();if(info.targetInfo.targetId===attached[0].id)page=p;}assert(page);page.setDefaultTimeout(12000);
 page.on('dialog',d=>{assert.equal(d.message(),'打开这份保留的资料？当前资料也会保留，不会删除录音或连接录音卡。');const p=cp.spawnSync('C:/Users/Billy/AppData/Local/Programs/Python/Python311/python.exe',[path.join(__dirname,'phone_native116.py'),'click','id:android:id/button1'],{encoding:'utf8',windowsHide:true});assert.equal(p.status,0,p.stderr);});
 await page.getByRole('navigation',{name:'主导航'}).getByRole('button',{name:'录音',exact:true}).click();await page.getByRole('region',{name:'当前资料位置',exact:true}).waitFor();
 const restore=page.getByRole('button',{name:'返回原有资料',exact:true});if(await restore.count())await restore.click();await page.getByRole('region',{name:'当前资料位置',exact:true}).getByText('原有资料',{exact:true}).waitFor();
 const output=path.join(__dirname,'android116/ui-result.json'),r=JSON.parse(fs.readFileSync(output));r.originalLibraryRestored=true;r.restoredAfterRetainedFailure=true;r.restoredAt=new Date().toISOString();fs.writeFileSync(output,JSON.stringify(r,null,2)+'\n');console.log(JSON.stringify({originalLibraryRestored:true,failedFeatureAcceptanceRetained:true,mainDisplayOperated:false}));
}finally{await browser.close()}})().catch(e=>{console.error(String(e));process.exitCode=1;});
