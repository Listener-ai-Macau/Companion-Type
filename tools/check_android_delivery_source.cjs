// Existing affected UI contracts, using one small shared test-output directory.
const path=require('node:path'),fs=require('node:fs'),{spawnSync}=require('node:child_process'),{build}=require('esbuild'),{pathToFileURL}=require('node:url');
const root=path.resolve(__dirname,'..'),out=path.join(root,'.cache/shared-android-ui');fs.mkdirSync(out,{recursive:true});
(async()=>{for(const name of ['test_selected_note_handoff','test_manual_note_editing','test_mobile_audio_import']){
 const file=path.join(out,name+'.mjs');await build({entryPoints:[path.join(root,'tools',name+'.tsx')],outfile:file,bundle:true,platform:'node',format:'esm',packages:'external',jsx:'automatic',tsconfig:path.join(root,'apps/mobile/tsconfig.json'),loader:{'.css':'empty'}});
 const r=spawnSync(process.execPath,['--import',pathToFileURL(path.join(root,'tools/component_test_environment.mjs')).href,file],{cwd:root,encoding:'utf8',windowsHide:true});process.stdout.write(r.stdout||'');process.stderr.write(r.stderr||'');if(r.status!==0)throw Error(name+' failed');
}})().catch(e=>{console.error(e);process.exitCode=1;});
