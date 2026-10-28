"""Check source/document limits, local docs links and every feature's context pack."""
import argparse
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

from context_pack import build_pack, render_files
from context_policy import ROOT, inspect_limits, load_features, load_policy, safe_file


LINK = re.compile(r"!?\[[^\]\n]*\]\((<[^>]+>|[^\s)]+)(?:\s+[^)]*)?\)")


def check_links(root):
    errors, count = [], 0
    names = ["AGENTS.md", "CONTEXT.md", "CONTEXT-MAP.md", "CHECKPOINT.md"]
    names += [path.relative_to(root).as_posix() for path in (root / "docs").rglob("*.md")]
    for name in names:
        path = safe_file(root, name)
        # Examples in fenced code are not navigation links.
        text = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
        for match in LINK.finditer(text):
            link = match[1].strip("<>")
            parsed = urlsplit(link)
            if parsed.scheme or link.startswith(("#", "//")):
                continue
            count += 1
            destination = (path.parent / unquote(parsed.path)).resolve()
            if not destination.is_relative_to(root) or not destination.exists():
                errors.append(f"Broken/outside local link in {name}: {link}")
    return errors, count


def inspect_repo(root):
    root = Path(root).resolve()
    policy = load_policy(root)
    result = inspect_limits(root, policy)
    features = load_features(root)
    links, result["links_checked"] = check_links(root)
    result["errors"].extend(links)
    startup = len(render_files(root, policy["context"]["startup_files"]).encode("utf-8"))
    result["startup_bytes"] = startup
    if startup > policy["context"]["startup_max_bytes"]:
        result["errors"].append(f"Startup context exceeds {policy['context']['startup_max_bytes']} bytes")
    result["feature_packs"] = {}
    for feature_id in features:
        try:
            pack = build_pack(root, feature_id, include_source=True, include_tests=True)
            result["feature_packs"][feature_id] = {"bytes": pack["payload_bytes"], "files": pack["file_count"]}
        except (ValueError, OSError) as error:
            result["errors"].append(str(error))
    result["passed"] = not result["errors"]
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = inspect_repo(args.root)
    except (ValueError, OSError, KeyError, TypeError) as error:
        result = {"passed": False, "errors": [str(error)]}
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        label = "PASS" if result["passed"] else "FAIL"
        print(f"{label}: docs/LOC/context guard")
        if "files_checked" in result:
            print(f"Files: {result['files_checked']}; links: {result['links_checked']}; startup: {result['startup_bytes']} bytes")
            for name, data in result["feature_packs"].items():
                print(f"  {name}: {data['bytes']} bytes, {data['files']} files")
        for message in result.get("errors", []):
            print(f"ERROR: {message}")
        for message in result.get("warnings", []):
            print(f"WARN: {message}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
