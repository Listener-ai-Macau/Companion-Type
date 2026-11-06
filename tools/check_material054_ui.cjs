const root='C:/Users/Billy/Desktop/Denzic/Companion/recovered-software050';
const {build}=require(root+'/node_modules/esbuild');const fs=require('fs'),{spawnSync}=require('child_process');
const dest=root+'/.cache/material054';fs.mkdirSync(dest,{recursive:true});
(async()=>{
 const file=dest+'/ui-test.mjs';await build({entryPoints:[root+'/tools/test_mobile_material_exports054.tsx'],outfile:file,bundle:true,platform:'node',format:'esm',packages:'external',jsx:'automatic',tsconfig:root+'/apps/mobile/tsconfig.json',loader:{'.css':'empty'}});
 const result=spawnSync(process.execPath,[file],{cwd:root,encoding:'utf8',timeout:30000,windowsHide:true});
 fs.writeFileSync('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261106-android-material-exports054/ui-controlled-result.json',JSON.stringify({status:result.status,stdout:result.stdout,stderr:result.stderr,scope:'Controlled mobile UI, no phone/system dialogs/clipboard or model'},null,2));process.stdout.write(result.stdout??'');process.stderr.write(result.stderr??'');process.exitCode=result.status;
})().catch(e=>{console.error(e);process.exitCode=1;});
