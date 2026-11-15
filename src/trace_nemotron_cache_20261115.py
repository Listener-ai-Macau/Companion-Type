"""Observe upstream cache updates without changing selection or tensors.

The actual upstream update is called exactly once with its original arguments.
Only small detached cache-probability snapshots and counts are written. No
reference labels, audio cuts, speaker names or output thresholds enter here.
"""
from pathlib import Path
import hashlib,inspect,json


def install_cache_trace(directory, *, expected_source_sha256, audio_seconds):
    import numpy as np
    from transformers.models.nemotron3_diarization.modeling_nemotron3_diarization import Nemotron3DiarizationSpeakerCache

    source=Path(inspect.getfile(Nemotron3DiarizationSpeakerCache))
    assert hashlib.sha256(source.read_bytes()).hexdigest()==expected_source_sha256
    directory=Path(directory);directory.mkdir()
    original=Nemotron3DiarizationSpeakerCache.update
    records=[];frame_cursor=0

    def snapshot(cache):
        if not cache.is_initialized or not cache.num_cache_frames:
            return {'frames':0,'activeFramesByChannel':[0]*8,'positiveScoreFramesByChannel':[0]*8,'maximumProbabilityByChannel':[0.]*8,'embeddingSha256ByFrame':[]}
        probabilities=cache.probs[:,:cache.num_cache_frames]
        scores=cache._get_frame_scores(probabilities)
        embeddings=cache.embeds[:,:cache.num_cache_frames].detach().float().cpu().numpy()[0]
        return {'frames':cache.num_cache_frames,
          'activeFramesByChannel':(probabilities>.5).sum(dim=1)[0].cpu().tolist(),
          'positiveScoreFramesByChannel':(scores>0).sum(dim=1)[0].cpu().tolist(),
          'maximumProbabilityByChannel':probabilities.max(dim=1).values[0].cpu().tolist(),
          'embeddingSha256ByFrame':[hashlib.sha256(memoryview(row).cast('B')).hexdigest() for row in embeddings]}

    def observed(cache,chunk_input_embeds,chunk_logits,silence_embeds,num_chunk_frames,
                 mask=None,num_lookback_frames=0):
        nonlocal frame_cursor
        before=snapshot(cache)
        value=original(cache,chunk_input_embeds,chunk_logits,silence_embeds,num_chunk_frames,
                       mask=mask,num_lookback_frames=num_lookback_frames)
        frame_cursor+=num_chunk_frames
        index=len(records)+1
        probabilities=cache.probs[:,:cache.num_cache_frames].detach().float().cpu().numpy()
        np.save(directory/('cache-%04d.npy'%index),probabilities,allow_pickle=False)
        row={'update':index,'sourceEndSeconds':min(frame_cursor*.08,audio_seconds),
          'encoderFrameCursor':frame_cursor,'chunkEncoderFrames':num_chunk_frames,
          'before':before,'after':snapshot(cache),'fifoFramesAfter':cache.num_fifo_frames,
          'isCompressedAfter':cache.is_compressed,'minPositiveScores':cache.min_positive_scores,
          'cacheCapacityFrames':cache.speaker_cache_length}
        records.append(row)
        (directory/('update-%04d.json'%index)).write_text(json.dumps(row,indent=2)+'\n',encoding='utf-8')
        return value

    Nemotron3DiarizationSpeakerCache.update=observed

    def restore():
        assert Nemotron3DiarizationSpeakerCache.update is observed
        Nemotron3DiarizationSpeakerCache.update=original
        (directory/'summary.json').write_text(json.dumps({'state':'OBSERVATIONAL_CACHE_TRACE_REQUIRES_EXACT_OUTPUT_CONTROL',
          'updates':len(records),'upstreamSourceSha256':expected_source_sha256,
          'speakerLabelsOrReferencesRead':False,'selectionChanged':False,
          'qualityQualified':False},indent=2)+'\n',encoding='utf-8')
    return restore
