const fs=require('node:fs');
const {chromium}=require('E:/CodexData/Companion/product-d1d2-20261114/app-source/node_modules/@playwright/test');
const root='E:/CodexData/Companion/product-d1d2-20261114/app-candidate-r5/qa/hidden-delivery-r1';
(async()=>{
  const browser=await chromium.connectOverCDP('http://127.0.0.1:19338');
  try{
    const page=browser.contexts().flatMap(c=>c.pages()).find(p=>p.url()==='http://tauri.localhost/');
    if(!page)throw Error('Owned native embedded app not found');
    const errors=[];page.on('pageerror',e=>errors.push(String(e)));
    const initial=await page.locator('body').innerText();
    if(!initial.includes('ES2003b.Array1-01')||!initial.includes('草稿')||!initial.includes('部分原音没有识别出文字'))throw Error('Real saved source/review state is not visible');
    await page.screenshot({path:root+'/native-english-minutes.png'});
    await page.getByRole('button',{name:'文字',exact:true}).click();
    await page.waitForTimeout(300);
    const transcript=await page.locator('body').innerText();
    fs.writeFileSync(root+'/native-transcript-visible.txt',transcript);
    await page.screenshot({path:root+'/native-english-transcript.png'});
    await page.getByRole('button',{name:'设置',exact:true}).click();
    await page.waitForTimeout(300);
    const provider=await page.locator('select').evaluateAll(nodes=>nodes.map(n=>({value:n.value,options:[...n.options].map(o=>({value:o.value,label:o.text}))}))).then(rows=>rows.find(r=>r.options.some(o=>o.value==='local-meeting')));
    if(!provider||provider.value!=='local-meeting')throw Error('Installed local bilingual provider is not selected in the real UI');
    if(errors.length)throw Error(errors.join('\n'));
    fs.writeFileSync(root+'/native-ui-result.json',JSON.stringify({state:'PASS_REAL_HIDDEN_NATIVE_UI_READING_TRANSCRIPT_REVIEW_AND_LOCAL_BILINGUAL_SETTINGS',
      origin:page.url(),realSavedMeeting:'ES2003b.Array1-01',sourceReviewVisible:true,minutesDraftVisible:true,provider,
      nativeBackend:true,fixtureBackend:false,newInference:false,newRecording:false,playback:false,
      desktopFocusChanged:false,qualityQualified:false,pageErrors:errors},null,2)+'\n');
    console.log('PASS_REAL_HIDDEN_NATIVE_UI_READING_TRANSCRIPT_REVIEW_AND_LOCAL_BILINGUAL_SETTINGS');
  }finally{await browser.close();}
})().catch(e=>{fs.writeFileSync(root+'/native-ui-failure.json',JSON.stringify({state:'FAILED_HIDDEN_UI_RETAINED',error:String(e)},null,2));console.error(String(e));process.exitCode=1;});
