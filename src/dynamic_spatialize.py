"""Dynamic binaural spatialisation scaffold.

This module is intended to become one of the main original implementation
components of the project.
"""

import numpy as np


def linear_trajectory(start_deg: float, end_deg: float, num_blocks: int) -> np.ndarray:
    """Create a simple azimuth trajectory."""
    if num_blocks < 1:
        raise ValueError("num_blocks must be >= 1")
    return np.linspace(start_deg, end_deg, num_blocks)


def spatialize_dynamic(source, trajectory_deg, hrtf_provider, block_size=4410, crossfade_size=882):
    """Planned block-based dynamic HRTF renderer.

    Future implementation:
    1. Divide a stem into overlapping/non-overlapping processing blocks.
    2. Obtain neighbouring HRIRs for each requested azimuth.
    3. Interpolate HRIRs or crossfade adjacent rendered blocks.
    4. Overlap/add blocks while preventing clicks and spatial jumps.
    5. Return a stereo binaural signal.

    `hrtf_provider` will later abstract the CIPIC dataset parser.
    """
    raise NotImplementedError("Dynamic HRTF rendering will be implemented after static rendering.")
