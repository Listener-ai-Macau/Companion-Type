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
export function MinutesDocument({markdown,renderText,renderSource,generationNote,manualReview=false}:{markdown:string;renderText:(text:string,section?:string,position?:{sectionOccurrence:number;itemOffset:number})=>React.ReactNode;renderSource?:(text:string)=>React.ReactNode;generationNote?:string;manualReview?:boolean}) {
 const manualNotice='> 人工修订：此版本包含使用者的核对或修改，不代表重新生成的 AI 结果；新增负责人和时间请按实际安排确认。\n\n';
 const display=splitGeneratedMeetingMetadata(manualReview&&markdown.startsWith(manualNotice)?markdown.slice(manualNotice.length):markdown);const sections=splitMinutesSections(display.body);
 const headings=sections.map((s,i)=>({s,i})).filter(({s})=>s.title!==null);
 if(!headings.length)return <>{renderText(display.body)}</>;
 return <MeetingReadingFrame markdown={markdown} sections={headings.map(({s})=>s.title!)}><div className="minutes-document">{manualReview&&<p className="manual-minutes-note">已编辑</p>}{sections.map((section,index)=>{
  const title=section.title?meetingHeadingForDisplay(section.title):null;
  if(!title)return <div key={index} className={/^>\s*整理视角：[^\r\n]+$/.test(section.body.trim())?'minutes-preamble minutes-preamble-generated':'minutes-preamble'}>{renderText(section.body)}</div>;
  if(/^(分段原文依据|原文依据)$/.test(section.title!))return <details key={index} className="minutes-source-section"><summary data-meeting-heading={section.title}><span>{title}</span><span>展开核对</span></summary>{renderSource?renderSource(section.body):renderText(section.body)}</details>;
  // Action cards own their one shared filter and their folding. Splitting the
  // source into two render calls would produce two incomplete action scopes.
  const remaining=['Action Items','行动事项'].includes(section.title!)?null:excerpt(section.body);
  const sectionOccurrence=sections.slice(0,index).filter(previous=>previous.title===section.title).length;
  return <section className="minutes-section" key={index}><h3 data-meeting-heading={section.title}>{title}</h3>{renderText(remaining?remaining.first:section.body,section.title!,{sectionOccurrence,itemOffset:0})}{remaining&&<details className="minutes-more"><summary>查看其余 {remaining.count} 项</summary>{renderText(remaining.remaining,section.title!,{sectionOccurrence,itemOffset:4})}</details>}</section>;
 })}{display.metadata&&<details className="minutes-more minutes-generation"><summary>查看生成说明</summary><p>{generationNote||'这是已保存的整理结果，内容请结合转写核对。人工修改会单独标示；生成说明不代表转写或事实准确性已经验证。'}</p></details>}</div></MeetingReadingFrame>;
}
