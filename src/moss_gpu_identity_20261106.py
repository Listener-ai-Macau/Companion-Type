"""Choose the declared external GPU by identity; an index is only a hint."""

class DeclaredGpuUnavailable(RuntimeError):
    pass


def enumerate_native_gpus(torch):
    devices=[]
    for index in range(torch.cuda.device_count()):
        properties=torch.cuda.get_device_properties(index)
        devices.append({'index':index,'name':properties.name,
                        'architecture':properties.gcnArchName,
                        'reportedMemoryBytes':properties.total_memory})
    return devices


def select_rx6800xt(devices, index_hint=None):
    candidates=[device for device in devices
                if 'rx 6800 xt' in ' '.join(device['name'].lower().split())
                and device['architecture'].startswith('gfx1030')]
    if not candidates:
        names=', '.join(device['name'] for device in devices) or 'no native GPU'
        raise DeclaredGpuUnavailable('Declared external RX 6800 XT/gfx1030 is not available; detected: '+names)
    if len(candidates)!=1:
        raise DeclaredGpuUnavailable('Multiple RX 6800 XT devices detected; explicit physical identity required')
    chosen=dict(candidates[0])
    chosen.update(requestedIndexHint=index_hint,indexChangedFromHint=index_hint!=chosen['index'],
                  selectionPolicy='Unique RX 6800 XT and gfx1030 identity; never substitute integrated graphics')
    return chosen
