// A reading projection only. Saved text, extraction, editing and exports keep
// the complete original document; this never derives tasks from a transcript.
import {emptyActionNotice} from './savedActions';
export function briefMinutes(markdown: string, transcript: string, durationMs: number, actionsFirst=false): string | null {
  if (!transcript.trim() || [...transcript.trim()].length > 280 || !Number.isFinite(durationMs)
      || durationMs < 0 || durationMs > 120_000
      || markdown.includes('```') || markdown.includes('~~~')) return null;
  const labels: Record<string, 'summary' | 'actions' | 'decisions' | 'questions' | 'keywords' | 'speakers' | 'unattributed'> = {
    Summary: 'summary', 摘要: 'summary',
    'Action Items': 'actions', 行动项: 'actions', 待办: 'actions',
    Decisions: 'decisions', 决定: 'decisions', 已明确的决定: 'decisions', 关键决定: 'decisions',
    Questions: 'questions', 问题: 'questions', 待确认: 'questions', 待确认问题: 'questions',
    Keywords: 'keywords', 关键词: 'keywords',
    '讨论纪要(按说话人)': 'speakers', '发言归属未确认的原话': 'unattributed',
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
  // A known empty summary is valid when the saved document has tasks or questions.
  // Keep missing/unknown structure on the full reading path.
  if (!sections.has('summary') || !sections.has('actions')) return null;
  const emptySection = (text: string) => !text || /^(?:- )?(?:None captured|无(?:[（(][^\r\n]*[）)])?)[。. ]*$/i.test(text);
  // Keep every actual decision/question visible in the short reading too.
  // An actual question must not bring back the full provenance/template dump.
  const actions=sections.get('actions')??'';
  const noActions=emptySection(actions)||actions.split(/\r?\n/).every(line=>!line.trim()||emptyActionNotice(line.replace(/^[-*+] (?:\[[ xX]\] )?/, '')));
  const actionSection=`## 待办\n\n${noActions?'本次没有提取到待办。':actions}`;
  // A short memo can already be readable in its original form. When the
  // entire summary is literally that same text, show the usable saved tasks
  // first without asking the reader to scan the same sentence again. Remove
  // only list formatting/CRLF for comparison, never punctuation or meaning.
  // The original text and complete saved document remain independently open.
  const summaryText=(sections.get('summary')??'').split(/\r?\n/)
    .map(line=>line.replace(/^[-*+] /,'')).join('\n').trim();
  const duplicateOriginal=!noActions&&summaryText===transcript.trim().replace(/\r\n/g,'\n');
  // Native source sections are retained in the complete document below. They
  // should not force a short note back to the repeated full report template.
  const attributedSource=sections.has('speakers')||sections.has('unattributed');
  const preferActions=!noActions||actionsFirst||duplicateOriginal||attributedSource;
  const reading=preferActions&&!noActions?[actionSection]:[];
  if(!duplicateOriginal && sections.get('summary')?.trim())reading.push(`## 重点\n\n${sections.get('summary')}`);
  if(!emptySection(sections.get('decisions')??''))reading.push(`## 已明确的决定\n\n${sections.get('decisions')}`);
  if(!preferActions||noActions)reading.push(actionSection);
  if(!emptySection(sections.get('questions')??''))reading.push(`## 需确认\n\n${sections.get('questions')}`);
  if(sections.get('unattributed')?.trim())reading.push('## 归属未确认\n\n部分原话的发言者未确认；可展开完整整理逐句核对。');
  return reading.join('\n\n');
}
