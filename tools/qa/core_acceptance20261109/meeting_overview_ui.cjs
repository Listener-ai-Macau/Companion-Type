const assert=require('node:assert/strict'),path=require('path');
module.exports=async(page,frame,out,tag,expected)=>{
 await frame.getByRole('button',{name:'会议一览',exact:true}).click();
 const overview=frame.locator('.meeting-overview');await overview.waitFor();
 const nodes=overview.locator('.meeting-overview-topics button');assert.equal(await nodes.count(),expected.length);
 for(let i=0;i<expected.length;i++){await nodes.nth(i).focus();await page.keyboard.press('Enter');assert.equal(await nodes.nth(i).getAttribute('aria-pressed'),'true');assert.equal(await overview.locator('.meeting-overview-detail>p').innerText(),expected[i]);}
 await nodes.first().click();await frame.locator('.meeting-reading-start').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'actual-visual-overview-'+tag+'.png'),animations:'disabled'});
 const actions=overview.locator('.meeting-overview-outcome').filter({hasText:'行动事项'});assert((await actions.locator('summary').innerText()).includes('未列出'));await actions.locator('summary').click();assert.equal(await actions.locator('li').count(),0);await actions.locator('summary').click();
 const decisions=overview.locator('.meeting-overview-outcome').filter({hasText:'讨论结论'});await decisions.locator('summary').click();assert((await decisions.locator('li').innerText()).includes('增加促销后仍不见好转'));await decisions.locator('summary').click();
 await overview.getByRole('button',{name:'纪要位置',exact:true}).click();await frame.locator('.meeting-reading-back').waitFor();assert(await frame.locator('.meeting-reading-content').isVisible());
 await frame.getByRole('button',{name:'返回会议一览',exact:true}).click();assert(await overview.isVisible());await overview.getByRole('button',{name:'阅读完整纪要',exact:true}).click();assert(await frame.locator('.meeting-reading-content').isVisible());
 return{allTopicsExact:true,emptyActionHonest:true,conditionalDecisionIntact:true,ordinaryContextAndReturn:true,completeNoteReachable:true};
};
