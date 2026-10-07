"""Fetch positive smile labels from the MPLab GENKI-4K public release."""
import hashlib
import json
import tarfile
import urllib.request
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
URL = "https://mplab.ucsd.edu/398/media/genki4k.tar"


def main():
    output = ROOT / ".cache/genki"
    output.mkdir(parents=True, exist_ok=True)
    archive = output / "genki4k.tar"
    if not archive.is_file():
        request = urllib.request.Request(URL, headers={"User-Agent": "driver-monitor-research"})
        with urllib.request.urlopen(request, timeout=90) as source, archive.with_suffix(".partial").open("wb") as dest:
            while chunk := source.read(1024 * 1024):
                dest.write(chunk)
        archive.with_suffix(".partial").replace(archive)
    records = []
    with tarfile.open(archive) as data:
        members = {PurePosixPath(m.name).name: m for m in data.getmembers() if m.isfile()}
        readmes = [m for name, m in members.items() if name.lower().startswith("readme")]
        for member in readmes:
            print(data.extractfile(member).read().decode("utf-8", errors="replace"), flush=True)
        label_file = next(m for name, m in members.items() if name.lower() == "labels.txt")
        labels = data.extractfile(label_file).read().decode("utf-8").splitlines()
        for index, row in enumerate(labels, 1):
            if not row.strip() or row.split()[0] != "1":
                continue  # non-smile is not an automatically valid no_yawn label
            filename = f"file{index:04d}.jpg"
            member = members[filename]
            if member.size > 8 * 1024 * 1024:
                raise ValueError("Unexpected image size")
            content = data.extractfile(member).read()
            destination = output / "positive" / filename
            destination.parent.mkdir(exist_ok=True)
            destination.write_bytes(content)
            records.append({"path": destination.relative_to(output).as_posix(),
                            "sha256": hashlib.sha256(content).hexdigest(), "label": "no_yawn",
                            "source_label": "smile", "subject": None})
    if not records:
        raise ValueError("No positive smile labels")
    provenance = {"source": "https://mplab.ucsd.edu/398/", "download": URL,
                  "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                  "subject_independence": "unknown; development evaluation only", "samples": records}
    (output / "source.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "smiles": len(records),
                      "archive_sha256": provenance["archive_sha256"]}), flush=True)


if __name__ == "__main__":
    main()
