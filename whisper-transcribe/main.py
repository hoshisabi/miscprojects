#!/usr/bin/env python3
import argparse
import logging
import os
import sys
import tempfile
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env")


def detect_device():
    # Ask ctranslate2 rather than torch, so the transcription process never
    # loads torch's CUDA libraries alongside ctranslate2's.
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda"
    except ImportError:
        pass
    return "cpu"


def preprocess_audio(audio_path, speed=1.0):
    """Convert to mono 16kHz MP3, optionally speed up. Returns temp file path."""
    from pydub import AudioSegment

    logging.debug("Preprocessing: mono 16kHz, speed=%.2f", speed)
    audio = AudioSegment.from_file(str(audio_path))

    if audio.channels > 1:
        audio = audio.set_channels(1)

    audio = audio.set_frame_rate(16000)

    if speed != 1.0:
        # Shift frame rate to change playback speed (also shifts pitch, acceptable for transcription)
        audio = audio._spawn(audio.raw_data, overrides={"frame_rate": int(16000 * speed)})
        audio = audio.set_frame_rate(16000)

    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    audio.export(tmp.name, format="mp3", bitrate="64k")
    size_mb = Path(tmp.name).stat().st_size / 1024 / 1024
    logging.debug("Preprocessed file: %s (%.1f MB)", tmp.name, size_mb)
    return Path(tmp.name)


def split_audio(audio_path, max_mb=24):
    """Split audio into chunks under max_mb on silence boundaries.
    Returns list of (chunk_path, offset_seconds) tuples."""
    from pydub import AudioSegment
    from pydub.silence import detect_silence

    size_mb = audio_path.stat().st_size / 1024 / 1024
    if size_mb <= max_mb:
        return [(audio_path, 0.0)]

    logging.debug("File is %.1f MB, splitting into <%d MB chunks", size_mb, max_mb)
    audio = AudioSegment.from_file(str(audio_path))
    total_ms = len(audio)
    target_ms = int(total_ms * (max_mb / size_mb) * 0.85)

    silences = detect_silence(audio, min_silence_len=300, silence_thresh=-40)

    chunks = []
    start_ms = 0

    for silence_start, silence_end in silences:
        split_point = (silence_start + silence_end) // 2
        if split_point - start_ms >= target_ms:
            chunk = audio[start_ms:split_point]
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            chunk.export(tmp.name, format="mp3", bitrate="64k")
            chunks.append((Path(tmp.name), start_ms / 1000.0))
            logging.debug("Chunk %d: %.1fs–%.1fs", len(chunks), start_ms / 1000, split_point / 1000)
            start_ms = split_point

    # Final chunk
    chunk = audio[start_ms:]
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    chunk.export(tmp.name, format="mp3", bitrate="64k")
    chunks.append((Path(tmp.name), start_ms / 1000.0))
    logging.debug("Chunk %d: %.1fs–%.1fs (final)", len(chunks), start_ms / 1000, total_ms / 1000)

    return chunks


def transcribe_groq(audio_path, api_key, language="en", speed=1.0, preprocess=True):
    from groq import Groq

    temp_files = []
    try:
        if preprocess:
            processed_path = preprocess_audio(audio_path, speed=speed)
            temp_files.append(processed_path)
        else:
            processed_path = audio_path

        chunks = split_audio(processed_path)
        if len(chunks) > 1:
            logging.debug("Split into %d chunks", len(chunks))
            # These chunk files are temp files too (unless it's the preprocessed file itself)
            temp_files.extend(p for p, _ in chunks if p != processed_path)

        client = Groq(api_key=api_key)
        all_segments = []
        language_detected = language
        language_prob = 1.0

        for i, (chunk_path, offset_sped) in enumerate(chunks):
            if len(chunks) > 1:
                logging.debug("Transcribing chunk %d/%d (offset %.1fs)", i + 1, len(chunks), offset_sped)
            with open(chunk_path, "rb") as f:
                result = client.audio.transcriptions.create(
                    file=(chunk_path.name, f),
                    model="whisper-large-v3",
                    language=language,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"],
                )
            language_detected = result.language
            language_prob = getattr(result, "language_probability", 1.0)

            for seg in result.segments:
                t_start = seg["start"] if isinstance(seg, dict) else seg.start
                t_end = seg["end"] if isinstance(seg, dict) else seg.end
                text = seg["text"] if isinstance(seg, dict) else seg.text
                # Convert sped-up timestamps back to original audio time
                orig_start = (t_start + offset_sped) * speed
                orig_end = (t_end + offset_sped) * speed
                all_segments.append((orig_start, orig_end, text))

        return language_detected, language_prob, all_segments

    finally:
        for f in temp_files:
            try:
                f.unlink()
            except Exception:
                pass


def diarize(audio_path, hf_token, num_speakers=None):
    """Run pyannote speaker diarization. Returns list of (start, end, speaker) tuples."""
    from pyannote.audio import Pipeline
    from pydub import AudioSegment
    import torch

    logging.debug("Loading pyannote diarization pipeline")
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        token=hf_token,
    )
    device = "cuda" if torch.cuda.is_available() else "cpu"
    pipeline = pipeline.to(torch.device(device))

    # torchcodec is broken on Windows, and torchaudio falls back to it too.
    # Load via pydub and convert raw samples to a torch tensor directly.
    logging.debug("Extracting audio for diarization")
    audio = AudioSegment.from_file(str(audio_path))
    if audio.channels > 1:
        audio = audio.set_channels(1)
    audio = audio.set_frame_rate(16000)

    import numpy as np
    samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
    samples /= float(2 ** (8 * audio.sample_width - 1))  # normalize to [-1.0, 1.0]
    waveform = torch.from_numpy(samples).unsqueeze(0)  # (1, num_samples)
    audio_input = {"waveform": waveform, "sample_rate": audio.frame_rate}
    logging.debug("Waveform shape=%s sample_rate=%d max=%.4f", waveform.shape, audio.frame_rate, waveform.abs().max().item())

    logging.debug("Running diarization (device=%s)", device)
    kwargs = {}
    if num_speakers is not None:
        kwargs["num_speakers"] = num_speakers
    diarization = pipeline(audio_input, **kwargs)

    if hasattr(diarization, "speaker_diarization"):
        sd_turns = list(diarization.speaker_diarization.itertracks(yield_label=True))
        ex_turns = list(diarization.exclusive_speaker_diarization.itertracks(yield_label=True))
        logging.debug("speaker_diarization turns=%d exclusive turns=%d", len(sd_turns), len(ex_turns))
        annotation = diarization.exclusive_speaker_diarization if ex_turns else diarization.speaker_diarization
    else:
        annotation = diarization
    turns = [
        (turn.start, turn.end, speaker)
        for turn, _, speaker in annotation.itertracks(yield_label=True)
    ]
    logging.debug("Diarization found %d turns", len(turns))
    return turns


def assign_speakers(segments, turns):
    """Map each (start, end, text) segment to the speaker with the most overlap."""
    result = []
    for start, end, text in segments:
        best_speaker = "UNKNOWN"
        best_overlap = 0.0
        for t_start, t_end, speaker in turns:
            overlap = max(0.0, min(end, t_end) - max(start, t_start))
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = speaker
        result.append((start, end, best_speaker, text))
    return result


SAMPLE_RATE = 16000


def find_split_points(samples, sample_rate, chunk_s, search_s=30.0, window_s=0.5):
    """Return sample offsets at which to cut audio into ~chunk_s slices.

    Each cut lands in the quietest window_s window within +/- search_s of the
    target, so slices rarely end mid-word. The first offset is always 0.
    chunk_s <= 0 disables splitting."""
    import numpy as np

    total = len(samples)
    chunk = int(chunk_s * sample_rate)
    if chunk <= 0:
        return [0]
    search = min(int(search_s * sample_rate), chunk // 2)
    window = max(1, int(window_s * sample_rate))

    points = [0]
    # Stop once the remainder fits in one slice plus the search margin, so the
    # last slice is never a sliver.
    while total - points[-1] > chunk + search:
        center = points[-1] + chunk
        lo = center - search
        region = samples[lo:center + search]
        n = len(region) // window
        if n == 0:
            points.append(center)
            continue
        frames = np.asarray(region[:n * window], dtype=np.float32).reshape(n, window)
        quietest = int(np.argmin((frames ** 2).mean(axis=1)))
        points.append(lo + quietest * window + window // 2)
    return points


def transcribe_local(audio_path, args):
    """Transcribe in slices of args.chunk_minutes. Returns (segments, info), where
    segments yields (start, end, text) in seconds from the start of the file and
    info comes from the first slice."""
    from faster_whisper import WhisperModel, decode_audio
    device = args.device if args.device and args.device != "auto" else detect_device()
    if args.compute_type and args.compute_type != "auto":
        compute_type = args.compute_type
    elif device == "cuda":
        # float16 is ideal, but Pascal (sm_6x, e.g. GTX 10-series) lacks efficient
        # fp16 and CTranslate2 rejects it -- fall back to int8 there.
        try:
            import torch
            major = torch.cuda.get_device_capability(0)[0]
            compute_type = "float16" if major >= 7 else "int8"
        except Exception:
            compute_type = "int8"
    else:
        compute_type = "int8"
    logging.debug("Loading model '%s' on %s (%s)", args.model, device, compute_type)
    model = WhisperModel(
        args.model,
        device=device,
        compute_type=compute_type,
        cpu_threads=args.cpu_threads,
        num_workers=2,
    )

    logging.debug("Decoding audio")
    audio = decode_audio(str(audio_path), sampling_rate=SAMPLE_RATE)
    points = find_split_points(audio, SAMPLE_RATE, args.chunk_minutes * 60)
    bounds = list(zip(points, points[1:] + [len(audio)]))
    logging.debug("Audio is %.1fs, transcribing in %d slice(s)", len(audio) / SAMPLE_RATE, len(bounds))

    def run(start, end):
        return model.transcribe(
            audio[start:end],
            beam_size=args.beam_size,
            vad_filter=True,
            vad_parameters=dict(
                threshold=args.vad_threshold,
                min_silence_duration_ms=args.vad_min_silence_ms,
                speech_pad_ms=args.vad_speech_pad_ms,
            ),
            language=args.language,
            repetition_penalty=args.repetition_penalty,
        )

    first_segments, info = run(*bounds[0])

    def segments():
        for i, (start, end) in enumerate(bounds):
            offset = start / SAMPLE_RATE
            if len(bounds) > 1:
                logging.debug("Slice %d/%d: %.1fs-%.1fs", i + 1, len(bounds), offset, end / SAMPLE_RATE)
            slice_segments = first_segments if i == 0 else run(start, end)[0]
            for seg in slice_segments:
                yield seg.start + offset, seg.end + offset, seg.text

    return segments(), info


def setup_logging(verbose=False, quiet=False):
    level = logging.WARNING
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
    )


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe audio files using Whisper (local or Groq API)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py audio.wav
  python main.py audio.mp3 --out transcript.txt
  python main.py audio.wav --speed 1.5 --out transcript.txt
  python main.py audio.wav --model distil-large-v3 --out transcript.txt
  python main.py meeting.wav --local --out transcript.txt   # never uses cloud, even if a key is set

Groq API key can be set via GROQ_API_KEY in .env or environment.
Note: Groq preprocessing requires ffmpeg to be installed.
        """
    )

    parser.add_argument("audio_file", help="Path to the audio file to transcribe")
    parser.add_argument(
        "-o", "--out",
        help="Write transcript to file (default: stdout)"
    )
    parser.add_argument(
        "--groq-key",
        default=os.environ.get("GROQ_API_KEY"),
        help="Groq API key (or set GROQ_API_KEY env var); uses Groq cloud if provided"
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Force local transcription even if a Groq key is present (overrides --groq-key / GROQ_API_KEY). Use for audio that must not leave this machine."
    )

    # Diarization options (local path only)
    parser.add_argument(
        "--diarize",
        action="store_true",
        help="Run speaker diarization via pyannote (local path only; requires HF token)"
    )
    parser.add_argument(
        "--hf-token",
        default=os.environ.get("HF_TOKEN"),
        help="HuggingFace token for pyannote model access (or set HF_TOKEN env var)"
    )
    parser.add_argument(
        "--num-speakers",
        type=int,
        default=None,
        help="Expected number of speakers (optional hint for diarization)"
    )

    # Groq options
    parser.add_argument(
        "--no-preprocess",
        action="store_true",
        help="Skip mono/16kHz conversion before sending to Groq"
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Speed up audio before transcribing, e.g. 1.5 or 1.7 (reduces quota usage; default: 1.0)"
    )

    # Local model options
    parser.add_argument(
        "-m", "--model",
        default="distil-large-v3",
        choices=["tiny", "base", "small", "medium", "large-v2", "large-v3", "distil-large-v3"],
        help="Whisper model for local transcription (default: distil-large-v3); ignored when using Groq"
    )
    parser.add_argument(
        "--device",
        default=None,
        choices=["cpu", "cuda", "auto"],
        help="Device for local transcription (default: auto-detect); ignored when using Groq"
    )
    parser.add_argument(
        "--compute-type",
        default="auto",
        choices=["auto", "float16", "int8", "int8_float16", "float32"],
        help="CTranslate2 compute type (default: auto - float16 on Turing+ GPUs, int8 on Pascal/CPU); ignored when using Groq"
    )
    parser.add_argument(
        "-l", "--language",
        default="en",
        help="Audio language code, e.g., en, fr, de (default: en)"
    )
    parser.add_argument(
        "--beam-size",
        type=int,
        default=3,
        help="Beam size for local decoding (default: 3)"
    )
    parser.add_argument(
        "--repetition-penalty",
        type=float,
        default=1.2,
        help="Penalty to suppress repetition loops (default: 1.2)"
    )
    parser.add_argument(
        "--cpu-threads",
        type=int,
        default=12,
        help="Number of CPU threads for local transcription (default: 12)"
    )
    parser.add_argument(
        "--chunk-minutes",
        type=float,
        default=10,
        help="Transcribe locally in slices of this many minutes, cut at the quietest point nearby; 0 = whole file at once (default: 10)"
    )
    parser.add_argument(
        "--vad-threshold",
        type=float,
        default=0.3,
        help="VAD sensitivity 0.0-1.0; lower = less aggressive (default: 0.3)"
    )
    parser.add_argument(
        "--vad-min-silence-ms",
        type=int,
        default=500,
        help="Minimum silence duration in ms before splitting a segment (default: 500)"
    )
    parser.add_argument(
        "--vad-speech-pad-ms",
        type=int,
        default=400,
        help="Padding in ms added around detected speech (default: 400)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug output"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Only show errors"
    )

    args = parser.parse_args()
    setup_logging(verbose=args.verbose, quiet=args.quiet)

    if args.local and args.groq_key:
        logging.debug("--local set; ignoring Groq key and transcribing locally")
        args.groq_key = None

    audio_path = Path(args.audio_file)
    if not audio_path.exists():
        logging.error("Audio file not found: %s", args.audio_file)
        sys.exit(1)
    if not audio_path.is_file():
        logging.error("Not a file: %s", args.audio_file)
        sys.exit(1)

    out_file = None
    if args.out:
        try:
            out_file = open(args.out, "w", encoding="utf-8")
        except IOError as e:
            logging.error("Cannot write to %s: %s", args.out, e)
            sys.exit(1)

    try:
        if args.groq_key and args.diarize:
            logging.error("--diarize is only supported with local transcription; cannot be used with Groq API")
            sys.exit(1)

        if args.groq_key:
            logging.debug("Using Groq API (key: %s...%s)", args.groq_key[:6], args.groq_key[-4:])
            language, prob, segments = transcribe_groq(
                audio_path,
                args.groq_key,
                language=args.language,
                speed=args.speed,
                preprocess=not args.no_preprocess,
            )
            print("Detected language '%s' with probability %.2f" % (language, prob), file=out_file)
            for start, end, text in segments:
                line = "[%.2fs -> %.2fs] %s" % (start, end, text)
                print(line, file=out_file)
                logging.debug("Segment: %.2f -> %.2f: %s", start, end, text)
        else:
            if args.diarize and not args.hf_token:
                logging.error("--diarize requires an HF token (--hf-token or HF_TOKEN env var)")
                sys.exit(1)

            logging.debug("Using local model '%s'", args.model)
            segments_gen, info = transcribe_local(audio_path, args)
            print("Detected language '%s' with probability %.2f" % (info.language, info.language_probability), file=out_file)

            if args.diarize:
                turns = diarize(audio_path, args.hf_token, num_speakers=args.num_speakers)
                labeled = assign_speakers(list(segments_gen), turns)
                for start, end, speaker, text in labeled:
                    line = "[%s] [%.2fs -> %.2fs] %s" % (speaker, start, end, text)
                    print(line, file=out_file)
                    logging.debug("Segment: %s %.2f -> %.2f: %s", speaker, start, end, text)
            else:
                for start, end, text in segments_gen:
                    line = "[%.2fs -> %.2fs] %s" % (start, end, text)
                    print(line, file=out_file)
                    logging.debug("Segment: %.2f -> %.2f: %s", start, end, text)
    finally:
        if out_file:
            out_file.close()
            logging.info("Transcript saved to: %s", args.out)


if __name__ == "__main__":
    main()
