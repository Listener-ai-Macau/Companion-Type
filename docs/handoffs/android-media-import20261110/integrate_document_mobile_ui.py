from pathlib import Path
import json,os,subprocess,shutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');A=R/'companion-core-android20261109';S=R/'companion-device-closure055'
p=A/'package.json';a=json.loads(p.read_text(encoding='utf-8'));s=json.loads((S/'package.json').read_text(encoding='utf-8'))
for group in ['dependencies','devDependencies']:
    assert all(s[group][name]==version for name,version in a[group].items())
    a[group].update(s[group])
p.write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
lock=json.loads((S/'package-lock.json').read_text(encoding='utf-8'));lock['version']=a['version'];lock['packages']['']['version']=a['version'];lock['packages']['']['dependencies']=a['dependencies'];lock['packages']['']['devDependencies']=a['devDependencies'];(A/'package-lock.json').write_text(json.dumps(lock,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
# Reuse exact installed dependency cache without removing this tree's old inputs.
for name in s['dependencies']:
    target=S/'node_modules'/name;dest=A/'node_modules'/name
    if not dest.exists():
        dest.parent.mkdir(exist_ok=True);subprocess.run(['cmd','/d','/c','mklink','/J',str(dest),str(target.resolve())],check=True,capture_output=True)

p=A/'apps/mobile/src/App.tsx';raw=p.read_bytes();text=raw.decode('utf-8').replace('\r\n','\n')
def change(old,new):
    global text
    assert text.count(old)==1,old[:140];text=text.replace(old,new)
change("import {RecordingNotes,type RecordingNoteList,type RecordingNoteDraft} from './RecordingNotes';","import {RecordingNotes,type RecordingNoteList,type RecordingNoteDraft} from './RecordingNotes';\nimport {DocumentContextPanel} from '../../../packages/ui/src/DocumentContextPanel';\nimport type {ContextDocuments} from '../../../packages/document-context/src/storageTypes';")
change('pickNoteImage?(id:number,args:string):void;','pickNoteImage?(id:number,args:string):void;pickContextDocument?(id:number,args:string):void;')
change('function chooseNoteImage(args:object)', '''function chooseContextDocument(args:object):Promise<ContextDocuments|{cancelled:true}>{if(!window.CompanionNative?.pickContextDocument)return Promise.reject(new Error('请更新Android应用后添加文档。'));return new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});window.CompanionNative!.pickContextDocument!(id,JSON.stringify(args));});}
function chooseNoteImage(args:object)''')
change("const [aiContext,setAiContext]", "const [documentSource,setDocumentSource]=useState<{id:string;quote:string;nonce:string}|undefined>();\n const [aiContext,setAiContext]")
change("if(page!=='detail'||!selected||!detail?.transcript)","if(page!=='detail'||!selected||!detail)")
change("('aiContext').then(value", "('aiContext',{ownerKey:selected.key}).then(value")
change("{detail.transcript&&<><div className=\"ai-workspace-anchor\"", "{(detail.transcript||aiContext?.available.some(scope=>scope.kind==='supplement'))&&<><div className=\"ai-workspace-anchor\"")
needle="/>\u003c/section>}<section className=\"detail-card reading-card\" id=\"detail-panel-transcript\""
panel='''/><DocumentContextPanel key={'document-context:'+selected.key+':'+detail.libraryToken} contextId={selected.key} busy={!!busy||updateRunning} openSource={documentSource} onChanged={()=>setAiContextRetry(v=>v+1)} onNotice={setNotice} adapter={{
 load:()=>call<ContextDocuments>('documentContexts',{key:selected.key}),
 import:async(value,id)=>{const result=await run('请选择补充文档',()=>chooseContextDocument({key:selected.key,libraryToken:value.libraryToken,revision:value.revision,id}),false,true);if(!result)throw Error('原件尚未保存，请重新读取材料核对。');return result;},
 chunk:(value,id,offset)=>call('documentContextChunk',{key:selected.key,libraryToken:value.libraryToken,revision:value.revision,id,offset}),
 read:(value,id)=>call('documentContextRead',{key:selected.key,libraryToken:value.libraryToken,revision:value.revision,id}),
 commit:(value,id,extraction)=>call('documentContextCommit',{key:selected.key,libraryToken:value.libraryToken,revision:value.revision,id,extraction}),
 remove:(value,id)=>call('documentContextRemove',{key:selected.key,libraryToken:value.libraryToken,revision:value.revision,id}),
 saveOriginal:async(value,id)=>{const prepared=await call<{id:string}>('documentContextOriginal',{key:selected.key,libraryToken:value.libraryToken,revision:value.revision,id});return savePrepared(prepared.id);},
 }}/></section>}<section className="detail-card reading-card" id="detail-panel-transcript"'''
change(needle,panel)
change('onOpenSource={async(id,quote)=>{if(id!==selected.key)', '''onOpenSource={async(id,quote)=>{if(id.startsWith('document:')){const split=id.lastIndexOf(':'),owner=id.slice(9,split);if(owner!==selected.key){setError('请先打开材料所属会议。');return;}setDocumentSource({id:id.slice(split+1),quote,nonce:crypto.randomUUID()});selectDetailTab('notes');window.requestAnimationFrame(()=>tabsAnchor.current?.scrollIntoView({block:'start'}));return;}if(id!==selected.key)''')
assert p.read_bytes()==raw;p.write_bytes(text.replace('\n','\r\n' if b'\r\n' in raw else '\n').encode('utf-8'))
print('Shared local document reading panel connected to ordinary Android native picker, original save, owned extraction and explicit source navigation. Native packaging pending.')
