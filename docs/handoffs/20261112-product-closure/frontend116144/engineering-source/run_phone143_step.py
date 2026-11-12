from pathlib import Path
import os,subprocess,sys

root=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261110-android-media-import')
code=sys.argv[2] if len(sys.argv)>2 and sys.argv[1]=='--code' else '143'
assert code in ['143','144']
position=3 if sys.argv[1]=='--code' else 1
step=sys.argv[position];extra=sys.argv[position+1:]
env={**os.environ,'COMPANION_PHONE_QA_CODE':code,'NO_PROXY':'127.0.0.1,localhost,::1','no_proxy':'127.0.0.1,localhost,::1'}
env.pop('COMPANION_PHONE_QA_SESSION',None)
commands={
    'remember':['node',str(root/'software_phone_return.cjs'),'remember-appearance'],
    'restore':['python',str(root/'software_phone_restore.py'),code,*extra],
    'return':['node',str(root/'software_phone_return.cjs')],
    'restart':['python',str(root/'software_phone_session.py'),code,'restart'],
    'close':['python',str(root/'software_phone_session.py'),code,'close'],
    'review':['node',str(Path(__file__).with_name('review_phone143_library.cjs')),*extra],
}
raise SystemExit(subprocess.call(commands[step],env=env))
