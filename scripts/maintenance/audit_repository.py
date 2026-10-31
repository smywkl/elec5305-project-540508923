"""Read-only inventory, source-language, link and frozen-evidence checks."""
from __future__ import annotations

import argparse
import ast
import collections
import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import sys
import tokenize
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
CODE = {".py", ".m", ".ps1", ".sh", ".bat", ".cmd", ".js", ".ts", ".jsx", ".tsx", ".c", ".cpp", ".h", ".r"}
HAN = re.compile(r"[\u3400-\u9fff]")


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def inventory():
    files, directories = [], []
    for base, children, names in os.walk(ROOT):
        folder = Path(base)
        relative_folder = folder.relative_to(ROOT)
        if relative_folder.parts and relative_folder.parts[0] == ".git":
            children[:] = []
            continue
        directories.extend((folder / d).relative_to(ROOT).as_posix() for d in children if d != ".git")
        for name in names:
            file = folder / name
            relative = file.relative_to(ROOT).as_posix()
            stat = file.stat()
            files.append(dict(path=relative, bytes=stat.st_size, mtime_ns=stat.st_mtime_ns,
                              depth=len(file.relative_to(ROOT).parts) - 1))
    return dict(files=files, directories=directories,
                file_count=len(files), directory_count=len(directories),
                max_directory_depth=max((len(d.split("/")) for d in directories), default=0),
                top_level_files=dict(collections.Counter(f["path"].split("/")[0] if "/" in f["path"] else "<root>" for f in files)))


def source_audit(files):
    comments, strings, syntax, counts = [], [], [], collections.Counter()
    for item in files:
        file = ROOT / item["path"]
        if file.suffix.lower() not in CODE or ".git" in file.parts:
            continue
        counts[item["path"].split("/")[0]] += 1
        text = file.read_text(encoding="utf-8-sig", errors="strict")
        chinese_lines = [(i, line) for i, line in enumerate(text.splitlines(), 1) if HAN.search(line)]
        if file.suffix == ".py":
            try:
                tree = ast.parse(text, filename=str(file))
                for token in tokenize.generate_tokens(io.StringIO(text).readline):
                    if token.type == tokenize.COMMENT and HAN.search(token.string):
                        comments.append(dict(path=item["path"], line=token.start[0], kind="comment"))
                for node in ast.walk(tree):
                    if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        doc = ast.get_docstring(node)
                        if doc and HAN.search(doc):
                            comments.append(dict(path=item["path"], line=node.body[0].lineno, kind="docstring"))
            except (SyntaxError, tokenize.TokenError) as error:
                syntax.append(dict(path=item["path"], error=str(error)))
        for line_number, line in chinese_lines:
            if file.suffix != ".py":
                # Every non-Python Han line is retained for manual review of
                # inline/block comments versus useful test/path/UI literals.
                if line.lstrip().startswith(("%", "#", "//", "/*", "*", "REM ", "rem ", "::")):
                    comments.append(dict(path=item["path"], line=line_number, kind="comment"))
            strings.append(dict(path=item["path"], line=line_number, text=line))
    return dict(source_files=sum(counts.values()), by_top_level=dict(counts),
                chinese_comments_or_docstrings=comments, han_lines_for_manual_classification=strings,
                python_syntax_errors=syntax,
                scope="All source files including ignored outputs, vendored references and skill helpers; .git metadata excluded.")


def link_audit(files):
    broken, checked = [], 0
    for item in files:
        file = ROOT / item["path"]
        if file.suffix != ".md" or item["path"].split("/")[0] not in {"docs", "README.md", "PROJECT_STATE.md", "data"}:
            continue
        text = file.read_text(encoding="utf-8-sig")
        text = re.sub(r"```.*?```", "", text, flags=re.S)
        for target in re.findall(r"!?\[[^\]]*\]\(([^\n)]+)\)", text):
            target = target.strip().strip("<>")
            if target.startswith(("#", "http:", "https:", "mailto:", "codex:", "plugin:")):
                continue
            path = unquote(target.split("#", 1)[0])
            checked += 1
            if path and not (file.parent / path).exists():
                broken.append(dict(document=item["path"], target=target))
    return dict(checked=checked, broken=broken)


def import_file(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def science_audit():
    module = import_file("scripts/python/phase3/phase3_2b_cross_subject.py", "audit_cross_subject")
    run = ROOT / "outputs/phase3/phase3_2b_cross_subject_20261026_run1"
    preflight = module.read_json(run / "preflight.json")
    completion = module.read_json(run / "completion.json")
    checks = {}
    for group in ["frozen_hashes", "code_and_metadata_hashes"]:
        expected = preflight[group]
        bad = [path for path, wanted in expected.items() if not (ROOT / path).is_file() or sha(ROOT / path) != wanted]
        checks[group] = dict(count=len(expected), mismatches=bad)
    bad = [path for path, wanted in completion["output_sha256"].items() if sha(run / path) != wanted]
    checks["phase3_outputs"] = dict(count=len(completion["output_sha256"]), mismatches=bad)
    manifest = module.read_json(ROOT / "config/phase2/final_test_manifest.json")
    tracks = [t["track_name_original"] for t in manifest["selected_tracks"]]
    tables = {k: module.read_csv(run / "metrics" / v) for k, v in module.FILES.items()}
    checks["tables"] = module.validate_tables(tables, tracks, preflight["schemas"])
    # Compare stored pairs against stored raw tables, without writing/recomputing DSP.
    by_case = {module.key(r): r for r in tables["mechanism"]}
    paired = module.read_csv(run / "metrics/paired_comparison.csv")
    for row in paired:
        subject, rank, track = row["subject_id"], int(row["rank"]), row["track"]
        condition = row["contrast"].split("-")[0]
        expected = float(by_case[(subject, rank, track, condition)]["error_retention_ratio"]) - float(by_case[(subject, rank, track, "colocated")]["error_retention_ratio"])
        assert abs(float(row["delta_error_retention_ratio"]) - expected) < 1e-12
    checks["paired_contrasts"] = dict(rows=len(paired), positive_delta_R=sum(float(r["delta_error_retention_ratio"]) > 0 for r in paired))
    checkpoint_count, checkpoint_mismatches = 0, []
    for marker in sorted((run / "tracks").rglob("completion.json")):
        record = module.read_json(marker)
        for entry in record["files"]:
            # Files are stored as path/hash records in the historical marker.
            if isinstance(entry, dict):
                path = entry.get("path", entry.get("file"))
                expected = entry["sha256"]
            else:
                path, expected = entry, record["files"][entry]
            file = Path(path)
            if not file.is_absolute():
                file = marker.parent / file
            checkpoint_count += 1
            if not file.is_file() or sha(file) != expected:
                checkpoint_mismatches.append(str(file))
    checks["checkpoints"] = dict(files=checkpoint_count, mismatches=checkpoint_mismatches)
    checks["sofa"] = dict(count=3, mismatches=[s for s, wanted in zip(module.SUBJECTS, module.SOFA_HASHES) if sha(ROOT / f"data/hrtf/cipic/{s}.sofa") != wanted])
    pipeline = import_file("scripts/openunmix_v2/pipeline.py", "audit_pipeline")
    split = pipeline.load_and_validate_split()
    assert not (set(split["train"]) & set(split["validation"]))
    assert len(split["train"]) == 90 and len(split["validation"]) == 10
    test_names = {p.name for p in (ROOT / "data/musdb18hq/test").iterdir() if p.is_dir()}
    assert not (set(split["train"] + split["validation"]) & test_names)
    checks["split"] = dict(train=90, validation=10, official_test_tracks=len(test_names), test_overlap=0, seed=split["seed"])
    ft = import_file("scripts/evaluation/evaluate_htdemucs_ft.py", "audit_ft")
    model, fingerprint = ft.inspect_official_definition(ft.WEIGHTS_DIR, pipeline.split_sha256(split))
    historical = module.read_json(ft.OUTPUT_ROOT / "evaluation_results.json")
    assert fingerprint == historical["configuration_fingerprint"]
    records = ft.collect_valid_records(ft.OUTPUT_ROOT, split["validation"], fingerprint)
    assert len(records) == 10
    checks["phase1"] = dict(validated_records=len(records), revision=model["revision"], weight_files=len(model["models"]),
                            macro_si_sdr_db=historical["macro_mean_si_sdr_db"], fingerprint=fingerprint,
                            custom_checkpoint_used=model["custom_checkpoint_used"], official_test_used=historical["official_test_used"])
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--science", action="store_true")
    args = parser.parse_args()
    report = inventory()
    report["source_audit"] = source_audit(report["files"])
    report["links"] = link_audit(report["files"])
    if args.backup:
        before = json.loads((args.backup / "inventory_before.json").read_text(encoding="utf-8"))
        prefixes = ("data/", "outputs/phase2/", "outputs/phase3/", "outputs/evaluation/", "outputs/training/", "outputs/training_pilot/", "outputs/cache/")
        checked, bad = 0, []
        for item in before["files"]:
            if not item["path"].startswith(prefixes):
                continue
            checked += 1
            file = ROOT / item["path"]
            if not file.is_file() or file.stat().st_size != item["bytes"] or file.stat().st_mtime_ns != item["mtime_ns"] or ("sha256" in item and sha(file) != item["sha256"]):
                bad.append(item["path"])
        report["protected_initial_files"] = dict(count=checked, mismatches=bad, method="Size/mtime for all; SHA-256 for initial files <=2 MB, plus separate frozen-model/cache checks.")
        moves = list(csv.DictReader((ROOT / "docs/final_audit/cleanup_manifest.csv").open(encoding="utf-8", newline="")))
        bad = [r["backup_path"] for r in moves if not Path(r["backup_path"]).is_file() or sha(r["backup_path"]) != r["sha256_before"]]
        report["recovery"] = dict(manifest_rows=len(moves), missing_or_changed_backups=bad)
    if args.science:
        report["science"] = science_audit()
    failures = []
    if report["source_audit"]["chinese_comments_or_docstrings"] or report["source_audit"]["python_syntax_errors"]:
        failures.append("source comments/docstrings or Python syntax")
    if report["links"]["broken"]:
        failures.append("local documentation links")
    if args.backup and (report["protected_initial_files"]["mismatches"] or report["recovery"]["missing_or_changed_backups"]):
        failures.append("protected artifacts or recovery copies")
    if args.science:
        for name, value in report["science"].items():
            if value.get("mismatches"):
                failures.append("scientific evidence: " + name)
    report["status"] = "PASS" if not failures else "FAIL"
    report["failed_checks"] = failures
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in {"files", "directories", "source_audit"}}, indent=2))
    print("SOURCE_AUDIT", json.dumps({k: v for k, v in report["source_audit"].items() if k != "han_lines_for_manual_classification"}))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
