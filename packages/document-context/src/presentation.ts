import {DocumentArchive} from './archive';
import {mainPart,relationships,validateOfficeMembers} from './officePackage';
import {parseDocumentXml,attribute} from './xml';
import {SectionCollector,checkpoint,invalid,type DocumentReadOptions} from './types';

const DRAW=new Set(['http://schemas.openxmlformats.org/drawingml/2006/main','http://purl.oclc.org/ooxml/drawingml/main']);
export function readPresentation(archive:DocumentArchive,collector:SectionCollector,options:DocumentReadOptions){
 const main=mainPart(archive,'pptx'),relations=relationships(archive,main),order:string[]=[];validateOfficeMembers(archive);
 parseDocumentXml(archive.read(main),{open:tag=>{if(tag.local==='sldId'){const id=attribute(tag,'id','http://schemas.openxmlformats.org/officeDocument/2006/relationships')??attribute(tag,'id','http://purl.oclc.org/ooxml/officeDocument/relationships');if(!id||order.includes(id))invalid('演示文稿的页面顺序无法确认。');order.push(id);}}});
 for(let index=0;index<order.length;index++){
  checkpoint(options);const relation=relations.get(order[index]);if(!relation||relation.external||!relation.type.endsWith('/slide'))invalid('演示文稿缺少页面内容。');
  let text='',capture=false,hidden=false;parseDocumentXml(archive.read(relation.target),{open:tag=>{if(tag.local==='sld'&&attribute(tag,'show')==='0')hidden=true;if(DRAW.has(tag.uri)&&tag.local==='t')capture=true;if(DRAW.has(tag.uri)&&tag.local==='br')text+='\n';},close:tag=>{if(DRAW.has(tag.uri)&&tag.local==='t')capture=false;if(DRAW.has(tag.uri)&&tag.local==='p')text+='\n';if(DRAW.has(tag.uri)&&tag.local==='tc')text+='\t';},text:value=>{if(capture)text+=value;}});
  if(hidden){collector.warnings.add('隐藏幻灯片没有纳入提取文字。');continue;}collector.add('幻灯片 '+(index+1),text);
 }
 if(archive.names().some(name=>name.includes('/media/')))collector.warnings.add('图片和图表仍在原件中，本次没有识别图中文字。');
 if(archive.names().some(name=>/\/notesSlides\//.test(name)))collector.warnings.add('演讲者备注没有纳入本次幻灯片正文。');
 collector.warnings.add('文字按幻灯片对象顺序提取，复杂排版请对照原件。');
}
