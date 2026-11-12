from pathlib import Path
import subprocess,os,json,sys
r=Path('C:/Users/Billy/Desktop/Denzic/Companion');p=Path('E:/CodexData/Companion/.build-cache/android-media-import20261110/customer-edit142-20261112');o=r/'docs/handoffs/20261110-android-media-import/customer-edit142';a=r/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe'
# The exact recipient is on our logical display40 and shows only the declared
# public export title. Never use screencap's primary/all-display defaults.
state=subprocess.check_output([str(a),'-s','d6bd213d','shell','dumpsys','activity','activities'],text=True);block=next(x for x in state.split('Display #') if x.startswith('40 '));assert 'cn.wps.moffice_eng/cn.wps.moffice.writer.multiactivity.Writer1' in block
log=max((p/'ui-standard').glob('result-*.private.txt'),key=lambda q:q.stat().st_mtime).read_text(encoding='utf-8');nodes=json.loads(next(x for x in log.splitlines() if x.startswith('COMPANION_UI=')).split('=',1)[1])['nodes'];assert any(n.get('id')=='cn.wps.moffice_eng:id/component_title_text' and n.get('text')=='超市交流｜工程需求待收集（公开样例）-人工补充与跟进' for n in nodes)
exe=Path('E:/CodexData/Companion/.build-cache/device-phone055/background-display/scrcpy-win64-v5.0.1/scrcpy.exe');video=p/'public-receiver40.mp4';assert not video.exists()
with (p/'public-receiver-capture.log').open('wb') as stream:
 result=subprocess.run([str(exe),'-s','d6bd213d','--display-id=40','--no-window','--no-audio','--no-clipboard-autosync','--keyboard=disabled','--mouse=disabled','--no-power-on','--max-fps=1','--video-bit-rate=256K','--record='+str(video),'--time-limit=2'],env={**os.environ,'ADB':str(a)},stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,timeout=20)
assert result.returncode==0,(p/'public-receiver-capture.log').read_text(errors='replace')[-1500:]
subprocess.run(['ffmpeg','-v','error','-i',str(video),'-frames:v','1',str(o/'ordinary-wps-receiver.png')],check=True,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
print('Captured only the owned logical display40 showing the public WPS receiver; no primary display/audio/input captured.')
