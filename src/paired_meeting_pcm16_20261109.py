"""Bounded reads of unchanged PCM16 RIFF, including the official extensible header."""
from pathlib import Path
import struct

PCM_GUID = bytes.fromhex('0100000000001000800000aa00389b71')

def info(path):
    path = Path(path)
    with path.open('rb') as handle:
        head = handle.read(12)
        assert len(head) == 12 and head[:4] == b'RIFF' and head[8:] == b'WAVE'
        riff_end = struct.unpack_from('<I', head, 4)[0] + 8
        assert riff_end <= path.stat().st_size
        fmt = None
        while handle.tell() + 8 <= riff_end:
            kind, size = struct.unpack('<4sI', handle.read(8))
            start = handle.tell()
            assert start + size <= riff_end
            if kind == b'fmt ':
                assert 16 <= size <= 4096
                raw = handle.read(size)
                tag, channels, rate, byte_rate, align, bits = struct.unpack_from('<HHIIHH', raw)
                assert tag in [1, 65534] and bits == 16 and align == 2 * channels and byte_rate == rate * align
                if tag == 65534:
                    assert len(raw) >= 40 and struct.unpack_from('<H', raw, 16)[0] >= 22
                    assert struct.unpack_from('<H', raw, 18)[0] == 16 and raw[24:40] == PCM_GUID
                fmt = {'formatTag': tag, 'rate': rate, 'channels': channels, 'width': 2, 'blockAlign': align}
            elif kind == b'data':
                assert fmt is not None and size % fmt['blockAlign'] == 0
                return {**fmt, 'dataOffset': start, 'dataBytes': size,
                        'frames': size // fmt['blockAlign'],
                        'seconds': size / fmt['blockAlign'] / fmt['rate']}
            handle.seek(start + size + (size % 2))
    raise ValueError('No supported PCM data chunk')

def read(path, start_frame, end_frame, channel=0, metadata=None):
    import numpy as np
    meta = metadata if metadata is not None else info(path)
    assert 0 <= start_frame <= end_frame <= meta['frames']
    assert channel is None or 0 <= channel < meta['channels']
    with Path(path).open('rb') as handle:
        handle.seek(meta['dataOffset'] + start_frame * meta['blockAlign'])
        raw = handle.read((end_frame - start_frame) * meta['blockAlign'])
    assert len(raw) == (end_frame - start_frame) * meta['blockAlign']
    pcm = np.frombuffer(raw, dtype='<i2').reshape(-1, meta['channels'])
    return pcm if channel is None else pcm[:, channel]
