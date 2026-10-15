import { build } from 'esbuild';
import { resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
await build({entryPoints:['tools/test_companion_sync_pause.tsx'],bundle:true,
  platform:'node',format:'esm',jsx:'automatic',external:['react','react-dom/server','react-test-renderer','lucide-react'],
  alias:{'@companion-type/core':'./packages/core/src/index.ts','@companion-type/ui':'./packages/ui/src/index.ts'},
  plugins:[{name:'test-client',setup(build){
    build.onResolve({filter:/companionClient$/},()=>({path:resolve('tools/app_client_test_stub.ts')}));
    build.onLoad({filter:/\.css$/},()=>({contents:'',loader:'js'}));
  }}],outfile:'.cache/test-sync-pause-r31-bundle.mjs'});
const result=spawnSync(process.execPath,['.cache/test-sync-pause-r31-bundle.mjs'],{stdio:'inherit'});
process.exit(result.status??1);
