#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动分段处理长视频：按时间切分 -> 擦除 -> 合并
"""
import os
import sys
import subprocess
import argparse
import shutil
from pathlib import Path
import tempfile


def get_video_duration(video_path):
    """获取视频时长（秒）"""
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


def split_video(video_path, segment_duration, output_dir):
    """切分视频"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_pattern = str(output_dir / "segment_%03d.mp4")

    cmd = [
        'ffmpeg', '-i', video_path,
        '-c', 'copy',
        '-map', '0',
        '-segment_time', str(segment_duration),
        '-f', 'segment',
        '-reset_timestamps', '1',
        output_pattern
    ]

    print(f"Splitting video into {segment_duration}s segments...")
    subprocess.run(cmd, check=True)

    segments = sorted(output_dir.glob("segment_*.mp4"))
    print(f"Created {len(segments)} segments")
    return segments


def process_segment(segment_path, mask_path, output_dir, inference_args):
    """处理单个视频段"""
    segment_name = segment_path.stem
    output_path = Path(output_dir) / segment_name

    cmd = [
        sys.executable, 'inference_propainter.py',
        '-i', str(segment_path),
        '-m', mask_path,
        '-o', str(output_path.parent),
    ]

    # 添加额外参数
    if inference_args:
        cmd.extend(inference_args.split())

    print(f"\nProcessing {segment_name}...")
    subprocess.run(cmd, check=True)

    # 返回处理后的视频路径
    result_video = output_path / "inpaint_out.mp4"
    if not result_video.exists():
        raise FileNotFoundError(f"Result not found: {result_video}")

    return result_video


def merge_videos(video_list, output_path):
    """合并视频"""
    # 创建文件列表
    list_file = Path(tempfile.gettempdir()) / "video_list.txt"
    with open(list_file, 'w') as f:
        for video in video_list:
            f.write(f"file '{video.absolute()}'\n")

    cmd = [
        'ffmpeg', '-f', 'concat',
        '-safe', '0',
        '-i', str(list_file),
        '-c', 'copy',
        str(output_path)
    ]

    print(f"\nMerging {len(video_list)} segments...")
    subprocess.run(cmd, check=True)

    list_file.unlink()
    print(f"Merged video saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Process long videos by splitting into segments'
    )
    parser.add_argument(
        '-i', '--video', required=True,
        help='Input video path'
    )
    parser.add_argument(
        '-m', '--mask', required=True,
        help='Mask image or folder path'
    )
    parser.add_argument(
        '-o', '--output', default='results/merged_output.mp4',
        help='Output merged video path'
    )
    parser.add_argument(
        '--segment_duration', type=int, default=30,
        help='Segment duration in seconds (default: 30)'
    )
    parser.add_argument(
        '--keep_segments', action='store_true',
        help='Keep temporary segment files'
    )
    parser.add_argument(
        '--inference_args', type=str, default='--ultra_low_memory',
        help='Arguments to pass to inference_propainter.py (default: --ultra_low_memory)'
    )

    args = parser.parse_args()

    # 验证输入
    if not os.path.exists(args.video):
        print(f"Error: Video not found: {args.video}")
        return 1

    if not os.path.exists(args.mask):
        print(f"Error: Mask not found: {args.mask}")
        return 1

    # 创建临时目录
    temp_dir = Path(tempfile.mkdtemp(prefix="propainter_segments_"))
    segments_dir = temp_dir / "segments"
    results_dir = temp_dir / "results"

    try:
        # 1. 获取视频时长
        duration = get_video_duration(args.video)
        print(f"Video duration: {duration:.2f}s")
        estimated_segments = int(duration / args.segment_duration) + 1
        print(f"Estimated segments: {estimated_segments}")

        # 2. 切分视频
        segments = split_video(args.video, args.segment_duration, segments_dir)

        # 3. 处理每个片段
        processed_videos = []
        for i, segment in enumerate(segments, 1):
            print(f"\n{'='*60}")
            print(f"Processing segment {i}/{len(segments)}: {segment.name}")
            print(f"{'='*60}")

            result_video = process_segment(
                segment, args.mask, results_dir, args.inference_args
            )
            processed_videos.append(result_video)

        # 4. 合并视频
        print(f"\n{'='*60}")
        print("Merging all segments...")
        print(f"{'='*60}")

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        merge_videos(processed_videos, output_path)

        print(f"\n{'='*60}")
        print("✓ Processing complete!")
        print(f"{'='*60}")
        print(f"Output: {output_path.absolute()}")

        return 0

    except subprocess.CalledProcessError as e:
        print(f"\nError during processing: {e}")
        return 1

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 1

    finally:
        # 清理临时文件
        if not args.keep_segments and temp_dir.exists():
            print(f"\nCleaning up temporary files...")
            shutil.rmtree(temp_dir, ignore_errors=True)
        elif args.keep_segments:
            print(f"\nTemporary files kept in: {temp_dir}")


if __name__ == '__main__':
    sys.exit(main())
