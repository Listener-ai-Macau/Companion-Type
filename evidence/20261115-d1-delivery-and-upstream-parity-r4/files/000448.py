"""Prepare word-score diagnostics without overriding the rejected model decision."""
from pathlib import Path
import py_compile
S=Path(__file__).parent;source=(S/'score_tse_source_supervision_asr_20261108.py').read_text(encoding='utf8')
source=source.replace('==132','==156').replace("'allExpectedOutputsScored':132","'allExpectedOutputsScored':156")
start=source.index('result={')
control="""control_rows=[]
for example in read(C/'solo-control-scoring-only.json'):
    reference=re.sub(r'<[^>]*>','',example['referenceForScoringOnly']).replace('&','').strip();conditions={}
    for arm in ['raw','baseline','adapted']:
        output=byid[arm+'--'+example['id']];conditions[arm]={'text':output['text'],'edits':edits(reference,output['text'])}
    control_rows.append({'id':example['id'],'meeting':example['meeting'],'referenceForScoringOnly':reference,'conditions':conditions})
control_totals={arm:total([r['conditions'][arm]['edits'] for r in control_rows]) for arm in ['raw','baseline','adapted']}
word_metrics_pass=retain
retain=False
"""
source=source[:start]+control+source[start:];source=source.replace("'FIXED_TSE_PILOT_FREE_ASR_GAIN_REQUIRES_UNSEEN_AUTOMATIC_MEETINGS' if retain else 'FIXED_TSE_PILOT_REJECTED_FREE_ASR_REGRESSION'","'POST_REJECTION_NATURAL_WORD_GAIN_DIAGNOSTIC_ONLY' if word_metrics_pass else 'POST_REJECTION_NATURAL_WORD_REGRESSION_DIAGNOSTIC_ONLY'")
source=source.replace("'totals':totals,'categories':categories","'totals':totals,'categories':categories,'diagnosticOnlyAfterWaveformRejection':True,'wordMetricsMeetNextStageCriteria':word_metrics_pass,'naturalRowsScored':132,'realSoloControlRowsScored':24,'rawSoloControlTotals':control_totals,'rawSoloControlPerExample':control_rows")
target=S/'score_tse_source_supervision_diagnostic_asr_20261108.py';assert not target.exists();target.write_text(source,encoding='utf8',newline='\n');py_compile.compile(str(target),doraise=True);print('Prepared all156-row diagnostic scorer; promotion remains false.',flush=True)
