// Projection of literal list entries in a saved action section. It never
// extracts tasks from a transcript or infers a task from ordinary prose.
export interface SavedAction {
  lineIndex: number;
  text: string;
  completed: boolean;
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
    if (!text || /^(?:none captured|none|无|暂无|无行动项|暂无行动项|待确认)[.。]*$/i.test(text)) return;
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
