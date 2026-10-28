"""Prepare upload-only directories. Does not authenticate, upload, or start a job."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def prepare(username, run_id):
    if not re.fullmatch(r"[a-zA-Z0-9_-]{3,50}", username) or not re.fullmatch(r"[0-9]{8}-[0-9]{6}", run_id):
        raise ValueError("Invalid username/run ID")
    source = ROOT / "kaggle_upload/yawn_near_medium_dataset.zip"
    verification = json.loads((ROOT / "kaggle_upload/bundle_verification.json").read_text())
    actual_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if actual_hash != verification["sha256"]:
        raise ValueError("Dataset archive changed; rebuild and verify before uploading")
    with zipfile.ZipFile(source) as archive:
        if archive.testzip() is not None:
            raise ValueError("Dataset archive corrupted")
    destination = ROOT / "kaggle_upload/cloud" / run_id
    if destination.exists():
        raise ValueError("Run already prepared; use the existing metadata or a new run ID")
    dataset_dir, notebook_dir = destination / "dataset", destination / "notebook"
    dataset_dir.mkdir(parents=True)
    notebook_dir.mkdir()
    dataset_title = "Yawn Near Medium " + run_id
    notebook_title = "Yawn GPU Near Medium " + run_id
    dataset_id = username.lower() + "/" + dataset_title.lower().replace(" ", "-")
    notebook_id = username.lower() + "/" + notebook_title.lower().replace(" ", "-")
    shutil.copy2(source, dataset_dir / source.name)
    shutil.copy2(ROOT / "notebooks/yawn_near_medium_kaggle.ipynb", notebook_dir / "yawn_near_medium_kaggle.ipynb")
    dataset = {"title": dataset_title, "id": dataset_id, "licenses": [{"name": "other"}],
               "description": "Private research copy for this driver's yawn classifier. 735 native crop images: 575 train and 160 static validation. Two camera train clips (near/medium), no far or locked test clips. Includes two starting checkpoints and matching runtime preprocessing. Original source rights remain with their authors; no redistribution or public license is granted by this copy."}
    notebook = {"title": notebook_title, "id": notebook_id, "code_file": "yawn_near_medium_kaggle.ipynb",
                "language": "python", "kernel_type": "notebook", "is_private": True,
                "enable_gpu": True, "enable_internet": True, "machine_shape": "NvidiaTeslaT4",
                "dataset_sources": [dataset_id], "competition_sources": [], "kernel_sources": [], "model_sources": []}
    result = {"account": username.lower(), "dataset_id": dataset_id, "notebook_id": notebook_id,
              "dataset_directory": str(dataset_dir), "notebook_directory": str(notebook_dir),
              "dataset_sha256": actual_hash, "dataset_bytes": source.stat().st_size,
              "requested_accelerator": "NvidiaTeslaT4", "private": True, "cloud_execution_observed": False}
    for path, data in ((dataset_dir / "dataset-metadata.json", dataset), (notebook_dir / "kernel-metadata.json", notebook), (destination / "setup.json", result)):
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (ROOT / "kaggle_upload/cloud/latest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"))
    args = parser.parse_args()
    print(json.dumps(prepare(args.username, args.run_id), indent=2))
