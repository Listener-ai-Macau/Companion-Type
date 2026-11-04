import { useId, useRef, type ReactNode } from 'react';

type Mode = 'offlineStore' | 'onlineLive';
const modes: Mode[] = ['offlineStore', 'onlineLive'];

/** Both documents are already local. Keyboard navigation never generates data. */
export function MinutesModeTabs({ value, onChange, labels, dualMode, children }: {
  value: Mode;
  onChange: (mode: Mode) => void;
  labels: Record<Mode, { visible: string; accessible: string }>;
  dualMode: boolean;
  children: ReactNode;
}) {
  const prefix = useId();
  const buttons = useRef<Partial<Record<Mode, HTMLButtonElement | null>>>({});
  const activate = (mode: Mode) => { if (mode !== value) onChange(mode); };
  return <div className="ct-meeting-document">
    {dualMode ? <div className="ct-minutes-mode-tabs" role="tablist" aria-label="双模式纪要">
      {modes.map((mode, index) => <button key={mode} ref={element => { buttons.current[mode] = element; }}
        type="button" role="tab" id={`${prefix}-tab-${mode}`} aria-controls={`${prefix}-panel-${mode}`}
        aria-label={labels[mode].accessible} aria-selected={value === mode} tabIndex={value === mode ? 0 : -1}
        className={`ct-mode-chip ${value === mode ? 'active' : ''}`} onClick={() => activate(mode)}
        onKeyDown={event => {
          if (event.altKey || event.ctrlKey || event.metaKey) return;
          const next = event.key === 'ArrowRight' ? (index + 1) % modes.length
            : event.key === 'ArrowLeft' ? (index + modes.length - 1) % modes.length
            : event.key === 'Home' ? 0 : event.key === 'End' ? modes.length - 1 : null;
          if (next === null) return;
          event.preventDefault();
          activate(modes[next]);
          buttons.current[modes[next]]?.focus();
        }}>{labels[mode].visible}</button>)}
    </div> : null}
    {dualMode ? modes.map(mode => <div key={mode} role="tabpanel" id={`${prefix}-panel-${mode}`}
      className="ct-minutes-panel" aria-labelledby={`${prefix}-tab-${mode}`} hidden={value !== mode}
      tabIndex={value === mode ? 0 : -1}>{value === mode ? children : null}</div>) : children}
  </div>;
}
