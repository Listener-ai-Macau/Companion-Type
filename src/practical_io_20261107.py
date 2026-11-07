"""Windows-safe publication; an observer must not abort neural inference."""
from pathlib import Path
import json,os,time,uuid

def atomic_json(path,value,*,progress=False):
    path=Path(path);temp=path.parent/('.tmp-'+uuid.uuid4().hex)
    try:
        with temp.open('xb') as stream:
            stream.write((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf8'));stream.flush()
            if not progress:os.fsync(stream.fileno())
        for attempt in range(8):
            try:os.replace(temp,path);return True
            except OSError as error:
                if getattr(error,'winerror',None) not in (5,32,33) or attempt==7:raise
                time.sleep(min(.005*2**attempt,.1))
    except OSError:
        if not progress:raise
        return False
    finally:
        if temp.exists():
            try:temp.unlink()
            except OSError:pass

def stop_owned_family(child,root):
    """Only a still-running Popen and its verified descendants; no name kill."""
    import psutil,subprocess
    if child is None or child.poll() is not None:return False
    assert root.pid==child.pid and root.is_running()
    try:owned=root.children(recursive=True)+[root]
    except psutil.NoSuchProcess:owned=[]
    for member in reversed(owned):
        try:member.terminate()
        except psutil.NoSuchProcess:pass
    psutil.wait_procs(owned,timeout=2)
    try:child.wait(timeout=3)
    except subprocess.TimeoutExpired:child.kill();child.wait(timeout=3)
    return True
