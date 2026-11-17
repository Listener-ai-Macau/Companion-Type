"""Exact one-epoch boundaries and checkpoint identity; no neural imports."""
from meeting_acoustic_contract_20261116 import require

EXAMPLES=475
ACCUMULATION=4
UPDATES=(EXAMPLES+ACCUMULATION-1)//ACCUMULATION

def valid_resume_position(completed,updates,*,examples=EXAMPLES,accumulation=ACCUMULATION):
    require(type(examples) is int and examples>0 and accumulation==ACCUMULATION,
        'Invalid frozen one-epoch data scope')
    require(type(completed) is int and type(updates) is int,'Noninteger checkpoint progress')
    require(0<completed<=examples and (completed%accumulation==0 or completed==examples),
        'Checkpoint is not at a complete optimizer-update boundary')
    require(updates==(completed+accumulation-1)//accumulation,'Checkpoint example/update counts disagree')
    return completed,updates

def checkpoint_identity(receipt):
    return {key:receipt[key] for key in ('file','sha256','receiptFile','receiptSha256',
        'completedExamples','optimizerUpdates','orderSha256','frozenDigest','preflightOnly')}

def require_final_checkpoint(receipt,final,*,examples=EXAMPLES,accumulation=ACCUMULATION):
    valid_resume_position(receipt['completedExamples'],receipt['optimizerUpdates'],
        examples=examples,accumulation=accumulation)
    require(receipt['completedExamples']==examples and receipt['optimizerUpdates']==(examples+accumulation-1)//accumulation
        and not receipt['preflightOnly'],'Validation checkpoint is not the final candidate')
    require(checkpoint_identity(receipt)==final['finalCheckpoint'],'Validation checkpoint differs from completed epoch')
    return checkpoint_identity(receipt)

def training_scope(protocol):
    training=protocol['training'];examples=training['examples'];updates=training['optimizerUpdates']
    require(type(examples) is int and examples>0 and type(updates) is int
        and training['epochs']==1 and training['gradientAccumulationExamples']==ACCUMULATION
        and updates==(examples+ACCUMULATION-1)//ACCUMULATION,'Frozen data/one-epoch counts disagree')
    every=training.get('checkpointEveryUpdates',8);first=training.get('checkpointAtFirstUpdate',False)
    require(type(every) is int and every>0 and type(first) is bool,'Invalid checkpoint schedule')
    return examples,updates,every,first

def checkpoint_due(update,total_updates,*,every=8,first=False):
    require(type(update) is int and 0<update<=total_updates,'Checkpoint update outside fixed epoch')
    return (first and update==1) or update%every==0 or update==total_updates
