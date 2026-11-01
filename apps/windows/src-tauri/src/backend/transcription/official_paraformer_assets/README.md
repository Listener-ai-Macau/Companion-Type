# FunASR Paraformer-large metadata

The application downloads `model_quant.onnx` from the publisher's fixed revision
`6843c899b177f325d4bbdad8c08d85d5b1321f00`. It appends `metadata.bin`, which
contains ONNX `metadata_props` entries derived from that revision's `config.yaml`
and `am.mvn`, and uses `tokens.txt`, generated in the original token-list order.
This does not change the graph or weights. The publisher's model card labels the
model Apache-2.0. Source and hashes are included in OptionalSpeechModels.txt.

The append convention follows sherpa-onnx's Paraformer metadata conversion:
https://huggingface.co/csukuangfj/sherpa-onnx-paraformer-zh-2023-09-14/blob/main/add-model-metadata.py
