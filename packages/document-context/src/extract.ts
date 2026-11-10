import {DocumentArchive} from './archive';
import {readWord} from './word';
import {readPresentation} from './presentation';
import {readSpreadsheet} from './spreadsheet';
import {readPdf} from './pdf';
import {decodeDocumentText} from './xml';
import {DOCUMENT_LIMITS,SectionCollector,DocumentReadError,capacity,checkpoint,invalid,type DocumentFormat,type DocumentReadOptions} from './types';

export async function extractDocument(original:ArrayBuffer,filename:string,expectedSha256:string,options:DocumentReadOptions={}){
 checkpoint(options);if(!original.byteLength)invalid('所选文件为空。');if(original.byteLength>DOCUMENT_LIMITS.fileBytes)capacity('文档最多20MB，请选择较小的文件。');if(!/^[0-9a-f]{64}$/.test(expectedSha256))invalid('原件身份尚未确认，请重新打开材料。');
 const format=filename.split('.').at(-1)?.toLowerCase() as DocumentFormat|undefined;
 if(!format||!['pdf','docx','xlsx','pptx','txt','md','csv'].includes(format))throw new DocumentReadError('unsupported-format','请使用PDF、DOCX、XLSX、PPTX或纯文字文件；旧版Office文件可另存为新版后导入。');
 const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',original)),byte=>byte.toString(16).padStart(2,'0')).join('');if(digest!==expectedSha256)invalid('文档原件校验失败，已停止文字提取；请保留原件后重新导入。');checkpoint(options);
 const bytes=new Uint8Array(original),collector=new SectionCollector();options.onProgress?.('正在本机提取文档文字');
 if(format==='pdf')await readPdf(bytes,collector,options);
 else if(format==='docx')await readWord(new DocumentArchive(bytes),collector,options);
 else if(format==='pptx')readPresentation(new DocumentArchive(bytes),collector,options);
 else if(format==='xlsx')readSpreadsheet(new DocumentArchive(bytes),collector,options);
 else{
  const text=decodeDocumentText(bytes,options.encoding);if(/[\x00-\x08\x0b\x0e-\x1f]/.test(text))invalid('文件包含非文字内容，请确认文件类型或编码。');collector.add('原文件文字',text);
 }
 checkpoint(options);return collector.finish(format,digest);
}
