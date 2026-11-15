"""Prepare source-grounded error review, not a new scored or training cohort."""
from pathlib import Path
from datetime import datetime
import hashlib,json,math,os,shutil,sys,wave
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
sys.path.append('E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Lib/site-packages')
from reference_textgrid_20261104 import read_reference_intervals
import soundfile as sf
R=S.parent.parent;D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'context-matched-baseline-r3';OUT=D/'asr-audio-adjudication-r1';OUT.mkdir()
audio=Path('outputs/Companion-ASR原音复核-20261115').resolve();audio.mkdir()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
scores=read(C/'baseline-score.json')['cases'];cases=read(C/'scoring-only.json')
errors=[r for r in scores if r['condition']=='clean-short-response' and r['totalEdits']>0]
assert len(errors)==4 and sum(r['totalEdits'] for r in errors)==13
sources=read(R/'docs/handoffs/20261108-tse-source-supervision/sources.json');rows=[]
for i,error in enumerate(errors):
 case=next(r for r in cases if r['id']==error['id']);source=next(r for r in sources if r['meeting']==case['meeting'])
 assert source['role']=='validation' and sha(source['localFlac'])==source['expectedWholeFileLfsSha256']
 assert sha(source['reference'])==source['referenceSha256'] and sha(case['wav'])==case['wavSha256']
 target=audio/(str(i+1).zfill(2)+'-原识别输入.wav');shutil.copyfile(case['wav'],target);assert sha(target)==case['wavSha256']
 info=sf.info(source['localFlac']);assert info.samplerate==16000 and info.channels==8 and info.subtype=='PCM_16'
 low=max(0,case['sourceStartFrame']-32000);high=min(info.frames,case['sourceEndFrame']+32000)
 with sf.SoundFile(source['localFlac']) as stream:
  stream.seek(low);pcm=stream.read(high-low,dtype='int16',always_2d=True)[:,0].astype('<i2',copy=False).tobytes()
 assert len(pcm)==(high-low)*2
 context=audio/(str(i+1).zfill(2)+'-含前后各两秒原音.wav')
 with wave.open(str(context),'wb') as wav:
  wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000);wav.writeframes(pcm)
 with wave.open(str(context),'rb') as wav:assert wav.readframes(high-low)==pcm
 all_rows=read_reference_intervals(source['reference'])
 nearby=[r for r in all_rows if r['text'].strip() and r['start']<high/16000 and r['end']>low/16000]
 rows.append({'case':case['id'],'meeting':case['meeting'],'originalInput':str(target),'originalInputSha256':sha(target),
  'contextAudio':str(context),'contextAudioSha256':sha(context),'contextStartFrame':low,'contextEndFrame':high,
  'targetStartInContextSeconds':case['sourceStartFrame']/16000-low/16000,
  'targetEndInContextSeconds':case['sourceEndFrame']/16000-low/16000,
  'sourceWholeFlacSha256':source['expectedWholeFileLfsSha256'],'sourceReferenceSha256':source['referenceSha256'],
  'referenceTextPendingAudioAdjudication':error['rawReferenceText'],'rawAsrTextUnchanged':error['rawAsrText'],
  'originalCharacterEdits':error['totalEdits'],'nearbyOriginalAnnotations':nearby,
  'humanAudioReviewCompleted':False,'labelDecision':None,
  'scope':'Posthoc review of all4erroneous clean-short cases, not a held-out quality sample. Longer context may include partial neighbor utterances; it is for listening, never an ASR target or scored/transcribed input.'})
report={'state':'PREPARED_PUBLIC_ORIGINAL_AUDIO_ERROR_ADJUDICATION_PACKET_NOT_YET_REVIEWED',
 'at':datetime.now().astimezone().isoformat(),'cases':rows,'newNeuralCalls':0,'newParameterUpdates':0,
 'newScoredCohort':False,'selectedAfterKnownErrors':True,'trainingUseAuthorizedByThisPacket':False,
 'originalLabelsOrScoresChanged':False,'audioPlaybackStarted':False,'microphoneStarted':False,'humanReviewCompleted':False,
 'license':'AISHELL4 CC-BY-SA-4.0; original source manifest retained. https://www.openslr.org/111/',
 'next':'Listen to the original input and its unchanged surrounding source before adjudicating lexical content or annotation boundaries. Preserve all existing labels/scores until a justified separate correction. Do not claim the model is repaired by preparing this packet.',
 'qualityQualified':False,'limits':limits.query()}
(OUT/'packet.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
lines=['Companion 公开原音错误复核材料｜2026-11-15',
 '目的：确认已有4条短句错误到底是听错、标注文字歧义还是切句边界。尚未人工听审，不改变原分、不作为新训练或质量合格证据。',
 '原识别输入保留原文件字节；第二个文件仅保留该单麦原音及前后各2秒，未增益、降噪、变速、重采样或再转写。较长文件中的邻近话语可能不完整，只供回听，不当训练答案。',
 '没有启动播放、麦克风或任何模型。全部为AISHELL4公开音频，CC-BY-SA-4.0，来源 https://www.openslr.org/111/。','']
for i,row in enumerate(rows):
 lines.extend([str(i+1)+'. '+row['case'],'原参考（待听审）：'+row['referenceTextPendingAudioAdjudication'],
  '原模型输出：'+row['rawAsrTextUnchanged'],'原输入：'+Path(row['originalInput']).name,
  '前后文：'+Path(row['contextAudio']).name,
  '目标在前后文中的区间：'+format(row['targetStartInContextSeconds'],'.3f')+'—'+format(row['targetEndInContextSeconds'],'.3f')+'秒',
  '待核：听到的完整内容；有无削掉音节/夹入别人的话；是否能明确判定。无法听清时保留不确定，不猜。',''])
(audio/'复核说明.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({'state':report['state'],'cases':4,'audioFiles':8,'directory':str(audio),'newInference':0,'playbackStarted':False},ensure_ascii=False))
