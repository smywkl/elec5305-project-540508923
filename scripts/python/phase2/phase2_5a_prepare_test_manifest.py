"""Phase 2.5a official-test manifest selection and metadata-only preflight.

The ordering of operations is deliberate: tracked Git cleanliness and the
frozen protocol hash are verified before the official-test directory is ever
enumerated. Audio access is limited to RIFF/WAVE headers; no sample frame is
decoded or read, and no inference, metric, spectrogram, or listening output is
produced.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import unicodedata


REPO_ROOT = Path(__file__).resolve().parents[3]
PROTOCOL_PATH = REPO_ROOT / "config" / "phase2" / "static_experiment_protocol.json"
TEST_ROOT = REPO_ROOT / "data" / "musdb18hq" / "test"
MANIFEST_PATH = REPO_ROOT / "config" / "phase2" / "final_test_manifest.json"
OUTPUT_ROOT = REPO_ROOT / "outputs" / "phase2" / "phase2_5a_preflight"
ALL_HASHES_PATH = OUTPUT_ROOT / "all_test_track_hashes.csv"
PREFLIGHT_CSV_PATH = OUTPUT_ROOT / "selected_tracks_preflight.csv"
SUMMARY_PATH = OUTPUT_ROOT / "preflight_summary.json"
DOCUMENT_PATH = REPO_ROOT / "docs" / "phase2" / "phase2_5a_final_test_preflight.md"

EXPECTED_PROTOCOL_VERSION = "1.0"
EXPECTED_PROTOCOL_SHA256 = "54a27252bcba432f5fd1b62b108cdd28bb059201a5c482e604c687c703f3d9f0"
SELECTION_SALT = "ELEC5305_PHASE2_TEST_5305|"
NORMALIZATION = "Unicode NFC"
HASH_ALGORITHM = "SHA-256"
SORT_ORDER = "selection_sha256 ascending; track_name_nfc ascending as collision tie-break"
SELECTED_TRACK_COUNT = 10
REQUIRED_FILES = ("mixture.wav", "vocals.wav", "drums.wav", "bass.wav", "other.wav")
SOURCE_ORDER = ("bass", "vocals", "drums", "other")
SAMPLE_RATE_HZ = 44_100
EXCERPT_START_S = 30
EXCERPT_END_S = 60
SEPARATION_EXECUTION_RULE = "full_track_htdemucs_ft_then_extract_30_60s"
PHASE1_MEAN_RTF = 3.535904
FLOAT32_BYTES = 4
STEREO_CHANNELS = 2


def run_git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json_atomic(path: Path, value: object) -> None:
    write_text_atomic(
        path, json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    )


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def write_csv_atomic(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def verify_pre_access_gates() -> tuple[str, str, str, dict]:
    """Verify Git and protocol gates without touching the official test root."""
    branch = run_git("branch", "--show-current")
    head = run_git("rev-parse", "HEAD")
    tracked_status = run_git("status", "--porcelain=v1", "--untracked-files=no")
    require(not tracked_status, f"tracked working tree is not clean:\n{tracked_status}")

    protocol_sha256 = sha256_file(PROTOCOL_PATH)
    require(
        protocol_sha256 == EXPECTED_PROTOCOL_SHA256,
        "frozen protocol SHA-256 mismatch: "
        f"expected {EXPECTED_PROTOCOL_SHA256}, got {protocol_sha256}",
    )
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    verify_frozen_protocol(protocol)
    return branch, head, protocol_sha256, protocol


def verify_frozen_protocol(protocol: dict) -> None:
    require(protocol.get("protocol_version") == EXPECTED_PROTOCOL_VERSION, "protocol version mismatch")
    require(protocol.get("frozen_before_official_test") is True, "protocol is not frozen")
    require(protocol["dataset"]["number_of_tracks"] == SELECTED_TRACK_COUNT, "selected count mismatch")
    require(protocol["track_selection"]["normalization"].startswith("Unicode NFC"), "normalization mismatch")
    require(protocol["track_selection"]["salt"] == SELECTION_SALT, "selection salt mismatch")
    require(protocol["excerpt"]["start_seconds"] == EXCERPT_START_S, "excerpt start mismatch")
    require(protocol["excerpt"]["end_seconds"] == EXCERPT_END_S, "excerpt end mismatch")
    require(protocol["excerpt"]["sample_rate_hz"] == SAMPLE_RATE_HZ, "sample rate mismatch")
    require(tuple(protocol["source_representation"]["canonical_source_order"]) == SOURCE_ORDER, "source order mismatch")
    require(
        [item["azimuths_deg"] for item in protocol["spatial_conditions"]]
        == [[0, 0, 0, 0], [-30, -10, 10, 30], [-80, -30, 30, 80]],
        "spatial conditions mismatch",
    )

    sir = protocol["source_metrics"]["sir"]
    require(sir["package"] == "museval" and sir["version"] == "0.4.1", "SIR package mismatch")
    require(sir["parameters"] == {
        "window": "infinity",
        "hop": "infinity",
        "compute_permutation": False,
        "filters_len": 512,
        "framewise_filters": False,
        "bsseval_sources_version": False,
    }, "SIR parameters mismatch")
    require(tuple(sir["source_order"]) == SOURCE_ORDER, "SIR source order mismatch")

    downstream_names = [item["name"] for item in protocol["downstream_metrics"]["metrics"]]
    require(
        downstream_names == [
            "binaural SI-SDR",
            "relative waveform RMSE",
            "STFT log-magnitude MAE",
        ],
        "downstream metric plan mismatch",
    )
    stft = protocol["stft"]
    require(
        stft["window_type"] == "periodic Hann"
        and stft["window_length_samples"] == 1024
        and stft["hop_size_samples"] == 256
        and stft["overlap_samples"] == 768
        and stft["fft_size"] == 1024
        and stft["magnitude_epsilon"] == "MATLAB double eps (2.220446049250313e-16)"
        and stft["scientific_metric_db_floor"] is None,
        "STFT plan mismatch",
    )
    analysis = protocol["analysis_plan"]
    require(analysis["observation_unit"] == "one song" and analysis["final_n"] == 10, "RQ observation unit mismatch")
    require(analysis["rq1"]["design"].startswith("Each song is one paired unit"), "RQ1 plan mismatch")
    require(analysis["rq2"]["association"] == "Spearman rank correlation", "RQ2 association mismatch")
    require(analysis["rq2"]["primary_conditions"] == ["moderate", "wide"], "RQ2 conditions mismatch")


def enumerate_and_rank_tracks() -> list[dict[str, object]]:
    require(TEST_ROOT.is_dir(), f"official test root is missing: {TEST_ROOT}")
    original_names = [item.name for item in TEST_ROOT.iterdir() if item.is_dir()]
    require(original_names, "official test root contains no track directories")

    normalized_to_original: dict[str, str] = {}
    ranked: list[dict[str, object]] = []
    for original_name in original_names:
        normalized_name = unicodedata.normalize("NFC", original_name)
        previous = normalized_to_original.get(normalized_name)
        require(
            previous is None,
            "Unicode NFC normalization produced a duplicate: "
            f"{previous!r} and {original_name!r}",
        )
        normalized_to_original[normalized_name] = original_name
        digest = hashlib.sha256(
            (SELECTION_SALT + normalized_name).encode("utf-8")
        ).hexdigest()
        ranked.append(
            {
                "track_name_original": original_name,
                "track_name_nfc": normalized_name,
                "selection_sha256": digest,
            }
        )

    ranked.sort(key=lambda item: (str(item["selection_sha256"]), str(item["track_name_nfc"])))
    for index, item in enumerate(ranked, start=1):
        item["rank"] = index
        item["selected"] = index <= SELECTED_TRACK_COUNT
    require(len(ranked) >= SELECTED_TRACK_COUNT, "fewer than 10 official-test tracks")
    return ranked


def wave_subtype(format_tag: int, bits_per_sample: int, fmt_payload: bytes) -> tuple[str, int]:
    effective_tag = format_tag
    valid_bits = bits_per_sample
    if format_tag == 0xFFFE:
        require(len(fmt_payload) >= 40, "truncated WAVE_FORMAT_EXTENSIBLE fmt chunk")
        valid_bits = struct.unpack_from("<H", fmt_payload, 18)[0]
        effective_tag = struct.unpack_from("<H", fmt_payload, 24)[0]
    if effective_tag == 1:
        return f"PCM_{valid_bits}", valid_bits
    if effective_tag == 3:
        return ("FLOAT" if bits_per_sample == 32 else f"FLOAT_{bits_per_sample}"), valid_bits
    return f"WAVE_FORMAT_{effective_tag}_BITS_{bits_per_sample}", valid_bits


def read_wave_header(path: Path) -> dict[str, object]:
    """Read container metadata without reading or decoding the data payload."""
    file_size = path.stat().st_size
    with path.open("rb") as handle:
        riff_header = handle.read(12)
        require(len(riff_header) == 12, f"truncated RIFF header: {path}")
        riff_id, _riff_size, wave_id = struct.unpack("<4sI4s", riff_header)
        require(riff_id == b"RIFF" and wave_id == b"WAVE", f"unsupported WAV container: {path}")

        fmt_payload: bytes | None = None
        data_size: int | None = None
        while handle.tell() + 8 <= file_size:
            chunk_header = handle.read(8)
            require(len(chunk_header) == 8, f"truncated chunk header: {path}")
            chunk_id, chunk_size = struct.unpack("<4sI", chunk_header)
            payload_offset = handle.tell()
            require(payload_offset + chunk_size <= file_size + 1, f"invalid chunk size: {path}")
            if chunk_id == b"fmt ":
                fmt_payload = handle.read(chunk_size)
                require(len(fmt_payload) == chunk_size, f"truncated fmt chunk: {path}")
            elif chunk_id == b"data":
                data_size = chunk_size
                if fmt_payload is not None:
                    break
                handle.seek(chunk_size, os.SEEK_CUR)
            else:
                handle.seek(chunk_size, os.SEEK_CUR)
            if chunk_size % 2:
                handle.seek(1, os.SEEK_CUR)

    require(fmt_payload is not None and len(fmt_payload) >= 16, f"missing fmt chunk: {path}")
    require(data_size is not None, f"missing data chunk: {path}")
    format_tag, channels, sample_rate, byte_rate, block_align, bits_per_sample = struct.unpack_from(
        "<HHIIHH", fmt_payload, 0
    )
    require(channels > 0 and sample_rate > 0 and block_align > 0, f"invalid WAV format: {path}")
    require(data_size % block_align == 0, f"data size is not frame-aligned: {path}")
    frames = data_size // block_align
    subtype, valid_bits = wave_subtype(format_tag, bits_per_sample, fmt_payload)
    require(byte_rate == sample_rate * block_align, f"inconsistent WAV byte rate: {path}")
    return {
        "sample_rate_hz": sample_rate,
        "channels": channels,
        "frame_count": frames,
        "duration_s": frames / sample_rate,
        "subtype": subtype,
        "bits_per_sample": bits_per_sample,
        "valid_bits_per_sample": valid_bits,
        "file_size_bytes": file_size,
        "block_align_bytes": block_align,
    }


def preflight_selected_tracks(selected: list[dict[str, object]]) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for selection in selected:
        track_name = str(selection["track_name_original"])
        track_dir = TEST_ROOT / track_name
        files: dict[str, dict[str, object]] = {}
        missing_files: list[str] = []
        for filename in REQUIRED_FILES:
            path = track_dir / filename
            if not path.is_file():
                missing_files.append(filename)
                continue
            files[filename.removesuffix(".wav")] = read_wave_header(path)

        all_required_files_exist = not missing_files
        sample_rates = {int(item["sample_rate_hz"]) for item in files.values()}
        channel_counts = {int(item["channels"]) for item in files.values()}
        frame_counts = {int(item["frame_count"]) for item in files.values()}
        durations = [float(item["duration_s"]) for item in files.values()]
        all_sample_rates_44100 = all_required_files_exist and sample_rates == {SAMPLE_RATE_HZ}
        all_stereo = all_required_files_exist and channel_counts == {STEREO_CHANNELS}
        all_at_least_60s = all_required_files_exist and min(durations) >= EXCERPT_END_S
        frame_counts_compatible = all_required_files_exist and len(frame_counts) == 1
        preflight_pass = (
            all_required_files_exist
            and all_sample_rates_44100
            and all_stereo
            and all_at_least_60s
            and frame_counts_compatible
        )
        results.append(
            {
                **selection,
                "dataset_relative_path": (Path("data") / "musdb18hq" / "test" / track_name).as_posix(),
                "files": files,
                "missing_files": missing_files,
                "all_required_files_exist": all_required_files_exist,
                "all_sample_rates_44100": all_sample_rates_44100,
                "all_stereo": all_stereo,
                "all_at_least_60s": all_at_least_60s,
                "frame_counts_compatible": frame_counts_compatible,
                "minimum_duration_s": min(durations) if durations else None,
                "preflight_pass": preflight_pass,
            }
        )
    return results


def make_manifest(
    head: str,
    protocol_sha256: str,
    ranked: list[dict[str, object]],
    selected_results: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "manifest_version": "1.0",
        "protocol_version": EXPECTED_PROTOCOL_VERSION,
        "protocol_sha256": protocol_sha256,
        "git_head_before_test_access": head,
        "selection_seed_string": SELECTION_SALT,
        "unicode_normalization": NORMALIZATION,
        "hash_algorithm": HASH_ALGORITHM,
        "sort_order": SORT_ORDER,
        "total_test_tracks": len(ranked),
        "selected_track_count": len(selected_results),
        "selected_tracks": [
            {
                "rank": item["rank"],
                "track_name_original": item["track_name_original"],
                "track_name_nfc": item["track_name_nfc"],
                "selection_sha256": item["selection_sha256"],
                "dataset_relative_path": item["dataset_relative_path"],
            }
            for item in selected_results
        ],
        "source_order": list(SOURCE_ORDER),
        "excerpt_start_s": EXCERPT_START_S,
        "excerpt_end_s": EXCERPT_END_S,
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "separation_execution_rule": SEPARATION_EXECUTION_RULE,
        "official_test_audio_content_accessed": False,
        "official_test_inference_run": False,
        "official_test_metrics_computed": False,
        "official_test_listening_performed": False,
        "official_test_manifest_generated": True,
    }


def all_hash_rows(ranked: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "track_name": item["track_name_original"],
            "normalized_name": item["track_name_nfc"],
            "sha256": item["selection_sha256"],
            "rank": item["rank"],
            "selected": str(bool(item["selected"])).lower(),
        }
        for item in ranked
    ]


def preflight_csv_rows(results: list[dict[str, object]]) -> tuple[list[str], list[dict[str, object]]]:
    fieldnames = [
        "rank", "track_name", "selection_sha256", "mixture_frames", "duration_s",
        "sample_rate_hz", "channels", "vocals_exists", "drums_exists", "bass_exists",
        "other_exists", "minimum_stem_duration_s", "all_required_files_exist",
        "all_sample_rates_44100", "all_stereo", "frame_counts_compatible", "preflight_pass",
    ]
    fieldnames.extend(
        ["mixture_subtype", "mixture_bits_per_sample", "mixture_file_size_bytes"]
    )
    for basename in ("vocals", "drums", "bass", "other"):
        fieldnames.extend(
            [
                f"{basename}_frames", f"{basename}_duration_s", f"{basename}_sample_rate_hz",
                f"{basename}_channels", f"{basename}_subtype", f"{basename}_bits_per_sample",
                f"{basename}_file_size_bytes",
            ]
        )

    rows: list[dict[str, object]] = []
    for item in results:
        files = item["files"]
        mixture = files.get("mixture", {})
        stem_durations = [
            float(files[stem]["duration_s"])
            for stem in SOURCE_ORDER
            if stem in files
        ]
        row: dict[str, object] = {
            "rank": item["rank"],
            "track_name": item["track_name_original"],
            "selection_sha256": item["selection_sha256"],
            "mixture_frames": mixture.get("frame_count", ""),
            "duration_s": format_float(mixture.get("duration_s")),
            "sample_rate_hz": mixture.get("sample_rate_hz", ""),
            "channels": mixture.get("channels", ""),
            "vocals_exists": bool_string("vocals" in files),
            "drums_exists": bool_string("drums" in files),
            "bass_exists": bool_string("bass" in files),
            "other_exists": bool_string("other" in files),
            "minimum_stem_duration_s": format_float(min(stem_durations) if stem_durations else None),
            "all_required_files_exist": bool_string(item["all_required_files_exist"]),
            "all_sample_rates_44100": bool_string(item["all_sample_rates_44100"]),
            "all_stereo": bool_string(item["all_stereo"]),
            "frame_counts_compatible": bool_string(item["frame_counts_compatible"]),
            "preflight_pass": bool_string(item["preflight_pass"]),
        }
        for basename in ("mixture", "vocals", "drums", "bass", "other"):
            metadata = files.get(basename, {})
            if basename != "mixture":
                row.update(
                    {
                        f"{basename}_frames": metadata.get("frame_count", ""),
                        f"{basename}_duration_s": format_float(metadata.get("duration_s")),
                        f"{basename}_sample_rate_hz": metadata.get("sample_rate_hz", ""),
                        f"{basename}_channels": metadata.get("channels", ""),
                    }
                )
            row.update(
                {
                    f"{basename}_subtype": metadata.get("subtype", ""),
                    f"{basename}_bits_per_sample": metadata.get("bits_per_sample", ""),
                    f"{basename}_file_size_bytes": metadata.get("file_size_bytes", ""),
                }
            )
        rows.append(row)
    return fieldnames, rows


def bool_string(value: object) -> str:
    return str(bool(value)).lower()


def format_float(value: object) -> str:
    return "" if value is None else f"{float(value):.9f}"


def make_summary(
    branch: str,
    head: str,
    protocol_sha256: str,
    ranked: list[dict[str, object]],
    results: list[dict[str, object]],
) -> dict[str, object]:
    all_pass = all(bool(item["preflight_pass"]) for item in results)
    mixture_frames = sum(int(item["files"]["mixture"]["frame_count"]) for item in results if "mixture" in item["files"])
    total_duration_s = sum(float(item["files"]["mixture"]["duration_s"]) for item in results if "mixture" in item["files"])
    estimated_runtime_s = total_duration_s * PHASE1_MEAN_RTF
    cache_bytes = mixture_frames * len(SOURCE_ORDER) * STEREO_CHANNELS * FLOAT32_BYTES
    blockers = [] if all_pass else [
        f"rank {item['rank']} {item['track_name_original']}: metadata eligibility gate failed"
        for item in results
        if not item["preflight_pass"]
    ]
    return {
        "phase": "2.5a",
        "status": "READY FOR PHASE 2.5b FINAL BATCH" if all_pass else "NOT READY",
        "blockers": blockers,
        "pre_test_git": {
            "branch": branch,
            "head": head,
            "tracked_working_tree_clean": True,
        },
        "protocol": {
            "version": EXPECTED_PROTOCOL_VERSION,
            "sha256_expected": EXPECTED_PROTOCOL_SHA256,
            "sha256_actual": protocol_sha256,
            "sha256_match": True,
            "frozen_protocol_modified": False,
        },
        "selection": {
            "algorithm_executed_exactly": True,
            "total_test_tracks": len(ranked),
            "selected_track_count": len(results),
            "all_selected_tracks_pass": all_pass,
        },
        "selected_track_preflight": results,
        "runtime_estimate": {
            "total_selected_audio_duration_seconds": total_duration_s,
            "total_selected_audio_duration_hms": seconds_to_hms(total_duration_s),
            "phase1_mean_rtf": PHASE1_MEAN_RTF,
            "estimated_separation_runtime_seconds": estimated_runtime_s,
            "estimated_separation_runtime_hms": seconds_to_hms(estimated_runtime_s),
            "qualification": "rough estimate based on the Phase 1 mean CPU RTF; not a guaranteed runtime",
            "matlab_downstream_note": "30-second MATLAB HRTF rendering and downstream metrics are not expected to be the main runtime bottleneck relative to HTDemucs-FT CPU inference.",
        },
        "disk_estimate": {
            "plan": "10 selected tracks x 4 full-track estimated stereo float32 WAV stems",
            "theoretical_audio_payload_bytes": cache_bytes,
            "theoretical_audio_payload_gib": cache_bytes / (1024 ** 3),
            "wav_header_overhead_included": False,
            "per_condition_per_stem_binaural_intermediates_saved": False,
            "all_condition_listening_wavs_saved_by_default": False,
        },
        "phase2_5b_plan": {
            "separation_execution_rule": SEPARATION_EXECUTION_RULE,
            "source_metrics": {
                "per_stem": ["SI-SDR", "BSS Eval v4 SIR"],
                "macro": ["macro SI-SDR", "macro SIR"],
                "source_order": list(SOURCE_ORDER),
                "sir_package": "museval 0.4.1",
                "sir_parameters": {
                    "window": "infinity", "hop": "infinity", "compute_permutation": False,
                    "filters_len": 512, "framewise_filters": False,
                    "bsseval_sources_version": False,
                },
            },
            "downstream_metrics": [
                "binaural SI-SDR L/R/mean", "relative RMSE L/R/mean",
                "STFT log-magnitude MAE L/R/mean",
            ],
            "scientific_signal_policy": "raw float signals; listening-scaled PCM is excluded from scientific metrics",
            "representative_listening_ranks": [1, 5, 10],
            "representative_selection_rule": "deterministic manifest rank, not best/worst downstream metric",
        },
        "official_test_audio_content_accessed": False,
        "official_test_inference_run": False,
        "official_test_metrics_computed": False,
        "official_test_listening_performed": False,
        "official_test_manifest_generated": True,
    }


def seconds_to_hms(seconds: float) -> str:
    rounded = int(round(seconds))
    hours, remainder = divmod(rounded, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def make_document(manifest: dict, summary: dict) -> str:
    runtime = summary["runtime_estimate"]
    disk = summary["disk_estimate"]
    lines = [
        "# Phase 2.5a — Official Test Manifest Selection 与 Final Preflight",
        "",
        "## 结论",
        "",
        f"> {summary['status']}",
        "",
        "本阶段只访问 MUSDB18-HQ official test 的目录名、文件存在性和 RIFF/WAVE header metadata。"
        "未读取 waveform samples，未播放音频，未运行 HTDemucs-FT inference，未计算 source/downstream metrics，"
        "未生成 spectrogram、binaural output 或 listening WAV。",
        "",
        "## Pre-test Git 与冻结协议",
        "",
        f"- Branch：`{summary['pre_test_git']['branch']}`",
        f"- HEAD：`{summary['pre_test_git']['head']}`",
        "- Tracked working tree：clean",
        f"- Protocol version：`{manifest['protocol_version']}`",
        f"- Protocol SHA-256：`{manifest['protocol_sha256']}`（exact match）",
        "- `config/phase2/static_experiment_protocol.json`：untouched",
        "",
        "## Exact selection algorithm",
        "",
        f"对全部 {manifest['total_test_tracks']} 个 exact track directory name 执行 Unicode NFC；计算 "
        f"`SHA256(UTF8(\"{SELECTION_SALT}<normalized_track_name>\"))`，使用完整 lowercase hex digest 升序，"
        "仅在理论 digest collision 时以 NFC name 升序打破平局，选择 rank 1–10。未使用 random sampling、"
        "人工选择、genre/artist/duration balance 或 separation quality。",
        "",
        "## Final 10 tracks 与 header eligibility",
        "",
        "| Rank | Track | Selection SHA-256 | Duration (s) | fs (Hz) | Ch | 5 files | Frames compatible | Pass |",
        "|---:|---|---|---:|---:|---:|---|---|---|",
    ]
    for item in summary["selected_track_preflight"]:
        mixture = item["files"].get("mixture", {})
        lines.append(
            f"| {item['rank']} | {item['track_name_original']} | `{item['selection_sha256']}` | "
            f"{float(mixture.get('duration_s', 0.0)):.6f} | {mixture.get('sample_rate_hz', '—')} | "
            f"{mixture.get('channels', '—')} | {'yes' if item['all_required_files_exist'] else 'no'} | "
            f"{'yes' if item['frame_counts_compatible'] else 'no'} | {'PASS' if item['preflight_pass'] else 'FAIL'} |"
        )

    lines.extend(
        [
            "",
            "每首均检查 `mixture.wav`, `vocals.wav`, `drums.wav`, `bass.wav`, `other.wav`。每个文件的 "
            "sample rate、channels、frame count、duration、subtype/bit depth 与 file size 均保存在 "
            "`selected_tracks_preflight.csv` 和 `preflight_summary.json`。未执行 trim、resample 或修复。",
            "",
            "## Phase 2.5b execution clarification",
            "",
            f"固定规则：`{SEPARATION_EXECUTION_RULE}`。即先对完整 mixture 执行 full-track HTDemucs-FT，"
            "随后才提取 `[30 s, 60 s)`；禁止先截 mixture 再分离。这复现 Phase 2.3 使用 Phase 1 G "
            "full-track cache 后截取 excerpt 的 inference semantics，不是依据 test result 作出的调整，且未修改 frozen protocol JSON。",
            "",
            "## Runtime 与 disk estimate",
            "",
            f"- Selected mixture 总时长：`{runtime['total_selected_audio_duration_seconds']:.6f} s` "
            f"（`{runtime['total_selected_audio_duration_hms']}`）",
            f"- Phase 1 mean CPU RTF：`{runtime['phase1_mean_rtf']}`",
            f"- Estimated HTDemucs-FT CPU runtime：`{runtime['estimated_separation_runtime_seconds']:.3f} s` "
            f"（`{runtime['estimated_separation_runtime_hms']}`）",
            "- 上述仅为 Phase 1 mean RTF 的 rough estimate，不保证实际 runtime。",
            "- 30-second MATLAB HRTF rendering 与 downstream metrics 相对 HTDemucs-FT CPU inference 预计不是主要 bottleneck；本阶段未运行 MATLAB benchmark。",
            f"- 4 个 full-track stereo float32 estimated stems 理论 audio payload："
            f"`{disk['theoretical_audio_payload_bytes']} bytes`（`{disk['theoretical_audio_payload_gib']:.6f} GiB`），"
            "不含极小 WAV header overhead。",
            "- 不保存 per-condition/per-stem binaural intermediate WAV；不默认永久保存每首×每 condition 的全部 oracle/estimated listening WAV。",
            "",
            "## Phase 2.5b proposed output tree（只规划，未创建）",
            "",
            "```text",
            "outputs/phase2/phase2_5_final/",
            "├── manifest/",
            "├── metrics/",
            "├── figures/",
            "├── tracks/",
            "│   └── <track>/metadata/",
            "└── cache/htdemucs_ft/",
            "    └── <track>/",
            "        ├── vocals.wav",
            "        ├── drums.wav",
            "        ├── bass.wav",
            "        ├── other.wav",
            "        └── provenance.json",
            "```",
            "",
            "试听示例如需生成，固定使用 manifest rank `1`, `5`, `10`，不按 downstream metric 挑选最好/最差。",
            "",
            "## Frozen metric 与 RQ plan verification",
            "",
            "Phase 2.5b source-level metrics：per-stem SI-SDR、macro SI-SDR、per-stem BSS Eval v4 SIR、macro SIR；"
            "source order 为 `bass, vocals, drums, other`。SIR 使用 `museval 0.4.1`，`window=inf`, `hop=inf`, "
            "`compute_permutation=false`, `filters_len=512`, `framewise_filters=false`, `bsseval_sources_version=false`。",
            "",
            "MATLAB downstream metrics：binaural SI-SDR L/R/mean、relative RMSE L/R/mean、STFT log-magnitude MAE "
            "L/R/mean；spatial conditions 为 colocated/moderate/wide；scientific metrics 使用 raw float signals。"
            "STFT 固定为 periodic Hann、window 1024、hop 256、overlap 768、FFT 1024、MATLAB double eps，"
            "scientific metric 无额外 magnitude floor。",
            "",
            "RQ1 以 10 songs 为 paired units，报告 per-song points、mean、median 与 variability。RQ2 的 song-level "
            "`N=10`，Spearman 比较 macro SI-SDR / macro SIR 与 downstream metrics，moderate/wide 为 primary；"
            "禁止将 4 stems × 10 songs 当作 N=40。",
            "",
            "## Access provenance",
            "",
            "- `official_test_audio_content_accessed = false`",
            "- `official_test_inference_run = false`",
            "- `official_test_metrics_computed = false`",
            "- `official_test_listening_performed = false`",
            "- `official_test_manifest_generated = true`",
            "",
        ]
    )
    if summary["blockers"]:
        lines.extend(["## Blockers", ""] + [f"- {item}" for item in summary["blockers"]] + [""])
    else:
        lines.extend(["## Blockers", "", "无。", ""])
    return "\n".join(lines)


def main() -> None:
    branch, head, protocol_sha256, _protocol = verify_pre_access_gates()
    ranked = enumerate_and_rank_tracks()
    selected = [item for item in ranked if bool(item["selected"])]
    results = preflight_selected_tracks(selected)

    manifest = make_manifest(head, protocol_sha256, ranked, results)
    summary = make_summary(branch, head, protocol_sha256, ranked, results)
    csv_fieldnames, csv_rows = preflight_csv_rows(results)

    write_json_atomic(MANIFEST_PATH, manifest)
    write_csv_atomic(
        ALL_HASHES_PATH,
        ["track_name", "normalized_name", "sha256", "rank", "selected"],
        all_hash_rows(ranked),
    )
    write_csv_atomic(PREFLIGHT_CSV_PATH, csv_fieldnames, csv_rows)
    write_json_atomic(SUMMARY_PATH, summary)
    write_text_atomic(DOCUMENT_PATH, make_document(manifest, summary))

    print(json.dumps({
        "status": summary["status"],
        "git_head_before_test_access": head,
        "protocol_sha256": protocol_sha256,
        "total_test_tracks": len(ranked),
        "selected_track_count": len(results),
        "manifest": MANIFEST_PATH.relative_to(REPO_ROOT).as_posix(),
        "summary": SUMMARY_PATH.relative_to(REPO_ROOT).as_posix(),
    }, ensure_ascii=False, indent=2))
    if summary["blockers"]:
        raise RuntimeError("Phase 2.5a metadata eligibility gates failed; see preflight summary")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"PHASE2_5A_FAILED: {error}", file=sys.stderr)
        raise
