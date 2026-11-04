import {build} from 'esbuild';
import {spawnSync} from 'node:child_process';
import {mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const output=path.join(root,'.cache/core-model-boundary');
await mkdir(output,{recursive:true});
const entries=['test_reviewed_speaker_sources.tsx','test_speaker_labelled_sources.ts',
  'test_transcript_bulk_replace.tsx','test_minutes_history_journey.ts',
  'test_short_minutes_evidence.tsx','test_transcript_reading_20261103.tsx'];
const results=[];
for(const name of entries){
  const file=path.join(output,name+'.mjs');
  await build({entryPoints:[path.join(root,'tools',name)],outfile:file,bundle:true,platform:'node',format:'esm',
    packages:'external',jsx:'automatic',tsconfig:path.join(root,'apps/windows/tsconfig.json'),loader:{'.css':'empty'}});
  const result=spawnSync(process.execPath,[file],{cwd:root,encoding:'utf8',timeout:60000,windowsHide:true});
  results.push({name,exitCode:result.status,error:result.error?.message,stdout:result.stdout,stderr:result.stderr});
  process.stdout.write(result.stdout??'');process.stderr.write(result.stderr??'');
}
await writeFile(path.join(output,'result.json'),JSON.stringify({scope:'Offline software review/source compatibility; not model accuracy, devices or installed acceptance',results},null,2));
process.exitCode=results.every(row=>row.exitCode===0)?0:1;
