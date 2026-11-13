/** Reading projection for the native generated document, never a saved edit.
 * Exact source/review sections remain available together beneath the main note.
 * Authored documents without the native generation envelope are unchanged.
 */
import {splitGeneratedMeetingMetadata} from './meetingReading';
export function meetingReadingSources(markdown:string):{body:string;review:string}{
 if(!splitGeneratedMeetingMetadata(markdown).metadata)return {body:markdown,review:''};
 const main:string[]=[],review:string[]=[];let target=main,fence:string|null=null,questions=false;
 for(const line of markdown.split(/\r?\n/)){
  const marker=/^\s*(`{3,}|~{3,})/.exec(line);
  if(marker){const c=marker[1][0];if(!fence)fence=c;else if(fence===c)fence=null;target.push(line);continue;}
  const heading=!fence?/^## (.+)$/.exec(line):null;
  if(heading){
   questions=heading[1]==='Questions';
   target=['补充原文（供核对）','原话核对','待核对片段','Keywords'].includes(heading[1])?review:main;
  }
  // Earlier native releases stored local `unclear` classifications alongside
  // actual questions. Present that explicit marker as review, preserving every
  // source word; do not infer uncertainty from the wording of ordinary text.
  if(!fence&&questions&&/^[-*] 原话待核对：“[^\r\n]*”$/.test(line)){
   if(!review.includes('## 待核对片段（旧版纪要）'))review.push('','## 待核对片段（旧版纪要）','');
   review.push(line);continue;
  }
  target.push(line);
 }
 return {body:main.join('\n'),review:review.join('\n')};
}
