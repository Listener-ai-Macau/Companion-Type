"""Fsynced model state snapshots with an independently durable prior copy.

Existing crash artifacts are never repaired in place by the reader. This is
an OS-flush/atomic-replace guarantee, not a physical power-loss qualification.
"""
from pathlib import Path
import hashlib
import json
import os
import time
import uuid

def _replace_bytes(path,data):
    path=Path(path);temporary=path.with_name('.durable-'+uuid.uuid4().hex)
    try:
        with temporary.open('xb') as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
        for attempt in range(8):
            try:os.replace(temporary,path);return
            except OSError as error:
                if getattr(error,'winerror',None) not in (5,32,33) or attempt==7:raise
                time.sleep(min(.005*2**attempt,.1))
    finally:
        if temporary.exists():temporary.unlink()

def atomic_json(path,value,*,progress=False):
    """Drop-in writer; progress=True still flushes and propagates failures."""
    path=Path(path);encoded=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    json.loads(encoded)
    if path.exists():
        old=path.read_bytes()
        try:json.loads(old)
        except (ValueError,UnicodeError):
            # A future successful write must not erase the crash evidence.
            corrupt=path.with_name(path.name+'.corrupt-'+hashlib.sha256(old).hexdigest())
            if corrupt.exists():
                if corrupt.read_bytes()!=old:raise ValueError('Corrupt-state archive collision')
            else:_replace_bytes(corrupt,old)
        else:_replace_bytes(path.with_name(path.name+'.previous'),old)
    _replace_bytes(path,encoded)
    return True

def read_snapshot(path):
    """Return the selected data and explicit recovery provenance; no mutation."""
    path=Path(path);errors=[]
    for candidate in [path,path.with_name(path.name+'.previous')]:
        try:
            raw=candidate.read_bytes();value=json.loads(raw)
            return value,{'selectedFile':str(candidate),'sha256':hashlib.sha256(raw).hexdigest(),
                'usedPrevious':candidate!=path,'primaryFailures':errors,
                'originalCorruptBytesPreserved':True}
        except (OSError,ValueError,UnicodeError) as error:errors.append({'file':str(candidate),'error':repr(error)})
    raise ValueError('No valid durable model snapshot: '+json.dumps(errors))
