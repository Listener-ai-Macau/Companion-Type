import {build} from 'esbuild';
import {spawnSync} from 'node:child_process';
import {mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const revision=process.argv[2]??'r1';
const out=path.join(root,`.cache/p636-ui-${revision}`);await mkdir(out,{recursive:false});
const tests=['tools/test_customer_reading.tsx','tools/test_calendar_export_review.tsx','tools/test_calendar_event_export.tsx'];
const results=[];
for(const entry of tests){
 const file=path.join(out,path.basename(entry)+'.mjs');
 await build({entryPoints:[path.join(root,entry)],outfile:file,bundle:true,platform:'node',format:'esm',packages:'external',jsx:'automatic',tsconfig:path.join(root,'apps/windows/tsconfig.json'),loader:{'.css':'empty'}});
 const result=spawnSync(process.execPath,['--import',pathToFileURL(path.join(root,'tools/component_test_environment.mjs')).href,file],{cwd:root,encoding:'utf8',timeout:90000,windowsHide:true});
 results.push({entry,exitCode:result.status,error:result.error?.message,stdout:result.stdout,stderr:result.stderr});
 process.stdout.write(`${entry}: ${result.status}\n${result.stdout??''}${result.stderr??''}`);
}
await writeFile(path.join(root,`../ui-result-${revision}.json`),JSON.stringify({result:results.every(r=>r.exitCode===0)?'PASS_SOFTWARE_ONLY':'FAIL_PRESERVED',scope:'Affected public calendar export/date-edit/source/cancel checks; no calendar consumer or notification claim',results},null,2));
process.exitCode=results.every(r=>r.exitCode===0)?0:1;
