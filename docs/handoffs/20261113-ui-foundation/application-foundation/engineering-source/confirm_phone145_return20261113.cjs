const fs=require('fs'),assert=require('node:assert/strict'),cp=require('child_process');
const C='C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261110-android-media-import',O=C+'/android145';
const {connect}=require(C+'/organization_ui.cjs');
(async()=>{const{page,browser}=await connect();try{
 const expected=JSON.parse(fs.readFileSync(O+'/appearance-before.json','utf8')).appearance;
 const observed=await page.evaluate(()=>({appearance:localStorage.getItem('companion-appearance')||'system',theme:document.querySelector('.mobile-app')?.dataset.theme}));assert.equal(observed.appearance,expected);assert(['light','dark'].includes(observed.theme));
 const index=JSON.parse(cp.execFileSync('C:/Users/Billy/Desktop/Denzic/Companion/.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe',['-s','d6bd213d','shell','run-as','com.denzic.companion.app','cat','files/companion-library-index.json'],{encoding:'utf8',windowsHide:true}));assert.equal(index.activeId,'original');
 fs.writeFileSync(O+'/original-returned.json',JSON.stringify({at:new Date().toISOString(),state:'ORIGINAL_LIBRARY_AND_PRIOR_APPEARANCE_OBSERVED_AFTER_ORDINARY_RETURN',appearance:expected,observedTheme:observed.theme,originalActiveIndexConfirmed:true,ordinaryReturnAdapterFinalReadback:'Timed out after 10s; original switch had committed. Independent active-index and DOM appearance observation now passed; no return action replayed.',privateContentInspected:false},null,2));
 console.log('Original active library and prior appearance observed independently; no return action replayed');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
