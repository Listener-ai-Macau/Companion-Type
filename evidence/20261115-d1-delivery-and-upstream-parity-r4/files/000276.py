"""Observe raw greedy tokens before the author's timestamp reconstruction.

The pinned generate() rebuilds timestamped output using the tokenizer. Its final
tensor is not the raw decoder sequence and cannot prove EOS termination. This
observer calls the original sampler unchanged, and copies only its returned IDs.
"""
from contextlib import contextmanager
import types


@contextmanager
def capture_raw_greedy_sequences(model):
    original = model._sample
    had_instance_value = '_sample' in model.__dict__
    prior_instance_value = model.__dict__.get('_sample')
    calls = []

    def observed(self, *args, **kwargs):
        output = original(*args, **kwargs)
        sequences = output.sequences if hasattr(output, 'sequences') else output
        calls.append(sequences.detach().cpu().tolist())
        return output

    model._sample = types.MethodType(observed, model)
    try:
        yield calls
    finally:
        if had_instance_value:
            model._sample = prior_instance_value
        else:
            del model._sample
