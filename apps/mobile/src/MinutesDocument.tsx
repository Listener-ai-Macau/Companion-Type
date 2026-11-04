import { MeetingReadingFrame } from '../../../packages/ui/src/MeetingReadingFrame';
import { meetingHeadingForDisplay, splitGeneratedMeetingMetadata } from '../../../packages/ui/src/meetingReading';

type Section={title:string|null;body:string};
/** Split only level-two headings outside code fences; all other source text stays intact. */
export function splitMinutesSections(markdown:string):Section[] {
 const sections:Section[]=[];let title:string|null=null,lines:string[]=[],fence:string|null=null;
 const flush=()=>{if(title!==null||lines.some(x=>x.trim()))sections.push({title,body:lines.join('\n')});lines=[];};
 for(const line of markdown.split(/\r?\n/)){
  const marker=/^\s*(`{3,}|~{3,})/.exec(line);
  if(marker){const c=marker[1][0];if(!fence)fence=c;else if(fence===c)fence=null;lines.push(line);continue;}
  const heading=!fence?/^##\s+(.+?)\s*$/.exec(line):null;
  if(heading){flush();title=heading[1];}else lines.push(line);
 }
 flush();return sections;
}
function excerpt(body:string):{first:string;remaining:string;count:number}|null {
 const lines=body.split('\n');
 if(lines.some(line=>line.trim()&&!/^[-*]\s+\S/.test(line)))return null;
 const starts=lines.map((line,index)=>/^[-*]\s+\S/.test(line)?index:-1).filter(i=>i>=0);
 if(starts.length<=5)return null;
 const split=starts[4];return {first:lines.slice(0,split).join('\n'),remaining:lines.slice(split).join('\n'),count:starts.length-4};
}
export function MinutesDocument({markdown,renderText,renderSource}:{markdown:string;renderText:(text:string,section?:string)=>React.ReactNode;renderSource?:(text:string)=>React.ReactNode}) {
 const display=splitGeneratedMeetingMetadata(markdown);const sections=splitMinutesSections(display.body);
 const headings=sections.map((s,i)=>({s,i})).filter(({s})=>s.title!==null);
 if(headings.length<2)return <>{renderText(markdown)}</>;
 return <MeetingReadingFrame markdown={markdown} sections={headings.map(({s})=>s.title!)}><div className="minutes-document">{sections.map((section,index)=>{
  const title=section.title?meetingHeadingForDisplay(section.title):null;
  if(!title)return <div key={index} className="minutes-preamble">{renderText(section.body)}</div>;
  if(/^(分段原文依据|原文依据)$/.test(section.title!))return <details key={index} className="minutes-source-section"><summary data-meeting-heading={section.title}><span>{title}</span><span>展开核对</span></summary>{renderSource?renderSource(section.body):renderText(section.body)}</details>;
  const remaining=excerpt(section.body);
  return <section className="minutes-section" key={index}><h3 data-meeting-heading={section.title}>{title}</h3>{section.title==='Decisions'&&<p className="hint">可能包含建议或现行做法；是否已决定，请结合原话核对。</p>}{section.title==='Action Items'&&<p className="hint">请核对事项、负责人和时间；未明确的信息不会自动补全。</p>}{section.title==='会议概览'&&<p className="hint">概览可能遗漏细节。整段录音会一起整理；处理分段不代表会议场次，请结合完整纪要和原话查看。</p>}{renderText(remaining?remaining.first:section.body,section.title!)}{remaining&&<details className="minutes-more"><summary>查看其余 {remaining.count} 项</summary>{renderText(remaining.remaining,section.title!)}</details>}</section>;
 })}{display.metadata&&<details className="minutes-more"><summary>查看生成信息</summary><pre>{display.metadata}</pre></details>}</div></MeetingReadingFrame>;
}
