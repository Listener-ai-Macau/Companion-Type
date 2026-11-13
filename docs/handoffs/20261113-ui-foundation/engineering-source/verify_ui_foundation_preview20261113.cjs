const { chromium, expect } = require('C:/Users/Billy/Desktop/Denzic/Companion/companion-device-closure055/node_modules/@playwright/test');
const fs = require('fs');
const http = require('http');
const path = require('path');
const out = 'E:/CodexData/Companion/.build-cache/product-closure20261112/ui-foundation20261113';
const failures = [];
const report = {startedAt:new Date().toISOString(),scope:'Interactive design preview only; no installed application or hardware qualification',checks:[],pageErrors:[],consoleErrors:[]};
async function main(){
 const server=http.createServer((req,res)=>{res.setHeader('Content-Type','text/html; charset=utf-8');res.end(fs.readFileSync(path.join(out,'preview.html')));});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({channel:'msedge',headless:true,args:['--mute-audio']});
 try{
  const page=await browser.newPage({viewport:{width:1056,height:1000},colorScheme:'light'});
  page.on('pageerror',e=>report.pageErrors.push(e.message));
  page.on('console',msg=>{if(msg.type()==='error')report.consoleErrors.push(msg.text().slice(0,300));});
  await page.goto(`http://127.0.0.1:${server.address().port}`,{waitUntil:'domcontentloaded'});
  const frame=page.frameLocator('iframe');
  await expect(frame.locator('.cn-record')).toHaveCount(6);
  await expect(frame.locator('.viz-carousel-controls')).toHaveCount(1);
  await expect(frame.locator('.cn-logo svg').first()).toBeVisible({timeout:20000});
  report.hostCarouselInitialized=true;report.hostIconsRendered=true;
  for (const name of ['随身笔记','录音工作台']){
   if(name==='录音工作台')await frame.getByRole('button',{name:'下一个方向',exact:true}).click();
   const app=frame.locator(`[data-variant="${name}"] .cn-app`);
   const color=await app.locator('[data-action=export]').evaluate(el=>{const style=getComputedStyle(el);return {foreground:style.color,background:style.backgroundColor};});
   if(color.foreground===color.background)throw new Error('Export button text has no contrast');
   await app.locator('[data-pane=minutes]').focus();
   await page.keyboard.press('ArrowRight');
   await expect(app.locator('[data-pane=transcript]')).toHaveAttribute('aria-selected','true');
   await expect(app.locator('.cn-document-body')).toHaveAttribute('aria-labelledby',await app.locator('[data-pane=transcript]').getAttribute('id'));
   await app.locator('[data-pane=transcript]').click();
   await expect(app.locator('.cn-document-body')).toContainText('设备预算还没决定');
   await app.locator('[data-pane=minutes]').click();
   await app.locator('[data-action=export]').click();
   await expect(app.locator('.cn-export textarea')).toHaveValue(/周五演示安排/);
   await app.locator('[data-action=close-export]').click();
   await app.getByRole('searchbox').fill('散步');
   await expect(app.locator('.cn-record:visible')).toHaveCount(1);
   await app.locator('[data-record=public-idea]').click();
   await expect(app.locator('h1')).toHaveText('散步时的想法 · 文字示例');
   await expect(app.locator('.cn-player')).toBeHidden();
   await app.getByRole('searchbox').fill('');
   await app.locator('[data-record=public-voice]').click();
   await app.locator('[data-folder=favorite]').click();
   await expect(app.locator('.cn-record:visible')).toHaveCount(1);
   await app.locator('[data-folder=all]').click();
   await app.locator('[data-action=settings]').click();
   await app.getByLabel('界面主题',{exact:true}).selectOption('dark');
   await app.locator('[data-return]').click();
   await app.evaluate(el=>el.style.colorScheme='');
   report.checks.push({variant:name,interaction:'search, selection, transcript/minutes, export preview, favorite filter, theme',passed:true});
   for(const theme of ['light','dark']){
    await page.emulateMedia({colorScheme:theme});
    for(const width of [1056,768,422,352]){
     await page.setViewportSize({width,height:1100});
     if(width<680){
      await app.evaluate(el=>el.dataset.view='library');
      await app.locator('[data-record=public-voice]').click();
     }
     const layout=await app.evaluate(el=>{
      const box=el.getBoundingClientRect();
      const over=[...el.querySelectorAll('*')].filter(n=>{const r=n.getBoundingClientRect();const s=getComputedStyle(n);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&(r.right>box.right+1||r.left<box.left-1);}).map(n=>({tag:n.tagName,cls:typeof n.className==='string'?n.className:'svg',text:n.textContent.slice(0,80)}));
      return {width:Math.round(box.width),scrollWidth:el.scrollWidth,clientWidth:el.clientWidth,over};
     });
     if(layout.over.length||layout.scrollWidth>layout.clientWidth+1)failures.push({name,theme,width,layout});
     report.checks.push({variant:name,theme,viewport:width,layout,passed:!layout.over.length&&layout.scrollWidth<=layout.clientWidth+1});
     if((width===1056&&theme==='light')||(width===422&&theme==='light')||(width===1056&&theme==='dark'))await page.screenshot({path:path.join(out,`${name==='随身笔记'?'notebook':'workbench'}-${width}-${theme}.png`),fullPage:true});
     if(width<680){await app.locator('[data-action=back]').click();await expect(app.locator('.cn-library')).toBeVisible();await expect(app.locator('[data-action=device]')).toBeVisible();await expect(app.locator('[data-action=settings]')).toBeVisible();if(width===422&&theme==='light')await page.screenshot({path:path.join(out,`${name==='随身笔记'?'notebook':'workbench'}-422-library-light.png`),fullPage:true});}
    }
   }
   await page.setViewportSize({width:1056,height:1000});
   await page.emulateMedia({colorScheme:'light'});
  }
  const audio=frame.locator('audio');
  await audio.evaluate(el=>el.load());
  await expect.poll(()=>audio.evaluate(el=>Number.isFinite(el.duration)?el.duration:0)).toBeCloseTo(23.2245,2);
  report.actualEmbeddedAudioDuration=await audio.evaluate(el=>el.duration);
  const app=frame.locator('[data-variant="录音工作台"] .cn-app');
  await app.locator('[data-action=play]').click();
  await expect.poll(()=>audio.evaluate(el=>el.currentTime)).toBeGreaterThan(0);
  await app.locator('[data-action=play]').click();
  report.publicAudioPlaybackAdvancedMutedHeadless=true;
  report.failures=failures;
  report.passed=failures.length===0&&report.pageErrors.length===0;
 }catch(e){report.passed=false;report.fatal=e.stack;}
 finally{await browser.close();await new Promise(resolve=>server.close(resolve));fs.writeFileSync(path.join(out,'preview-qa.json'),JSON.stringify(report,null,2));}
 console.log(JSON.stringify({passed:report.passed,fatal:report.fatal,checks:report.checks.length,failures:report.failures,pageErrors:report.pageErrors,consoleErrors:report.consoleErrors},null,2));
 if(!report.passed)process.exitCode=1;
}
main().catch(e=>{console.error(e);process.exitCode=1;});
