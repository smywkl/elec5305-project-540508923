"""Transparent source-level metrics matching the frozen Phase 2.3 semantics."""

from __future__ import annotations

import importlib.metadata
import inspect
import os
from pathlib import Path
import sys

import numpy as np


SI_SDR_CAP_DB = 300.0
FLOAT64_EPSILON = float(np.finfo(np.float64).eps)
BSS_EVAL_FILTERS_LEN = 512


def _load_museval_bss_eval():
    """Load museval after activating the current Conda runtime on Windows."""
    if os.name == "nt":
        conda_runtime = Path(sys.prefix) / "Library" / "bin"
        ffmpeg_path = conda_runtime / "ffmpeg.exe"
        ffprobe_path = conda_runtime / "ffprobe.exe"
        if not ffmpeg_path.is_file() or not ffprobe_path.is_file():
            raise RuntimeError(
                "museval requires ffmpeg and ffprobe in the elec5305 Conda runtime"
            )
        path_entries = os.environ.get("PATH", "").split(os.pathsep)
        if str(conda_runtime) not in path_entries:
            os.environ["PATH"] = str(conda_runtime) + os.pathsep + os.environ.get(
                "PATH", ""
            )

    import museval
    from museval.metrics import bss_eval

    required_parameters = {
        "window",
        "hop",
        "compute_permutation",
        "filters_len",
        "framewise_filters",
        "bsseval_sources_version",
    }
    signature = inspect.signature(bss_eval)
    if not required_parameters.issubset(signature.parameters):
        raise RuntimeError(f"Unexpected museval bss_eval signature: {signature}")
    distribution_version = importlib.metadata.version("museval")
    if distribution_version != "0.4.1":
        raise RuntimeError(f"Expected museval 0.4.1, received {distribution_version}")
    return museval, bss_eval, str(signature)


def bss_eval_v4_whole_excerpt(
    reference_sources: np.ndarray, estimated_sources: np.ndarray
) -> dict[str, object]:
    """Run identity-fixed museval BSS Eval v4 on one whole excerpt."""
    reference = np.asarray(reference_sources, dtype=np.float64)
    estimate = np.asarray(estimated_sources, dtype=np.float64)
    if reference.shape != estimate.shape or reference.ndim != 3:
        raise ValueError("BSS Eval inputs must share shape (sources, frames, channels)")
    if reference.shape[0] < 2 or reference.shape[1] == 0 or reference.shape[2] != 1:
        raise ValueError("BSS Eval requires at least two nonempty mono sources")
    if not np.isfinite(reference).all() or not np.isfinite(estimate).all():
        raise ValueError("BSS Eval inputs contain NaN or Inf")

    museval, bss_eval, signature = _load_museval_bss_eval()
    sdr, isr, sir, sar, perm = bss_eval(
        reference,
        estimate,
        window=np.inf,
        hop=np.inf,
        compute_permutation=False,
        filters_len=BSS_EVAL_FILTERS_LEN,
        framewise_filters=False,
        bsseval_sources_version=False,
    )
    expected_shape = (reference.shape[0], 1)
    outputs = {"sdr": sdr, "isr": isr, "sir": sir, "sar": sar, "perm": perm}
    if any(np.asarray(value).shape != expected_shape for value in outputs.values()):
        shapes = {name: list(np.asarray(value).shape) for name, value in outputs.items()}
        raise RuntimeError(f"Unexpected whole-excerpt BSS Eval output shapes: {shapes}")
    expected_permutation = np.arange(reference.shape[0], dtype=perm.dtype)[:, None]
    if not np.array_equal(perm, expected_permutation):
        raise RuntimeError(f"BSS Eval returned non-identity permutation: {perm.tolist()}")
    if not np.isfinite(sir).all():
        raise RuntimeError(f"BSS Eval returned nonfinite SIR: {sir.tolist()}")

    return {
        "sdr": np.asarray(sdr, dtype=np.float64),
        "isr": np.asarray(isr, dtype=np.float64),
        "sir": np.asarray(sir, dtype=np.float64),
        "sar": np.asarray(sar, dtype=np.float64),
        "perm": np.asarray(perm),
        "museval_distribution_version": importlib.metadata.version("museval"),
        "museval_module_version_attribute": getattr(museval, "__version__", None),
        "bss_eval_signature": signature,
    }


def run_sir_sanity_checks() -> dict[str, object]:
    """Verify high clean SIR, interference sensitivity, and fixed identity."""
    sample_count = 1024
    sample_index = np.arange(sample_count, dtype=np.float64)
    source_1 = np.sin(2.0 * np.pi * 17.0 * sample_index / sample_count) + 0.3 * np.sin(
        2.0 * np.pi * 43.0 * sample_index / sample_count + 0.2
    )
    source_2 = np.cos(2.0 * np.pi * 71.0 * sample_index / sample_count + 0.4) + 0.2 * np.sin(
        2.0 * np.pi * 101.0 * sample_index / sample_count
    )
    reference = np.stack([source_1, source_2], axis=0)[:, :, None]
    case_a_estimate = np.stack(
        [source_1 + 1e-3 * source_2, source_2 + 1e-3 * source_1], axis=0
    )[:, :, None]
    case_b_estimate = np.stack(
        [source_1 + 0.5 * source_2, source_2 + 1e-3 * source_1], axis=0
    )[:, :, None]

    case_a = bss_eval_v4_whole_excerpt(reference, case_a_estimate)
    case_b = bss_eval_v4_whole_excerpt(reference, case_b_estimate)
    case_a_sir = case_a["sir"].reshape(-1)
    case_b_sir = case_b["sir"].reshape(-1)
    source_1_drop_db = float(case_a_sir[0] - case_b_sir[0])
    identity = [0, 1]
    passed = (
        bool(np.all(case_a_sir > 40.0))
        and source_1_drop_db > 20.0
        and case_a["perm"].reshape(-1).tolist() == identity
        and case_b["perm"].reshape(-1).tolist() == identity
    )
    if not passed:
        raise RuntimeError("Synthetic BSS Eval v4 SIR sanity test failed")
    return {
        "passed": True,
        "reference_shape": list(reference.shape),
        "case_a_sir_db": case_a_sir.tolist(),
        "case_b_sir_db": case_b_sir.tolist(),
        "source_1_sir_drop_db": source_1_drop_db,
        "case_a_permutation": case_a["perm"].reshape(-1).astype(int).tolist(),
        "case_b_permutation": case_b["perm"].reshape(-1).astype(int).tolist(),
    }


def mono_downmix(stereo: np.ndarray) -> np.ndarray:
    """Apply the fixed Phase 2 stereo-to-mono equation."""
    audio = np.asarray(stereo, dtype=np.float64)
    if audio.ndim != 2 or audio.shape[0] == 0 or audio.shape[1] != 2:
        raise ValueError("stereo input must have shape [frames, 2]")
    if not np.isfinite(audio).all():
        raise ValueError("stereo input contains NaN or Inf")
    mono = 0.5 * (audio[:, 0] + audio[:, 1])
    if not np.isfinite(mono).all():
        raise ValueError("mono output contains NaN or Inf")
    return mono


def transparent_si_sdr_db(reference: np.ndarray, estimate: np.ndarray) -> float:
    """Compute zero-mean projection SI-SDR with the Phase 2.3 finite cap."""
    reference_array = np.asarray(reference, dtype=np.float64).reshape(-1)
    estimate_array = np.asarray(estimate, dtype=np.float64).reshape(-1)
    if reference_array.shape != estimate_array.shape or reference_array.size == 0:
        raise ValueError("SI-SDR inputs must be nonempty and have identical shapes")
    if not np.isfinite(reference_array).all() or not np.isfinite(estimate_array).all():
        raise ValueError("SI-SDR inputs contain NaN or Inf")

    reference_zero_mean = reference_array - np.mean(reference_array)
    estimate_zero_mean = estimate_array - np.mean(estimate_array)
    reference_energy = float(np.dot(reference_zero_mean, reference_zero_mean))
    if reference_energy <= FLOAT64_EPSILON:
        raise ValueError("SI-SDR is undefined for a silent reference")

    alpha = float(np.dot(estimate_zero_mean, reference_zero_mean) / reference_energy)
    target = alpha * reference_zero_mean
    error = estimate_zero_mean - target
    target_energy = float(np.dot(target, target))
    error_energy = float(np.dot(error, error))
    if error_energy <= FLOAT64_EPSILON * max(target_energy, 1.0):
        return SI_SDR_CAP_DB

    value = 10.0 * np.log10(
        (target_energy + FLOAT64_EPSILON) / (error_energy + FLOAT64_EPSILON)
    )
    value = float(min(value, SI_SDR_CAP_DB))
    if not np.isfinite(value):
        raise ValueError("SI-SDR result is nonfinite")
    return value


def run_si_sdr_sanity_checks(sample_rate_hz: int = 44_100) -> dict[str, float | bool]:
    """Check perfect-match finiteness and scale invariance without randomness."""
    time = np.arange(8192, dtype=np.float64) / float(sample_rate_hz)
    reference = np.sin(2.0 * np.pi * 440.0 * time)
    interference = np.sin(2.0 * np.pi * 997.0 * time + 0.37)
    imperfect_estimate = reference + 0.05 * interference

    identical_db = transparent_si_sdr_db(reference, reference)
    perfect_scaled_db = transparent_si_sdr_db(reference, 2.5 * reference)
    imperfect_db = transparent_si_sdr_db(reference, imperfect_estimate)
    imperfect_scaled_db = transparent_si_sdr_db(reference, 2.5 * imperfect_estimate)
    scale_difference_db = abs(imperfect_db - imperfect_scaled_db)

    passed = (
        identical_db == SI_SDR_CAP_DB
        and perfect_scaled_db == SI_SDR_CAP_DB
        and scale_difference_db <= 1e-10
    )
    if not passed:
        raise RuntimeError("SI-SDR perfect/scaled synthetic sanity check failed")
    return {
        "passed": True,
        "identical_si_sdr_db": identical_db,
        "perfect_scaled_si_sdr_db": perfect_scaled_db,
        "imperfect_si_sdr_db": imperfect_db,
        "imperfect_scaled_si_sdr_db": imperfect_scaled_db,
        "imperfect_scale_difference_db": scale_difference_db,
    }
