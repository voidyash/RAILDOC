"""CV inference layer for the Detection Agent.

One locally-trained unified detector (see app/cv/train_detector.py):

  Rail infrastructure detector (YOLO26n-det)
  - Two classes from RAILDOC_02.yolo26: light_pole, tracks_fault
  - Real bounding boxes from detection, via the NMS-free end-to-end head
  - The same weights serve both asset types: results are filtered per class

It degrades gracefully when weights are missing: the registry reports
`model_available=False` and the API surfaces a clear message instead of
crashing, so the rest of the pipeline stays demo-able before training
finishes.
"""

from __future__ import annotations

import base64
import io
import threading
import uuid
from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Optional

import numpy as np

# Models live at <project>/models by default. When the backend runs from a
# different layout (e.g. Docker: app code at /app, models mounted elsewhere),
# set RAILDOC_MODEL_DIR to the directory containing
#   raildoc_detection/raildoc_det/weights/best.pt
_DEFAULT_ROOT = Path(__file__).resolve().parents[3]
ROOT = Path(os.getenv("RAILDOC_MODEL_DIR", str(_DEFAULT_ROOT)))
if not (ROOT / "models").exists():
    # env var may point directly at the models dir itself
    ROOT = Path(os.getenv("RAILDOC_MODEL_DIR", str(_DEFAULT_ROOT / "models")))

RAILDOC_DET_DIR = (
    ROOT / "models" / "raildoc_detection" / "raildoc_det"
    if (ROOT / "models").exists()
    else ROOT / "raildoc_detection" / "raildoc_det"
)

# Confidence (0-1) above which a detection is reported at all.
DETECTION_THRESHOLD = 0.25

# Severity bands over the model confidence (defect classes).
SEVERITY_BANDS = [
    (0.90, "critical"),
    (0.75, "high"),
]

# Model class name -> (asset_type, defect_type) used downstream.
_CLASS_MAP = {
    "light_pole": ("light_pole", "light_pole"),
    "tracks_fault": ("track", "track_defect"),
}


@dataclass
class Detection:
    """One localized defect/asset finding on an image."""

    label: str
    confidence: float
    bbox: list[int]                      # xyxy pixels
    severity: str
    defect_type: str
    asset_type: str


@dataclass
class InferenceResult:
    asset_type: str                      # 'track' | 'light_pole' | 'auto'
    is_defective: bool
    detections: list[Detection] = field(default_factory=list)
    annotated_image_b64: Optional[str] = None
    model_info: dict = field(default_factory=dict)


class ModelRegistry:
    """Lazy-loads and caches the unified YOLO detector."""

    def __init__(self) -> None:
        self._det_model = None
        self._load_errors: dict[str, str] = {}
        # The lazy load must be race-free (first hits can arrive from both
        # the threadpool and the event loop), and ultralytics' shared
        # predictor is not thread-safe — concurrent model.predict calls
        # corrupt each other's state, so inference is serialised.
        self._load_lock = threading.Lock()
        self.predict_lock = threading.Lock()

    @staticmethod
    def _best_weights(dir_path: Path) -> Optional[Path]:
        """Prefer best.pt, fall back to last.pt, then any *.pt in the dir.
        Ultralytics saves under <dir>/weights/, so that is checked too."""
        candidates = [dir_path, dir_path / "weights"]
        for base in candidates:
            if not base.exists():
                continue
            for name in ("best.pt", "last.pt"):
                p = base / name
                if p.exists():
                    return p
            pts = sorted(base.glob("*.pt"))
            if pts:
                return pts[0]
        return None

    def get_detector(self):
        if self._det_model is None:
            with self._load_lock:
                if self._det_model is None:
                    weights = self._best_weights(RAILDOC_DET_DIR)
                    if weights is None:
                        self._load_errors["detector"] = f"no weights in {RAILDOC_DET_DIR}"
                        return None
                    try:
                        from ultralytics import YOLO
                        self._det_model = YOLO(str(weights))
                    except Exception as e:  # pragma: no cover
                        self._load_errors["detector"] = str(e)
                        return None
        return self._det_model

    def status(self) -> dict:
        return {
            "raildoc_detector": self._status_for("detector", RAILDOC_DET_DIR),
        }

    def _status_for(self, key: str, dir_path: Path) -> dict:
        return {
            "available": self.get_detector() is not None,
            "kind": "yolo26n-det",
            "weights_dir": str(dir_path),
            "error": self._load_errors.get(key),
        }


registry = ModelRegistry()


# Architecture reported when the training artifacts are missing (fresh
# clone): the API/UI should still be able to name the kind.
_ARCH_BY_TASK = {
    "detect": "yolo26n-det",
}


def read_model_metrics() -> dict:
    """Parse training artifacts (results.csv + args.yaml) for the detector.

    Returns: metric summary, training config, sample predictions
    availability. Safe against missing/partial artifacts.
    """
    out: dict[str, dict] = {}

    for key, dir_path, task in (
        ("raildoc_detector", RAILDOC_DET_DIR, "detect"),
    ):
        info: dict = {"weights_dir": str(dir_path), "task": task}

        csv_path = dir_path / "results.csv"
        if csv_path.exists():
            try:
                lines = csv_path.read_text().strip().splitlines()
                if len(lines) >= 2:
                    header = [h.strip() for h in lines[0].split(",")]
                    rows = [dict(zip(header, [c.strip() for c in ln.split(",")]))
                            for ln in lines[1:] if ln.strip()]
                    # detect: report last-epoch metrics (standard YOLO
                    # practice) plus best mAP50 across training
                    last = rows[-1]
                    best_map = max(float(r.get("metrics/mAP50(B)") or 0) for r in rows)
                    info["epochs_trained"] = len(rows)
                    info["metrics"] = {
                        "mAP50": _f(last.get("metrics/mAP50(B)")) or round(best_map, 4),
                        "mAP50_95": _f(last.get("metrics/mAP50-95(B)")),
                        "precision": _f(last.get("metrics/precision(B)")),
                        "recall": _f(last.get("metrics/recall(B)")),
                    }
            except Exception as e:  # malformed csv — skip metrics
                info["metrics_error"] = str(e)

        args_path = dir_path / "args.yaml"
        if args_path.exists():
            try:
                import yaml
                cfg = yaml.safe_load(args_path.read_text()) or {}
                info["config"] = {
                    "base_model": cfg.get("model"),
                    "epochs": cfg.get("epochs"),
                    "imgsz": cfg.get("imgsz"),
                    "dataset": Path(str(cfg.get("data", ""))).name,
                }
            except Exception:
                pass
        else:
            # No training run here (fresh clone with weights only): fall back
            # to the known architecture for this task.
            info["config"] = {"base_model": _ARCH_BY_TASK.get(task)}

        info["artifacts"] = {
            "results_png": (dir_path / "results.png").exists(),
            "confusion_matrix": (dir_path / "confusion_matrix.png").exists(),
            "val_predictions": any(dir_path.glob("val_batch*_pred.jpg")),
        }
        info["available"] = registry.get_detector() is not None
        out[key] = info

    return out


def _f(v) -> Optional[float]:
    try:
        return round(float(v), 4) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _severity_for(confidence: float) -> str:
    for floor, name in SEVERITY_BANDS:
        if confidence >= floor:
            return name
    return "medium"


def _to_b64(rgb_array: np.ndarray) -> str:
    from PIL import Image

    buf = io.BytesIO()
    Image.fromarray(rgb_array).save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _detect(image: np.ndarray, draw: bool, wanted: Optional[set[str]]) -> InferenceResult:
    """Unified detection. `wanted` is an optional set of class names to keep
    (None keeps everything — used by the sample-prediction screen)."""
    import cv2
    from ultralytics.utils.plotting import Annotator

    model = registry.get_detector()
    if model is None:
        raise RuntimeError(registry._load_errors.get("detector", "detector model unavailable"))

    # YOLO26 has a dual-head architecture. The default one-to-many head needs
    # NMS post-processing; nms=False selects the native end-to-end (one-to-one)
    # head, which emits the final boxes directly. Both heads are populated on
    # `result`, so the boxing code below is unchanged either way.
    with registry.predict_lock:
        result = model.predict(image, imgsz=640, conf=DETECTION_THRESHOLD, nms=False, verbose=False)[0]
    names = result.names

    detections: list[Detection] = []
    boxes = result.boxes
    for i in range(len(boxes)):
        cls_id = int(boxes.cls[i].item())
        conf = float(boxes.conf[i].item())
        cls_name = str(names.get(cls_id, cls_id)).strip().lower()
        if wanted is not None and cls_name not in wanted:
            continue
        asset_type, defect_type = _CLASS_MAP.get(cls_name, (cls_name, cls_name))
        xyxy = [int(v) for v in boxes.xyxy[i].tolist()]
        if asset_type == "track":
            severity = _severity_for(conf)
        else:
            severity = "medium" if conf < 0.75 else "high"
        detections.append(Detection(
            label=str(names.get(cls_id, cls_id)),
            confidence=round(conf, 4),
            bbox=xyxy,
            severity=severity,
            defect_type=defect_type,
            asset_type=asset_type,
        ))

    annotated_b64 = None
    if draw and detections:
        annotator = Annotator(cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
        for d in detections:
            # Label shows the class name only: confidence stays in the
            # Detection payload/app state but must not be rendered on the
            # maintenance-facing imagery.
            annotator.box_label(
                tuple(d.bbox),
                d.label,
                color=(0, 0, 255) if d.asset_type == "track" else (255, 128, 0),
            )
        annotated_b64 = _to_b64(cv2.cvtColor(annotator.result(), cv2.COLOR_BGR2RGB))

    return InferenceResult(
        asset_type="auto" if wanted is None else next(iter(wanted)).replace("tracks_fault", "track").replace("light_pole", "light_pole"),
        is_defective=len(detections) > 0,
        detections=detections,
        annotated_image_b64=annotated_b64,
        model_info={"kind": "yolo26n-det", "classes": names, "model_available": True},
    )


def run_inference(image: np.ndarray, asset_type: str, draw: bool = True) -> InferenceResult:
    """Entry point used by the API layer. Filters detections per asset type."""
    wanted = {
        "track": {"tracks_fault"},
        "light_pole": {"light_pole"},
    }.get(asset_type)
    if wanted is None:
        raise ValueError(f"unsupported asset_type: {asset_type}")
    return _detect(image, draw, wanted)


def run_inference_auto(image: np.ndarray, draw: bool = True) -> InferenceResult:
    """Detect every class (sample-prediction screen / mixed imagery)."""
    return _detect(image, draw, None)


def make_asset_id(asset_type: str) -> str:
    return f"{asset_type.upper().replace('_', '-')}-{uuid.uuid4().hex[:6].upper()}"
