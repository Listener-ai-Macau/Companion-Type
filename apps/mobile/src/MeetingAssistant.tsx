import {ArrowUpRight,FileText,GitBranch,Languages,Sparkles} from 'lucide-react';

export function MeetingAssistant({hasMinutes,serviceReady,busy,onGenerate,onSetup,onTranscript,onMindmap,onTranslate,readingPreview=false}:{
 hasMinutes:boolean;serviceReady:boolean;busy:boolean;onGenerate:()=>void;onSetup:()=>void;onTranscript:()=>void;onMindmap:()=>void;onTranslate:()=>void;
 readingPreview?:boolean;
}) {
 return <section className="meeting-assistant" aria-label="会后整理工具">
  <header><span className="meeting-assistant-icon" aria-hidden="true"><Sparkles size={19}/></span><div><span>会后工作台</span><h3>{hasMinutes?'继续整理这场会议':'把讨论，整理成清楚的下一步'}</h3></div></header>
  <p>{hasMinutes?'核对原文、整理结构，或准备另一种语言的分享。':'从已有转写中整理重点、讨论结论、待办和待解问题，结果保存在这条录音中。'}</p>
  <button type="button" className="primary meeting-assistant-generate" disabled={busy||readingPreview} onClick={serviceReady?onGenerate:onSetup}>{readingPreview?'在线 AI · 本轮未提供':serviceReady?(hasMinutes?'重新整理纪要':'生成会议纪要'):'连接 AI 服务并整理'}<ArrowUpRight size={16}/></button>
  {readingPreview?<p className="meeting-assistant-service">本轮可以阅读预置纪要；不提供在线生成，无需填写密钥。</p>:!serviceReady&&<p className="meeting-assistant-service">使用你配置的第三方服务，需自备密钥，可能产生费用。</p>}
  <div className="meeting-assistant-options"><button type="button" disabled={busy} onClick={onTranscript}><FileText size={17}/><span><strong>核对原文</strong><small>{readingPreview?'查找已提供的文字':'查找文字与回听位置'}</small></span><ArrowUpRight size={14}/></button>{hasMinutes&&<button type="button" disabled={busy} onClick={onMindmap}><GitBranch size={17}/><span><strong>思维导图</strong><small>查看已保存纪要的结构</small></span><ArrowUpRight size={14}/></button>}<button type="button" disabled={busy||readingPreview} onClick={onTranslate}><Languages size={17}/><span><strong>翻译分享</strong><small>{readingPreview?'在线翻译 · 本轮未提供':'按所选语言生成译文'}</small></span><ArrowUpRight size={14}/></button></div>
 </section>;
}
