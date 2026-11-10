import {SaxesParser,type SaxesTagNS} from 'saxes';
import {DOCUMENT_LIMITS,DocumentReadError,capacity,invalid} from './types';

export type XmlHandlers={open?:(tag:SaxesTagNS)=>void;close?:(tag:SaxesTagNS)=>void;text?:(text:string)=>void};
export function decodeDocumentText(bytes:Uint8Array,encoding?:string):string {
 let selected=encoding||'utf-8';if(bytes[0]===0xff&&bytes[1]===0xfe)selected='utf-16le';else if(bytes[0]===0xfe&&bytes[1]===0xff)selected='utf-16be';
 try{return new TextDecoder(selected,{fatal:true}).decode(bytes);}catch{invalid('文字编码无法读取，请选择正确编码或另存为UTF-8后导入。');}
}
/** Namespace-aware event parsing. No external entities, DTD, DOM or fetching. */
export function parseDocumentXml(bytes:Uint8Array,handlers:XmlHandlers){
 const text=decodeDocumentText(bytes);if(/<!DOCTYPE|<!ENTITY/i.test(text))invalid('文档含暂不支持的实体定义，请另存后导入。');
 const parser=new SaxesParser({xmlns:true});let nodes=0,depth=0;
 parser.on('error',()=>invalid('文档XML内容不完整，请检查原件。'));
 parser.on('doctype',()=>invalid('文档含暂不支持的实体定义。'));
 parser.on('opentag',tag=>{if(++nodes>DOCUMENT_LIMITS.xmlNodes||++depth>DOCUMENT_LIMITS.xmlDepth)capacity();handlers.open?.(tag);});
 parser.on('closetag',tag=>{handlers.close?.(tag);depth--;});parser.on('text',text=>handlers.text?.(text));parser.on('cdata',text=>handlers.text?.(text));
 try{for(let offset=0;offset<text.length;offset+=8192)parser.write(text.slice(offset,offset+8192));parser.close();}catch(error){if(error instanceof DocumentReadError)throw error;invalid('文档XML内容无法完整读取，请检查原件。');}return nodes;
}
export function attribute(tag:SaxesTagNS,local:string,namespace?:string):string|undefined{return Object.values(tag.attributes).find(value=>value.local===local&&(namespace===undefined||value.uri===namespace))?.value;}
