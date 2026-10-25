import { useEffect, useId, useRef } from 'react';

/** Native modal behavior keeps background controls inert; Escape only cancels. */
export function DeleteConfirmation({ title, detail, targetTitle, blocked, onCancel, onConfirm }: {
  title: string; detail: string; targetTitle?: string;
  blocked: boolean; onCancel: () => void; onConfirm: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const keep = useRef<HTMLButtonElement>(null);
  const prefix = useId();
  useEffect(() => {
    const opener = document.activeElement;
    const element = dialog.current;
    element?.showModal();
    keep.current?.focus();
    return () => {
      element?.close();
      if (opener instanceof HTMLElement && opener.isConnected && opener.getClientRects().length)
        opener.focus({preventScroll:true});
    };
  }, []);
  return <dialog ref={dialog} className="ct-delete-confirm" aria-labelledby={`${prefix}-title`}
    aria-describedby={`${prefix}-detail`} onCancel={event => { event.preventDefault(); onCancel(); }}
    onKeyDown={event => {
      if (event.key !== 'Tab') return;
      const actions = [...event.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')];
      const first = actions[0], last = actions[actions.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }}>
    <strong id={`${prefix}-title`}>{title}</strong>
    {targetTitle ? <p>当前录音：{targetTitle}</p> : null}
    <p id={`${prefix}-detail`}>{detail}</p>
    <div className="ct-button-row">
      <button ref={keep} type="button" className="ct-action" onClick={onCancel}>保留内容</button>
      <button type="button" className="ct-action ct-action-danger" disabled={blocked} onClick={onConfirm}>确认删除</button>
    </div>
  </dialog>;
}
