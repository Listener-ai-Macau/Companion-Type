"""Resume only the specifically proven interrupted receipt-publication failure."""
from pathlib import Path
import ast,hashlib,json
from practical_io_20261107 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';C=R/'docs/handoffs/20261108-dual-mic-independent-meetings/oracle-activity-control';read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
old=S/'run_independent_oracle_gss_recovery_20261108.py';new=S/'run_independent_oracle_gss_artifact_recovery_20261108.py';text=old.read_text(encoding='utf8')
text=text.replace("parser.add_argument('--resume-after-observer-fix',action='store_true');args=parser.parse_args()","parser.add_argument('--resume-after-observer-fix',action='store_true');parser.add_argument('--resume-after-orphan-repair',action='store_true');args=parser.parse_args()")
needle="    else:\n        assert args.resume_after_observer_fix";assert text.count(needle)==1
text=text.replace(needle,"""    elif old['state']=='FAILED_PS4_COMPONENT_RETAINED_NO_AUTOMATIC_RETRY':
        assert args.resume_after_orphan_repair and read(C/'orphan-pcm-repair.json')['state']=='PASS_EXISTING_ORPHAN_MONO_PCM_EXACT_FROZEN_INPUTS_RECEIPT_RECOVERED'
        failed=read(C/'separation-state-r2.json');assert failed['state']=='FAILED_DUAL_MIC_REFERENCE_STAGE_RETAINED' and 'assert not dest.exists()' in failed['traceback']
        assert not pressure.low()
    else:
        assert args.resume_after_observer_fix""")
text=text.replace('else:assert not args.resume_after_low_ram and not args.resume_after_observer_fix','else:assert not args.resume_after_low_ram and not args.resume_after_observer_fix and not args.resume_after_orphan_repair')
ast.parse(text);assert not new.exists();new.write_text(text,encoding='utf8')
atomic_json(C/'artifact-recovery-source.json',{'state':'SOURCE_FIXED_OBSERVER_AND_EXACT_PCM_ARTIFACT_RECOVERY_ONLY','controller':str(new),'controllerSha256':hashlib.sha256(new.read_bytes()).hexdigest(),'failedRunSha256':hashlib.sha256((C/'run-r2.json').read_bytes()).hexdigest(),'acousticWorkerAndProtocolUnmodified':True,'orphanOriginalPcmPreserved':True,'newModelParameters':0,'modelErrorRetryAllowed':False})
