const fs=require('fs'),assert=require('assert/strict');
const root='C:/Users/Billy/Desktop/Denzic/Companion',base=root+'/docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows060-system-handoff';
const meta=JSON.parse(fs.readFileSync(base+'/session.json','utf8'));
const {chromium}=require(root+'/recovered-software050/node_modules/playwright-core');
let browser;
(async()=>{
 browser=await chromium.connectOverCDP('http://127.0.0.1:'+meta.port,{timeout:12000});
 const pages=browser.contexts().flatMap(c=>c.pages()).filter(p=>/localhost/.test(p.url()));assert.equal(pages.length,1);
 const page=pages[0];page.setDefaultTimeout(12000);const action=process.argv[2]||'inspect',arg=process.argv[3];
 const panel=page.locator('.ct-content-export');
 if(action==='setup'){
  await page.getByRole('button',{name:'我的记录',exact:true}).click();
  await page.locator('.ct-library-card').filter({hasText:'公开虚构Windows内容验收 · 非真实会议'}).click();
  if(!await panel.evaluate(n=>n.open))await panel.locator(':scope > summary').click();
  await panel.getByLabel('整理结果',{exact:true}).uncheck();await panel.getByLabel('录音文字',{exact:true}).check();
 }else if(action==='format')await panel.getByLabel('所选内容文件格式',{exact:true}).selectOption(arg);
 else if(action==='preview')await panel.getByRole('button',{name:'预览所选内容',exact:true}).click();
 else if(action==='save'){
  const button=panel.getByRole('button').filter({hasText:/^保存/});assert.equal(await button.count(),1);await button.click();
 }else if(action==='share')await panel.getByRole('button',{name:'分享所选文件…',exact:true}).click();
 else if(action!=='inspect')throw Error('Unsupported action');
 await page.waitForTimeout(250);
 const info={action,buttons:await panel.getByRole('button').allTextContents(),selectedFormat:await panel.getByLabel('所选内容文件格式',{exact:true}).inputValue(),status:await page.locator('[role=status],[role=alert]').allTextContents(),preview:await panel.getByLabel('所选内容预览',{exact:true}).allTextContents()};
 fs.writeFileSync(meta.isolation+'/web-'+Date.now()+'-'+action+'.json',JSON.stringify(info,null,2));console.log(JSON.stringify(info));
})().catch(e=>{console.error(e.stack||String(e));process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();});
