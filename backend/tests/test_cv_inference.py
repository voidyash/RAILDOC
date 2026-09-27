"""Smoke tests for the YOLO26 inference layer (app/cv/inference.py).

These exercise the real trained weights, so the model-dependent cases skip
whenever the artifacts are absent (fresh clone, CI without the models/ mount).
"""

import numpy as np
import pytest

from app.cv import inference as inf

_WEIGHT = inf.ModelRegistry._best_weights(inf.RAILDOC_DET_DIR)

requires_detector = pytest.mark.skipif(
    _WEIGHT is None, reason="unified detector weights not present"
)


@pytest.fixture(scope="module")
def image():
    """A synthetic frame — content-independent, so tests never need the dataset."""
    return np.zeros((640, 640, 3), dtype=np.uint8)


class TestModelLoading:

    @requires_detector
    def test_unified_detector_loads(self):
        assert inf.registry.get_detector() is not None

    def test_status_reports_detector(self):
        status = inf.registry.status()
        assert status["raildoc_detector"]["available"] is (_WEIGHT is not None)
        assert status["raildoc_detector"]["kind"] == "yolo26n-det"


class TestYolo26Inference:

    @requires_detector
    def test_detector_reports_yolo26(self, image):
        result = inf.run_inference(image, "track", draw=False)
        assert result.asset_type == "track"
        assert result.model_info["kind"] == "yolo26n-det"
        assert result.model_info["model_available"] is True

    @requires_detector
    def test_uses_nms_free_end_to_end_head(self, image):
        """nms=False selects YOLO26's one-to-one head: inference must still
        yield plain boxes (capped at 300) for the API layer to consume."""
        model = inf.registry.get_detector()
        result = model.predict(image, imgsz=640, conf=0.25, nms=False, verbose=False)[0]

        assert result.boxes is not None
        assert len(result.boxes) <= 300

    @requires_detector
    def test_detection_boxes_are_valid_xyxy(self):
        """Whatever the head emits must survive conversion to Detection.bbox."""
        img = np.random.default_rng(0).integers(0, 255, (640, 640, 3), dtype=np.uint8)
        result = inf.run_inference_auto(img, draw=True)

        for d in result.detections:
            x1, y1, x2, y2 = d.bbox
            assert all(isinstance(v, int) for v in d.bbox)
            assert x2 > x1 and y2 > y1
            assert d.asset_type in ("track", "light_pole")
            assert d.confidence >= inf.DETECTION_THRESHOLD

    @requires_detector
    def test_asset_type_filters_classes(self):
        """run_inference(track) must never return light_pole detections."""
        img = np.random.default_rng(1).integers(0, 255, (640, 640, 3), dtype=np.uint8)
        result = inf.run_inference(img, "light_pole", draw=False)
        for d in result.detections:
            assert d.asset_type == "light_pole"

    def test_unsupported_asset_type(self, image):
        with pytest.raises(ValueError):
            inf.run_inference(image, "signal", draw=False)


class TestModelMetadata:

    def test_metrics_report_yolo26_base_model(self):
        metrics = inf.read_model_metrics()
        configs = {
            key: (info.get("config") or {}).get("base_model")
            for key, info in metrics.items()
        }
        if not any(configs.values()):
            pytest.skip("no args.yaml training configs available")

        for key, base_model in configs.items():
            if base_model is not None:
                assert base_model.startswith("yolo26"), f"{key} trained from {base_model}"

    @requires_detector
    def test_detector_metrics_are_parsed(self):
        metrics = inf.read_model_metrics()
        assert metrics["raildoc_detector"]["metrics"]["mAP50"] is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
