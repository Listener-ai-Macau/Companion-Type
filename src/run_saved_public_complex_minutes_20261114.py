"""Run the frozen installed product on a completed public ASR document.

This runner accepts no reference transcript, identity mapping or expected facts.
It preserves the normal application state and stops on actual Windows pressure.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse, hashlib, json, os, subprocess, time
import psutil
from moss_windows_resource_limits_20261104 import WorkerLimits, SystemRamPressure
from practical_io_20261107 import stop_owned_family

ROOT = Path('C:/Users/Billy/Desktop/Denzic/Companion')
APP = Path('E:/CodexData/Companion/.model-cache/complex-minutes20261114/product133-paraformer-baseline/app')
BINARIES = {'companion-type.exe': '3750a18d0924db1060f97ccba8d38c6db7c4a2e48d9b8689db6a44027d4e09f5',
            'companion_type_lib.dll': 'c37dafa6f88eb7a8ba14591f39f722a633a936bfdf5241382dd9d8a1d5cc8876'}
read = lambda p: json.loads(p.read_text(encoding='utf-8'))
now = lambda: datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')

def sha(path):
    with path.open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--document', type=Path, required=True)
    parser.add_argument('--audio', type=Path, required=True)
    parser.add_argument('--audio-sha256', required=True)
    parser.add_argument('--duration-seconds', type=float, required=True)
    parser.add_argument('--public-session', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert args.document.is_absolute() and args.audio.is_absolute() and args.output.is_absolute()
    assert not args.output.exists(), 'Retain earlier calls; no automatic retries'
    assert args.duration_seconds > 0 and sha(args.audio) == args.audio_sha256
    assert all(sha(APP / name) == value for name, value in BINARIES.items())
    document = read(args.document)
    assert document['isFinal'] and document['text'].strip()
    assert not document.get('unlocatedText'), 'Retain unresolved lexical rows before product import'
    limits = WorkerLimits(cpu_percent=5, memory_bytes=512 * 1024**2)
    args.output.mkdir(parents=True)
    template = read(ROOT / 'companion-device-closure055/apps/windows/src-tauri/src/calendar_test_fixtures/p738-sessions.json')[0]
    session = {**template, 'id': 'model-public-complex-' + args.public_session + '-20261114',
               'title': '公开会议 ' + args.public_session + '（复杂场景研究）',
               'source': 'importedTranscript', 'status': 'transcribed', 'processingPolicy': 'manual',
               'startedAt': None, 'stoppedAt': None, 'durationMs': round(args.duration_seconds * 1000),
               'audioPath': str(args.audio), 'audioBytes': args.audio.stat().st_size, 'audioStored': True,
               'transcriptText': document['text'], 'transcriptFinal': True,
               'transcriptPreview': document['text'][:160], 'utterances': document['utterances'],
               'transcriptSegments': len(document['utterances']), 'minutes': None, 'minutesByMode': {},
               'exportMarkdown': '', 'exportedAt': None, 'calendarCopies': [], 'calendarSlotCopies': [],
               'calendarCopyRevision': 0, 'noteRevision': 0, 'meetingNotes': [],
               'retention': {**template['retention'], 'audioCached': True, 'minutesCached': False}}
    state = args.output / 'sessions.json'
    write(state, [session])
    for name in ['recordings', 'local', 'temp']:
        (args.output / name).mkdir()
    settings = Path(os.environ['APPDATA']) / 'Companion Type/product-settings.json'
    settings_before = sha(settings) if settings.exists() else None
    env = {**os.environ, 'COMPANION_TYPE_STATE_PATH': str(state),
           'COMPANION_TYPE_RECORDING_DIR': str(args.output / 'recordings'),
           'LOCALAPPDATA': str(args.output / 'local'), 'TEMP': str(args.output / 'temp'),
           'TMP': str(args.output / 'temp'), 'COMPANION_TYPE_DISABLE_AUTO_RECOVERY': '1',
           'COMPANION_TYPE_DISABLE_AUTO_RECONNECT': '1'}
    env.pop('COMPANION_TYPE_PRODUCT_SETTINGS_PATH', None)
    record = {'at': now(), 'state': 'RUNNING_FROZEN_PRODUCT_PUBLIC_COMPLEX_MINUTES',
              'publicSession': args.public_session, 'sourceDocumentSha256': sha(args.document),
              'sourceAudioSha256': args.audio_sha256, 'binaries': BINARIES,
              'referenceAnswersSupplied': False, 'speakerNamesOrRecordingDateInvented': False,
              'newAsrCalls': 0, 'steps': [], 'normalLibraryTouched': False,
              'privateRecordingsUploaded': False, 'qualityQualified': False, 'saleQualified': False}
    pressure = SystemRamPressure()
    try:
        write(args.output / 'result.json', record)
        for mode in ['offlineStore', 'onlineLive']:
            assert not pressure.low(), 'Actual Windows low-memory signal before native call'
            request = {'action': 'meetingGenerateMinutes', 'sessionId': session['id'],
                       'meetingMode': mode, 'minutesTemplate': {'id': 'meeting'}}
            input_path = args.output / (mode + '-request.json')
            output = args.output / (mode + '-session.json')
            write(input_path, request)
            started = time.perf_counter()
            with (args.output / (mode + '.log')).open('xb') as log:
                process = subprocess.Popen([str(APP / 'companion-type.exe'), '--meeting-minutes-request',
                                            str(input_path), str(output)], env=env, cwd=APP,
                                           stdout=log, stderr=subprocess.STDOUT,
                                           creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS)
                try:
                    while process.poll() is None:
                        if pressure.low() or time.perf_counter() - started > 600:
                            raise RuntimeError('Owned native minutes stopped on actual memory pressure or deadline')
                        time.sleep(.5)
                finally:
                    if process.poll() is None:
                        stop_owned_family(process, psutil.Process(process.pid))
            record['steps'].append({'mode': mode, 'exitCode': process.returncode,
                                    'seconds': time.perf_counter() - started, 'outputExists': output.exists()})
            write(args.output / 'result.json', record)
            assert process.returncode == 0 and output.exists(), 'Native minutes incomplete; evidence retained'
            saved = read(output)
            assert saved['transcriptText'] == document['text'] and saved['utterances'] == document['utterances']
            mode_result = saved['minutesByMode'][mode]
            assert mode_result['status'] == 'minutesReady' and mode_result['processing']['complete']
            assert mode_result['processing']['processedSourceBytes'] == mode_result['processing']['sourceBytes']
            assert mode_result['markdown'].strip(), 'Check the requested mode rather than the default minutes field'
            record['steps'][-1].update(requestedModeReady=True, allSourceBytesProcessed=True,
                                        markdownSha256=hashlib.sha256(mode_result['markdown'].encode()).hexdigest())
        assert (sha(settings) if settings.exists() else None) == settings_before
        record.update(state='FROZEN_PRODUCT_COMPLEX_MINUTES_BOTH_MODES_SAVED_REVIEW_PENDING',
                      originalTranscriptUnchanged=True, settingsFileUnchanged=True)
    except BaseException as error:
        record.update(state='FROZEN_PRODUCT_COMPLEX_MINUTES_STOPPED_RETAINED', errorType=type(error).__name__,
                      error=str(error))
        raise
    finally:
        pressure.close()
        record.update(finishedAt=now(), limits=limits.query())
        write(args.output / 'result.json', record)
    print(json.dumps({'state': record['state'], 'steps': record['steps']}, ensure_ascii=False))

if __name__ == '__main__':
    main()
