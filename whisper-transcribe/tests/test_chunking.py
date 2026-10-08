import numpy as np

from main import find_split_points

SR = 100  # small rate keeps the arrays tiny


def noise(seconds, rng):
    return rng.uniform(-1, 1, int(seconds * SR)).astype(np.float32)


def test_short_audio_is_one_slice():
    rng = np.random.default_rng(0)
    assert find_split_points(noise(90, rng), SR, chunk_s=60, search_s=30) == [0]


def test_zero_chunk_disables_splitting():
    rng = np.random.default_rng(0)
    assert find_split_points(noise(1000, rng), SR, chunk_s=0) == [0]


def test_cut_lands_in_silence_near_target():
    rng = np.random.default_rng(0)
    audio = noise(200, rng)
    # Silence from 70s to 71s, inside the +/-30s search window around 60s.
    audio[70 * SR:71 * SR] = 0
    points = find_split_points(audio, SR, chunk_s=60, search_s=30, window_s=0.5)
    assert 70 * SR <= points[1] <= 71 * SR


def test_cuts_advance_and_last_slice_is_not_a_sliver():
    rng = np.random.default_rng(0)
    audio = noise(3000, rng)
    points = find_split_points(audio, SR, chunk_s=600, search_s=30)
    assert points[0] == 0
    assert all(b > a for a, b in zip(points, points[1:]))
    gaps = np.diff(points + [len(audio)]) / SR
    assert all(570 <= g <= 660 for g in gaps[:-1])
    assert gaps[-1] >= 30
