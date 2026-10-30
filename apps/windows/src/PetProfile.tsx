import {operationErrorText} from '../../../packages/ui/src/operationFailure';
import {useEffect,useLayoutEffect,useRef,useState} from 'react';
import {invoke} from '@tauri-apps/api/core';
import {DeleteConfirmation} from '../../../packages/ui/src/DeleteConfirmation';

type Memory={id:number;createdUtc:number;expiresUtc:number;kind:number;text:string};
type Profile={uid:string;generation:number;personality:number;seed:number;petName:string;ownerName:string;
  memoryEnabled:boolean;briefReplies:boolean;doNotInterrupt:boolean;memories:Memory[]};
type Preset={code:number;label:string;title:string;description:string};
type View={profile:Profile;persisted:boolean;cleanupPending:boolean;presets:Preset[]};
type Editor=Memory&{expiry:string};
const kindLabel=['相处习惯','以后接着聊的事','我确认的事实'];
const date=(seconds:number)=>new Date(seconds*1000).toLocaleDateString();
const uidKey=(value?:string|null)=>typeof value==='string'&&/^[0-9a-f]{24}$/i.test(value)?value.toLowerCase():null;
function memoryEditorChanged(editor:Editor|null,profile?:Profile):boolean{
  if(!editor)return false;const saved=profile?.memories.find(m=>m.id===editor.id);
  return saved?editor.text!==saved.text||editor.kind!==saved.kind||editor.expiry!=='keep'
    :editor.text!==''||editor.kind!==0||editor.expiry!=='7';
}
const sameEditor=(a:Editor|null,b:Editor)=>!!a&&a.id===b.id&&a.text===b.text&&a.kind===b.kind
  &&a.expiry===b.expiry&&a.createdUtc===b.createdUtc&&a.expiresUtc===b.expiresUtc;

export function PetProfile({disabled,deviceUid,transcript,onUnsavedChange}:{disabled:boolean;deviceUid?:string|null;transcript?:string;onUnsavedChange?:(unsaved:boolean)=>void}){
  const [open,setOpen]=useState(false),[view,setView]=useState<View|null>(null),[draft,setDraft]=useState<Profile|null>(null);
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const [uncertain,setUncertain]=useState(false),[editor,setEditor]=useState<Editor|null>(null);
  const [personaOpen,setPersonaOpen]=useState(false);
  const [confirm,setConfirm]=useState<number|'reset'|'reload'|{switchUid:string}|null>(null);
  const epoch=useRef(0),working=useRef(false),writing=useRef(false);
  const connectedUid=uidKey(deviceUid),currentUid=useRef(connectedUid);currentUid.current=connectedUid;
  const currentDisabled=useRef(disabled);currentDisabled.current=disabled;
  const reportUnsaved=useRef(onUnsavedChange);reportUnsaved.current=onUnsavedChange;
  const personaDirty=!!view&&!!draft&&(draft.personality!==view.profile.personality||
    draft.petName!==view.profile.petName||draft.ownerName!==view.profile.ownerName);
  const localPending=personaDirty||memoryEditorChanged(editor,view?.profile)||uncertain||(busy&&writing.current);
  const pendingNow=useRef(localPending);pendingNow.current=localPending;
  // The close listener may arrive immediately after an input event. Report in
  // the commit phase so the parent guard is current before its next frame.
  useLayoutEffect(()=>{onUnsavedChange?.(localPending);},[localPending,onUnsavedChange]);
  useEffect(()=>{
    // Retire response ownership, not local edits, when a link becomes unknown.
    const unconfirmedWrite=writing.current;epoch.current++;working.current=false;writing.current=false;
    setBusy(false);setConfirm(null);setError('');setNotice('');
    if(unconfirmedWrite)setUncertain(true);
    if(connectedUid&&view&&uidKey(view.profile.uid)!==connectedUid&&!pendingNow.current){
      setView(null);setDraft(null);setEditor(null);setUncertain(false);setPersonaOpen(false);
    }
  },[connectedUid]);
  useEffect(()=>()=>{epoch.current++;reportUnsaved.current?.(false);},[]);
  const unavailable=disabled||!connectedUid;
  const differentPet=!!view&&!!connectedUid&&uidKey(view.profile.uid)!==connectedUid;
  const blocked=unavailable||busy||uncertain||differentPet;
  const localEditBlocked=disabled||busy;
  const accept=(next:View,preservePersona:boolean)=>{
    setView(next);setDraft(before=>preservePersona&&before?{...next.profile,
      personality:before.personality,petName:before.petName,ownerName:before.ownerName}:{...next.profile});
  };
  const action=async(command:string,args:Record<string,unknown>={},write=false,preservePersona=false,expectedUid?:string)=>{
    const target=currentUid.current;
    if(working.current||currentDisabled.current||!target||(expectedUid&&target!==expectedUid))return false;
    if(write&&(!view||uidKey(view.profile.uid)!==target||uncertain))return false;
    working.current=true;writing.current=write;setBusy(true);setError('');setNotice('');const started=epoch.current;
    try{
      const next=await invoke<View>(command,args);
      if(started!==epoch.current||currentUid.current!==target)return false;
      if(uidKey(next.profile.uid)!==target)throw new Error('连接的宠物变了，请重新读取。');
      accept(next,preservePersona);setUncertain(false);setConfirm(null);
      if(write&&!preservePersona)setPersonaOpen(false);
      setNotice(write?(next.cleanupPending?'新内容已保存，旧副本清理尚未完成。':'已保存在这只宠物中。'):
        (next.persisted?'已读取这只宠物保存的档案。':'这是这只宠物的初始性格，保存后可继续调整。'));
      return true;
    }catch(e){if(started===epoch.current&&currentUid.current===target){setError(operationErrorText(e,'profile'));if(write)setUncertain(true);}return false;}
    finally{if(started===epoch.current&&currentUid.current===target){working.current=false;writing.current=false;setBusy(false);}}
  };
  const read=()=>void action('get_companion_pet_profile');
  const load=()=>{
    if(differentPet&&connectedUid){setConfirm({switchUid:connectedUid});return;}
    if(personaDirty||editor)setConfirm('reload');else read();
  };
  const switchPet=(expected:string)=>{
    if(currentUid.current!==expected||currentDisabled.current||working.current){setConfirm(null);setError('连接已变化，请核对当前宠物后再查看。');return;}
    epoch.current++;setView(null);setDraft(null);setEditor(null);setConfirm(null);setUncertain(false);setPersonaOpen(false);
    void action('get_companion_pet_profile',{},false,false,expected);
  };
  const startMemory=(text='')=>{
    const ids=new Set(view?.profile.memories.map(m=>m.id));let id=0;
    do{id=crypto.getRandomValues(new Uint32Array(1))[0]||1;}while(ids.has(id));
    setEditor({id,createdUtc:Math.floor(Date.now()/1000),expiresUtc:0,kind:text?1:0,text,expiry:'7'});
    setConfirm(null);setError('');setNotice('');
  };
  const saveMemory=async()=>{
    if(!view||!editor)return;
    if(!editor.text.trim()){setError('写一句你确实想让它记住的内容即可。');return;}
    const now=Math.floor(Date.now()/1000);
    const original=view.profile.memories.find(m=>m.id===editor.id);
    const contentChanged=!original||editor.text.trim()!==original.text||editor.kind!==original.kind;
    const createdUtc=contentChanged?now:editor.createdUtc;
    const expiresUtc=editor.expiry==='keep'?editor.expiresUtc:editor.expiry==='forever'?0:now+Number(editor.expiry)*86400;
    if(expiresUtc!==0&&expiresUtc<=createdUtc){setError('这条记忆的原有效期已结束，请选择新的保留时间。');return;}
    const memory:Memory={id:editor.id,createdUtc,expiresUtc,
      kind:editor.kind,text:editor.text.trim()};
    const memories=view.profile.memories.filter(m=>m.id!==memory.id);memories.push(memory);
    const submitted={...editor};
    if(await action('save_companion_pet_profile',{profile:{...view.profile,memories}},true,true))setEditor(current=>sameEditor(current,submitted)?null:current);
  };
  const remove=async(id:number)=>{
    if(!view)return;
    const memories=view.profile.memories.filter(m=>m.id!==id);
    await action('save_companion_pet_profile',{profile:{...view.profile,memories}},true,true);
  };
  const clearMemories=async()=>{
    if(!view)return;
    await action('save_companion_pet_profile',{profile:{...view.profile,memories:[],memoryEnabled:false}},true,true);
  };
  const preset=view?.presets.find(p=>p.code===draft?.personality);
  const savedPreset=view?.presets.find(p=>p.code===view.profile.personality);
  const memoryBytes=editor?new TextEncoder().encode(editor.text.trim()).length:0;
  return <details open={open} onToggle={e=>setOpen(e.currentTarget.open)} style={{marginTop:16,borderTop:'1px solid #d8ded8',paddingTop:12}}>
    <summary style={{cursor:'pointer',fontWeight:650}}>名字、性格与记忆</summary>
    {open?<div style={{paddingTop:12}}>
      <p style={{margin:'0 0 10px'}}>给它起个名字，或告诉它一件想记住的事。内容保存在这只宠物里。</p>
      {!view?<button disabled={unavailable||busy} onClick={load}>查看这只宠物</button>:null}
      {!connectedUid?<p role="status">{view?'连接暂时不可用。上次读取的档案和未保存编辑保留在这个窗口；回到同一只宠物后，再明确保存。':'先到“设备与同步”连接宠物，再回来查看。'}</p>:null}
      {differentPet?<div role="alert"><p>连接的宠物已变化。下面保留的是上一只宠物的编辑，不会写入当前宠物。</p>
        <button disabled={unavailable||busy} onClick={load}>查看当前宠物</button></div>:null}
      {typeof confirm==='object'&&confirm?<DeleteConfirmation title="切换到当前宠物？"
        detail="这会放弃窗口里上一只宠物尚未提交的编辑，再读取当前宠物。不会删除宠物中已保存的内容，也不会撤回已提交的写入。你也可以保留编辑，连接回原来的宠物。"
        blocked={unavailable||busy||confirm.switchUid!==connectedUid} cancelLabel="保留这些编辑" confirmLabel="放弃编辑并查看当前宠物"
        onCancel={()=>setConfirm(null)} onConfirm={()=>switchPet(confirm.switchUid)}/>:null}
      {busy?<p role="status">正在核对宠物中的内容，请稍等。</p>:null}
      {notice?<p role="status">{notice}</p>:null}
      {error?<p role="alert">{error}</p>:null}
      {uncertain?<p>这次写入尚未确认。请先重新读取实际内容，未保存的文字仍留在这里供你核对。</p>:null}
      {confirm==='reload'?<div><p>重新读取会放弃未保存的性格与称呼；记忆编辑文字会保留，供你核对。</p>
        <button disabled={busy} onClick={()=>{setConfirm(null);read();}}>重新读取</button>{' '}
        <button disabled={busy} onClick={()=>setConfirm(null)}>继续编辑</button></div>:null}
      {view&&draft?<>
        <div style={{margin:'16px 0 8px'}}>
          <strong>{view.profile.petName||'Companion'}</strong>{' · '}{savedPreset?.title}
          <p style={{margin:'6px 0'}}>{savedPreset?.description}</p>
        </div>
        <details open={personaOpen} onToggle={e=>setPersonaOpen(e.currentTarget.open)} style={{margin:'12px 0 18px'}}>
          <summary>改名字与性格{personaDirty?' · 有未保存的修改':''}</summary>
          <fieldset disabled={localEditBlocked} style={{border:0,padding:0,margin:'14px 0'}}>
          <legend style={{fontWeight:650}}>名字与相处方式</legend>
          <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:12,marginTop:10}}>
            <label>宠物称呼（聊天时使用）<input style={{display:'block',width:'100%'}} maxLength={16} readOnly={uncertain||differentPet} value={draft.petName}
              onChange={e=>setDraft({...draft,petName:e.target.value})}/></label>
            <label>希望它怎么称呼你<input style={{display:'block',width:'100%'}} maxLength={16} readOnly={uncertain||differentPet} value={draft.ownerName}
              onChange={e=>setDraft({...draft,ownerName:e.target.value})}/></label>
          </div>
          <label style={{display:'block',marginTop:12}}>选择性格<select disabled={uncertain||differentPet} style={{display:'block',marginTop:4}} value={draft.personality}
            onChange={e=>setDraft({...draft,personality:Number(e.target.value)})}>
            {view.presets.map(p=><option key={p.code} value={p.code}>{p.title}</option>)}
          </select></label>
          <p>{preset?.description}</p>
          <p style={{fontSize:12,opacity:.75}}>影响它日常的小动作和聊天语气。{preset?.label} 属于16种宠物创作参考，不是对你的心理测评。</p>
          <button disabled={blocked||(!personaDirty&&view.persisted)} onClick={()=>void action('save_companion_pet_profile',
            {profile:{...view.profile,personality:draft.personality,petName:draft.petName,ownerName:draft.ownerName}},true)}>保存性格与称呼</button>
          {personaDirty?<><span style={{marginLeft:10}}>尚未保存</span>{' '}<button disabled={busy} onClick={()=>setDraft({...view.profile})}>取消修改</button></>:null}
          </fieldset>
        </details>
        <section aria-label="宠物记忆" style={{borderTop:'1px solid #e2e5e2',paddingTop:14}}>
          <h3 style={{fontSize:15,margin:'0 0 8px'}}>它记住的事</h3>
          <p style={{fontSize:13}}>只记你确认的事，随时能改或删除。先记一件就好，最多8件。</p>
          <label><input type="checkbox" checked={view.profile.memoryEnabled} disabled={blocked||!!editor}
            onChange={e=>void action('save_companion_pet_profile',{profile:{...view.profile,memoryEnabled:e.target.checked}},true,true)}/>{' '}
            我点“开聊”时，使用这些记忆和称呼</label>
          <p style={{fontSize:12,opacity:.75}}>开启后，你确认的称呼和有效记忆会交给当前聊天服务处理。关闭只暂停使用，不删除记忆。</p>
          {!view.profile.memories.length?<p>还没有保存的记忆。</p>:<ul style={{listStyle:'none',padding:0,margin:'12px 0'}}>
            {view.profile.memories.map(m=><li key={m.id} style={{padding:'10px 0',borderBottom:'1px solid #eceeec'}}>
              <div>{m.text}</div><small>{kindLabel[m.kind]} · 确认于 {date(m.createdUtc)} · {m.expiresUtc?
                `${m.expiresUtc<=Date.now()/1000?'已到期，不用于聊天':'有效至 '+date(m.expiresUtc)}`:'保留至你删除'}</small>
              <div style={{display:'flex',gap:8,marginTop:6}}>
                <button disabled={blocked||!!editor} onClick={()=>{setEditor({...m,expiry:'keep'});setConfirm(null);}}>修改</button>
                <button disabled={blocked||!!editor} onClick={()=>setConfirm(m.id)}>删除</button>
              </div>
              {confirm===m.id?<div><p>删除这条记忆？保存后，它不再用于聊天。</p><button disabled={blocked} onClick={()=>void remove(m.id)}>确认删除</button>{' '}
                <button disabled={busy} onClick={()=>setConfirm(null)}>保留</button></div>:null}
            </li>)}
          </ul>}
          {!editor?<div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
            <button disabled={blocked||view.profile.memories.length>=8} onClick={()=>startMemory()}>记住一句</button>
            {transcript?<button disabled={blocked||view.profile.memories.length>=8} onClick={()=>startMemory(transcript)}>把刚才这句核对后保存</button>:null}
            {!!view.profile.memories.length?<button disabled={blocked} onClick={()=>setConfirm(-1)}>清空记忆条目</button>:null}
          </div>:<fieldset disabled={localEditBlocked} style={{border:'1px solid #d8ded8',borderRadius:8,padding:12,marginTop:12}}>
            <legend>{view.profile.memories.some(m=>m.id===editor.id)?'修改这条记忆':'确认一句想让它记住的话'}</legend>
            <textarea style={{width:'100%',minHeight:72}} maxLength={160} readOnly={uncertain||differentPet} value={editor.text} placeholder="例如：和我说话尽量简短。"
              onChange={e=>setEditor({...editor,text:e.target.value})}/>
            <small style={{color:memoryBytes>160?'#ad352b':undefined}}>{memoryBytes>160?'这句话太长了，请简短一点。':'简短一句，最多约50个汉字。'}</small>
            <p style={{fontSize:12}}>修改内容或类型后，保存日期会作为新的确认日期；选择“保留原有效期”时，到期时间不变。</p>
            <div style={{display:'flex',gap:12,flexWrap:'wrap',margin:'8px 0'}}>
              <label>保留多久<select disabled={uncertain||differentPet} value={editor.expiry} onChange={e=>setEditor({...editor,expiry:e.target.value})}>
                {editor.expiry==='keep'?<option value="keep">保留原有效期</option>:null}
                <option value="1">一天</option><option value="7">一周</option><option value="forever">直到我删除</option>
              </select></label>
            </div>
            <details style={{margin:'8px 0'}}><summary>更多选项</summary>
              <label>记忆类型<select disabled={uncertain||differentPet} value={editor.kind} onChange={e=>setEditor({...editor,kind:Number(e.target.value)})}>
                {kindLabel.map((label,i)=><option key={i} value={i}>{label}</option>)}</select></label>
            </details>
            <button disabled={blocked||!memoryBytes||memoryBytes>160} onClick={()=>void saveMemory()}>保存这条记忆</button>{' '}
            <button onClick={()=>{setEditor(null);setError('');}}>取消</button>
          </fieldset>}
          {confirm===-1?<div><p>清空所有记忆条目并暂停聊天使用？性格和称呼会保留。</p>
            <button disabled={blocked} onClick={()=>void clearMemories()}>确认清空记忆</button>{' '}
            <button disabled={busy} onClick={()=>setConfirm(null)}>保留</button></div>:null}
          {view.cleanupPending?<p role="alert">新内容已保存，旧副本还没清理完。<button disabled={blocked}
            onClick={()=>void action('cleanup_companion_pet_profile',{},true,true)}>重试清理旧副本</button></p>:null}
        </section>
        <details style={{marginTop:18}}><summary>更多管理</summary>
          <button disabled={unavailable||busy} onClick={load}>重新读取宠物中的内容</button>
          <p style={{fontSize:12}}>内容保存在宠物里，换电脑后也能读取；录音库不会自动变成记忆。</p>
          <details><summary>重置这只宠物的档案</summary><p>清空称呼与记忆，恢复它的初始性格。录音与原文不受影响。</p>
          {confirm!=='reset'?<button disabled={blocked||!!editor} onClick={()=>setConfirm('reset')}>重置宠物档案</button>:
            <div><p>确认重置当前这只宠物吗？</p><button disabled={blocked} onClick={async()=>{
              if(await action('reset_companion_pet_profile',{uid:view.profile.uid,generation:view.profile.generation,confirmed:true},true))setEditor(null);
            }}>确认重置档案</button>{' '}<button disabled={busy} onClick={()=>setConfirm(null)}>取消</button></div>}
          </details>
        </details>
      </>:null}
    </div>:null}
  </details>;
}
