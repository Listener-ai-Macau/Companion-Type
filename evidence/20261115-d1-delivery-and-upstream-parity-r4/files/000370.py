"""Bounded-RAM loading of a hash-pinned safetensors file, without mmap.

The public format is an8-byte header length, JSON tensor metadata, then tensor
bytes. Copy bounded byte ranges to the fixed device and verify their roundtrip
hash. No training, quantization, dtype conversion or CPU parameter offload.
"""
from pathlib import Path
import hashlib,json,math,struct,time


def load_streamed_weights(path, *, torch, device, expected_sha256, chunk_bytes=16*1024**2, tensor_prefixes=None):
    started=time.perf_counter();path=Path(path)
    assert 64<=chunk_bytes<=16*1024**2
    if tensor_prefixes is not None:
        assert tensor_prefixes and set(tensor_prefixes)<={'model.language_model.','model.whisper_encoder.','model.vq_adaptor.'},'Only exact declared stage groups'
    dtypes={'BF16':(torch.bfloat16,2),'F16':(torch.float16,2),'F32':(torch.float32,4),
            'F64':(torch.float64,8),'I64':(torch.int64,8),'I32':(torch.int32,4),
            'I16':(torch.int16,2),'I8':(torch.int8,1),'U8':(torch.uint8,1),'BOOL':(torch.bool,1)}
    source_hash=hashlib.sha256();roundtrip_hash=hashlib.sha256();selected_source=hashlib.sha256();selected_return=hashlib.sha256();result={};copied=0;largest=0
    with path.open('rb',buffering=0) as stream:
        prefix=stream.read(8);assert len(prefix)==8
        header_size=struct.unpack('<Q',prefix)[0];assert 0<header_size<=100*1024**2
        raw_header=stream.read(header_size);assert len(raw_header)==header_size
        header=json.loads(raw_header);items=[(key,value) for key,value in header.items() if key!='__metadata__']
        assert 0<len(items)<10000
        source_hash.update(prefix+raw_header);roundtrip_hash.update(prefix+raw_header)
        items.sort(key=lambda pair:pair[1]['data_offsets'][0]);offset=0
        scratch=bytearray(chunk_bytes)
        return_buffer=bytearray(chunk_bytes)
        return_tensor=torch.frombuffer(return_buffer,dtype=torch.uint8)
        for name,meta in items:
            start,end=meta['data_offsets'];shape=meta['shape'];dtype,size=dtypes[meta['dtype']]
            assert isinstance(name,str) and all(isinstance(n,int) and n>=0 for n in shape)
            assert start==offset and end>=start and end-start==math.prod(shape)*size
            assert end<=path.stat().st_size-8-header_size
            selected=tensor_prefixes is None or any(name.startswith(group) for group in tensor_prefixes)
            if selected:value=torch.empty(shape,dtype=dtype,device=device);flat=value.reshape(-1)
            within=0
            while start+within<end:
                take=min(chunk_bytes-chunk_bytes%size,end-start-within)
                view=memoryview(scratch)[:take]
                assert stream.readinto(view)==take,'Truncated pinned checkpoint'
                source_hash.update(view)
                if not selected:
                    within+=take
                    del view
                    continue
                selected_source.update(view)
                cpu_view=torch.frombuffer(view,dtype=dtype)
                target=flat[within//size:(within+take)//size]
                target.copy_(cpu_view,non_blocking=False)
                # A bitwise roundtrip is cheap compared with inference and
                # proves the published bytes survived the transfer unchanged.
                # Reuse one bounded CPU destination instead of allocating a
                # new CPU tensor, NumPy owner and Python bytes for every slice.
                # Blocking byte copy preserves dtype bits, including BF16.
                return_tensor[:take].copy_(target.view(torch.uint8),non_blocking=False)
                payload=memoryview(return_buffer)[:take]
                assert payload==view
                roundtrip_hash.update(payload)
                selected_return.update(payload)
                del cpu_view,target,payload,view
                within+=take;copied+=take;largest=max(largest,take)
            if selected:result[name]=value
            offset=end
        assert stream.tell()==path.stat().st_size,'Unaccounted checkpoint bytes'
    assert source_hash.hexdigest()==expected_sha256,'Pinned file changed; do not infer'
    if tensor_prefixes is None:assert roundtrip_hash.hexdigest()==expected_sha256,'Device tensors differ from pinned bytes'
    assert result and selected_source.hexdigest()==selected_return.hexdigest(),'Selected device tensors differ from source bytes'
    receipt={'state':'PINNED_TENSOR_BYTES_STREAMED_AND_ROUNDTRIP_VERIFIED' if tensor_prefixes is None else 'PINNED_STAGE_TENSORS_STREAMED_AND_ROUNDTRIP_VERIFIED','tensorCount':len(result),
      'dataBytesCopied':copied,'maximumTransferChunkBytes':largest,'scratchBytes':chunk_bytes,
      'roundtripBufferBytes':chunk_bytes,'roundtripCpuBufferReused':True,
      'fileSha256':source_hash.hexdigest(),'deviceRoundtripSha256':roundtrip_hash.hexdigest() if tensor_prefixes is None else None,
      'selectedSourceBytesSha256':selected_source.hexdigest(),'selectedDeviceBytesSha256':selected_return.hexdigest(),
      'selectedPrefixes':tensor_prefixes,'sourceTensorCount':len(items),'skippedTensorCount':len(items)-len(result),
      'targetDevice':str(device),'mmapUsed':False,'wholeCpuStateDictCreated':False,
      'seconds':time.perf_counter()-started}
    return result,receipt
