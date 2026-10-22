// Projection of literal list entries in a saved action section. It never
// extracts tasks from a transcript or infers a task from ordinary prose.
export interface SavedAction {
  lineIndex: number;
  text: string;
  completed: boolean;
}

// Display the exact native source/condition prefixes once. The saved action,
// its line index, checkbox identity and exports always keep the original text.
// Do not infer conditions or split/reorder clauses from arbitrary prose.
export function compactActionSource(text: string): { title: string; conditional: boolean; supplementary: boolean } {
  const conditional = text.startsWith('有条件：');
  const body = conditional ? text.slice('有条件：'.length) : text;
  const supplementary = body.startsWith('用户补充：');
  const title = supplementary ? body.slice('用户补充：'.length) : body;
  return title.trim() ? { title, conditional, supplementary }
    : { title: text, conditional: false, supplementary: false };
}

// Fold only a literal, identical supplement attached to every saved task.
// The original action text/line index remain the persistence authority.
export function commonActionSupplement(actions: readonly SavedAction[]): { suffix: string; text: string; displayTexts: string[] } | null {
  if (actions.length < 2) return null;
  const first = actions[0].text;
  const start = first.lastIndexOf('（补充：');
  if (start <= 0 || !first.endsWith('）')) return null;
  const suffix = first.slice(start);
  const text = suffix.slice('（补充：'.length, -1);
  if (!text.trim() || /[\r\n]/.test(text)) return null;
  if (actions.every(action => action.text.endsWith(suffix) && action.text.length > suffix.length)) {
    return { suffix, text, displayTexts: actions.map(action=>action.text.slice(0,-suffix.length)) };
  }
  // Fold identical complete shared clauses, retaining their order in every list.
  // No semantic condition extraction: quoted/nested/custom prose stays whole.
  const parts = actions.map(action=>splitActionSupplement(action.text));
  if(parts.some(part=>!part || /[（）()“”‘’「」『』"']/u.test(part.context)))return null;
  const clauses = parts.map(part=>part!.context.split('；'));
  if(clauses.some(items=>items.some(item=>!item.trim())))return null;
  // Do not collapse repeated occurrences or conflicting common-clause order.
  // These are literal attachments, not inferred equivalence or a new sequence.
  if(clauses.some(items=>new Set(items).size!==items.length))return null;
  const common=clauses[0].filter(clause=>clauses.every(items=>items.includes(clause)));
  if(!common.length)return null;
  const sharedSet=new Set(common);
  if(clauses.some(items=>items.filter(clause=>sharedSet.has(clause)).some((clause,index)=>clause!==common[index])))return null;
  const shared=common.join('；');
  return { suffix:'', text:shared, displayTexts:parts.map((part,index)=>{
    const remaining=clauses[index].filter(clause=>!sharedSet.has(clause)).join('；');
    return part!.title+(remaining?`（补充：${remaining}）`:'');
  }) };
}

// Display only: split the exact native supplement wrapper without changing
// any saved text, row identity or its conditions. Ambiguous/custom prose keeps
// its ordinary whole-line presentation.
export function splitActionSupplement(text: string): { title: string; context: string } | null {
  const marker='（补充：';const start=text.indexOf(marker);
  if(start<=0 || !text.endsWith('）') || text.indexOf(marker,start+marker.length)!==-1)return null;
  const context=text.slice(start+marker.length,-1);
  if(!context.trim() || /[\r\n]/.test(context))return null;
  let depth=0;
  for(const ch of context){
    if(ch==='（')depth++;
    else if(ch==='）' && --depth<0)return null;
  }
  return depth===0?{title:text.slice(0,start),context}:null;
}

// Aligned with native action_export::empty_action_notice. These are anchored
// absence statements, not a search for negative words inside a real task.
// Keep the original prose visible; it simply isn't a completable/exported task.
export function emptyActionNotice(text: string): boolean {
  const value=text.trim().replace(/[.。]+$/, '');
  // A complete absence label can explain itself in one matched bracket pair.
  // Its explanation must independently be a known no-task statement. Keep
  // custom titles, quoted negatives and any following actual task untouched.
  const wrapped=/^(?:无|暂无|none(?: captured)?)\s*(?:（([^（）()\r\n]+)）|\(([^（）()\r\n]+)\))$/i.exec(value);
  const explanation=(wrapped?.[1]??wrapped?.[2]??'').trim().replace(/[.。]+$/, '');
  // Existing top-level prose recognition permits explanatory tails. A new
  // wrapper must be stricter: a second instruction inside it is unknown,
  // so retain the whole saved line instead of silently dropping that task.
  const atomicAbsence=/^(?:none captured|none|无|暂无|无行动项|暂无行动项|待确认)$/i.test(explanation)
    || /^(?:(?:转写|原文|录音|本次|当前|会议|文中|内容)(?:中|里)?[，,：:\s]*)?(?:未(?:明确)?(?:给出|提及|记录|识别|提取)(?:明确的?|具体的?)?|没有(?:明确的?|具体的?)?|暂无|无)(?:行动项|待办(?:事项)?|跟进任务|可执行任务|任务)(?:[、或和及](?:负责人|责任人|截止时间|截止日期|截止日|日期|时间))*$/.test(explanation)
    || /^no (?:action items?|tasks?|to-dos?)(?:\s+(?:were |was |are |is )?(?:identified|captured|recorded|found|specified|available|mentioned))?$/i.test(explanation);
  if(wrapped && atomicAbsence)return true;
  return /^(?:none captured|none|无|暂无|无行动项|暂无行动项|待确认)$/i.test(value)
    || /^(?:(?:转写|原文|录音|本次|当前|会议|文中|内容)(?:中|里)?[，,：:\s]*)?(?:未(?:明确)?(?:给出|提及|记录|识别|提取)(?:明确的?|具体的?)?|没有(?:明确的?|具体的?)?|暂无|无)(?:行动项|待办(?:事项)?|跟进任务|可执行任务|任务)(?:[、，,。；;：:\s].*)?$/.test(value)
    || /^no (?:action items?|tasks?|to-dos?)(?:\s+(?:were |was |are |is )?(?:identified|captured|recorded|found|specified|available|mentioned).*)?$/i.test(value);
}

export function savedActions(markdown: string): SavedAction[] {
  const result: SavedAction[] = [];
  let active = false;
  let sectionLevel = 0;
  let fence: string | null = null;
  markdown.split(/\r?\n/).forEach((raw, lineIndex) => {
    const line = raw.trim();
    if (/^(?:```|~~~)/.test(line)) {
      const marker = line[0];
      if (fence === marker) fence = null;
      else if (fence === null) fence = marker;
      return;
    }
    if (fence !== null) return;
    const heading = /^(#+) (.*)$/.exec(line);
    if (heading) {
      const label = heading[2].trim().replace(/#+$/, '').trim().toLowerCase()
        .replace(/^\*+|\*+$/g, '').replace(/[:：]+$/, '');
      if (['action items', 'actions', 'todo', 'to-do', '行动项', '待办', '待办事项', '行动计划'].includes(label)) {
        active = true;
        sectionLevel = heading[1].length;
      } else if (heading[1].length <= sectionLevel) active = false;
      return;
    }
    if (!active) return;
    const item = /^(?:[-*+] |\d+[.)] )(.*)$/.exec(line);
    if (!item) return;
    const completed = /^\[[xX]\] /.test(item[1]);
    const text = item[1].replace(/^\[[ xX]\] /, '').trim();
    if (!text || emptyActionNotice(text)) return;
    result.push({lineIndex, text, completed});
  });
  return result;
}

export function markSavedAction(markdown: string, lineIndex: number, completed: boolean): string | null {
  const item = savedActions(markdown).find(row => row.lineIndex === lineIndex);
  if (!item || item.completed === completed) return null;
  const lines = markdown.split('\n');
  const match = /^(\s*(?:[-*+] |\d+[.)] ))(?:\[[ xX]\] )?(.*?)(\r?)$/.exec(lines[lineIndex]);
  if (!match) return null;
  lines[lineIndex] = `${match[1]}[${completed ? 'x' : ' '}] ${match[2]}${match[3]}`;
  return lines.join('\n');
}
