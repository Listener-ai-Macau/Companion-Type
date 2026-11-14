"""Local adapter CLI for normalized recorder PCM and existing WAV files.
No microphone/card/cloud access. A frontend decoder may call PcmSession directly.
"""
from pathlib import Path
import argparse, hashlib, json, time, uuid, wave
from companion_local_pcm_session_20261114 import PcmSession, atomic_json

def sha(path):
    with Path(path).open('rb') as file:return hashlib.file_digest(file,'sha256').hexdigest()

def replay_wav(session,audio_path,*,pace=False,from_frame=0,seal=True,stop_after_frames=None):
    state=session.state();assert not state['sealed']
    before=sha(audio_path);began=time.perf_counter();packets=0
    with wave.open(str(audio_path),'rb') as audio:
        assert (audio.getnchannels(),audio.getsampwidth(),audio.getframerate(),audio.getcomptype())==(1,2,16000,'NONE')
        total=audio.getnframes();assert 0<=from_frame<=state['confirmedFrames']<=total
        # A resumed transport is allowed only for the exact already confirmed
        # prefix of this source; changing files is an explicit conflict.
        remaining=state['confirmedFrames']*2
        with session.audio.open('rb') as recorded:
            while remaining:
                chunk=audio.readframes(min(16000,remaining//2))
                assert recorded.read(len(chunk))==chunk,'Confirmed source prefix differs from replay file'
                remaining-=len(chunk)
        audio.setpos(from_frame);offset=from_frame
        end=total if stop_after_frames is None else min(total,from_frame+stop_after_frames)
        while offset<end:
            pcm=audio.readframes(min(1600 if pace else 16000,end-offset));assert pcm
            session.append(offset,pcm);offset+=len(pcm)//2;packets+=1
            if pace:time.sleep(max(0,(offset-from_frame)/16000-(time.perf_counter()-began)))
    if seal:
        assert offset==total,'A partial source must not send EOS'
        session.seal(total)
    assert sha(audio_path)==before
    return {'state':'LOCAL_PCM_SOURCE_SEALED' if seal else 'LOCAL_PCM_PARTIAL_INTAKE_SAVED',
            'sourceAudio':str(audio_path),'sourceAudioSha256':before,'startFrame':from_frame,
            'endFrame':offset,'totalFrames':total,'packets':packets,'paced':pace,
            'seconds':time.perf_counter()-began,'inferencePerformedByProducer':False,
            'sourceUploaded':False,'realCardTransferVerified':False}

def main():
    parser=argparse.ArgumentParser();commands=parser.add_subparsers(dest='command',required=True)
    create=commands.add_parser('create');create.add_argument('--session',type=Path,required=True)
    create.add_argument('--recording-id',default=None);create.add_argument('--language',choices=['auto','Chinese','English'],default='auto')
    for name in ['status','document','append','seal','reconcile','replay-wav']:
        command=commands.add_parser(name);command.add_argument('--session',type=Path,required=True)
        if name=='append':command.add_argument('--pcm-file',type=Path,required=True);command.add_argument('--start-frame',type=int,required=True)
        if name=='seal':command.add_argument('--total-frames',type=int,required=True)
        if name=='replay-wav':
            command.add_argument('--audio',type=Path,required=True);command.add_argument('--pace',action='store_true')
            command.add_argument('--from-frame',type=int,default=0);command.add_argument('--leave-open',action='store_true')
            command.add_argument('--stop-after-frames',type=int);command.add_argument('--receipt',type=Path)
    args=parser.parse_args()
    if args.command=='create':
        session=PcmSession.create(args.session,recording_id=args.recording_id or str(uuid.uuid4()),language=args.language)
        result=session.state()
    else:
        session=PcmSession(args.session)
        if args.command=='status':
            state=session.state();result={'confirmedFrames':state['confirmedFrames'],'sealed':state['sealed'],
                                         'pendingInferenceJobs':len(session.pending()),'localOnly':True}
        elif args.command=='document':result=session.document()
        elif args.command=='append':result=session.append(args.start_frame,args.pcm_file.read_bytes())
        elif args.command=='seal':session.seal(args.total_frames);result=session.state()
        elif args.command=='reconcile':result=session.reconcile()
        else:
            result=replay_wav(session,args.audio,pace=args.pace,from_frame=args.from_frame,
                              seal=not args.leave_open,stop_after_frames=args.stop_after_frames)
            if args.receipt:atomic_json(args.receipt,result)
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
