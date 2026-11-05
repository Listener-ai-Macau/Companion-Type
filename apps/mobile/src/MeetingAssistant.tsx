import type {ReactNode} from 'react';
import {ArrowUpRight,FileText,GitBranch,Languages,Sparkles} from 'lucide-react';

export function MeetingAssistant({hasMinutes,serviceReady,busy,onGenerate,onSetup,onTranscript,onMindmap,onTranslate,readingPreview=false,generationBlocked=false,children}:{
 hasMinutes:boolean;serviceReady:boolean;busy:boolean;onGenerate:()=>void;onSetup:()=>void;onTranscript:()=>void;onMindmap:()=>void;onTranslate:()=>void;
 readingPreview?:boolean;generationBlocked?:boolean;children?:ReactNode;
}) {
 return <section className="meeting-assistant" aria-label="会后整理工具">
  <header><span className="meeting-assistant-icon" aria-hidden="true"><Sparkles size={19}/></span><div><span>会议整理</span><h3>{hasMinutes?'整理方式与新版本':'把讨论，整理成清楚的下一步'}</h3></div></header>
  <p>{hasMinutes?'已有纪要可继续阅读；需要另一种整理方式时再生成。':'从已有转写中整理重点、讨论结论、待办和待解问题，结果保存在这条录音中。'}</p>
  {children}
  <button type="button" className="primary meeting-assistant-generate" disabled={busy||readingPreview||(serviceReady&&generationBlocked)} onClick={serviceReady?onGenerate:onSetup}>{readingPreview?'在线 AI · 本轮未提供':serviceReady?(hasMinutes?'重新整理纪要':'生成会议纪要'):'设置AI服务'}<ArrowUpRight size={16}/></button>
  {readingPreview?<p className="meeting-assistant-service">本轮可以阅读预置纪要；不提供在线生成，无需填写密钥。</p>:!serviceReady&&<p className="meeting-assistant-service">使用你配置的第三方服务，需自备密钥，可能产生费用。</p>}

 </section>;
}
