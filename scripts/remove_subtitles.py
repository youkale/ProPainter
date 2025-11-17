#!/usr/bin/env python3
"""
One-click subtitle removal pipeline.

Example:
    python scripts/remove_subtitles.py \
        --video results/subtitle_1.mp4 \
        --region 0.1 0.2 0.9 0.05
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Sequence

ROOT = Path(__file__).resolve().parents[1]


def build_mask(
    video: Path,
    regions: Sequence[Sequence[float]],
    origin: str,
    mask_path: Path,
    region_json: str | None,
) -> None:
    cmd: List[str] = [
        sys.executable,
        str(ROOT / "scripts" / "generate_mask_from_regions.py"),
        "--video",
        str(video),
        "--output",
        str(mask_path),
        "--origin",
        origin,
    ]
    for region in regions:
        cmd += ["--region"] + [str(v) for v in region]
    if region_json:
        cmd += ["--region-json", region_json]

    print(f"[1/2] Generating mask at {mask_path} ...")
    subprocess.run(cmd, check=True)


def run_inference(
    video: Path,
    mask_path: Path,
    output_dir: Path,
    width: int,
    height: int,
    fp16: bool,
    save_frames: bool,
    save_fps: int | None,
) -> None:
    cmd: List[str] = [
        sys.executable,
        str(ROOT / "inference_propainter.py"),
        "--video",
        str(video),
        "--mask",
        str(mask_path),
        "--output",
        str(output_dir),
    ]
    if width > 0:
        cmd += ["--width", str(width)]
    if height > 0:
        cmd += ["--height", str(height)]
    if fp16:
        cmd.append("--fp16")
    if save_frames:
        cmd.append("--save_frames")
    if save_fps is not None:
        cmd += ["--save_fps", str(save_fps)]

    print(f"[2/2] Running ProPainter inference into {output_dir} ...")
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate masks and remove subtitles in one command.")
    parser.add_argument("--video", required=True, type=str, help="Input video path.")
    parser.add_argument(
        "--region",
        dest="regions",
        metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"),
        type=float,
        nargs=4,
        action="append",
        help="Normalized region defined with left-bottom origin. Repeat for multiple regions.",
    )
    parser.add_argument("--region-json", type=str, default=None, help="Optional JSON file containing regions.")
    parser.add_argument("--origin", choices=["left-bottom", "left-top"], default="left-bottom", help="Coordinate origin.")
    parser.add_argument("--output", type=str, default="results", help="Directory where inference output is stored.")
    parser.add_argument("--mask-output", type=str, default=None, help="Optional path to save the generated mask image.")
    parser.add_argument("--keep-mask", action="store_true", help="Keep the generated mask file when using a temporary path.")
    parser.add_argument("--width", type=int, default=-1, help="Processing width passed to ProPainter.")
    parser.add_argument("--height", type=int, default=-1, help="Processing height passed to ProPainter.")
    parser.add_argument("--fp16", action="store_true", help="Enable fp16 inference.")
    parser.add_argument("--save-frames", action="store_true", help="Save output frames in addition to the video.")
    parser.add_argument("--save-fps", type=int, default=None, help="FPS for saving the result video.")
    args = parser.parse_args()

    video_path = Path(args.video).expanduser().resolve()
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    if not args.regions and not args.region_json:
        raise ValueError("Please provide at least one region via --region or --region-json.")

    regions = [tuple(region) for region in (args.regions or [])]

    output_dir = Path(args.output).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.mask_output:
        mask_path = Path(args.mask_output).expanduser().resolve()
        mask_path.parent.mkdir(parents=True, exist_ok=True)
        temp_dir = None
    else:
        temp_dir = Path(tempfile.mkdtemp(prefix="propainter_mask_"))
        mask_path = temp_dir / f"{video_path.stem}_mask.png"

    try:
        build_mask(video_path, regions, args.origin, mask_path, args.region_json)
        run_inference(
            video=video_path,
            mask_path=mask_path,
            output_dir=output_dir,
            width=args.width,
            height=args.height,
            fp16=args.fp16,
            save_frames=args.save_frames,
            save_fps=args.save_fps,
        )
    finally:
        if temp_dir and not args.keep_mask:
            try:
                os.remove(mask_path)
                os.rmdir(temp_dir)
            except OSError:
                pass

    print("Subtitle removal completed successfully.")


if __name__ == "__main__":
    main()
