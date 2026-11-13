const fs=require('fs'),assert=require('node:assert/strict'),cp=require('child_process');
const C='C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261110-android-media-import',O=C+'/android146';
const{connect,native}=require(C+'/organization_ui.cjs'),{read}=require(C+'/organization_readback.cjs');
const A='C:/Users/Billy/Desktop/Denzic/Companion/.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';
(async()=>{const{page,browser}=await connect();try{
 assert.equal((await read(page,'appPreferences')).version,'0.1.146');const own=JSON.parse(fs.readFileSync(O+'/public-libraries.json'));assert(own.ids.includes((await read(page,'libraryStatus')).activeId));
 const appearance=JSON.parse(fs.readFileSync(O+'/appearance-before.json')).appearance;
 page.on('dialog',d=>{assert.equal(d.type(),'confirm');assert.match(d.message(),/打开这份保留的资料|返回原有资料/);native('click','id:android:id/button1');});
 const nav=()=>page.getByRole('navigation',{name:'主导航',exact:true});await nav().getByRole('button',{name:'设置',exact:true}).click();await page.getByRole('radio',{name:appearance==='system'?'跟随系统':appearance==='dark'?'深色':'浅色',exact:true}).check();await nav().getByRole('button',{name:'录音',exact:true}).click();await page.getByRole('button',{name:'返回原有资料',exact:true}).click();
 // After the ordinary switch, verify only the active-ID index and appearance.
 // Do not reissue the known-to-timeout application bridge read or inspect original rows.
 let index;const end=Date.now()+15000;do{index=JSON.parse(cp.execFileSync(A,['-s','d6bd213d','shell','run-as','com.denzic.companion.app','cat','files/companion-library-index.json'],{encoding:'utf8',windowsHide:true}));if(index.activeId==='original')break;await new Promise(r=>setTimeout(r,200));}while(Date.now()<end);
 assert.equal(index.activeId,'original');const observed=await page.evaluate(()=>({appearance:localStorage.getItem('companion-appearance')||'system',theme:document.querySelector('.mobile-app')?.dataset.theme}));assert.equal(observed.appearance,appearance);
 fs.writeFileSync(O+'/original-returned.json',JSON.stringify({at:new Date().toISOString(),state:'ORIGINAL_LIBRARY_AND_PRIOR_APPEARANCE_RETURNED_BY_ORDINARY_UI_AND_INDEPENDENT_INDEX_OBSERVATION',appearance,observedTheme:observed.theme,originalActiveIndexConfirmed:true,privateContentInspected:false,knownFinalBridgeReadNotRepeated:true},null,2));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
