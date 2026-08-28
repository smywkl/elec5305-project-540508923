"""Evaluation scaffold for separated and binaural audio."""

import numpy as np
from scipy.signal import correlate


def rms(x):
    x = np.asarray(x, dtype=float)
    return np.sqrt(np.mean(x ** 2) + 1e-12)


def ild_db(stereo):
    """Simple broadband Interaural Level Difference estimate."""
    stereo = np.asarray(stereo, dtype=float)
    left_rms = rms(stereo[:, 0])
    right_rms = rms(stereo[:, 1])
    return 20.0 * np.log10((right_rms + 1e-12) / (left_rms + 1e-12))


def itd_seconds(stereo, sample_rate):
    """Estimate ITD from the peak of left/right cross-correlation."""
    stereo = np.asarray(stereo, dtype=float)
    left = stereo[:, 0] - np.mean(stereo[:, 0])
    right = stereo[:, 1] - np.mean(stereo[:, 1])

    corr = correlate(right, left, mode="full")
    lags = np.arange(-len(left) + 1, len(right))
    best_lag = lags[np.argmax(corr)]
    return best_lag / float(sample_rate)


if __name__ == "__main__":
    fs = 44100
    left = np.zeros(2048)
    right = np.zeros(2048)
    left[100] = 0.5
    right[110] = 1.0
    stereo = np.column_stack([left, right])

    print("ILD (dB):", ild_db(stereo))
    print("ITD (s):", itd_seconds(stereo, fs))
