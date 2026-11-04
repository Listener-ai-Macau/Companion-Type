import {build} from 'esbuild';
await build({entryPoints:['tools/test_transcript_reading_20261103.tsx'],outfile:'.cache/transcript-reading-20261103.mjs',bundle:true,platform:'node',format:'esm',packages:'external',jsx:'automatic',tsconfig:'apps/windows/tsconfig.json',loader:{'.css':'empty'}});
