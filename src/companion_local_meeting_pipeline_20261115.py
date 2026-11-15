"""Local complete-meeting command for the product's versioned model package.

One source timeline, durable incremental ASR cache, independent alignment and
speaker activity. Only the final document is printed; stage output stays local.
"""
from pathlib import Path
from datetime import datetime
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
import wave

os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
from companion_local_pcm_session_20261114 import PcmSession, atomic_json, exclusive_file
from companion_windows_power_request_20261115 import PowerLease
from moss_windows_resource_limits_20261104 import SystemRamPressure
from practical_io_20261107 import stop_owned_family
import psutil

SRC = Path(__file__).resolve().parent
read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
now = lambda: datetime.now().astimezone().isoformat(timespec='seconds')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run_stage(root, state, name, command, *, timeout, env=None):
    """Keep the owned child tree bounded and leave durable nodes on failure."""
    state.update(state='RUNNING_'+name.upper(), activeStage=name)
    atomic_json(root/'job.json', state)
    logs = root/'logs'
    logs.mkdir(exist_ok=True)
    log_path = logs/(name+'-'+str(time.time_ns())+'.log')
    child = owned = None
    pressure = SystemRamPressure()
    tick, peak = time.perf_counter(), 0
    try:
        if pressure.low():
            raise RuntimeError('Actual Windows low-memory signal; original audio and progress retained')
        with log_path.open('xb') as log:
            child = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            owned = psutil.Process(child.pid)
            state.update(activePid=child.pid, activePidCreatedAt=owned.create_time())
            atomic_json(root/'job.json', state)
            while child.poll() is None:
                if pressure.low() or (root/'stop.request').exists() or time.perf_counter()-tick > timeout:
                    stop_owned_family(child, owned)
                    raise InterruptedError('Owned local model stage stopped; durable source and completed nodes retained')
                try:
                    peak = max(peak, sum(p.memory_info().private for p in [owned]+owned.children(recursive=True)))
                except psutil.Error:
                    pass
                time.sleep(.5)
        if child.returncode:
            raise RuntimeError('Local '+name+' stage did not complete; inspect retained stage log')
    finally:
        if child is not None and child.poll() is None:
            stop_owned_family(child, owned)
        pressure.close()
        state.pop('activePid', None)
        state.pop('activePidCreatedAt', None)
        state.setdefault('attempts', []).append({'stage':name, 'exitCode':child.returncode if child else None,
            'seconds':time.perf_counter()-tick, 'privatePeakBytes':peak, 'log':str(log_path)})
        atomic_json(root/'job.json', state)


def canonical_audio(root, manifest):
    target = root/'input.wav'
    expected = manifest['files']
    for item in expected:
        assert sha(item['path']) == item['sha256'], 'Source audio changed'
    if target.exists():
        proof = read(root/'input-binding.json')
        assert proof['files'] == expected and sha(target) == proof['audioSha256']
        return proof
    pending = root/('input.pending-'+str(time.time_ns())+'.wav')
    digest = hashlib.sha256()
    frames = 0
    with wave.open(str(pending), 'wb') as output:
        output.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        for item in expected:
            with wave.open(item['path'], 'rb') as source:
                assert (source.getnchannels(),source.getsampwidth(),source.getframerate(),source.getcomptype()) == (1,2,16000,'NONE')
                assert source.getnframes()*2 == item['pcmBytes']
                while pcm := source.readframes(32000):
                    output.writeframesraw(pcm)
                    digest.update(pcm)
                    frames += len(pcm)//2
    pending.replace(target)
    proof = {'files':expected, 'audio':str(target), 'audioSeconds':frames/16000,
             'audioSha256':sha(target), 'pcmSha256':digest.hexdigest(), 'frames':frames,
             'allOriginalSamplesCopiedOnce':True, 'sourceUploaded':False}
    atomic_json(root/'input-binding.json', proof)
    return proof


def asr_session(root, bundle, audio):
    language = 'auto'
    for entry in bundle.get('completedPcmCaches', []):
        if entry['pcmSha256'] != audio['pcmSha256'] or entry['frames'] != audio['frames']:
            continue
        session = PcmSession(Path(entry['session']))
        if sha(session.audio) != audio['pcmSha256']:
            raise RuntimeError('Bound cached PCM changed')
        if session.state()['config']['language'] != language or not session.document()['isFinal']:
            continue
        return session, True
    session_path = root/'asr-session'
    stream_roots = bundle.get('ownedStreamRoots')
    if stream_roots is None:
        stream_root = bundle.get('streamRoot')
        stream_roots = sorted(str(p) for p in Path(stream_root).glob('*') if p.is_dir()) if stream_root else []
    if stream_roots:
        for path in [Path(p)/'audio.pcm' for p in stream_roots]:
            if not path.is_file(): continue
            if path.stat().st_size == audio['frames']*2 and sha(path) == audio['pcmSha256']:
                candidate = PcmSession(path.parent/'session')
                if candidate.meta.exists() and candidate.state()['config']['language'] == language:
                    # Rust holds leases for these same-owner stream roots for
                    # the entire finalization. Keep immutable absolute request
                    # bindings and original decoder nodes; audit resumed writes
                    # in that root's own ledger. No request/result is rewritten.
                    session_path = candidate.root
                    atomic_json(root/'stream-cache-lineage.json',{
                        'session':str(candidate.root), 'pcmSha256':audio['pcmSha256'],
                        'frames':audio['frames'], 'confirmedFramesBeforeResume':candidate.state()['confirmedFrames'],
                        'completedFinalBlocksBeforeResume':sum(1 for p in (candidate.root/'results').glob('*.json') if read(p)['request']['blockFinal']),
                        'immutableRequestsRewritten':False, 'sameOwnerNativeLeaseHeld':True})
                    break
    if session_path.exists():
        session = PcmSession(session_path)
        session.reconcile()
    else:
        session = PcmSession.create(session_path, recording_id=str(uuid.uuid5(uuid.NAMESPACE_URL, audio['pcmSha256'])), language=language)
    if not session.state()['sealed']:
        with wave.open(audio['audio'], 'rb') as source:
            confirmed = session.state()['confirmedFrames']
            with session.audio.open('rb') as stored:
                remaining = confirmed
                while remaining:
                    pcm = source.readframes(min(32000, remaining))
                    assert pcm == stored.read(len(pcm)), 'Resume source differs'
                    remaining -= len(pcm)//2
            offset = confirmed
            while pcm := source.readframes(32000):
                session.append(offset, pcm)
                offset += len(pcm)//2
        session.seal(audio['frames'])
    return session, False


def alignment_plan(root, bundle, session, audio, case):
    expected = bundle['asrInferenceBinding']
    selected = {}
    for path in (session.root/'results').glob('*.json'):
        packet = read(path)
        request = packet['request']
        if request['blockFinal'] and packet['result'].get('accepted') is True:
            selected[request['block']] = packet
    leaves = []
    for block, packet in sorted(selected.items()):
        assert packet['inferenceBinding'] == expected, 'Do not mix model/language/runtime cache bindings'
        request, result = packet['request'], packet['result']
        session.read_request_pcm(request)
        unconfirmed=result.get('unconfirmedAudioIntervals',[])
        if result.get('reviewRequired'):
            assert unconfirmed, 'Unconfirmed decoder state needs explicit original audio ranges'
        for leaf in result['leaves']:
            node_file = session.root/'decode'/request['jobId']/(leaf['node']+'.json')
            node = read(node_file)
            raw = node['raw']
            if any(r['startFrame']==raw['startSample'] and r['endFrame']==raw['endSample'] for r in unconfirmed):
                assert raw['text']=='', 'Do not promote failed or unconfirmed nonempty decoding'
            assert node['binding'] == {**expected,'jobId':request['jobId'],
                'pcmSha256':request['pcmSha256'],'configSha256':request['configSha256']}
            canonical = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(',',':')).encode()
            assert hashlib.sha256(canonical).hexdigest() == node['rawSha256']
            language = raw.get('language') or 'Chinese'
            assert language in {'Chinese','English'}, 'Language outside this installed bilingual package'
            leaves.append({'id':str(block).zfill(6)+'-'+leaf['node'], 'nodeFile':str(node_file),
                'nodeSha256':sha(node_file), 'text':raw['text'], 'startSample':raw['startSample'],
                'endSample':raw['endSample'], 'alignmentLanguage':language})
    document = session.document()
    assert document['isFinal']
    assert leaves[0]['startSample'] == 0 and leaves[-1]['endSample'] == audio['frames']
    assert all(a['endSample'] == b['startSample'] for a,b in zip(leaves,leaves[1:]))
    assert document['text'] == '\n'.join(l['text'] for l in leaves)
    source = root/'source-asr.json'
    atomic_json(source, document)
    control = root/'alignment'
    control.mkdir(exist_ok=True)
    template = Path(bundle['alignmentTemplate'])
    for name in ['model-source.json','preparation.json','tiny-loader-proof.json']:
        if not (control/name).exists():
            shutil.copy2(template/name,control/name)
    plan = [{**case,'sourceDocument':str(source),'sourceDocumentSha256':sha(source),'leaves':leaves}]
    atomic_json(control/'audio-text-only.json',plan)
    protocol = read(template/'protocol.json')
    protocol.update(workerSourceSha256=sha(SRC/'practical_bilingual_alignment_worker_20261115.py'),
                    inputPlanSha256=sha(control/'audio-text-only.json'),
                    inputSelection='Complete same-session automatic Chinese/English ASR text, no references/person labels',
                    pilotRule='First nonempty actual source leaf, character conservation and valid predicted onsets',
                    fullRule='Complete original source timeline; same model and loading, language per recognized source leaf')
    atomic_json(control/'protocol.json',protocol)
    return control, plan[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, required=True)
    args = parser.parse_args()
    manifest, bundle = read(args.manifest), read(args.bundle)
    assert bundle['schema'] == 'companion.local-meeting-bundle.v1'
    for file, digest in bundle['sourceFiles'].items():
        assert sha(file) == digest, 'Installed model package source changed'
    owned_root = manifest.get('artifactRoot')
    if owned_root:
        from companion_local_cache_audit_20261115 import activate
        activate(owned_root, SRC/'cache-audit-hook', owned_stream_roots=manifest.get('ownedStreamRoots', []))
        bundle = {**bundle, 'ownedStreamRoots':manifest.get('ownedStreamRoots', [])}
    if manifest['schema'] == 'companion.local-meeting-stream.v1':
        from companion_local_meeting_stream_20261115 import run
        run(manifest,bundle)
        return
    assert manifest['schema'] == 'companion.local-meeting-input.v1'
    assert manifest['localOnly'] is True and manifest['finalize'] is True and manifest['language'] == 'auto'
    assert manifest['files'] and all(set(x) == {'path','sha256','pcmBytes'} for x in manifest['files'])
    binding = {'inputSha256':sha(args.manifest), 'bundleSha256':sha(args.bundle)}
    # Paths may change on reimport, so content and configuration identify work.
    identity = hashlib.sha256(json.dumps({'sources':[x['sha256'] for x in manifest['files']],
                                         'bundle':binding['bundleSha256']},sort_keys=True).encode()).hexdigest()
    root = Path(owned_root) if owned_root else Path(bundle['workRoot'])/identity
    root.mkdir(parents=True, exist_ok=True)
    with exclusive_file(Path(bundle['workRoot'])/'local-meeting-pipeline.lock'), exclusive_file(root/'pipeline.lock'), PowerLease():
        target = root/'job.json'
        state = read(target) if target.exists() else {'state':'PREPARING_LOCAL_MEETING','startedAt':now(),'attempts':[]}
        state.update(binding=binding,localOnly=True,sourceUploaded=False,qualityQualified=False)
        if (root/'final-binding.json').exists():
            final = read(root/'final-binding.json')
            assert sha(root/'final-document.json') == final['documentSha256']
            assert final['bundleSha256'] == binding['bundleSha256']
            # Even a cache hit verifies every declared source before returning.
            for item in manifest['files']: assert sha(item['path']) == item['sha256']
            print((root/'final-document.json').read_text(encoding='utf-8'), end='')
            return
        try:
            audio = canonical_audio(root, manifest)
            case = {k:audio[k] for k in ['audio','audioSeconds','audioSha256']}
            case['meeting'] = 'local-'+identity[:16]
            session, reused = asr_session(root, bundle, audio)
            state.update(asrSession=str(session.root), adoptedCompletedAsrCache=reused)
            atomic_json(root/'job.json',state)
            timeout = min(43200, audio['audioSeconds']*2+300)
            if session.pending():
                inventory = root/('asr-inventory-'+str(time.time_ns()))
                run_stage(root,state,'asr-inventory',[sys.executable,str(SRC/'run_practical_qwen_native_20261107.py'),
                    '--phase','inventory','--control',str(inventory)],timeout=120)
                run_stage(root,state,'asr',[sys.executable,str(SRC/'run_local_pcm_decoder_20261114.py'),
                    '--session',str(session.root),'--inventory',str(inventory/'hip-inventory.json'),
                    '--run',str(root/('asr-run-'+str(time.time_ns()))),'--deadline-seconds',str(min(14400,timeout))],timeout=timeout)
            assert session.document()['isFinal'], 'Full original audio is not yet decoded'
            alignment, plan = alignment_plan(root,bundle,session,audio,case)
            if not (alignment/'full-state.json').exists() or read(alignment/'full-state.json')['state'] != 'COMPLETE_NATIVE_ALIGNMENT_FULL_NOT_TIME_QUALIFIED':
                inventory = root/('align-inventory-'+str(time.time_ns()))
                run_stage(root,state,'align-inventory',[sys.executable,str(SRC/'run_practical_qwen_native_20261107.py'),
                    '--phase','inventory','--control',str(inventory)],timeout=120)
                run_stage(root,state,'alignment',[sys.executable,str(SRC/'run_bilingual_alignment_20261115.py'),
                    '--control',str(alignment),'--inventory',str(inventory/'hip-inventory.json')]
                    +(['--resume'] if (alignment/'run.json').exists() else []),timeout=timeout)
            # Speaker stage is replaceable; a completed research result is only
            # reused for exactly the same audio and bound producer/model policy.
            journal = None
            posterior = None
            producer_file = None
            for entry in bundle.get('completedSpeakerCaches',[]):
                if entry['pcmSha256'] == audio['pcmSha256'] and entry['frames'] == audio['frames']:
                    assert sha(entry['file']) == entry['sha256'] and sha(entry['producer']) == entry['producerSha256']
                    journal = Path(entry['file'])
                    posterior = Path(entry['posteriorDirectory'])
                    producer_file = Path(entry['producer'])
                    break
            if journal is None:
                speaker = root/'speaker'
                if not speaker.exists():
                    speaker.mkdir()
                    protocol = read(bundle['speakerProtocol'])
                    protocol['probabilityCacheRoot'] = str(root/'speaker-posteriors')
                    atomic_json(speaker/'protocol.json',protocol)
                    atomic_json(speaker/'audio-only.json',[case])
                terminal = speaker/'results'/case['meeting']/'completed-state.json'
                if not terminal.exists() or read(terminal)['state'] != 'COMPLETE_CPU_SPEAKER_JOURNAL_UNQUALIFIED':
                    with exclusive_file(Path('E:/CodexData/Companion/.model-cache/local-qwen-decoder.lock')):
                        run_stage(root,state,'speaker',[sys.executable,str(SRC/'run_practical_nemotron_20261107.py'),
                            '--control',str(speaker),'--native-control-proof',bundle['speakerExecutionProof']],timeout=timeout)
                journal = speaker/'results'/case['meeting']/'speaker-journal.json'
                posterior = root/'speaker-posteriors'/case['meeting']
                producer_file = terminal
            # The pure join keeps every ASR character. Approximate word times
            # and anonymous identities remain explicit in the saved evidence.
            from companion_local_speaker_document_20261114 import join_aligned_recording
            from companion_exclusive_journal_20261114 import exclusive_journal
            from practical_nemotron_worker_20261107 import probability_segments
            import numpy as np
            raw_journal = read(journal)
            original_sha = raw_journal['audioSha256']
            if original_sha != case['audioSha256']:
                # Exact PCM equality was bound in the installed cache entry;
                # only the WAV container/header differs. Preserve that lineage.
                atomic_json(root/'speaker-container-binding.json',{
                    'originalJournal':str(journal),'originalJournalSha256':sha(journal),
                    'originalAudioSha256':original_sha,'canonicalAudioSha256':case['audioSha256'],
                    'verifiedIdenticalPcmSha256':audio['pcmSha256']})
                raw_journal = {**raw_journal,'audioSha256':case['audioSha256']}
            probability = read(posterior/'probabilities.json')
            assert probability['audioSha256'] == original_sha
            array = np.load(posterior/'probabilities.npy',mmap_mode='r',allow_pickle=False)
            frames = probability['committedFrames']
            assert hashlib.sha256(memoryview(array[:frames]).cast('B')).hexdigest() == probability['committedPrefixSha256']
            cadence = read(producer_file)['nativeSecondsPerFrame']
            assert probability_segments(array,frames,cadence,case['audioSeconds'],.5) == raw_journal['segments']
            exclusive, derivation = exclusive_journal(array,frames=frames,seconds_per_frame=cadence,source_journal=raw_journal)
            atomic_json(root/'exclusive-speaker-view.json',exclusive)
            atomic_json(root/'exclusive-derivation.json',derivation)
            payloads = [read(alignment/'aligned'/case['meeting']/(leaf['id']+'.json'))['payload'] for leaf in plan['leaves']]
            document, trace = join_aligned_recording(read(plan['sourceDocument']),plan['leaves'],payloads,raw_journal,
                audio_seconds=case['audioSeconds'],audio_sha256=case['audioSha256'],attribution_journal=exclusive)
            unrecognized=[]
            for packet in (session.root/'results').glob('*.json'):
                value=read(packet)
                if not value['request']['blockFinal'] or not value['result'].get('accepted'):continue
                for interval in value['result'].get('unconfirmedAudioIntervals',[]):
                    unrecognized.append({'startMs':interval['startFrame']//16,
                        'endMs':(interval['endFrame']+15)//16,'source':'本地识别待核对'})
            unrecognized.sort(key=lambda row:(row['startMs'],row['endMs']))
            assert bool(unrecognized)==bool(session.document()['reviewRequired'])
            document.update(reviewRequired=bool(unrecognized),unrecognizedAudio=unrecognized,qualityQualified=False)
            assert document['text'] == ''.join(r['text'] for r in document['utterances'])
            atomic_json(root/'attribution-evidence.json',trace)
            atomic_json(root/'final-document.json',document)
            atomic_json(root/'final-binding.json',{'documentSha256':sha(root/'final-document.json'),
                'bundleSha256':binding['bundleSha256'],'inputPcmSha256':audio['pcmSha256'],
                'speakerJournalSha256':sha(journal),'qualityQualified':False})
            state.update(state='COMPLETE_LOCAL_MEETING_REVIEW_REQUIRED_UNQUALIFIED' if unrecognized else 'COMPLETE_LOCAL_MEETING_CANDIDATE_NOT_QUALITY_QUALIFIED',finishedAt=now(),
                         documentSha256=sha(root/'final-document.json'))
            atomic_json(target,state)
            print(json.dumps(document,ensure_ascii=False))
        except BaseException as error:
            state.update(state='INCOMPLETE_LOCAL_MEETING_RETAINED',error=repr(error),finishedAt=now())
            atomic_json(target,state)
            raise


if __name__ == '__main__':
    main()
