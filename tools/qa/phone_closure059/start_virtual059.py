from pathlib import Path
import json,os,re,subprocess,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
C=Path('E:/CodexData/Companion/.build-cache/device-phone055/acceptance059');C.mkdir(exist_ok=True)
A=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe'
X=Path('E:/CodexData/Companion/.build-cache/device-phone055/background-display/scrcpy-win64-v5.0.1/scrcpy.exe')
serial='6LCAPVHE9PBE45DU'
line=''.join(x for x in (R/'docs/board_operations.md').open(encoding='utf-8-sig') if x.startswith('- **占用中**'))
assert 'Companion第1-2项059控制与公开资料导出验收' in line
def adb(*args):
    p=subprocess.run([str(A),'-s',serial,*args],capture_output=True,text=True,encoding='utf8',errors='replace',timeout=25)
    assert p.returncode==0,p.stderr
    return p.stdout
before=adb('shell','dumpsys','activity','activities')
before_top=[s.strip() for s in before.splitlines() if 'topResumedActivity=' in s]
assert len(before_top)==1
log=C/'virtual-display.log'
args=[str(X),'-s',serial,'--new-display=1080x1920/360','--no-window','--no-audio',
    '--no-clipboard-autosync','--display-ime-policy=local','--keyboard=disabled','--mouse=disabled',
    '--no-power-on','--no-vd-system-decorations','--no-terminal-title','--max-fps=1','--video-bit-rate=128K',
    '--record='+str(C/'virtual-own-app-only.mkv')]
env={**os.environ,'ADB':str(A)}
with log.open('wb') as out:
    p=subprocess.Popen(args,stdout=out,stderr=subprocess.STDOUT,env=env,
        creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
state={'pid':p.pid,'serial':serial,'beforeMainResumed':before_top[0],
    'log':str(log),'recordingOnlyNewVirtualDisplay':True,'audioForwarding':False,
    'clipboardSync':False,'physicalInputForwarding':False}
(C/'virtual-session.json').write_text(json.dumps(state,indent=2),encoding='utf8')
for _ in range(15):
    text=log.read_text(encoding='utf8',errors='replace')
    if p.poll() is not None:raise AssertionError(text)
    if re.search(r'New display.*?(?:id|ID|:).*?\d+',text):break
    time.sleep(1)
print(log.read_text(encoding='utf8',errors='replace')[-2500:])
display=adb('shell','dumpsys','display')
print('\n'.join(s.strip() for s in display.splitlines() if 'DisplayDeviceInfo{' in s and ('scrcpy' in s.lower() or 'Virtual' in s)))
print('\n'.join(s.strip() for s in adb('shell','dumpsys','activity','activities').splitlines() if 'Display #' in s or 'topResumedActivity=' in s or 'mResumedActivity:' in s))
