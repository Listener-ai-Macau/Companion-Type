"""Record actual completed outcomes and the next original-backlog work point."""
from pathlib import Path
from datetime import datetime
import json
from practical_io_20261107 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';C=R/'docs/handoffs/20261107-model-generation-recovery/practical-qwen-bounded-r4'
review=json.loads((C/'review.json').read_text(encoding='utf8'))
assert review['state']=='BOUNDED_NATIVE_TWO_FULL_MEETINGS_COMPLETE_ACCURACY_AND_SALE_OPEN'
next_step='原QM04准确率优先：同一原生部署路线下一项只比较官方Qwen3-ASR-1.7B-hf的实测收益，保持同两整会/无参考热词/严格含语气词与儿化评分及CPU5%/private2GiB预算；先完整权重精确加载与正常/失败原音/静音短控，再全会，失败不原样重跑。普通仍须<5%，大模型不预设通过。随后用官方Qwen3-ForcedAligner-0.6B-hf独立对齐已有识别文字，保留原字、分别测时间精度与逐人内容，再接FP16分人；对齐不当作纠词或声音分离。复杂重叠必须逐路恢复声音并分别转写、核对身份和两路内容；保留短句/跨域失败。纪要事实/手机电脑新模型安装/实卡/最终未见集/售卖门继续OPEN，不先启动自研训练。'
direction={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'ORIGINAL_QM04_NEXT_WORK_POINT_NO_GATE_CLOSED','next':next_step,
  'basis':{'ordinaryStrictFullTextCer':0.06438438438438439,'complexFullMixedTextDiagnosticCer':0.23420931304748732,
    'fixed30sNativeDecoderItselfRepeated':True,'boundedRecoveryCompletedBothFullMeetings':True,'ordinaryWholeDocumentUnchangedByRecovery':True,
    'notSolvedByNativeImplementationAlone':True,'wordAlignmentAndSpeakerTextPending':True},
  'sourcesCheckedOn':'2026-11-07','primarySources':['https://huggingface.co/Qwen/Qwen3-ASR-1.7B-hf','https://github.com/QwenLM/Qwen3-ASR'],
  'verifiedSourceScope':'Author documents native Transformers ASR and a separate word-level forced-aligner interface. Author results/throughput are not our two full recordings or RX6800XT5%CPU/2GiB results. A1.7B checkpoint has not been downloaded or run by this batch.',
  'doNotRepeat':['Do not infer no repetition from one passed short control or from using native instead of exported inference.',
    'Do not strip generated repetitions or fillers to manufacture CER5% or a final result.',
    'Do not label time bisection as two-voice source separation.',
    'Do not treat anonymous speaker activity DER as aligned word/person or factual-minute accuracy.',
    'Do not treat cached S reconstruction seconds as new ASR inference time.',
    'Do not mix actual memory recovery/manual engineering waits with model process time or summary latency.',
    'Do not consume final holdout or train before existing development/cross-corpus gates justify it.'],
  'nextCheckpointDownloadedOrRun':False,'sourceReviewAloneIsCapabilityProgress':False,'qualityQualified':False}
assert not (C/'next-direction.json').exists();atomic_json(C/'next-direction.json',direction)
path=M/'README.md';raw=path.read_text(encoding='utf8');marker='Observed bounded native ASR batch,2026-11-07:'
assert marker not in raw
rows={r['meeting']:r for r in review['results']};s=rows['S_R004S03C01'];l=rows['L_R003S01C02']
addition=f'''

{marker} the same two complete exposed public meetings remain strict development comparisons. A documented native SenseVoice `useItn=False` control changes full S38:47 raw CER7.6997%→6.9550%, and L39:23 chronological mixed-text diagnostic26.7635%→26.1296%; no fillers/er or reference text are removed. This is an output-format control, not an acoustic-model breakthrough or product default change.

Official Qwen3-ASR-0.6B-hf revision7f1569a48a89f3e3f4dc3a5c9d28bddd903bc76c now executes natively in existing Transformers5.22.1/Torch2.11ROCm10. CPU feature allocation failure and whole-file Windows1455 loading failure are retained. Supported GPU feature preparation was checked against an independent NumPy implementation. A bounded16MiB streamed reader verifies all611 BF16 tensor payloads by full GPU byte roundtrip, with deterministic buffers/tied embeddings preserved and a standard-versus-streamed tiny-model exact-logit/generation control. Successful native workers use about1.25GB Job private commit under the2GiB limit, with5% worker CPU and actual Windows low-memory protection; GPU utilization is not hard capped. Bare-model all-zero silence hallucinated “嗯”; the exact-zero-only input guard does not claim to solve noisy silence, and preserves even one-PCM16-LSB nonzero input.

The immutable fixed30s native run completed S with full chronological strict CER6.43844% (536/8325 edits), but failed on L1020–1050s:512 generated tokens with repeated acknowledgements and no natural EOS. Native inference alone therefore does not establish that repetition was an export problem. The incomplete complex run has no full CER, and its raw failed output remains in practical-qwen-signal-r3. Parsed-decoder repetition cleanup was never used to turn that failure into a final result.

The separately frozen practical-qwen-bounded-r4 policy keeps failed raw nodes and bisects their entire original input, at most two levels with7.5s minimum children. The existing20-copy/1..8-token short-control repetition rule stops a failed loop early without changing its generated prefix. Every accepted leaf retains all raw text. Missing EOS or repeated output at the bound remains a failure. Actual ordinary first30s generated IDs/text match exactly; the failed real30s recovered as two natural-EOS15s leaves. In the complete new comparison, S's whole shared Document is byte-identical with0new neural calls for migration, while all79 L roots complete, only root34 requiring recovery. Time bisection is not overlap-voice separation.

Final whole S CER is{s['rawChronologicalCerNativeQwen']*100:.5f}%; L chronological mixed-text diagnostic is{l['rawChronologicalCerNativeQwen']*100:.5f}% ({l['editsNativeQwen']}/8676 edits). L's overlapping reference utterances have no unique merged word order, so this is not per-person or overlap acceptance. All text speakers remain unknown; no verified word alignment, person labels or factual minutes were added. Known combined owned ASR process-family time including interrupted attempts is{s['knownCombinedAsrProcessFamilySecondsIncludingInterruptedAttempts']:.6f}s for S and{l['knownCombinedAsrProcessFamilySecondsIncludingInterruptedAttempts']:.6f}s for L; shared pilot{review['sharedPilotOwnedProcessFamilySeconds']:.6f}s is separate. Actual memory-recovery/manual engineering waits, scoring, transfer and minutes are excluded; one externally aborted controller has censored duration. S's1.3s cached reconstruction is not38:47 of new ASR in1.3s. These are not stop-recording-to-final-summary timings.

Both complete outputs pass the real shared Rust Document parser. An isolated public-tree check reopens the identical complete output with0models, and missing committed raw nodes refuse twice without neural fallback, retaining the existing complete output. The real independent command refuses while the new native full worker is active, before launching another model. No installed Windows/Android default, card, real customer trial or final holdout was changed. Read evidence/20261107-practical-cpu/practical-qwen-bounded-r4/review.json and next-direction.json. Strict text5%, aligned people/overlap words, factual minutes, prior AMI31.0766% diarization cross-corpus failure, actual mobile/card and sale gates remain open. Continue the original backlog; do not begin blind training or call this sale-qualified.
'''
assert path.read_text(encoding='utf8')==raw;path.write_text(raw+addition,encoding='utf8')
print(json.dumps({'state':direction['state'],'nextCheckpointRun':False,'readmeUpdatedFromActualReview':True}))
