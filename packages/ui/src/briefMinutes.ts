// A reading projection only. Saved text, extraction, editing and exports keep
// the complete original document; this never derives tasks from a transcript.
export function briefMinutes(markdown: string, transcript: string, durationMs: number): string | null {
  if (!transcript.trim() || [...transcript.trim()].length > 280 || !Number.isFinite(durationMs)
      || durationMs < 0 || durationMs > 120_000
      || markdown.includes('```') || markdown.includes('~~~')) return null;
  const labels: Record<string, 'summary' | 'actions' | 'decisions' | 'questions' | 'keywords'> = {
    Summary: 'summary', 摘要: 'summary',
    'Action Items': 'actions', 行动项: 'actions', 待办: 'actions',
    Decisions: 'decisions', 决定: 'decisions', 已明确的决定: 'decisions', 关键决定: 'decisions',
    Questions: 'questions', 问题: 'questions', 待确认: 'questions', 待确认问题: 'questions',
    Keywords: 'keywords', 关键词: 'keywords',
  };
  const headings = [...markdown.matchAll(/^## ([^\r\n]+)\r?$/gm)];
  if (!headings.length) return null;
  const prefix = markdown.slice(0, headings[0].index).trim();
  // A custom introduction or unknown section must stay in the normal view.
  const prefixLines = prefix.split(/\r?\n/).filter(line => line.trim());
  if (prefixLines.some((line, index) => index === 0 ? !/^# [^\r\n]+$/.test(line)
      : !/^(Generated:|Duration:|Source:|Minutes engine:) /.test(line))) return null;
  const sections = new Map<string, string>();
  for (let i = 0; i < headings.length; i++) {
    const heading = headings[i];
    const key = labels[heading[1]];
    if (!key || sections.has(key)) return null;
    sections.set(key, markdown.slice(heading.index! + heading[0].length,
      headings[i + 1]?.index ?? markdown.length).trim());
  }
  if (!sections.get('summary') || !sections.has('actions')) return null;
  const emptySection = (text: string) => !text || /^(?:- )?(?:None captured|无(?:[（(][^\r\n]*[）)])?)[。. ]*$/i.test(text);
  // Do not fold actual decisions/questions merely because the recording is short.
  if (['decisions', 'questions'].some(key => !emptySection(sections.get(key) ?? ''))) return null;
  return `## 重点\n\n${sections.get('summary')}\n\n## 待办\n\n${sections.get('actions') || '本次没有提取到待办。'}`;
}
