"""Five frozen public inputs through the installed Windows candidate's native CLI.

Engineering ASR comparator only: no UI, microphone, Bluetooth, new model,
training, reference text, cloud inference, or substitution of saved transcripts.
"""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,shutil,subprocess,sys,time,traceback,wave,zipfile
import psutil
S=Path(__file__).resolve().parents[3];O=S/'paired-product-asr-output';O.mkdir()
assert os.environ.get('GITHUB_ACTIONS')=='true' and os.name=='nt'
spec=json.loads((Path(__file__).parent/'input-spec.json').read_text(encoding='utf8'))
P=Path(os.environ['RUNNER_TEMP'])/'companion-paired-product-asr';P.mkdir()
now=lambda:datetime.now(timezone.utc).isoformat(timespec='seconds')
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def command(name,args):
    with (O/(name+'.log')).open('wb') as f:q=subprocess.run(list(map(str,args)),stdout=f,stderr=subprocess.STDOUT)
    assert q.returncode==0,name+' failed; retained log'
def asset(name,id,digest):
    target=P/name
    with target.open('wb') as f,(O/(name+'-download.log')).open('wb') as error:
        q=subprocess.run(['gh','api','repos/Listener-ai-Macau/Companion-Type/releases/assets/'+str(id),'-H','Accept: application/octet-stream'],stdout=f,stderr=error)
    assert q.returncode==0 and sha(target)==digest,'Frozen input asset mismatch'
    return target
state={'at':now(),'state':'PREPARING_FROZEN_PUBLIC_FIVE_INPUT_PRODUCT_ASR','testSource':os.environ['GITHUB_SHA'],'appSource':spec['app']['sourceCommit'],'appVersion':spec['app']['version'],'modelSha256':spec['model']['readyValue'],'completed':[],'newModelSelected':False,'trainingPerformed':False,'referencesOpened':False,'productDefaultChanged':False,'phoneOrBoardAccessed':False,'localOwnerComputerModelWorkers':0,'qualityQualified':False,'saleQualified':False}
def checkpoint():save(O/'result.json',state)
checkpoint()
try:
    native=P/'native';native.mkdir()
    command('download-frozen-product',['gh','run','download',spec['app']['buildRun'],'--repo','Listener-ai-Macau/Companion-Type','--name','companion-windows-candidate-'+spec['app']['sourceCommit'],'--dir',native])
    build=json.loads((native/'result.json').read_text(encoding='utf8'));assert build['sourceCommit']==spec['app']['sourceCommit']
    for row in build['nativeFiles']:assert sha(native/'windows-bin'/row['path'])==row['sha256']
    app=P/'app';app.mkdir();raw=(native/'windows-bin/companion-type.exe').read_bytes();assert raw.count(b'__TAURI_BUNDLE_TYPE_VAR_UNK')==1
    (app/'companion-type.exe').write_bytes(raw.replace(b'__TAURI_BUNDLE_TYPE_VAR_UNK',b'__TAURI_BUNDLE_TYPE_VAR_MSI'));shutil.copy2(native/'windows-bin/companion_type_lib.dll',app/'companion_type_lib.dll')
    assert sha(app/'companion-type.exe')==spec['app']['exeSha256'] and sha(app/'companion_type_lib.dll')==spec['app']['dllSha256']
    model=P/'model';model.mkdir();bundle=asset('model.zip',spec['model']['privateDraftAsset'],spec['model']['bundleSha256'])
    with zipfile.ZipFile(bundle) as z:
        assert set(z.namelist())==set(spec['model']['files'])|{'funasr-paraformer-large-zh-2024/ready'};z.extractall(model)
    for name,digest in spec['model']['files'].items():assert sha(model/name)==digest
    assert (model/'funasr-paraformer-large-zh-2024/ready').read_text(encoding='ascii').strip()==spec['model']['readyValue']
    audio=P/'public-audio';audio.mkdir();bundle=asset('public-audio.zip',spec['input']['privateDraftAsset'],spec['input']['sha256'])
    with zipfile.ZipFile(bundle) as z:
        assert set(z.namelist())=={'audio-only.json'}|{r['wav'] for r in spec['input']['cases']};z.extractall(audio)
    cases=json.loads((audio/'audio-only.json').read_text(encoding='utf8'));assert cases==spec['input']['cases']
    env={k:v for k,v in os.environ.items() if k not in ['GH_TOKEN','GITHUB_TOKEN','ACTIONS_RUNTIME_TOKEN','ACTIONS_ID_TOKEN_REQUEST_TOKEN','DEEPSEEK_API_KEY','OPENAI_API_KEY','COMPANION_TYPE_ASR_API_KEY','COMPANION_TYPE_VOLC_APP_KEY','COMPANION_TYPE_VOLC_ACCESS_KEY']}
    env.update(COMPANION_TYPE_LOCAL_ASR_DIR=str(model),COMPANION_TYPE_DISABLE_AUTO_RECOVERY='1',COMPANION_TYPE_DISABLE_AUTO_RECONNECT='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
    for case in cases:
        original=audio/case['wav'];assert sha(original)==case['sha256']
        with wave.open(str(original),'rb') as f:assert (f.getnchannels(),f.getframerate(),f.getsampwidth(),f.getnframes()/f.getframerate())==(1,16000,2,case['seconds'])
        root=P/case['id'];root.mkdir();recordings=root/'recordings';recordings.mkdir()
        for name in ['roaming','local','temp']:(root/name).mkdir()
        millis=round(case['seconds']*1000)
        row={'id':case['id'],'title':'Public paired '+case['id'],'source':'importedAudio','status':'saved','meetingMode':'offlineStore','processingPolicy':'manual','startedAt':None,'stoppedAt':None,'durationMs':millis,'audioPath':str(original),'audioBytes':original.stat().st_size,'audioStored':True,'chunks':[{'id':case['id']+'-original','path':str(original),'startedAt':None,'stoppedAt':None,'durationMs':millis,'bytes':original.stat().st_size,'status':'sealed'}],'transcriptText':'','transcriptPreview':'','transcriptSegments':0,'minutes':None,'exportMarkdown':'','exportedAt':None,'retention':{'audioCached':True,'transcriptCached':False,'minutesCached':False,'consentRequired':True,'retentionLabel':'Public engineering fixture only','expiresAt':None}}
        save(root/'sessions.json',[row]);request=root/'request.json';save(request,{'sessionId':case['id']});output=root/'native-result.json'
        own_env={**env,'APPDATA':str(root/'roaming'),'LOCALAPPDATA':str(root/'local'),'TEMP':str(root/'temp'),'TMP':str(root/'temp'),'COMPANION_TYPE_STATE_PATH':str(root/'sessions.json'),'COMPANION_TYPE_RECORDING_DIR':str(recordings),'COMPANION_TYPE_PRODUCT_SETTINGS_PATH':str(root/'product-settings.json')}
        state.update(state='RUNNING_FROZEN_PRODUCT_NATIVE_ASR',activeCase=case['id']);checkpoint();print('Starting '+case['id'],flush=True)
        resources=[];started=time.perf_counter();child=None;peak=0
        with (O/(case['id']+'-native.log')).open('wb') as log:
            try:
                child=subprocess.Popen([str(app/'companion-type.exe'),'--meeting-transcribe-request',str(request),str(output)],cwd=app,env=own_env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                owned=psutil.Process(child.pid)
                while child.poll() is None:
                    assert time.perf_counter()-started<900,'Case exceeded bounded fifteen-minute runtime'
                    try:
                        family=[owned]+owned.children(recursive=True);private=sum(p.memory_info().private for p in family);peak=max(peak,private)
                        assert private<3*1024**3,'Dedicated CI owned family exceeded3GiB'
                        resources.append({'seconds':time.perf_counter()-started,'privateBytes':private,'availableBytes':psutil.virtual_memory().available})
                    except psutil.NoSuchProcess:pass
                    time.sleep(.5)
            finally:
                if child is not None and child.poll() is None:
                    for p in owned.children(recursive=True):
                        try:p.kill()
                        except psutil.NoSuchProcess:pass
                    child.kill();child.wait()
        elapsed=time.perf_counter()-started;save(O/(case['id']+'-resources.json'),resources)
        if output.exists():shutil.copy2(output,O/(case['id']+'-native-result.json'))
        assert child.returncode==0 and output.exists(),'Native ASR failed; inspect retained log'
        result=json.loads(output.read_text(encoding='utf8'));assert result['operationError'] is None and result['transcriptionRequested'] and not result['deviceAccess']
        assert result['settings']['asrProvider']=='local-paraformer'
        rows=result['snapshot']['host']['sessions'];assert len(rows)==1 and rows[0]['id']==case['id'];actual=rows[0]
        assert actual['transcriptFinal'] and actual['transcriptText'].strip() and actual['utterances']
        assert actual['minutes'] is None and sha(original)==case['sha256']
        doc={'isFinal':True,'text':actual['transcriptText'],'utterances':actual['utterances'],'unrecognized':actual.get('transcriptUnrecognized',[])}
        target=O/(case['id']+'-output.json');save(target,doc)
        receipt={**case,'modelSha256':spec['model']['readyValue'],'outputSha256':sha(target),'transcriptSha256':hashlib.sha256(actual['transcriptText'].encode()).hexdigest(),'characters':len(actual['transcriptText']),'utterances':len(actual['utterances']),'elapsedSeconds':elapsed,'privatePeakBytes':peak,'sourceAudioUnchanged':True,'referencesPassed':False,'nativeExitCode':child.returncode,'scope':'Native product backend CLI; not ordinary UI/phone/diarization qualification'}
        save(O/(case['id']+'-complete.json'),receipt);state['completed'].append(receipt);checkpoint();print('Completed '+case['id']+' in '+str(round(elapsed,2))+'s',flush=True)
    state.pop('activeCase',None);state.update(state='COMPLETE_FIVE_FIXED_PRODUCT_ASR_INPUTS_UNSCORED',finishedAt=now());checkpoint()
except BaseException as error:
    state.update(state='INCOMPLETE_FIVE_INPUT_PRODUCT_ASR_RETAINED',error=repr(error),finishedAt=now());checkpoint();(O/'failure.txt').write_text(traceback.format_exc(),encoding='utf8');raise
