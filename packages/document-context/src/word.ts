import mammoth from 'mammoth/mammoth.browser.js';
import {DocumentArchive} from './archive';
import {checkedOfficeInput,mainPart,relationships} from './officePackage';
import {documentHtmlText} from './htmlText';
import {parseDocumentXml} from './xml';
import {SectionCollector,checkpoint,type DocumentReadOptions} from './types';

export async function readWord(archive:DocumentArchive,collector:SectionCollector,options:DocumentReadOptions){
 const main=mainPart(archive,'docx');checkpoint(options);const input=checkedOfficeInput(archive);
 const result=await mammoth.convertToHtml({arrayBuffer:input.buffer.slice(input.byteOffset,input.byteOffset+input.byteLength) as ArrayBuffer},{externalFileAccess:false,includeEmbeddedStyleMap:false,includeDefaultStyleMap:true,convertImage:mammoth.images.imgElement(async()=>({src:''}))});checkpoint(options);
 collector.add('正文与附注',documentHtmlText(result.value));
 if(result.messages.length)collector.warnings.add('部分文档对象未能按原版呈现，请对照原件核对提取文字。');
 const seen=new Set<string>();let headers=0,footers=0;
 for(const relation of relationships(archive,main).values()){
  if(relation.external){collector.warnings.add('外部链接和文件未被访问。');continue;}
  if(!/\/(?:header|footer)$/.test(relation.type)||seen.has(relation.target))continue;seen.add(relation.target);
  if(!archive.has(relation.target)){collector.warnings.add('部分页眉或页脚无法读取，提取文字可能不完整。');continue;}
  let text='',capture=false;parseDocumentXml(archive.read(relation.target),{open:tag=>{if(tag.local==='t')capture=true;if(tag.local==='tab')text+='\t';if(tag.local==='br')text+='\n';},close:tag=>{if(tag.local==='t')capture=false;if(tag.local==='p')text+='\n';},text:value=>{if(capture)text+=value;}});
  collector.add(relation.type.endsWith('/header')?'页眉补充 '+(++headers):'页脚补充 '+(++footers),text);
 }
 if(archive.names().some(name=>name.includes('/media/')))collector.warnings.add('图片保留在原件中，本次没有识别图中文字。');
 collector.warnings.add('文字按文档结构提取，不对应Word页码；排版、修订和隐藏样式请以原件为准。');
}
