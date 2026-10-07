"""CLI: camera/video execution, preflight, export and evidence collection."""
import argparse
import json
import sys
from .config import ROOT, load_config


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    commands = {"run", "fetch-models", "export", "convert", "preflight", "evaluate-classifier", "evaluate-session", "evaluate-study", "parity", "prepare-dataset", "train"}
    if not argv or argv[0] not in commands:
        argv.insert(0, "run")
    parser = argparse.ArgumentParser(description="Driver monitor for PC and ROCK 4D")
    sub = parser.add_subparsers(dest="command", required=True)
    runtime = sub.add_parser("run")
    runtime.add_argument("--config", default=str(ROOT / "configs/driver_monitor.yaml"))
    runtime.add_argument("--source", default="0")
    runtime.add_argument("--backend", choices=("torch", "onnx", "rknn"))
    runtime.add_argument("--manifest")
    runtime.add_argument("--log-dir")
    runtime.add_argument("--esp32-port", dest="serial_port")
    runtime.add_argument("--headless", action="store_true", default=None)
    runtime.add_argument("--display", action="store_true")
    runtime.add_argument("--realtime", action="store_true", default=None, help="pace video playback using media timestamps")
    runtime.add_argument("--max-frames", type=int)
    runtime.add_argument("--rotate", dest="rotation_degrees", type=int, choices=(0, 90, 180, 270))
    runtime.add_argument("--duration", type=float, default=0)
    fetch = sub.add_parser("fetch-models")
    fetch.add_argument("--output", default=str(ROOT / "models"))
    export = sub.add_parser("export")
    export.add_argument("--output", default=str(ROOT / "models"))
    export.add_argument("--eye", default=str(ROOT / "camera_classical/best_eye.pt"))
    export.add_argument("--yawn", default=str(ROOT / "camera_classical/best_yawn.pt"))
    convert = sub.add_parser("convert")
    convert.add_argument("--manifest", default=str(ROOT / "models/manifest.json"))
    convert.add_argument("--calibration")
    preflight = sub.add_parser("preflight")
    preflight.add_argument("--config", default=str(ROOT / "configs/driver_monitor.yaml"))
    preflight.add_argument("--output", default=str(ROOT / "reports/preflight.json"))
    preflight.add_argument("--backend", choices=("torch", "onnx", "rknn"))
    for command in ("evaluate-classifier", "parity"):
        p = sub.add_parser(command)
        p.add_argument("--config", default=str(ROOT / "configs/driver_monitor.yaml"))
        p.add_argument("--name", choices=("eye", "yawn"), required=True)
        p.add_argument("--data", required=True)
        p.add_argument("--split", choices=("train", "val", "test"), default="test")
        p.add_argument("--backend", choices=("torch", "onnx", "rknn"), default="onnx")
        p.add_argument("--crop", choices=("original", "face"), default="original")
        p.add_argument("--output", required=True)
        p.add_argument("--limit", type=int, default=0)
        if command == "parity":
            p.add_argument("--reference", choices=("torch", "onnx"), default="torch")
    p = sub.add_parser("evaluate-session")
    p.add_argument("--frames", required=True)
    p.add_argument("--annotations", required=True)
    p.add_argument("--clip-id", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--config", default=str(ROOT / "configs/driver_monitor.yaml"))
    p = sub.add_parser("evaluate-study")
    p.add_argument("--reports", required=True)
    p.add_argument("--annotations", required=True)
    p.add_argument("--output", required=True)
    p = sub.add_parser("prepare-dataset")
    p.add_argument("--annotations", required=True)
    p.add_argument("--videos", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--config", default=str(ROOT / "configs/driver_monitor.yaml"))
    p = sub.add_parser("train")
    p.add_argument("--name", choices=("eye", "yawn"), required=True)
    p.add_argument("--data", required=True)
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--epochs", type=int, default=40)
    p.add_argument("--device", default="cpu")
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            from .runtime import run
            overrides = {k: getattr(args, k) for k in ("backend", "manifest", "log_dir", "serial_port", "headless", "max_frames", "rotation_degrees", "realtime")}
            if args.display:
                overrides["headless"] = False
            if args.duration < 0:
                raise ValueError("duration cannot be negative")
            run(load_config(args.config, **overrides), args.source, args.duration)
        elif args.command == "fetch-models":
            from .assets import fetch_yunet
            print(json.dumps(fetch_yunet(args.output), indent=2))
        elif args.command == "export":
            from .exporting import export_models
            export_models(args.output, args.eye, args.yawn)
        elif args.command == "convert":
            from .exporting import convert_models
            convert_models(args.manifest, args.calibration)
        elif args.command == "preflight":
            from .diagnostics import preflight_report
            preflight_report(load_config(args.config, backend=args.backend), args.output)
        elif args.command in ("evaluate-classifier", "parity"):
            from .evaluation import evaluate_classifier
            evaluate_classifier(load_config(args.config, backend=args.backend), args, compare=args.command == "parity")
        elif args.command == "evaluate-session":
            from .evaluation import evaluate_session
            evaluate_session(args.frames, args.annotations, args.clip_id, args.output, load_config(args.config))
        elif args.command == "evaluate-study":
            from .evaluation import evaluate_study
            evaluate_study(args.reports, args.annotations, args.output)
        elif args.command == "prepare-dataset":
            from .dataset import prepare_dataset
            prepare_dataset(args.annotations, args.videos, args.output, load_config(args.config))
        elif args.command == "train":
            from .dataset import train
            train(args)
        return 0
    except (ValueError, OSError, RuntimeError, ImportError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
