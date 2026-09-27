"""Train the unified rail-infrastructure detector (YOLO26n).

One detection model covers both asset classes from RAILDOC_02.yolo26:
  0: light_pole
  1: tracks_fault

Replaces the previous two-model setup (track classifier + pole detector).

Requires ultralytics>=8.4.0 (YOLO26 ships in that release).

Fresh train (v1 recipe):
    python -m app.cv.train_detector

Accuracy fine-tune (v2 recipe): start from the v1 weights, raise resolution
to 960px (small objects — track faults, distant poles — benefit most), lower
LR, stronger geometric/color augmentation for recall:
    python -m app.cv.train_detector \
        --weights ../models/raildoc_detection/raildoc_det/weights/best.pt \
        --imgsz 960 --epochs 40 --batch 8 --lr0 0.001 --name raildoc_det_v2
"""

import argparse
from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[3]
DATA_YAML = ROOT / "RAILDOC_02.yolo26" / "data.yaml"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", default="yolo26n.pt",
                    help="starting weights: pretrained name or a best.pt to fine-tune")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr0", type=float, default=0.01)
    ap.add_argument("--name", default="raildoc_det")
    ap.add_argument("--patience", type=int, default=15)
    args = ap.parse_args()

    model = YOLO(args.weights)
    model.train(
        data=str(DATA_YAML),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=0,
        name=args.name,
        # absolute, so runs land in <project>/models where inference looks
        project=str(ROOT / "models" / "raildoc_detection"),
        exist_ok=True,
        patience=args.patience,
        lr0=args.lr0,
        # Stronger augmentation for recall on a small dataset.
        degrees=10.0,          # slight rotation
        translate=0.15,
        scale=0.6,
        fliplr=0.5,
        mosaic=1.0,
        mixup=0.15,            # mild mixing regularizes small datasets
        close_mosaic=15,       # disable mosaic for the last epochs
        # Detection batches are large enough that spawned dataloader workers
        # die mid-epoch on Windows ("DataLoader worker exited unexpectedly").
        # Raise this if your machine handles the batches comfortably.
        workers=0,
    )
    print("TRAIN_DONE")


if __name__ == "__main__":
    main()
