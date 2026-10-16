"""HRTF/HRIR data handling scaffold."""

from dataclasses import dataclass
import numpy as np


@dataclass
class HRIRPair:
    left: np.ndarray
    right: np.ndarray
    azimuth_deg: float
    elevation_deg: float = 0.0


def load_hrir_pair(dataset_path: str, azimuth_deg: float, elevation_deg: float = 0.0) -> HRIRPair:
    """Placeholder for HRIR loading; the validated CIPIC loader is in src/matlab/."""
    raise NotImplementedError("CIPIC HRIR parser will be implemented in the next project stage.")
