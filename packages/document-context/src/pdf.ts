import {SectionCollector,DOCUMENT_LIMITS,DocumentReadError,checkpoint,capacity,invalid,type DocumentReadOptions} from './types';
import type {TextItem} from 'pdfjs-dist/types/src/display/api';
type PdfModule=typeof import('pdfjs-dist');

/** Engine files are bundled locally, never loaded from a CDN at runtime. */
export async function readPdf(bytes:Uint8Array,collector:SectionCollector,options:DocumentReadOptions){
 if(!options.engineBaseUrl||!globalThis.location)throw new DocumentReadError('environment','内置PDF读取组件尚未就绪，请更新应用后重试，原件仍保留。');
 const base=new URL(options.engineBaseUrl,globalThis.location.href);if(base.origin!==globalThis.location.origin)throw new DocumentReadError('environment','PDF读取组件位置无法确认，请更新应用后重试。');
 let engine:PdfModule;try{engine=await import(/* @vite-ignore */ new URL('pdf.min.mjs',base).href) as PdfModule;}catch{throw new DocumentReadError('environment','当前系统组件暂不能读取PDF，请更新系统WebView或应用后重试。');}
 engine.GlobalWorkerOptions.workerSrc=new URL('pdf.worker.min.mjs',base).href;
 // PDF.js's default display-side binary factory uses document.baseURI, which
 // does not exist inside this dedicated reader worker. Fetch local CMaps in
 // its PDF worker instead; no page renderer or image WASM is needed for text.
 const task=engine.getDocument({data:bytes,password:options.password,useSystemFonts:true,disableFontFace:true,useWasm:false,useWorkerFetch:true,disableWorkerRendering:true,stopAtErrors:true,cMapPacked:true,cMapUrl:new URL('cmaps/',base).href,standardFontDataUrl:new URL('standard_fonts/',base).href});
 const abort=()=>{void task.destroy().catch(()=>{});};options.signal?.addEventListener('abort',abort,{once:true});
 try{
  const document=await task.promise;checkpoint(options);if(document.numPages>DOCUMENT_LIMITS.pdfPages)capacity('PDF页数超过200页，请拆分后导入。');
  const permissions=await document.getPermissions();if(permissions&&!permissions.has(engine.PermissionFlag.COPY))throw new DocumentReadError('unsupported-format','这份PDF限制文字提取，原件仍保留；请提供允许提取的副本。');
  for(let index=1;index<=document.numPages;index++){
   checkpoint(options);options.onProgress?.('正在读取PDF，第 '+index+' / '+document.numPages+' 页');const page=await document.getPage(index);
   try{
    const content=await page.getTextContent({includeMarkedContent:false,disableNormalization:false});let text='',previous:TextItem|null=null;
    for(const item of content.items){
     if(!('str' in item))continue;const current=item as TextItem;
     if(previous&&!text.endsWith('\n')&&text&&!/\s$/.test(text)&&current.str&&!/^\s/.test(current.str)){
      const height=Math.max(Math.abs(previous.height),Math.abs(current.height),1),lineChange=Math.abs(current.transform[5]-previous.transform[5])>height*.65;
      const gap=previous.dir==='rtl'?previous.transform[4]-previous.width-current.transform[4]:current.transform[4]-(previous.transform[4]+previous.width);
      if(lineChange)text+='\n';else if(gap>height*.22)text+=' ';
     }
     text+=current.str;if(current.hasEOL)text+='\n';if(collector.characters+text.length>DOCUMENT_LIMITS.textCharacters)capacity();previous=current;
    }
    collector.add('PDF 第 '+index+' 页',text);
   }finally{page.cleanup();}
  }
  collector.warnings.add('分栏、竖排和复杂排版请对照原件；本次没有识别图中文字。');
 }catch(error){
  checkpoint(options);if(error instanceof DocumentReadError)throw error;const failure=error as {name?:string;code?:number};
  if(failure?.name==='PasswordException')throw new DocumentReadError(failure.code===engine.PasswordResponses.INCORRECT_PASSWORD?'wrong-password':'password-required',failure.code===engine.PasswordResponses.INCORRECT_PASSWORD?'PDF密码不正确，请重新输入；密码不会保存。':'这份PDF需要密码才能读取，密码仅用于本机本次提取。');
  invalid('PDF文字无法完整读取，请检查原件或另存后重试。');
 }finally{options.signal?.removeEventListener('abort',abort);await task.destroy().catch(()=>{});}
}
