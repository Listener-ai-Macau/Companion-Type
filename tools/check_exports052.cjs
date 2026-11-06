const root='C:/Users/Billy/Desktop/Denzic/Companion/recovered-software050';
const {build}=require(root+'/node_modules/esbuild');
const {spawnSync}=require('child_process'),fs=require('fs');
const out=root+'/.cache/exports052';fs.mkdirSync(out,{recursive:true});
(async()=>{
  const rows=[];
  for(const name of ['test_selected_content_copy.tsx','test_pdf_export_selection.tsx','test_content_export_panel051.tsx']){
    const file=out+'/'+name+'.mjs';
    await build({entryPoints:[root+'/tools/'+name],outfile:file,bundle:true,platform:'node',format:'esm',packages:'external',jsx:'automatic',tsconfig:root+'/apps/windows/tsconfig.json',loader:{'.css':'empty'}});
    const result=spawnSync(process.execPath,[file],{cwd:root,encoding:'utf8',timeout:30000,windowsHide:true});
    rows.push({name,status:result.status,stdout:result.stdout,stderr:result.stderr});
    process.stdout.write(result.stdout??'');process.stderr.write(result.stderr??'');
  }
  fs.writeFileSync(out+'/result.json',JSON.stringify({scope:'controlled shared UI, no native/OS clipboard or owner data',rows},null,2));
  process.exitCode=rows.every(r=>r.status===0)?0:1;
})().catch(error=>{console.error(error);process.exitCode=1;});
