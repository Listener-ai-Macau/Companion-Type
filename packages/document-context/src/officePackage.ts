import {zipSync} from 'fflate';
import {DocumentArchive,resolvePart} from './archive';
import {parseDocumentXml,attribute} from './xml';
import {DOCUMENT_LIMITS,capacity,invalid,type DocumentFormat} from './types';

const REL='http://schemas.openxmlformats.org/package/2006/relationships',CONTENT='http://schemas.openxmlformats.org/package/2006/content-types';
const MAIN_TYPES={docx:'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml',xlsx:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml',pptx:'application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml'};
export type PartRelation={id:string;type:string;target:string;external:boolean};
export function relationships(archive:DocumentArchive,part:string):Map<string,PartRelation>{
 const split=part.lastIndexOf('/'),file=part?part.slice(0,split+1)+'_rels/'+part.slice(split+1)+'.rels':'_rels/.rels',result=new Map<string,PartRelation>();if(!archive.has(file))return result;
 parseDocumentXml(archive.read(file),{open:tag=>{
  if(tag.uri!==REL||tag.local!=='Relationship')return;
  const id=attribute(tag,'Id'),type=attribute(tag,'Type'),target=attribute(tag,'Target'),external=attribute(tag,'TargetMode')?.toLowerCase()==='external';
  if(!id||!type||!target||result.has(id))invalid('文档内部引用不完整或重复，请另存后导入。');
  result.set(id,{id,type,target:external?target:resolvePart(part,target),external});
 }});return result;
}
export function mainPart(archive:DocumentArchive,format:Extract<DocumentFormat,'docx'|'xlsx'|'pptx'>):string {
 const candidates=[...relationships(archive,'').values()].filter(item=>item.type.endsWith('/officeDocument'));
 if(candidates.length!==1||candidates[0].external||!archive.has(candidates[0].target))invalid('未找到可读取的Office正文，请检查原件。');
 const part=candidates[0].target;let contentType:string|undefined;
 parseDocumentXml(archive.read('[Content_Types].xml'),{open:tag=>{if(tag.uri===CONTENT&&tag.local==='Override'&&attribute(tag,'PartName')==='/'+part){if(contentType!==undefined)invalid();contentType=attribute(tag,'ContentType');}}});
 if(contentType!==MAIN_TYPES[format])invalid('文件内容与所选格式不符，或属于暂不支持的模板/宏格式。请另存为普通Office文件后导入。');return part;
}
/** Libraries see only checked members with rebuilt ZIP metadata. Input originals
 * stay untouched. This prevents a downstream parser from trusting false sizes.
 */
function checkedMembers(archive:DocumentArchive,keep:boolean):Record<string,Uint8Array> {
 const files:Record<string,Uint8Array>=Object.create(null);let text=0,nodes=0;
 for(const name of archive.names()){
  const bytes=archive.read(name);if(keep)files[name]=bytes;
  if(/\.(?:xml|rels)$/i.test(name)){nodes+=parseDocumentXml(bytes,{text:value=>{text+=value.length;if(text>DOCUMENT_LIMITS.textCharacters*3)capacity();}});if(nodes>DOCUMENT_LIMITS.xmlNodes)capacity();}
 }
 return files;
}
export function checkedOfficeInput(archive:DocumentArchive):Uint8Array{return zipSync(checkedMembers(archive,true),{level:0});}
export function validateOfficeMembers(archive:DocumentArchive){checkedMembers(archive,false);}
