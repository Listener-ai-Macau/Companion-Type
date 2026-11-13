/** Display-only handling of the exact generated metadata header; source markdown stays intact. */
export function isGeneratedReadingNotice(line:string):boolean {
 return line==='> AI根据详细纪要整理，请结合原文核对。'
  || /^> 长会议已按原文顺序处理全部\d+段。分段原文依据见下文，识别和事实准确性仍需核对。$/.test(line);
}
export function splitGeneratedMeetingMetadata(markdown:string):{body:string;metadata:string|null} {
 const lines=markdown.split(/\r?\n/);let fence:string|null=null;
 for(let i=0;i<lines.length;i++){
  const marker=/^\s*(`{3,}|~{3,})/.exec(lines[i]);
  if(marker){const c=marker[1][0];if(!fence)fence=c;else if(fence===c)fence=null;continue;}
  if(fence||!/^# [^\r\n]+$/.test(lines[i])||lines[i+1]!==''||!/^Generated: .+/.test(lines[i+2]||'')||!/^Duration: \d+ ms$/.test(lines[i+3]||'')||!/^Source: .+/.test(lines[i+4]||'')||!/^Minutes engine: (?:rules_l0 \(draft\)|llm_deepseek \(final\))$/.test(lines[i+5]||''))continue;
  const prefix=lines.slice(0,i);
  const generatedPerspective=prefix.length>=2&&/^> 整理视角：[^\r\n]+$/.test(prefix[0])&&prefix[1]==='';
  // A generated overview can stand between the template label and metadata.
  // Remove only that label; keep every overview/notice line in the reading body.
  const metadata=[...(generatedPerspective?prefix.slice(0,2):[]),...lines.slice(i,i+6)].join('\n');return {body:[...(generatedPerspective?prefix.slice(2):prefix),...lines.slice(i+6)].join('\n'),metadata};
 }
 return {body:markdown,metadata:null};
}
export function meetingHeadingForDisplay(title:string):string {
 const labels:Record<string,string>={Summary:'会议摘要',Decisions:'讨论结论（需核对）','Action Items':'行动事项',Questions:'会中问题','Open Questions':'待确认问题',Keywords:'关键词'};
 return labels[title]||title;
}
