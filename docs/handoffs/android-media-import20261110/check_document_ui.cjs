const fs=require('node:fs'),path=require('node:path'),{spawnSync}=require('node:child_process');
const R='C:/Users/Billy/Desktop/Denzic/Companion',S=path.join(R,'companion-device-closure055'),A=path.join(R,'companion-core-android20261109'),D='E:/CodexData/Companion/.build-cache/document-context20261110',C=__dirname;
const {build}=require(S+'/node_modules/esbuild'),result={at:new Date().toISOString(),state:'CHECKING',checks:[],nativePackaged:false,phoneTested:false,modelsRun:false};
function run(root,name,args){const p=spawnSync(process.execPath,['--max-old-space-size=512',...args],{cwd:root,windowsHide:true,encoding:'utf8',timeout:90000});fs.writeFileSync(path.join(D,name+'.log'),(p.stdout||'')+(p.stderr||'')+(p.error||''));result.checks.push({name,exit:p.status});if(p.status!==0)throw Error(name+' failed; see '+D+'/'+name+'.log');}
(async()=>{try{
 for(const [root,label] of [[A,'android'],[S,'windows']])run(root,label+'-typecheck',['node_modules/typescript/bin/tsc','-p','apps/'+(label==='android'?'mobile':'windows')+'/tsconfig.json']);
 for(const [root,name] of [[A,'test_recording_notes'],[A,'test_long_minutes_reading'],[S,'test_document_context_panel']]){
  const output=path.join(root,'.cache/document-context/'+name+'.mjs');fs.mkdirSync(path.dirname(output),{recursive:true});await build({entryPoints:[path.join(root,'tools/'+name+'.tsx')],outfile:output,bundle:true,platform:'node',format:'esm',packages:'external',jsx:'automatic',tsconfig:path.join(root,'apps/windows/tsconfig.json'),loader:{'.css':'empty'}});run(root,name,['--import',require('node:url').pathToFileURL(root+'/tools/component_test_environment.mjs').href,output]);
 }
 result.state='DOCUMENT_CONTEXT_AND_RELATED_READING_SOURCE_CHECKS_PASS';
}catch(error){result.state='FAILED';result.error=String(error);throw error;}finally{fs.writeFileSync(path.join(C,'document-ui-checks.json'),JSON.stringify(result,null,2)+'\n');}})().catch(error=>{console.error(String(error));process.exitCode=1;});
