import unittest
from unittest.mock import patch
from driver_monitor.__main__ import main


class CliTests(unittest.TestCase):
    def test_run_retains_its_default_model_profile(self):
        with patch("driver_monitor.runtime.run") as run:
            self.assertEqual(main(["run", "--max-frames", "1"]), 0)
        self.assertNotIn("yawn_camera_refined", str(run.call_args.args[0].manifest))

    def test_serve_uses_pc_profile_headless_and_port_8765(self):
        with patch("driver_monitor.dashboard_server.serve") as serve:
            result = main(["serve", "--source", "1", "--duration", "10"])
        self.assertEqual(result, 0)
        config = serve.call_args.args[0]
        self.assertTrue(config.headless)
        self.assertIn("yawn_camera_refined", str(config.manifest))
        self.assertEqual(serve.call_args.kwargs["port"], 8765)
        self.assertEqual(serve.call_args.kwargs["preview_fps"], 15)
        self.assertEqual(serve.call_args.args[1], "1")
