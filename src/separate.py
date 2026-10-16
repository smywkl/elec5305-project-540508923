"""Early separation scaffold; the frozen evaluator is in scripts/evaluation/."""

from pathlib import Path


def separate_music(input_audio: str, output_dir: str, model_name: str = "htdemucs"):
    """Return planned stem paths without running separation.

    Model loading, inference, and aligned WAV export are not implemented here.
    """
    input_path = Path(input_audio)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        raise FileNotFoundError(input_path)

    # TODO: Run Demucs and save aligned stems; these paths are placeholders.
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
