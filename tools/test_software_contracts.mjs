import {build} from 'esbuild';
import {spawnSync} from 'node:child_process';
import {mkdir,mkdtemp,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

// Bundle TypeScript's extensionless project imports for Node. No browser,
// board, cloud provider or live application is opened by these contracts.
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const group=process.argv[2]??'core';
const groups={core:['packages/core/src/companionV1.test.ts','packages/core/src/recordingProcessing.test.ts'],
  customer:['tools/test_customer_reading.tsx']};
if(!Object.hasOwn(groups,group))throw Error('Choose core or customer');
const cache=path.join(root,'.cache/software-contracts');await mkdir(cache,{recursive:true});
const out=await mkdtemp(path.join(cache,group+'-')),results=[];
for(const name of groups[group]){
  const file=path.join(out,path.basename(name)+'.mjs');
  await build({entryPoints:[path.join(root,name)],outfile:file,bundle:true,platform:'node',format:'esm',
    packages:'external',jsx:'automatic',tsconfig:path.join(root,'apps/windows/tsconfig.json'),loader:{'.css':'empty'}});
  const result=spawnSync(process.execPath,[file],{cwd:root,encoding:'utf8',timeout:90000,windowsHide:true});
  results.push({name,exitCode:result.status,error:result.error?.message,stdout:result.stdout,stderr:result.stderr});
  process.stdout.write(result.stdout??'');process.stderr.write(result.stderr??'');
}
await writeFile(path.join(out,'result.json'),JSON.stringify({group,scope:'offline software contracts only',results},null,2));
process.exitCode=results.every(row=>row.exitCode===0)?0:1;
