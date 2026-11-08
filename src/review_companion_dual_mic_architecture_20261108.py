"""Bind the speaker-first architecture decision to current source and old evidence."""
from pathlib import Path
from datetime import datetime
import hashlib,json,subprocess
from practical_io_20261107 import atomic_json

R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research'
S=R/'companion-device-closure055';F=R/'firmware-recovery';A=R/'recovered-android-backend'
C=R/'docs/handoffs/20261108-dual-mic-architecture-review'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
head=lambda p:subprocess.check_output(['git','rev-parse','HEAD'],cwd=p,text=True).strip()
assert not (C/'review.json').exists();integrity=read(C/'input-integrity-review.json')
assert len(integrity['realArchivedInputs'])==2 and all(r['pcmReinterleaveExactlyOriginal'] for r in integrity['realArchivedInputs'])
inputs=[
    (F,'app/companion_pendant/recording/wba_pdm_capture.h','PDM pair has two channels; ordinary callback emits mono; separate synchronous pre-beamforming pair observer is optional.'),
    (F,'app/companion_pendant/recording/wba_pdm_capture.c','LEFT/RIGHT/average/beamform choices emit a single selected stream. Raw pair observer can expose both only before this reduction.'),
    (F,'app/companion_pendant/recording/wba_microphone_profile.h','Uncalibrated normal voice and meeting profiles select LEFT and selected_only when no pair observer is attached.'),
    (F,'app/companion_pendant/recording/companion_opus16_rt.c','opus_encoder_init channels=1 and COP header channels=1. Normal16k mode is16kbps; changing a header cannot create a spatial recording.'),
    (F,'app/companion_pendant/recording/companion_recording_audio_profile.h','APM1 prelude encodes/requires one output channel; filtered_mask=3 describes processing provenance, not two stored audio channels.'),
    (S,'apps/windows/src-tauri/src/backend/import_audio.rs','Original import is retained. ASR derivative is downmixed and may invert a strongly anti-correlated right channel. This derivative must not be reused as the phase-preserving spatial input.'),
    (A,'apps/android-backend/native/src/long_transcription.rs','Current mobile ASR path validates16k mono. This is the complete recovered Android backend, not the old incomplete software050 Android tree.'),
    (M,'src/companion_local_meeting_20261107.py','Standalone model provider currently accepts only normalized16k mono.'),
    (S,'packages/meeting-transcript/src/lib.rs','Existing stable shared Document is a suitable downstream boundary; channel-aware input can evolve independently of UI/minutes output.')]
audit=[{'repo':str(root),'repoHeadAtReview':head(root),'path':str(root/relative),'sha256':sha(root/relative),'finding':finding} for root,relative,finding in inputs]
backlog=read(R/'docs/product_backlog.json');embedded=backlog['owner_module_execution']['embedded']
previous=backlog['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104']
old_spatial=read(Path('C:/Users/Billy/Documents/Codex/2026-10-28/companion-upper-delivery-20261028/work/isolated-sources-p692/analysis.json'))
sources=[
    {'url':'https://github.com/desh2608/gss','type':'author implementation','relevance':'Multi-channel original recording plus RTTM speaker boundaries -> per-target enhancement. Uses speaker activity inside CACGMM/GSS and beamforming, not merely zeroing audio outside annotated intervals. A training-free reference architecture; not yet verified on our two close microphones.'},
    {'url':'https://arxiv.org/abs/2212.05271','type':'author paper','relevance':'Reproducible GSS/ASR recipes for AMI,AliMeeting,LibriCSS; microphone-count and context dependence mean multi-mic results cannot be copied to our dual-mic device.'},
    {'url':'https://github.com/espnet/espnet/blob/master/egs2/chime8_task1/README.md','type':'official challenge recipe','relevance':'Diarization -> channel selection/GSS -> ASR is an established full pipeline. Its Pyannote/CuPy installation is not an automatic choice for this machine or existing model defaults.'},
    {'url':'https://www.microsoft.com/en-us/research/publication/vararray-array-geometry-agnostic-continuous-speech-separation/','type':'author research','relevance':'Inter-channel correlation/phase can improve continuous meeting separation; separation-first CSS remains an alternative architecture, not a new checkpoint being run here.'},
    {'url':'https://learn.microsoft.com/en-us/azure/ai-services/speech-service/speech-sdk-microphone','type':'manufacturer engineering guidance','relevance':'Documents an example40mm two-mic linear array and amplitude/phase/port matching. These are Microsoft Audio Stack recommendations, not universal pass/fail limits or proof our device meets them.'},
    {'url':'https://www.st.com/resource/en/user_manual/dm00391112-getting-started-with-acousticbf-real-time-beam-forming-middleware-stmicroelectronics.pdf','type':'manufacturer manual','relevance':'Two-mic directional beamforming is feasible under a specified geometry/calibration. A fixed-direction virtual microphone is not a complete multi-speaker meeting separator.'},
    {'url':'https://datatracker.ietf.org/doc/html/rfc6716#section-4.3','type':'codec standard','relevance':'CELT intensity stereo discards left/right differences in selected bands. A stereo channel count or audible stereo alone does not prove spatial information survives coding; compare decoded spatial separation to original PCM first.'},
    {'url':'https://docs.cupy.dev/en/stable/install.html#using-cupy-on-amd-gpu-experimental','type':'official runtime documentation','relevance':'GSS author GPU path uses CuPy; current AMD support is experimental and includes eigen-solver limitations. Windows RX6800XT with working PyTorch does not establish native CuPy/GSS compatibility. No driver/CUDA install is triggered.'}]
decision={'at':datetime.now().astimezone().isoformat(timespec='seconds'),
    'state':'SPEAKER_FIRST_DUAL_MIC_REFACTOR_RECOMMENDED_INPUT_PREREQUISITE_VERIFIED',
    'ownerOriginal':'可能不要这样子优化而是要做重构吧, 仔细研究一下, 感觉单麦做这种东西好做嘛, 现在有双麦, 按照这个看看能不能区分不同说话人, 先区分后撰写',
    'ownerCorrection':'转写','interpretedRequirement':'Reassess the architecture around available dual microphones: identify who speaks when, use this to separate overlapping speech, then transcribe each speaker. Pause failed activity-head tuning; preserve the ordinary baseline.',
    'previousModelWorkpoint':{'state':previous['status'],'next':previous['next'],'kept':True},
    'recommendation':'Refactor the audio input and processing stages around preserved synchronized microphone channels. First evaluate a diarization-first guided multi-channel separator before investing in further model training. This is a feasibility recommendation, not evidence that two microphones already meet accuracy targets.',
    'keyFindings':[
        'Normal board recording currently reaches the host as a one-channel stream. The second microphone cannot be recovered from that mono recording.',
        'Two microphone signals both contain every audible person; microphone indices are not speaker identities. Multiple meeting participants can be diarized from one channel, while overlapping content is much harder.',
        'The current pipeline crosses mono boundaries in capture selection, codec/header/profile, import-ASR derivative and model commands. Changing one model or merely changing channels metadata cannot implement dual-mic separation.',
        'Existing raw synchronous pair observation demonstrates a possible independent capture boundary on historical hardware; it is a finite diagnostic, not continuous stereo storage or product delivery.',
        'Perfect downstream activity zeroing tested this morning is not internally guided spatial source separation. Its negative result does not disprove GSS or a multi-channel redesign.',
        'Archived layout estimate is approximately31.8mm between component centers, not a measured current acoustic-port distance. Near spacing supplies limited angular diversity and front/back ambiguity; two microphones do not guarantee separation of3+simultaneous speakers.'
    ],
    'architecture':[
        {'stage':'recording_input','contract':'Immutable original paired channels, common sample grid/channel IDs, recorded clock/geometry/calibration and codec identity. No early downmix or independent nonlinear phase-changing preprocessing.'},
        {'stage':'speaker_activity','contract':'Global anonymous people and overlapping activity intervals/confidence from voice identity plus available spatial cues. Preserve uncertainty; do not require a perfect hard decision or equate direction to a real identity.'},
        {'stage':'target_audio','contract':'Nonoverlap may use the original reference channel. Overlap uses the activity estimate inside multi-channel separation/beamforming; preserve original samples and provenance. GSS-style training-free reference first, subject to actual two-channel benefit.'},
        {'stage':'per_speaker_asr','contract':'Feed each extracted target to the protected existing recognizer. Retain raw outputs; align globally to reconcile speaker/lane permutations and timing. A fixed output lane is not a permanent person.'},
        {'stage':'document_and_minutes','contract':'Reuse stable shared Document; attach time/person/source evidence for minutes and roles. Unconfirmed names/roles remain unconfirmed. Model implementations stay replaceable and separate from recording/management/UI.'}],
    'refactorScope':[
        'Capture paired frames once, retain both with common sequence/sample offset; measure actual second-channel DSP/codec CPU,stack,RAM and energy before continuous firmware enablement.',
        'Version the mono-only storage/transport/codec contract; preserve old sessions/clients. Distinguish sample frames from interleaved sample elements, retain both channels through gaps/reconnect and exact segment recovery.',
        'Keep original multi-channel assets distinct from the mono ASR derivative in both host backends; expose one channel-aware model-independent input contract.',
        'Evaluate original PCM before compressed dual input. Measure whether codec preserves useful phase and delay; ordinary low-bitrate stereo may erase the information that spatial separation needs.',
        'Keep existing mono path available; any dual candidate must improve per-person errors without harming ordinary speech. No default switch or firmware installation before this evidence.'
    ],
    'resourceTradeoff':{'calculationOnly':True,'PCM16_16k_twoChannelBytesPerSecond':16000*2*2,
        'existingMono16kbpsPayloadBytesPerHour':16000//8*3600,
        'twoIndependent16kbpsPayloadBytesPerHour':2*(16000//8)*3600,
        'note':'Two16kbpsstreams are14.4MB/h before framing versus7.2MB/h mono. With16MiB NOR, two-hour offline retention cannot be assumed. Codec choice, compression, storage and real-time transfer require joint evaluation; CPU and battery cost are not inferred from these byte calculations.'},
    'historicalSpatialEvidence':{'source':str(Path('C:/Users/Billy/Documents/Codex/2026-10-28/companion-upper-delivery-20261028/work/isolated-sources-p692/analysis.json')),
        'state':old_spatial['result'],'medianSourceSpatialSimilarity':old_spatial['analyses'][0]['medianSourceSpatialSimilarity'],
        'eligibleBandPowerFractions':[r['eligibleBandPowerFraction'] for r in old_spatial['analyses'][0]['sourceMetrics']],
        'meaning':'In that old isolated-playback setup the two source spatial signatures were nearly identical in a limited stable band. No geometry or true simultaneous-person proof. Do not repeat fixed FIR/null tuning or call it a universal dual-mic impossibility.'},
    'sourceAudit':audit,'primaryReferences':sources,
    'newImplementation':{'file':str(M/'src/companion_multichannel_input_20261108.py'),
        'sha256':sha(M/'src/companion_multichannel_input_20261108.py'),
        'scope':'Independent research input preserves per-microphone PCM and sample positions. No neural call, downmix, polarity change or product backend installation.',
        'verification':str(C/'input-integrity-review.json'),'verificationSha256':sha(C/'input-integrity-review.json')},
    'hardwareBoundary':{'recordedCurrentFirmware':embedded['baseline']['firmwareVersion'],
        'sourceCommit':embedded['baseline']['sourceCommit'],'runningWorkAtReview':embedded['runningWork'],
        'newBoardAccess':False,'newFirmwareBuild':False,'newInstallation':False,
        'scope':'Other ordinary long recording continues unchanged. No claim that an old capture UID proves current assembled microphone geometry or current paired capture.'},
    'validationOrder':[
        'First preserve independent synchronous raw channels; validate clipping, channel order, gain/polarity, clock drift and actual acoustic geometry.',
        'Use matched real meetings for single-channel versus exactly two-channel comparison. If public array geometry differs, report it as algorithm evidence only; current-board two-person overlap remains necessary.',
        'Keep predicted-activity end-to-end result separate from an explicitly labeled oracle-activity diagnostic; activity must influence spatial mask/beamforming, not reference word selection.',
        'Report per-person word errors and omissions, speaker confusion, duplication, short turns and true2/3+overlap, plus ordinary speech regression and actual CPU/RAM/time.',
        'Only a reproducible short gain triggers full independent meetings and then Windows/Android/card integration. Original strict<5% and minutes-fact/sale gates remain open.'
    ],
    'next':'继续原RM-OVERLAP，优先验证“保留双麦原音→说话人活动→引导式空间分离→逐人转写”的最小真实会议对照。已完成双路无损研究输入；先建立恰好两路、同步/几何明确的公开会议输入并与单路公平比较，GSS参考实现需先解决本机轻量数值执行可行性。当前实板长录期间不占用或重刷，后续在正常空闲边界补当前实板双人重叠样本。看到逐人实际收益后才推进双声道固件/格式/双端整体重构，不把研究入口完成当效果合格。',
    'actualNewAccuracyMeasured':False,'newModelsOrTraining':0,'productDefaultChanged':False,
    'currentDeviceDualMicSpeakerSeparationQualified':False,'finalHoldoutOpened':False,'qualityQualified':False}
atomic_json(C/'review.json',decision)
readme=M/'README.md';text=readme.read_text(encoding='utf8');marker='Observed dual-microphone architecture review,2026-11-08:';assert marker not in text
text+='\n\n'+marker+' the owner corrected the goal to identify speakers before transcription and asked for an architecture reassessment using both available microphones. Current normal firmware selects LEFT and emits mono; Opus initialization/header andAPM1 require one output channel, while Windows/mobile/model ASR paths use a mono derivative. Windows preserves imported originals, so the spatial path must use that original instead of its downmix/polarity-adjusted ASR copy. A hardware pair observer exists, but continuous dual-channel product storage/transmission is not implemented. A new independent channel-preserving research input reinterleaves two original historical2s physical pairs exactly, preserves an anti-phase fixture, and rejects mono/duplicated stereo as a distinct spatial pair. No speaker separation/model run or product default change is claimed.\n\nThe recommended bounded next architecture is preserved synchronous microphone channels -> overlapping global speaker activity -> internally guided multichannel spatial separation -> per-person ASR -> existing shared Document/minutes, retaining ordinary speech and all uncertain/raw evidence. GSS is a training-free reference architecture, not already qualified for two close microphones or this Windows AMD runtime. Source reviews bind the actual66734firmware source25e108f and current software sources. Public larger-array scores cannot prove current dual-mic quality; archived31.8mmcomponent-center estimates are not acoustic-port measurements. Historical isolated-source spatial similarity0.9966was limited to its capture setup and not true multi-person ground truth. Low-bitrate intensity stereo can discard inter-channel differences; raw PCM comparison precedes codec choice. Two16kbpspayloads cost14.4MB/h before overhead versus7.2MB/h mono, so16MiBstorage/two-hour offline retention, real CPU/RAM/energy and transfer need joint review. The existing two-hour board run is untouched. Read evidence/20261108-dual-mic-architecture-review/review.json; actual close-pair meeting benefit, full cross-meeting<5%, both installed hosts/card and sale gates remain open.\n'
readme.write_text(text,encoding='utf8')
print(json.dumps({'state':decision['state'],'firmwareSource':head(F),'normalStoredChannels':1,'historicalPairInputChecked':2,'speakerSeparationMeasured':False,'newHardwareAccess':0},ensure_ascii=False),flush=True)
