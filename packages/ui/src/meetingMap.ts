import {splitGeneratedMeetingMetadata} from './meetingReading';
import {topicReadingParts} from './MeetingTopic';

export type MindMapNode={title:string;body:string[];children:MindMapNode[]};
/** The existing phone outline, shared with the desktop. All source lines survive. */
export function minutesOutline(markdown:string):MindMapNode {
 const root:MindMapNode={title:'',body:[],children:[]};
 const stack:{level:number;node:MindMapNode}[]=[{level:0,node:root}];
 let fence:{character:string;length:number}|null=null;
 for(const line of markdown.split(/\r?\n/)){
  const marker=/^\s*(`{3,}|~{3,})(.*)$/.exec(line);
  if(marker){
   if(!fence)fence={character:marker[1][0],length:marker[1].length};
   else if(marker[1][0]===fence.character&&marker[1].length>=fence.length&&!marker[2].trim())fence=null;
   stack[stack.length-1].node.body.push(line);continue;
  }
  const heading=!fence?/^\s{0,3}(#{1,6})\s+(.+?)\s*$/.exec(line):null;
  if(!heading){stack[stack.length-1].node.body.push(line);continue;}
  const level=heading[1].length;
  while(stack.length>1&&stack[stack.length-1].level>=level)stack.pop();
  const node:MindMapNode={title:heading[2],body:[],children:[]};
  stack[stack.length-1].node.children.push(node);stack.push({level,node});
 }
 return root;
}
export type MeetingMapPoint={kind:'观点'|'建议'|'预计'|'现状'|'决定';text:string};
export type MeetingMapTopic={id:string;label:string;text:string;section:string;takeaway?:string;points?:MeetingMapPoint[];details?:string[];sourceText?:string;sourceSection?:string};
export type MeetingMapSection={title:string;items:string[]};
const overviewTitles=['会议概览','全会重点','Summary','会议摘要','摘要','重点'];
const emptyItem=/^(?:None captured[.。]?|暂无[。]?|无[。]?)$/i;
export function meetingListItems(lines:readonly string[]):string[]{
 const items:string[]=[];let fence:{character:string;length:number}|null=null;
 for(const line of lines){
  const marker=/^\s*(`{3,}|~{3,})(.*)$/.exec(line);
  if(marker){if(!fence)fence={character:marker[1][0],length:marker[1].length};else if(marker[1][0]===fence.character&&marker[1].length>=fence.length&&!marker[2].trim())fence=null;continue;}
  if(fence)continue;
  const item=/^\s*(?:[-*+]\s+|\d+[.)]\s+)(.+)$/.exec(line);
  if(item){items.push(item[1]);continue;}
  if(/^\s{2,}\S/.test(line)&&items.length)items[items.length-1]+='\n'+line.trim();
 }
 return items.filter(x=>!emptyItem.test(x.trim()));
}
export function meetingMapModel(markdown:string){
 const root=minutesOutline(splitGeneratedMeetingMetadata(markdown).body);
 const sections:MeetingMapSection[]=[];
 const visit=(nodes:MindMapNode[])=>nodes.forEach(node=>{
  sections.push({title:node.title,items:meetingListItems(node.body)});visit(node.children);
 });
 visit(root.children);
 const purposeSection=root.children.find(n=>n.title==='会议主线');
 const narrative=root.children.find(n=>n.title==='主题脉络');
 const purpose=purposeSection?meetingListItems(purposeSection.body)[0]??null:null;
 const organized:MeetingMapTopic[]=(narrative?.children??[]).map((node,index)=>{
  const lines=meetingListItems(node.body),first=lines[0]??'';
  const source=sections.find(s=>s.title===node.title+' · 原话');
  const points=lines.flatMap(line=>{const m=/^(观点|建议|预计|现状|决定)：(.+)$/.exec(line);return m?[{kind:m[1] as MeetingMapPoint['kind'],text:m[2]}]:[];});
  const legacy=first.startsWith('判断：');
  return (legacy||points.length>0)&&source?.items.length?{id:'organized-'+index,label:node.title,text:legacy?first:points.map(p=>p.kind+'：'+p.text).join('\n'),section:node.title,
   takeaway:legacy?first.slice(3):points.map(p=>p.kind+'：'+p.text).join('\n'),points:legacy?undefined:points,details:legacy?lines.slice(1).map(t=>t.replace(/^补充：/,'')):lines.filter(t=>t.startsWith('补充：')).map(t=>t.slice(3)),sourceSection:source.title,sourceText:source.items[0]}:null;
 }).filter((item):item is NonNullable<typeof item>=>item!==null);
 const structured=!!purpose&&organized.length>0&&organized.length===(narrative?.children.length??0);
 const overview=overviewTitles.map(title=>sections.find(s=>s.title===title&&s.items.length)).find(Boolean);
 // Without an overview, use actual authored headings. Never invent topic names,
 // decisions, owners, dates or relationships from prose.
 const topics:MeetingMapTopic[]=structured?organized:overview?overview.items.map((text,index)=>({
  id:'topic-'+index,label:topicReadingParts(text).title||text,text,section:overview.title,
 })):sections.filter(s=>s.items.length&&!/依据|原话|核对片段|Keywords|关键词/.test(s.title)).map((section,index)=>({
  id:'section-'+index,label:section.title,text:section.items.join('\n\n'),section:section.title,
 }));
 const find=(titles:string[])=>titles.map(title=>sections.find(s=>s.title===title)).find(Boolean);
 const topicLabel=overview?(['会议概览','全会重点','重点'].includes(overview.title)?'主题':'要点'):'分组';
 return {topics,topicLabel,sections,structured,purpose:structured?purpose:null,outlineUnavailable:sections.some(s=>s.title==='主题整理未完成'),decisions:find(['Decisions','讨论结论（需核对）','讨论结论','决策']),actions:find(['Action Items','行动事项','待办']),discussionQuestions:find(['Questions','会中问题']),questions:find(['Open Questions','待解问题','待确认问题'])};
}
