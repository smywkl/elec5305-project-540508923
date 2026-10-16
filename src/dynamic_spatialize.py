"""Early dynamic-renderer scaffold; see docs/architecture.md for project status."""

import numpy as np


def linear_trajectory(start_deg: float, end_deg: float, num_blocks: int) -> np.ndarray:
    """Create a simple azimuth trajectory."""
    if num_blocks < 1:
        raise ValueError("num_blocks must be >= 1")
    return np.linspace(start_deg, end_deg, num_blocks)


def spatialize_dynamic(source, trajectory_deg, hrtf_provider, block_size=4410, crossfade_size=882):
    """Placeholder for block rendering with smooth HRIR transitions and overlap-add."""
    raise NotImplementedError("Dynamic HRTF rendering will be implemented after static rendering.")
