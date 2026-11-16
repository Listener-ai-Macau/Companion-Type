"""Close the day analysis against evidence; no model execution or training."""
from pathlib import Path
from datetime import datetime
import json
import hashlib

R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
J=D/'joint-architecture-r1'; C=J/'microphone-diagnostic-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

report={
 'state':'DIRECTION_FIRST_REVIEW_CLOSED_GPU_INFERENCE_RESULT_SEPARATE',
 'at':datetime.now().astimezone().isoformat(timespec='seconds'),
 'ownerDecision':'Mature pretrained specialist components and reliable product integration are the mainline. Training remains conditional gap-filling after the bottleneck is demonstrated, not an automatic overnight activity.',
 'scopeOrder':['A:multiple speakers taking turns without overlap, separately Chinese and English',
               'B:overlap and speaker-conditioned recognition/separation only after A is acceptable',
               'C:noise/far-field robustness by recording condition, followed by product recovery and deployment'],
 'quality':{'targetAccuracy':.98,'minimumAccuracy':.95,
   'originalSingleMicrophonePerSpeakerFactAndHoldoutGatesUnchanged':True,
   'CERandWERAreSeparateEditRatesNotOneUniversalAccuracy':True,
   'headsetMixMayQualifyProduct':False,'qualityQualified':False,'saleQualified':False},
 'existingEvidence':[
   {'case':'Frozen12 English nonoverlap validation clips','errors':141,'words':709,'wer':141/709,
    'deletions':72,'implication':'A separator or diarizer alone cannot repair plain words already absent from raw ASR.'},
   {'case':'Ordinary Chinese39minute source','errors':461,'characters':8325,'cer':461/8325,
    'implication':'Even this easier whole-meeting condition misses the5% floor, with two individual speakers worse. It does not establish universal Chinese performance.'},
   {'case':'Same exposed English words, unchanged PCM energy association','lowEnergyQuartileWords':178,
    'lowEnergyQuartileDeletions':29,'otherWords':531,'otherDeletions':43,
    'implication':'Deletion frequency is about twice as high in the lowest energy quartile, but43/72 deletions remain elsewhere. Energy is not target-speaker SNR; do not infer causality or apply blind gain/denoise.'},
   {'case':'Original speaker activity review','rawMultiVoiceDer':.209019,
    'missedActivityFractionOfErrorSeconds':37.95/43.7101,
    'implication':'Speaker activity recall and continuous identity remain a separate important failure mode; do not count an exclusive-view metric as the original multi-voice DER.'}],
 'avoidRepeating':[
   'Tiny language/acoustic adapters already failed to deliver cross-source improvements; changing rank or another threshold is not evidence of a better direction.',
   'Fixed30second MOSS improved one English source but regressed Chinese; it is not adopted as a universal replacement.',
   'Whisper large-v3-turboQ8 on the same English set scored195/709 versus nativeQwen141/709; no broad expansion of that rejected candidate.',
   'A third-partyQ8 CPU port was not equivalent to the native model and did not pass quality gates. No new quantization/model grid.',
   'The existing317M-parameter acoustic-training preparation has no verified real-GPU fit, throughput or quality gain. Code readiness is not a justification to train.'],
 'specialistResponsibilities':[
   {'part':'Audio acquisition and input','job':'Preserve waveform timing, channel/codec integrity, quiet short turns, incremental/offline continuity.'},
   {'part':'Pretrained bilingual ASR','job':'Produce faithful raw words; measure ChineseCER and EnglishWER separately before assigning speakers.'},
   {'part':'Speaker activity and identity','job':'Recall all speech and keep speaker identity continuous across the full meeting; evaluate original zero-collar protocol.'},
   {'part':'Alignment','job':'Attach words to real audio times; do not use forced alignment to invent missing words.'},
   {'part':'Overlap-specific recognition','job':'Use diarization-conditioned target-speaker recognition or carefully admitted separation only for proved overlap needs.'},
   {'part':'Product finalization','job':'Provisional incremental results and revisable offline final results; preserve raw transcript, uncertainty, recoverability and evidence links.'}],
 'fixedNextExperiment':{'pairing':str(C/'pairing.json'),'protocol':str(C/'inference-protocol.json'),
   'maximumNewDecodes':13,'trainingUpdates':0,'originalControlMustMatchGeneratedIdsExactly':True,
   'sameExposedEnglishMeetings':2,'sameIntervals':12,'referenceWords':709,
   'interpretationBranches':[
     'Both sources materially better in headset mix: investigate acoustic recording condition, actual card input and far-field robustness first; do not infer defective hardware.',
     'Headset mix also poor: prioritize faithful recognizer/task/inference conditions and one justified mature component contrast before deciding on acoustic adaptation.',
     'Raw words acceptable but speaker-attributed words fail: prioritize activity recall, global identity and alignment.',
     'Effects inconsistent across sources: retain uncertainty and inspect source-specific acoustics; no universal improvement claim.'],
   'diagnosticRelative25PercentHeuristicIsNotAProductGate':True,
   'nextGpuUseOwnerConfirmed':True,'inferenceOutputsAndScoresInSeparateImmutableRun':True},
 'sources':[
   {'url':'https://github.com/m-bain/whisperX',
    'supported':'Recognition, word alignment and diarization are distinct components. The project also acknowledges overlap and diarization limitations.',
    'decision':'Borrow tested modular responsibilities; its CUDA stack is not established as a drop-in AMD solution and its model choice is not assumed to pass our data.'},
   {'url':'https://huggingface.co/pyannote/speaker-diarization-community-1',
    'supported':'Mono16kHz diarization, offline local usage, improved assignment/counting. Official benchmarks still show nonzero far-field meeting error.',
    'decision':'An optional mature diarization comparator. Account/contact-sharing acceptance is pending; do not access credentials or bypass the gate. Not a current dependency.'},
   {'url':'https://github.com/BUTSpeechFIT/TS-ASR-Whisper',
    'supported':'DiCoW conditions recognition on diarization activity; SE-DiCoW uses automatic self-enrollment for overlapping regions.',
    'decision':'A later evidence-backed overlap direction, not proof of Chinese gains or justification to replace current A-stage raw-word work.'},
   {'url':'https://groups.inf.ed.ac.uk/ami/corpus/meetingrooms.shtml',
    'supported':'Common word-clock acquisition synchronizes audio channels.',
    'decision':'Corroborates same-meeting recorded-view timing; independent unchanged-waveform review remains attached.'}],
 'executionBoundaries':{'cpuOrIntegratedGpuTraining':False,'broadTrainingAutomaticAdmission':False,
   'userLabellingRequired':False,'privateFinalHoldoutOpened':False,
   'shippedWeightsChanged':False,'newProductQualityClaim':False},
 'evidence':[{'file':str(p),'sha256':sha(p)} for p in [
   J/'english-acoustic-omission-review20261116.json',C/'pairing.json',C/'timebase-review.json',
   C/'initial-timebase-prefight-failure.json',C/'inference-protocol.json',C/'scoring-control.json']],
}
(J/'direction-first-review20261116.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'state':report['state'],'trainingAutomaticAdmission':False,'nextMaximumDecodes':13},ensure_ascii=False))
