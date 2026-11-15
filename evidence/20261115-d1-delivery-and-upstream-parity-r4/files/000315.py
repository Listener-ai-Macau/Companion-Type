"""Consolidate actual spatial/codec gain and the failed gate-removal ablation."""
from pathlib import Path
from datetime import datetime
import hashlib,json,psutil
from practical_io_20261107 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research'
C=R/'docs/handoffs/20261108-dual-mic-real-meeting-validation'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert not (C/'decision.json').exists()
main=read(C/'review.json');ablation=read(C/'no-hard-gate/review.json');audit=read(C/'codec-and-gate-audit.json')
assert audit['sourceReviewSha256']==ablation['sourceMainReviewSha256']==sha(C/'review.json')
for source in read(C/'protocol-r2.json')['sourceFiles']:assert sha(source['file'])==source['sha256']
assert main['ordinaryRawTextSameAcrossArms'] and not main['qualityQualified'] and not ablation['qualityQualified']
owned=[]
for p in psutil.process_iter(['cmdline']):
    for a in p.info['cmdline'] or []:
        if str(a).replace('\\','/').lower().startswith(str(M/'src').replace('\\','/').lower()+'/') and Path(str(a)).name in ['dual_mic_gss_worker_20261108.py','dual_mic_gss_asr_worker_20261108.py','dual_mic_gss_no_gate_asr_worker_20261108.py','run_dual_mic_gss_validation_20261108.py','run_dual_mic_gss_no_gate_20261108.py']:owned.append(p.pid)
assert not owned
mono=main['overlapTotals']['mono_activity'];raw=main['overlapTotals']['dual_pcm'];coded=main['overlapTotals']['dual_opus']
per_person=[]
for row in [r for r in main['perPerson'] if r['meeting']=='L_R003S01C02']:
    a=row['conditions']['mono_activity']['edits'];b=row['conditions']['dual_pcm']['edits']
    per_person.append({'root':row['rootIndex'],'person':row['referencePersonForScoringOnly'],'rawDualMinusMatchedMonoEdits':b['total']-a['total'],'rawDualMinusMatchedMonoDeletions':b['delete']-a['delete']})
assert all(r['rawDualMinusMatchedMonoEdits']<=0 for r in per_person)
decision={'at':datetime.now().astimezone().isoformat(timespec='seconds'),
    'state':'REAL_DUAL_INPUT_LOCAL_GAIN_CODEC_LOSS_AND_ACTIVITY_LIMIT_IDENTIFIED',
    'ownerRequest':'那你看看验证一下咯  开始看看怎么继续推进吧',
    'ownerCompressionQuestion':'然后你看看是不是音频压缩了比较难分析要解压了好分析一点',
    'actualValidation':'Processed real original channels0/1 from pinned complete lossless AISHELL-4 sources, prior predicted nativeFP16 speaker journal, one fixed GSS reference and unchanged native1.7B ASR. Compared matched mono activity-only, rawdual spatial separation and decodedhostOpusdual; then one evidence-triggered no-hard-gate control on all6existing target lanes.',
    'dataScope':'90s original roots: two30s overlapping excerpts of one exposed Mandarin meeting, including the disclosed1.900779s triple supplement, plus30sordinary from another meeting. Spatial estimation uses15scontext eachside. This is not cross-corpus/general meeting qualification.',
    'mainComparison':{'referenceCharactersInOverlapClips':256,'matchedMonoActivityOnly':mono,
        'rawDualGuided':raw,'decodedOpusDualGuided':coded,
        'rawDualErrorReductionVersusMatchedMono':1-raw['total']/mono['total'],
        'cachedPreviousSingleMicPs4':main['cachedPreviousSingleMicPs4'],
        'cachedPs4IsDifferentSegmentationAndMethod':True,
        'perRootSpatialEditImprovement':[{'root':r['case'],'mono':r['totals']['mono_activity']['total'],'rawDual':r['totals']['dual_pcm']['total']} for r in main['perRoot'] if r['kind']!='ordinary-regression'],
        'perPersonDeltas':per_person,'noMatchedMonoPersonTotalRegressedInThisScreen':True},
    'compressionConclusion':{'losslessSourceFlacDecodedPcmExactlyPreviousChannel0':True,
        'flacRoundtripPcmExactlyEqualAllThreeClips':True,
        'lossyOpusControl':'Hostlibopus32kbpsstereo,20msCBR,lowdelay,complexity0; all input channels/timeline decoded before analysis. Not current-board monoCELT bitstream.',
        'rawDualOverlapEdits':raw['total'],'opusDualOverlapEdits':coded['total'],
        'rawDualOverlapDeletions':raw['delete'],'opusDualOverlapDeletions':coded['delete'],
        'ordinaryRawEdits':main['ordinaryTotals']['dual_pcm']['total'],'ordinaryOpusEdits':main['ordinaryTotals']['dual_opus']['total'],
        'meaning':'DecodedPCM is necessary but cannot recreate information discarded by lossy coding. In this fixed screen compression increased errors. FLAC/source compression was lossless and cannot explain the older baseline errors. Phase and amplitude both change; this does not isolate phase as the sole cause.'},
    'activityFailure':{'posthocFullyContainedRemovedChars':sum(r['fullyContainedCompletelyRemovedCharacters'] for r in audit['predictedGateCoverage'] if not r['ordinaryBypassDoesNotApplyThisGate']),
        'case':'Lroot27reference002-F has only1.6681of5.6539targetseconds inside its predicted activity; eight entirely interior reference characters have no retained audio under the hard gate.',
        'noHardGateTotals':ablation['totals'],'noHardGateDecision':ablation['state'],
        'interpretation':'Gating can erase missed target speech, while removing it restores some content but admits extensive other-speaker text. Neither posthoc word deletion nor selecting gated/ungated text per person is acceptable. Existing activity prediction and target isolation remain actual unresolved gates.'},
    'retained':'Preserve rawdual as one promising research direction, protect current ordinary and product defaults, retain all27generated condition rows and oldPS4/small-head failures. Do not install the hard-gated or ungated prototype as a finished meeting backend.',
    'methodAndRuntime':{'algorithm':'One pinned GSS NumPyCPU reference of author formulas;20iterations+1post,1024/256Blackman,15scontext,fixedrefchannel0,MVDR+BAN,WPEoff. No parameter,codecrate or channel-pair sweep.',
        'independentNumericalProof':str(C/'numpy-numerical-proof.json'),'nativeGpuParityMeasured':False,
        'recognizerInferenceAstUnchanged':True,'newTrainingRuns':0,'newModelFamilies':0,
        'newSpatialCalls':main['newSpatialAlgorithmCalls'],'mainAsrCalls':main['newAsrCalls'],'extraNoGateAsrCalls':ablation['newAsrCalls'],
        'mainOwnedStageSeconds':main['timings'],'extraNoGateAsrOwnedSeconds':ablation['asrOwnedSeconds'],
        'timingScope':'Sum of this owned finite experiment process families, all compared conditions included; excludes manual analysis/source download/preparation/publishing. Not stop-recording-to-summary latency or a whole-meeting speed claim.',
        'cpuPercentLimit':5,'privateCommitLimitBytes':2*1024**3,'maximumRecordedJobPrivateBytes':main['maximumRecordedJobPrivateBytes'],
        'gpuUtilizationHardCapped':False,'currentOwnedWorkers':owned,'resourcePauseResumeNotExercisedInThisRun':True},
    'limitations':['Fixed midpoint-utterance clip edit counts retain/report edge-straddling references; not strict full-recordingCER or pure-overlapCER.',
        'Two microphones from a larger public array do not verify the close recorder ports, synchronization/calibration or encoded transport.',
        'New mono_activity is an activity-only comparison, not state-of-the-art single-mic separation;oldPS4 is reported separately.',
        'The research common hard activity gate exposes false-negative limitations and is not adopted as a product rule.',
        'Host stereo codec result is limited to this frozen setting; recording capacity, battery and microphone phase preservation still require product engineering.',
        'No phone/card installation, customer hearing trial, final-holdout opening or sale qualification occurred.'],
    'next':'继续原RM-OVERLAP：保留这版原始双路GSS作为研究候选，固定算法/ASR/编码设置，到另一个房间或另一场未用于本轮决策的真实多人会议复验，重点单列弱声、短插话和3+重叠的逐人漏话与串话。说话人活动的漏判/误判须独立评分，不能用硬静音或逐人挑文字掩盖；本次取消硬门控支路已拒绝，不再追加同片段参数/模型试跑。当前实板长录结束并释放后才验证实卡双路原音与解码相位，再按真实收益确定存储/传输/双端重构。严格<5%、纪要事实、双端实卡及售卖门继续OPEN。',
    'productDefaultChanged':False,'newHardwareAccess':False,'finalHoldoutOpened':False,'strictWordErrorGatePassed':False,'saleGatePassed':False,'qualityQualified':False}
atomic_json(C/'decision.json',decision)
readme=M/'README.md';text=readme.read_text(encoding='utf8');marker='Observed real dual-input/codec validation,2026-11-08:';assert marker not in text
text+=f'\n\n{marker} original8channelFLACpayloads for the exposed L/S meetings match their pinned full LFS hashes. Exactly channels0/1 are retained;decoded channel0 exactly matches prior rootPCM, and three local FLAC roundtrips reproduce every PCM value. A separate hostlibopus32kbpsstereo/20msCBR/lowdelay/complexity0 control decodes before analysis with the same sample count. Raw and decoded spatial diagnostics are kept; this is not the current board monoCELT bitstream or verified recorder geometry.\n\nOne pinned GSS10fad18cae85e2e4342c77421abc70c9c5da23ed source is retained with MITlicense and a transparent NumPyCPU backend; no CuPy/AMD-GPU parity is claimed. Independent inverse covariance density/weighted PSD/fixed-reference MVDR,20iteration frequency-loop consistency and exact PCMSTFT roundtrip controls pass before meetings. The frozen reference uses1024Blackman/256hop,15scontext,20+1GSSiterations,noiseclass,fixedref0,MVDR+BAN,WPEoff. Existing predicted nativeFP16 activity supplies every new arm; the common post-GSS predicted waveform gate is an explicitly limited diagnostic, not a new product rule. Native1.7B recognition AST/settings remain unchanged.\n\nAcross fixed Lroots12/27 (two-speaker and disclosed true-triple), matched mono_activity has82edits,rawdual72,decodedOpusdual81 on256midpoint-reference characters. Rawdual improves each root by5edits and no matched person total regresses; this is a12.20%local reduction, not a generalCER/pass. Cached earlier singlemicPS4has174edits under a different pipeline/segmentation, not hardware-only proof. Ordinary Sroot1 rawmono/dualPCM+text are identical (22local clipedits);Opus has26. Boundary-straddling texts remain reported, so these are not full-recording or pure-overlapCER.\n\nA posthoc coverage audit finds8entire interior reference characters of one short Lroot27person erased by the predicted activity gate. One causal no-gate test reuses all6unmodified GSSfloat outputs with identical export gain;0new separation. Deletions21→4 but insertions33→456,total72→489,so that branch is rejected for every-person reporting without word selection. Rawdual direction is retained only for independent real-meeting replication and activity-quality work, with no further same-clip parameter sweeps. Source/derivative/audio/generation hashes,all27condition rows,codec phase diagnostics and failures are retained. Main spatial/inventory/ASR owned times143.357788/7.108935/319.967821s and extra no-gate ASR205.781390s are experimental stage costs, not one deployment/whole-meeting/minutes latency. CPU5%/private2GiB,max actual Job private{main["maximumRecordedJobPrivateBytes"]}B,one stage at a time;no driver/other-app changes. All workers ended. Current card long recording and phone remain untouched,defaults/finalholdout unchanged,and strict<5%/facts/installed hosts/card/sale gates remain open. Read evidence/20261108-dual-mic-real-meeting-validation/decision.json.\n'
readme.write_text(text,encoding='utf8')
print(json.dumps({'state':decision['state'],'rawDualEdits':raw['total'],'monoEdits':mono['total'],'codecEdits':coded['total'],'noGateEdits':ablation['totals']['ungated']['total'],'ownedWorkers':owned,'qualityQualified':False},ensure_ascii=False),flush=True)
