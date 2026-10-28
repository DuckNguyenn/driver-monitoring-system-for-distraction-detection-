import json
import multiprocessing as mp
from pathlib import Path
import queue
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from driver_monitor.config import Config
from driver_monitor.dashboard_server import _worker


def _hung_worker(ready):
    ready.set()
    while True:
        time.sleep(.05)


class ProcessTests(unittest.TestCase):
    def test_occupied_port_fails_before_starting_inference_or_creating_logs(self):
        with tempfile.TemporaryDirectory() as directory, socket.socket() as occupied:
            occupied.bind(('127.0.0.1', 0))
            occupied.listen()
            port = occupied.getsockname()[1]
            logs = Path(directory) / 'logs'
            result = subprocess.run([
                sys.executable, '-m', 'driver_monitor', 'serve',
                '--manifest', str(Path(directory) / 'missing.json'),
                '--log-dir', str(logs), '--host', '127.0.0.1', '--port', str(port),
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10,
                env=dict(os.environ, DRIVER_MONITOR_TOKEN='test-pairing-code-for-process'))
            self.assertEqual(result.returncode, 1)
            self.assertFalse(logs.exists(), 'Port conflict must not start inference or create a session')
            self.assertIn(str(port), result.stderr)
            self.assertIn('Ctrl+C', result.stderr)
            self.assertNotIn('Ma ket noi:', result.stdout)

    def test_hung_worker_ignoring_terminate_is_killed_within_bounded_shutdown(self):
        from driver_monitor.dashboard_server import stop_worker
        context=mp.get_context('spawn');ready=context.Event()
        process=context.Process(target=_hung_worker,args=(ready,))
        process.start()
        class IgnoresTerminate:
            def is_alive(self):return process.is_alive()
            def join(self,timeout):return process.join(timeout)
            def terminate(self):pass  # POSIX handler cannot interrupt hung native inference.
            def kill(self):process.kill()
        try:
            self.assertTrue(ready.wait(5))
            began=time.monotonic()
            stop_worker(IgnoresTerminate(),grace=.1,terminate_grace=.1,kill_grace=1.)
            self.assertFalse(process.is_alive())
            self.assertLess(time.monotonic()-began,2.)
        finally:
            if process.is_alive():process.kill();process.join(2)
    @unittest.skipUnless(os.name == 'nt', 'Windows console signal regression')
    def test_console_break_shuts_api_down_normally_without_orphaning_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with socket.socket() as port_probe:
                port_probe.bind(('127.0.0.1', 0))
                port = port_probe.getsockname()[1]
            process = subprocess.Popen([sys.executable, '-m', 'driver_monitor', 'serve', '--manifest', str(root/'missing.json'),
                '--log-dir', str(root/'logs'), '--host', '127.0.0.1', '--port', str(port)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                env=dict(os.environ, DRIVER_MONITOR_TOKEN='test-pairing-code-for-process'))
            try:
                deadline = time.monotonic() + 8
                while not list((root/'logs').glob('*.summary.json')) and time.monotonic() < deadline:
                    time.sleep(.05)
                self.assertIsNone(process.poll(), 'API must remain available after inference startup error')
                request = urllib.request.Request(f'http://127.0.0.1:{port}/api/v1/health',
                    headers={'Authorization': 'Bearer test-pairing-code-for-process'})
                with urllib.request.urlopen(request, timeout=3) as response:
                    self.assertTrue(json.load(response)['read_only'])
                process.send_signal(signal.CTRL_BREAK_EVENT)
                self.assertEqual(process.wait(10), 0)
            finally:
                if process.poll() is None:
                    process.terminate(); process.wait(4)

    def test_startup_fault_exits_child_and_keeps_original_evidence(self):
        context = mp.get_context('spawn')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            statuses, frames = context.Queue(4), context.Queue(1)
            stop, demand = context.Event(), context.Value('d', 0., lock=False)
            config = Config(manifest=root / 'missing.json', log_dir=root / 'logs')
            process = context.Process(target=_worker, args=(config, '0', 0, statuses, frames, demand, stop, 5))
            process.start()
            process.join(8)
            if process.is_alive():
                process.terminate(); process.join()
                self.fail('Startup fault did not stop inference child')
            values = []
            try:
                while True: values.append(statuses.get(timeout=.2))
            except queue.Empty:
                pass
            statuses.close(); frames.close()
            self.assertEqual(values[-1]['lifecycle'], 'error')
            self.assertFalse(values[-1]['alert'])
            self.assertIn('FileNotFoundError', values[-1]['devices']['models']['error'])
            summary = json.loads(next(config.log_dir.glob('*.summary.json')).read_text())
            self.assertEqual(summary['frames'], 0)
            self.assertIn('FileNotFoundError', summary['fault'])
