import type { ChecklistPhoneCode } from './checklistPhone';

export type ChecklistPhoneResult = { sessionId: string; sourceKey: string } &
  ({ kind: 'pending' } | { kind: 'error'; message: string } | ChecklistPhoneCode);

export function CompanionChecklistPhone({ result, onClose }: {
  result: ChecklistPhoneResult; onClose: () => void;
}) {
  return <section id="ct-phone-checklist" className="ct-checklist-phone" aria-label="手机带走清单" tabIndex={-1}
    style={{ marginTop: 12, padding: 16, border: '1px solid var(--ct-border, #d8ded9)', borderRadius: 12 }}>
    <div className="ct-button-row" style={{ justifyContent: 'space-between' }}>
      <strong>带到手机</strong><button type="button" className="ct-text-button" onClick={onClose}>收起</button>
    </div>
    {result.kind === 'pending' ? <p role="status">正在准备已保存的清单…</p>
      : result.kind === 'error' ? <p role="alert">{result.message}</p>
      : result.kind === 'tooLong' ? <p role="status">清单较长，二维码无法在这里清楚地完整展示。请用“复制清单”或“导出清单”带走；内容没有截短。</p>
      : <>
        <p>用支持文字二维码的手机扫码工具打开，再保存到备忘录。若相机没有显示文字，可用“复制清单”或“导出清单”。</p>
        <img src={result.dataUrl} width={result.pixels} height={result.pixels} alt="当前已保存清单的文字二维码"
          style={{ display: 'block', maxWidth: '100%', height: 'auto', imageRendering: 'pixelated', background: '#fff' }} />
        <details><summary>查看二维码里的完整文字</summary><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{result.text}</pre></details>
        <p className="ct-step-meta">二维码在本机生成，内含清单文字；没有上传或自动发送。手机保存后才能离开电脑查看，不会自动设置提醒。</p>
      </>}
  </section>;
}
