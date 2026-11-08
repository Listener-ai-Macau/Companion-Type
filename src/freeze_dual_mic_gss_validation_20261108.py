"""Freeze one bounded spatial/codec hypothesis, not a parameter search."""
from pathlib import Path
from datetime import datetime
import ast,hashlib,json
from practical_io_20261107 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
B=R/'docs/handoffs/20261107-model-generation-recovery';C=R/'docs/handoffs/20261108-dual-mic-real-meeting-validation'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert not (C/'protocol-r2.json').exists()
old=B/'practical-conditioned-ps4-full-r1';oldP=read(old/'protocol-r2.json');original=S/'practical_ps4_full_worker_20261107.py';assert sha(original)==oldP['workerSourceSha256']
text=original.read_text(encoding='utf8').replace(str(old).replace('\\','/'),str(C).replace('\\','/'))
text=text.replace("choices=['separation','asr']","choices=['asr']")
begin=text.index("    if args.stage=='separation':");end=text.index("    else:\n        assert read(C/'separation-state-r2.json')",begin)
text=text[:begin]+"    if args.stage=='asr':\n"+text[end+len('    else:\n'):]
text=text.replace("P['workerSourceSha256']","P['asrWorkerSourceSha256']")
text=text.replace('COMPLETE_PS4_SEPARATION_UNQUALIFIED','COMPLETE_GUIDED_DUAL_MIC_SEPARATION_NOT_PRODUCT')
text=text.replace("            if not case['voiceIdentity']['targetIsTop1']:continue\n",'')
text=text.replace("result={**case,'text':","result={**case,'binding':binding,'text':")
text=text.replace("'COMPLETE_PS4_'+args.stage.upper()+'_UNQUALIFIED'","'COMPLETE_DUAL_MIC_FIXED_ASR_NOT_PRODUCT'")
needle='            def infer(lo,hi):'
assert text.count(needle)==1
text=text.replace(needle,"""            same=next((r for r in outputs if r['audioSha256']==case['audioSha256']),None)
            if same is not None:
                result={**case,'binding':binding,'text':same['text'],'acceptedLeaves':same['acceptedLeaves'],'sameAudioReuseSource':same['id'],'newAsrCallsForThisLane':0}
                atomic_json(folder/'completed.json',result);outputs.append(result);state['reusedOutputs']+=1;state['completedInputs']+=1;save();continue
"""+needle)
def infer_ast(value):return ast.dump(next(n for n in ast.walk(ast.parse(value)) if isinstance(n,ast.FunctionDef) and n.name=='infer'),include_attributes=False)
assert infer_ast(text)==infer_ast(original.read_text(encoding='utf8'))
worker=S/'dual_mic_gss_asr_worker_20261108.py';assert not worker.exists();worker.write_text(text,encoding='utf8')
controller=(S/'run_practical_ps4_full_20261107.py').read_text(encoding='utf8')
controller=controller.replace(str(old).replace('\\','/'),str(C).replace('\\','/'))
start=controller.index('stages=[');end=controller.index('\ntry:',start)
controller=controller[:start]+"""stages=[('separation','dual_mic_gss_worker_20261108.py',[],C/'separation-state-r2.json','COMPLETE_GUIDED_DUAL_MIC_SEPARATION_NOT_PRODUCT'),
    ('inventory','practical_qwen_native_worker_20261107.py',['--control',str(C),'--inventory-only'],C/'hip-inventory.json','PASS_CURRENT_HIP_DEVICE_INVENTORY_NO_MODEL'),
    ('asr','dual_mic_gss_asr_worker_20261108.py',['--stage','asr'],C/'asr-state-r2.json','COMPLETE_DUAL_MIC_FIXED_ASR_NOT_PRODUCT')]
"""+controller[end:]
controller=controller.replace("if stage!='inventory':env['HIP_VISIBLE_DEVICES']","if stage=='asr':env['HIP_VISIBLE_DEVICES']")
controller=controller.replace("command=[PY,str(Path(__file__).with_name(module)),*extra]","command=[('E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe' if stage=='separation' else PY),str(Path(__file__).with_name(module)),*extra]")
old_guard=next(l for l in controller.splitlines() if 'assert not any(Path(a).name in' in l)
controller=controller.replace(old_guard,"        assert not any(str(a).replace('\\\\','/').lower().startswith(str(Path(__file__).parent).replace('\\\\','/').lower()+'/') and '_worker_' in Path(str(a)).name for a in member.info['cmdline'] or []),'Another owned model/spatial stage runs'")
controller=controller.replace('COMPLETE_TARGET_SEPARATION_AND_ASR_REVIEW_REQUIRED','COMPLETE_DUAL_MIC_SPATIAL_CODEC_SCREEN_REVIEW_REQUIRED')
launcher=S/'run_dual_mic_gss_validation_20261108.py';assert not launcher.exists();ast.parse(controller);launcher.write_text(controller,encoding='utf8')
(C/'model-ready.json').write_bytes((old/'model-ready.json').read_bytes());atomic_json(C/'seed-manifest.json',{})
helpers=['companion_gss_numpy_backend_20261108.py']
source_files=[C/'audio-only.json',C/'numpy-backend.json',C/'numpy-numerical-proof.json',S/'dual_mic_gss_worker_20261108.py',S/'companion_gss_numpy_backend_20261108.py']
P={**oldP,'at':datetime.now().astimezone().isoformat(timespec='seconds'),
    'state':'FROZEN_REAL_MEETING_PREDICTED_ACTIVITY_SPATIAL_AND_CODEC_SCREEN',
    'workerSourceSha256':sha(S/'dual_mic_gss_worker_20261108.py'),'asrWorkerSourceSha256':sha(worker),
    'audioOnlySha256':sha(C/'audio-only.json'),'modelReadySha256':sha(C/'model-ready.json'),
    'sourceFiles':[{'file':str(p),'sha256':sha(p)} for p in source_files],
    'algorithm':'PinnedGSS10fad18 native equations via explicit validated NumPy CPU backend;1024Blackman/256hop/fullfade,20GSSiterations+1post,15scontext eachside,noiseclass,referencechannel0fixed,MVDRSouden+BAN,WPEoff,postfilterNone. No algorithm/iteration/channel-pair search.',
    'conditions':['mono_activity: originalchannel0 plus fixed predicted activity gate','dual_pcm: originalchannels0/1 GSS plus same gate','dual_opus: host32kbpsstereoOpus decodedPCM GSS plus same gate'],
    'activity':'Existing full nativeFP16 diarization only. The identical predicted lexical-segment sample mask is applied to every overlap arm, including the mono baseline, after spatial processing. This is a bounded segmentation-controlled research screen, not a new production hard-gating policy; all missed words outside the prediction are charged. No reference/oracle activities or words enter processing.',
    'ordinary':'Sroot1 bypasses gate/GSS, rawmono and rawdualPCM are byte-identical; compressed first channel is separately recognized. Same-audio recognition is reused within this run.',
    'recognition':'Exact prior native1.7B inference AST, same512tokens/BF16/greedy/Chinese/no-context/bounded recovery. All raw generations retained; no filler, duplication or reference-word filtering.',
    'primaryComparison':'Score every person/root with fixed whole-meeting identity mapping and midpoint-in-clip reference. Compare new rawdual versus mono_activity to assess added spatial processing under matched predicted gating; also report previous singlemicPS4cached6lanes. The new mono baseline is not a claim about best possible single-mic neural separation. Codec effect is rawdual versus decodedOpusdual under identical GSS/settings.',
    'retention':'No default promotion from this exposed90s/one Mandarin corpus screen. Require lower total overlap edits without hiding per-person omissions and ordinary raw-path regression; any failure stops full expansion and parameter/codec sweeps. Report codec loss and true triple separately; geometry differs from current device.',
    'qualityQualified':False,'finalHoldoutOpened':False,'asrInferenceAstMatchesOriginal':True,
    'scope':'Local pipeline feasibility, not fullCER<5%, pure-overlapCER, current-card dual-mic performance, Android deployment or sale qualification.'}
atomic_json(C/'protocol-r2.json',P)
atomic_json(C/'protocol-summary.json',{'state':P['state'],'roots':['L12','L27','S1'],'conditions':3,'expectedOutputRows':21,'newSeparationAlgorithms':1,'newModelFamilies':0,'trainingRuns':0,'asrInferenceAstMatchesOriginal':True,'referenceActivityUsed':False,'protocolSha256':sha(C/'protocol-r2.json')})
print(json.dumps(read(C/'protocol-summary.json')),flush=True)
