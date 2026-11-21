"""Compile the real ESP-IDF protocol core against a fake GPIO/serial sink."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class EspIdfProtocolTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("gcc"), "Native GCC is required for firmware core tests")
    def test_protocol_handles_framing_watchdog_and_uart_faults(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "firmware_idf_test.exe"
            compile_result = subprocess.run([
                shutil.which("gcc"), "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic",
                "-I", str(ROOT / "esp32_buzzer_idf/main"),
                str(ROOT / "tests/firmware_idf_test.c"),
                str(ROOT / "esp32_buzzer_idf/main/buzzer_protocol.c"), "-o", str(executable),
            ], capture_output=True, text=True, timeout=30)
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            run = subprocess.run([str(executable)], capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("ESP-IDF protocol: PASS", run.stdout)


if __name__ == "__main__":
    unittest.main()
