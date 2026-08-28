"""Static binaural spatialisation functions."""

import numpy as np
from scipy.signal import fftconvolve


def spatialize_static(source: np.ndarray, hrir_left: np.ndarray, hrir_right: np.ndarray):
    """Render one source at one fixed binaural position.

    y_L(t) = s(t) * h_L(t)
    y_R(t) = s(t) * h_R(t)
    """
    source = np.asarray(source, dtype=float).reshape(-1)
    hrir_left = np.asarray(hrir_left, dtype=float).reshape(-1)
    hrir_right = np.asarray(hrir_right, dtype=float).reshape(-1)

    left = fftconvolve(source, hrir_left, mode="full")
    right = fftconvolve(source, hrir_right, mode="full")

    length = max(len(left), len(right))
    stereo = np.zeros((length, 2), dtype=float)
    stereo[: len(left), 0] = left
    stereo[: len(right), 1] = right
    return stereo


if __name__ == "__main__":
    # Minimal numerical smoke test with synthetic impulse responses.
    x = np.zeros(1024)
    x[0] = 1.0

    h_l = np.array([1.0, 0.2, 0.05])
    h_r = np.array([0.7, 0.1, 0.02])

    y = spatialize_static(x, h_l, h_r)
    print("Static spatialisation smoke-test output shape:", y.shape)
