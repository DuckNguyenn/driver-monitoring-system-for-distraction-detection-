"""Verify software evidence and create a truthful machine-readable test report."""
import csv
import json
from pathlib import Path
import subprocess
import sys
import re
import argparse
import shutil
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from driver_monitor.config import ROOT
from driver_monitor.models import artifact_path, read_manifest, sha256

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, default=ROOT / "reports/software_verification.json")
parser.add_argument("--require-local-evidence", action="store_true",
                    help="Fail if local image regressions or the technical video evidence are missing")
args = parser.parse_args()
report = {"physical_board_tested": False, "esp32_flashing_tested": False}
suites = {}
for directory in ("tests", "camera_classical/tests"):
    # Legacy suites share module names; independent processes prevent import collisions.
    result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", directory], cwd=ROOT, capture_output=True, text=True)
    output = result.stdout + result.stderr
    print(output, end="")
    count = re.search(r"Ran (\d+) tests?", output)
    skipped = re.search(r"skipped=(\d+)", output)
    suites[directory] = {"tests": int(count.group(1)) if count else 0, "passed": result.returncode == 0,
                         "skipped": int(skipped.group(1)) if skipped else 0,
                         "output": output.strip()}
report["test_suites"] = suites
report["tests_total"] = sum(row["tests"] for row in suites.values())
report["tests_skipped"] = sum(row["skipped"] for row in suites.values())
pip = subprocess.run([sys.executable, "-m", "pip", "check"], cwd=ROOT, capture_output=True, text=True)
report["pip_check"] = {"passed": pip.returncode == 0, "output": pip.stdout.strip() or pip.stderr.strip()}
manifest_path = ROOT / "models/manifest.json"
manifest = read_manifest(manifest_path)
report["models"] = {"yunet": sha256(artifact_path(manifest_path, manifest["detector"]))}
for name, spec in manifest["classifiers"].items():
    report["models"][name] = {backend: sha256(artifact_path(manifest_path, artifact)) for backend, artifact in spec["artifacts"].items()}
video_csvs = sorted((ROOT / "reports/video_fixture_final").glob("*.csv"))
if video_csvs and (ROOT / "reports/video_fixture.avi").is_file():
    video_csv = video_csvs[-1]
    with video_csv.open(newline="", encoding="utf-8") as stream:
        frames = list(csv.DictReader(stream))
    video_passed = (len(frames) == 135 and all(row["quality"] == "usable" for row in frames)
                    and any(row["yawn_state"] == "yawn" for row in frames)
                    and max(int(row["yawn_count"]) for row in frames) == 1
                    and all(row["alert"] == "0" for row in frames)
                    and all(float(a["timestamp"]) < float(b["timestamp"]) for a, b in zip(frames, frames[1:])))
    report["technical_video"] = {"passed": video_passed, "skipped": False, "frames": len(frames),
                                 "csv": str(video_csv.relative_to(ROOT)),
                                 "source_sha256": sha256(ROOT / "reports/video_fixture.avi"), "real_cabin_accuracy_test": False}
else:
    video_passed = None
    report["technical_video"] = {"passed": None, "skipped": True,
                                 "note": "Local video and per-frame evidence are not distributed with the repository.",
                                 "real_cabin_accuracy_test": False}
compiler_name = shutil.which("g++")
compiler = Path(compiler_name) if compiler_name else Path("C:/MinGW/bin/g++.exe")
if compiler.is_file():
    (ROOT / "reports").mkdir(parents=True, exist_ok=True)
    executable = ROOT / "reports/firmware_test.exe"
    build = subprocess.run([str(compiler), str(ROOT / "tools/firmware_test.cpp"), "-std=c++11", "-static-libgcc", "-static-libstdc++", "-o", str(executable)], capture_output=True, text=True)
    result = subprocess.run([str(executable)], capture_output=True, text=True) if build.returncode == 0 else build
    report["firmware_host_simulator"] = {"passed": result.returncode == 0, "output": result.stdout.strip() or result.stderr.strip(), "sketch_sha256": sha256(ROOT / "esp32_buzzer/esp32_buzzer.ino")}
else:
    report["firmware_host_simulator"] = {"passed": None, "note": "Host compiler unavailable; hardware validation remains separate."}
report["local_evidence_complete"] = report["tests_skipped"] == 0 and video_passed is not None
report["software_checks_passed"] = (all(row["passed"] for row in suites.values()) and pip.returncode == 0
                                     and video_passed is not False and report["firmware_host_simulator"]["passed"] is not False)
path = args.output.resolve()
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
print(path)
raise SystemExit(0 if report["software_checks_passed"]
                 and (not args.require_local_evidence or report["local_evidence_complete"]) else 1)
