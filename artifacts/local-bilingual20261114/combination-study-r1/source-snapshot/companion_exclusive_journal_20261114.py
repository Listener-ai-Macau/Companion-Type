"""Optional exclusive attribution view of unchanged native activity posteriors.

Inspired by the separate exclusive diarization output in pyannote community-1:
https://huggingface.co/pyannote/speaker-diarization-community-1
This adapts existing native posteriors; it does not load the pyannote model or
replace the original multi-voice journal. It cannot recover overlapping words.
"""


def exclusive_journal(probabilities, *, frames, seconds_per_frame, source_journal):
    import numpy as np
    if frames <= 0 or frames > len(probabilities) or seconds_per_frame <= 0:
        raise ValueError('Invalid committed posterior bounds')
    data = np.asarray(probabilities[:frames])
    if data.ndim != 2 or not data.shape[1] or not np.isfinite(data).all() or data.min() < 0 or data.max() > 1:
        raise ValueError('Invalid native speaker posteriors')
    # Match the existing native threshold exactly, including its last-state
    # carry on a value equal to0.5. No threshold/pad/duration changes.
    active = np.zeros(data.shape, dtype=bool)
    for speaker in range(data.shape[1]):
        values = data[:, speaker]
        last = np.maximum.accumulate(np.where(values != .5, np.arange(frames), -1))
        active[:, speaker] = (last >= 0) & (values[np.maximum(last, 0)] > .5)
    values = np.where(active, data, -np.inf)
    best = values.max(axis=1)
    winners = values.argmax(axis=1)
    ties = (values == best[:, None]).sum(axis=1) != 1
    speech = active.any(axis=1)
    winners[~speech | ties] = -1
    rows = []
    for speaker in range(data.shape[1]):
        edges = np.diff(np.r_[0, winners == speaker, 0].astype(np.int8))
        starts, ends = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
        for start, end in zip(starts, ends):
            low, high = float(start*seconds_per_frame), min(float(end*seconds_per_frame), source_journal['audioSeconds'])
            if low < high:
                rows.append({'start': low, 'end': high, 'speaker': speaker})
    rows.sort(key=lambda row: (row['start'], row['end'], row['speaker']))
    output = {**source_journal, 'segments': rows,
              'scope': 'Optional exclusive transcription attribution only. Raw multi-voice journal remains authoritative for simultaneous activity.',
              'exclusiveAttributionView': True, 'overlappingWordsRecovered': False, 'qualityQualified': False}
    receipt = {'committedFrames': frames, 'secondsPerFrame': seconds_per_frame,
               'rawSpeechFrames': int(speech.sum()), 'rawMultiVoiceFrames': int((active.sum(axis=1) > 1).sum()),
               'exclusiveSpeechFrames': int((winners >= 0).sum()),
               'speechFramesUnassignedDueToExactPosteriorTie': int((speech & ties).sum()),
               'thresholdUnchanged': .5, 'smoothingOrGapFillApplied': False,
               'speakerCountHintProvided': False, 'referenceUsed': False, 'newNeuralCalls': 0,
               'cannotUseExclusiveViewAsOverlapDERProof': True}
    return output, receipt
