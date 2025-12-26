"""VixSrc Video Downloader - Download videos from vixsrc.to using TMDB IDs."""

from .batch import BatchDownloader, DownloadTask
from .downloader import VixSrcDownloader, DownloadExecutor
from .extractor import PlaylistExtractor
from .metadata import TMDBMetadata
from .progress import ProgressTracker, ProgressParser
from .utils import sanitize_filename, ensure_dependency

__version__ = "1.0.0"
__all__ = [
    "VixSrcDownloader",
    "DownloadExecutor",
    "PlaylistExtractor",
    "TMDBMetadata",
    "BatchDownloader",
    "DownloadTask",
    "ProgressTracker",
    "ProgressParser",
    "sanitize_filename",
    "ensure_dependency",
]
