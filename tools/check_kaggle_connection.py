"""Read-only Kaggle MCP verification; credentials are never written or printed."""
import argparse
import json
from pathlib import Path
import sys

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.kaggle_mcp_headers import access_token


class KaggleMCP:
    URL = "https://www.kaggle.com/mcp"

    def __init__(self):
        self.session = requests.Session()
        self.headers = {"Authorization": "Bearer " + access_token(), "Accept": "application/json, text/event-stream"}
        self.sequence = 0
        result, response = self.request("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "driver-monitor", "version": "1.0"}})
        self.headers["MCP-Protocol-Version"] = result["protocolVersion"]
        if response.headers.get("Mcp-Session-Id"):
            self.headers["Mcp-Session-Id"] = response.headers["Mcp-Session-Id"]
        initialized = self.session.post(self.URL, headers=self.headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"}, timeout=20)
        initialized.raise_for_status()

    def request(self, method, params):
        self.sequence += 1
        response = self.session.post(self.URL, headers=self.headers, json={"jsonrpc": "2.0", "id": self.sequence, "method": method, "params": params}, timeout=30)
        response.raise_for_status()
        if "text/event-stream" in response.headers.get("Content-Type", ""):
            messages = [json.loads(line[5:]) for line in response.text.splitlines() if line.startswith("data:")]
            data = next(m for m in messages if m.get("id") == self.sequence)
        else:
            data = response.json()
        if "error" in data:
            raise RuntimeError("MCP request rejected")
        return data["result"], response

    def tools(self):
        result, _ = self.request("tools/list", {})
        return result["tools"]

    def read(self, name, arguments):
        if name not in {"get_dataset_info", "get_notebook_info", "get_notebook_session_status", "get_accelerator_quota"}:
            raise ValueError("Only configured read-only methods are allowed")
        result, _ = self.request("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            raise RuntimeError("Kaggle read failed")
        if "structuredContent" in result:
            return result["structuredContent"]
        texts = [c["text"] for c in result.get("content", []) if c.get("type") == "text"]
        return json.loads(texts[0]) if len(texts) == 1 else {"content": texts}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--describe-tool")
    parser.add_argument("--dataset", help="Verify actual read access to this private owner/slug")
    args = parser.parse_args()
    try:
        mcp = KaggleMCP()
        tools = mcp.tools()
        if args.describe_tool:
            print(json.dumps(next(t["inputSchema"] for t in tools if t["name"] == args.describe_tool), indent=2))
        else:
            verification = {"mcp_connected": True, "tool_count": len(tools), "token_logged": False,
                            "private_resource_authorized": None}
            if args.dataset:
                owner, slug = args.dataset.split("/", 1)
                mcp.read("get_dataset_info", {"request": {"ownerSlug": owner, "datasetSlug": slug}})
                verification["private_resource_authorized"] = True
            print(json.dumps(verification))
            destination = ROOT / "kaggle_upload/cloud/connection_verification.json"
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(verification, indent=2) + "\n", encoding="utf-8")
    except Exception as error:
        verification = {"private_resource_authorized": False, "error_type": type(error).__name__, "token_logged": False}
        print(json.dumps(verification))
        destination = ROOT / "kaggle_upload/cloud/connection_verification.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(verification, indent=2) + "\n", encoding="utf-8")
        sys.exit(1)


if __name__ == "__main__":
    main()
