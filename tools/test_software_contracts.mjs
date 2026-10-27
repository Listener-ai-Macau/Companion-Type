import {build} from 'esbuild';
import {spawnSync} from 'node:child_process';
import {access,mkdir,mkdtemp,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';

// Bundle TypeScript's extensionless project imports for Node. No browser,
// board, cloud provider or live application is opened by these contracts.
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const group=process.argv[2]??'core';
const groups={core:['packages/core/src/companionV1.test.ts','packages/core/src/recordingProcessing.test.ts'],
  customer:['tools/test_customer_reading.tsx','tools/test_calendar_export_review.tsx','tools/test_checklist_phone.tsx']};
if(!Object.hasOwn(groups,group))throw Error('Choose core or customer');
const environment=path.join(root,'tools/component_test_environment.mjs');
const inputs=[...groups[group].map(name=>path.join(root,name)),path.join(root,'apps/windows/tsconfig.json'),
  ...(group==='customer'?[environment]:[])];
const missing=[];
for(const file of inputs)try{await access(file);}catch{missing.push(path.relative(root,file));}
if(missing.length)throw Error('Test prerequisites missing; no suite started: '+missing.join(', '));
if(process.argv.includes('--check')){
  process.stdout.write(JSON.stringify({result:'TEST_PREREQUISITES_READY',group,testsExecuted:false,inputs:inputs.length})+'\n');
  process.exit(0);
}
const cache=path.join(root,'.cache/software-contracts');await mkdir(cache,{recursive:true});
const out=await mkdtemp(path.join(cache,group+'-')),results=[];
for(const name of groups[group]){
  const file=path.join(out,path.basename(name)+'.mjs');
  await build({entryPoints:[path.join(root,name)],outfile:file,bundle:true,platform:'node',format:'esm',
    packages:'external',jsx:'automatic',tsconfig:path.join(root,'apps/windows/tsconfig.json'),loader:{'.css':'empty'}});
  const result=spawnSync(process.execPath,[...(group==='customer'?['--import',pathToFileURL(environment).href]:[]),file],{cwd:root,encoding:'utf8',timeout:90000,windowsHide:true});
  results.push({name,exitCode:result.status,error:result.error?.message,stdout:result.stdout,stderr:result.stderr});
  process.stdout.write(result.stdout??'');process.stderr.write(result.stderr??'');
}
await writeFile(path.join(out,'result.json'),JSON.stringify({group,scope:'offline software contracts only',results},null,2));
process.exitCode=results.every(row=>row.exitCode===0)?0:1;
