"""Music source-separation scaffold.

Initial goal:
    stereo music -> vocals / drums / bass / other

The project is expected to use a pretrained Demucs-based model. This module
keeps model integration separate from the later signal-processing stages.
"""

from pathlib import Path


def separate_music(input_audio: str, output_dir: str, model_name: str = "htdemucs"):
    """Separate an input music file into stems.

    This is an initial project scaffold. The Demucs invocation, model-loading
    strategy, sample-rate handling and returned paths will be finalised after
    environment testing.

    Parameters
    ----------
    input_audio:
        Path to stereo input music.
    output_dir:
        Directory for separated stems.
    model_name:
        Planned pretrained Demucs model.

    Returns
    -------
    dict
        Planned mapping from stem name to generated audio path.
    """
    input_path = Path(input_audio)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        raise FileNotFoundError(input_path)

    # TODO:
    # 1. Load/run the pretrained Demucs model.
    # 2. Confirm input sample-rate and stereo handling.
    # 3. Save aligned stems.
    # 4. Return actual generated paths.
    planned = {
        "vocals": out / "vocals.wav",
        "drums": out / "drums.wav",
        "bass": out / "bass.wav",
        "other": out / "other.wav",
    }

    print(f"[Scaffold] Planned separation using model: {model_name}")
    print(f"[Scaffold] Input: {input_path}")
    return planned


if __name__ == "__main__":
    print("Source-separation module scaffold. Integration testing pending.")
