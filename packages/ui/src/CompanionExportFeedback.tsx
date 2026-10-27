import { CompanionChecklistHandoff } from './CompanionChecklistHandoff';

export interface CompanionExportFeedbackValue {
  message: string;
  format?: string;
  hasWarning?: boolean;
  kind?: 'saved' | 'cancelled' | 'pending' | 'error';
  path?: string;
}

export function exportFileName(path: string): string {
  return path.split(/[\\/]/).filter(Boolean).pop() ?? path;
}

export function CompanionExportFeedback({ feedback, className='ct-export-result' }: {
  feedback: CompanionExportFeedbackValue; className?: string;
}) {
  const classes = new Set(className.split(/\s+/).filter(Boolean));
  if (feedback.hasWarning) {
    classes.delete('ct-step-ok');
    classes.add('ct-step-warn');
  }
  return <div className={[...classes].join(' ')} role={feedback.kind === 'error' ? 'alert' : 'status'}>
    <span>{feedback.message}</span>
    {feedback.kind === 'saved' && feedback.path && (feedback.format === 'todo' || feedback.format === 'todotxt' || feedback.format === 'ics' || feedback.format === 'calendar' || feedback.format?.startsWith('calendarreminder'))
      ? <CompanionChecklistHandoff format={feedback.format?.startsWith('calendarreminder')?'calendar':feedback.format as 'todo'|'todotxt'|'ics'|'calendar'}/> : null}
    {feedback.kind === 'saved' && feedback.path ? <details>
      <summary>查看保存位置</summary>
      <p style={{ overflowWrap: 'anywhere' }}>{feedback.path}</p>
    </details> : null}
  </div>;
}
