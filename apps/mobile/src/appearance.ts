export type Appearance='system'|'light'|'dark';
export function readAppearance(storage:Pick<Storage,'getItem'>):Appearance{
 try{const current=storage.getItem('companion-appearance');if(current==='system'||current==='light'||current==='dark')return current;const previous=storage.getItem('companion-theme');if(previous==='light'||previous==='dark')return previous;}catch{}
 return 'system';
}
export function resolvedAppearance(value:Appearance,systemDark:boolean):'light'|'dark'{return value==='system'?(systemDark?'dark':'light'):value;}
