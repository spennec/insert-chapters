# insert-chapters

A small Python CLI that inserts chapter metadata into an existing video file (`.mp4` or `.mkv`) using a YouTube-style chapter list from a text file.

The video is remuxed with `ffmpeg` using stream copy (`-codec copy`), so it does not re-encode video/audio.

## Requirements

- Python 3.10+
- `ffmpeg` and `ffprobe` available in your `PATH`

Optional for tests:

- `pytest`

## Chapter File Format

Use one chapter per line:

```text
0:00 Intro
1:23 Setup
2:34 - Deep dive
3:45 | Wrap up
01:02:03 Final notes
```

Supported timestamp formats:

- `MM:SS`
- `HH:MM:SS`

Notes:

- If the first chapter does not start at `0:00`, the script automatically inserts `0:00 Intro`.
- Blank lines are ignored.

## Usage

From the repo root:

```bash
python3 insert_chapters.py <video.mp4|video.mkv> <chapters.txt>
```

Example:

```bash
python3 insert_chapters.py movie.mp4 chapters.txt
```

By default, output is written next to the input video as:

- `movie.chapters.mp4`
- `movie.chapters.mkv`

You can set a custom output path:

```bash
python3 insert_chapters.py movie.mp4 chapters.txt --output movie-with-chapters.mp4
```

## Run Tests

Install pytest and run:

```bash
python3 -m pip install pytest
python3 -m pytest
```
