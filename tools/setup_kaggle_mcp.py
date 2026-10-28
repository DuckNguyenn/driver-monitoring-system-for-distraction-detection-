"""Configure the official remote MCP without placing secrets in config.toml."""
import argparse
import copy
import json
from pathlib import Path
import re
import shutil
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def server_settings():
    command = subprocess.list2cmdline([
        str(ROOT / ".venv-cloud/Scripts/python.exe"),
        str(ROOT / "tools/kaggle_mcp_headers.py"),
    ])
    return {"url": "https://www.kaggle.com/mcp", "bearer_token_env_var": "KAGGLE_API_TOKEN",
            "http_headers_helper": command, "startup_timeout_sec": 30, "tool_timeout_sec": 120}


def merge_config(original, settings):
    before = tomllib.loads(original)
    if before.get("mcp_servers", {}).get("kaggle", {}).get("url") not in (None, settings["url"]):
        raise ValueError("Existing Kaggle server has a different endpoint")
    # Preserve all other sections, including comments; only change this server.
    match = re.search(r"(?m)^\[mcp_servers\.kaggle\]\s*$", original)
    if match:
        following = re.search(r"(?m)^\[", original[match.end():])
        end = match.end() + following.start() if following else len(original)
        section = original[match.end():end]
        for key, value in settings.items():
            line = key + " = " + json.dumps(value, ensure_ascii=False)
            pattern = rf"(?m)^{re.escape(key)}\s*=.*$"
            section = re.sub(pattern, lambda _: line, section) if re.search(pattern, section) else section.rstrip() + "\n" + line + "\n"
        merged = original[:match.end()] + section.rstrip() + "\n\n" + original[end:]
    else:
        merged = original.rstrip() + "\n\n[mcp_servers.kaggle]\n"
        merged += "".join(k + " = " + json.dumps(v, ensure_ascii=False) + "\n" for k, v in settings.items())
    expected = copy.deepcopy(before)
    expected.setdefault("mcp_servers", {}).setdefault("kaggle", {}).update(settings)
    if tomllib.loads(merged) != expected:
        raise ValueError("Configuration verification failed; file not changed")
    return merged


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write the reviewed global Codex config")
    args = parser.parse_args()
    settings = server_settings()
    draft = ROOT / "kaggle_upload/kaggle-mcp.toml"
    draft.parent.mkdir(exist_ok=True)
    draft.write_text("[mcp_servers.kaggle]\n" + "".join(k + " = " + json.dumps(v) + "\n" for k, v in settings.items()), encoding="utf-8")
    if args.apply:
        config = Path.home() / ".codex/config.toml"
        original = config.read_text(encoding="utf-8")
        merged = merge_config(original, settings)
        if merged != original:
            backup = config.with_name("config.toml.before-kaggle-helper.bak")
            if not backup.exists():
                shutil.copy2(config, backup)
            config.write_text(merged, encoding="utf-8")
        print("Kaggle MCP configured; credentials remain outside this project.")
    else:
        print("Reviewed draft:", draft)


if __name__ == "__main__":
    main()
