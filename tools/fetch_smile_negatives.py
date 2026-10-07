"""Fetch a pinned SMILEs snapshot; only smiling faces are no_yawn negatives.

The repository's non-smile set is deliberately excluded: non-smile does not
mean non-yawn. Identity labels are unavailable, so this is a development set.
"""
import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
COMMIT = "6afac66f50061948eed7da5a351cecd9c4a99fe3"
URL = f"https://codeload.github.com/hromi/SMILEsmileD/zip/{COMMIT}"


def main():
    output = ROOT / ".cache" / "smiles"
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"{COMMIT}.zip"
    if not archive.exists():
        request = urllib.request.Request(URL, headers={"User-Agent": "driver-monitor-research"})
        with urllib.request.urlopen(request, timeout=90) as source, archive.with_suffix(".partial").open("wb") as dest:
            while chunk := source.read(1024 * 1024):
                dest.write(chunk)
        archive.with_suffix(".partial").replace(archive)
    records = []
    with zipfile.ZipFile(archive) as data:
        for info in data.infolist():
            parts = PurePosixPath(info.filename).parts
            if len(parts) < 4 or parts[1:3] != ("SMILEs", "positives"):
                continue
            if PurePosixPath(info.filename).suffix.lower() not in (".jpg", ".jpeg", ".png", ".pgm"):
                continue
            if ".." in parts or info.file_size > 8 * 1024 * 1024:
                raise ValueError(f"Unsafe archive entry: {info.filename}")
            relative = Path(*parts[3:])
            destination = (output / "positive" / relative).resolve()
            if not destination.is_relative_to(output.resolve()):
                raise ValueError("Archive entry outside dataset directory")
            content = data.read(info)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
            records.append({"path": destination.relative_to(output).as_posix(),
                            "sha256": hashlib.sha256(content).hexdigest(),
                            "label": "no_yawn", "source_label": "smile", "subject": None})
    if not records:
        raise ValueError("Snapshot contains no smiling faces")
    provenance = {"source": "https://github.com/hromi/SMILEsmileD", "commit": COMMIT,
                  "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                  "subject_independence": "unknown; development evaluation only", "samples": records}
    (output / "source.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "smiles": len(records),
                      "archive_sha256": provenance["archive_sha256"]}), flush=True)


if __name__ == "__main__":
    main()
