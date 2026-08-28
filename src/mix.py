"""Multi-stem binaural mixing utilities."""

import numpy as np


def peak_normalise(stereo: np.ndarray, peak_target: float = 0.95) -> np.ndarray:
    """Peak-normalise a stereo mix while preserving headroom."""
    stereo = np.asarray(stereo, dtype=float)
    peak = np.max(np.abs(stereo)) if stereo.size else 0.0

    if peak == 0:
        return stereo.copy()

    return stereo * (peak_target / peak)


def mix_binaural_stems(stems, gains=None, peak_target: float = 0.95):
    """Mix multiple stereo binaural stems and prevent clipping."""
    if not stems:
        raise ValueError("At least one stereo stem is required.")

    gains = gains or [1.0] * len(stems)
    if len(gains) != len(stems):
        raise ValueError("gains and stems must have the same length.")

    max_len = max(len(s) for s in stems)
    mix = np.zeros((max_len, 2), dtype=float)

    for stem, gain in zip(stems, gains):
        stem = np.asarray(stem, dtype=float)
        if stem.ndim != 2 or stem.shape[1] != 2:
            raise ValueError("Each stem must have shape (samples, 2).")
        mix[: len(stem)] += gain * stem

    return peak_normalise(mix, peak_target=peak_target)
