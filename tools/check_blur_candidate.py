"""Run the existing pixel regressions using an explicitly selected candidate."""
import argparse
import contextlib
import importlib
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
from driver_monitor.config import load_config
from driver_monitor.models import sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/camera_blur_candidate.yaml")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/blur_refinement/pixel_regressions.json")
    parser.add_argument("--require-local-evidence", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    modules = [importlib.import_module(name) for name in ("test_eye_classifier", "test_smile_classifier",
               "test_yawn_camera_classifier", "test_head_motion", "test_blur_candidate")]
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in modules)
    with contextlib.ExitStack() as stack:
        for module in modules:
            stack.enter_context(patch.object(module, "load_config", lambda *a, **kw: load_config(args.config, **kw)))
        result = unittest.TextTestRunner(verbosity=1).run(suite)
    report = {"candidate_config": str(args.config.resolve().relative_to(ROOT)),
              "manifest_sha256": sha256(config.manifest), "tests_run": result.testsRun,
              "skipped": [{"test": str(t), "reason": r} for t, r in result.skipped],
              "failures": len(result.failures), "errors": len(result.errors),
              "passed": result.wasSuccessful() and (not args.require_local_evidence or not result.skipped),
              "independent_camera_acceptance": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
