"""Human-only hidden token entry using Kaggle's documented local token file."""
import getpass
import os
from pathlib import Path
import sys


def main():
    if not sys.stdin.isatty():
        raise SystemExit("Run this command in your own interactive terminal; never send the token in chat.")
    token = getpass.getpass("Paste Kaggle API token here (hidden): ").strip()
    if not token.startswith("KGAT") or any(c.isspace() for c in token):
        raise SystemExit("Invalid token format; nothing saved.")
    directory = Path(os.environ.get("KAGGLE_CONFIG_DIR") or Path.home() / ".kaggle")
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / "access_token"
    temporary = directory / "access_token.new"
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(token + "\n")
    temporary.chmod(0o600)
    temporary.replace(destination)
    print("Token saved locally. No token was printed or added to the project.")
    print("Restart Codex after verifying the MCP connection.")


if __name__ == "__main__":
    main()
