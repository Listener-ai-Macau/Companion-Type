export type MeetingOutlineItem={kind:'summary'|'decisions'|'actions'|'questions';title:string;label:string;count:number;hint:string};
const categories:ReadonlyArray<{kind:MeetingOutlineItem['kind'];titles:readonly string[];label:string;hint:string}>=[
 {kind:'summary',titles:['会议概览','全会重点','Summary','会议摘要','重点'],label:'会议重点',hint:'快速了解讨论内容'},
 {kind:'decisions',titles:['Decisions','讨论结论（需核对）','讨论结论','决策'],label:'讨论结论',hint:'结合原话确认'},
 {kind:'actions',titles:['Action Items','行动事项','待办'],label:'行动事项',hint:'核对负责人和时间'},
 {kind:'questions',titles:['Questions','Open Questions','待解问题','待确认问题'],label:'待解问题',hint:'留待下次跟进'},
];
/** Reading index only. Never derives decisions, commitments or people from prose. */
function savedSections(markdown:string) {
 const sections:Array<{title:string;items:string[]}>=[];let current:typeof sections[number]|null=null;
 let fence:{character:string;length:number}|null=null;
 for(const line of markdown.split(/\r?\n/)){
  const marker=/^\s*(`{3,}|~{3,})(.*)$/.exec(line);
  if(marker){if(!fence)fence={character:marker[1][0],length:marker[1].length};
   else if(marker[1][0]===fence.character&&marker[1].length>=fence.length&&!marker[2].trim())fence=null;
   continue;}
  if(fence)continue;
  const heading=/^##\s+(.+?)\s*$/.exec(line);
  if(heading){current={title:heading[1],items:[]};sections.push(current);continue;}
  const item=/^\s*(?:[-*+]\s+|\d+[.)]\s+)(.+)$/.exec(line);
  if(current&&item&&!/^(?:None captured[.。]?|暂无[。]?|无[。]?)$/i.test(item[1].trim()))current.items.push(item[1]);
 }
 return sections;
}
export function meetingSectionTitles(markdown:string):string[] {
 return [...new Set(savedSections(markdown).map(section=>section.title))];
}
export function meetingOutline(markdown:string):MeetingOutlineItem[] {
 const sections=savedSections(markdown);
 return categories.flatMap(category=>{
  // Prefer the saved concise overview when both it and a detailed summary exist.
  const section=category.titles.map(title=>sections.find(s=>s.title===title)).find(s=>s?.items.length);
  return section?[{kind:category.kind,title:section.title,label:category.label,count:section.items.length,hint:category.hint}]:[];
 });
}
