from pathlib import Path
import sys

root=Path('C:/Users/Billy/Desktop/Denzic/Companion/companion-core-android20261109')
path=root/'apps/mobile/src/App.tsx'
text=path.read_text(encoding='utf-8')
if '--finish-route' in sys.argv:
    old="setDetailTab('minutes');}return d;}"
    assert text.count(old)==1
    text=text.replace(old,"setDetailTab('minutes');else setDetailTab('transcript');}return d;}")
    path.write_text(text,encoding='utf-8')
    print('A recording without saved minutes opens its actual transcript/ASR view.')
    raise SystemExit(0)
if '--finish-scope' in sys.argv:
    old='<div className="library-search-scope" role="group"'
    assert text.count(old)==1
    text=text.replace(old,'<div className="library-search-scope" hidden={!query.trim()&&searchScope===\'all\'} role="group"')
    path.write_text(text,encoding='utf-8')
    print('Search scope stays available while typing; ordinary library stays focused on recordings.')
    raise SystemExit(0)
replacements={
    "import './mobilePremium.css';":"import './mobilePremium.css';\nimport './recordingLibrary.css';",
    '<span className="eyebrow">资料库</span><h1>所有录音</h1>':'<h1>我的记录</h1>',
    "{rows.length?`共 ${rows.length} 条录音`:'连接录音卡或导入已有录音，即可开始整理'}":"{rows.length?`共 ${rows.length} 条 · 打开录音可回听、读文字或整理纪要`:'连接录音卡，或导入一段音频'}",
    "title={query.trim()?'搜索结果':'全部录音'}":"title={query.trim()?'搜索结果':'录音库'}",
    '<strong>{row.title}</strong>{row.matchSnippet':'<strong>{recordingName(row)}</strong>{row.matchSnippet',
    "{row.source==='importedAudio'?'文件导入':recordingDate(row.recordedAtUnixSeconds)} · {stateText(row.state)}":"{recordingDate(row.recordedAtUnixSeconds)} · {row.source==='importedAudio'?'导入音频':row.source==='derivedAudio'?'编辑成品':'卡片录音'} · {stateText(row.state)}",
}
for old,new in replacements.items():
    assert text.count(old)==1,old
    text=text.replace(old,new)
start=text.index('<div className="empty"><div className="empty-art"')
end=text.index('}{!readingPreview&&<section className="library-maintenance"',start)
text=text[:start]+'<div className="empty recording-empty"><Headphones size={30} aria-hidden="true"/><strong>还没有录音</strong><p>接上录音卡或导入音频。保存的录音、文字和纪要都会留在这里。</p><button className="primary" disabled={navigationBlocked} onClick={()=>nav(\'devices\')}>连接录音卡</button></div>'+text[end:]
text=text.replace('Settings2, Moon, Sun, Play','Settings2, Moon, Sun, Headphones, Play',1)
anchor='function recordingDate(seconds?:number|null)'
index=text.index(anchor)
helper="function recordingName(row:Row){if(row.title.trim()&&!/^(?:Companion (?:device recording|录音)|设备分段录音|(?:设备|会议)?录音\\s*#?\\d+)$/i.test(row.title.trim()))return row.title;return row.recordedAtUnixSeconds?recordingDate(row.recordedAtUnixSeconds)+' 的录音':row.title||'录音 · 日期未知';}\n"
text=text[:index]+helper+text[index:]
text=text.replace('title={selected.title}>{selected.title}</strong>','title={selected.title}>{recordingName(selected)}</strong>',1)
path.write_text(text,encoding='utf-8')
print('Mobile library structure, honest default naming and date/source identity refined; native backend and saved data untouched.')
