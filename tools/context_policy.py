"""Shared, standard-library-only limits and safe paths for documentation tools."""
from fnmatch import fnmatchcase
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {"node_modules", "dist", ".expo", "__pycache__", ".git", ".cache"}
SCAN_ROOTS = ("driver_monitor", "camera_classical", "frontend", "tools", "tests",
              "scripts", "esp32_buzzer", "docs")
GENERATED_TREES = {("frontend", "mobile", "android")}
SOURCE_SUFFIXES = {".cjs", ".py", ".ts", ".tsx", ".js", ".mjs", ".css", ".ps1", ".sh", ".ino", ".cpp", ".h"}
PRIVATE_PARTS = {".git", ".cache", ".codex", ".agents", ".aws", "node_modules",
                 ".kaggle", ".ssh", ".scratch", "credentials", "secrets", "dist", ".expo",
                 "logs", "kaggle_output", "kaggle_upload", "data_collection", "data_reviews"}
PRIVATE_NAMES = {".dashboard-token", "kaggle.json", "id_rsa", "id_ed25519"}
PRIVATE_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".jsonl", ".avi", ".mp4", ".mov", ".sqlite3", ".pt", ".onnx", ".rknn"}


def generated_path(relative):
    parts = tuple(part.casefold() for part in Path(relative).parts)
    return any(parts[:len(prefix)] == prefix for prefix in GENERATED_TREES)


def safe_file(root, relative):
    """Resolve before reading; prevent traversal, secret inclusion and link escapes."""
    name = str(relative).replace("\\", "/")
    path = Path(name)
    if path.is_absolute() or ":" in name or ".." in path.parts:
        raise ValueError(f"Unsafe context path: {name}")
    if (generated_path(path) or any(part.casefold() in PRIVATE_PARTS or part.casefold().startswith(".venv") for part in path.parts)
            or path.name.casefold().startswith(".env") or path.name.casefold() in PRIVATE_NAMES
            or path.suffix.lower() in PRIVATE_SUFFIXES):
        raise ValueError(f"Private/generated artifact excluded from context: {name}")
    root = Path(root).resolve()
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError(f"Missing or outside workspace: {name}")
    return resolved


def read_json(root, relative):
    return json.loads(safe_file(root, relative).read_text(encoding="utf-8"))


def load_policy(root):
    policy = read_json(root, "docs/engineering/limits.json")
    if policy.get("schema_version") != 1:
        raise ValueError("Unsupported limits schema")
    return policy


def load_features(root):
    mapping = read_json(root, "docs/feature-map.json")
    if mapping.get("schema_version") != 1 or not mapping.get("features"):
        raise ValueError("Invalid feature map")
    features = mapping["features"]
    for key, feature in features.items():
        if not key or not isinstance(feature.get("summary"), str):
            raise ValueError("Feature id and summary are required")
        for name in [feature["doc"], *feature.get("sources", []), *feature.get("tests", [])]:
            safe_file(root, name)
        if any(related not in features for related in feature.get("related", [])):
            raise ValueError(f"Unknown related feature: {key}")
    return features


def measurements(path):
    raw = path.read_bytes()
    return {"lines": len(raw.splitlines()), "bytes": len(raw)}


def file_limits(name, policy):
    for rule in policy["rules"]:
        if any(fnmatchcase(name, pattern) for pattern in rule["patterns"]):
            return {key: rule[key] for key in ("max_lines", "max_bytes")}
    return None


def scoped_files(root):
    root = Path(root).resolve()
    for path in sorted(root.glob("*.md")):
        yield path
    for folder in SCAN_ROOTS:
        start = root / folder
        if not start.is_dir():
            continue
        for current, directories, files in os.walk(start, followlinks=False):
            directories[:] = sorted(d for d in directories if d not in SKIP_DIRS
                                    and not d.startswith(".venv")
                                    and not generated_path((Path(current) / d).relative_to(root)))
            for name in sorted(files):
                path = Path(current) / name
                if path.suffix.lower() in SOURCE_SUFFIXES | {".md"}:
                    yield path


def inspect_limits(root, policy):
    root = Path(root).resolve()
    errors, warnings, count = [], [], 0
    exceptions = policy.get("legacy_exceptions", {})
    for path in scoped_files(root):
        relative = path.relative_to(root).as_posix()
        limits = file_limits(relative, policy)
        if limits is None:
            continue
        path = safe_file(root, relative)
        count += 1
        actual = measurements(path)
        legacy = exceptions.get(relative)
        if legacy:
            if not legacy.get("reason"):
                errors.append(f"Legacy exception lacks reason: {relative}")
            limits = {key: max(limits[key], legacy.get(key, 0)) for key in limits}
        for field, key in (("lines", "max_lines"), ("bytes", "max_bytes")):
            if actual[field] > limits[key]:
                errors.append(f"{relative}: {actual[field]} {field} > {limits[key]}")
        if actual["lines"] > 300:
            warnings.append(f"{relative}: {actual['lines']} lines; prefer a focused module")
    for name in exceptions:
        safe_file(root, name)
        if file_limits(name, policy) is None:
            errors.append(f"Unscoped legacy exception: {name}")
    return {"files_checked": count, "errors": errors, "warnings": warnings}
