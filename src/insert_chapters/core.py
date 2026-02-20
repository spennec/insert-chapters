from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

TIMESTAMP_RE = re.compile(r"^(?P<ts>(?:\d+:)?\d{1,2}:\d{2})\s*(?:[-–—|]\s*)?(?P<title>.+?)\s*$")
LEADING_END_TIMESTAMP_RE = re.compile(r"^(?:\d+:)?\d{1,2}:\d{2}\s+(?P<title>.+)$")


@dataclass
class ChapterStart:
    start_ms: int
    title: str


@dataclass
class ChapterRange:
    start_ms: int
    end_ms: int
    title: str


def parse_timestamp_to_ms(raw: str) -> int:
    parts = raw.split(":")
    if len(parts) == 2:
        hours = 0
        minutes, seconds = parts
    elif len(parts) == 3:
        hours, minutes, seconds = parts
    else:
        raise ValueError(f"Invalid timestamp format: {raw!r}")

    try:
        h = int(hours)
        m = int(minutes)
        s = int(seconds)
    except ValueError as exc:
        raise ValueError(f"Timestamp contains non-numeric values: {raw!r}") from exc

    if m < 0 or m > 59 or s < 0 or s > 59 or h < 0:
        raise ValueError(f"Timestamp out of range: {raw!r}")

    return (h * 3600 + m * 60 + s) * 1000


def parse_chapter_file(path: Path) -> list[ChapterStart]:
    chapters: list[ChapterStart] = []

    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue

        match = TIMESTAMP_RE.match(stripped)
        if not match:
            raise ValueError(
                f"Could not parse line {idx}: {line!r}. Expected '<timestamp> <title>' like '0:00 Intro'."
            )

        start_ms = parse_timestamp_to_ms(match.group("ts"))
        title = match.group("title").strip()
        # Allow "start - end title" format by discarding the optional end timestamp.
        end_match = LEADING_END_TIMESTAMP_RE.match(title)
        if end_match:
            title = end_match.group("title").strip()
        if not title:
            raise ValueError(f"Chapter title is empty on line {idx}: {line!r}")

        chapters.append(ChapterStart(start_ms=start_ms, title=title))

    if not chapters:
        raise ValueError("No chapters found in chapter file.")

    return chapters


def normalize_chapters(starts: list[ChapterStart], duration_ms: int) -> list[ChapterRange]:
    if not starts:
        raise ValueError("No chapter start times were provided.")

    starts_sorted = sorted(starts, key=lambda c: c.start_ms)

    if 0 < starts_sorted[0].start_ms < 10_000:
        starts_sorted[0] = ChapterStart(start_ms=0, title=starts_sorted[0].title)
    elif starts_sorted[0].start_ms > 0:
        starts_sorted.insert(0, ChapterStart(start_ms=0, title="Intro"))

    for i in range(1, len(starts_sorted)):
        if starts_sorted[i].start_ms == starts_sorted[i - 1].start_ms:
            raise ValueError(
                f"Duplicate chapter timestamp at {starts_sorted[i].start_ms // 1000} seconds."
            )

    if starts_sorted[-1].start_ms >= duration_ms:
        raise ValueError(
            "Last chapter starts at or after video duration. "
            f"Last start: {starts_sorted[-1].start_ms} ms, duration: {duration_ms} ms"
        )

    ranges: list[ChapterRange] = []
    for i, chapter in enumerate(starts_sorted):
        end_ms = starts_sorted[i + 1].start_ms if i + 1 < len(starts_sorted) else duration_ms
        if end_ms <= chapter.start_ms:
            raise ValueError(
                f"Invalid chapter order near '{chapter.title}': next chapter is not later in time."
            )
        ranges.append(ChapterRange(start_ms=chapter.start_ms, end_ms=end_ms, title=chapter.title))

    return ranges


def escape_ffmetadata(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("=", "\\=")
        .replace(";", "\\;")
        .replace("#", "\\#")
        .replace("\n", "\\n")
    )


def build_ffmetadata(chapters: list[ChapterRange]) -> str:
    lines = [";FFMETADATA1", ""]
    for chapter in chapters:
        lines.extend(
            [
                "[CHAPTER]",
                "TIMEBASE=1/1000",
                f"START={chapter.start_ms}",
                f"END={chapter.end_ms}",
                f"title={escape_ffmetadata(chapter.title)}",
                "",
            ]
        )
    return "\n".join(lines)


def get_video_duration_ms(video_path: Path) -> int:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    result = subprocess.run(cmd, check=True, text=True, capture_output=True)
    duration_str = result.stdout.strip()
    if not duration_str:
        raise RuntimeError("ffprobe did not return a duration.")

    try:
        duration_seconds = float(duration_str)
    except ValueError as exc:
        raise RuntimeError(f"Could not parse ffprobe duration: {duration_str!r}") from exc

    duration_ms = int(duration_seconds * 1000)
    if duration_ms <= 0:
        raise RuntimeError(f"Invalid video duration: {duration_ms} ms")
    return duration_ms


def run_ffmpeg_with_metadata(video_path: Path, metadata_path: Path, output_path: Path) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(metadata_path),
        "-map_metadata",
        "1",
        "-map_chapters",
        "1",
        "-codec",
        "copy",
        str(output_path),
    ]
    subprocess.run(cmd, check=True)


def pick_default_output(video_path: Path) -> Path:
    return video_path.with_name(f"{video_path.stem}.chapters{video_path.suffix}")


def ensure_ff_tools_available() -> None:
    missing = [tool for tool in ("ffmpeg", "ffprobe") if shutil.which(tool) is None]
    if missing:
        raise RuntimeError(
            "Missing required tools: "
            + ", ".join(missing)
            + ". Install FFmpeg so both ffmpeg and ffprobe are available in PATH."
        )


def validate_video_path(video_path: Path) -> None:
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    if video_path.suffix.lower() not in {".mp4", ".mkv"}:
        raise ValueError("Video file must have .mp4 or .mkv extension.")
