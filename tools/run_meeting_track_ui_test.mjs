import {build} from 'esbuild';
import {mkdirSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const root=process.cwd(),dir=path.join(root,'.cache/meeting-track-ui-test');mkdirSync(dir,{recursive:true});
for (const name of ['test_meeting_track_ui','test_meeting_track_resume','test_meeting_track_dashboard']) {
 const out=path.join(dir,`${name}.mjs`),alias=process.env.COMPANION_TEST_QRCODE_PATH?{qrcode:process.env.COMPANION_TEST_QRCODE_PATH}:{};
 await build({entryPoints:[path.join(root,`tools/${name}.tsx`)],outfile:out,bundle:true,platform:'node',format:'esm',packages:'external',jsx:'automatic',tsconfig:path.join(root,'apps/windows/tsconfig.json'),alias,loader:{'.css':'empty'}});
 const env=path.join(root,'tools/component_test_environment.mjs');
 const result=spawnSync(process.execPath,['--import',pathToFileURL(env).href,out],{cwd:root,encoding:'utf8',windowsHide:true});process.stdout.write(result.stdout+result.stderr);if(result.status!==0)process.exitCode=result.status??1;
}
