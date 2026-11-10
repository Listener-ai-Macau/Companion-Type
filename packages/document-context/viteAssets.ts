import {createRequire} from 'node:module';
import {dirname,join} from 'node:path';
import {readFileSync,readdirSync,statSync} from 'node:fs';
import type {Plugin} from 'vite';

/** Keep PDF.js's modern module separate from the app's older WebView target. */
export function documentEngineAssets(noticesFile:string):Plugin{
 const require=createRequire(import.meta.url),root=dirname(require.resolve('pdfjs-dist/package.json'));
 const files=new Map<string,string>([['pdf.min.mjs',join(root,'legacy/build/pdf.min.mjs')],['pdf.worker.min.mjs',join(root,'legacy/build/pdf.worker.min.mjs')],['ThirdPartyNotices.txt',noticesFile]]);
 // This is a text reader. It neither renders pages nor ships PDF.js's
 // optional GPL Liberation fallback TTFs or image/color WASM engines.
 for(const folder of ['cmaps','standard_fonts'])for(const name of readdirSync(join(root,folder))){if(folder==='standard_fonts'&&name.endsWith('.ttf'))continue;const file=join(root,folder,name);if(statSync(file).isFile())files.set(folder+'/'+name,file);}
 return {name:'companion-local-document-engine',
  generateBundle(){for(const [name,file] of files)this.emitFile({type:'asset',fileName:'document-engine/'+name,source:readFileSync(file)});},
  configureServer(server){server.middlewares.use((request,response,next)=>{
   const prefix='/document-engine/',url=request.url?.split('?')[0];if(!url?.startsWith(prefix)){next();return;}
   const file=files.get(url.slice(prefix.length));if(!file){response.statusCode=404;response.end();return;}
   response.setHeader('Content-Type',url.endsWith('.mjs')?'text/javascript; charset=utf-8':'application/octet-stream');response.setHeader('Cache-Control','no-store');response.end(readFileSync(file));
  });},
 };
}
