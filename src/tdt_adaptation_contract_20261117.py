"""Exact one-epoch boundaries and checkpoint identity; no neural imports."""
from meeting_acoustic_contract_20261116 import require

EXAMPLES=475
ACCUMULATION=4
UPDATES=(EXAMPLES+ACCUMULATION-1)//ACCUMULATION

def valid_resume_position(completed,updates):
    require(type(completed) is int and type(updates) is int,'Noninteger checkpoint progress')
    require(0<completed<=EXAMPLES and (completed%ACCUMULATION==0 or completed==EXAMPLES),
        'Checkpoint is not at a complete optimizer-update boundary')
    require(updates==(completed+ACCUMULATION-1)//ACCUMULATION,'Checkpoint example/update counts disagree')
    return completed,updates

def checkpoint_identity(receipt):
    return {key:receipt[key] for key in ('file','sha256','receiptFile','receiptSha256',
        'completedExamples','optimizerUpdates','orderSha256','frozenDigest','preflightOnly')}

def require_final_checkpoint(receipt,final):
    valid_resume_position(receipt['completedExamples'],receipt['optimizerUpdates'])
    require(receipt['completedExamples']==EXAMPLES and receipt['optimizerUpdates']==UPDATES
        and not receipt['preflightOnly'],'Validation checkpoint is not the final candidate')
    require(checkpoint_identity(receipt)==final['finalCheckpoint'],'Validation checkpoint differs from completed epoch')
    return checkpoint_identity(receipt)
