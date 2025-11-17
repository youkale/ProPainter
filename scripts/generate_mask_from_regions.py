#!/usr/bin/env python3
"""
Generate binary mask images from normalized regions for video inpainting.

Given a video (or a folder of frames) and a list of regions defined in a
left-bottom-origin coordinate system, this script creates a black background
mask where the specified regions are painted white. The output can be a single
mask image (reused for every frame) or a folder of per-frame masks.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import cv2
import numpy as np

EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff")


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def parse_regions(
    region_args: Sequence[Sequence[float]],
    origin: str,
) -> List[Tuple[float, float, float, float]]:
    """
    Parse regions from CLI arguments.
    """
    regions: List[Tuple[float, float, float, float]] = []
    for region in region_args:
        if len(region) != 4:
            raise ValueError(f"Each region must contain 4 values, got {region}")
        left, top, right, bottom = [float(v) for v in region]
        left, top, right, bottom = clamp01(left), clamp01(top), clamp01(right), clamp01(bottom)
        if right <= left:
            raise ValueError(f"Region {region} has non-positive width.")
        if origin == "left-bottom":
            if top <= bottom:
                raise ValueError(f"Region {region} has non-positive height.")
        else:
            if top >= bottom:
                raise ValueError(f"Region {region} has non-positive height.")
        regions.append((left, top, right, bottom))
    return regions


def parse_json_regions(json_path: str | None) -> List[Tuple[float, float, float, float]]:
    if not json_path:
        return []
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, Iterable):
        raise ValueError("JSON regions must be a list of [left, top, right, bottom] values.")
    regions = []
    for idx, region in enumerate(data):
        if not isinstance(region, Sequence) or len(region) != 4:
            raise ValueError(f"Region entry #{idx} is invalid: {region}")
        regions.append(tuple(float(v) for v in region))  # type: ignore[arg-type]
    return regions


def get_video_metadata(video_path: Path) -> Tuple[int, int, int]:
    """
    Returns width, height, and frame count.
    """
    if video_path.is_dir():
        frame_paths = sorted(
            [p for p in video_path.iterdir() if p.suffix.lower() in EXTENSIONS]
        )
        if not frame_paths:
            raise FileNotFoundError(f"No image frames found in {video_path}.")
        sample = cv2.imread(str(frame_paths[0]))
        if sample is None:
            raise ValueError(f"Failed to read sample frame: {frame_paths[0]}")
        height, width = sample.shape[:2]
        frame_count = len(frame_paths)
        return width, height, frame_count

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Unable to open video {video_path}")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid video resolution ({width}x{height}) for {video_path}")
    return width, height, max(frame_count, 1)


def convert_region_to_pixels(
    region: Tuple[float, float, float, float],
    width: int,
    height: int,
    origin: str,
) -> Tuple[int, int, int, int]:
    """
    Convert normalized (left, top, right, bottom) coordinates where
    (0,0) is located at either left-bottom or left-top into pixel coordinates
    where numpy image arrays use (0,0) at the left-top corner.
    """
    left, top, right, bottom = region
    x1 = int(np.floor(left * width))
    x2 = int(np.ceil(right * width))

    if origin == "left-bottom":
        y_top_ratio = 1.0 - top
        y_bottom_ratio = 1.0 - bottom
    else:  # left-top
        y_top_ratio = top
        y_bottom_ratio = bottom

    y1 = int(np.floor(y_top_ratio * height))
    y2 = int(np.ceil(y_bottom_ratio * height))

    x1 = max(0, min(width, x1))
    x2 = max(0, min(width, x2))
    y1 = max(0, min(height, y1))
    y2 = max(0, min(height, y2))

    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"Region {region} collapsed after conversion. Check input values.")
    return x1, y1, x2, y2


def render_mask(
    width: int,
    height: int,
    regions: List[Tuple[float, float, float, float]],
    origin: str,
) -> np.ndarray:
    mask = np.zeros((height, width), dtype=np.uint8)
    for region in regions:
        x1, y1, x2, y2 = convert_region_to_pixels(region, width, height, origin)
        mask[y1:y2, x1:x2] = 255
    return mask


def write_single_mask(mask: np.ndarray, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), mask):
        raise IOError(f"Failed to write mask to {output_path}")


def write_per_frame_masks(mask: np.ndarray, output_dir: Path, frame_count: int) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for idx in range(frame_count):
        out_path = output_dir / f"{idx:05d}.png"
        if not cv2.imwrite(str(out_path), mask):
            raise IOError(f"Failed to write mask for frame {idx} to {out_path}")


def infer_default_output(video_path: Path, per_frame: bool) -> Path:
    video_name = video_path.stem if video_path.is_file() else video_path.name
    suffix = "mask_frames" if per_frame else "mask.png"
    return Path("results") / f"{video_name}_{suffix}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate mask images from normalized regions.")
    parser.add_argument(
        "--video",
        required=True,
        type=str,
        help="Path to the input video file or a directory of frames.",
    )
    parser.add_argument(
        "--region",
        dest="regions",
        metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"),
        type=float,
        nargs=4,
        action="append",
        help="Normalized region defined with left-bottom origin. Repeat for multiple regions.",
    )
    parser.add_argument(
        "--region-json",
        type=str,
        default=None,
        help="Optional path to a JSON file containing a list of regions.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output path. If --per-frame is set, provide a folder path.",
    )
    parser.add_argument(
        "--per-frame",
        action="store_true",
        help="Save one mask per frame instead of a single shared mask.",
    )
    parser.add_argument(
        "--origin",
        choices=["left-bottom", "left-top"],
        default="left-bottom",
        help="Coordinate origin used by the normalized regions. Default: left-bottom.",
    )
    args = parser.parse_args()

    video_path = Path(args.video).expanduser().resolve()
    if not video_path.exists():
        raise FileNotFoundError(f"Input video or folder not found: {video_path}")

    cli_regions = args.regions if args.regions else []
    json_regions = parse_json_regions(args.region_json)
    regions = parse_regions([tuple(region) for region in cli_regions + json_regions], args.origin)
    if not regions:
        raise ValueError("At least one region must be provided via --region or --region-json.")

    width, height, frame_count = get_video_metadata(video_path)
    mask = render_mask(width, height, regions, args.origin)

    output_path = Path(args.output).expanduser().resolve() if args.output else infer_default_output(video_path, args.per_frame)

    if args.per_frame:
        if output_path.suffix:
            raise ValueError("When using --per-frame, --output must be a directory path.")
        write_per_frame_masks(mask, output_path, frame_count)
        print(f"Wrote {frame_count} mask frames to {output_path}")
    else:
        if output_path.is_dir():
            output_path = output_path / "mask.png"
        write_single_mask(mask, output_path)
        print(f"Wrote mask image to {output_path}")

    print(f"Input resolution: {width}x{height}, regions: {len(regions)}")


if __name__ == "__main__":
    main()
