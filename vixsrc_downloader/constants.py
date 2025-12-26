"""Constants used throughout the VixSrc downloader."""

# Status icons
STATUS_ICON_SUCCESS = "✓"
STATUS_ICON_FAILURE = "✗"

# Default settings
DEFAULT_EXTENSION = "mp4"
DEFAULT_TIMEOUT = 30
DEFAULT_LANG = "en"
DEFAULT_QUALITY = "best"
DEFAULT_YTDLP_CONCURRENCY = 5

# VixSrc configuration
VIXSRC_BASE_URL = "https://vixsrc.to"
VIXSRC_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# File name sanitization
INVALID_FILENAME_CHARS = '<>:"/\\|?*'

# Regex patterns for extraction
PATTERN_MASTER_PLAYLIST = r'window\.masterPlaylist\s*=\s*\{[^}]*\{[^}]*\}[^}]*\}'
PATTERN_PLAYLIST_DIRECT = r'https://vixsrc\.to/playlist/(\d+)\?[^"\']*'
PATTERN_API_ENDPOINTS = r'["\'](/api/[^"\']+)["\']'
PATTERN_VIDEO_ID = r'video[_-]?id["\']?\s*[:=]\s*["\']?(\d+)'
PATTERN_DURATION = r'Duration:\s*(\d{2}):(\d{2}):(\d{2}\.\d+)'
PATTERN_FFMPEG_TIME = r'time=(\d{2}):(\d{2}):(\d{2}\.\d+)'
PATTERN_FFMPEG_BITRATE = r'bitrate=\s*(\d+\.?\d*)\s*([kmgt]?bits/s)'
PATTERN_YTDLP_PROGRESS = r'PROGRESS:(\d+\.?\d*)%'
