export interface CompanionExportFeedbackValue {
  message: string;
  kind?: 'saved' | 'cancelled' | 'pending' | 'error';
  path?: string;
}

export function exportFileName(path: string): string {
  return path.split(/[\\/]/).filter(Boolean).pop() ?? path;
}

export function CompanionExportFeedback({ feedback, className='ct-export-result' }: {
  feedback: CompanionExportFeedbackValue; className?: string;
}) {
  return <div className={className} role={feedback.kind === 'error' ? 'alert' : 'status'}>
    <span>{feedback.message}</span>
    {feedback.kind === 'saved' && feedback.path ? <details>
      <summary>查看保存位置</summary>
      <p style={{ overflowWrap: 'anywhere' }}>{feedback.path}</p>
    </details> : null}
  </div>;
}
