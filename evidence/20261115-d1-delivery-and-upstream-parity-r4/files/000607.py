from pathlib import Path
from datetime import datetime
import json,os,socket,subprocess,sys,time
import psutil
E=Path('E:/CodexData/Companion/product-d1d2-20261114');OUT=E/'app-candidate-r5';QA=OUT/'qa/hidden-delivery-r1';P=OUT/'review-library';QA.mkdir()
sys.path.insert(0,'C:/Users/Billy/Desktop/Denzic/Companion/model-research/src')
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from companion_windows_power_request_20261115 import PowerLease
from practical_io_20261107 import stop_owned_family
port=19338
with socket.socket() as check:check.bind(('127.0.0.1',port))
assert json.loads((OUT/'qa/speaker-review-portability-r1/result.json').read_text(encoding='utf-8'))['state'].startswith('PASS_')
assert not (QA/'gui-process.json').exists()
env={**os.environ,'COMPANION_TYPE_STATE_PATH':str(P/'sessions.json'),'COMPANION_TYPE_RECORDING_DIR':str(P/'recordings'),
 'COMPANION_TYPE_PRODUCT_SETTINGS_PATH':str(P/'settings.json'),'COMPANION_TYPE_LOCAL_MEETING_CONFIG':str(E/'local-package-r8/package.json'),
 'COMPANION_TYPE_ASR_PROVIDER':'local-meeting','COMPANION_TYPE_BACKGROUND_WINDOW':'1',
 'COMPANION_TYPE_DISABLE_AUTO_RECONNECT':'1','COMPANION_TYPE_DISABLE_AUTO_RECOVERY':'1',
 'WEBVIEW2_USER_DATA_FOLDER':str(P/'webview'),
 'COMPANION_TYPE_WEBVIEW_ARGS':f'--remote-debugging-address=127.0.0.1 --remote-debugging-port={port} --disable-background-timer-throttling'}
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);pressure=SystemRamPressure();child=None
state={'state':'STARTING_OWN_HIDDEN_NATIVE_UI','port':port,'startedAt':datetime.now().astimezone().isoformat(),
       'nativeWindowVisible':False,'automaticRecoveryDisabled':True,'deviceReconnectDisabled':True,'qualityQualified':False}
save=lambda:(QA/'gui-process.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
started=time.monotonic()
with PowerLease():
    try:
        with (QA/'gui-console.log').open('xb') as log:
            child=subprocess.Popen([str(OUT/'companion-type.exe')],env=env,cwd=OUT,stdout=log,stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            owned=psutil.Process(child.pid);state.update(state='RUNNING_OWN_HIDDEN_NATIVE_UI',pid=child.pid,pidCreatedAt=owned.create_time());save()
            while child.poll() is None and not (QA/'gui-stop.request').exists():
                assert not pressure.low(),'Actual Windows low-memory signal'
                assert time.monotonic()-started<240,'Bounded hidden app inspection'
                import ctypes
                user=ctypes.WinDLL('user32',use_last_error=True)
                callback=ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_void_p,ctypes.c_void_p)
                def hide_owned_event_target(hwnd,_):
                    pid=ctypes.c_ulong();user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
                    if pid.value==child.pid:
                        title=ctypes.create_unicode_buffer(256);user.GetWindowTextW(hwnd,title,256)
                        if title.value=='Tao Thread Event Target':user.ShowWindow(hwnd,0)
                    return True
                user.EnumWindows(callback(hide_owned_event_target),0)
                time.sleep(.5)
    finally:
        if child is not None and child.poll() is None:stop_owned_family(child,psutil.Process(child.pid))
        pressure.close();state.update(state='OWN_HIDDEN_NATIVE_UI_CLOSED',finishedAt=datetime.now().astimezone().isoformat(),
            seconds=time.monotonic()-started,limits=limits.query());save()
print(json.dumps(state,ensure_ascii=False))
