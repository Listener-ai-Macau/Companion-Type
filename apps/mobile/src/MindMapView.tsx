import { minutesOutline, type MindMapNode } from './mobileMindMap';
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
function Branch({node}:{node:MindMapNode}) {
 return <li><details open={!/^(分段原文依据|原文依据|未核对的参考草稿)$/.test(node.title)}><summary><span>{meetingHeadingForDisplay(node.title)}</span><ChevronDown size={15} aria-hidden="true"/></summary><NodeText lines={node.body} className="mindmap-body"/>{node.children.length>0&&<ul>{node.children.map((child,i)=><Branch key={i} node={child}/>)}</ul>}</details></li>;
}
/** The saved minutes are reorganized by their own headings, without an AI request. */
export function MobileMindMap({title,markdown,stale,onExport,busy}:Props){
 const root=minutesOutline(splitGeneratedMeetingMetadata(markdown).body);
 return <div className="mindmap-view"><div className="mindmap-intro"><div><span className="mindmap-eyebrow">会议内容 · 结构视图</span><h2>思维导图 · 结构视图</h2></div><button className="secondary" disabled={busy} onClick={onExport}>导出导图</button></div><p className="hint">根据已保存纪要的标题整理；可展开或收起分支，内容不会重新生成。</p>{stale&&<p className="source-stale" role="status"><CircleAlert size={16} aria-hidden="true"/><span>转写已更改，导图依据较早的纪要，请核对内容。</span></p>}<div className="mindmap-scroll" role="region" aria-label="思维导图结构" tabIndex={0}><div className="mindmap-tree" aria-label="纪要结构"><div className="mindmap-root"><span>会议主题</span><strong>{title}</strong></div><NodeText lines={root.body} className="mindmap-preamble"/>{root.children.length>0&&<ul>{root.children.map((node,i)=><Branch key={i} node={node}/>)}</ul>}</div></div></div>;
}
