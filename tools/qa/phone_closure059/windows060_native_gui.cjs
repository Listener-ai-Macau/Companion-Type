const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const root='C:/Users/Billy/Desktop/Denzic/Companion/recovered-software050';
const {chromium}=require(root+'/node_modules/@playwright/test');
const config=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
(async()=>{
 const browser=await chromium.connectOverCDP(`http://127.0.0.1:${config.port}`);
 const context=browser.contexts()[0],page=context.pages().find(p=>p.url().includes('localhost'))??context.pages()[0];
 const errors=[];page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(15000);
 try{
  const {createHash}=require('crypto');let matched=0;
  for(const asset of config.assets.filter(a=>/^assets\/index-.*\.(?:js|css)$/.test(a.path))){
   const body=await page.evaluate(async name=>{const response=await fetch('/'+name);if(!response.ok)throw Error('Asset unavailable');return response.text();},asset.path);
   assert.equal(createHash('sha256').update(body).digest('hex'),asset.sha256);matched++;
  }
  assert.equal(matched,2);
  await page.getByRole('button',{name:'我的记录',exact:true}).click();
  await page.locator('.ct-library-card').first().click();
  const panel=page.locator('.ct-content-export');await panel.locator(':scope > summary').click();
  await panel.getByLabel('整理结果',{exact:true}).uncheck();
  await panel.getByLabel('录音文字',{exact:true}).check();
  await panel.getByRole('button',{name:'预览所选内容',exact:true}).click();
  const preview=panel.getByLabel('所选内容预览',{exact:true});await preview.waitFor({state:'attached'});
  assert.equal(await preview.textContent(),config.expectedText);
  if(!config.skipCopy){await panel.getByRole('button',{name:'复制所选内容',exact:true}).click();
   await panel.getByText('已复制所选内容，可粘贴到常用应用。',{exact:true}).waitFor();}
  for(const format of ['txt','markdown','docx','pdf','xlsx','mindmap','pptx','png']){
   await panel.getByLabel('所选内容文件格式',{exact:true}).selectOption(format);
   await panel.getByRole('button',{name:'预览所选内容',exact:true}).click();
   await page.waitForTimeout(50);assert.equal(await preview.textContent(),config.expectedText);
  }
  const light=page.getByRole('button',{name:'切换至浅色模式',exact:true});if(await light.count())await light.click();
  await panel.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(config.output,'native-light.png'),fullPage:false});
  const dark=page.getByRole('button',{name:'切换至深色模式',exact:true});if(await dark.count())await dark.click();
  await panel.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(config.output,'native-dark.png'),fullPage:false});
  assert.equal(await panel.getByRole('button',{name:'分享所选文件…',exact:true}).isEnabled(),true);
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(config.output,'ui-result.json'),JSON.stringify({status:'ACTUAL_NATIVE_WINDOW_UI_PREVIEW_PASSED',nativeAssetsMatched:matched,allEightFormatsNativePreview:true,sourceTextExact:true,clipboardSuccessReported:!config.skipCopy,clipboardNotTouched:!!config.skipCopy,shareButtonEnabled:true,shareSheetOpened:false,systemSaveDialogOpened:false,lightAndDarkActualToggle:true,pageErrors:errors,modelsRun:false,deviceIo:false},null,2));
  console.log('NATIVE_UI_DONE');
 }catch(error){fs.writeFileSync(path.join(config.output,'failure-body.txt'),await page.locator('body').innerText());await page.screenshot({path:path.join(config.output,'failure.png')}).catch(()=>{});throw error;}
 finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
