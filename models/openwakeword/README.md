# Hey HAL model

Place an openWakeWord ONNX model trained for "Hey HAL" at `hey-hal.onnx`, or set
`OPENWAKEWORD_MODEL_PATH` to another model file.

The former Porcupine `.ppn` model cannot be converted because it is a proprietary,
runtime-specific format. Train an openWakeWord model with the project's upstream Colab or
training workflow, then test it in the target room with `python scripts/test_wakeword.py`.

Model files have their own training-data and distribution terms. Record the model's source and
license here before committing one to the repository.

## Bundled runtime assets

The shared ONNX feature models come from openWakeWord v0.5.1 and are used by the 0.6.0 runtime:

- `embedding_model.onnx`: SHA-256 `70D164290C1D095D1D4EE149BC5E00543250A7316B59F31D056CFF7BD3075C1F`
- `melspectrogram.onnx`: SHA-256 `BA2B0E0F8B7B875369A2C89CB13360FF53BAC436F2895CCED9F479FA65EB176F`

Source: <https://github.com/dscripka/openWakeWord/releases/tag/v0.5.1>. These runtime assets are
covered by openWakeWord's Apache 2.0 license in `LICENSE.openwakeword.txt`. A separately trained
wake-phrase model may have different terms.
