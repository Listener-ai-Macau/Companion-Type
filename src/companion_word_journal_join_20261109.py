"""Conservative word/journal join. Never duplicates, deletes, or invents words.

Inputs are a recognizer's final response and an independently predicted speaker
journal. No reference speaker names, counts, transcripts, or scoring answers.
"""
from collections import defaultdict
import math
import re
import unicodedata

def text_signature(text):
    # Text conservation only; this processing module imports no reference scorer
    # or numerical/model runtime.
    return ''.join(c for c in re.sub(r'<[^>]*>', '', text)
                   if not c.isspace() and not unicodedata.category(c).startswith(('P','S'))).lower()

def result_object(document):
    result = document.get('result')
    if isinstance(result, list):
        if len(result) != 1:
            raise ValueError('Expected one authoritative recognition result')
        result = result[0]
    if not isinstance(result, dict):
        raise ValueError('Missing authoritative result')
    return result

def speaker_id(utterance):
    import json
    additions = utterance.get('additions', {})
    if isinstance(additions, str):
        try:
            additions = json.loads(additions)
        except ValueError:
            additions = {}
    for obj in [utterance, additions]:
        if not isinstance(obj, dict):
            continue
        for key in ['speaker', 'speaker_id', 'speakerId', 'spk_id']:
            value = obj.get(key)
            if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value).strip():
                return str(value).strip()
    return 'unknown'

def word_time(word, names):
    for key in names:
        value = word.get(key)
        if isinstance(value, (int, float, str)) and not isinstance(value, bool):
            try:
                number = float(value) / 1000
            except ValueError:
                continue
            if math.isfinite(number):
                return number
    return None

def provider_words(document, audio_seconds):
    utterances = result_object(document).get('utterances')
    if not isinstance(utterances, list):
        raise ValueError('Missing source utterances')
    rows = []
    for utterance_index, utterance in enumerate(utterances):
        words = utterance.get('words')
        explicit = utterance.get('text')
        if not isinstance(words, list) or not all(isinstance(x.get('text'), str) for x in words):
            raise ValueError(f'Missing complete source word tokens {utterance_index}')
        if isinstance(explicit, str) and explicit.strip() and text_signature(explicit) != text_signature(''.join(x['text'] for x in words)):
            raise ValueError(f'Word text differs from source utterance {utterance_index}; refuse silent rewriting')
        for word_index, word in enumerate(words):
            text = word.get('text')
            if not isinstance(text, str):
                raise ValueError('Missing source token text')
            start = word_time(word, ['start_time', 'startTime', 'start_ms'])
            end = word_time(word, ['end_time', 'endTime', 'end_ms'])
            if start is None or end is None or not 0 <= start <= end <= audio_seconds + 1e-6:
                raise ValueError('Source word timing is absent or out of bounds')
            rows.append({'id':f'{utterance_index}:{word_index}', 'utteranceIndex':utterance_index,
                         'wordIndex':word_index, 'sourceOrder':len(rows), 'text':text,
                         'start':start, 'end':end, 'speaker':speaker_id(utterance),
                         'textSource':'utterance.text' if isinstance(explicit,str) and explicit.strip() else 'utterance.words'})
    return rows

def joined_words(words, journal_segments, source_offset_seconds):
    # Merge overlapping/touching spans of the same anonymous predicted person;
    # otherwise duplicate spans could falsely increase a person's vote.
    by_person = defaultdict(list)
    for segment in journal_segments:
        start, end = float(segment['start']), float(segment['end'])
        if not math.isfinite(start) or not math.isfinite(end) or not 0 <= start < end:
            raise ValueError('Invalid predicted journal interval')
        by_person[str(segment['speaker'])].append((start, end))
    merged = {}
    for person, spans in by_person.items():
        runs = []
        for start, end in sorted(spans):
            if runs and start <= runs[-1][1]:
                runs[-1] = (runs[-1][0], max(end, runs[-1][1]))
            else:
                runs.append((start, end))
        merged[person] = runs
    output = []
    for word in words:
        start = word['start'] + source_offset_seconds
        end = word['end'] + source_offset_seconds
        votes = {person:sum(max(0, min(end, b)-max(start, a)) for a,b in spans)
                 for person,spans in merged.items()}
        votes = {k:v for k,v in votes.items() if v > 1e-9}
        top = max(votes.values(), default=0)
        winners = sorted(k for k,v in votes.items() if abs(v-top) <= 1e-9)
        reason = 'unique_largest_predicted_voice_overlap'
        if end == start:
            identity, reason = 'unattributed:zero_duration', 'zero_duration_source_word'
        elif not votes:
            identity, reason = 'unattributed:no_voice', 'no_predicted_voice_overlap'
        elif len(winners) != 1:
            identity, reason = 'unattributed:overlap', 'ambiguous_simultaneous_predicted_voices'
        else:
            identity = 'native:' + winners[0]
        output.append(dict(word, speaker=identity, providerSpeaker=word['speaker'],
                           assignmentReason=reason, predictedVoiceOverlapSeconds=votes))
    if [(x['id'],x['text'],x['start'],x['end']) for x in output] != [(x['id'],x['text'],x['start'],x['end']) for x in words]:
        raise AssertionError('All source words and timings must survive once and unchanged')
    return output

def refine_recovered_words(words, joined):
    """Only fill the identity seam on recovered tokens, never relabel normal text.

    Aliases come from observed provider labels during intervals in which the
    independent journal predicts exactly one voice. No reference labels/counts.
    Overlap, ties, or missing evidence retain the original provider identity.
    """
    if [(x['id'],x['text'],x['start'],x['end']) for x in words] != [(x['id'],x['text'],x['start'],x['end']) for x in joined]:
        raise ValueError('Join must preserve the original source words')
    votes = defaultdict(lambda: defaultdict(float))
    for original, aligned in zip(words, joined):
        evidence = aligned['predictedVoiceOverlapSeconds']
        if original['textSource'] == 'utterance.text' and len(evidence) == 1:
            native, seconds = next(iter(evidence.items()))
            votes[native][original['speaker']] += seconds
    aliases = {}
    for native, labels in votes.items():
        maximum = max(labels.values())
        winners = [label for label, seconds in labels.items() if abs(seconds-maximum) <= 1e-9]
        if len(winners) == 1:
            aliases[native] = winners[0]
    output = []
    for original, aligned in zip(words, joined):
        row = dict(original, assignmentReason='original_recognizer_identity_preserved')
        evidence = aligned['predictedVoiceOverlapSeconds']
        if original['textSource'] == 'utterance.words':
            row['assignmentReason'] = 'recovered_word_identity_unresolved_original_label_retained'
            if len(evidence) == 1:
                native = next(iter(evidence))
                if native in aliases:
                    row.update(speaker=aliases[native], assignmentReason='recovered_word_single_voice_with_observed_alias')
        output.append(row)
    if [(x['id'],x['text'],x['start'],x['end']) for x in words] != [(x['id'],x['text'],x['start'],x['end']) for x in output]:
        raise AssertionError('Source content must not change')
    for original, row in zip(words, output):
        if original['textSource'] == 'utterance.text' and original['speaker'] != row['speaker']:
            raise AssertionError('Normal utterance identity must not change')
    return output, {'aliases':aliases, 'evidenceSeconds':{k:dict(v) for k,v in votes.items()}}
