"""Bounded native MOSS processor inputs with target-only, padding-aware labels.

Uses the existing audio-only inference prompt. No model is loaded here. The
separate prompt processor call measures the actual expanded audio-token span;
it avoids estimating the loss boundary from the unexpanded template.
"""
from meeting_acoustic_contract_20261116 import require

def prepare_target_only_batch(processor,audios,targets,*,torch,expected_target_ids=None,heartbeat=lambda:None):
    require(len(audios)==len(targets)>0,'Empty or unequal Chinese training batch')
    require(processor.tokenizer.padding_side in ('left','right'),'Unsupported native padding convention')
    messages=[{'role':'user','content':[{'type':'audio','audio':'LOCAL_TRAIN_CLIP'}]}]
    prefix=processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)
    eos=processor.tokenizer.eos_token
    expected=[processor.tokenizer.encode(text+eos,add_special_tokens=False) for text in targets]
    if expected_target_ids is not None:
        require(expected==expected_target_ids,'Frozen Chinese target token IDs changed')
    options={'audio':audios,'sampling_rate':16000,'padding':True,'truncation':False,
        'return_tensors':'pt','audio_kwargs':{'device':'cpu'}}
    heartbeat();prompt=processor(text=[prefix]*len(audios),**options)
    heartbeat();batch=processor(text=[prefix+text+eos for text in targets],**options)
    # The same unmodified waveform must produce the same native signal features.
    require(torch.equal(batch['input_features'],prompt['input_features']),
        'Prompt and full requests processed different source audio')
    labels=batch['input_ids'].clone().fill_(-100);details=[]
    for i,target_ids in enumerate(expected):
        active=batch['attention_mask'][i].bool();prefix_active=prompt['attention_mask'][i].bool()
        source_ids=prompt['input_ids'][i][prefix_active].tolist()
        full_ids=batch['input_ids'][i][active].tolist()
        require(full_ids==source_ids+target_ids,'Native expanded prompt/target token boundary differs')
        positions=active.nonzero(as_tuple=False).flatten()
        answer_positions=positions[len(source_ids):]
        require(len(answer_positions)==len(target_ids),'Target token count differs')
        labels[i,answer_positions]=batch['input_ids'][i,answer_positions]
        require(labels[i][labels[i]!=-100].tolist()==target_ids,'Prompt/padding leaked into target supervision')
        require(all(value==-100 for value in labels[i,positions[:len(source_ids)]].tolist()),'Prompt trained')
        require(all(value==-100 for value in labels[i,~active].tolist()),'Padding trained')
        require(target_ids[-1]==processor.tokenizer.eos_token_id and target_ids.count(processor.tokenizer.eos_token_id)==1,
            'Target lacks exactly one final EOS')
        details.append({'inputTokens':len(full_ids),'expandedPromptTokens':len(source_ids),
            'supervisedTargetTokensIncludingEos':len(target_ids),'maskedPaddingTokens':int((~active).sum()),
            'audioPadTokens':source_ids.count(processor.audio_token_id),
            'originalSamplesSupplied':len(audios[i])})
    batch['labels']=labels
    return batch,details
