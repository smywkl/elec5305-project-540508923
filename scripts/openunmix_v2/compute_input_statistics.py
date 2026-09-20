"""Compute/cache official-style Open-Unmix input statistics for V2."""

import argparse
import json
from pathlib import Path

from pipeline import INPUT_STATISTICS_FILE, compute_input_statistics, load_and_validate_split


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=INPUT_STATISTICS_FILE)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    split = load_and_validate_split()
    result = compute_input_statistics(split, args.output.resolve(), force=args.force)
    summary = {
        "path": str(args.output.resolve()),
        "mean_bins": int(result["mean"].size),
        "std_bins": int(result["std"].size),
        "mean_min": float(result["mean"].min()),
        "mean_max": float(result["mean"].max()),
        "std_min": float(result["std"].min()),
        "std_max": float(result["std"].max()),
        "std_floor": float(result["std_floor"].item()),
        "computed_seconds": float(result["computed_seconds"].item()),
        **result["metadata"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
