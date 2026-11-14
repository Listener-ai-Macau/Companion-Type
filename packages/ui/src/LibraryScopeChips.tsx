import {useRef} from 'react';
import {X} from 'lucide-react';
import './libraryScopeChips.css';

export type LibraryScopeChip={id:string;label:string;removeLabel:string;onRemove:()=>void};
/** Visible scope and reset follow the shadcn Tasks toolbar pattern (MIT). */
export function LibraryScopeChips({chips,onClear,disabled=false,onEmptyFocus,className=''}:{chips:readonly LibraryScopeChip[];onClear:()=>void;disabled?:boolean;onEmptyFocus?:()=>void;className?:string}){
 const group=useRef<HTMLDivElement>(null);
 function change(action:()=>void){action();window.requestAnimationFrame(()=>{const next=group.current?.querySelector<HTMLButtonElement>('button');if(next)next.focus();else onEmptyFocus?.();});}
 if(!chips.length)return null;
 return <div ref={group} className={'library-scope-chips '+className} role="group" aria-label="当前筛选">
  {chips.map(chip=><button key={chip.id} type="button" className="library-scope-chip" disabled={disabled} aria-label={chip.removeLabel} title={chip.label} onClick={()=>change(chip.onRemove)}><span>{chip.label}</span><X size={12} aria-hidden="true"/></button>)}
  <button type="button" className="library-scope-clear" disabled={disabled} onClick={()=>change(onClear)}>清除筛选</button>
 </div>;
}
