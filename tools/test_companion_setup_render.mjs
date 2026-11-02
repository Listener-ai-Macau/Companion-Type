import {build} from 'esbuild';
import {spawnSync} from 'node:child_process';
import {mkdir, mkdtemp, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

// Component and stubbed app tests only. This does not operate a device,
// launch a browser/native window, capture speech, or call a remote service.
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const names=['test_companion_setup_render','test_companion_dashboard_state','test_companion_journey',
  'test_companion_diagnostics','test_companion_service_actions','test_companion_credentials',
  'test_companion_recovery_center','test_companion_desktop_update','test_recording_readiness',
  'test_companion_app_state','test_transcript_bulk_replace'];
const cache=path.join(root,'.cache','ui-acceptance');
await mkdir(cache,{recursive:true});
const out=await mkdtemp(path.join(cache,'run-'));
const results=[];
for(const name of names){
  const file=path.join(out,name+'.mjs');
  try{
    await build({entryPoints:[path.join(root,'tools',name+'.tsx')],outfile:file,bundle:true,
      platform:'node',format:'esm',jsx:'automatic',packages:'external',
      tsconfig:path.join(root,'apps/windows/tsconfig.json'),loader:{'.css':'empty'},
      plugins:name==='test_companion_app_state'?[{name:'test-client',setup(build){
        build.onResolve({filter:/companionClient$/},()=>({path:path.join(root,'tools/app_client_test_stub.ts')}));
      }}]:[]});
    const result=spawnSync(process.execPath,['--import',pathToFileURL(path.join(root,'tools/component_test_environment.mjs')).href,file],
      {cwd:root,encoding:'utf8',windowsHide:true});
    results.push({name,exitCode:result.status,error:result.error?.message,stdout:result.stdout,stderr:result.stderr});
    process.stdout.write(result.stdout??'');process.stderr.write(result.stderr??'');
  }catch(error){
    results.push({name,exitCode:null,error:String(error)});
    process.stderr.write(`${name}: ${String(error)}\n`);
  }
}
await writeFile(path.join(out,'result.json'),JSON.stringify({scope:'isolated UI and stubbed app only',results},null,2));
process.exitCode=results.every(row=>row.exitCode===0)?0:1;
