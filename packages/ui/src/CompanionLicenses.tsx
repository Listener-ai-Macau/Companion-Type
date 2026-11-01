import { useEffect, useRef, useState } from 'react';

/** The desktop provides a lazy, bundled text reader. No IPC, external links or data export. */
export function CompanionLicenses({ readText }: { readText: () => Promise<string> }) {
  const [text, setText] = useState<string | null>(null);
  const [state, setState] = useState<'idle' | 'loading' | 'error'>('idle');
  const mounted = useRef(true);
  const reading = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const load = async () => {
    if (reading.current || text !== null) return;
    reading.current = true;
    setState('loading');
    try {
      const next = await readText();
      if (mounted.current) { setText(next); setState('idle'); }
    } catch {
      if (mounted.current) setState('error');
    } finally { reading.current = false; }
  };
  return <details onToggle={event => { if (event.currentTarget.open) void load(); }}>
    <summary>开源许可与组件说明</summary>
    <p>第三方组件许可与可选本地转写模型的来源说明保存在本机。对应公开源码随安装包提供，模型许可链接列于下方。</p>
    {state === 'loading' ? <p role="status">正在读取本机说明…</p> : null}
    {state === 'error' ? <p role="alert">本机说明暂时未能打开。<button type="button" className="ct-text-button" onClick={() => void load()}>重试读取</button></p> : null}
    {text !== null ? <pre tabIndex={0} aria-label="第三方许可原文" style={{ maxHeight: '24rem', overflow: 'auto', whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', fontSize: '0.8rem', lineHeight: 1.5 }}>{text}</pre> : null}
  </details>;
}
