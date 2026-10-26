export interface CompanionExportFeedbackValue {
  message: string;
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
    {feedback.kind === 'saved' && feedback.path ? <details>
      <summary>查看保存位置</summary>
      <p style={{ overflowWrap: 'anywhere' }}>{feedback.path}</p>
    </details> : null}
  </div>;
}
