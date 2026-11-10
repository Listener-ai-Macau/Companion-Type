const {connect}=require('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261110-android-media-import/organization_ui.cjs');
(async()=>{ const {page,browser}=await connect(); try {console.log(await page.locator('body').innerText());} finally {await browser.close();} })().catch(e=>{console.error(e);process.exit(1)});
