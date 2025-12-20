# VixSrc Downloader - Project Structure

## File Overview

```
vixsrc-downloader/
├── vixsrc_downloader.py    # Main downloader script (Python)
├── batch_download.sh        # Batch download helper (Bash)
├── setup.sh                 # Installation script
├── requirements.txt         # Python dependencies
├── downloads.txt.example    # Example batch download list
└── README.md               # Main documentation
```

## File Descriptions

### vixsrc_downloader.py
The main Python script that handles downloading videos from vixsrc.to.

**Key Features:**
- Constructs embed URLs from TMDB IDs
- Extracts HLS playlist URLs from embed pages
- Downloads videos using yt-dlp or ffmpeg
- Supports quality selection
- Command-line interface

**Class: VixSrcDownloader**
- `get_movie_url(tmdb_id)` - Construct movie embed URL
- `get_tv_url(tmdb_id, season, episode)` - Construct TV show embed URL
- `extract_playlist_url(embed_url)` - Extract HLS URL from page
- `get_playlist_url(...)` - Main method to get playlist URL
- `download_video(url, output, quality)` - Download the video

### batch_download.sh
Bash script for downloading multiple videos from a list.

**Features:**
- Process multiple downloads sequentially
- Support for both movies and TV shows
- Color-coded output
- Download statistics

**Usage:**
```bash
./batch_download.sh downloads.txt
```

### setup.sh
Installation and setup script.

**What it does:**
- Checks Python version
- Installs Python dependencies
- Checks for yt-dlp/ffmpeg
- Makes scripts executable
- Provides usage examples

### requirements.txt
Python package dependencies:
- `requests` - HTTP library for API calls
- `yt-dlp` - Video downloader (recommended)

### downloads.txt.example
Example file showing format for batch downloads.

**Format:**
```
tv TMDB_ID SEASON EPISODE [OUTPUT_FILE]
movie TMDB_ID [OUTPUT_FILE]
```

## Quick Start

1. **Install dependencies:**
   ```bash
   ./setup.sh
   ```

2. **Download a movie:**
   ```bash
   ./vixsrc_downloader.py --movie 550 --output fight_club.mp4
   ```

3. **Download TV episode:**
   ```bash
   ./vixsrc_downloader.py --tv 60625 --season 4 --episode 4
   ```

4. **Batch download:**
   ```bash
   cp downloads.txt.example downloads.txt
   # Edit downloads.txt
   ./batch_download.sh downloads.txt
   ```

## Technical Implementation

### URL Pattern Recognition
The script uses regex patterns to extract playlist URLs:
```python
playlist_pattern = r'https://vixsrc\.to/playlist/(\d+)\?[^"\']*'
```

### Download Methods
1. **yt-dlp** (preferred):
   - Better HLS stream handling
   - Automatic format selection
   - Quality filtering

2. **ffmpeg** (fallback):
   - Direct stream copy
   - No transcoding (faster)
   - Simpler but less flexible

### Error Handling
- Network request errors
- Missing playlist URLs
- Download failures
- Invalid input validation

## Architecture Diagram

```
User Input (TMDB ID)
        ↓
Construct Embed URL
        ↓
Fetch Embed Page (HTTP GET)
        ↓
Extract Playlist URL (Regex)
        ↓
Download Video (yt-dlp/ffmpeg)
        ↓
Save to File (MP4)
```

## API Flow

1. **Embed Page Request:**
   - URL: `https://vixsrc.to/movie/{id}` or `https://vixsrc.to/tv/{id}/{s}/{e}`
   - Method: GET
   - Response: HTML with embedded player

2. **Playlist URL Extraction:**
   - Parse HTML for playlist endpoint
   - Pattern: `/playlist/{id}?token=...&expires=...`
   - Returns: HLS master playlist URL

3. **Video Download:**
   - Input: HLS playlist URL
   - Tool: yt-dlp or ffmpeg
   - Output: MP4 file

## Customization

### Adding New Features

1. **Add subtitle support:**
   ```python
   def download_subtitles(self, playlist_url, output):
       # Implementation here
   ```

2. **Add proxy support:**
   ```python
   self.session.proxies = {
       'http': 'http://proxy:port',
       'https': 'https://proxy:port'
   }
   ```

3. **Add resume capability:**
   - Use yt-dlp's `--continue` flag
   - Track partially downloaded files

### Extending the Batch Downloader

Add support for movie lists:
```bash
# In batch_download.sh
elif [ "$TYPE" == "search" ]; then
    # Implement TMDB search
fi
```

## Troubleshooting

### Common Issues

1. **"Failed to get playlist URL"**
   - Content not available on vixsrc.to
   - Page structure changed
   - Check embed URL manually in browser

2. **"Neither yt-dlp nor ffmpeg found"**
   - Run `./setup.sh` again
   - Install manually: `pip install yt-dlp --break-system-packages`

3. **Download stuck/slow**
   - Try lower quality: `--quality 720`
   - Check network connection
   - Try at different time

## Development Notes

### Testing
```bash
# Test URL extraction only
./vixsrc_downloader.py --movie 550 --url-only

# Test with known working TMDB ID
./vixsrc_downloader.py --movie 550 --output test.mp4
```

### Debugging
Enable verbose output by adding print statements:
```python
print(f"[DEBUG] HTML content length: {len(html_content)}")
print(f"[DEBUG] Found patterns: {matches}")
```

### Performance
- Uses `requests.Session()` for connection pooling
- Timeout configurable via `--timeout` flag
- Downloads in highest available quality by default

## Legal & Ethical Notes

- Educational purpose only
- Only download content you have rights to
- Respect copyright laws
- Terms of service compliance

## Future Enhancements

Potential features to add:
- [ ] Multi-threaded batch downloads
- [ ] Resume interrupted downloads
- [ ] TMDB API integration for metadata
- [ ] Subtitle extraction
- [ ] Quality pre-selection
- [ ] Download queue management
- [ ] Progress bar for downloads
- [ ] Web UI interface
- [ ] Docker container
- [ ] Automatic retry on failure

## Version History

**v1.0 - Initial Release**
- Basic movie/TV show download
- yt-dlp and ffmpeg support
- Batch download capability
- Quality selection
- URL-only mode
