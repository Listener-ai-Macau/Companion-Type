const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');const {connect,native}=require('./organization_ui.cjs');
(async()=>{const{page,browser}=await connect();try{page.on('dialog',d=>{assert.equal(d.type(),'confirm');assert.match(d.message(),/返回|切换|资料/);native('click','id:android:id/button1');});
 const before=JSON.parse(fs.readFileSync(path.join(__dirname,'android133/reader-before.json')));
 await page.getByRole('navigation',{name:'主导航'}).getByRole('button',{name:'设置',exact:true}).click();
 await page.getByRole('radio',{name:({system:'跟随系统',light:'浅色',dark:'深色'})[before.appearance],exact:true}).check();
 await page.getByRole('navigation',{name:'主导航'}).getByRole('button',{name:'录音',exact:true}).click();await page.getByRole('button',{name:'返回原有资料',exact:true}).click();
 console.log('Ordinary original-library return completed; previous effective appearance restored. Native index/hash readback follows.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
