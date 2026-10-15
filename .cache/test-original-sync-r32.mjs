import {build} from 'esbuild';
import {spawnSync} from 'node:child_process';
await build({entryPoints:['tools/test_companion_original_sync.tsx'],bundle:true,platform:'node',format:'esm',jsx:'automatic',
  external:['react','react-dom/server','react-test-renderer','lucide-react'],alias:{'@companion-type/core':'./packages/core/src/index.ts'},
  outfile:'.cache/test-original-sync-r32-bundle.mjs'});
process.exit(spawnSync(process.execPath,['.cache/test-original-sync-r32-bundle.mjs'],{stdio:'inherit'}).status??1);
