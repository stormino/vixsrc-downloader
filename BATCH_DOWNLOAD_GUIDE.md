# Batch Download Guide

This guide explains how to use the batch download feature in the VixSrc Downloader.

## Overview

The batch download feature allows you to download multiple movies and TV episodes from a single file, with support for parallel downloads to speed up the process.

## Quick Start

1. **Create a batch file** (e.g., `downloads.txt`):

```
# Movies
movie 550 fight_club.mp4 en 1080
movie 603 the_matrix.mp4 en 720

# TV Shows
tv 60625 4 1 - en 1080
tv 60625 4 2 - en 1080
```

2. **Run the batch download**:

```bash
# Sequential downloads
python3 vixsrc_downloader.py --batch downloads.txt --output-dir ./videos

# Parallel downloads (3 at a time)
python3 vixsrc_downloader.py --batch downloads.txt --output-dir ./videos --parallel 3
```

## Batch File Format

Each line in the batch file represents one download task:

### Movies
```
movie TMDB_ID [OUTPUT_FILE] [LANG] [QUALITY]
```

**Examples:**
```
movie 550                              # Auto-generated filename, default settings
movie 550 fight_club.mp4               # Custom filename
movie 550 fight_club.mp4 en            # Custom filename, English audio
movie 550 fight_club.mp4 en 1080       # Full specification
movie 550 - en 1080                    # Auto-filename, English, 1080p
```

### TV Shows
```
tv TMDB_ID SEASON EPISODE [OUTPUT_FILE] [LANG] [QUALITY]
```

**Examples:**
```
tv 60625 4 1                           # Auto-generated filename, default settings
tv 60625 4 1 bb_s04e01.mp4             # Custom filename
tv 60625 4 1 bb_s04e01.mp4 en          # Custom filename, English audio
tv 60625 4 1 bb_s04e01.mp4 en 1080     # Full specification
tv 60625 4 1 - en 1080                 # Auto-filename, English, 1080p
```

### Special Characters

- **`#`** - Lines starting with `#` are comments and will be ignored
- **`-`** - Use dash to skip a parameter and use the default value
- Empty lines are ignored

## Command-Line Options

```bash
python3 vixsrc_downloader.py --batch FILE [OPTIONS]
```

### Required
- `--batch FILE` - Path to the batch file

### Optional
- `--output-dir DIR` or `-d DIR` - Output directory for all downloads (default: current directory)
- `--parallel N` or `-p N` - Number of parallel downloads (default: 1)
- `--lang LANG` - Default language for all downloads (can be overridden per-task)
- `--quality QUALITY` or `-q QUALITY` - Default quality (best/worst/720/1080)
- `--tmdb-api-key KEY` - TMDB API key for metadata (or set TMDB_API_KEY env var)
- `--no-metadata` - Disable TMDB metadata fetching

## Examples

### Download an entire TV season

Create a file `bb_season4.txt`:
```
# Breaking Bad Season 4
tv 60625 4 1 - en 1080
tv 60625 4 2 - en 1080
tv 60625 4 3 - en 1080
tv 60625 4 4 - en 1080
tv 60625 4 5 - en 1080
tv 60625 4 6 - en 1080
tv 60625 4 7 - en 1080
tv 60625 4 8 - en 1080
tv 60625 4 9 - en 1080
tv 60625 4 10 - en 1080
tv 60625 4 11 - en 1080
tv 60625 4 12 - en 1080
tv 60625 4 13 - en 1080
```

Download with 3 parallel jobs:
```bash
python3 vixsrc_downloader.py --batch bb_season4.txt --parallel 3 --output-dir ./breaking_bad/season4
```

### Download a movie collection

Create a file `nolan_movies.txt`:
```
# Christopher Nolan Movies
movie 550 fight_club.mp4 en 1080
movie 155 the_dark_knight.mp4 en 1080
movie 27205 inception.mp4 en 1080
movie 157336 interstellar.mp4 en 1080
movie 424783 dunkirk.mp4 en 1080
```

Download sequentially:
```bash
python3 vixsrc_downloader.py --batch nolan_movies.txt --output-dir ./movies/nolan
```

### Mixed content with different languages

```
# Mixed downloads
movie 550 - en 1080
movie 603 - es 720
tv 60625 4 1 - it 1080
tv 1399 1 1 - en 1080
```

Download:
```bash
python3 vixsrc_downloader.py --batch mixed.txt --parallel 2
```

## Parallel Downloads

The `--parallel` option controls how many downloads run simultaneously:

- `--parallel 1` (default) - Sequential, one at a time
- `--parallel 2` - Two downloads at once
- `--parallel 3` - Three downloads at once
- etc.

**Recommendations:**
- For local storage: 2-4 parallel downloads
- For network storage: 1-2 parallel downloads
- Consider your bandwidth and system resources

**Note:** Too many parallel downloads may:
- Saturate your network bandwidth
- Trigger rate limiting from the server
- Use excessive CPU/memory resources

## Output

The batch downloader provides real-time progress bars for each download:

1. **Individual progress bars** - Each download shows its own progress bar with percentage and elapsed time
2. **Concurrent tracking** - When using `--parallel`, multiple progress bars display simultaneously
3. **Status indicators** - Clear visual feedback: queued → downloading → ✓ (completed) or ✗ (failed)
4. **Clean display** - Progress bars replace verbose logging for a cleaner interface
5. **Summary statistics** - Final report with total, successful, and failed downloads

Example output:
```
VixSrc Batch Downloader - 5 tasks - 2 parallel jobs

Downloading Fight.Club.1999.mp4:  45%|████████████          | [00:23]
Downloading The.Matrix.1999.mp4:  78%|████████████████████  | [00:15]
Queued: TV 60625 S04E01:   0%|                              | [00:00]

============================================================
Summary
============================================================
Total:   5
Success: 4
Failed:  1
============================================================
```

**Progress Bar Features:**
- Real-time download percentage
- Elapsed time tracking
- Filename display
- Status updates (Queued → Downloading → ✓/✗)
- No verbose logging clutter

## Generating Batch Files Programmatically

### Entire TV season

```bash
#!/bin/bash
TMDB_ID=60625  # Breaking Bad
SEASON=4
OUTPUT="season_${SEASON}.txt"

echo "# Breaking Bad Season $SEASON" > "$OUTPUT"
for EPISODE in {1..13}; do
    echo "tv $TMDB_ID $SEASON $EPISODE - en 1080" >> "$OUTPUT"
done
```

### Multiple seasons

```bash
#!/bin/bash
TMDB_ID=60625  # Breaking Bad
OUTPUT="all_seasons.txt"

echo "# Breaking Bad All Seasons" > "$OUTPUT"
for SEASON in {1..5}; do
    echo "" >> "$OUTPUT"
    echo "# Season $SEASON" >> "$OUTPUT"
    for EPISODE in {1..13}; do
        echo "tv $TMDB_ID $SEASON $EPISODE - en 1080" >> "$OUTPUT"
    done
done
```

## Troubleshooting

### Some downloads fail
- Check the TMDB ID is correct
- Verify the content is available on vixsrc.to
- Ensure you have enough disk space
- Try reducing parallel jobs if experiencing network issues

### Downloads are slow
- Reduce quality: change `1080` to `720`
- Reduce parallel jobs
- Check your network connection

### All downloads fail
- Verify vixsrc.to is accessible
- Check your TMDB API key (if using metadata)
- Ensure yt-dlp or ffmpeg is installed

## Best Practices

1. **Start with sequential downloads** - Test with `--parallel 1` first
2. **Use comments** - Document your batch files with `#` comments
3. **Organize by directory** - Use `--output-dir` to keep downloads organized
4. **Test small batches first** - Try 2-3 items before large batches
5. **Use auto-generated filenames** - Let TMDB metadata generate descriptive names
6. **Monitor the first few** - Watch the first downloads to catch errors early

## Exit Codes

- `0` - All downloads successful
- `1` - One or more downloads failed

You can check the exit code in bash:
```bash
python3 vixsrc_downloader.py --batch downloads.txt
if [ $? -eq 0 ]; then
    echo "All downloads completed successfully!"
else
    echo "Some downloads failed. Check the output above."
fi
```
