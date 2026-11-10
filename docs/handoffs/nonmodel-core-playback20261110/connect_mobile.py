from pathlib import Path
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/companion-core-android20261109')
p=S/'apps/mobile/src/App.tsx';t=p.read_text(encoding='utf8')
def replace(old,new):
 global t
 assert t.count(old)==1,old[:100]
 t=t.replace(old,new)
replace("import {MobileActionCards} from './MobileActionCards';","import {MobileActionCards} from './MobileActionCards';\nimport {PlaybackTools} from './PlaybackTools';")
replace('type Detail={lifecycle?:','type Detail={playback?:{positionMs:number;speed:number;completed:boolean;saved:boolean;warning?:string;sourceChanged?:boolean};lifecycle?:')
replace("const [playing,setPlaying]=useState(false);", "const [playbackSpeed,setPlaybackSpeed]=useState(1);const [playing,setPlaying]=useState(false);")
replace("async function open(row:Row){if(operationActive.current)return;", "async function open(row:Row){if(operationActive.current)return;if(playing||paused)void call('stopPlayback').catch(()=>{});playbackEpoch.current++;window.clearTimeout(seekTimer.current);seekTimer.current=undefined;seekTarget.current=null;setPlaying(false);setPaused(false);setPosition(0);setDuration(row.durationMs??0);setPlaybackSpeed(1);")
replace('if(d){setDetail(d);setDraft(d.transcript);', 'if(d){setPosition(d.playback?.positionMs??0);setPlaybackSpeed(d.playback?.speed??1);if(d.playback?.warning)setNotice(d.playback.warning);setDetail(d);setDraft(d.transcript);')
replace("call<{playing:boolean;paused?:boolean;positionMs?:number}>('playbackStatus')","call<{playing:boolean;paused?:boolean;positionMs?:number;speed?:number;key?:string;saveWarning?:string}>('playbackStatus')")
replace('if(epoch!==playbackEpoch.current)return;if(s.positionMs', 'if(epoch!==playbackEpoch.current||s.key&&s.key!==selected?.key)return;if(s.speed)setPlaybackSpeed(s.speed);if(s.saveWarning)setNotice(s.saveWarning);if(s.positionMs')
replace('},[playing]);', '},[playing,selected?.key]);')
replace("const result=await call<{complete:boolean;durationMs:number}>('play',{key:selected.key});setDuration(result.durationMs);setPosition(0);", "const result=await call<{complete:boolean;durationMs:number;positionMs:number;speed:number}>('play',{key:selected.key,libraryToken:detail?.libraryToken});setDuration(result.durationMs);setPosition(result.positionMs);setPlaybackSpeed(result.speed);")
replace("const exportDeviceMarks=()=>", """const seekByControls=(target:number)=>void run('正在定位回听',async()=>{if(!selected)return;await flushSeek();const epoch=++playbackEpoch.current;const result=await call<{positionMs:number}>('seekPlayback',{key:selected.key,libraryToken:detail?.libraryToken,positionMs:target});if(epoch===playbackEpoch.current)setPosition(result.positionMs);});
 const changePlaybackSpeed=(speed:number)=>void run('正在调整回听速度',async()=>{if(!selected)return;await flushSeek();const result=await call<{speed:number}>('setPlaybackSpeed',{key:selected.key,libraryToken:detail?.libraryToken,speed});setPlaybackSpeed(result.speed);});
 const restartPlayback=()=>void run('正在从头回听',async()=>{if(!selected)return;playbackEpoch.current++;window.clearTimeout(seekTimer.current);seekTimer.current=undefined;seekTarget.current=null;const result=await call<{complete:boolean;durationMs:number;positionMs:number;speed:number}>('play',{key:selected.key,libraryToken:detail?.libraryToken,restart:true});setDuration(result.durationMs);setPosition(result.positionMs);setPlaybackSpeed(result.speed);setPlaying(true);setPaused(false);});
 const exportDeviceMarks=()=>""")
replace("'从本机回听'", "position>0?`从 ${clock(position)} 继续`:'从本机回听'")
replace("{(playing||paused)&&<div className=\"playback\">", "{(playing||paused)&&<div className=\"playback\">") # Assert the original seek control remains present.
replace('</div></div>}</section>}{!readingPreview&&<div className="meeting-audio-tools">', '</div></div>}<PlaybackTools active={playing||paused} disabled={!!busy||updateRunning} position={position} duration={duration} speed={playbackSpeed} onSeek={seekByControls} onSpeed={changePlaybackSpeed} onRestart={restartPlayback}/></section>}{!readingPreview&&<div className="meeting-audio-tools">')
p.write_text(t,encoding='utf8')
print('Connected native continued playback, explicit jumps and rate controls without changing transcription or minutes.')
