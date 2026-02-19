from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from .core import (
    build_ffmetadata,
    ensure_ff_tools_available,
    get_video_duration_ms,
    normalize_chapters,
    parse_chapter_file,
    pick_default_output,
    run_ffmpeg_with_metadata,
    validate_video_path,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Insert chapter metadata into an MP4/MKV using a YouTube-style chapter text file."
        )
    )
    parser.add_argument("video", type=Path, help="Input video file (.mp4 or .mkv)")
    parser.add_argument("chapters", type=Path, help="Text file with chapter lines like '0:00 Intro'")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output video path. Defaults to '<input>.chapters.<ext>' in the same folder.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        ensure_ff_tools_available()
        validate_video_path(args.video)

        if not args.chapters.exists():
            raise FileNotFoundError(f"Chapter file not found: {args.chapters}")

        output_path = args.output if args.output else pick_default_output(args.video)

        duration_ms = get_video_duration_ms(args.video)
        chapter_starts = parse_chapter_file(args.chapters)
        chapter_ranges = normalize_chapters(chapter_starts, duration_ms)
        ffmetadata_text = build_ffmetadata(chapter_ranges)

        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", suffix=".ffmeta") as temp_meta:
            temp_meta.write(ffmetadata_text)
            temp_meta_path = Path(temp_meta.name)

        try:
            run_ffmpeg_with_metadata(args.video, temp_meta_path, output_path)
        finally:
            temp_meta_path.unlink(missing_ok=True)

        print(f"Inserted {len(chapter_ranges)} chapters into: {output_path}")
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI tool should show concise errors.
        print(f"Error: {exc}", file=sys.stderr)
        return 1
