"""Keep both full native-verbatim results and reattribute with zero ASR inference."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,shutil,subprocess,sys,time
from practical_io_20261107 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');base=R/'docs/handoffs/20261107-model-generation-recovery';C=base/'practical-verbatim-r1';native=base/'native8-f16-full-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
run=read(C/'transcript-run.json');assert run['state']=='TWO_COMPLETE_TEXT_ONLY_MEETINGS_SCORED_SPEAKERS_PENDING'
assert read(C/'cache-binding-proof.json')['state']=='PASS_DEFAULT_CACHE_COMPATIBILITY_AND_CHANGED_ITN_REFUSAL_NO_MODEL'
assert not (C/'review.json').exists()
protocol=read(C/'asr-protocol.json');assert protocol['useItn'] is False and protocol['speakerJournals']=={}
shutil.copyfile(C/'asr-protocol.json',C/'asr-protocol-text-only-original.json')
for case in read(C/'audio-only.json'):
    name=case['meeting'];out=C/'results'/name;out.mkdir(parents=True,exist_ok=False)
    for filename in ['speaker-journal.json','predicted.rttm','completed-state.json','review.json']:shutil.copyfile(native/'results'/name/filename,out/filename)
    producer=read(out/'completed-state.json');assert producer['audioSha256']==case['audioSha256'] and sha(out/'predicted.rttm')==producer['rttmSha256']
    protocol['speakerJournals'][name]=sha(out/'speaker-journal.json')
atomic_json(C/'asr-protocol.json',protocol)
checker=Path('E:/CodexData/Companion/.build-cache/practical-model-contract-20261107/x86_64-pc-windows-msvc/debug/companion-model-output-contract-check.exe')
assert sha(R/'companion-device-closure055/packages/meeting-transcript/src/lib.rs')=='f8f5b87017ebf10616b93d36520bab388f7e63033187bc289dfa1034b3af1684'
rows=[]
for index,case in enumerate(read(C/'audio-only.json')):
    name=case['meeting'];out=C/'transcripts'/name
    before={p.name:sha(p) for p in (out/'windows').glob('*.raw.json')}
    shutil.copyfile(out/'model-output.json',out/'text-only-original-model-output.json')
    shutil.copyfile(out/'quality-review.json',out/'text-only-original-quality-review.json')
    # The full text-only result remains archived; scorer refuses overwrites.
    os.replace(out/'quality-review.json',out/'quality-review-before-attribution.json')
    tick=time.perf_counter()
    with (out/'cache-only-native8-attribution.log').open('xb') as log:
        code=subprocess.run([sys.executable,str(Path(__file__).with_name('practical_transcript_worker_20261107.py')),'--control',str(C),'--index',str(index),'--resume','--cached-only'],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW).returncode
    assert code==0;worker=read(out/'completed-state.json');assert worker['newNeuralWindows']==0 and not worker['modelLoaded']
    assert before=={p.name:sha(p) for p in (out/'windows').glob('*.raw.json')}
    with (out/'attributed-score.log').open('xb') as log:
        assert subprocess.run(['E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe',str(Path(__file__).with_name('score_practical_transcript_20261107.py')),'--control',str(C),'--meeting',name],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW).returncode==0
    check=subprocess.run([str(checker),str(out/'model-output.json'),str(round(case['audioSeconds']*1000))],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW);assert check.returncode==0,check.stderr
    (out/'product-contract.json').write_text(check.stdout,encoding='utf8')
    old=read(base/'practical-text-first-r1/transcripts'/name/'quality-review.json');new=read(out/'quality-review.json')
    assert new['chronologicalTextDiagnostic']['cer']==read(out/'text-only-original-quality-review.json')['chronologicalTextDiagnostic']['cer']
    row={'meeting':name,'audioSeconds':case['audioSeconds'],'audioSha256':case['audioSha256'],
      'rawCerBefore':old['chronologicalTextDiagnostic']['cer'],'rawCerAfter':new['chronologicalTextDiagnostic']['cer'],
      'rawMetricScope':'Ordinary full text CER' if name.startswith('S_') else 'Mixed chronological diagnostic only; not per-person overlap acceptance',
      'strictEditsBefore':sum(old['chronologicalTextDiagnostic']['edits'].values()),'strictEditsAfter':sum(new['chronologicalTextDiagnostic']['edits'].values()),
      'referenceCharacters':new['referenceCharacters'],'jointCpCerDiagnostic':new['anonymousStreamCpCerDiagnostic']['characterErrorRate'],
      'unconfirmedTextFraction':new['unconfirmedSpeakerText']['fractionOfRecognizedCharacters'],
      'rawAsrProcessFamilySeconds':next(r['accumulatedProcessFamilySeconds'] for r in run['results'] if r['meeting']==name),
      'cacheAttributionAndScoringSeconds':time.perf_counter()-tick,'rawCacheUnchangedDuringAttribution':True,'additionalNeuralInference':0,
      'actualProductDocumentContractPassed':True,'modelOutputSha256':sha(out/'model-output.json'),'qualified':False}
    rows.append(row)
record={'at':now(),'state':'NATIVE_VERBATIM_TWO_FULL_MEETINGS_COMPLETE_TEXT5_AND_SALE_OPEN','results':rows,
 'decision':'Keep opt-in native verbatim output support and its distinct cache binding. Do not promote as acoustic accuracy fix or change installed defaults. No flag sweep/per-meeting choosing; both fixed full meetings and baseline retained.',
 'scope':'No text/reference rewrite, filler/er deletion, training, new ASR weights, or new diarization inference. Only documented native useItn flag changed. Low-RAM interrupted8 windows reused and35.8886455s retained. New full texts were then attributed with existing FP16 journals, no new ASR. Shared product format works; no app/mobile/card/customer/factual-minute qualification.',
 'next':'原QM04继续：原生数字格式控制S6.95495%仍>5%、L混音26.12955%仅诊断，停止继续调该开关。保留FP16分人研究基线和跨域失败。现在只验证已固定官方Qwen3-ASR-0.6B-hf原生Transformers5.22.1/BF16，不重跑旧社区ONNX复读实现；现有外置6800XT唯一型号识别、CPU5%/private2GiB/实际低RAM保护不变，先短段EOS/复读/静音/资源，过门后才同两完整真实会评分；失败保留无自动重试。不喂参考/人数/热词、不训练或扩大预算。最终未见集、重叠逐路内容/事实纪要/手机实卡/售卖门继续OPEN。',
 'qualityQualified':False,'defaultProductChanged':False,'finalHoldoutOpened':False}
atomic_json(C/'review.json',record);print(json.dumps({'state':record['state'],'results':rows},ensure_ascii=False))
