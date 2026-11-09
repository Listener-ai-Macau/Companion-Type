from pathlib import Path
import sys
code=int(sys.argv[1]) if len(sys.argv)>1 else 111;assert code in [111,112,113,114,115]
source=(Path(__file__).parent/'backup_unified_android.py').read_text(encoding='utf8')
for before,after in [('android110','android'+str(code)),('Android110','Android'+str(code)),('ANDROID110','ANDROID'+str(code))]:source=source.replace(before,after)
source=source.replace('UNIFIED_SOURCE_SIGNED_PAYLOAD_VERIFIED_PHONE_PENDING','CI_PAYLOAD_TRUSTED_SIGNER_AND_MODEL_RESOURCES_VERIFIED')
exec(compile(source,str(Path(__file__).parent/'backup_unified_android.py'),'exec'))
