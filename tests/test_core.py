from pathlib import Path

import pytest

from insert_chapters.core import (
    ChapterStart,
    build_ffmetadata,
    normalize_chapters,
    parse_chapter_file,
    parse_timestamp_to_ms,
    pick_default_output,
    validate_video_path,
)


def test_parse_timestamp_to_ms_supports_mm_ss_and_hh_mm_ss() -> None:
    assert parse_timestamp_to_ms("0:00") == 0
    assert parse_timestamp_to_ms("12:34") == 754000
    assert parse_timestamp_to_ms("01:02:03") == 3723000


@pytest.mark.parametrize("value", ["1", "99:99", "1:2:3:4", "aa:bb"])
def test_parse_timestamp_to_ms_rejects_bad_values(value: str) -> None:
    with pytest.raises(ValueError):
        parse_timestamp_to_ms(value)


def test_parse_chapter_file_accepts_youtube_style_lines(tmp_path: Path) -> None:
    chapters_file = tmp_path / "chapters.txt"
    chapters_file.write_text(
        "\n".join([
            "0:00 Intro",
            "1:23 - Setup",
            "2:34 | Deep dive",
            "3:45 — Wrap up",
        ]),
        encoding="utf-8",
    )

    chapters = parse_chapter_file(chapters_file)

    assert [c.start_ms for c in chapters] == [0, 83000, 154000, 225000]
    assert [c.title for c in chapters] == ["Intro", "Setup", "Deep dive", "Wrap up"]


def test_parse_chapter_file_ignores_end_timestamp_prefix_in_title(tmp_path: Path) -> None:
    chapters_file = tmp_path / "chapters.txt"
    chapters_file.write_text(
        "\n".join(
            [
                "0:01 - 5:13 Take Back The City",
                "5:14 - 8:33 Chocolate",
                "57:32 - 1:02:11 Just Say Yes",
            ]
        ),
        encoding="utf-8",
    )

    chapters = parse_chapter_file(chapters_file)

    assert [c.start_ms for c in chapters] == [1000, 314000, 3452000]
    assert [c.title for c in chapters] == ["Take Back The City", "Chocolate", "Just Say Yes"]


def test_parse_chapter_file_errors_on_unparseable_line(tmp_path: Path) -> None:
    chapters_file = tmp_path / "chapters.txt"
    chapters_file.write_text("not-a-timestamp title", encoding="utf-8")

    with pytest.raises(ValueError, match="Could not parse line"):
        parse_chapter_file(chapters_file)


def test_parse_then_normalize_inserts_intro_if_missing_zero(tmp_path: Path) -> None:
    chapters_file = tmp_path / "chapters.txt"
    chapters_file.write_text(
        "\n".join(
            [
                "0:10 First topic",
                "0:20 Second topic",
            ]
        ),
        encoding="utf-8",
    )

    starts = parse_chapter_file(chapters_file)
    ranges = normalize_chapters(starts, duration_ms=30000)

    assert [(c.start_ms, c.end_ms, c.title) for c in ranges] == [
        (0, 10000, "Intro"),
        (10000, 20000, "First topic"),
        (20000, 30000, "Second topic"),
    ]


def test_parse_then_normalize_sets_first_chapter_to_zero_when_under_ten_seconds(tmp_path: Path) -> None:
    chapters_file = tmp_path / "chapters.txt"
    chapters_file.write_text(
        "\n".join(
            [
                "0:01 First topic",
                "0:20 Second topic",
            ]
        ),
        encoding="utf-8",
    )

    starts = parse_chapter_file(chapters_file)
    ranges = normalize_chapters(starts, duration_ms=30000)

    assert [(c.start_ms, c.end_ms, c.title) for c in ranges] == [
        (0, 20000, "First topic"),
        (20000, 30000, "Second topic"),
    ]


def test_normalize_chapters_builds_ranges() -> None:
    starts = [
        ChapterStart(0, "Intro"),
        ChapterStart(5000, "Part 1"),
        ChapterStart(10000, "Part 2"),
    ]

    ranges = normalize_chapters(starts, duration_ms=20000)

    assert [(c.start_ms, c.end_ms, c.title) for c in ranges] == [
        (0, 5000, "Intro"),
        (5000, 10000, "Part 1"),
        (10000, 20000, "Part 2"),
    ]


def test_normalize_chapters_inserts_intro_when_first_chapter_is_not_zero() -> None:
    starts = [ChapterStart(10000, "Part 1"), ChapterStart(13000, "Part 2")]

    ranges = normalize_chapters(starts, duration_ms=25000)

    assert [(c.start_ms, c.end_ms, c.title) for c in ranges] == [
        (0, 10000, "Intro"),
        (10000, 13000, "Part 1"),
        (13000, 25000, "Part 2"),
    ]


def test_build_ffmetadata_escapes_special_characters() -> None:
    metadata = build_ffmetadata(normalize_chapters([ChapterStart(0, "Intro")], duration_ms=1000))
    assert metadata.startswith(";FFMETADATA1")

    ranges = normalize_chapters(
        [ChapterStart(0, "A=B;C#D\\E")],
        duration_ms=1000,
    )
    escaped = build_ffmetadata(ranges)

    assert "title=A\\=B\\;C\\#D\\\\E" in escaped


def test_pick_default_output_preserves_suffix() -> None:
    assert pick_default_output(Path("/tmp/video.mp4")) == Path("/tmp/video.chapters.mp4")
    assert pick_default_output(Path("/tmp/video.mkv")) == Path("/tmp/video.chapters.mkv")


def test_validate_video_path_checks_existence_and_suffix(tmp_path: Path) -> None:
    missing = tmp_path / "missing.mp4"
    with pytest.raises(FileNotFoundError):
        validate_video_path(missing)

    bad = tmp_path / "video.mov"
    bad.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match=".mp4 or .mkv"):
        validate_video_path(bad)

    good = tmp_path / "video.mp4"
    good.write_text("x", encoding="utf-8")
    validate_video_path(good)
