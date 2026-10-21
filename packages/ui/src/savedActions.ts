// Projection of literal list entries in a saved action section. It never
// extracts tasks from a transcript or infers a task from ordinary prose.
export interface SavedAction {
  lineIndex: number;
  text: string;
  completed: boolean;
}

// Aligned with native action_export::empty_action_notice. These are anchored
// absence statements, not a search for negative words inside a real task.
// Keep the original prose visible; it simply isn't a completable/exported task.
export function emptyActionNotice(text: string): boolean {
  const value=text.trim().replace(/[.。]+$/, '');
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
