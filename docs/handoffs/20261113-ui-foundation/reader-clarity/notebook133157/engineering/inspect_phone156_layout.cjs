const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const C='C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261110-android-media-import',Q='E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113/whole-delivery133156';
const{connect}=require(C+'/organization_ui.cjs');
(async()=>{const{page,browser,session}=await connect();try{
 assert.equal(session.displayId,54);
 await page.getByRole('tab',{name:'纪要',exact:true}).click();await page.locator('main').evaluate(e=>e.scrollTop=0);
 const selectors=['.detail-title','.detail-title h1','.detail-meta','.player-card','.player-control','.player-copy','.recording-content-navigation','.minutes-origin','.minutes-section>h3','.minutes-section p'];
 const measure=()=>page.evaluate(selectors=>Object.fromEntries(selectors.map(s=>{const e=document.querySelector(s),c=getComputedStyle(e),b=e.getBoundingClientRect();return[s,{top:b.top,height:b.height,width:b.width,padding:c.padding,margin:c.margin,display:c.display,flexDirection:c.flexDirection,flex:c.flex,font:c.font}];})),selectors);
 const before=await measure(),final=process.argv[2]==='final',prefix=final?'phone157':'phone';
 const css=final?fs.readFileSync('C:/Users/Billy/Desktop/Denzic/Companion/companion-core-android20261109/apps/mobile/src/notebookMobile.css','utf8'):'.mobile-app .detail-title{padding:0}.mobile-app .detail-title h1{margin:0}.mobile-app .player-card-idle{flex-wrap:nowrap}.mobile-app .player-card-idle .player-control{width:auto}.mobile-app .player-card-idle .player-copy{flex:initial;flex-direction:row}';
 await page.addStyleTag({content:css});await page.locator('main').evaluate(e=>e.scrollTop=0);const after=await measure();
 const screenshot=path.join(Q,prefix+'-layout-candidate.png');await page.screenshot({path:screenshot});
 fs.writeFileSync(path.join(Q,prefix+'-layout-discriminator.json'),JSON.stringify({scope:'Transient CSS experiment on own declared-public display54, not new native build/install',before,after,css,screenshot,nativeChanges:false,modelsRun:false},null,2));console.log(JSON.stringify({beforeFirst:before['.minutes-section p'].top,afterFirst:after['.minutes-section p'].top}));
 assert.equal(after['.player-copy'].flexDirection,'row');
 if(final){assert.equal(after['.detail-title'].padding,'0px');assert(after['.player-card'].height<=60);assert(after['.detail-title h1'].font.includes('21px'));}
 else assert(after['.minutes-section p'].top<before['.minutes-section p'].top-30);
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
