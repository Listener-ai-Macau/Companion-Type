/** Local, supplementary source documents. These are never recorded speech. */
export const DOCUMENT_READER_VERSION='2026-11-10.1';
export const DOCUMENT_LIMITS=Object.freeze({fileBytes:20*1024*1024,zipEntries:4096,archiveBytes:32*1024*1024,partBytes:8*1024*1024,xmlNodes:300000,xmlDepth:128,textCharacters:300000,sections:300,pdfPages:200,spreadsheetCells:100000,spreadsheetRows:10000,deadlineMs:45000});
export type DocumentFormat='pdf'|'docx'|'xlsx'|'pptx'|'txt'|'md'|'csv';
export type DocumentFailureCode='unsupported-format'|'invalid-file'|'capacity'|'cancelled'|'password-required'|'wrong-password'|'no-text'|'environment';
export class DocumentReadError extends Error {
 constructor(readonly code:DocumentFailureCode,message:string){super(message);this.name='DocumentReadError';}
}
export type DocumentSection={id:string;label:string;text:string};
export type DocumentExtraction={schema:1;readerVersion:string;format:DocumentFormat;sourceSha256:string;sections:DocumentSection[];warnings:string[];characters:number};
export type DocumentReadOptions={password?:string;encoding?:'utf-8'|'gb18030'|'utf-16le'|'utf-16be';signal?:AbortSignal;engineBaseUrl?:string;onProgress?:(message:string)=>void};
export function capacity(message='文件内容超过本机处理范围，请拆分后导入。'):never{throw new DocumentReadError('capacity',message);}
export function invalid(message='文件内容无法完整读取，请检查原件或另存后重试。'):never{throw new DocumentReadError('invalid-file',message);}
export function checkpoint(options:DocumentReadOptions){if(options.signal?.aborted)throw new DocumentReadError('cancelled','已停止提取文字，已保存的原件仍保留。');}
export class SectionCollector {
 readonly sections:DocumentSection[]=[];readonly warnings=new Set<string>();characters=0;
 add(label:string,text:string){
  text=text.replace(/\r\n?/g,'\n');if(!text.trim())return;
  if(this.sections.length>=DOCUMENT_LIMITS.sections||this.characters+text.length>DOCUMENT_LIMITS.textCharacters)capacity();
  this.characters+=text.length;this.sections.push({id:'part-'+(this.sections.length+1),label:label.slice(0,160),text});
 }
 finish(format:DocumentFormat,sourceSha256:string):DocumentExtraction {
  if(!this.sections.length)throw new DocumentReadError('no-text','未提取到可读取文字；扫描图片或特殊排版可能需要另行识别，原件仍保留。');
  return {schema:1,readerVersion:DOCUMENT_READER_VERSION,format,sourceSha256,sections:this.sections,warnings:[...this.warnings],characters:this.characters};
 }
}
