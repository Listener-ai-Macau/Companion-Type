"""Audit only selected training references and the already downloaded archive prefix."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import re
import tarfile

R = Path('C:/Users/Billy/Desktop/Denzic/Companion')
D = R / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
J = D / 'joint-architecture-r1'
E = Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
DATA = E / 'meeting-domain-data-r1'
OUT = DATA / 'chinese-speaker-audit-r1'
read = lambda p: json.loads(Path(p).read_text(encoding='utf-8-sig'))
digest = lambda b: hashlib.sha256(b).hexdigest()


def main():
    plan_path = J / 'meeting-domain-data-r1/plan.json'
    plan = read(plan_path)
    selected = {r['meeting']: r for r in plan['sources'] if r['language'] == 'Chinese'}
    assert len(selected) == 12
    assert not any('L_R003' in name for name in selected)
    assert not set(selected) & set(plan['existingDevelopmentSourcesExcluded'])
    references = []
    for meeting in sorted(selected):
        f = DATA / meeting / 'reference.TextGrid'
        raw = f.read_bytes()
        names = re.findall(r'name\s*=\s*"([^"]*)"', raw.decode('utf-8-sig'))
        assert names and all(re.fullmatch(r'\d{3}-[MF]', n) for n in names)
        references.append({'meeting': meeting, 'referenceSha256': digest(raw),
                           'tierNames': names, 'tierCount': len(names)})

    prefix = OUT / 'train_L-prefix.gz'
    original_fetch = read(OUT / 'bounded-archive-probe.json')
    assert prefix.stat().st_size <= original_fetch['maximumRequestedBytes']
    headers, comparisons, labels = [], [], []
    stop = 'member_limit30'
    with tarfile.open(prefix, mode='r|gz') as archive:
        for i, member in enumerate(archive):
            if i >= 30:
                break
            headers.append({'name': member.name, 'bytes': member.size,
                            'type': member.type.decode('ascii', 'replace')})
            if 'L_R003' in member.name:
                stop = 'reserved_prefix_header_only_no_payload_read'
                break
            if member.size > 1024 ** 2:
                stop = 'large_payload_not_opened'
                break
            meeting = Path(member.name).stem
            if meeting not in selected or not member.isfile():
                continue
            if member.name.endswith('.TextGrid'):
                raw = archive.extractfile(member).read()
                cached = (DATA / meeting / 'reference.TextGrid').read_bytes()
                comparisons.append({
                    'meeting': meeting, 'officialPrefixReferenceBytes': len(raw),
                    'cachedReferenceBytes': len(cached), 'officialRawSha256': digest(raw),
                    'cachedRawSha256': digest(cached), 'exactBytesEqual': raw == cached,
                    'lfNormalizedBytesEqual': raw.replace(b'\r\n', b'\n') == cached.replace(b'\r\n', b'\n'),
                    'normalizationOnlyForSourceComparisonNotModelOrEvaluation': True})
            elif member.name.endswith('.rttm'):
                raw = archive.extractfile(member).read()
                labels.append({'meeting': meeting,
                               'speakerLabels': sorted({row.split()[7] for row in raw.decode('utf-8').splitlines()})})

    metadata_path = plan_path.parent / 'aishell-publisher-metadata.json'
    assert digest(metadata_path.read_bytes()) == plan['metadataSha256']
    metadata = read(metadata_path)
    sibling_names = [x['rfilename'] for x in metadata['siblings']]
    global_tables = [n for n in sibling_names if n.lower().endswith(('.xlsx', '.xls', '.csv'))
                     or 'spk_info' in n.lower()]
    report = {
        'at': datetime.now().astimezone().isoformat(timespec='seconds'),
        'state': 'CHINESE_GLOBAL_SPEAKER_DISJOINTNESS_UNPROVEN_TRAINING_STAYS_UNREADY',
        'sourcePlan': str(plan_path), 'sourcePlanSha256': digest(plan_path.read_bytes()),
        'selectedTrainMeetings': len(selected), 'selectedTrainingReferenceTiers': references,
        'selectedTrainingTierInstances': sum(r['tierCount'] for r in references),
        'distinctLocalLabelsDoNotEqualGlobalPeople': sorted({n for r in references for n in r['tierNames']}),
        'wholePublisherMetadataRevision': metadata['sha'],
        'publisherMetadataFileCount': len(sibling_names),
        'globalSpeakerTableCandidatesInCachedMirrorIndex': global_tables,
        'boundedGlobalTableLocationEvidence': read(OUT / 'global-table-location-evidence.json'),
        'officialSources': [
            {'url': 'https://www.isca-archive.org/interspeech_2021/fu21b_interspeech.pdf',
             'finding': 'The publisher paper reports36training and25evaluation participants, with one speaker shared between those splits.'},
            {'url': 'https://aishell-4.oss-cn-hangzhou.aliyuncs.com/AISHELL-4%20Data-Specification.pdf',
             'finding': 'The corpus directory diagram names DOC/spk_info.xlsx. Its existence in a specification does not provide a downloadable global speaker-to-meeting mapping.'},
            {'url': 'https://github.com/felixfuyihui/AISHELL-4/blob/master/data_preparation/generate_spk_testdata.py',
             'finding': 'The baseline speaker-dependent test preparation consumes per-meetingRTTM speaker labels and uses them in clip names; this code does not establish cross-meeting identity.'},
            {'url': 'https://www.openslr.org/111/', 'finding': 'Official licenseCC-BY-SA4.0 retained; the mirrorApache tag is not substituted.'}],
        'boundedExistingPrefixInspection': {
            'originalFetch': original_fetch, 'compressedBytes': prefix.stat().st_size,
            'compressedSha256': digest(prefix.read_bytes()), 'membersObserved': headers,
            'stopReason': stop, 'entireArchiveAudited': False,
            'fullArchiveAbsenceOfGlobalTableProven': False,
            'selectedReferenceComparisons': comparisons,
            'selectedRttmSpeakerLabels': labels,
            'newNetworkRequestsByThisAudit': 0,
            'originalFetchWasTimeout28WithUsablePartialBytes': original_fetch['curlExitCode'] == 28},
        'decision': {
            'chineseGlobalSpeakerDisjointnessVerified': False,
            'chineseAdaptationLaunchAllowed': False,
            'inferGlobalIdentityByLocalIdOrRoomOrGenderAllowed': False,
            'meetingDisjointnessAloneIsNotGlobalSpeakerDisjointness': True,
            'englishVerifiedParticipantSplitAffected': False,
            'existingChineseEvaluationScoreChanged': False,
            'qualityQualified': False, 'saleQualified': False,
            'next': 'Keep current Chinese published-model baseline and original evaluations. Before Chinese adaptation, obtain a verifiable public global speaker-to-session map or an independently auditable speaker-disjoint training source. Do not consume the reserved final holdout or relabel an unknown split as verified.'},
        'reservedFinalAudioLabelsOrEmbeddingsOpened': False,
        'newNeuralCalls': 0, 'parameterUpdates': 0, 'audioDecoded': False,
        'trainingOrEvaluationTextsModified': False}
    target = J / 'meeting-domain-data-r1/chinese-global-speaker-audit-20261117.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'receipt': str(target), 'trainingMeetings': len(selected),
                      'tierInstances': report['selectedTrainingTierInstances'],
                      'mirrorGlobalTableCandidates': len(global_tables),
                      'prefixSelectedReferenceComparisons': comparisons,
                      'globalSpeakerSplitVerified': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
