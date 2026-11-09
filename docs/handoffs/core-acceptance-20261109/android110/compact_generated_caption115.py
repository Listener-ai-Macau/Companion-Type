"""Treat the generated template label as a caption, not another reading card."""
from pathlib import Path
R=Path('C:/Users/Billy/Desktop/Denzic/Companion/companion-core-android20261109')
p=R/'apps/mobile/src/MinutesDocument.tsx';s=p.read_text();old='if(!title)return <div key={index} className="minutes-preamble">'
new="if(!title)return <div key={index} className={/^>\\s*整理视角：[^\\r\\n]+$/.test(section.body.trim())?'minutes-preamble minutes-preamble-generated':'minutes-preamble'}>"
# The exact product-generated single-line label is metadata. Authored introductions
# and other quotes retain the normal reading-card presentation and full text.
new=new.replace('\\\\','\\');assert s.count(old)==1;p.write_text(s.replace(old,new),encoding='utf8')
css='''
#detail-panel-minutes .minutes-preamble-generated .minutes-reading{padding:0;background:none;border:0;box-shadow:none}
#detail-panel-minutes .minutes-preamble-generated .minutes-quote{margin:0 0 8px;padding:0;border:0;font-size:11px;line-height:1.6;color:var(--muted)}
#detail-panel-minutes .minutes-preamble-generated .minutes-gap{display:none}
'''
p=R/'apps/mobile/src/mobilePremium.css';p.write_text(p.read_text()+css,encoding='utf8')
(Path(__file__).parent/'phone-d6/caption115-preview.css').write_text(css,encoding='utf8')
p=R/'apps/android/app/build.gradle';s=p.read_text();assert 'versionCode 114' in s;p.write_text(s.replace('versionCode 114','versionCode 115').replace("versionName '0.1.114'","versionName '0.1.115'"),encoding='utf8')
print('Generated template caption compacted; source text and authored introductions preserved')
