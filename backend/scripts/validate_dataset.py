"""Validate the bundled RAILDOC_02.yolo26 annotation dataset.

Checks (all offline — no training, no network):

  * data.yaml parses; its paths, nc and names line up with the folders
  * every image has a label file and vice versa (per split)
  * no unexpected file types in images/ or labels/
  * every image decodes (PIL structural verify) with non-zero size
  * every label line is `class x y w h` with:
      - exactly 5 whitespace-separated fields
      - class id an integer inside [0, nc)
      - all values finite and in [0, 1]
      - w > 0, h > 0
      - the box fits the frame: x±w/2, y±h/2 within [0, 1] (1e-6 slack)
  * exact-duplicate image content inside / across splits (leakage warning)
  * class distribution report per split

Exit code 0 = clean (warnings allowed), 1 = at least one error.

Usage:
    python scripts/validate_dataset.py [--root PATH] [--no-hash]
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections import Counter
from pathlib import Path

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
TOL = 1e-6

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = REPO_ROOT / "RAILDOC_02.yolo26"


def _load_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError:  # PyYAML is a backend dependency; be helpful anyway
        print("ERROR: PyYAML is required (pip install PyYAML)")
        sys.exit(2)
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_DATASET,
                        help="dataset directory (default: %(default)s)")
    parser.add_argument("--no-hash", action="store_true",
                        help="skip the duplicate-content (leakage) scan")
    args = parser.parse_args()

    root: Path = args.root
    errors: list[str] = []
    warnings: list[str] = []

    def err(msg: str) -> None:
        errors.append(msg)

    def warn(msg: str) -> None:
        warnings.append(msg)

    if not root.is_dir():
        print(f"ERROR: dataset directory not found: {root}")
        return 1

    # ── data.yaml ────────────────────────────────────────────────
    yaml_path = root / "data.yaml"
    if not yaml_path.exists():
        err("data.yaml is missing")
        print("\n".join(errors))
        return 1
    cfg = _load_yaml(yaml_path)

    names = cfg.get("names") or []
    nc = cfg.get("nc")
    if not isinstance(names, (list, dict)) or not names:
        err(f"data.yaml: `names` missing or empty: {names!r}")
        names = []
    if isinstance(names, dict):
        names = [names[k] for k in sorted(names, key=lambda x: int(x))]
    if nc != len(names):
        err(f"data.yaml: nc={nc!r} does not match len(names)={len(names)}")

    split_dirs = {
        "train": cfg.get("train"),
        "valid": cfg.get("val"),
        "test": cfg.get("test"),
    }
    print(f"Dataset: {root}")
    print(f"Classes ({len(names)}): {names}")

    hashes: dict[str, list[tuple[str, Path]]] = {}

    total_images = total_labels = 0
    class_hist: Counter = Counter()
    empty_label_files = 0

    for split, rel in split_dirs.items():
        if not rel:
            err(f"data.yaml: no entry for split '{split}'")
            continue
        img_dir = root / str(rel)
        lbl_dir = img_dir.parent / "labels"
        if not img_dir.is_dir():
            err(f"{split}: image directory missing: {img_dir}")
            continue
        if not lbl_dir.is_dir():
            err(f"{split}: label directory missing: {lbl_dir}")
            continue

        images = sorted(p for p in img_dir.iterdir() if p.is_file())
        labels = sorted(p for p in lbl_dir.iterdir() if p.is_file())

        img_by_stem: dict[str, Path] = {}
        for p in images:
            if p.suffix.lower() not in IMAGE_SUFFIXES:
                err(f"{split}: unexpected file in images/: {p.name}")
                continue
            if p.stem in img_by_stem:
                err(f"{split}: duplicate image stem {p.stem!r}")
            img_by_stem[p.stem] = p

        lbl_by_stem: dict[str, Path] = {}
        for p in labels:
            if p.suffix.lower() != ".txt":
                err(f"{split}: unexpected file in labels/: {p.name}")
                continue
            if p.stem in lbl_by_stem:
                err(f"{split}: duplicate label stem {p.stem!r}")
            lbl_by_stem[p.stem] = p

        missing = sorted(set(img_by_stem) - set(lbl_by_stem))
        orphans = sorted(set(lbl_by_stem) - set(img_by_stem))
        for stem in missing[:20]:
            err(f"{split}: image without label file: {stem}")
        if len(missing) > 20:
            err(f"{split}: ...and {len(missing) - 20} more images without labels")
        for stem in orphans[:20]:
            err(f"{split}: label without image file: {stem}")
        if len(orphans) > 20:
            err(f"{split}: ...and {len(orphans) - 20} more orphan labels")

        # Images: decode check.
        for stem, img_path in img_by_stem.items():
            try:
                from PIL import Image

                with Image.open(img_path) as im:
                    im.verify()                       # structural check
                with Image.open(img_path) as im:
                    w, h = im.size                    # header re-read
                if w <= 0 or h <= 0:
                    err(f"{split}: {img_path.name}: degenerate size {w}x{h}")
                elif w * h > 80_000_000:
                    warn(f"{split}: {img_path.name}: very large image {w}x{h}")
            except Exception as exc:                  # noqa: BLE001
                err(f"{split}: {img_path.name}: cannot decode ({exc})")

            if not args.no_hash:
                digest = hashlib.md5(img_path.read_bytes()).hexdigest()
                hashes.setdefault(digest, []).append((split, img_path))

        # Labels: parse + geometry.
        for stem, lbl_path in lbl_by_stem.items():
            if stem not in img_by_stem:
                continue  # already reported as orphan
            try:
                text = lbl_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                err(f"{split}: {lbl_path.name}: not valid UTF-8")
                continue
            stripped = text.strip()
            if not stripped:
                empty_label_files += 1
                continue  # background image — valid in YOLO

            for lineno, line in enumerate(stripped.splitlines(), 1):
                raw = line.rstrip("\r")
                if not raw.strip():
                    err(f"{split}: {lbl_path.name}:{lineno}: blank line inside label")
                    continue
                parts = raw.split()
                where = f"{split}: {lbl_path.name}:{lineno}"
                if len(parts) != 5:
                    err(f"{where}: expected 5 fields, got {len(parts)}: {raw!r}")
                    continue
                cls_raw, *coords_raw = parts
                try:
                    coords = [float(c) for c in coords_raw]
                except ValueError:
                    err(f"{where}: non-numeric coordinate: {raw!r}")
                    continue
                if not cls_raw.isdigit():
                    err(f"{where}: class id is not a non-negative integer: {cls_raw!r}")
                    continue
                cls = int(cls_raw)
                if names and cls >= len(names):
                    err(f"{where}: class {cls} out of range (nc={len(names)})")
                class_hist[cls] += 1

                if any(c != c or c in (float("inf"), float("-inf")) for c in coords):
                    err(f"{where}: non-finite coordinate: {raw!r}")
                    continue
                x, y, w, h = coords
                if not (0.0 - TOL <= x <= 1.0 + TOL and 0.0 - TOL <= y <= 1.0 + TOL):
                    err(f"{where}: center outside [0,1]: {raw!r}")
                if not (0.0 < w <= 1.0 + TOL and 0.0 < h <= 1.0 + TOL):
                    err(f"{where}: bad width/height: {raw!r}")
                if (x - w / 2 < -TOL or x + w / 2 > 1 + TOL
                        or y - h / 2 < -TOL or y + h / 2 > 1 + TOL):
                    err(f"{where}: box overflows the frame: {raw!r}")

        total_images += len(img_by_stem)
        total_labels += len(lbl_by_stem)
        print(f"  {split:>5}: {len(img_by_stem):>4} images, {len(lbl_by_stem):>4} labels")

    # ── duplicate content / split leakage ───────────────────────
    if not args.no_hash:
        split_leaks: list[str] = []
        intra_dupes: list[str] = []
        for digest, occ in hashes.items():
            if len(occ) < 2:
                continue
            splits = {s for s, _ in occ}
            names_ = " | ".join(f"{s}:{p.name}" for s, p in occ)
            if len(splits) > 1:
                split_leaks.append(names_)
            else:
                intra_dupes.append(names_)
        for entry in split_leaks[:10]:
            warn(f"identical image content across splits (leakage): {entry}")
        if len(split_leaks) > 10:
            warn(f"...and {len(split_leaks) - 10} more cross-split duplicates")
        for entry in intra_dupes[:10]:
            warn(f"identical image content within a split: {entry}")
        if len(intra_dupes) > 10:
            warn(f"...and {len(intra_dupes) - 10} more intra-split duplicates")

    # ── report ───────────────────────────────────────────────────
    print(f"\nTotals: {total_images} images, {total_labels} label files")
    if empty_label_files:
        print(f"Background images (empty labels): {empty_label_files}")
    if names:
        print("Class distribution:",
              ", ".join(f"{names[i] if i < len(names) else f'class{i}'}={class_hist.get(i, 0)}"
                        for i in range(len(names))))
        extra = [c for c in class_hist if c >= len(names)]
        if extra:
            print(f"Out-of-range classes seen: {sorted(extra)}")

    if warnings:
        print(f"\n{len(warnings)} warning(s):")
        for w in warnings:
            print(f"  WARN  {w}")
    if errors:
        print(f"\n{len(errors)} error(s):")
        for e in errors:
            print(f"  ERROR {e}")
        print("\nDataset validation FAILED")
        return 1

    print("\nDataset validation PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
