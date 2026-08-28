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
    """Load the nearest or interpolated HRIR pair for a requested direction.

    Planned responsibilities:
    - read the public HRTF/HRIR dataset;
    - map dataset coordinates to project coordinates;
    - select neighbouring measured positions;
    - return left/right HRIRs;
    - later support interpolation.

    The exact CIPIC file parser will be implemented after the dataset format
    is inspected.
    """
    raise NotImplementedError("CIPIC HRIR parser will be implemented in the next project stage.")
