# TODO

Nothing open.

## Done

- **Two-pass diarization to fix OOM on long files.** `--diarize` now runs pyannote in a child
  process (`diarize_in_subprocess`) that exits before the whisper model loads, so the two models
  are never in VRAM together.
- **Native abort (0xC0000409) on long local runs.** Caused by ctranslate2 4.7.1's CUDA sampling
  path (used by faster-whisper's temperature fallback); fixed by requiring ctranslate2 >= 4.8.2.
  Local transcription also runs in `--chunk-minutes` slices and writes output line-buffered.
