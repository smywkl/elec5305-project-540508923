"""Shared data, model, validation, and checkpoint utilities for Open-Unmix V2."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import json
import math
import os
import random
import time
from pathlib import Path
from typing import Iterable

import numpy as np
import soundfile as sf
import torch
from torch.utils.data import Dataset
from openunmix import model, transforms, utils
from sklearn.preprocessing import StandardScaler


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MUSDB_ROOT = PROJECT_ROOT / "data" / "musdb18hq"
MUSDB_TRAIN = MUSDB_ROOT / "train"
SPLIT_FILE = PROJECT_ROOT / "outputs" / "training" / "openunmix" / "split.json"
V2_OUTPUT = PROJECT_ROOT / "outputs" / "training" / "openunmix_v2" / "vocals"
INPUT_STATISTICS_FILE = PROJECT_ROOT / "outputs" / "training" / "openunmix_v2" / "input_statistics.npz"
REFERENCE_SONG = "Swinging Steaks - Lost My Way"

SEED = 5305
SAMPLE_RATE = 44100
CHANNELS = 2
CHUNK_SECONDS = 6.0
CHUNK_FRAMES = int(SAMPLE_RATE * CHUNK_SECONDS)
SAMPLES_PER_TRACK = 64
TRAIN_TRACKS = 90
SAMPLES_PER_EPOCH_EQUIVALENT = TRAIN_TRACKS * SAMPLES_PER_TRACK
CHECKPOINT_SAMPLES = SAMPLES_PER_EPOCH_EQUIVALENT // 2
SOURCES = ("vocals", "drums", "bass", "other")
NFFT = 4096
NHOP = 1024
HIDDEN_SIZE = 512
BANDWIDTH = 16000
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-5


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def atomic_torch_save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(value, temporary)
    os.replace(temporary, path)


def split_sha256(split: dict) -> str:
    payload = json.dumps(split, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_and_validate_split() -> dict:
    split = read_json(SPLIT_FILE)
    if split.get("seed") != SEED:
        raise RuntimeError("The formal split seed is not 5305")
    if len(split.get("train", [])) != TRAIN_TRACKS or len(split.get("validation", [])) != 10:
        raise RuntimeError("The formal split is not 90 train / 10 validation")
    if set(split["train"]) & set(split["validation"]):
        raise RuntimeError("Train and validation split overlap")
    dataset_names = {path.name for path in MUSDB_TRAIN.iterdir() if path.is_dir()}
    if set(split["train"]) | set(split["validation"]) != dataset_names:
        raise RuntimeError("The formal split does not exactly partition MUSDB18-HQ train/")
    if split.get("official_test_used") is not False:
        raise RuntimeError("split.json does not explicitly exclude official test/")
    if REFERENCE_SONG not in split["validation"]:
        raise RuntimeError(f"Listening reference is not in validation: {REFERENCE_SONG}")
    return split


def _read_chunk(path: Path, start_frame: int, frames: int = CHUNK_FRAMES) -> torch.Tensor:
    with sf.SoundFile(path) as handle:
        if handle.samplerate != SAMPLE_RATE or handle.channels != CHANNELS:
            raise RuntimeError(f"Unexpected audio format: {path}")
        handle.seek(start_frame)
        audio = handle.read(frames, dtype="float32", always_2d=True)
    if audio.shape[0] < frames:
        audio = np.pad(audio, ((0, frames - audio.shape[0]), (0, 0)))
    return torch.from_numpy(audio.T.copy())


class AugmentedMusdbDataset(Dataset):
    """Balanced, deterministic implementation of official-style MUSDB augmentation.

    Each local epoch index maps to one of 64 target-vocal examples for each of
    the 90 tracks. Interfering sources come from independently selected tracks.
    Per-source gain and channel swapping mirror openunmix.data augmentations.
    """

    def __init__(self, split: dict, seed: int = SEED):
        self.tracks = list(split["train"])
        self.seed = int(seed)
        if len(self.tracks) != TRAIN_TRACKS:
            raise RuntimeError(f"Expected {TRAIN_TRACKS} training tracks")
        self.frames = {
            track: {
                source: sf.info(MUSDB_TRAIN / track / f"{source}.wav").frames
                for source in SOURCES
            }
            for track in self.tracks
        }

    def __len__(self) -> int:
        return SAMPLES_PER_EPOCH_EQUIVALENT

    def __getitem__(self, encoded_index):
        epoch_index, local_index = encoded_index
        target_track_index = int(local_index) // SAMPLES_PER_TRACK
        target_track = self.tracks[target_track_index]
        sample_seed = self.seed * 10**12 + int(epoch_index) * 10**6 + int(local_index)
        rng = np.random.default_rng(sample_seed)
        augmented_sources = []
        selected_tracks = []
        starts = []
        gains = []
        swaps = []

        for source in SOURCES:
            track = target_track if source == "vocals" else self.tracks[int(rng.integers(len(self.tracks)))]
            available = self.frames[track][source]
            start = int(rng.integers(0, max(1, available - CHUNK_FRAMES + 1)))
            audio = _read_chunk(MUSDB_TRAIN / track / f"{source}.wav", start)
            # Matches official _augment_gain: one independent scalar per source.
            gain = float(rng.uniform(0.25, 1.25))
            audio = audio * gain
            # Matches official _augment_channelswap: p=0.5 per source.
            swap = bool(rng.random() < 0.5)
            if swap:
                audio = torch.flip(audio, dims=(0,))
            augmented_sources.append(audio)
            selected_tracks.append(track)
            starts.append(start)
            gains.append(gain)
            swaps.append(swap)

        stems = torch.stack(augmented_sources)
        mixture = stems.sum(dim=0)
        target = stems[0]
        metadata = {
            "worker_pid": os.getpid(),
            "local_index": int(local_index),
            "target_track_index": target_track_index,
            "selected_tracks": selected_tracks,
            "start_frames": starts,
            "gains": gains,
            "channel_swaps": swaps,
        }
        return mixture, target, metadata


class FixedValidationDataset(Dataset):
    def __init__(self, split: dict):
        segments = split.get("validation_segments")
        if not segments or len(segments) != 10:
            raise RuntimeError("split.json is missing the 10 fixed validation segments")
        self.segments = segments

    def __len__(self) -> int:
        return len(self.segments)

    def __getitem__(self, index: int):
        item = self.segments[index]
        track = item["song"]
        start = int(item["start_frame"])
        sources = torch.stack([
            _read_chunk(MUSDB_TRAIN / track / f"{source}.wav", start)
            for source in SOURCES
        ])
        return sources.sum(dim=0), sources[0], track


def epoch_indices(epoch_index: int, sample_offset: int = 0) -> list[tuple[int, int]]:
    generator = torch.Generator().manual_seed(SEED + int(epoch_index))
    permutation = torch.randperm(SAMPLES_PER_EPOCH_EQUIVALENT, generator=generator).tolist()
    return [(int(epoch_index), local) for local in permutation[int(sample_offset):]]


def dataloader_worker_init(_worker_id: int) -> None:
    torch.set_num_threads(1)


def build_model(input_mean: np.ndarray, input_scale: np.ndarray) -> model.OpenUnmix:
    """Build a from-scratch model using official Open-Unmix scaler semantics.

    OpenUnmix stores ``-input_mean`` and ``1/input_scale`` internally, so the
    caller must pass the unmodified global magnitude mean and clipped std.
    """
    if input_mean is None or input_scale is None:
        raise ValueError("V2 from-scratch models require cached input mean/std")
    return model.OpenUnmix(
        input_mean=input_mean,
        input_scale=input_scale,
        nb_bins=NFFT // 2 + 1,
        nb_channels=CHANNELS,
        hidden_size=HIDDEN_SIZE,
        max_bin=utils.bandwidth_to_max_bin(SAMPLE_RATE, NFFT, BANDWIDTH),
        unidirectional=False,
    )


def build_encoder() -> torch.nn.Module:
    stft, _ = transforms.make_filterbanks(n_fft=NFFT, n_hop=NHOP, sample_rate=SAMPLE_RATE)
    return torch.nn.Sequential(stft, model.ComplexNorm(mono=False))


def load_pretrained_umxhq_vocals_model() -> model.OpenUnmix:
    """Load the complete pretrained model, including its own input statistics."""
    return utils.load_target_models(
        ["vocals"], model_str_or_path="umxhq", device="cpu", pretrained=True
    )["vocals"]


def compute_input_statistics(split: dict, output_path: Path = INPUT_STATISTICS_FILE, force: bool = False) -> dict:
    """Compute official-style frequency-bin mean/std from training mixtures only."""
    if output_path.exists() and not force:
        return load_input_statistics(split, output_path)
    started = time.perf_counter()
    encoder = build_encoder().to("cpu")
    encoder.eval()
    scaler = StandardScaler()
    tracks = list(split["train"])
    if len(tracks) != TRAIN_TRACKS:
        raise RuntimeError(f"Expected {TRAIN_TRACKS} statistics tracks")
    total_frames = 0
    with torch.inference_mode():
        for index, track in enumerate(tracks, 1):
            path = MUSDB_TRAIN / track / "mixture.wav"
            mixture, rate = sf.read(path, dtype="float32", always_2d=True)
            if rate != SAMPLE_RATE or mixture.shape[1] != CHANNELS:
                raise RuntimeError(f"Unexpected statistics audio format: {path}")
            waveform = torch.from_numpy(mixture.T.copy()).unsqueeze(0)
            # Official get_statistics(): mono downmix after magnitude STFT,
            # then present time frames as observations and bins as features.
            magnitude = encoder(waveform).mean(1, keepdim=False).permute(0, 2, 1)
            observations = np.squeeze(magnitude.cpu().numpy())
            scaler.partial_fit(observations)
            total_frames += int(observations.shape[0])
            del mixture, waveform, magnitude, observations
            if index == 1 or index % 10 == 0 or index == len(tracks):
                print(f"STATISTICS {index}/{len(tracks)}", flush=True)
    mean = scaler.mean_
    raw_std = scaler.scale_
    std_floor = 1e-4 * float(np.max(raw_std))
    std = np.maximum(raw_std, std_floor)
    elapsed = time.perf_counter() - started
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.savez(
            handle,
            mean=mean,
            std=std,
            split_sha256=np.asarray(split_sha256(split)),
            n_fft=np.asarray(NFFT, dtype=np.int64),
            n_hop=np.asarray(NHOP, dtype=np.int64),
            sample_rate=np.asarray(SAMPLE_RATE, dtype=np.int64),
            number_of_training_tracks=np.asarray(len(tracks), dtype=np.int64),
            total_spectrogram_frames=np.asarray(total_frames, dtype=np.int64),
            std_floor=np.asarray(std_floor, dtype=np.float64),
            computed_seconds=np.asarray(elapsed, dtype=np.float64),
            method=np.asarray("official_get_statistics_equivalent_train_mixture_only"),
        )
    os.replace(temporary, output_path)
    return load_input_statistics(split, output_path)


def load_input_statistics(split: dict, path: Path = INPUT_STATISTICS_FILE) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"Input statistics cache not found: {path}. Run compute_input_statistics.py first."
        )
    with np.load(path, allow_pickle=False) as cache:
        result = {name: cache[name].copy() for name in cache.files}
    expected = {
        "split_sha256": split_sha256(split),
        "n_fft": NFFT,
        "n_hop": NHOP,
        "sample_rate": SAMPLE_RATE,
        "number_of_training_tracks": TRAIN_TRACKS,
    }
    actual = {
        "split_sha256": str(result["split_sha256"].item()),
        "n_fft": int(result["n_fft"].item()),
        "n_hop": int(result["n_hop"].item()),
        "sample_rate": int(result["sample_rate"].item()),
        "number_of_training_tracks": int(result["number_of_training_tracks"].item()),
    }
    if actual != expected:
        raise RuntimeError(f"Input statistics cache metadata mismatch: {actual} != {expected}")
    mean = np.asarray(result["mean"], dtype=np.float64)
    std = np.asarray(result["std"], dtype=np.float64)
    if mean.shape != (NFFT // 2 + 1,) or std.shape != mean.shape:
        raise RuntimeError(f"Unexpected input statistics shapes: {mean.shape}, {std.shape}")
    if not np.isfinite(mean).all() or not np.isfinite(std).all() or not np.all(std > 0):
        raise RuntimeError("Input statistics contain invalid values")
    result["mean"] = mean
    result["std"] = std
    result["metadata"] = actual
    return result


def magnitude_mse(network: torch.nn.Module, encoder: torch.nn.Module, mixture, target):
    estimate = network(encoder(mixture))
    expected = encoder(target)
    return torch.nn.functional.mse_loss(estimate, expected)


def deterministic_validation_loss(network, encoder, split: dict) -> tuple[float, list[dict]]:
    dataset = FixedValidationDataset(split)
    was_training = network.training
    network.eval()
    details = []
    with torch.inference_mode():
        for mixture, target, track in dataset:
            value = float(magnitude_mse(network, encoder, mixture[None], target[None]).item())
            details.append({"song": track, "loss": value})
    if was_training:
        network.train()
    return float(np.mean([item["loss"] for item in details])), details


def load_reference_audio() -> tuple[torch.Tensor, torch.Tensor]:
    mixture, mixture_rate = sf.read(
        MUSDB_TRAIN / REFERENCE_SONG / "mixture.wav", dtype="float32", always_2d=True
    )
    vocals, vocals_rate = sf.read(
        MUSDB_TRAIN / REFERENCE_SONG / "vocals.wav", dtype="float32", always_2d=True
    )
    if mixture_rate != SAMPLE_RATE or vocals_rate != SAMPLE_RATE or mixture.shape != vocals.shape:
        raise RuntimeError("Reference mixture/vocals format mismatch")
    return torch.from_numpy(mixture.T.copy()), torch.from_numpy(vocals.T.copy())


def load_hybrid_interferer_models() -> dict[str, torch.nn.Module]:
    return utils.load_target_models(
        ["drums", "bass", "other"],
        model_str_or_path="umxhq",
        device="cpu",
        pretrained=True,
    )


def hybrid_vocals_overlap_add(
    custom_vocals: torch.nn.Module,
    pretrained_interferers: dict[str, torch.nn.Module],
    mixture: torch.Tensor,
    overlap: float = 0.5,
) -> torch.Tensor:
    was_training = custom_vocals.training
    targets = {
        "vocals": custom_vocals,
        "drums": pretrained_interferers["drums"],
        "bass": pretrained_interferers["bass"],
        "other": pretrained_interferers["other"],
    }
    separator = model.Separator(
        targets,
        niter=1,
        softmask=False,
        residual=False,
        sample_rate=SAMPLE_RATE,
        n_fft=NFFT,
        n_hop=NHOP,
        nb_channels=CHANNELS,
        wiener_win_len=300,
        filterbank="torch",
    )
    separator.eval()
    chunk_frames = CHUNK_FRAMES
    hop_frames = int(chunk_frames * (1.0 - overlap))
    pad_frames = chunk_frames // 2
    padded = torch.nn.functional.pad(mixture, (pad_frames, pad_frames))
    starts = list(range(0, max(1, padded.shape[-1] - chunk_frames + 1), hop_frames))
    final_start = padded.shape[-1] - chunk_frames
    if not starts or starts[-1] != final_start:
        starts.append(final_start)
    window = torch.hann_window(chunk_frames, periodic=False, dtype=mixture.dtype)
    output = torch.zeros_like(padded)
    weight = torch.zeros(padded.shape[-1], dtype=mixture.dtype)
    with torch.inference_mode():
        for start in starts:
            estimates = separator(padded[:, start:start + chunk_frames].unsqueeze(0))
            output[:, start:start + chunk_frames] += estimates[0, 0] * window
            weight[start:start + chunk_frames] += window
    result = output / weight.clamp_min(1e-8).unsqueeze(0)
    if was_training:
        custom_vocals.train()
    return result[:, pad_frames:pad_frames + mixture.shape[-1]].contiguous()


def si_sdr_db(estimate: torch.Tensor, reference: torch.Tensor, epsilon: float = 1e-8) -> float:
    if estimate.shape != reference.shape:
        raise ValueError("SI-SDR inputs must have identical shapes")
    estimate = estimate.double() - estimate.double().mean(dim=-1, keepdim=True)
    reference = reference.double() - reference.double().mean(dim=-1, keepdim=True)
    scale = (estimate * reference).sum(dim=-1, keepdim=True) / (
        reference.square().sum(dim=-1, keepdim=True) + epsilon
    )
    target = scale * reference
    noise = estimate - target
    scores = 10.0 * torch.log10(
        (target.square().sum(dim=-1) + epsilon) /
        (noise.square().sum(dim=-1) + epsilon)
    )
    return float(scores.mean().item())


def save_float_wav(path: Path, audio: torch.Tensor) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, audio.detach().cpu().T.numpy(), SAMPLE_RATE, subtype="FLOAT")


def training_configuration(batch_size: int, workers: int, init_mode: str = "random") -> dict:
    return {
        "run": "Open-Unmix V2 augmented vocals",
        "target": "vocals",
        "initialization": init_mode,
        "device": "cpu",
        "sample_rate": SAMPLE_RATE,
        "channels": CHANNELS,
        "chunk_seconds": CHUNK_SECONDS,
        "n_fft": NFFT,
        "n_hop": NHOP,
        "hidden_size": HIDDEN_SIZE,
        "bandwidth_hz": BANDWIDTH,
        "batch_size": int(batch_size),
        "dataloader_workers": int(workers),
        "optimizer": "Adam",
        "learning_rate": LEARNING_RATE if init_mode == "random" else None,
        "weight_decay": WEIGHT_DECAY,
        "objective": "magnitude-domain MSE",
        "seed": SEED,
        "train_tracks": TRAIN_TRACKS,
        "samples_per_track_per_epoch_equivalent": SAMPLES_PER_TRACK,
        "samples_per_epoch_equivalent": SAMPLES_PER_EPOCH_EQUIVALENT,
        "checkpoint_samples": CHECKPOINT_SAMPLES,
        "augmentation": {
            "balanced_target_track_sampling": True,
            "random_6_second_chunks": True,
            "per_source_gain_range": [0.25, 1.25],
            "per_source_channel_swap_probability": 0.5,
            "random_track_mixing": "vocals fixed to balanced target track; drums/bass/other independently sampled",
        },
        "validation": {
            "fixed_segments": 10,
            "every_epoch_equivalent": 1.0,
            "reference_song": REFERENCE_SONG,
            "hybrid_targets": "custom vocals + pretrained UMXHQ drums/bass/other",
            "metric": "mean stereo-channel SI-SDR in dB",
        },
        "official_test_used": False,
    }


class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


def process_memory(pid: int) -> tuple[float, float] | None:
    access = 0x0400 | 0x0010
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    handle = kernel32.OpenProcess(access, False, int(pid))
    if not handle:
        return None
    try:
        counters = PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = ctypes.sizeof(counters)
        fn = kernel32.K32GetProcessMemoryInfo
        fn.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        fn.restype = wintypes.BOOL
        if not fn(handle, ctypes.byref(counters), counters.cb):
            return None
        gib = 1024 ** 3
        return counters.WorkingSetSize / gib, counters.PeakWorkingSetSize / gib
    finally:
        kernel32.CloseHandle(handle)


def process_cpu_seconds(pid: int) -> float | None:
    access = 0x0400
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    handle = kernel32.OpenProcess(access, False, int(pid))
    if not handle:
        return None
    try:
        creation = wintypes.FILETIME()
        exit_time = wintypes.FILETIME()
        kernel = wintypes.FILETIME()
        user = wintypes.FILETIME()
        if not kernel32.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exit_time), ctypes.byref(kernel), ctypes.byref(user)):
            return None
        def value(item):
            return (item.dwHighDateTime << 32) + item.dwLowDateTime
        return (value(kernel) + value(user)) / 10_000_000.0
    finally:
        kernel32.CloseHandle(handle)
