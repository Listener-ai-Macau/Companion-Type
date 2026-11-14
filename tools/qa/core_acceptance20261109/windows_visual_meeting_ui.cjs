const assert=require('node:assert/strict'),path=require('path');
module.exports=async(page,spec,out)=>{
 const frame=page.locator('#ct-meeting-result-pane .meeting-reading-frame').first();
 await frame.waitFor();const expected=spec.expectedVisualTopics;
 assert(Array.isArray(expected)&&expected.length>1);
 const nav=page.getByRole('navigation',{name:'主要功能',exact:true});
 assert.equal(await nav.getByRole('button',{name:'全部录音',exact:true}).count(),1);
 assert.equal(await nav.getByRole('button',{name:'我的录音卡',exact:true}).count(),1);
 const labels=await nav.locator('button>span').evaluateAll(nodes=>nodes.map(e=>({text:e.textContent,right:e.getBoundingClientRect().right,parentRight:e.closest('button').getBoundingClientRect().right,whiteSpace:getComputedStyle(e).whiteSpace})));
 assert(labels.every(x=>x.whiteSpace==='nowrap'&&x.right<=x.parentRight-4));
 const light=page.getByRole('button',{name:'切换至浅色模式',exact:true});if(await light.count())await light.click();
 for(const theme of ['light','dark']){
  if(theme==='dark')await page.getByRole('button',{name:'切换至深色模式',exact:true}).click();
  if(spec.expectClearReading)await require('./meeting_clarity_ui.cjs')(page,frame,out,theme);
  await frame.getByRole('button',{name:'思维导图',exact:true}).click();
  const topics=frame.locator('.meeting-map-branches>li');assert.equal(await topics.count(),expected.length);
  const mapLayout=await frame.locator('.meeting-map-canvas').evaluate(e=>({width:e.closest('.meeting-reading-frame').getBoundingClientRect().width,columns:getComputedStyle(e).gridTemplateColumns.trim().split(/\s+/).length}));
  if(mapLayout.width<=640)assert.equal(mapLayout.columns,1);
  await frame.getByRole('button',{name:'展开全部',exact:true}).click();
  await page.waitForFunction(n=>document.querySelectorAll('.meeting-map-branches details[open]').length===n,expected.length);
  assert.deepEqual(await topics.locator('.meeting-map-topic-content>p').allTextContents(),expected);
  await frame.getByRole('button',{name:'收起',exact:true}).click();
  await page.evaluate(()=>window.scrollTo(0,0));
  await page.screenshot({animations:'disabled',path:path.join(out,'actual-visual-map-'+theme+'.png')});
  const palette=await page.locator('.ct-shell').evaluate(e=>({paper:getComputedStyle(e).getPropertyValue('--notebook-paper').trim(),accent:getComputedStyle(e).getPropertyValue('--notebook-accent').trim(),width:document.body.scrollWidth,viewport:innerWidth}));
  assert.equal(palette.paper,theme==='light'?'#ffffff':'#1c1f26');assert.equal(palette.accent,theme==='light'?'#345edb':'#9cb8ff');assert(palette.width<=palette.viewport);
  await topics.last().locator('summary').click();
  await topics.last().getByRole('button',{name:'查看纪要上下文',exact:true}).click();
  await page.waitForFunction(text=>document.activeElement?.getAttribute('data-meeting-topic')===text,expected.at(-1));
  await frame.getByRole('button',{name:'按发言人',exact:true}).click();
  assert((await frame.locator('.meeting-speakers').innerText()).includes('还没有区分发言人'));
  assert.equal(await frame.locator('.meeting-speaker-card').count(),0);
  await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({animations:'disabled',path:path.join(out,'actual-speakers-unavailable-'+theme+'.png')});
  await frame.getByRole('button',{name:'阅读纪要',exact:true}).click();
 }
 await page.getByRole('button',{name:'切换至浅色模式',exact:true}).click();await page.evaluate(()=>window.scrollTo(0,0));
 return {actualPublicTopicCount:expected.length,allTopicWordsExact:true,mapExpandAndCollapse:true,lastTopicContextAndFocus:true,noInventedParticipants:true,neutralLightAndDarkPalettes:true,ownerAppearanceAccepted:false};
};
