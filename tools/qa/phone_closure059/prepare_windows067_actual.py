from pathlib import Path
import hashlib,json,subprocess
W=Path(__file__).parent
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
P=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12'
G=P/'windows067-literal-and-rendering'
v=json.loads((G/'windows-verification.json').read_text(encoding='utf8'))
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=S,text=True).strip()==v['sourceCommit']
p=S/'apps/windows/src-tauri/Cargo.toml'
expected=subprocess.check_output(['git','show',v['sourceCommit']+':apps/windows/src-tauri/Cargo.toml'],cwd=S)
actual=p.read_bytes();assert actual.replace(b'\r\n',b'\n')==expected.replace(b'\r\n',b'\n')
if actual!=expected:
 (G/'bundler-Cargo-after.toml').write_bytes(actual);p.write_bytes(expected)
assert not subprocess.check_output(['git','status','--porcelain'],cwd=S).strip()
text=(W/'install_windows060_verified.py').read_text(encoding='utf8')
text=text.replace('frozen060 Word repair','frozen067 content fidelity and render repair').replace('windows060-word062','windows067-literal-and-rendering').replace('upgrade060-private-','upgrade067-private-').replace("'candidateVersion':'0.1.60','previousInstalledVersion':'0.1.52'","'candidateVersion':'0.1.67','previousInstalledVersion':'0.1.60'").replace('WINDOWS060_INSTALLED','WINDOWS067_INSTALLED')
(W/'install_windows067_verified.py').write_text(text,encoding='utf8')
text=(W/'windows060_system_session.py').read_text(encoding='utf8')
text=text.replace("F=P/'windows060-system-handoff'","F=P/'windows067-literal-and-rendering/system-handoff'").replace("F.mkdir(exist_ok=True)","F.mkdir(parents=True,exist_ok=True)")
text=text.replace('system-handoff060-','system-handoff067-').replace('windows060-word062/installation.json','windows067-literal-and-rendering/installation.json').replace('time.monotonic()+1200','time.monotonic()+2400')
text=text.replace("\n# literal **keep**", "\n# literal **keep**")
(W/'windows067_system_session.py').write_text(text,encoding='utf8')
text=(W/'windows060_system_native.py').read_text(encoding='utf8').replace('windows060-system-handoff','windows067-literal-and-rendering/system-handoff').replace('Windows060-public-','Windows067-public-')
(W/'windows067_system_native.py').write_text(text,encoding='utf8')
text=(W/'windows060_literal_baseline.py').read_text(encoding='utf8')
text=text.replace("out=F/'baseline-native'", "out=F.parent/'windows067-literal-and-rendering/release-native'")
text=text.replace("exe=Path(m['exe'])", "exe=Path('C:/Program Files/Companion Type/companion-type.exe'); v=json.loads((F.parent/'windows067-literal-and-rendering/windows-verification.json').read_text(encoding='utf8')); m['expectedExeSha256']=v['embeddedExeSha256']")
start=text.index("actual=C/'saved/");end=text.index("rows=json.loads",start);text=text[:start]+text[end:]
text=text.replace("receipt=F/'baseline-native-progress.json'", "receipt=out/'progress.json'").replace("(F/'baseline-native-progress.json')", "(out/'progress.json')")
text=text.replace('baseline-','release067-')
(W/'windows067_release_native.py').write_text(text,encoding='utf8')
print('Prepared installed067 protection and scoped actual UI drivers; source exact after bundling.')
