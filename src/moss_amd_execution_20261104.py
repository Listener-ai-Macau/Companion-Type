"""Exact-context inference scheduling for GPUs without fused SDPA kernels.

No weights, context window, audio, or speaker logic is changed. Queries are
evaluated in blocks against the same allowed keys. Whisper's independent
30-second encoder chunks are microbatched before the existing global adaptor.
"""
import torch
import torch.nn.functional as F


def bounded_sdpa(original, query, key, value, attn_mask=None, dropout_p=0.0,
                 is_causal=False, *, scale=None, enable_gqa=False, query_block=256, stats=None, pacer=None):
    qlen, klen = query.shape[-2], key.shape[-2]
    if stats is not None:
        stats['sdpaCalls'] += 1
        stats['maxQueryTokens'] = max(stats['maxQueryTokens'], qlen)
        stats['maxKeyTokens'] = max(stats['maxKeyTokens'], klen)
    # Non-inference calls and short queries preserve the framework path exactly.
    if qlen <= query_block or dropout_p != 0.0 or (is_causal and attn_mask is not None):
        return original(query, key, value, attn_mask=attn_mask, dropout_p=dropout_p,
                        is_causal=is_causal, scale=scale, enable_gqa=enable_gqa)
    if stats is not None:
        stats['blockedCalls'] += 1
    answers = []
    for start in range(0, qlen, query_block):
        stop = min(qlen, start + query_block)
        key_stop = min(klen, stop) if is_causal else klen
        mask = attn_mask
        if is_causal:
            # F.sdpa uses an upper-left causal mask, including when Q != K.
            # Global query indices are essential after the first query block.
            mask = (torch.arange(key_stop, device=query.device)[None, :] <=
                    torch.arange(start, stop, device=query.device)[:, None])
        elif mask is not None:
            mask = mask[..., :key_stop]
            if mask.shape[-2] != 1:
                mask = mask[..., start:stop, :]
        answers.append(original(query[..., start:stop, :], key[..., :key_stop, :],
                                value[..., :key_stop, :], attn_mask=mask,
                                dropout_p=0.0, is_causal=False, scale=scale,
                                enable_gqa=enable_gqa))
        if pacer is not None:pacer.checkpoint()
    return torch.cat(answers, dim=-2)


def install_execution_adapters(model, *, query_block=256, encoder_batch=2, pacer=None, key_block=None):
    assert not model.training and query_block > 0 and encoder_batch > 0
    from transformers.modeling_outputs import BaseModelOutput
    stats = {'sdpaCalls': 0, 'blockedCalls': 0, 'maxQueryTokens': 0,
             'maxKeyTokens': 0, 'encoderCalls': 0, 'encoderChunks': 0,
             'encoderMicrobatches': 0, 'encoderNativeSdpaCalls': 0, 'queryBlock': query_block,
             'keyBlock':key_block,'keyStreamedCalls':0,'keyTiles':0,'maximumScoreTileElements':0,
             'encoderBatch': encoder_batch,
             'semantics': 'All original keys/context retained; no time/audio chunk discard or speaker reset.'}
    original_sdpa = F.scaled_dot_product_attention
    encoder_active = False

    def language_attention(query,key,value,attn_mask=None,dropout_p=0.0,is_causal=False,*,scale=None,enable_gqa=False):
        if key_block and query.shape[-2]>1 and key.shape[-2]>key_block and dropout_p==0.0:
            from moss_key_streamed_attention_20261104 import key_streamed_sdpa
            return key_streamed_sdpa(query,key,value,attn_mask,dropout_p,is_causal,scale=scale,
                enable_gqa=enable_gqa,key_block=key_block,stats=stats,pacer=pacer)
        return original_sdpa(query,key,value,attn_mask=attn_mask,dropout_p=dropout_p,
            is_causal=is_causal,scale=scale,enable_gqa=enable_gqa)

    def scheduled(query, key, value, attn_mask=None, dropout_p=0.0, is_causal=False,
                  *, scale=None, enable_gqa=False):
        if encoder_active:
            # Its fixed 1500-position attention fits with chunk microbatching.
            # Keep this exact native path: BF16 changes here accumulated across
            # the 24-layer pretrained encoder during the controlled comparison.
            stats['encoderNativeSdpaCalls'] += 1
            result=original_sdpa(query, key, value, attn_mask=attn_mask,
                                 dropout_p=dropout_p, is_causal=is_causal,
                                 scale=scale, enable_gqa=enable_gqa)
            if pacer is not None:pacer.checkpoint()
            return result
        return bounded_sdpa(language_attention, query, key, value, attn_mask, dropout_p,
                            is_causal, scale=scale, enable_gqa=enable_gqa,
                            query_block=query_block, stats=stats, pacer=pacer)
    F.scaled_dot_product_attention = scheduled
    encoder = model.model.whisper_encoder
    original_encoder = encoder.forward

    def encode_independent_chunks(input_features, *args, **kwargs):
        nonlocal encoder_active
        count = int(input_features.shape[0])
        stats['encoderCalls'] += 1
        stats['encoderChunks'] += count
        # The published get_audio_features calls only return_dict=True. Refuse
        # unsupported auxiliary returns instead of silently dropping anything.
        encoder_active = True
        try:
            if count <= encoder_batch:
                stats['encoderMicrobatches'] += 1
                return original_encoder(input_features, *args, **kwargs)
            if args or kwargs != {'return_dict': True}:
                raise ValueError('Unexpected Whisper encoder call; cannot microbatch it safely')
            values = []
            for start in range(0, count, encoder_batch):
                result = original_encoder(input_features[start:start+encoder_batch], return_dict=True)
                assert result.hidden_states is None and result.attentions is None
                values.append(result.last_hidden_state)
                stats['encoderMicrobatches'] += 1
            return BaseModelOutput(last_hidden_state=torch.cat(values, dim=0))
        finally:
            encoder_active = False
    encoder.forward = encode_independent_chunks
    return stats
