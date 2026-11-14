import {MeetingDisclosure} from '../../../packages/ui/src/MeetingDisclosure';
import { MeetingReadingFrame } from '../../../packages/ui/src/MeetingReadingFrame';
import { isGeneratedReadingNotice, meetingHeadingForDisplay, splitGeneratedMeetingMetadata } from '../../../packages/ui/src/meetingReading';
import '../../../packages/ui/src/overviewTopics.css';
import '../../../packages/ui/src/meetingNoteDocument.css';
import {MeetingTopic} from '../../../packages/ui/src/MeetingTopic';

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
function excerpt(body:string):{first:string;remaining:string;count:number;next:string}|null {
 const lines=body.split('\n');
 if(lines.some(line=>line.trim()&&!/^[-*]\s+\S/.test(line)))return null;
 const starts=lines.map((line,index)=>/^[-*]\s+\S/.test(line)?index:-1).filter(i=>i>=0);
 if(starts.length<=5)return null;
 const split=starts[4],next=lines[split].replace(/^[-*]\s+/,'').slice(0,36);return {first:lines.slice(0,split).join('\n'),remaining:lines.slice(split).join('\n'),count:starts.length-4,next};
}
export function MinutesDocument({markdown,title,renderText,renderSource,generationNote,manualReview=false}:{markdown:string;title?:string;renderText:(text:string,section?:string,position?:{sectionOccurrence:number;itemOffset:number})=>React.ReactNode;renderSource?:(text:string)=>React.ReactNode;generationNote?:string;manualReview?:boolean}) {
 const manualNotice='> 人工修订：此版本包含使用者的核对或修改，不代表重新生成的 AI 结果；新增负责人和时间请按实际安排确认。\n\n';
 const display=splitGeneratedMeetingMetadata(manualReview&&markdown.startsWith(manualNotice)?markdown.slice(manualNotice.length):markdown);
 const notices:string[]=[];let noticeFence:string|null=null;
 const reading=display.metadata?display.body.split(/\r?\n/).filter(line=>{
  const marker=/^\s*(`{3,}|~{3,})/.exec(line);
  if(marker){const kind=marker[1][0];noticeFence=noticeFence===kind?null:noticeFence??kind;return true;}
  if(!noticeFence&&isGeneratedReadingNotice(line)){if(!notices.includes(line))notices.push(line);return false;}
  return true;
 }).join('\n'):display.body;
 const sections=splitMinutesSections(reading);
 const headings=sections.map((s,i)=>({s,i})).filter(({s})=>s.title!==null);
 if(!headings.length)return <>{renderText(display.body)}</>;
 return <MeetingReadingFrame markdown={markdown} title={title} sections={headings.map(({s})=>s.title!)}><div className="minutes-document">{manualReview?<p className="manual-minutes-note">含人工修订 · 负责人和时间请按实际安排确认</p>:display.metadata?<p className="hint minutes-origin">AI 整理 · 请结合原话核对</p>:null}{sections.map((section,index)=>{
  const title=section.title?meetingHeadingForDisplay(section.title):null;
  if(!title)return <div key={index} className={/^>\s*整理视角：[^\r\n]+$/.test(section.body.trim())?'minutes-preamble minutes-preamble-generated':'minutes-preamble'}>{renderText(section.body)}</div>;
  if(/^(分段原文依据|原文依据|补充原文（供核对）|原话核对|待核对片段|Keywords)$/.test(section.title!))return <MeetingDisclosure key={index} className="minutes-source-section" title={title} heading={section.title!} description="展开核对保存的原始内容">{renderSource?renderSource(section.body):renderText(section.body)}</MeetingDisclosure>;
  if(['Summary','摘要'].includes(section.title!)&&notices.some(line=>line.startsWith('> 长会议已按原文顺序处理全部'))&&headings.some(({s})=>['全会重点','会议概览'].includes(s.title!)))return <MeetingDisclosure key={index} className="minutes-source-section minutes-full-summary" title="完整会议摘要" heading={section.title!} description="按原文顺序查看全部讨论内容">{renderText(section.body)}</MeetingDisclosure>;
  const fallback=['全会重点','会议概览'].includes(section.title!)&&section.body.split('\n').every(line=>!line.trim()||/^[-*]\s+\S/.test(line));
  if(fallback){const points=section.body.split('\n').filter(line=>line.trim()).map(line=>line.replace(/^[-*]\s+/,''));return <section className="minutes-section" key={index}><h3 data-meeting-heading={section.title}>{title}</h3>{points.map((point,i)=><MeetingTopic text={point} key={`${i}:${point}`}/>)}</section>;}
  // Action cards own their one shared filter and their folding. Splitting the
  // source into two render calls would produce two incomplete action scopes.
  const remaining=['Action Items','行动事项'].includes(section.title!)?null:excerpt(section.body);
  const sectionOccurrence=sections.slice(0,index).filter(previous=>previous.title===section.title).length;
  const emptyCopy:Record<string,string>={Decisions:'这份纪要未记录明确结论。','Action Items':'这份纪要尚未提取到明确的行动事项。',Questions:'这份纪要未记录会中问题。',Keywords:'这份纪要未提取关键词。'};
  const empty=/^(?:[-*]\s+)?None captured[.。]?$/i.test(section.body.trim())?emptyCopy[section.title!]:undefined;
  return <section className="minutes-section" key={index}><h3 data-meeting-heading={section.title}>{title}</h3>{section.title==='Decisions'&&!empty&&<p className="hint">可能包含建议或现行做法；是否已决定，请结合原话核对。</p>}{section.title==='Action Items'&&!empty&&<p className="hint">请核对事项、负责人和时间；未明确的信息不会自动补全。</p>}{empty?<p className="hint">{empty}</p>:renderText(remaining?remaining.first:section.body,section.title!,{sectionOccurrence,itemOffset:0})}{remaining&&<MeetingDisclosure className="minutes-more" title={`其余 ${remaining.count} 项`} description={remaining.next?remaining.next+(remaining.next.length>=36?'…':''):undefined}>{renderText(remaining.remaining,section.title!,{sectionOccurrence,itemOffset:4})}</MeetingDisclosure>}</section>;
 })}{display.metadata&&<details className="minutes-more minutes-generation"><summary>查看生成说明</summary><p>{generationNote||'这是已保存的整理结果，内容请结合转写核对。人工修改会单独标示；生成说明不代表转写或事实准确性已经验证。'}</p>{notices.length?renderText(notices.join('\n\n')):null}</details>}</div></MeetingReadingFrame>;
}
