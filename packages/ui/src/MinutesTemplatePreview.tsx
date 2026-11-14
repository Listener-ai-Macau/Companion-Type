import './minutesTemplatePreview.css';

const focus={meeting:'整理会议重点、已作结论和需要跟进的安排。',interview:'突出提问、回应和与访谈目的有关的原话。',lecture:'突出概念、讲解和录音中提到的例子。'};
/** Preview the chosen instructions, never fabricate a sample meeting result. */
export function MinutesTemplatePreview({template}:{template:{id:'meeting'|'interview'|'lecture'|'custom';name?:string;instructions?:string}}){
 return <details className="minutes-template-preview"><summary>预览整理侧重点</summary>
  <p>{template.id==='custom'?template.instructions||'填写自己的整理要求后，可以在这里核对。':focus[template.id]}</p>
  <small>这是整理要求的预览。生成时使用当前原文，已有纪要保留；没有明确的负责人和时间不会自动补全。</small>
 </details>;
}
