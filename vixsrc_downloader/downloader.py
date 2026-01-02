"""Core download functionality."""

import os
import subprocess
from pathlib import Path
from typing import Optional, List

from .constants import (
    VIXSRC_BASE_URL,
    VIXSRC_USER_AGENT,
    DEFAULT_TIMEOUT,
    DEFAULT_LANG,
    DEFAULT_QUALITY,
    DEFAULT_YTDLP_CONCURRENCY,
    DEFAULT_EXTENSION
)
from .extractor import PlaylistExtractor
from .progress import ProgressTracker, ProgressParser

try:
    import cloudscraper
except ImportError:
    cloudscraper = None  # type: ignore

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None  # type: ignore


class DownloadExecutor:
    """Execute video downloads with progress tracking"""

    def __init__(self, base_url: str, ytdlp_concurrency: int):
        """
        Initialize executor.

        Args:
            base_url: VixSrc base URL for referer
            ytdlp_concurrency: Number of concurrent fragment downloads
        """
        self.base_url = base_url
        self.ytdlp_concurrency = ytdlp_concurrency

    def build_ytdlp_command(self, url: str, output: Path, quality: str, lang: str) -> List[str]:
        """
        Build yt-dlp command with appropriate flags.

        Args:
            url: Video URL
            output: Output path
            quality: Quality setting
            lang: Language code

        Returns:
            Command list for subprocess
        """
        # Determine format selection
        if quality.isdigit():
            format_selector = (
                f'bestvideo[height<={quality}]+bestaudio[language={lang}]/'
                f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]'
            )
        else:
            format_selector = (
                f'bestvideo+bestaudio[language={lang}]/'
                f'bestvideo+bestaudio/best'
            )

        cmd = [
            'yt-dlp',
            '-N', str(self.ytdlp_concurrency),
            '-f', format_selector,
            '--merge-output-format', DEFAULT_EXTENSION,
            '--referer', self.base_url,
            '--add-header', 'Accept: */*',
            '-o', str(output),
            '--newline',
            '--no-warnings',
            '--progress-template', 'download:PROGRESS:%(progress._percent_str)s',
            url
        ]

        return cmd

    def execute_with_progress(self, cmd: List[str], output: Path,
                             tracker: ProgressTracker) -> bool:
        """
        Execute yt-dlp with progress tracking.

        Args:
            cmd: Command to execute
            output: Output path
            tracker: Progress tracker

        Returns:
            True if successful
        """
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=0,
                env={**os.environ, 'PYTHONUNBUFFERED': '1'}
            )

            parser = ProgressParser(tracker, output.name)

            for line in process.stdout:  # type: ignore
                line = line.strip()
                if line:
                    parser.parse_line(line)

            process.wait()

            if process.returncode == 0:
                parser.finalize_success()
                return True
            else:
                parser.finalize_failure()
                return False

        except Exception as e:
            tracker.log(f"Exception: {e}", "!")
            tracker.mark_complete(False, f"{output.name} - Error")
            return False

class VixSrcDownloader:
    """Download videos from vixsrc.to"""

    BASE_URL = VIXSRC_BASE_URL

    def __init__(self, timeout: int = DEFAULT_TIMEOUT, lang: str = DEFAULT_LANG,
                 quiet: bool = False, ytdlp_concurrency: int = DEFAULT_YTDLP_CONCURRENCY):
        self.timeout = timeout
        self.lang = lang
        self.quiet = quiet
        self.ytdlp_concurrency = ytdlp_concurrency

        # Use cloudscraper to bypass Cloudflare protection
        if cloudscraper:
            self.session = cloudscraper.create_scraper()
            self.session.headers.update({
                'User-Agent': VIXSRC_USER_AGENT,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': self.BASE_URL
            })
        else:
            raise ImportError("cloudscraper is required")

        # Create executor for downloads
        self.executor = DownloadExecutor(self.BASE_URL, ytdlp_concurrency)

    def get_movie_url(self, tmdb_id: int) -> str:
        """Get the embed URL for a movie"""
        return f"{self.BASE_URL}/movie/{tmdb_id}?lang={self.lang}"

    def get_tv_url(self, tmdb_id: int, season: int, episode: int) -> str:
        """Get the embed URL for a TV show episode"""
        return f"{self.BASE_URL}/tv/{tmdb_id}/{season}/{episode}?lang={self.lang}"

    def extract_playlist_url(self, embed_url: str,
                            progress_tracker: Optional[ProgressTracker] = None) -> Optional[str]:
        """
        Extract the HLS playlist URL from the vixsrc embed page.

        Args:
            embed_url: Embed page URL
            progress_tracker: Optional progress tracker for logging

        Returns:
            Playlist URL or None
        """
        tracker = progress_tracker or ProgressTracker(quiet=self.quiet)
        extractor = PlaylistExtractor(self.session, self.BASE_URL,
                                     self.lang, self.timeout, tracker)
        return extractor.extract(embed_url)

    def get_playlist_url(self, tmdb_id: int, season: Optional[int] = None,
                         episode: Optional[int] = None,
                         progress_tracker: Optional[ProgressTracker] = None) -> Optional[str]:
        """
        Get the HLS playlist URL for a movie or TV show episode.

        Args:
            tmdb_id: The Movie Database ID
            season: Season number (for TV shows)
            episode: Episode number (for TV shows)
            progress_tracker: Optional progress tracker for logging

        Returns:
            The HLS playlist URL or None if not found
        """
        if season is not None and episode is not None:
            embed_url = self.get_tv_url(tmdb_id, season, episode)
        else:
            embed_url = self.get_movie_url(tmdb_id)

        return self.extract_playlist_url(embed_url, progress_tracker)

    def download_video(self, playlist_url: str, output_path: str,
                       quality: str = DEFAULT_QUALITY, progress_bar: Optional['tqdm'] = None,
                       rich_progress: Optional[tuple] = None) -> bool:
        """
        Download video from HLS playlist URL using yt-dlp or ffmpeg.

        Args:
            playlist_url: The HLS playlist URL
            output_path: Path to save the downloaded video
            quality: Quality selector (best/worst/specific height like 1080)
            progress_bar: Optional tqdm progress bar for tracking download progress
            rich_progress: Optional rich progress tuple for tracking

        Returns:
            True if download successful, False otherwise
        """
        output = Path(output_path)

        # Create progress tracker
        tracker = ProgressTracker(progress_bar, rich_progress, self.quiet)

        # Try yt-dlp first (better at handling HLS)
        if self._check_command('yt-dlp'):
            return self._download_with_ytdlp(playlist_url, output, quality, tracker)

        # Fall back to ffmpeg
        elif self._check_command('ffmpeg'):
            return self._download_with_ffmpeg(playlist_url, output, tracker)

        else:
            tracker.log("Error: Neither yt-dlp nor ffmpeg found.", "!")
            tracker.log("Install yt-dlp: pip install yt-dlp --break-system-packages")
            tracker.log("Or install ffmpeg: apt-get install ffmpeg")
            return False

    def _check_command(self, command: str) -> bool:
        """Check if a command is available in PATH"""
        try:
            subprocess.run([command, '--version'],
                          stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL,
                          check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _download_with_ytdlp(self, url: str, output: Path,
                            quality: str, tracker: ProgressTracker) -> bool:
        """Download using yt-dlp with progress tracking"""
        cmd = self.executor.build_ytdlp_command(url, output, quality, self.lang)
        return self.executor.execute_with_progress(cmd, output, tracker)

    def _download_with_ffmpeg(self, url: str, output: Path, tracker: ProgressTracker) -> bool:
        """Download using ffmpeg"""
        tracker.log(f"Downloading with ffmpeg to: {output}")

        cmd = [
            'ffmpeg',
            '-i', url,
            '-c', 'copy',
            '-bsf:a', 'aac_adtstoasc',
            '-y',  # Overwrite output file
            str(output)
        ]

        try:
            subprocess.run(cmd, check=True)
            tracker.log(f"Download completed: {output}", "+")
            return True
        except subprocess.CalledProcessError as e:
            tracker.log(f"Download failed: {e}", "!")
            return False
