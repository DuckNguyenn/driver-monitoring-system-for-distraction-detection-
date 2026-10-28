"""Supply Kaggle credentials to Codex privately; never invoke this in a log.

Stdout is a credential channel consumed by Codex's http_headers_helper. Diagnostic
commands must call connection checks instead of displaying this program's stdout.
"""
import json
import os
from pathlib import Path


def access_token():
    token = os.environ.get("KAGGLE_API_TOKEN", "").strip()
    if not token:
        directory = Path(os.environ.get("KAGGLE_CONFIG_DIR") or Path.home() / ".kaggle")
        for name in ("access_token", "access_token.txt"):
            path = directory / name
            if path.is_file():
                token = path.read_text(encoding="utf-8-sig").strip()
                break
    if not token:
        from kagglesdk import KaggleClient
        from kagglesdk.kaggle_creds import KaggleCredentials
        with KaggleClient() as client:
            credentials = KaggleCredentials.load(client=client)
            if credentials is not None:
                token = credentials.get_access_token()
    if not token or any(c.isspace() for c in token):
        raise RuntimeError("Kaggle login required or token invalid")
    return token


def main():
    try:
        headers = {"Authorization": "Bearer " + access_token()}
    except Exception:
        # Do not include exception text: it can contain request/credential details.
        headers = {}
    print(json.dumps(headers))


if __name__ == "__main__":
    main()
