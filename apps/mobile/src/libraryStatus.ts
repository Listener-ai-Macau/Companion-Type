export type LibraryStatus={version:number;activeId:string;previousId?:string;token:string;libraries:Array<{id:string;restoredAt:number}>};

export function validateLibraryStatus(value:LibraryStatus):LibraryStatus {
 if(value?.version!==1||typeof value.token!=='string'||!value.token||typeof value.activeId!=='string'||!Array.isArray(value.libraries))throw new Error('当前资料信息未能确认，请重新读取。');
 const ids=new Set<string>();
 for(const item of value.libraries){
  if(!item||typeof item.id!=='string'||!item.id||ids.has(item.id)||!Number.isFinite(item.restoredAt)||item.restoredAt<0||!Number.isFinite(new Date(item.restoredAt).getTime()))throw new Error('保留的资料信息未能确认，请重新读取。');
  ids.add(item.id);
 }
 if(!ids.has('original')||!ids.has(value.activeId))throw new Error('当前资料与原有资料未能完整确认，请重新读取。');
 return value;
}

export function libraryLabel(item:{id:string;restoredAt:number}):string {
 if(item.id==='original')return '原有资料';
 return `${new Intl.DateTimeFormat('zh-CN',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(item.restoredAt))} 恢复的资料`;
}
