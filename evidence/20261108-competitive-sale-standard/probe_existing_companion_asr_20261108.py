"""One bounded silence probe; use only Companion's existing legacy provider bundle."""
from pathlib import Path
from datetime import datetime
import asyncio
import ctypes
import ctypes.wintypes as w
import json
import logging
import struct
import time
import uuid
from websockets.legacy.client import Connect
from websockets.exceptions import InvalidStatusCode

OUTPUT = Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261108-competitive-sale-standard/existing-service-probe.json')
logging.getLogger('websockets').setLevel(logging.CRITICAL)

class ProbeFailure(Exception):
    pass

class NoRedirect(Connect):
    def handle_redirect(self, uri):
        raise ProbeFailure('REDIRECT_REJECTED')

class Credential(ctypes.Structure):
    _fields_ = [('Flags',w.DWORD),('Type',w.DWORD),('TargetName',w.LPWSTR),('Comment',w.LPWSTR),('LastWritten',w.FILETIME),('CredentialBlobSize',w.DWORD),('CredentialBlob',ctypes.POINTER(ctypes.c_ubyte)),('Persist',w.DWORD),('AttributeCount',w.DWORD),('Attributes',ctypes.c_void_p),('TargetAlias',w.LPWSTR),('UserName',w.LPWSTR)]

def existing_provider():
    api = ctypes.WinDLL('Advapi32', use_last_error=True)
    api.CredReadW.argtypes = [w.LPCWSTR,w.DWORD,w.DWORD,ctypes.POINTER(ctypes.POINTER(Credential))]
    api.CredReadW.restype = w.BOOL
    api.CredFree.argtypes = [ctypes.c_void_p]
    ptr = ctypes.POINTER(Credential)()
    if not api.CredReadW('credentials.v1.chunk.0.com.listener.type', 1, 0, ctypes.byref(ptr)):
        raise ProbeFailure('EXISTING_CREDENTIAL_NOT_FOUND')
    try:
        size = ptr.contents.CredentialBlobSize
        if not 0 < size <= 2560 or size % 2:
            raise ProbeFailure('CREDENTIAL_FORMAT_UNSUPPORTED')
        raw = ctypes.string_at(ptr.contents.CredentialBlob, size)
    finally:
        api.CredFree(ptr)
    try:
        data = json.loads(raw.decode('utf-16-le').rstrip('\x00'))['providers']['asr']['volcengine']
        values = tuple(str(data.get(k, '')).strip() for k in ['appKey', 'accessKey', 'resourceId'])
    except (ValueError, KeyError, UnicodeError):
        raise ProbeFailure('CREDENTIAL_FORMAT_UNSUPPORTED') from None
    if not all(values[:2]):
        raise ProbeFailure('EXISTING_CREDENTIAL_INCOMPLETE')
    if any('\r' in x or '\n' in x for x in values):
        raise ProbeFailure('CREDENTIAL_FORMAT_UNSUPPORTED')
    return values[0], values[1], values[2] or 'volc.seedasr.sauc.duration'

def frame(kind, flags, serial, body, sequence=None):
    header = bytes([0x11, kind << 4 | flags, serial << 4, 0])
    return header + (struct.pack('>i', sequence) if sequence is not None else b'') + struct.pack('>I', len(body)) + body

def parse(data):
    if not isinstance(data, bytes) or not 8 <= len(data) <= 4 * 1024**2 or data[0] >> 4 != 1:
        raise ProbeFailure('RESPONSE_PROTOCOL_INVALID')
    offset = (data[0] & 15) * 4
    kind, flags = data[1] >> 4, data[1] & 15
    if offset < 4 or data[2] & 15:
        raise ProbeFailure('RESPONSE_PROTOCOL_UNSUPPORTED')
    seq = None
    if flags in [1,3]:
        seq = struct.unpack_from('>i', data, offset)[0]
        offset += 4
    code = None
    if kind == 15:
        code = struct.unpack_from('>I', data, offset)[0]
        offset += 4
    size = struct.unpack_from('>I', data, offset)[0]
    offset += 4
    if len(data) != offset + size:
        raise ProbeFailure('RESPONSE_PROTOCOL_INVALID')
    if code is not None:
        raise ProbeFailure('PROVIDER_ERROR_' + str(code))
    return kind, flags in [2,3] or seq is not None and seq < 0, json.loads(data[offset:])

async def probe():
    app, access, resource = existing_provider()
    seed = resource.lower().startswith('volc.seedasr.sauc.')
    endpoint = 'wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_' + ('nostream' if seed else 'async')
    ident = str(uuid.uuid4())
    headers = {'X-Api-App-Key': app, 'X-Api-Access-Key': access, 'X-Api-Resource-Id': resource, 'X-Api-Connect-Id': ident}
    if seed:
        headers['X-Api-App-Id'] = app
    request = {'model_name':'bigmodel','enable_itn':True,'enable_punc':True,'show_utterances':True,'enable_speaker_info':True,'result_type':'full'}
    if seed:
        request.update(reqid=ident, sequence=1, additions={'with_speaker_info':'True'})
    else:
        request['enable_nonstream'] = False
    audio = {'format':'pcm','rate':16000,'bits':16,'channel':1}
    audio.update({'sample_rate':16000} if seed else {'codec':'raw'})
    config = json.dumps({'user':{'uid':ident},'audio':audio,'request':request}, separators=(',',':')).encode()
    async with NoRedirect(endpoint, extra_headers=headers, open_timeout=8, close_timeout=2, max_size=4*1024**2, compression=None) as ws:
        await ws.send(frame(1, 0 if seed else 1, 1, config, None if seed else 1))
        async def receive():
            count = 0
            async for data in ws:
                kind, final, value = parse(data)
                if kind == 9:
                    count += 1
                    if final:
                        if not isinstance(value, dict) or not isinstance(value.get('result'), (dict,list)):
                            raise ProbeFailure('FINAL_RESPONSE_INVALID')
                        return count
            raise ProbeFailure('NO_FINAL_RESPONSE')
        receiving = asyncio.create_task(receive())
        try:
            for i in range(10):
                flags = (2 if i == 9 else 0) if seed else 1
                await ws.send(frame(2, flags, 0, bytes(3200), None if seed else i+2))
                await asyncio.sleep(.1)
            if not seed:
                await ws.send(frame(2, 3, 0, b'', -12))
            count = await receiving
        finally:
            if not receiving.done():
                receiving.cancel()
                await asyncio.gather(receiving, return_exceptions=True)
    return {'state':'EXISTING_SERVICE_SILENCE_PROBE_PASSED','responsePackets':count,'providerGeneration':'seed-asr-v2' if seed else 'bigmodel','endpoint':endpoint}

if __name__ == '__main__':
    started = time.perf_counter()
    result = {'at':datetime.now().astimezone().isoformat(timespec='seconds'),'audio':'one_second_generated_zero_pcm16_16000_mono','privateAudioReadOrUploaded':False,'credentialsLoggedOrPersisted':False,'redirectsAllowed':False,'retryCount':0,'accuracyMeasured':False,'saleQualified':False,'productSettingsChanged':False}
    try:
        result.update(asyncio.run(asyncio.wait_for(probe(), timeout=25)))
    except InvalidStatusCode as e:
        result.update(state='SERVICE_HANDSHAKE_REJECTED', httpStatus=int(e.status_code))
    except ProbeFailure as e:
        result.update(state='SERVICE_PROBE_FAILED', reason=str(e))
    except asyncio.TimeoutError:
        result.update(state='SERVICE_PROBE_TIMEOUT')
    except Exception as e:
        result.update(state='SERVICE_PROBE_FAILED', failureType=type(e).__name__)
    result['wholeProcessProbeSeconds'] = time.perf_counter() - started
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps(result, ensure_ascii=False), flush=True)
