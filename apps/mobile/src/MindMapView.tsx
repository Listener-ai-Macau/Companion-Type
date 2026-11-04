import { minutesOutline, type MindMapNode } from './mobileMindMap';
import {useMemo,useState} from 'react';
import { ChevronDown, CircleAlert } from 'lucide-react';
import { meetingHeadingForDisplay, splitGeneratedMeetingMetadata } from '../../../packages/ui/src/meetingReading';

type Props={title:string;markdown:string;stale:boolean;onExport:()=>void;busy:boolean};
function NodeText({lines,className}:{lines:string[];className:string}) {
 let fence:string|null=null;
 const visible=lines.some(line=>line.trim());
 if(!visible)return null;
 return <div className={className}>{lines.map((line,index)=>{
  const marker=/^\s*(`{3,}|~{3,})/.exec(line);
  if(marker){const c=marker[1][0];if(!fence)fence=c;else if(fence===c)fence=null;return null;}
  if(fence)return <div className="mindmap-code" key={index}>{line||'\u00a0'}</div>;
  const bullet=/^\s*[-*]\s+(.+)$/.exec(line);
  if(bullet)return <p className="mindmap-item" key={index}><span aria-hidden="true">•</span><span>{bullet[1]}</span></p>;
  const quote=/^\s*>\s?(.*)$/.exec(line);
  if(quote)return <blockquote className="mindmap-quote" key={index}>{quote[1]}</blockquote>;
  if(!line.trim())return <span className="mindmap-line-gap" key={index}/>;
  return <p key={index}>{line}</p>;
 })}</div>;
}
function Branch({node,path,expanded,onToggle}:{node:MindMapNode;path:string;expanded:ReadonlySet<string>;onToggle:(path:string,open:boolean)=>void}) {
 return <li><details open={expanded.has(path)} onToggle={event=>{if(event.target===event.currentTarget)onToggle(path,event.currentTarget.open);}}><summary><span>{meetingHeadingForDisplay(node.title)}<small>{node.children.length?`${node.children.length} 个分支`:'查看内容'}</small></span><ChevronDown size={15} aria-hidden="true"/></summary><NodeText lines={node.body} className="mindmap-body"/>{node.children.length>0&&<ul>{node.children.map((child,i)=><Branch key={i} node={child} path={`${path}.${i}`} expanded={expanded} onToggle={onToggle}/>)}</ul>}</details></li>;
}
/** The saved minutes are reorganized by their own headings, without an AI request. */
export function MobileMindMap({title,markdown,stale,onExport,busy}:Props){
 const root=useMemo(()=>minutesOutline(splitGeneratedMeetingMetadata(markdown).body),[markdown]);
 const [expansion,setExpansion]=useState<{source:string;paths:ReadonlySet<string>}>({source:markdown,paths:new Set()});
 const expanded=expansion.source===markdown?expansion.paths:new Set<string>();
 const paths:string[]=[];const visit=(nodes:MindMapNode[],prefix='')=>nodes.forEach((node,i)=>{const path=prefix?`${prefix}.${i}`:String(i);paths.push(path);visit(node.children,path);});visit(root.children);
 const toggle=(path:string,open:boolean)=>setExpansion(previous=>{const next=new Set(previous.source===markdown?previous.paths:[]);if(next.has(path)===open)return previous;if(open)next.add(path);else next.delete(path);return {source:markdown,paths:next};});
 return <div className="mindmap-view"><div className="mindmap-intro"><div><span className="mindmap-eyebrow">会议内容 · 结构视图</span><h2>思维导图 · 结构视图</h2></div><button className="secondary" disabled={busy} onClick={onExport}>导出导图</button></div><p className="hint">先查看主题，再点开分支。结构来自已保存纪要的标题，不会重新生成内容。</p>{stale&&<p className="source-stale" role="status"><CircleAlert size={16} aria-hidden="true"/><span>转写已更改，导图依据较早的纪要，请核对内容。</span></p>}<div className="mindmap-expansion" role="group" aria-label="导图展开层级"><span>{root.children.length} 个主题分支</span><button type="button" disabled={expanded.size===paths.length||!paths.length} onClick={()=>setExpansion({source:markdown,paths:new Set(paths)})}>全部展开</button><button type="button" disabled={!expanded.size} onClick={()=>setExpansion({source:markdown,paths:new Set()})}>全部收起</button></div><div className="mindmap-scroll" role="region" aria-label="思维导图结构" tabIndex={0}><div className="mindmap-tree" aria-label="纪要结构"><div className="mindmap-root"><span>会议主题</span><strong>{title}</strong></div><NodeText lines={root.body} className="mindmap-preamble"/>{root.children.length>0&&<ul>{root.children.map((node,i)=><Branch key={i} node={node} path={String(i)} expanded={expanded} onToggle={toggle}/>)}</ul>}</div></div></div>;
}
