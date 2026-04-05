"""Export a YOLOv8 .pt model to ONNX format optimised for CPU inference.

Usage:
    python export_onnx.py
    python export_onnx.py --model models/yolov8s_ap.pt --imgsz 640
"""

from __future__ import annotations

import argparse
from pathlib import Path


def export(model_path: str, imgsz: int) -> None:
    from ultralytics import YOLO

    src = Path(model_path)
    if not src.exists():
        raise FileNotFoundError(f"Model not found: {src}")

    print(f"Loading {src} ...")
    model = YOLO(str(src))

    print("Exporting to ONNX (dynamic=True, simplify=True) ...")
    out = model.export(
        format="onnx",
        imgsz=imgsz,
        dynamic=True,      # variable batch size / image dims
        simplify=True,     # runs onnx-simplifier to fold constants & fuse ops
        opset=17,          # latest stable opset; onnxruntime >= 1.15 required
    )

    print(f"\nExport complete: {out}")
    print("Next step: set MODEL_PATH=models/yolov8s_ap.onnx (or rename the file)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export YOLOv8 .pt → ONNX")
    parser.add_argument(
        "--model",
        default="models/yolov8s_ap.pt",
        help="Path to the .pt model (default: models/yolov8s_ap.pt)",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=640,
        help="Inference image size (default: 640)",
    )
    args = parser.parse_args()
    export(args.model, args.imgsz)
