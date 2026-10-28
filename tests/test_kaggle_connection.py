import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest.mock import patch

from tools import kaggle_mcp_headers as headers
from tools import check_kaggle_connection as connection
from tools.setup_kaggle_mcp import merge_config, server_settings


class KaggleConnectionTests(unittest.TestCase):
    def test_merge_preserves_other_servers_and_keys(self):
        text = '# local settings\nmodel = "test"\n[mcp_servers.other]\nurl = "https://example.org"\n[mcp_servers.kaggle]\nurl = "https://www.kaggle.com/mcp"\n[features]\nfoo = true\n'
        settings = server_settings()
        merged = merge_config(text, settings)
        self.assertEqual(tomllib.loads(merged)["mcp_servers"]["other"], tomllib.loads(text)["mcp_servers"]["other"])
        self.assertEqual(merge_config(merged, settings), merged)
        self.assertNotIn("Authorization", merged)

    def test_merge_does_not_replace_different_endpoint(self):
        with self.assertRaises(ValueError):
            merge_config('[mcp_servers.kaggle]\nurl="https://other.example"\n', server_settings())

    def test_helper_uses_env_before_file_without_printing(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "access_token").write_text("file-sentinel-123456789")
            output = io.StringIO()
            with patch.dict(os.environ, {"KAGGLE_CONFIG_DIR": directory, "KAGGLE_API_TOKEN": "env-sentinel-123456789"}), contextlib.redirect_stdout(output):
                self.assertEqual(headers.access_token(), "env-sentinel-123456789")
            self.assertEqual(output.getvalue(), "")

    def test_helper_error_does_not_expose_exception(self):
        output = io.StringIO()
        with patch.object(headers, "access_token", side_effect=RuntimeError("secret-sentinel")), contextlib.redirect_stdout(output):
            headers.main()
        self.assertEqual(json.loads(output.getvalue()), {})
        self.assertNotIn("secret-sentinel", output.getvalue())

    def test_invalid_header_token_is_rejected(self):
        with patch.dict(os.environ, {"KAGGLE_API_TOKEN": "abc\nInjected: bad"}):
            with self.assertRaises(RuntimeError):
                headers.access_token()

    def test_tool_catalog_does_not_prove_private_access(self):
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with patch.object(connection, "ROOT", Path(directory)), patch.object(connection, "KaggleMCP") as client, patch.object(connection.sys, "argv", ["check_kaggle_connection.py"]), contextlib.redirect_stdout(output):
                client.return_value.tools.return_value = [{"name": "get_dataset_info"}]
                connection.main()
            result = json.loads(output.getvalue())
            self.assertTrue(result["mcp_connected"])
            self.assertIsNone(result["private_resource_authorized"])
            client.return_value.read.assert_not_called()

    def test_private_denial_is_reported_even_when_catalog_succeeds(self):
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with patch.object(connection, "ROOT", Path(directory)), patch.object(connection, "KaggleMCP") as client, patch.object(connection.sys, "argv", ["check_kaggle_connection.py", "--dataset", "owner/private-data"]), contextlib.redirect_stdout(output):
                client.return_value.tools.return_value = [{"name": "get_dataset_info"}]
                client.return_value.read.side_effect = RuntimeError("secret-sentinel")
                with self.assertRaises(SystemExit) as stopped:
                    connection.main()
            self.assertEqual(stopped.exception.code, 1)
            result = json.loads(output.getvalue())
            self.assertFalse(result["private_resource_authorized"])
            self.assertNotIn("secret-sentinel", output.getvalue())
            saved = json.loads(Path(directory, "kaggle_upload/cloud/connection_verification.json").read_text())
            self.assertFalse(saved["private_resource_authorized"])


if __name__ == "__main__":
    unittest.main()
