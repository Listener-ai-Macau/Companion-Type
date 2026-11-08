"""Bounded independent CPU numerical controls, not meeting accuracy evidence."""
import os
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
from pathlib import Path
from datetime import datetime
import hashlib,json,time,traceback
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_gss_numpy_backend_20261108 import load_backend
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261108-dual-mic-real-meeting-validation')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2);start=time.perf_counter()
assert not (C/'numpy-numerical-proof.json').exists()
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'CHECKING_PINNED_GSS_CPU_REFERENCE','neuralCalls':0,'qualityQualified':False}
try:
    import numpy as np
    GSS,spectral,beam,cacg,utils=load_backend(read(C/'numpy-backend.json'))
    rng=np.random.default_rng(20261108)
    pcm=rng.integers(-30000,30000,size=(2,16037),dtype=np.int16)
    x=pcm.astype(np.float64)/32768
    spectrum=spectral.stft(x,size=1024,shift=256,fading=True)
    restored=spectral.istft(spectrum,size=1024,shift=256,fading=True)[:,:len(pcm[0])]
    max_error=float(np.max(np.abs(restored-x)))
    assert max_error<1e-10 and np.array_equal(np.rint(restored*32768).astype(np.int16),pcm)
    obs=rng.normal(size=(2,40,7))+1j*rng.normal(size=(2,40,7))
    activities=np.zeros((3,40),dtype=bool);activities[0,:28]=True;activities[1,12:]=True;activities[2,:]=True
    batched=GSS(iterations=20,iterations_post=1)(obs,activities)
    per_frequency=np.concatenate([GSS(iterations=20,iterations_post=1)(obs[:,:,i:i+1],activities) for i in range(7)],axis=-1)
    frequency_error=float(np.max(np.abs(batched-per_frequency)))
    assert frequency_error<1e-8 and np.isfinite(batched).all() and np.all(batched>=0)
    assert np.max(np.abs(batched.sum(axis=0)-1))<1e-10
    matrix=np.array([[2,.3+.2j],[.3-.2j,1]],dtype=np.complex128)
    model=cacg.ComplexAngularCentralGaussian.from_covariance(matrix,eigenvalue_floor=1e-10)
    covariance=(model.covariance_eigenvectors*model.covariance_eigenvalues[None,:])@model.covariance_eigenvectors.conj().T
    y=rng.normal(size=(31,2))+1j*rng.normal(size=(31,2));u=y/np.linalg.norm(y,axis=-1,keepdims=True)
    q=np.einsum('td,dt->t',u.conj(),np.linalg.solve(covariance,u.T)).real
    independent=-2*np.log(q)-np.linalg.slogdet(covariance)[1]
    density_error=float(np.max(np.abs(independent-model.log_pdf(y))))
    assert density_error<1e-8
    Y=obs.transpose(2,0,1);mask=rng.random(size=(7,40))
    native_psd=beam.get_power_spectral_density_matrix(Y,mask)
    reference_psd=np.stack([sum(mask[f,t]*np.outer(Y[f,:,t],Y[f,:,t].conj()) for t in range(40))/mask[f].sum() for f in range(7)])
    psd_error=float(np.max(np.abs(native_psd-reference_psd)));assert psd_error<1e-10
    noise=np.stack([np.eye(2)*(.5+f*.1) for f in range(7)]).astype(np.complex128)
    vector=beam.get_mvdr_vector_souden(native_psd,noise,ref_channel=0,eps=1e-10)
    reference=[]
    for f in range(7):
        phi=np.linalg.inv(noise[f])@reference_psd[f];reference.append((phi/np.trace(phi).real)[:,0])
    vector_error=float(np.max(np.abs(vector-np.stack(reference))));assert vector_error<1e-10
    result.update(state='PASS_PINNED_GSS_NUMPY_NUMERICAL_CONTROLS',numpyVersion=np.__version__,
        stftInverseMaxAbsoluteError=max_error,pcm16RoundtripExactlyEqual=True,
        full20IterationBatchVersusFrequencyLoopMaxError=frequency_error,
        independentInverseCovarianceLogDensityMaxError=density_error,
        independentWeightedOuterProductPsdMaxError=psd_error,
        independentFixedReferenceMvdrMaxError=vector_error,
        nativeGpuParityClaimed=False,realMeetingAccuracyMeasured=False)
except BaseException as e:result.update(state='GSS_CPU_REFERENCE_PREPARATION_FAILURE_RETAINED',error=repr(e),traceback=traceback.format_exc());raise
finally:
    result.update(seconds=time.perf_counter()-start,limits=limits.query());atomic_json(C/'numpy-numerical-proof.json',result);print(json.dumps(result,ensure_ascii=False),flush=True)
