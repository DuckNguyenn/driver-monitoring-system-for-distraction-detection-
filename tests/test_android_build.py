"""Regression for PowerShell treating successful native stderr as a fatal error."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which('powershell.exe')
NODE = shutil.which('node.exe')


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


@unittest.skipUnless(os.name == 'nt' and POWERSHELL and NODE, 'Windows PowerShell and Node required')
class AndroidNativeCommandTests(unittest.TestCase):
    def invoke(self, exit_code):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory, 'native.cjs')
            fixture.write_text(f"console.error('SDK warning fixture');process.exit({exit_code});", encoding='utf-8')
            helper = ROOT / 'tools' / 'android_native_command.ps1'
            command = ("$ErrorActionPreference='Stop'; . " + quote(helper) +
                       "; Invoke-AndroidNative -FilePath " + quote(NODE) +
                       " -ArgumentList @(" + quote(fixture) + "); Write-Output 'NATIVE_COMPLETED'")
            return subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', command],
                                  cwd=ROOT, capture_output=True, text=True, timeout=20)

    def test_successful_native_warning_does_not_abort_build(self):
        result = self.invoke(0)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('SDK warning fixture', result.stdout)
        self.assertIn('NATIVE_COMPLETED', result.stdout)

    def test_nonzero_native_exit_still_fails_build(self):
        result = self.invoke(7)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('NATIVE_COMPLETED', result.stdout)
        self.assertIn('exited with code 7', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
