import { useEffect, useState } from 'react';
import { Moon, Play, Sparkles, Square } from 'lucide-react';

type CompanionBehaviorMode = 'standard' | 'lively' | 'quiet';

const BEHAVIORS: Record<CompanionBehaviorMode, { label: string; detail: string; beats: string[] }> = {
  standard: { label: '标准 Standard', detail: '使用标准互动间隔；自然眨眼保留，日常提示音遵守安静时段。', beats: ['安静注视', '自然眨眼', '回到时钟'] },
  lively: { label: '活泼 Lively', detail: '拿起或摇晃后的互动回应更积极；自然眨眼节奏保持不变。', beats: ['注意到动作', '积极回应', '稍后安静'] },
  quiet: { label: '安静 Quiet', detail: '减少动作触发表情并关闭日常提示音；自然眨眼和关键状态仍保留。', beats: ['保持安静', '自然眨眼', '时钟常驻'] },
};

export function CompanionBehaviorPreview({ recording }: { recording: boolean }) {
  const [mode, setMode] = useState<CompanionBehaviorMode>('standard');
  const [remaining, setRemaining] = useState(0);
  useEffect(() => {
    if (!remaining) return;
    const timer = globalThis.setTimeout(() => setRemaining((value) => Math.max(0, value - 1)), 1000);
    return () => globalThis.clearTimeout(timer);
  }, [remaining]);
  useEffect(() => {
    if (recording) setRemaining(0);
  }, [recording]);
  const behavior = BEHAVIORS[mode];
  const beat = behavior.beats[Math.min(behavior.beats.length - 1, Math.floor((10 - remaining) / 4))];
  return <section className="ct-panel ct-behavior-preview" aria-label="陪伴模式预览">
    <div className="ct-panel-title"><Moon size={18} /><span>陪伴模式与安静时段</span></div>
    <p className="ct-meeting-hint">Standard、Lively、Quiet 是设备已有模式。这里播放 10 秒无声文字动画，只演示节奏，不会更改设备设置，也不会连接外部音频。</p>
    <div className="ct-mode-row" role="group" aria-label="预览陪伴模式">
      {(Object.keys(BEHAVIORS) as CompanionBehaviorMode[]).map((item) => <button key={item} type="button"
        className={`ct-mode-chip ${mode === item ? 'active' : ''}`} disabled={remaining > 0 || recording}
        onClick={() => setMode(item)}>{BEHAVIORS[item].label}</button>)}
    </div>
    <div className={`ct-behavior-stage ${remaining ? `ct-behavior-${mode}` : ''}`} aria-live="polite">
      <span className="ct-behavior-face">{mode === 'quiet' ? <Moon size={24} /> : <Sparkles size={24} />}</span>
      <div><strong>{remaining ? beat : behavior.label}</strong><p>{behavior.detail}</p></div>
      {remaining ? <span>{remaining} 秒</span> : null}
    </div>
    <div className="ct-button-row">
      <button type="button" className="ct-action" disabled={recording || remaining > 0} onClick={() => setRemaining(10)}><Play size={15} />开始 10 秒预览</button>
      <button type="button" className="ct-action" disabled={!remaining} onClick={() => setRemaining(0)}><Square size={14} />停止预览</button>
    </div>
    <p className="ct-step-meta">{recording ? '录音期间不提供预览，避免声音和注意力干扰。' : '安静时段在设备本地时间可靠后抑制日常提示音；录音、低电和错误等关键状态仍保持可见。'}</p>
  </section>;
}
