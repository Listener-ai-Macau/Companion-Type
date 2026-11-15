"""A transiently locked progress file must not terminate a valid owned worker.

Only for observation. Configuration and final acceptance receipts stay strict.
The controller's existing no-progress deadline still applies to cached samples.
"""
from pathlib import Path
import json,os
def read_progress(path,previous):
    try:return json.loads(Path(path).read_text(encoding='utf8')),None
    except FileNotFoundError:return previous,'not_yet_published'
    except OSError as error:
        if os.name!='nt' or (getattr(error,'winerror',None) not in (5,32,33) and error.errno!=13):raise
        return previous,'transient_windows_share_lock'
