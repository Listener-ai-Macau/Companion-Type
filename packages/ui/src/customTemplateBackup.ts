export type CustomTemplateDraft={name:string;instructions:string};
const currentKey='companion.minutes.customTemplate.v1';
const restoredKey='companion.minutes.restoredTemplates.v1';
function parseTemplate(value:unknown):CustomTemplateDraft|null {
  if(!value||typeof value!=='object')return null;
  const item=value as Record<string,unknown>;
  if(typeof item.name!=='string'||typeof item.instructions!=='string')return null;
  return {name:item.name,instructions:item.instructions};
}
function distinct(items:CustomTemplateDraft[]):CustomTemplateDraft[] {
  const seen=new Set<string>();return items.filter(item=>{const key=JSON.stringify([item.name,item.instructions]);
    if(seen.has(key))return false;seen.add(key);return true;});
}
export function readRestoredCustomTemplates(storage:Storage):CustomTemplateDraft[] {
  const raw=storage.getItem(restoredKey);if(!raw)return [];
  const parsed:unknown=JSON.parse(raw);if(!Array.isArray(parsed))throw new Error('已恢复的模板无法读取。');
  const items=parsed.map(parseTemplate);if(items.some(item=>item===null))throw new Error('已恢复的模板无法读取。');
  return distinct(items as CustomTemplateDraft[]);
}
export function templatesForBackup(storage:Storage):CustomTemplateDraft[] {
  const raw=storage.getItem(currentKey);const current=raw?parseTemplate(JSON.parse(raw)):null;
  if(raw&&!current)throw new Error('当前自定义模板无法读取。');
  return distinct([...(current&&(current.name||current.instructions)?[current]:[]),...readRestoredCustomTemplates(storage)]);
}
export function mergeRestoredCustomTemplates(storage:Storage,incoming:CustomTemplateDraft[]):void {
  const current=readRestoredCustomTemplates(storage);
  const validated=incoming.map(parseTemplate);if(validated.some(item=>item===null))throw new Error('备份中的自定义模板无效。');
  const merged=distinct([...current,...validated as CustomTemplateDraft[]]);
  if(merged.length)storage.setItem(restoredKey,JSON.stringify(merged));
}
