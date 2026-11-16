"""Durable local PCM intake shared by incremental and completed-file ASR.

No neural runtime, network, reference text, VAD dropping or lexical deduplication.
The receiver stays independent of the inference consumer. Growing-block drafts
are replaced by revision; closed blocks cover every confirmed sample once.
"""
from contextlib import contextmanager, ExitStack
from datetime import datetime, timezone
from pathlib import Path
import hashlib, json, os, time, uuid
from companion_local_paths_20261116 import local_path

RATE = 16000
FRAME_BYTES = 2
SCHEMA = 1

def digest(data):
    return hashlib.sha256(data).hexdigest()

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def atomic_json(path, value):
    path = Path(path)
    # Keep temporary names independent of a request's already long filename.
    # App cache roots include a64-character content hash; appending another
    # filename+UUID can exceed Windows MAX_PATH before the final path does.
    temporary = path.with_name('.tmp-'+uuid.uuid4().hex)
    with temporary.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    # A concurrent ordinary Windows reader can briefly deny rename/delete
    # sharing. Keep the fsynced new file and retry only the atomic commit;
    # never rewrite PCM or expose a partially written JSON to that reader.
    deadline = time.monotonic()+3
    while True:
        try:
            os.replace(temporary, path)
            break
        except PermissionError as error:
            if os.name!='nt' or error.winerror not in (5,32,33) or time.monotonic()>=deadline:
                raise
            time.sleep(.01)

class SessionConflict(ValueError):
    pass

@contextmanager
def exclusive_file(path):
    """OS-owned lock: a process crash releases ownership without a stale PID."""
    stream = Path(path).open('a+b')
    try:
        if stream.seek(0,os.SEEK_END)==0:
            stream.write(b'0'); stream.flush()
        stream.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as error:
            raise SessionConflict('Another operation owns this session lock') from error
        try:
            yield
        finally:
            stream.seek(0)
            if os.name=='nt':
                msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:
                fcntl.flock(stream.fileno(),fcntl.LOCK_UN)
    finally:
        stream.close()

class PcmSession:
    def __init__(self, directory):
        self.root = local_path(directory)
        self.meta = self.root/'session.json'
        self.audio = self.root/'audio.pcm'

    @classmethod
    def create(cls, directory, *, recording_id, language='auto', block_seconds=30, draft_seconds=5):
        if language not in ('auto','Chinese','English'):
            raise ValueError('Supported language modes: auto, Chinese, English')
        if not (type(block_seconds) is int and type(draft_seconds) is int
                and 1 <= draft_seconds <= block_seconds <= 30):
            raise ValueError('Bounded integral windows up to the original30s limit')
        recording_id = str(uuid.UUID(recording_id))
        session = cls(directory)
        session.root.mkdir(parents=True, exist_ok=False)
        for name in ['requests','results']:
            (session.root/name).mkdir()
        session.audio.touch(exist_ok=False)
        config = {'schema':SCHEMA, 'recordingId':recording_id, 'sampleRate':RATE,
                  'channels':1, 'sampleWidthBytes':FRAME_BYTES, 'language':language,
                  'blockFrames':block_seconds*RATE, 'draftFrames':draft_seconds*RATE}
        atomic_json(session.meta, {'config':config, 'configSha256':digest(json.dumps(config,sort_keys=True).encode()),
                    'confirmedFrames':0, 'sealed':False, 'createdAt':datetime.now(timezone.utc).isoformat()})
        return session

    @contextmanager
    def locked(self):
        # Intake/reconcile are short durable transactions. Waiting here is
        # limited to ownership acquisition; conflicts raised by the body
        # (gaps, changed replay bytes or EOS) must still fail immediately.
        deadline = time.monotonic()+3
        with ExitStack() as stack:
            while True:
                try:
                    stack.enter_context(exclusive_file(self.root/'intake.lock'))
                    break
                except SessionConflict as error:
                    if not isinstance(error.__cause__,OSError) or time.monotonic()>=deadline:
                        raise
                    time.sleep(.01)
            yield

    def state(self):
        value = read_json(self.meta)
        if value['config']['schema'] != SCHEMA or value['config']['sampleRate'] != RATE:
            raise SessionConflict('Unsupported audio/session contract')
        if value['configSha256'] != digest(json.dumps(value['config'],sort_keys=True).encode()):
            raise SessionConflict('Immutable session configuration changed')
        if self.audio.stat().st_size < value['confirmedFrames']*FRAME_BYTES:
            raise SessionConflict('Confirmed durable audio is missing; original state retained')
        return value

    def append(self, start_frame, pcm):
        if type(start_frame) is not int or start_frame < 0:
            raise ValueError('Absolute sample offset is required')
        if not isinstance(pcm,bytes) or not pcm or len(pcm)%FRAME_BYTES or len(pcm)>1024*1024:
            raise ValueError('One nonempty frame-aligned PCM16 packet, at most1MiB')
        with self.locked():
            value = self.state()
            if start_frame > value['confirmedFrames']:
                raise SessionConflict('Audio gap; request the missing interval before acknowledging this packet')
            first = start_frame*FRAME_BYTES
            end_frame = start_frame+len(pcm)//FRAME_BYTES
            if value['sealed'] and end_frame > value['confirmedFrames']:
                raise SessionConflict('Cannot append a new tail after EOS')
            # A crash may leave fsynced bytes after the last metadata commit.
            # Keep them, and require byte-identical replay before confirming.
            with self.audio.open('r+b') as stream:
                physical = stream.seek(0,os.SEEK_END)
                overlap = min(len(pcm), max(0,physical-first))
                stream.seek(first)
                if stream.read(overlap) != pcm[:overlap]:
                    raise SessionConflict('Retransmitted audio differs; retain both caller data and original file')
                if first+len(pcm)>physical:
                    stream.seek(physical); stream.write(pcm[overlap:]); stream.flush(); os.fsync(stream.fileno())
            previous = value['confirmedFrames']
            value['confirmedFrames'] = max(previous,end_frame)
            value['updatedAt'] = datetime.now(timezone.utc).isoformat()
            atomic_json(self.meta,value)
            self._publish(value)
            return {'confirmedFrames':value['confirmedFrames'], 'newFrames':value['confirmedFrames']-previous,
                    'duplicate':end_frame<=previous, 'unconfirmedTailBytes':self.audio.stat().st_size-value['confirmedFrames']*2}

    def seal(self, expected_total_frames):
        if type(expected_total_frames) is not int or expected_total_frames <= 0:
            raise ValueError('EOS must bind the exact capture length')
        with self.locked():
            value = self.state()
            if expected_total_frames != value['confirmedFrames'] or self.audio.stat().st_size != expected_total_frames*2:
                raise SessionConflict('EOS length differs from confirmed PCM; retain pending tail and request missing bytes')
            value['sealed'] = True
            value['sealedAt'] = datetime.now(timezone.utc).isoformat()
            atomic_json(self.meta,value)
            self._publish(value)

    def reconcile(self):
        """Publish work after an interrupted metadata/job transaction; no inference."""
        with self.locked():
            value = self.state(); self._publish(value)
            return {'confirmedFrames':value['confirmedFrames'], 'sealed':value['sealed'],
                    'unconfirmedTailBytes':self.audio.stat().st_size-value['confirmedFrames']*2}

    def _request(self, value, block, end, final):
        start = block*value['config']['blockFrames']
        job = f'{block:08d}-{end-start:08d}-'+('final' if final else 'draft')
        path = self.root/'requests'/(job+'.json')
        if path.exists():
            return
        with self.audio.open('rb') as stream:
            stream.seek(start*2); pcm = stream.read((end-start)*2)
        if len(pcm)!=(end-start)*2:
            raise SessionConflict('Confirmed source disappeared during request creation')
        atomic_json(path, {'schema':SCHEMA, 'jobId':job, 'recordingId':value['config']['recordingId'],
                          'configSha256':value['configSha256'], 'block':block, 'startFrame':start, 'endFrame':end,
                          'sourcePcm':str(self.audio), 'pcmSha256':digest(pcm),
                          'language':value['config']['language'], 'blockFinal':final,
                          'publishedAtMonotonic':time.perf_counter(),
                          'wholeRecordingFinal':False, 'speaker':None})

    def _publish(self,value):
        size = value['config']['blockFrames']; frames = value['confirmedFrames']
        previous = value.get('publishedFinalBlocks',0)
        for block in range(previous,frames//size):
            self._request(value,block,(block+1)*size,True)
        if frames//size != previous:
            value['publishedFinalBlocks'] = frames//size
            atomic_json(self.meta,value)
        tail = frames%size
        if tail:
            if value['sealed']:
                self._request(value,frames//size,frames,True)
            elif tail>=value['config']['draftFrames']:
                # Only the latest available revision is needed by a slow worker;
                # no waveform or decoded raw result is removed.
                end = frames-tail+(tail//value['config']['draftFrames'])*value['config']['draftFrames']
                self._request(value,frames//size,end,False)

    def pending(self):
        latest = {}
        for path in (self.root/'requests').glob('*.json'):
            job = read_json(path)
            key = job['block']; rank = (job['blockFinal'],job['endFrame'])
            if key not in latest or rank > latest[key][0]:
                latest[key] = (rank,job)
        pending = []
        for _,job in sorted(latest.values(),key=lambda pair:pair[1]['block']):
            if not (self.root/'results'/(job['jobId']+'.json')).exists():
                pending.append(job)
        return pending

    def read_request_pcm(self,job):
        if (not isinstance(job.get('jobId'),str) or Path(job['jobId']).name!=job['jobId']
                or not job['jobId'] or '..' in job['jobId']):
            raise SessionConflict('Invalid frozen request identifier')
        canonical=read_json(self.root/'requests'/(job['jobId']+'.json'))
        value=self.state()
        if (canonical!=job or job['configSha256']!=value['configSha256']
                or local_path(job['sourcePcm'])!=self.audio
                or not 0<=job['startFrame']<job['endFrame']<=value['confirmedFrames']
                or job['endFrame']-job['startFrame']>value['config']['blockFrames']):
            raise SessionConflict('Frozen source interval/configuration changed')
        with self.audio.open('rb') as stream:
            stream.seek(job['startFrame']*2);pcm=stream.read((job['endFrame']-job['startFrame'])*2)
        if digest(pcm)!=job['pcmSha256']:
            raise SessionConflict('Confirmed audio changed; raw results and source retained')
        return pcm

    def save_result(self, job, result, *, inference_binding):
        self.read_request_pcm(job)
        if not isinstance(result.get('text'),str) or 'rawGeneratedIds' not in result:
            raise ValueError('Retain raw text and generated IDs, including failed/empty decodes')
        record = {'request':job, 'inferenceBinding':inference_binding, 'result':result}
        path = self.root/'results'/(job['jobId']+'.json')
        if path.exists():
            if read_json(path) != record:
                raise SessionConflict('A completed raw result cannot be overwritten')
            return
        atomic_json(path,record)

    def document(self):
        value = self.state(); selected = {}
        for path in (self.root/'results').glob('*.json'):
            record = read_json(path); job = record['request']; block = job['block']
            if job['configSha256'] != value['configSha256']:
                raise SessionConflict('Result belongs to a different session configuration')
            if block not in selected or (job['blockFinal'],job['endFrame']) > (selected[block]['request']['blockFinal'],selected[block]['request']['endFrame']):
                selected[block] = record
        rows = []; covered = 0; all_final = True; bindings = set()
        for block,record in sorted(selected.items()):
            job = record['request']; result = record['result']
            contiguous = job['startFrame']==covered
            all_final = all_final and contiguous and job['blockFinal'] and result.get('accepted') is True
            if contiguous and job['blockFinal'] and result.get('accepted') is True:
                covered = job['endFrame']
            bindings.add(json.dumps(record['inferenceBinding'],sort_keys=True))
            rows.append({'text':result['text'], 'startMs':job['startFrame']/16,'endMs':job['endFrame']/16,
                         'speaker':None,'approximateTiming':True,'block':block,'revision':job['jobId'],
                         'blockFinal':job['blockFinal'],'language':result.get('language'),
                         'decodeAccepted':result.get('accepted') is True,
                         'reviewRequired':result.get('reviewRequired',False),
                         'unconfirmedAudioIntervals':result.get('unconfirmedAudioIntervals',[])})
        if len(bindings)>1:
            raise SessionConflict('Do not merge different model/runtime/language-policy results')
        final = bool(value['sealed'] and all_final and covered==value['confirmedFrames'] and rows)
        return {'isFinal':final,'text':'\n'.join(row['text'] for row in rows),'utterances':rows,
                'confirmedAudioFrames':value['confirmedFrames'],'finalDecodedFrames':covered,
                'audioSealed':value['sealed'],'speakerIdentityVerified':False,
                'reviewRequired':any(row['reviewRequired'] for row in rows),
                'wordTimingVerified':False,'qualityQualified':False}

def parse_generated_tokens(ids, tokenizer, *, language='auto'):
    """Extract protocol metadata without the upstream repetition-fixing parser."""
    text = tokenizer.decode(ids,skip_special_tokens=True,clean_up_tokenization_spaces=False)
    if language != 'auto':
        return {'text':text,'language':language,'languageHeaderPresent':False}
    marker = tokenizer.convert_tokens_to_ids('<asr_text>')
    if marker is not None and marker in ids:
        index = ids.index(marker)
        header = tokenizer.decode(ids[:index],skip_special_tokens=True,clean_up_tokenization_spaces=False).strip()
        body = tokenizer.decode(ids[index+1:],skip_special_tokens=True,clean_up_tokenization_spaces=False)
        if header.startswith('language '):
            detected = header[len('language '):].strip()
            return {'text':body,'language':None if detected=='None' else detected,'languageHeaderPresent':True}
    # A malformed/absent header must never erase actual spoken words.
    return {'text':text,'language':None,'languageHeaderPresent':False}
