/** Display-only handling of the exact generated metadata header; source markdown stays intact. */
export function splitGeneratedMeetingMetadata(markdown:string):{body:string;metadata:string|null} {
 const lines=markdown.split(/\r?\n/);let fence:string|null=null;
 for(let i=0;i<lines.length;i++){
  const marker=/^\s*(`{3,}|~{3,})/.exec(lines[i]);
  if(marker){const c=marker[1][0];if(!fence)fence=c;else if(fence===c)fence=null;continue;}
  if(fence||!/^# [^\r\n]+$/.test(lines[i])||lines[i+1]!==''||!/^Generated: .+/.test(lines[i+2]||'')||!/^Duration: \d+ ms$/.test(lines[i+3]||'')||!/^Source: .+/.test(lines[i+4]||'')||!/^Minutes engine: (?:rules_l0 \(draft\)|llm_deepseek \(final\))$/.test(lines[i+5]||''))continue;
  const metadata=lines.slice(i,i+6).join('\n');return {body:[...lines.slice(0,i),...lines.slice(i+6)].join('\n'),metadata};
 }
 return {body:markdown,metadata:null};
}
export function meetingHeadingForDisplay(title:string):string {
 const labels:Record<string,string>={Summary:'会议摘要',Decisions:'讨论结论（需核对）','Action Items':'行动事项',Questions:'会中问题','Open Questions':'待确认问题',Keywords:'关键词'};
 return labels[title]||title;
}
