"""Select one feature's context, with explicit byte/file budgets; no model imports."""
import argparse
import json
from pathlib import Path
import sys

from context_policy import ROOT, load_features, load_policy, safe_file


def render_files(root, names):
    chunks = []
    for name in names:
        text = safe_file(root, name).read_text(encoding="utf-8")
        chunks.append(f"\n--- FILE: {name} ---\n{text.rstrip()}\n")
    return "".join(chunks)


def build_pack(root, feature_id, *, include_source=False, include_tests=False, max_bytes=None):
    policy = load_policy(root)
    features = load_features(root)
    if feature_id not in features:
        raise ValueError(f"Unknown feature {feature_id!r}; use --list")
    budget = policy["context"]
    limit = budget["pack_max_bytes"] if max_bytes is None else max_bytes
    if isinstance(limit, bool) or not isinstance(limit, int) or not 0 < limit <= budget["pack_hard_max_bytes"]:
        raise ValueError(f"max-bytes must be 1..{budget['pack_hard_max_bytes']}")
    feature = features[feature_id]
    names = [*budget["startup_files"], feature["doc"]]
    if include_source:
        names.extend(feature.get("sources", []))
    if include_tests:
        names.extend(feature.get("tests", []))
    names = list(dict.fromkeys(names))
    if len(names) > budget["max_files"]:
        raise ValueError(f"{feature_id}: {len(names)} files > {budget['max_files']}; narrow the task")
    text = render_files(root, names)
    size = len(text.encode("utf-8"))
    if size > limit:
        raise ValueError(f"{feature_id}: {size} UTF-8 bytes > {limit}; select fewer inputs or split the task")
    files = [{"path": name, "bytes": safe_file(root, name).stat().st_size} for name in names]
    return {"feature": feature_id, "files": files, "file_count": len(files),
            "payload_bytes": size, "max_bytes": limit,
            "token_count": None,
            "note": "Bytes measure selected repo text, not total model/system/history tokens.",
            "text": text}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--feature")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--include-source", action="store_true")
    parser.add_argument("--include-tests", action="store_true")
    parser.add_argument("--max-bytes", type=int)
    parser.add_argument("--print", dest="show_text", action="store_true",
                        help="explicitly print the selected files; default lists sizes only")
    args = parser.parse_args(argv)
    try:
        if args.list:
            for key, value in load_features(args.root).items():
                print(f"{key}: {value['summary']}")
            return 0
        if not args.feature:
            raise ValueError("Choose --feature or --list")
        result = build_pack(args.root.resolve(), args.feature, include_source=args.include_source,
                            include_tests=args.include_tests, max_bytes=args.max_bytes)
        text = result.pop("text")
        print(text if args.show_text else json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"Context error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
