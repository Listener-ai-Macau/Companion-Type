"""Exact retained presence/identity algorithm, factored for cached outputs.

The policy body is verbatim from compose_presence_identity_20261116.py;
preparation verifies its AST identity and an original native180 RTTM control.
"""
from pathlib import Path
from types import SimpleNamespace
from collections import defaultdict
import math
import numpy as np
from meeting_acoustic_contract_20261116 import require,sha
from score_joint_whole_meetings_20261115 import union
from compose_presence_identity_20261116 import intersections

def compose(activity,base,data,source,case,output,meeting):
    a=SimpleNamespace(output=Path(output),meeting=meeting)
    duration=case['audioSeconds'];occupied=union([{'start':max(0,r['start']),'end':min(duration,r['end'])}
        for r in base if r['end']>0 and r['start']<duration])
    gaps=[];end=0.
    for interval in occupied:
        if interval['start']>end:gaps.append({'start':end,'end':interval['start']})
        end=max(end,interval['end'])
    if end<duration:gaps.append({'start':end,'end':duration})
    support=intersections(union(activity),gaps);supplement=[];unknown=[];cadence=source['cadence']
    minimum_margin=1.;minimum_posterior=1.;assigned_seconds=unknown_seconds=0.
    for index,interval in enumerate(support):
        for g in range(math.floor(interval['start']/cadence),math.ceil(interval['end']/cadence)):
            low=max(interval['start'],g*cadence);high=min(interval['end'],(g+1)*cadence)
            if high<=low:continue
            require(0<=g<source['frames'],'Missing native8 posterior frame')
            values=np.asarray(data[g]);require(values.shape==(8,) and np.isfinite(values).all(),'Invalid native8 posteriors')
            winner=int(values.argmax());best=float(values[winner]);unique=int(np.count_nonzero(values==values[winner]))==1
            if unique:
                label='speaker_'+str(winner);assigned_seconds+=high-low
                minimum_posterior=min(minimum_posterior,best)
                minimum_margin=min(minimum_margin,best-float(np.partition(values,-2)[-2]))
            else:
                label='unknown_identity_'+str(index);unknown_seconds+=high-low
            row={'start':low,'end':high,'speaker':label};supplement.append(row)
            if not unique:unknown.append(row)
    a.output.mkdir(parents=True,exist_ok=False)
    def write(name,rows):
        groups=defaultdict(list)
        rounded_zero=0;rounded_zero_seconds=0.
        for row in rows:
            # Match the retained RTTM's six-decimal format before merging.
            # Native cadence is a float; intersections at the same serialized
            # boundary can otherwise produce positive1e-14s phantom cells.
            low=round(row['start']*1000000);high=round(row['end']*1000000)
            require(high>=low,'Time serialization reversed an interval')
            if high==low:
                # Each independently rounded endpoint has at most0.5us error.
                # A zero-width serialized cell therefore spans at most1us,
                # not a fixed total10ns independent of the number of cells.
                require(abs(row['start']-low/1000000)<=.5e-6+1e-12
                    and abs(row['end']-high/1000000)<=.5e-6+1e-12,
                    'Endpoint exceeds the six-decimal rounding bound')
                require(0<=row['end']-row['start']<=1e-6+2e-12,
                    'A resolvable interval vanished in time serialization')
                rounded_zero+=1;rounded_zero_seconds+=row['end']-row['start'];continue
            groups[row['speaker']].append(dict(row,start=low/1000000,end=high/1000000))
        require(rounded_zero_seconds<=rounded_zero*(1e-6+2e-12),
            'Total serialization loss exceeds the sum of endpoint rounding bounds')
        rows=[dict(r,speaker=s) for s,items in groups.items() for r in union(items)]
        rows.sort(key=lambda r:(r['start'],r['end'],r['speaker']))
        path=a.output/name
        path.write_text(''.join(f"SPEAKER {a.meeting} 1 {r['start']:.6f} {r['end']-r['start']:.6f} <NA> <NA> {r['speaker']} <NA> <NA>\n" for r in rows),encoding='utf-8')
        return {'file':str(path),'sha256':sha(path),'segments':len(rows),
            'zeroDurationFloatIntersectionCellsNotSerialized':rounded_zero,
            'totalFloatPhantomSeconds':rounded_zero_seconds,'timeResolutionSeconds':1e-6,
            'maximumTotalRoundingLossSeconds':rounded_zero*(1e-6+2e-12)}
    supplemental=write('presence-identity-supplement.rttm',supplement)
    combined=write('combined.rttm',base+supplement)
    return {'mossMapped':supplemental,'combined':combined,'unknownIdentitySeconds':unknown_seconds,
        'assignedSupplementSeconds':assigned_seconds,'unmatchedLocalSpeakerSegments':unknown,
        'minimumAssignedPosterior':minimum_posterior,'minimumAssignedTopTwoMargin':minimum_margin}
