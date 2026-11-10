const fs=require('node:fs'),path=require('node:path'),{spawnSync}=require('node:child_process');
const code=process.argv[2]||'126';if(!['126','127'].includes(code))throw Error('Unsupported scoped version');
const root='C:/Users/Billy/Desktop/Denzic/Companion/companion-core-android20261109',out='E:/CodexData/Companion/.build-cache/android-media-import20261110/library'+code+'-check';
const {build}=require(root+'/node_modules/esbuild');fs.mkdirSync(out,{recursive:true});
const record={at:new Date().toISOString(),state:'CHECKING_ANDROID_LIBRARY_HIERARCHY',results:[],nativePhoneQualified:false,modelsRun:false};
const save=()=>fs.writeFileSync(path.join(__dirname,'library'+code+'-check.json'),JSON.stringify(record,null,2));
function run(name,args){const r=spawnSync(process.execPath,['--max-old-space-size=512',...args],{cwd:root,encoding:'utf8',windowsHide:true,timeout:90000});fs.writeFileSync(path.join(out,name+'.log'),(r.stdout||'')+(r.stderr||''));record.results.push({name,exit:r.status});save();if(r.status!==0)throw Error(name+' failed '+r.stderr);}
(async()=>{try{
 run('mobile-typecheck',[root+'/node_modules/typescript/bin/tsc','-p',root+'/apps/mobile/tsconfig.json','--noEmit']);
 for(const name of (code==='127'?['test_mobile_audio_import','test_recording_notes','test_playback_tools','test_long_minutes_reading']:['test_mobile_audio_import'])){const output=path.join(out,name+'.mjs');await build({entryPoints:[root+'/tools/'+name+'.tsx'],outfile:output,bundle:true,platform:'node',format:'esm',packages:'external',jsx:'automatic',tsconfig:root+'/apps/mobile/tsconfig.json',loader:{'.css':'empty'}});
 // Resolve external React from the workspace without installing a second copy.
 const local=path.join(root,'.cache/library'+code);fs.mkdirSync(local,{recursive:true});const test=path.join(local,name+'.mjs');fs.copyFileSync(output,test);
 run(name,['--import',require('node:url').pathToFileURL(root+'/tools/component_test_environment.mjs').href,test]);}
 run('mobile-build',[root+'/node_modules/vite/bin/vite.js','build','--config',root+'/apps/mobile/vite.config.ts']);
 record.state='ANDROID_LIBRARY_SOURCE_AND_IMPORT_RESULT_BEHAVIOR_PASSED';save();console.log(JSON.stringify(record));
}catch(e){record.state='ANDROID_LIBRARY_SOURCE_NOT_QUALIFIED';record.error=String(e);save();throw e;}})().catch(e=>{console.error(e);process.exitCode=1;});
