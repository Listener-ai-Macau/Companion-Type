const fs=require('node:fs'),path=require('node:path'),{spawnSync}=require('node:child_process'),{pathToFileURL}=require('node:url');
const R='C:/Users/Billy/Desktop/Denzic/Companion',S=R+'/companion-device-closure055',A=R+'/companion-core-android20261109',D='E:/CodexData/Companion/.build-cache/document-context20261110';
const {build}=require(S+'/node_modules/esbuild'),out=D+'/node-dependencies/.cache/manual-followup-'+Date.now(),result={at:new Date().toISOString(),state:'CHECKING',results:[],logs:out,nativeQualified:false,modelsRun:false};fs.mkdirSync(out,{recursive:true});
(async()=>{try{
 for(const [root,label,names] of [[S,'windows',['test_manual_note_context','test_manual_followup_notes','test_manual_followup_documents','test_windows_note_images','test_document_context_panel']],[A,'android',['test_manual_followup_notes','test_manual_followup_documents','test_recording_notes']]]){
  for(const name of names){
   const source=root+'/tools/'+name+(name==='test_manual_note_context'?'.ts':'.tsx'),output=out+'/'+label+'-'+name+'.mjs';
   await build({entryPoints:[source],outfile:output,bundle:true,platform:'node',format:'esm',packages:'external',jsx:'automatic',tsconfig:root+'/apps/windows/tsconfig.json',loader:{'.css':'empty'}});
   const p=spawnSync(process.execPath,['--max-old-space-size=192','--import',pathToFileURL(root+'/tools/component_test_environment.mjs').href,output],{cwd:root,windowsHide:true,encoding:'utf8',timeout:90000});
   fs.writeFileSync(out+'/'+label+'-'+name+'.log',(p.stdout||'')+(p.stderr||'')+(p.error||''));result.results.push({platform:label,check:name,exitCode:p.status});console.log(label,name,p.status);
  }
 }
 result.state=result.results.every(r=>r.exitCode===0)?'MANUAL_FOLLOWUP_COMPONENTS_AND_AFFECTED_NOTES_PASSED':'SOURCE_TESTS_FAILED';
}finally{fs.writeFileSync(__dirname+'/manual-followup-ui-source-checks.json',JSON.stringify(result,null,2)+'\n');}})().catch(e=>{console.error(String(e));process.exitCode=1});
