"""Run existing unittest cases and fixture-free test functions without pytest."""
from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    suite = unittest.TestSuite()
    files = sorted((ROOT / "tests").rglob("test_*.py"))
    for index, file in enumerate(files):
        name = f"repository_regression_{index}_{file.stem}"
        spec = importlib.util.spec_from_file_location(name, file)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
        for name, function in inspect.getmembers(module, inspect.isfunction):
            if name.startswith("test_") and function.__module__ == module.__name__:
                if inspect.signature(function).parameters:
                    raise RuntimeError(f"Use pytest for tests with fixtures: {file}:{name}")
                suite.addTest(unittest.FunctionTestCase(function, description=f"{file.name}:{name}"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {
        "status": "PASS" if result.wasSuccessful() else "FAIL",
        "tests": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "files": [p.relative_to(ROOT).as_posix() for p in files],
        "python": sys.version,
        "executable": sys.executable,
        "scope": "Existing tests only; stub/tiny-model inference, no training or new scientific results.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
