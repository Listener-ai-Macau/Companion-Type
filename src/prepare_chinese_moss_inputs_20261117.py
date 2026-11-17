"""Source-bound Chinese MOSS target/token contract, without a neural runtime.

Exports the official conversation schema. Single original utterances carry an
anonymous S01 local to each clip; this is not multi-person diarization training.
The actual GPU frontend, native labels, gradients and training remain unproven.
"""
from pathlib import Path
from datetime import datetime
from decimal import Decimal
import argparse,ast,hashlib,json,os,re,shutil,sys,time,wave
os.environ.update(TOKENIZERS_PARALLELISM='false',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
from meeting_acoustic_contract_20261116 import read,require,sha,padded_labels
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from durable_model_state_20261117 import atomic_json

R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
O=E/'meeting-domain-data-r1/alimeeting-official-intake-r2/range-training-cohort-r2'
N=E/'native-model'
UPSTREAM={
    'finetune.py':'fe94110d41ab8851d2afd24089236b1f493cbaad',
    'FINETUNING.md':'187c1bd926f202ddde5b99fc55e277841d707a54',
    'inference_utils.py':'f59091c6521b0b5606b35e9f789213056ce155ec'}

def literal_assignment(tree,name):
    node=next(n for n in tree.body if isinstance(n,ast.Assign)
              and any(isinstance(t,ast.Name) and t.id==name for t in n.targets))
    return ast.literal_eval(node.value)

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
    pressure=SystemRamPressure();a.output.mkdir(parents=True,exist_ok=False)
    began=time.monotonic();state={'state':'PREPARING_CHINESE_MOSS_CONVERSATIONS_NO_MODEL',
        'at':datetime.now().astimezone().isoformat(),'examples':0,'newNeuralCalls':0,
        'parameterUpdates':0,'modelTrainingAdmitted':False,'qualityQualified':False}
    def stop():
        import psutil
        require(time.monotonic()-began<180,'Bounded three-minute metadata preparation')
        require(not pressure.low() and psutil.virtual_memory().available>=3414499000,'Original low-RAM guard')
        require(shutil.disk_usage(a.output).free>=50*1024**3,'Original disk reserve')
        require(not(a.output/'stop.request').exists(),'Owned stop requested')
    def save(**values):
        state.update(values,observedAt=datetime.now().astimezone().isoformat(),limits=limits.query())
        atomic_json(a.output/'state.json',state)
    try:
        stop();save();proof=read(O/'integrity-r1/completed.json')
        require(proof['state']=='PASS_5027_ORIGINAL_CHINESE_ASR_INPUTS_SOURCE_TEXT_PCM_TIMING_AND_PERSON_INTEGRITY'
            and proof['verifiedExamples']==5027 and proof['verifiedFrames']==345643200
            and proof['participantIntersection']==[],'Verified original inputs missing')
        manifest=Path(proof['manifest']);require(sha(manifest)==proof['manifestSha256'],'Original training manifest changed')
        model=read(J/'preparation.json')
        for entry in model['files']:require(sha(entry['file'])==entry['sha256'],'Pinned model tokenizer/config changed')
        upstream=a.output.parent/'upstream';upstream_receipts=[]
        for name,expected in UPSTREAM.items():
            f=upstream/name;raw=f.read_bytes()
            actual=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
            require(actual==expected,'Official source blob differs: '+name)
            upstream_receipts.append({'file':str(f),'gitBlobSha1':actual,'sha256':sha(f)})
        tree=ast.parse((upstream/'finetune.py').read_text(encoding='utf-8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='ConversationDataset')
        parse=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_parse');parse.decorator_list=[]
        namespace={'Path':Path};exec(compile(ast.Module(body=[parse],type_ignores=[]),'official-schema-parser','exec'),namespace)
        official_parse=namespace['_parse']
        prompt=literal_assignment(ast.parse((upstream/'inference_utils.py').read_text(encoding='utf-8')),'DEFAULT_PROMPT')
        # A no-op generation block renders the unmodified local template. It
        # does not pretend to execute processor audio expansion or its labels.
        from jinja2 import Environment,nodes
        from jinja2.ext import Extension
        class GenerationBlock(Extension):
            tags={'generation'}
            def parse(self,parser):
                token=next(parser.stream)
                body=parser.parse_statements(['name:endgeneration'],drop_needle=True)
                return nodes.CallBlock(self.call_method('_render'),[],[],body).set_lineno(token.lineno)
            def _render(self,caller):return caller()
        template=Environment(extensions=[GenerationBlock]).from_string((N/'chat_template.jinja').read_text(encoding='utf-8'))
        messages=[{'role':'user','content':[{'type':'audio','audio':'LOCAL_TRAIN_CLIP'},
                    {'type':'text','text':prompt}]}]
        prefix=template.render(messages=messages,add_generation_prompt=True)
        from tokenizers import Tokenizer
        tokenizer=Tokenizer.from_file(str(N/'tokenizer.json'))
        eos=tokenizer.token_to_id('<|im_end|>');pad=tokenizer.token_to_id('<|endoftext|>')
        require(eos==151645 and pad==151643,'Pinned EOS/padding IDs differ')
        prefix_ids=tokenizer.encode(prefix,add_special_tokens=False).ids
        rows=[];maximum=None;minimum=None;characters=0;target_tokens=0
        pending=a.output/'chinese-moss-conversations.jsonl.pending'
        with manifest.open(encoding='utf-8') as inputs,pending.open('x',encoding='utf-8',newline='\n') as output:
            for line_no,line in enumerate(inputs,1):
                if line_no%100==1:stop();save(examples=line_no-1)
                row=json.loads(line);require(row['role']=='train-only' and row['language']=='Chinese','Wrong training role')
                require(row['frames']==row['endFrame']-row['startFrame']>0,'Original frame interval differs')
                require(not any(token in row['text'] for token in ['<|im_start|>','<|im_end|>','<|audio_pad|>','<|endoftext|>']),
                    'Raw text contains a model control token; retain and diagnose')
                duration=format(Decimal(row['frames'])/Decimal(16000),'f')
                target='[0.00][S01]'+row['text']+'['+duration+']'
                match=re.fullmatch(r'\[([^\[\]]+)\]\[S01\](.*)\[([^\[\]]+)\]',target,re.DOTALL)
                require(match is not None and match[2]==row['text'] and Decimal(match[3])*16000==row['frames'],
                    'Target text or exact relative timing changed')
                tokens=tokenizer.encode(target,add_special_tokens=False).ids+[eos]
                require(tokenizer.decode(tokens[:-1],skip_special_tokens=False)==target,'Target tokenization lost raw characters')
                full=tokenizer.encode(prefix+target+'<|im_end|>',add_special_tokens=False).ids
                require(full==prefix_ids+tokens,'Prefix/answer BPE boundary differs; no guessed mask')
                require(tokens.count(eos)==1 and pad not in tokens,'EOS/padding contaminated target')
                conversation=[{'role':'user','message_type':'text','content':prompt},
                    {'role':'user','message_type':'audio','content':row['audio']},
                    {'role':'assistant','message_type':'text','content':target}]
                exported={'conversation':conversation,'source':row,'targetTokenIdsIncludingEos':tokens,
                    'anonymousSpeakerScope':'S01 is local to this one-utterance clip; not a permanent person ID',
                    'relativeStartFrame':0,'relativeEndFrame':row['frames']}
                parsed=official_parse(exported,a.output,line_no)
                require(parsed=={'audio':row['audio'],'prompt':prompt,'target':target},'Official dataset parser differs')
                with wave.open(row['audio'],'rb') as w:
                    require((w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes())==(1,2,16000,row['frames']),
                        'Verified source WAV header differs')
                output.write(json.dumps(exported,ensure_ascii=False,separators=(',',':'))+'\n')
                require(output.tell()<32*1024**2,'Bounded metadata output exceeded32MiB')
                item={'id':row['id'],'frames':row['frames'],'targetTokensIncludingEos':len(tokens),
                    'prefixTokensBeforeActualAudioExpansion':len(prefix_ids),'targetIds':tokens}
                rows.append(item);characters+=len(row['text']);target_tokens+=len(tokens)
                if maximum is None or len(tokens)>maximum['targetTokensIncludingEos']:maximum=item
                if minimum is None or len(tokens)<minimum['targetTokensIncludingEos']:minimum=item
            output.flush();os.fsync(output.fileno())
        require(len(rows)==5027 and characters==proof['sourceTextCharacters'],'Original input count/characters differ')
        # Actual unequal source answers exercise both padding conventions. The
        # answers are compared back to the tokenizer, independently of offsets.
        chosen=[minimum,maximum,rows[0],rows[-1]]
        mask_cases=[]
        for side in ('left','right'):
            batch=padded_labels([prefix_ids]*len(chosen),[x['targetIds'] for x in chosen],pad,side=side)
            for row,ids,mask,labels in zip(chosen,batch['input_ids'],batch['attention_mask'],batch['labels']):
                require([v for v in labels if v!=-100]==row['targetIds'],'Answer/EOS dropped or prompt trained')
                require(all(label==-100 for label,attention in zip(labels,mask) if not attention),'Padding trained')
                active=[value for value,attention in zip(ids,mask) if attention]
                require(active==prefix_ids+row['targetIds'],'Batched input order changed')
                n=sum(mask);offset=len(mask)-n if side=='left' else 0
                require(all(v==-100 for v in labels[offset:offset+len(prefix_ids)]),'Prompt loss was not masked')
            mask_cases.append({'paddingSide':side,'examples':len(chosen),'allPromptAudioPlaceholderAndPaddingMasked':True,
                'allAnswerTokensAndExactlyOneEosSupervised':True})
        result=a.output/'chinese-moss-conversations.jsonl';pending.rename(result)
        bounds=lambda v:{k:x for k,x in v.items() if k!='targetIds'}
        save(state='PASS_5027_CHINESE_MOSS_OFFICIAL_CONVERSATION_TARGET_AND_TOKEN_CONTRACT_NOT_TRAINING_ADMISSION',
            examples=len(rows),frames=proof['verifiedFrames'],sourceTextCharacters=characters,
            manifest=str(result),manifestSha256=sha(result),manifestBytes=result.stat().st_size,
            originalManifest=str(manifest),originalManifestSha256=sha(manifest),sourceIntegrityReceiptSha256=sha(O/'integrity-r1/completed.json'),
            upstreamSources=upstream_receipts,nativeModelTokenizerSha256=sha(N/'tokenizer.json'),
            nativeChatTemplateSha256=sha(N/'chat_template.jinja'),sourceSha256=sha(__file__),
            supervisedTargetTokensIncludingEos=target_tokens,minimumTarget=bounds(minimum),maximumTarget=bounds(maximum),
            paddingMaskCases=mask_cases,all5027OfficialDatasetParserAccepted=True,
            all5027RawTextsAndExactFrameDurationsPreserved=True,all5027TargetTokenizationRoundtripsExact=True,
            unexpandedPromptAndTargetTokenBoundariesExact=True,sourcePcmRewrittenOrDownloaded=False,
            anonymousPerClipSpeakerOnly=True,continuousSpeakerIdentityTraining=False,
            actualAudioFeatureExpansionAndForwardProof=False,actualGpuGradientOrModelTraining=False,
            actualProcessorTrainingLabelsProven=False,originalAishellCrossCorpusPersonIsolationProven=False,
            evaluationAudioOrTextgridRead=False,originalQualityAndResourceGatesChanged=False,
            torchImported='torch' in sys.modules,elapsedSeconds=time.monotonic()-began)
        require('torch' not in sys.modules,'Metadata contract imported a neural runtime')
        atomic_json(a.output/'completed.json',state)
        print(json.dumps({k:state[k] for k in ['state','examples','manifestBytes','supervisedTargetTokensIncludingEos','elapsedSeconds','limits']}))
    except BaseException as error:
        import traceback
        save(state='FAILED_CHINESE_MOSS_CONTRACT_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
    finally:pressure.close()

if __name__=='__main__':main()
