export type NoteReadingOrder='recent'|'created';
type DatedNote={id:string;createdAt?:string|number;updatedAt?:string|number};
export function noteTimestamp(value:string|number|undefined){
 const time=typeof value==='number'?value:typeof value==='string'?(/^-?\d+(?:\.\d+)?$/.test(value)?Number(value):Date.parse(value)):0;
 return Number.isSafeInteger(time)&&time>0&&time<=8640000000000000?time:0;
}
export function readingOrder<T extends DatedNote>(notes:readonly T[],order:NoteReadingOrder='recent'):T[]{
 const stamp=(note:T)=>order==='recent'?noteTimestamp(note.updatedAt)||noteTimestamp(note.createdAt):noteTimestamp(note.createdAt);
 return notes.map((note,index)=>({note,index,time:stamp(note)})).sort((a,b)=>{
  if(!a.time||!b.time)return a.time===b.time?a.index-b.index:a.time?-1:1;
  return (order==='recent'?b.time-a.time:a.time-b.time)||a.index-b.index;
 }).map(row=>row.note);
}
export function notePreview(text:string){return Array.from(text).slice(0,260).join('').split('\n').slice(0,4).join('\n');}
