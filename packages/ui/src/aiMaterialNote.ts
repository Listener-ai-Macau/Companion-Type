import type {AiMaterial,AiSave} from './MeetingAiWorkbench';
const prefix='AI 材料（请核对）｜';
export function materialNote(value:AiSave){
 if(!value.title.trim()||/[\r\n]/.test(value.title))throw Error('请填写单行材料名称。');
 const citations=value.result.items.map((item,i)=>`${i+1}. 《${item.citation.title}》\n${item.citation.quote}`).join('\n\n');
 const incomplete=value.result.incomplete?`查询未完成（${value.result.completedChunks}/${value.result.totalChunks}段），材料可能遗漏，请核对。\n`:'';
 const text=`${prefix}${value.title.trim()}\n${value.edited?'含人工编辑':'AI生成草稿'}\n${incomplete}问题：${value.question}\n\n${value.body}\n\n原文依据：\n${citations}`;
 if(Array.from(text).length>4000)throw Error('材料和原文依据合计超过4000字，请精简正文或先复制保留。');
 return text;
}
export function readMaterialNote(note:{id:string;text:string;createdAt?:string}):AiMaterial|null{
 if(!note.text.startsWith(prefix))return null;
 const newline=note.text.indexOf('\n');if(newline<0)return null;
 const raw=note.text.slice(newline+1),parts=readSavedParts(raw);
 return {id:note.id,title:note.text.slice(prefix.length,newline),body:parts?parts.display:raw,question:parts?.question,createdAt:note.createdAt,edited:raw.startsWith('含人工编辑\n')};
}

/** Read only the known unambiguous envelope. All saved source quotes survive;
 * ambiguous or multiline custom envelopes remain literal, without guessing. */
function readSavedParts(raw:string):{question:string;answer:string;display:string}|null{
 const header=/^(?:AI生成草稿|含人工编辑)\n(查询未完成[^\n]*\n)?问题：([^\n]+)\n\n/.exec(raw);
 const marker='\n\n原文依据：\n',end=raw.indexOf(marker);
 if(!header||end<header[0].length||raw.indexOf(marker,end+marker.length)!==-1)return null;
 const answer=raw.slice(header[0].length,end),warning=header[1]?.trim();
 return {question:header[2],answer,display:(warning?warning+'\n\n':'')+raw.slice(header[0].length)};
}

/** Prefer the saved answer in search previews. Ambiguous/custom notes keep
 * their full text; this never changes the stored material or its sources. */
export function materialAnswerText(note:{id:string;text:string}):string|null {
 if(!note.text.startsWith(prefix))return null;
 const newline=note.text.indexOf('\n');if(newline<0)return null;
 return readSavedParts(note.text.slice(newline+1))?.answer.trim()||null;
}
