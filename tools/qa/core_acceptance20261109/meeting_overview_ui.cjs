const assert=require('node:assert/strict'),path=require('path'),fs=require('fs');
module.exports=async(page,frame,out,tag,expected,brief=false)=>{
 await frame.getByRole('button',{name:'会议一览',exact:true}).click();
 const overview=frame.locator('.meeting-overview');await overview.waitFor();
 const nodes=overview.locator('.meeting-overview-topics button');assert.equal(await nodes.count(),expected.length);
 if(brief){
  assert(!await overview.locator('.meeting-overview-detail').isVisible());
  assert((await overview.locator('.meeting-overview-outcomes').innerText()).includes('对销售不好的产品实行末尾淘汰制'));
  assert.equal(await overview.locator('.meeting-glance-qualifier').innerText(),'待核对');
  const actions=overview.locator('.meeting-glance-actions');assert((await actions.innerText()).includes('纪要未列出事项'));assert.equal(await actions.locator('li').count(),0);
  for(let i=0;i<expected.length;i++){await nodes.nth(i).focus();await page.keyboard.press('Enter');assert.equal(await nodes.nth(i).getAttribute('aria-expanded'),'true');assert.equal(await overview.locator('.meeting-overview-detail>p').innerText(),expected[i]);}
  await overview.getByRole('button',{name:'关闭主题原文',exact:true}).focus();await page.keyboard.press('Escape');assert(!await overview.locator('.meeting-overview-detail').isVisible());assert(await nodes.last().evaluate(e=>e===document.activeElement));
  await page.evaluate(()=>window.scrollTo(0,0));
  const geometry=await overview.evaluate(e=>({height:e.getBoundingClientRect().height,defaultText:e.innerText,characters:e.innerText.replace(/\s/g,'').length}));
  fs.writeFileSync(path.join(out,'actual-brief-glance-'+tag+'.json'),JSON.stringify({noDefaultLongParagraph:true,directSourceResults:true,...geometry},null,2));
  await page.screenshot({path:path.join(out,'actual-visual-overview-'+tag+'.png'),animations:'disabled'});
  const decisions=overview.locator('.meeting-overview-outcome').filter({hasText:'讨论结论'});await decisions.locator('summary').click();assert((await decisions.locator('li').innerText()).includes('增加促销后仍不见好转'));await decisions.locator('summary').click();
  await nodes.last().click();await overview.getByRole('button',{name:'纪要位置',exact:true}).click();assert(await frame.locator('.meeting-reading-content').isVisible());
  await frame.getByRole('button',{name:'返回会议一览',exact:true}).click();assert(!await frame.locator('.meeting-overview-detail').isVisible());await frame.getByRole('button',{name:'阅读完整纪要',exact:true}).click();
  return{brief:true,exactAllTopics:true,defaultLongTextHidden:true,directResults:true,conditionalSourceIntact:true,contextAndReturn:true,keyboardCloseAndFocus:true};
 }
 for(let i=0;i<expected.length;i++){await nodes.nth(i).focus();await page.keyboard.press('Enter');assert.equal(await nodes.nth(i).getAttribute('aria-pressed'),'true');assert.equal(await overview.locator('.meeting-overview-detail>p').innerText(),expected[i]);}
 await nodes.first().click();await frame.locator('.meeting-reading-start').scrollIntoViewIfNeeded();
 const visibleResults=await overview.locator('.meeting-overview-outcomes').boundingBox();assert(visibleResults&&visibleResults.y+visibleResults.height<=await page.evaluate(()=>innerHeight),'Results must be visible in the first reading viewport.');
 fs.writeFileSync(path.join(out,'actual-overview-first-viewport-'+tag+'.json'),JSON.stringify({results:visibleResults,viewportHeight:await page.evaluate(()=>innerHeight),resultsVisibleBeforeTopics:true},null,2));
 await page.screenshot({path:path.join(out,'actual-visual-overview-'+tag+'.png'),animations:'disabled'});
 const actions=overview.locator('.meeting-overview-outcome').filter({hasText:'行动事项'});assert((await actions.locator('summary').innerText()).includes('未列出'));await actions.locator('summary').click();assert.equal(await actions.locator('li').count(),0);await actions.locator('summary').click();
 const decisions=overview.locator('.meeting-overview-outcome').filter({hasText:'讨论结论'});await decisions.locator('summary').click();assert((await decisions.locator('li').innerText()).includes('增加促销后仍不见好转'));await decisions.locator('summary').click();
 await overview.getByRole('button',{name:'纪要位置',exact:true}).click();await frame.locator('.meeting-reading-back').waitFor();assert(await frame.locator('.meeting-reading-content').isVisible());
 await frame.getByRole('button',{name:'返回会议一览',exact:true}).click();assert(await overview.isVisible());await overview.getByRole('button',{name:'阅读完整纪要',exact:true}).click();assert(await frame.locator('.meeting-reading-content').isVisible());
 return{allTopicsExact:true,emptyActionHonest:true,conditionalDecisionIntact:true,ordinaryContextAndReturn:true,completeNoteReachable:true};
};
