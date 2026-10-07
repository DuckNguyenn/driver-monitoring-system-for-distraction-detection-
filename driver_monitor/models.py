"""One crop/class-probability interface for PyTorch, ONNX and RKNN Lite2."""
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_manifest(path):
    path = Path(path).resolve()
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported model manifest version")
    for name, expected in (("eye", {"closed", "open"}), ("yawn", {"no_yawn", "yawn"})):
        spec = manifest["classifiers"][name]
        labels = spec["classes"]
        if len(labels) != 2 or {n.casefold() for n in labels} != expected:
            raise ValueError(f"invalid {name} classes: {labels}")
        p = spec["preprocessing"]
        if p["color"] != "RGB" or p["resize"] != "shorter_center_crop" or p["interpolation"] != "bilinear":
            raise ValueError("unsupported preprocessing; export a compatible manifest")
        if spec["input_size"] <= 0 or p["resize_shorter"] < spec["input_size"]:
            raise ValueError("invalid input/resize size")
        if len(p["mean"]) != 3 or len(p["std"]) != 3 or any(s <= 0 for s in p["std"]):
            raise ValueError("invalid normalization")
        if spec["output"] not in ("probabilities", "logits"):
            raise ValueError("unsupported classifier output")
    return manifest


def artifact_path(manifest_path, artifact):
    path = (Path(manifest_path).resolve().parent / artifact["file"]).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Model missing: {path}; run fetch-models/export/convert first")
    expected = artifact.get("sha256")
    if not expected or sha256(path) != expected:
        raise ValueError(f"Model checksum mismatch: {path}")
    return path


def prepare_rgb(crop, spec):
    """PIL resize/center crop matching torchvision's classification transforms."""
    if crop is None or crop.size == 0 or crop.ndim != 3 or crop.shape[2] != 3 or crop.dtype != np.uint8:
        raise ValueError("classifier requires a nonempty BGR uint8 crop")
    image = Image.fromarray(crop[:, :, ::-1])
    w, h = image.size
    shorter = spec["preprocessing"]["resize_shorter"]
    if w <= h:
        size = (shorter, int(shorter * h / w))
    else:
        size = (int(shorter * w / h), shorter)
    image = image.resize(size, Image.Resampling.BILINEAR)
    target = spec["input_size"]
    left, top = round((size[0] - target) / 2), round((size[1] - target) / 2)
    return np.array(image.crop((left, top, left + target, top + target)), dtype=np.uint8)


def prepare_tensor(rgb, spec):
    p = spec["preprocessing"]
    data = rgb.astype(np.float32) / 255.0
    data = (data - np.asarray(p["mean"], np.float32)) / np.asarray(p["std"], np.float32)
    return np.ascontiguousarray(data.transpose(2, 0, 1)[None])


class Classifier:
    def __init__(self, manifest_path, name, backend, threads=2):
        self.backend = backend
        self.spec = read_manifest(manifest_path)["classifiers"][name]
        artifact = self.spec["artifacts"].get(backend)
        if artifact is None:
            raise ValueError(f"No {backend} artifact for {name}; export/convert it first")
        path = artifact_path(manifest_path, artifact)
        if backend == "torch":
            import os
            from .config import ROOT
            cache = ROOT / ".cache/ultralytics"
            cache.mkdir(parents=True, exist_ok=True)
            os.environ.setdefault("YOLO_CONFIG_DIR", str(cache))
            mpl = ROOT / ".cache/matplotlib"
            mpl.mkdir(parents=True, exist_ok=True)
            os.environ.setdefault("MPLCONFIGDIR", str(mpl))
            import torch
            from ultralytics import YOLO
            torch.set_num_threads(threads)
            loaded = YOLO(str(path))
            if loaded.task != "classify":
                raise ValueError("checkpoint is not a classification model")
            actual = [loaded.names[i] for i in range(len(loaded.names))]
            if actual != self.spec["classes"]:
                raise ValueError("checkpoint labels differ from manifest")
            self.model = loaded.model.cpu().float().eval()
        elif backend == "onnx":
            import onnxruntime as ort
            options = ort.SessionOptions()
            options.intra_op_num_threads = threads
            options.inter_op_num_threads = 1
            self.model = ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])
            self.input_name = self.model.get_inputs()[0].name
            if self.model.get_inputs()[0].shape != [1, 3, self.spec["input_size"], self.spec["input_size"]]:
                raise ValueError("ONNX input shape differs from manifest")
        elif backend == "rknn":
            import platform
            import importlib.metadata
            from rknnlite.api import RKNNLite
            if platform.machine().lower() not in ("aarch64", "arm64"):
                raise RuntimeError("RKNN Lite2 inference requires the ARM64 Radxa board")
            if artifact.get("target_platform") != "rk3576":
                raise ValueError("ROCK 4D requires an rk3576 artifact")
            if importlib.metadata.version("rknn-toolkit-lite2") != artifact.get("toolkit_version"):
                raise RuntimeError("RKNN Lite2 version differs from the model's Toolkit2 version")
            self.model = RKNNLite()
            try:
                if self.model.load_rknn(str(path)) != 0 or self.model.init_runtime() != 0:
                    raise RuntimeError("RKNN initialization failed; inspect NPU driver/runtime versions")
            except Exception:
                self.model.release()
                raise
        else:
            raise ValueError(f"unknown backend {backend}")

    def predict(self, crop):
        rgb = prepare_rgb(crop, self.spec)
        if self.backend == "torch":
            import torch
            with torch.inference_mode():
                output = self.model(torch.from_numpy(prepare_tensor(rgb, self.spec)))
            if isinstance(output, tuple):
                output = output[0]
            output = output.detach().cpu().numpy()
        elif self.backend == "onnx":
            output = self.model.run(None, {self.input_name: prepare_tensor(rgb, self.spec)})[0]
        else:
            # RKNN config embeds mean/std normalization. Do not divide by 255 twice.
            output = self.model.inference(inputs=[rgb[None]], data_format=["nhwc"])
            if output is None:
                raise RuntimeError("RKNN inference returned no result")
            output = output[0]
        values = np.asarray(output, dtype=np.float64).reshape(-1)
        if values.size != len(self.spec["classes"]) or not np.isfinite(values).all():
            raise ValueError("invalid classifier output shape/values")
        if self.spec["output"] == "logits":
            values = np.exp(values - values.max())
        elif np.any(values < -0.001) or abs(values.sum() - 1) > 0.02:
            raise ValueError("expected probabilities, not logits")
        values = np.maximum(values, 0)
        if values.sum() <= 0:
            raise ValueError("empty probability distribution")
        values /= values.sum()
        return dict(zip(self.spec["classes"], map(float, values)))

    def close(self):
        if self.backend == "rknn":
            self.model.release()
