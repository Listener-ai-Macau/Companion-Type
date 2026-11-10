const {connect}=require('./notes_ui.cjs'),path=require('node:path');
(async()=>{const{page,browser}=await connect();try{
 const close=page.getByRole('button',{name:'关闭提示',exact:true});if(await close.count())await close.click();
 const light=page.getByRole('button',{name:'切换浅色模式',exact:true});if(await light.count())await light.click();if(await close.count())await close.click();await page.locator('.recording-note').first().scrollIntoViewIfNeeded();await page.screenshot({path:path.join(__dirname,'android124/notes-content-light.png')});
 await page.getByRole('button',{name:'切换深色模式',exact:true}).click();if(await close.count())await close.click();await page.locator('.recording-note').last().scrollIntoViewIfNeeded();await page.screenshot({path:path.join(__dirname,'android124/notes-content-dark.png')});console.log('Captured actual notes cards and image on own phone display in both themes.');
}finally{await browser.close();}})().catch(e=>{console.error(String(e));process.exitCode=1;});
