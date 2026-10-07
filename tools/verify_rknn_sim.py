"""SDK graph simulator smoke; explicitly not inference on an exported blob/NPU."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
from rknn.api import RKNN
from driver_monitor.config import Config, ROOT
from driver_monitor.evaluation import image_samples
from driver_monitor.models import Classifier, artifact_path, prepare_rgb, read_manifest

config = Config()
manifest = read_manifest(config.manifest)
report = {"verification": "Toolkit2 graph simulator using same ONNX/config as conversion",
          "exported_rknn_blob_inference_tested": False, "npu_inference_tested": False, "physical_board_tested": False,
          "classifiers": {}}
for name, spec in manifest["classifiers"].items():
    p = spec["preprocessing"]
    model = RKNN(verbose=False)
    reference = Classifier(config.manifest, name, "onnx")
    try:
        model.config(target_platform="rk3576", mean_values=[[v * 255 for v in p["mean"]]], std_values=[[v * 255 for v in p["std"]]])
        if model.load_onnx(model=str(artifact_path(config.manifest, spec["artifacts"]["onnx"]))) or model.build(do_quantization=False) or model.init_runtime():
            raise RuntimeError(f"Simulator initialization failed: {name}")
        counts = {label: 0 for label in spec["classes"]}
        errors, agreement, entries = [], 0, []
        for path, label in image_samples(ROOT / f"kaggle_output/data/{name}_dataset", "test"):
            label = next(c for c in spec["classes"] if c.casefold() == label.casefold())
            if counts[label] >= 10:
                continue
            image = cv2.imread(str(path))
            expected = reference.predict(image)
            output = model.inference(inputs=[prepare_rgb(image, spec)[None]], data_format=["nhwc"])
            if output is None:
                raise RuntimeError("Simulator returned no output")
            values = np.asarray(output[0], np.float64).reshape(-1)
            if values.size != 2 or not np.isfinite(values).all() or np.any(values < 0) or abs(values.sum() - 1) > .02:
                raise ValueError("Invalid simulator probabilities")
            values /= values.sum()
            actual = dict(zip(spec["classes"], map(float, values)))
            error = max(abs(actual[c] - expected[c]) for c in spec["classes"])
            errors.append(error)
            agreement += max(actual, key=actual.get) == max(expected, key=expected.get)
            entries.append({"file": path.name, "truth": label, "onnx": expected, "simulator": actual})
            counts[label] += 1
            if min(counts.values()) == 10:
                break
        passed = len(entries) == 20 and agreement == 20 and max(errors) <= .02
        report["classifiers"][name] = {"samples": len(entries), "label_agreement": agreement / max(len(entries), 1),
                  "maximum_probability_error": max(errors), "passed": passed, "predictions": entries}
        print(f"Simulator {name}: {agreement}/{len(entries)} same labels, maximum probability error={max(errors):.6g}", flush=True)
    finally:
        model.release()
        reference.close()
report["passed"] = all(row["passed"] for row in report["classifiers"].values())
output = ROOT / "reports/rknn_simulator_smoke.json"
output.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(output)
raise SystemExit(0 if report["passed"] else 1)
