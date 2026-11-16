import os,sys
if os.environ.get('COMPANION_LOCAL_ARTIFACT_ROOT'):
    try:
        sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
        from companion_local_cache_audit_20261115 import install
        install()
    except BaseException:
        os._exit(78)
