// Affected source behavior only. No app runtime, board, cloud or model calls.
const fs=require('node:fs'),path=require('node:path'),{spawnSync}=require('node:child_process');
const {build}=require('esbuild');
const root=path.resolve(__dirname,'../../..'),out=path.join(root,'core-ui-output');fs.mkdirSync(out);
const result={state:'CHECKING_GROUPED_MEETING_UI_SOURCE',sourceCommit:process.env.GITHUB_SHA,nativePackaged:false,actualRuntimeQualified:false,results:[]};
const save=()=>fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(result,null,2));
function run(name,args){
 const r=spawnSync(process.execPath,args,{cwd:root,encoding:'utf8',timeout:90000,windowsHide:true});
 fs.writeFileSync(path.join(out,name+'.log'),(r.stdout||'')+(r.stderr||'')+(r.error?String(r.error):''));result.results.push({name,exitCode:r.status});save();if(r.status!==0)throw Error(name+' failed; retained log');
}
(async()=>{try{
 run('windows-typecheck',[path.join(root,'node_modules/typescript/bin/tsc'),'--project',path.join(root,'apps/windows/tsconfig.json'),'--noEmit']);
 const cache=path.join(root,'.cache/core-meeting-ui');fs.mkdirSync(cache,{recursive:true});
 for(const name of ['test_content_export_panel051','test_selected_content_copy','test_action_review_tools','test_windows_note_images','test_document_context_panel','test_document_table','test_audio_edit_recording_entry']){
  const output=path.join(cache,name+'.mjs');await build({entryPoints:[path.join(root,'tools',name+'.tsx')],outfile:output,bundle:true,platform:'node',format:'esm',packages:'external',jsx:'automatic',tsconfig:path.join(root,'apps/windows/tsconfig.json'),loader:{'.css':'empty'}});
  run(name,['--import',require('node:url').pathToFileURL(path.join(root,'tools/component_test_environment.mjs')).href,output]);
 }
 result.state='GROUPED_MEETING_UI_SOURCE_CONTRACTS_PASSED';save();
}catch(error){result.state='GROUPED_MEETING_UI_SOURCE_NOT_QUALIFIED';result.error=String(error);save();throw error;}})().catch(error=>{console.error(error);process.exitCode=1;});
