"""Export existing classifiers and produce the authoritative model contract."""
import argparse
import copy
import importlib.metadata
import json
import os
from pathlib import Path

from .config import ROOT
from .models import read_manifest, sha256


def export_models(output, eye_path, yawn_path):
    (ROOT / ".cache/ultralytics").mkdir(parents=True, exist_ok=True)
    (ROOT / ".cache/matplotlib").mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".cache/ultralytics"))
    os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache/matplotlib"))
    import torch
    from ultralytics import YOLO
    from ultralytics.data.augment import classify_transforms
    torch.set_num_threads(2)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    detector = json.loads((output / "yunet.source.json").read_text(encoding="utf-8"))
    manifest = {"schema_version": 1, "target_platform": "rk3576", "detector": detector, "classifiers": {},
                "export_versions": {name: importlib.metadata.version(name) for name in ("torch", "torchvision", "ultralytics", "onnx")},
                "deployment_validation": "pending Radxa hardware and annotated cabin videos"}
    for name, source in (("eye", eye_path), ("yawn", yawn_path)):
        source = Path(source).resolve()
        loaded = YOLO(str(source))
        if loaded.task != "classify":
            raise ValueError(f"{source} is not a classification checkpoint")
        labels = [loaded.names[i] for i in range(len(loaded.names))]
        expected = {"closed", "open"} if name == "eye" else {"no_yawn", "yawn"}
        if {label.casefold() for label in labels} != expected:
            raise ValueError(f"wrong classes for {name}: {labels}")
        size = int(loaded.ckpt.get("train_args", {}).get("imgsz", 224))
        crop_fraction = float(loaded.ckpt.get("train_args", {}).get("crop_fraction", 1.0))
        transforms = classify_transforms(size=size, crop_fraction=crop_fraction)
        resize, center, tensor, normalize = transforms.transforms
        if resize.interpolation.name != "BILINEAR" or list(center.size) != [size, size]:
            raise ValueError(f"unsupported classification transforms: {transforms}")
        shorter = resize.size if isinstance(resize.size, int) else resize.size[0]
        model = copy.deepcopy(loaded.model).cpu().float().eval()
        model.model[-1].export = True
        target = output / f"best_{name}.onnx"
        torch.onnx.export(model, torch.zeros(1, 3, size, size), str(target), input_names=["images"],
                          output_names=["probabilities"], opset_version=12, do_constant_folding=True)
        import onnx
        onnx.checker.check_model(onnx.load(target))
        manifest["classifiers"][name] = {
            "classes": labels, "input_size": size, "output": "probabilities",
            "preprocessing": {"color": "RGB", "resize": "shorter_center_crop", "resize_shorter": shorter,
                              "interpolation": "bilinear", "mean": list(map(float, normalize.mean)), "std": list(map(float, normalize.std))},
            "reference_transform": str(transforms), "checkpoint_ultralytics": loaded.ckpt.get("version"),
            "artifacts": {"torch": {"file": os.path.relpath(source, output).replace(os.sep, "/"), "sha256": sha256(source)},
                          "onnx": {"file": target.name, "sha256": sha256(target)}}}
    path = output / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    read_manifest(path)
    print(f"Exported classifiers and manifest: {path}")
    return path


def convert_models(manifest_path, quantization=None):
    import platform
    if platform.system() != "Linux":
        raise RuntimeError("Run RKNN-Toolkit2 conversion on Linux (WSL2 or Radxa)")
    if importlib.metadata.version("rknn-toolkit2") != "2.3.2":
        raise RuntimeError("Use the pinned RKNN-Toolkit2 2.3.2 conversion environment")
    from rknn.api import RKNN
    from .models import artifact_path
    path = Path(manifest_path).resolve()
    manifest = read_manifest(path)
    built = {}
    for name, spec in manifest["classifiers"].items():
        source = artifact_path(path, spec["artifacts"]["onnx"])
        config = spec["preprocessing"]
        calibration = None
        if quantization:
            # Calibration manifests are generated only from train crops by prepare-dataset.
            calibration_path = Path(quantization) / f"{name}.calibration.json"
            entries = json.loads(calibration_path.read_text(encoding="utf-8"))
            if len(entries) < 200 or any(e["split"] != "train" or e["kind"] != name for e in entries):
                raise ValueError("INT8 requires >=200 matching train-only crop records per classifier")
            calibration = path.parent / f"{name}.calibration.txt"
            lines = []
            for entry in entries:
                image = (calibration_path.parent / entry["file"]).resolve()
                if not image.is_file() or sha256(image) != entry["sha256"]:
                    raise ValueError("calibration crop missing/checksum mismatch")
                lines.append(str(image))
            calibration.write_text("\n".join(lines) + "\n", encoding="utf-8")
        rknn = RKNN(verbose=False)
        try:
            rknn.config(target_platform="rk3576", mean_values=[[v * 255 for v in config["mean"]]],
                        std_values=[[v * 255 for v in config["std"]]])
            if rknn.load_onnx(model=str(source)) != 0:
                raise RuntimeError(f"RKNN load failed: {name}")
            if rknn.build(do_quantization=bool(calibration), dataset=str(calibration) if calibration else None) != 0:
                raise RuntimeError(f"RKNN build failed: {name}")
            target = path.parent / f"best_{name}.rknn"
            if rknn.export_rknn(str(target)) != 0:
                raise RuntimeError(f"RKNN export failed: {name}")
            built[name] = {"file": target.name, "sha256": sha256(target), "target_platform": "rk3576",
                           "quantization": "int8" if calibration else "none",
                           "toolkit_version": importlib.metadata.version("rknn-toolkit2")}
        finally:
            rknn.release()
    for name, artifact in built.items():
        manifest["classifiers"][name]["artifacts"]["rknn"] = artifact
    host = {"system": platform.system(), "machine": platform.machine(), "python": platform.python_version(),
            "versions": {name: importlib.metadata.version(name) for name in ("torch", "onnx", "rknn-toolkit2")}}
    manifest["conversion_host"] = host
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    report_dir = path.parent.parent / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "rknn_conversion.json").write_text(json.dumps({"target_platform": "rk3576", "host": host,
                "models": built, "conversion_passed": True, "npu_inference_tested": False,
                "accuracy_tested": False, "physical_board_tested": False}, indent=2), encoding="utf-8")
    print(f"Converted both models for rk3576: {path}")


def export_main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(ROOT / "models"))
    parser.add_argument("--eye", default=str(ROOT / "camera_classical/best_eye.pt"))
    parser.add_argument("--yawn", default=str(ROOT / "camera_classical/best_yawn.pt"))
    args = parser.parse_args()
    export_models(args.output, args.eye, args.yawn)


def convert_main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=str(ROOT / "models/manifest.json"))
    parser.add_argument("--calibration", default=None)
    args = parser.parse_args()
    convert_models(args.manifest, args.calibration)
