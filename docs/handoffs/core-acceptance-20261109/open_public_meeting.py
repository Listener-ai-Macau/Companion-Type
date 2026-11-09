"""Owner-clicked entry for the actual public meeting, separate from daily data."""
from pathlib import Path
import ctypes,json,os,subprocess,sys
ROOT=Path('E:/CodexData/Companion/.build-cache/core-acceptance20261109/whole-805278e2b7214018a4ddef74e361a9e8')
APP=Path('C:/Program Files/Companion Type/companion-type.exe')
def main():
 try:
  rows=json.loads((ROOT/'sessions.json').read_text(encoding='utf8'))
  assert len(rows)==1 and rows[0]['id']=='import-00817de5e4dc4f55b9119da5a170fcaa'
  assert APP.is_file() and Path(rows[0]['audioPath']).is_file()
  assert all(Path(c['path']).is_file() for c in rows[0]['chunks'])
  if '--check-only' in sys.argv:
   print(json.dumps({'publicMeetingReady':True,'dailyLibraryOpened':False,'appStarted':False}));return
  for name in ['preview-roaming','preview-local','preview-webview','preview-temp']:(ROOT/name).mkdir(exist_ok=True)
  env={**os.environ,'APPDATA':str(ROOT/'preview-roaming'),'LOCALAPPDATA':str(ROOT/'preview-local'),
   'TEMP':str(ROOT/'preview-temp'),'TMP':str(ROOT/'preview-temp'),
   'COMPANION_TYPE_STATE_PATH':str(ROOT/'sessions.json'),'COMPANION_TYPE_RECORDING_DIR':str(ROOT/'recordings'),
   'COMPANION_TYPE_PRODUCT_SETTINGS_PATH':str(ROOT/'preview-settings.json'),
   'COMPANION_TYPE_DISABLE_AUTO_RECOVERY':'1','COMPANION_TYPE_DISABLE_AUTO_RECONNECT':'1',
   'WEBVIEW2_USER_DATA_FOLDER':str(ROOT/'preview-webview'),
   'COMPANION_TYPE_LOCAL_ASR_DIR':str(Path(os.environ['APPDATA'])/'Companion Type/models/local-asr')}
  env.pop('COMPANION_TYPE_BACKGROUND_WINDOW',None);env.pop('COMPANION_TYPE_WEBVIEW_ARGS',None)
  subprocess.Popen([str(APP)],cwd=APP.parent,env=env,creationflags=subprocess.CREATE_NO_WINDOW)
 except Exception:
  if '--check-only' in sys.argv:raise
  ctypes.windll.user32.MessageBoxW(None,'公开会议验收资料暂不可用。请按本批已保存收据恢复公开样例；原有日用资料库未改动。','Companion 公开会议入口',0x10)
if __name__=='__main__':main()
