"""Reproduce the architecture inventory from the deployed model artifacts."""
from __future__ import annotations

import hashlib
import json
import math
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for variable, directory in (("YOLO_CONFIG_DIR", ".cache/ultralytics"),
                            ("MPLCONFIGDIR", ".cache/matplotlib")):
    path = ROOT / directory
    path.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault(variable, str(path))


def artifact(path: Path) -> dict:
    return {"file": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def tensor_shape(value):
    if isinstance(value, (tuple, list)):
        return [tensor_shape(item) for item in value]
    if hasattr(value, "shape"):
        return list(value.shape)
    return str(type(value))


def inspect_onnx(path: Path) -> dict:
    import onnx
    from onnx import TensorProto, helper

    graph_model = onnx.load(path)
    onnx.checker.check_model(graph_model)
    graph = graph_model.graph
    weights = {item.name: item for item in graph.initializer}
    shape_model = onnx.shape_inference.infer_shapes(graph_model)
    shapes = {item.name: [dim.dim_param if dim.dim_param else dim.dim_value
                          for dim in item.type.tensor_type.shape.dim]
              for item in (*shape_model.graph.input, *shape_model.graph.value_info, *shape_model.graph.output)}

    def interface(item):
        tensor = item.type.tensor_type
        return {"name": item.name, "dtype": TensorProto.DataType.Name(tensor.elem_type),
                "shape": [dim.dim_param if dim.dim_param else dim.dim_value
                          for dim in tensor.shape.dim]}

    convs = []
    learned_names = set()
    for node in graph.node:
        if node.op_type in ("Conv", "Gemm"):
            learned_names.update(name for name in node.input[1:] if name in weights)
        if node.op_type != "Conv":
            continue
        attributes = {a.name: helper.get_attribute_value(a) for a in node.attribute}
        weight = weights.get(node.input[1])
        convs.append({"name": node.name, "input": list(node.input), "output": list(node.output),
                      "input_shape": shapes.get(node.input[0]), "output_shape": shapes.get(node.output[0]),
                      "weight_shape": list(weight.dims) if weight is not None else None,
                      "group": attributes.get("group", 1), "strides": attributes.get("strides", [1, 1]),
                      "kernel_shape": attributes.get("kernel_shape"), "pads": attributes.get("pads")})
    return {**artifact(path), "opsets": {op.domain or "ai.onnx": op.version for op in graph_model.opset_import},
            "inputs": [interface(item) for item in graph.input],
            "outputs": [interface(item) for item in graph.output],
            "node_count": len(graph.node), "operator_counts": dict(sorted(Counter(n.op_type for n in graph.node).items())),
            "initializer_elements": sum(math.prod(item.dims) for item in graph.initializer),
            "conv_gemm_weight_bias_elements": sum(math.prod(weights[name].dims) for name in learned_names),
            "initializer_count": len(graph.initializer),
            "initializer_types": dict(Counter(TensorProto.DataType.Name(item.data_type) for item in graph.initializer)),
            "convolutions": convs}


def inspect_classifier(path: Path, size: int) -> dict:
    import torch
    from ultralytics import YOLO

    loaded = YOLO(str(path))
    model = loaded.model.cpu().float().eval()
    # Match the probability-only contract used by this project's ONNX export.
    model.model[-1].export = True
    stages, handles, operations = [], [], []

    def operation_hook(module, inputs, output):
        if isinstance(module, torch.nn.Conv2d):
            count = (int(output.numel()) * module.in_channels // module.groups
                     * math.prod(module.kernel_size))
        else:
            count = int(output.numel()) * module.in_features
        operations.append(count)

    def stage_hook(index):
        def capture(module, inputs, output):
            entry = {"index": index, "type": type(module).__name__,
                     "input_shape": tensor_shape(inputs[0]), "output_shape": tensor_shape(output),
                     "parameters": sum(p.numel() for p in module.parameters())}
            conv = getattr(module, "conv", None)
            if isinstance(conv, torch.nn.Conv2d):
                entry["conv"] = {"in_channels": conv.in_channels, "out_channels": conv.out_channels,
                                 "kernel": list(conv.kernel_size), "stride": list(conv.stride),
                                 "groups": conv.groups, "bias": conv.bias is not None,
                                 "activation": type(module.act).__name__,
                                 "batch_norm_eps": module.bn.eps}
            if type(module).__name__ == "C2f":
                entry["c2f"] = {"hidden_channels": module.c, "bottlenecks": len(module.m),
                                "shortcut": [m.add for m in module.m],
                                "bottleneck_expansion": [m.cv1.conv.out_channels / m.cv2.conv.out_channels for m in module.m]}
            if type(module).__name__ == "Classify":
                entry["head"] = {"conv_out_channels": module.conv.conv.out_channels,
                                 "pool": type(module.pool).__name__,
                                 "pool_output_size": module.pool.output_size,
                                 "dropout_probability": module.drop.p,
                                 "linear_in_features": module.linear.in_features,
                                 "linear_out_features": module.linear.out_features}
            stages.append(entry)
        return capture

    for index, module in enumerate(model.model):
        handles.append(module.register_forward_hook(stage_hook(index)))
    for module in model.modules():
        if isinstance(module, (torch.nn.Conv2d, torch.nn.Linear)):
            handles.append(module.register_forward_hook(operation_hook))
    try:
        with torch.inference_mode():
            output = model(torch.zeros(1, 3, size, size))
    finally:
        for handle in handles:
            handle.remove()
    args = loaded.ckpt.get("train_args", {})
    fields = ("task", "model", "imgsz", "epochs", "batch", "optimizer", "lr0",
              "dropout", "pretrained", "seed", "crop_fraction")
    return {**artifact(path), "task": loaded.task, "labels": loaded.names,
            "checkpoint_ultralytics": loaded.ckpt.get("version"),
            "checkpoint_epoch": loaded.ckpt.get("epoch"),
            "checkpoint_date": loaded.ckpt.get("date"),
            "checkpoint_train_args": {key: args[key] for key in fields if key in args},
            "yaml": model.yaml, "stages": stages,
            "total_parameters": sum(p.numel() for p in model.parameters()),
            "parameter_dtype": str(next(model.parameters()).dtype),
            "conv_linear_macs_at_batch1": sum(operations),
            "macs_definition": "Conv2d and Linear multiply-accumulates only; excludes activation, BN, pooling and Softmax",
            "output_shape": tensor_shape(output),
            "source_files": {type(m).__name__: __import__("inspect").getfile(type(m))
                             for m in model.model}}


def main():
    import torch
    import ultralytics
    import onnx

    torch.set_num_threads(2)
    manifest_path = ROOT / "models/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    inventory = {"generated_at_utc": datetime.now(timezone.utc).isoformat(),
                 "versions": {"torch": torch.__version__, "ultralytics": ultralytics.__version__, "onnx": onnx.__version__},
                 "manifest": artifact(manifest_path), "classifiers": {}}
    for name, spec in manifest["classifiers"].items():
        result = {"torch": inspect_classifier((manifest_path.parent / spec["artifacts"]["torch"]["file"]).resolve(), spec["input_size"]),
                  "onnx": inspect_onnx(manifest_path.parent / spec["artifacts"]["onnx"]["file"]),
                  "rknn": artifact(manifest_path.parent / spec["artifacts"]["rknn"]["file"])}
        for kind, actual in result.items():
            expected = spec["artifacts"][kind]["sha256"]
            if actual["sha256"] != expected:
                raise ValueError(f"Artifact differs from manifest: {name}/{kind}")
        inventory["classifiers"][name] = result
    detector = manifest["detector"]
    inventory["yunet"] = inspect_onnx(manifest_path.parent / detector["file"])
    if inventory["yunet"]["sha256"] != detector["sha256"]:
        raise ValueError("YuNet differs from manifest")
    import cv2
    import numpy as np
    net = cv2.dnn.readNetFromONNX(str(manifest_path.parent / detector["file"]))
    runtime_size = detector["input_size"]
    net.setInput(cv2.dnn.blobFromImage(np.zeros((runtime_size, runtime_size, 3), np.uint8)))
    names = [item["name"] for item in inventory["yunet"]["outputs"]]
    inventory["yunet"]["opencv_runtime_probe"] = {
        "opencv": cv2.__version__, "input_shape": [1, 3, runtime_size, runtime_size],
        "input_color": "BGR", "input_scale": 1.0,
        "outputs": [{"name": name, "shape": list(value.shape)}
                    for name, value in zip(names, net.forward(names))],
        "probe_image": "all-zero synthetic image; tensor contract only, not accuracy measurement"}
    target = ROOT / "reports/model_architecture_inventory.json"
    target.write_text(json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {target}")
    for name, item in inventory["classifiers"].items():
        print(name, item["torch"]["total_parameters"], "parameters;", item["torch"]["conv_linear_macs_at_batch1"], "MACs")
        for layer in item["torch"]["stages"]:
            print(layer["index"], layer["type"], layer["output_shape"], layer["parameters"], layer.get("c2f", layer.get("head", "")))
    print("YuNet:", inventory["yunet"]["initializer_elements"], "initializer elements;", inventory["yunet"]["operator_counts"])
    print("YuNet I/O:", inventory["yunet"]["inputs"], inventory["yunet"]["outputs"])


if __name__ == "__main__":
    main()
