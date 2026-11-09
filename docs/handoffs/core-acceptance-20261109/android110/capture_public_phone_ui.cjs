const fs=require('node:fs'),path=require('node:path');
const {chromium}=require('C:/Users/Billy/Desktop/Denzic/Companion/companion-device-closure055/node_modules/@playwright/test');
const root='E:/CodexData/Companion/.build-cache/core-acceptance20261109/android110-phone-d6';
(async()=>{
 const info=JSON.parse(fs.readFileSync(path.join(root,'cdp.json'),'utf8'));
 const browser=await chromium.connectOverCDP('http://127.0.0.1:'+info.cdpPort);
 try{
  const targets=await (await fetch('http://127.0.0.1:'+info.cdpPort+'/json/list')).json();
  const attached=targets.filter(t=>JSON.parse(t.description).attached);if(attached.length!==1)throw Error('One attached own WebView required');
  let page;
  for(const candidate of browser.contexts()[0].pages()){
   const channel=await browser.contexts()[0].newCDPSession(candidate);const target=await channel.send('Target.getTargetInfo');await channel.detach();if(target.targetInfo.targetId===attached[0].id)page=candidate;
  }
  if(!page)throw Error('Attached page required');page.on('dialog',()=>{});
  if(!(await page.locator('.detail-title h1').innerText()).includes('S_R004S03C01'))throw Error('Public test meeting required');
  await page.locator('.detail-title').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(root,'public-meeting-ui-113.png'),fullPage:false});
  process.stdout.write(JSON.stringify({saved:true,ordinaryPhoneWebView:true,physicalDisplayCaptured:false}));
 }finally{await browser.close();}
})().catch(e=>{process.stderr.write(String(e));process.exitCode=1;});
