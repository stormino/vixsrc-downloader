# VixSrc Video Downloader

A Python tool to download videos from vixsrc.to using TMDB (The Movie Database) IDs.

## ⚠️ Legal Notice

**This tool is for educational purposes only.** Only download content you have legal rights to access. Downloading copyrighted material without permission may violate copyright laws in your jurisdiction.

## Features

- **Search for content** - Search TMDB for movies and TV shows, showing only content available on vixsrc
- Download movies and TV show episodes using TMDB IDs
- **Bulk TV downloads** - Download entire shows or seasons with a single command
- **Real-time progress bars** showing download progress for each running task
- **Auto-generate descriptive filenames** from TMDB metadata (e.g., `Fight.Club.1999.mp4` or `Breaking.Bad.S04E04.Ozymandias.mp4`)
- **Cloudflare bypass** using cloudscraper for reliable access
- Supports both yt-dlp and ffmpeg for downloading
- Quality selection (best/worst/720p/1080p)
- Language/audio track selection (with automatic preference for selected language)
- Simple command-line interface
- Option to just retrieve the playlist URL without downloading

## Requirements

- Python 3.7+
- One of the following:
  - `yt-dlp` (recommended) - `pip install yt-dlp`
  - `ffmpeg` - Available in most package managers

## Installation

### Quick Setup

```bash
# Clone or download the repository
cd vixsrc-downloader

# Run the setup script (installs dependencies automatically)
chmod +x setup.sh
./setup.sh
```

### Manual Installation

1. Install required Python packages:
```bash
pip install -r requirements.txt --break-system-packages
```

2. Install a downloader (choose one):
```bash
# Option 1: yt-dlp (recommended)
pip install yt-dlp --break-system-packages

# Option 2: ffmpeg (alternative)
sudo apt-get install ffmpeg  # Debian/Ubuntu
sudo yum install ffmpeg       # CentOS/RHEL
brew install ffmpeg           # macOS
```

3. **(Optional but Recommended)** Set up TMDB API key for enhanced filenames:

   a. Get a free API key from [TMDB](https://www.themoviedb.org/settings/api):
      - Create a free account at themoviedb.org
      - Go to Settings → API
      - Request an API key (choose "Developer" option)
      - Copy your API key (v3 auth)

   b. Set the API key as an environment variable:
   ```bash
   # Linux/macOS (add to ~/.bashrc or ~/.zshrc for persistence)
   export TMDB_API_KEY="your_api_key_here"

   # Or pass it directly when running
   python3 vixsrc_downloader.py --movie 550 --tmdb-api-key "your_api_key_here"
   ```

   Without the API key, the tool will still work but will use basic filenames like `movie_550.mp4` instead of `Fight.Club.1999.mp4`.

## Project Structure

The project has been refactored into a modular package for better code organization:

```
vixsrc-downloader/
├── vixsrc_downloader/          # Main package
│   ├── __init__.py             # Package exports
│   ├── __main__.py             # CLI entry point
│   ├── constants.py            # Configuration constants
│   ├── utils.py                # Utility functions
│   ├── progress.py             # Progress tracking (ProgressTracker, ProgressParser)
│   ├── metadata.py             # TMDB metadata fetching (TMDBMetadata)
│   ├── extractor.py            # Playlist URL extraction (PlaylistExtractor)
│   ├── downloader.py           # Core download logic (VixSrcDownloader, DownloadExecutor)
│   └── batch.py                # Batch processing (BatchDownloader, DownloadTask)
├── vixsrc_downloader.py        # Wrapper script (backward compatibility)
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Container definition
└── setup.sh                    # Installation script
```

### Usage Methods

You can run the downloader in three ways:

```bash
# Method 1: Using the wrapper script (backward compatible)
python3 vixsrc_downloader.py --movie 550

# Method 2: As a Python module
python3 -m vixsrc_downloader --movie 550

# Method 3: Import as a library in your own code
from vixsrc_downloader import VixSrcDownloader, TMDBMetadata
downloader = VixSrcDownloader()
playlist_url = downloader.get_playlist_url(550)  # Movie ID 550
```

**Docker:**
```bash
# Build the image
docker build -t vixsrc-downloader .

# Run with TMDB API key
docker run -e TMDB_API_KEY="your_key" -v ./downloads:/downloads vixsrc-downloader --movie 550

# Run without TMDB key (basic filenames)
docker run -v ./downloads:/downloads vixsrc-downloader --movie 550 --no-metadata
```

## Usage

### Search for Content

Search TMDB for movies and TV shows, with automatic verification that content is available on vixsrc (requires TMDB API key):

```bash
# Set your TMDB API key
export TMDB_API_KEY="your_api_key_here"

# Search for content
python3 vixsrc_downloader.py --search "breaking bad"
python3 vixsrc_downloader.py --search "fight club"
```

The search displays:
- **Movies**: TMDB ID, title, year, rating, overview
- **TV Shows**: TMDB ID, name, year, **number of seasons**, **total episodes**, rating, overview

Only content actually available on vixsrc is shown, so you can download anything from the results immediately.

### Finding TMDB IDs

You can find TMDB IDs at [themoviedb.org](https://www.themoviedb.org/):

1. Search for your movie or TV show
2. The ID is in the URL: `https://www.themoviedb.org/movie/550` → ID is **550**

Or use the built-in search feature (see above).

### Download a Movie

```bash
# Basic usage (with TMDB API key set, auto-generates filename: Fight.Club.1999.mp4)
python3 vixsrc_downloader.py --movie 550

# Specify custom output filename
python3 vixsrc_downloader.py --movie 550 --output fight_club.mp4

# With quality selection
python3 vixsrc_downloader.py --movie 550 --quality 1080

# With specific language/audio track
python3 vixsrc_downloader.py --movie 550 --lang es

# Without metadata (uses basic filename: movie_550.mp4)
python3 vixsrc_downloader.py --movie 550 --no-metadata
```

### Download TV Shows

**Single Episode:**
```bash
# Download Breaking Bad S04E04 (auto-generates filename: Breaking.Bad.S04E04.Ozymandias.mp4)
python3 vixsrc_downloader.py --tv 60625 --season 4 --episode 4

# Specify custom output filename
python3 vixsrc_downloader.py --tv 60625 --season 4 --episode 4 --output bb_s04e04.mp4

# Without metadata (uses basic filename: tv_60625_s04e04.mp4)
python3 vixsrc_downloader.py --tv 60625 --season 4 --episode 4 --no-metadata
```

**Bulk Downloads (requires TMDB API key):**
```bash
# Download entire TV show (all seasons)
python3 vixsrc_downloader.py --tv 60625 --output-dir ./breaking_bad --parallel 3

# Download entire season
python3 vixsrc_downloader.py --tv 60625 --season 4 --output-dir ./bb_s4 --parallel 2

# Download season with specific quality and language
python3 vixsrc_downloader.py --tv 60625 --season 1 --quality 720 --lang en --parallel 3
```

**Features:**
- Automatically discovers all episodes using TMDB API
- Supports parallel processing for faster downloads
- Shows individual progress bars for each episode
- Generates descriptive filenames for all episodes

### Get Playlist URL Only

```bash
# Just print the HLS playlist URL without downloading
python3 vixsrc_downloader.py --movie 550 --url-only
```

### Command-Line Options

```
usage: vixsrc_downloader.py [-h] (--movie TMDB_ID | --tv TMDB_ID | --search TERM)
                             [--season N] [--episode N] [--output FILE]
                             [--output-dir DIR] [--quality QUALITY] [--url-only]
                             [--timeout SEC] [--lang LANG] [--tmdb-api-key KEY]
                             [--no-metadata] [--parallel N] [--ytdlp-concurrency N]

optional arguments:
  -h, --help            show this help message and exit
  --movie TMDB_ID       TMDB ID for a movie
  --tv TMDB_ID          TMDB ID for a TV show
  --search TERM         Search for movies and TV shows by title (requires TMDB API key)
  --season N            Season number (optional: if omitted with --tv, downloads all seasons)
  --episode N           Episode number (optional: if omitted with --tv, downloads whole season)
  --output FILE, -o FILE
                        Output file path (default: auto-generated from TMDB)
  --output-dir DIR, -d DIR
                        Output directory for auto-generated filenames
  --quality QUALITY, -q QUALITY
                        Video quality: best/worst/720/1080 (default: best)
  --url-only            Only print the playlist URL, don't download
  --timeout SEC         Request timeout in seconds (default: 30)
  --lang LANG           Language code for audio/subtitles (default: en)
  --tmdb-api-key KEY    TMDB API key (or set TMDB_API_KEY env var)
  --no-metadata         Disable TMDB metadata fetching for filenames
  --parallel N, -p N    Number of parallel downloads for bulk TV downloads (default: 1)
  --ytdlp-concurrency N Number of concurrent fragment downloads for yt-dlp (default: 5)
```

## Examples

```bash
# Search for content to find TMDB IDs
export TMDB_API_KEY="your_api_key"
python3 vixsrc_downloader.py --search "matrix"
python3 vixsrc_downloader.py --search "game of thrones"

# Download The Matrix (TMDB ID: 603) - auto-generates: The.Matrix.1999.mp4
python3 vixsrc_downloader.py --movie 603

# Download Game of Thrones S01E01 (TMDB ID: 1399) - auto-generates: Game.of.Thrones.S01E01.Winter.Is.Coming.mp4
python3 vixsrc_downloader.py --tv 1399 --season 1 --episode 1

# Download entire season of Game of Thrones (all episodes in Season 1)
python3 vixsrc_downloader.py --tv 1399 --season 1 --output-dir ./got_s1 --parallel 3

# Download all seasons of a TV show
python3 vixsrc_downloader.py --tv 60625 --output-dir ./breaking_bad --parallel 2

# Download in 720p quality with auto-generated filename
python3 vixsrc_downloader.py --movie 603 --quality 720

# Get URL for use with another tool
python3 vixsrc_downloader.py --movie 603 --url-only

# Download with Spanish audio
python3 vixsrc_downloader.py --movie 603 --lang es

# Download with Italian audio and 720p quality
python3 vixsrc_downloader.py --tv 1399 --season 1 --episode 1 --lang it --quality 720

# Use custom filename instead of auto-generated
python3 vixsrc_downloader.py --movie 603 --output my_custom_name.mp4
```

## Filename Formats

When TMDB API key is configured, the tool automatically generates descriptive filenames:

### Movies
- **Format:** `Title.Year.mp4`
- **Example:** `Fight.Club.1999.mp4`

### TV Shows
- **Format:** `Show.S##E##.Episode.mp4`
- **Example:** `Breaking.Bad.S04E04.Ozymandias.mp4`

Special characters that are invalid for filenames (`<>:"/\|?*`) are automatically removed, and the title is sanitized for filesystem compatibility.

**Note:** If no TMDB API key is set or `--no-metadata` is used, basic filenames will be used:
- Movies: `movie_{tmdb_id}.mp4` (e.g., `movie_550.mp4`)
- TV Shows: `tv_{tmdb_id}_s{season}e{episode}.mp4` (e.g., `tv_60625_s04e04.mp4`)

## How It Works

1. **Metadata Fetching** (if TMDB API key set): Fetches movie/TV show metadata from TMDB API
2. **URL Construction**: Builds the embed URL using TMDB ID
3. **Cloudflare Bypass**: Uses cloudscraper to bypass Cloudflare protection
4. **Page Parsing**: Fetches the embed page and extracts the HLS playlist URL with required parameters (h=1, lang, token, expires)
5. **Filename Generation**: Creates descriptive filename from metadata or uses basic format
6. **Download**: Uses yt-dlp or ffmpeg to download and merge the HLS stream into MP4

## Troubleshooting

### "Failed to get playlist URL"

This usually means:
- The content is not available on vixsrc.to
- The page structure has changed (requires script update)
- Network connectivity issues

**Note:** The script now uses cloudscraper to automatically bypass Cloudflare protection, so this error should be rare.

### "Neither yt-dlp nor ffmpeg found"

Install one of the downloaders:
```bash
pip install yt-dlp --break-system-packages
# or
sudo apt-get install ffmpeg
```

### Download is very slow

Try specifying a lower quality:
```bash
python3 vixsrc_downloader.py --movie 550 --quality 720
```

## Advanced Usage

### Using with MPV Player

Play directly without downloading:

```bash
# Get the playlist URL
URL=$(python3 vixsrc_downloader.py --movie 550 --url-only | grep "https://")

# Play with mpv
mpv "$URL"
```

## Technical Details

### Architecture

The project is organized into focused modules:

**Core Components:**
- **constants.py** - All configuration constants and regex patterns
- **utils.py** - Utility functions (filename sanitization, dependency management)

**Download Pipeline:**
- **extractor.py** (`PlaylistExtractor`) - Extracts HLS playlist URLs from vixsrc.to
  - Multiple extraction strategies with automatic fallback
  - Playlist verification and URL construction
- **downloader.py** (`VixSrcDownloader`, `DownloadExecutor`) - Core download functionality
  - Handles yt-dlp and ffmpeg download backends
  - Command building and execution management
- **progress.py** (`ProgressTracker`, `ProgressParser`) - Unified progress tracking
  - Supports both tqdm and rich progress bars
  - Parses yt-dlp/ffmpeg output for real-time updates

**Metadata & Parallel Downloads:**
- **metadata.py** (`TMDBMetadata`) - TMDB API integration
  - Fetches movie and TV show metadata
  - Generates descriptive filenames
- **batch.py** (`BatchDownloader`, `DownloadTask`) - Download orchestration
  - Manages bulk TV downloads
  - Handles parallel downloads with progress tracking

**Class Responsibilities:**

```
VixSrcDownloader
├── get_movie_url()        - Construct movie embed URL
├── get_tv_url()           - Construct TV show embed URL
├── extract_playlist_url() - Delegate to PlaylistExtractor
└── download_video()       - Download using yt-dlp/ffmpeg

PlaylistExtractor
├── extract()                      - Try all extraction strategies
├── _extract_from_master_playlist() - Strategy 1: window.masterPlaylist
├── _extract_from_direct_pattern()  - Strategy 2: Direct regex match
├── _extract_from_api_endpoints()   - Strategy 3: API endpoint discovery
└── _extract_from_video_id()        - Strategy 4: Video ID extraction

DownloadExecutor
├── build_ytdlp_command()   - Construct yt-dlp command
├── execute_with_progress() - Run with progress tracking
└── execute_simple()        - Run with native progress

TMDBMetadata
├── search_movies()           - Search for movies by title (returns list with availability check)
├── search_tv_shows()         - Search for TV shows by title (returns list with availability check)
├── get_movie_info()          - Fetch movie metadata from TMDB
├── get_tv_info()             - Fetch TV show metadata from TMDB
├── get_show_name()           - Get TV show name for display
├── get_all_seasons()         - Get all seasons for a TV show (for bulk downloads)
├── get_season_episodes()     - Get all episodes in a season (for bulk downloads)
├── generate_movie_filename() - Generate descriptive movie filename
└── generate_tv_filename()    - Generate descriptive TV filename

BatchDownloader
├── generate_bulk_tv_tasks()  - Generate tasks for bulk TV downloads
├── process_single_download() - Process one download task
└── download_batch()          - Execute downloads with parallel support

ProgressTracker
├── log()               - Conditional logging
├── update_percent()    - Update progress percentage
├── mark_complete()     - Mark task as complete/failed
└── has_progress_ui()   - Check if progress UI is active
```

### URL Pattern

- Movies: `https://vixsrc.to/movie/{tmdb_id}?lang={lang}`
- TV Shows: `https://vixsrc.to/tv/{tmdb_id}/{season}/{episode}?lang={lang}`
- Playlist: `https://vixsrc.to/playlist/{id}?token=...&expires=...&h=1&lang={lang}`

**Note:** The `h=1` parameter is required for the playlist URL to work correctly.

### Language Codes

The `--lang` parameter accepts ISO 639-1 language codes. Common examples:
- `en` - English (default)
- `es` - Spanish
- `fr` - French
- `de` - German
- `it` - Italian
- `pt` - Portuguese
- `ja` - Japanese
- `ko` - Korean

Note: Language availability depends on the content provider.

## License

This is free and unencumbered software released into the public domain.

## Disclaimer

This tool is provided as-is for educational purposes. The authors are not responsible for any misuse of this tool. Always respect copyright laws and terms of service.
