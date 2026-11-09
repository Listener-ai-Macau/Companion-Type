const fs=require('node:fs'),path=require('node:path');
const {chromium}=require('C:/Users/Billy/Desktop/Denzic/Companion/companion-device-closure055/node_modules/@playwright/test');
const root='E:/CodexData/Companion/.build-cache/core-acceptance20261109/android110-phone-d6',control=path.join(root,'web-control');fs.mkdirSync(control,{recursive:true});
const save=(p,v)=>{fs.writeFileSync(p+'.tmp',JSON.stringify(v,null,2));fs.renameSync(p+'.tmp',p);};const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{const session=JSON.parse(fs.readFileSync(path.join(root,'cdp.json'),'utf8'));const browser=await chromium.connectOverCDP('http://127.0.0.1:'+session.cdpPort);try{
 const page=browser.contexts()[0].pages()[0];
 // A listener prevents Playwright's automatic dismissal. Confirmation remains
 // a real Android dialog, clicked through the scoped native input driver.
 page.on('dialog',dialog=>save(path.join(control,'pending-dialog.json'),{type:dialog.type(),message:dialog.message(),nativeInputRequired:true}));
 save(path.join(control,'ready.json'),{ready:true,url:page.url(),displayId:session.displayId});const handled=new Set();let stop=false;
 while(!stop){for(const name of fs.readdirSync(control).filter(n=>/^request-\d+\.json$/.test(n)&&!handled.has(n))){const request=JSON.parse(fs.readFileSync(path.join(control,name),'utf8'));let result;try{
  const base=request.scope?page.locator(request.scope):page;const locator=request.label?base.getByLabel(request.label,{exact:true}):request.role?base.getByRole(request.role,{name:request.name,exact:true}):request.selector?base.locator(request.selector):base;
  if(request.action==='click'){await locator.click({timeout:15000});result={clicked:true};}
  else if(request.action==='select'){await locator.selectOption(request.value);result={selected:true};}
  else if(request.action==='fill'){await locator.fill(request.value);result={filled:true};}
  else if(request.action==='press'){await locator.press(request.key);result={pressed:true};}
  else if(request.action==='inspect'){result={headings:await page.locator('.title-row h1').allTextContents(),status:await page.getByRole('status').allTextContents(),alerts:await page.getByRole('alert').allTextContents(),rowCount:await page.locator('.list .row').count()};if(request.public){if(!(await page.locator('body').innerText()).includes('S_R004S03C01'))throw Error('Public meeting marker required');result.text=await locator.innerText();}}
  else if(request.action==='stop'){stop=true;result={stopped:true};}
  else throw Error('Unsupported ordinary UI action');
 }catch(error){result={error:String(error)};}save(path.join(control,name.replace('request-','reply-')),result);handled.add(name);}await sleep(100);}
 }finally{await browser.close();}})().catch(error=>{save(path.join(control,'failure.json'),{error:String(error),stack:error.stack});process.exitCode=1;});
