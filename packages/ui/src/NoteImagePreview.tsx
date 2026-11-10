import {useEffect,useRef,useState} from 'react';
import type {CompanionMeetingNote} from '@companion-type/core';
export function NoteImagePreview({sessionId,note,onLoad}:{sessionId:string;note:CompanionMeetingNote;onLoad?:(sessionId:string,noteId:string)=>Promise<string>}){
 const [src,setSrc]=useState(''),[error,setError]=useState(''),[loading,setLoading]=useState(false),[expanded,setExpanded]=useState(false),[retry,setRetry]=useState(0);const container=useRef<HTMLDivElement>(null);
 useEffect(()=>{let alive=true;setSrc('');setError('');const load=()=>{if(!onLoad)return;setLoading(true);void onLoad(sessionId,note.id).then(value=>{if(!value.startsWith('data:image/jpeg;base64,')||value.length>6*1024*1024)throw Error('图片预览结果无效。');if(alive)setSrc(value);}).catch(e=>{if(alive)setError(e instanceof Error?e.message:'图片暂不可读取，原备注保留。');}).finally(()=>{if(alive)setLoading(false);});};
  if(typeof IntersectionObserver==='undefined'){load();return()=>{alive=false;};}const observer=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)){observer.disconnect();load();}},{rootMargin:'100px'});if(container.current)observer.observe(container.current);return()=>{alive=false;observer.disconnect();};
 },[sessionId,note.id,note.image?.previewSha256,onLoad,retry]);
 if(!note.image)return null;
 return <div className="ct-note-image" ref={container}>{src?<button type="button" className={expanded?'expanded':undefined} aria-label={`展开图片 ${note.image.name}`} onClick={()=>setExpanded(v=>!v)}><img src={src} alt={note.image.name}/></button>:<div role="status">{loading?'正在读取图片…':error||'图片预览'}{error&&<button type="button" onClick={()=>setRetry(v=>v+1)}>重试读取</button>}</div>}<small>{note.image.name} · 原图保存在本机{src?' · 轻点展开':''}</small>{!onLoad&&<small>请在桌面版查看原图片。</small>}</div>;
}
