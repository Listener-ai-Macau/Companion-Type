"""Audio/profile-only inference inputs and exact known component training targets."""
from companion_tse_model_io_20261108 import load_pair
from companion_tse_source_data_20261108 import pcm_read,sha
def unit_inputs(unit,profiles,*,torch):
    mix=unit['mixture'];ids=[x['profileId'] for x in unit['targets']] if unit.get('targets') else [unit['profileId']];enrollments=[];pair=None
    for identity in ids:
        profile=profiles[identity];audio={'audio':mix['audio'],'audioSha256':mix['audioSha256'],'profileAudio':profile['audio'],'profileAudioSha256':profile['audioSha256']};current,enrollment,peak=load_pair(audio,torch=torch,device='cuda:0')
        if pair is None:pair=current;scale=peak
        else:assert scale==peak and torch.equal(pair,current)
        enrollments.append(enrollment)
    targets=[]
    for target in unit.get('targets',[]):
        packet=target['component'];assert sha(packet['audio'])==packet['audioSha256'];value=pcm_read(packet['audio'],2)[:,0].astype('float32')/32768/scale;targets.append(torch.from_numpy(value).to('cuda:0'))
    return pair,enrollments,targets,scale
def unit_objective(unit,estimates,targets,pair,*,torch):
    from companion_tse_source_objective_20261108 import positive_loss,consistency_loss,absence_loss
    if unit['kind']=='absent_known_identity':assert not targets;return absence_loss(estimates[0],pair[0,0],torch=torch)
    loss=sum(positive_loss(a,b,torch=torch) for a,b in zip(estimates,targets))/len(targets)
    if unit['kind']=='known_additive_mixture':assert len(targets)==2;loss=loss+consistency_loss(estimates[0],estimates[1],pair[0,0],torch=torch)
    return loss
