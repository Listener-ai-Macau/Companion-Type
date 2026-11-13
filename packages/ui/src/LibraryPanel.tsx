import {useEffect,useRef,useState,type ReactNode} from 'react';

/** Native-dialog adapter for the shadcn Mail toolbar's requested tool panels.
 * Layout reference: shadcn/ui, MIT, copyright shadcn. See THIRD_PARTY_NOTICES.
 * Children stay mounted so closing a panel cannot silently discard a draft.
 */
export function LibraryPanel({open,title,blocked,onClose,children}:{open:boolean;title:string;blocked:boolean;onClose:()=>void;children:ReactNode}){
 const dialog=useRef<HTMLDialogElement>(null);const [notice,setNotice]=useState('');
 useEffect(()=>{const d=dialog.current;if(!d)return;if(open&&!d.open){setNotice('');if(d.showModal)d.showModal();else d.setAttribute('open','');}else if(!open&&d.open){if(d.close)d.close();else d.removeAttribute('open');}},[open]);
 function close(){if(blocked){setNotice('还有未保存的分类修改，请先保存或撤销。');return;}onClose();}
 return <dialog ref={dialog} className="ct-library-dialog" aria-label={title} onCancel={e=>{e.preventDefault();close();}}>
  <header><div><h2>{title}</h2><p>{title==='筛选录音'?'缩小当前列表的范围。':'整理所选录音，或备份和恢复会议库。'}</p></div><button type="button" className="ct-action" onClick={close} aria-label="关闭录音面板">关闭</button></header>
  {notice&&<p role="status">{notice}</p>}{children}
 </dialog>;
}
