from pathlib import Path
A=Path('C:/Users/Billy/Desktop/Denzic/Companion/companion-core-android20261109')
p=A/'apps/mobile/src/App.tsx';t=p.read_text(encoding='utf8')
def change(old,new):
 global t
 assert t.count(old)==1,(old[:120],t.count(old));t=t.replace(old,new)
change("import {TranscriptReplace} from './TranscriptReplace';","import {TranscriptReplace} from './TranscriptReplace';\nimport {CommonSettings,type AppPreferences} from './CommonSettings';\nimport {readAppearance,resolvedAppearance,type Appearance} from './appearance';")
change('openBluetoothSettings():void;','openBluetoothSettings():void;openAppSettings?():void;')
change('companionBack:()=>void;','companionSystemAppearance?:(dark:boolean)=>void; companionBack:()=>void;')
old=next(s for s in t.splitlines() if 'const [theme,setTheme]' in s)
change(old,""" const [appearance,setAppearance]=useState<Appearance>(()=>readAppearance(localStorage));
 const [systemDark,setSystemDark]=useState(()=>window.matchMedia?.('(prefers-color-scheme: dark)').matches??false);
 const theme=resolvedAppearance(appearance,systemDark);
 const [preferences,setPreferences]=useState<AppPreferences|null>(null),[preferencesError,setPreferencesError]=useState(''),[aiSettingsDirty,setAiSettingsDirty]=useState(false);
 const preferenceRead=useRef(0);
 async function loadPreferences(){const generation=++preferenceRead.current;try{const value=await call<AppPreferences>('appPreferences');if(generation!==preferenceRead.current)return;setPreferences(value);setSystemDark(value.systemDark);setPreferencesError('');}catch{if(generation===preferenceRead.current)setPreferencesError('手机设置尚未读取，请重新读取；已有录音仍保留。');}}
 useEffect(()=>{if(readingPreview)return;void loadPreferences();window.companionSystemAppearance=dark=>{setSystemDark(dark);void loadPreferences();};return()=>{preferenceRead.current++;delete window.companionSystemAppearance;};},[]);
 useEffect(()=>{if(window.CompanionNative)return;const media=window.matchMedia?.('(prefers-color-scheme: dark)');const changed=()=>setSystemDark(media?.matches??false);media?.addEventListener?.('change',changed);return()=>media?.removeEventListener?.('change',changed);},[]);
 function chooseAppearance(value:Appearance){setAppearance(value);try{localStorage.setItem('companion-appearance',value);setNotice('外观设置已保存。');}catch{setNotice('外观已应用，本次未能保存；下次打开可能需要重新选择。');}}
 async function savePreferences(value:Partial<Pick<AppPreferences,'defaultPlaybackSpeed'|'resumePlayback'>>){const result=await run('正在保存设置',()=>call<AppPreferences>('saveAppPreferences',value));if(!result)throw Error('尚未确认设置保存。');preferenceRead.current++;setPreferences(result);setSystemDark(result.systemDark);setPreferencesError('');setNotice('设置已保存在这台手机。');}""")
change("if((templatePending||(editing&&draft!==detail?.transcript)","if((aiSettingsDirty||templatePending||(editing&&draft!==detail?.transcript)")
change("onClick={()=>{const next=theme==='dark'?'light':'dark';setTheme(next);try{localStorage.setItem('companion-theme',next);}catch{}}}","onClick={()=>chooseAppearance(theme==='dark'?'light':'dark')}")
start=t.index(" {page==='settings'&&<>");end=t.index(' </main>',start);section=t[start:end]
section=section.replace('<span className="eyebrow">服务与隐私</span>','<span className="eyebrow">你的 Companion</span>')
intro='<p className="intro">生成时会将当前录音的标题和转写文字发送到所选服务，可能产生费用。不会发送音频。生成内容和待办需要核对。</p>'
assert intro in section
section=section.replace(intro,'<p className="intro">调整回听与外观，让每次整理更顺手。</p><CommonSettings appearance={appearance} preferences={preferences} busy={!!busy} error={preferencesError} onAppearance={chooseAppearance} onChange={savePreferences} onRetry={()=>void loadPreferences()} onPermissions={()=>window.CompanionNative?.permissions()} onSystemSettings={()=>window.CompanionNative?.openAppSettings?.()}/><details className="settings-ai-group"><summary><span>AI 服务</span><small>{aiService.configured?\'已配置 · 展开管理\':\'纪要、问答与翻译\'}</small></summary>')
old="onReturn={()=>{if(settingsTarget){setPage('detail');setDetailTab('minutes');}else nav('library');}}/>"
assert old in section
section=section.replace(old,"onDirtyChange={setAiSettingsDirty} returnLabel={settingsTarget?'返回会议':'返回录音库'} onReturn={()=>nav(settingsTarget?'detail':'library')}/></details>")
t=t[:start]+section+t[end:];p.write_text(t,encoding='utf8')
p=A/'apps/mobile/src/commonSettings.css';p.write_text(p.read_text().replace('var(--text)','var(--ink)'))
p=A/'apps/android/app/build.gradle';s=p.read_text();assert 'versionCode 120' in s;s=s.replace('versionCode 120','versionCode 121').replace("versionName '0.1.120'","versionName '0.1.121'");p.write_text(s)
p=A/'tools/qa/core_acceptance20261109/ui_source.cjs';s=p.read_text();s=s.replace("'test_transcript_replace']","'test_transcript_replace','test_common_settings']");p.write_text(s)
print('Grouped settings UI wired to durable native preferences; source only, not installed.')
