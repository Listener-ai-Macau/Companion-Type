const REVIEW = '## 待核实的跟进清单';

export function readTaskDraft(text: string) {
 const draft = text.split('\n' + REVIEW + '\n')[1];
 if (!draft) return [];
 return draft.trim().split(/\n\n+/).flatMap(block => {
  const [first, ...evidence] = block.split('\n');
  if (!first.startsWith('- ') || !evidence.length || evidence.some(line => !line.startsWith('> '))) return [];
  return [{text:first.slice(2), quotes:evidence.map(line=>line.slice(2))}];
 });
}

/** Headings are already supplied by the source-verified short draft. Keep
 * “请某人核对” separate from the action and any confirmed assignment. */
export function roleChecklist(text: string) {
 if (!/^## 请[^\n]+核对$/m.test(text)) return [];
 let heading = '';
 const result: string[] = [];
 for (const line of text.split('\n')) {
  if (line.startsWith('## ')) heading = line.slice(3);
  else if (line.startsWith('- ') && (/^请.+核对$/.test(heading) || heading==='待确认问题')) {
   result.push(heading+'｜'+line.slice(2));
  }
 }
 return result;
}
