# TODO

## Two-pass diarization to fix OOM on long files

When `--diarize` is used with long recordings (3+ hours), both the whisper model and pyannote
pipeline are live in VRAM simultaneously, causing an OOM kill on 12GB cards.

Fix: restructure `main()` to materialize whisper segments first, then flush VRAM before diarizing.

```python
segments_gen, info = transcribe_local(audio_path, args)
raw_segments = list(segments_gen)   # materialize before diarization
del model                            # need to expose model ref from transcribe_local
torch.cuda.empty_cache()
turns = diarize(audio_path, ...)
```

`transcribe_local()` will need to return the model object so the caller can del it, or accept a
callback, or be restructured to not hold the model after transcription completes.
