"""Core download functionality."""

import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional, List, Tuple

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


class MultiLanguageDownloader:
    """Handle multi-language audio track downloads"""

    def __init__(self, downloader: 'VixSrcDownloader', executor: DownloadExecutor):
        self.downloader = downloader
        self.executor = executor

    def download_multi_audio(self, playlist_urls: List[Tuple[str, str]],
                            output_path: str, quality: str,
                            tracker: ProgressTracker) -> bool:
        """Download video with multiple audio tracks"""

        temp_dir = tempfile.mkdtemp(prefix='vixsrc_')
        temp_path = Path(temp_dir)

        try:
            # 1. Download primary language (video+audio)
            primary_lang, primary_url = playlist_urls[0]
            video_file = temp_path / f"video_{primary_lang}.mp4"

            tracker.log(f"Downloading {primary_lang} (video+audio)")
            cmd = self.executor.build_ytdlp_command(primary_url, video_file,
                                                   quality, primary_lang)
            if not self.executor.execute_with_progress(cmd, video_file, tracker):
                return False

            # If single language, just move file
            if len(playlist_urls) == 1:
                shutil.move(str(video_file), output_path)
                return True

            # 2. Download additional audio tracks
            audio_files = []
            successful_langs = [primary_lang]

            for lang, url in playlist_urls[1:]:
                audio_file = temp_path / f"audio_{lang}.m4a"
                tracker.log(f"Downloading {lang} audio")

                if self._download_audio_only(url, audio_file, lang, tracker):
                    audio_files.append((lang, audio_file))
                    successful_langs.append(lang)
                else:
                    tracker.log(f"Warning: Failed {lang}, skipping", "!")

            # 3. Merge with ffmpeg
            tracker.log(f"Merging {len(successful_langs)} tracks...")
            if self._merge_audio_tracks(video_file, audio_files, output_path, tracker):
                tracker.log(f"Success: {', '.join(successful_langs)}", "+")
                return True
            return False

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _download_audio_only(self, url: str, output: Path, lang: str,
                            tracker: ProgressTracker) -> bool:
        """Download audio-only track

        Note: The playlist URL already contains the language-specific audio
        because it was requested with ?lang={lang}. We just need to download
        the best audio stream without language filtering.
        """
        tracker.log(f"  Downloading {lang} audio from language-specific playlist...")

        # Download best audio stream (playlist URL already has correct language)
        cmd = [
            'yt-dlp',
            '-f', 'bestaudio',
            '--referer', self.downloader.BASE_URL,
            '--add-header', 'Accept: */*',
            '-o', str(output),
            '--newline',
            '--progress-template', 'download:PROGRESS:%(progress._percent_str)s',
            url
        ]

        try:
            # Show progress by streaming output
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            # Track progress from yt-dlp output
            last_percent = None
            for line in process.stdout:
                line = line.strip()
                if line:
                    # Look for progress indicators
                    if 'PROGRESS:' in line:
                        try:
                            percent_str = line.split('PROGRESS:')[1].strip()
                            if percent_str != last_percent:
                                tracker.log(f"  {lang} audio: {percent_str}")
                                last_percent = percent_str
                        except Exception:
                            pass
                    # Also show other important messages
                    elif '[download]' in line or 'Downloading' in line:
                        tracker.log(f"  {line}")

            process.wait()

            if process.returncode == 0 and output.exists():
                tracker.log(f"  ✓ Downloaded {lang} audio successfully")
                return True
            else:
                tracker.log(f"  ✗ Failed to download {lang} audio (exit code: {process.returncode})", "!")
                return False

        except Exception as e:
            tracker.log(f"  ✗ Error downloading {lang} audio: {e}", "!")
            return False

    def _merge_audio_tracks(self, video_file: Path,
                           audio_files: List[Tuple[str, Path]],
                           output_path: str, tracker: ProgressTracker) -> bool:
        """Merge video + audio tracks with ffmpeg"""

        # Language code to name mapping
        lang_names = {
            'en': 'English', 'it': 'Italian', 'es': 'Spanish', 'fr': 'French',
            'de': 'German', 'pt': 'Portuguese', 'ru': 'Russian', 'ja': 'Japanese',
            'zh': 'Chinese', 'ko': 'Korean', 'ar': 'Arabic', 'hi': 'Hindi',
            'pl': 'Polish', 'nl': 'Dutch', 'tr': 'Turkish', 'sv': 'Swedish',
            'no': 'Norwegian', 'da': 'Danish', 'fi': 'Finnish', 'cs': 'Czech',
            'hu': 'Hungarian', 'ro': 'Romanian', 'el': 'Greek', 'he': 'Hebrew',
            'th': 'Thai', 'vi': 'Vietnamese', 'id': 'Indonesian', 'ms': 'Malay',
            'uk': 'Ukrainian', 'bg': 'Bulgarian', 'hr': 'Croatian', 'sr': 'Serbian',
            'sk': 'Slovak', 'sl': 'Slovenian', 'lt': 'Lithuanian', 'lv': 'Latvian',
            'et': 'Estonian', 'ca': 'Catalan', 'eu': 'Basque', 'gl': 'Galician'
        }

        # Get the primary language (from video file)
        primary_lang = self.downloader.languages[0]
        primary_lang_name = lang_names.get(primary_lang, primary_lang.upper())

        tracker.log(f"  Building ffmpeg command...")
        tracker.log(f"  Primary audio: {primary_lang} ({primary_lang_name})")
        for lang, _ in audio_files:
            lang_name = lang_names.get(lang, lang.upper())
            tracker.log(f"  Additional audio: {lang} ({lang_name})")

        cmd = ['ffmpeg', '-i', str(video_file)]

        # Add audio inputs
        for lang, audio_path in audio_files:
            cmd.extend(['-i', str(audio_path)])

        # Map video and primary audio
        cmd.extend(['-map', '0:v:0', '-map', '0:a:0'])

        # Map additional audio tracks
        for i in range(len(audio_files)):
            cmd.extend(['-map', f'{i+1}:a:0'])

        # Copy codecs (no re-encoding)
        cmd.extend(['-c', 'copy'])

        # Set disposition: first audio as default, others as non-default
        cmd.extend(['-disposition:a:0', 'default'])
        for i in range(len(audio_files)):
            cmd.extend([f'-disposition:a:{i+1}', '0'])  # Clear default flag

        # Add metadata for PRIMARY audio track (language + title)
        cmd.extend([
            '-metadata:s:a:0', f'language={primary_lang}',
            '-metadata:s:a:0', f'title={primary_lang_name}'
        ])

        # Add metadata for ADDITIONAL audio tracks (language + title)
        for i, (lang, _) in enumerate(audio_files):
            lang_name = lang_names.get(lang, lang.upper())
            cmd.extend([
                f'-metadata:s:a:{i+1}', f'language={lang}',
                f'-metadata:s:a:{i+1}', f'title={lang_name}'
            ])

        cmd.extend(['-y', output_path])

        tracker.log(f"  Running ffmpeg merge...")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            if Path(output_path).exists():
                tracker.log(f"  Merge successful!")
                return True
            return False
        except subprocess.CalledProcessError as e:
            tracker.log(f"  ffmpeg error: {e.stderr[:200]}", "!")
            return False


class VixSrcDownloader:
    """Download videos from vixsrc.to"""

    BASE_URL = VIXSRC_BASE_URL

    def __init__(self, timeout: int = DEFAULT_TIMEOUT, languages: List[str] = None,
                 quiet: bool = False, ytdlp_concurrency: int = DEFAULT_YTDLP_CONCURRENCY):
        self.timeout = timeout
        self.languages = languages or [DEFAULT_LANG]
        self.lang = self.languages[0]  # Backward compatibility
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

        # Create multi-language downloader
        self.multi_lang_downloader = None  # Will be initialized when needed

    def get_movie_url(self, tmdb_id: int, lang: str = None) -> str:
        """Get the embed URL for a movie"""
        language = lang or self.lang
        return f"{self.BASE_URL}/movie/{tmdb_id}?lang={language}"

    def get_tv_url(self, tmdb_id: int, season: int, episode: int, lang: str = None) -> str:
        """Get the embed URL for a TV show episode"""
        language = lang or self.lang
        return f"{self.BASE_URL}/tv/{tmdb_id}/{season}/{episode}?lang={language}"

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

        # Extract language from embed_url (?lang=XX)
        import re
        lang_match = re.search(r'[?&]lang=([a-z]{2})', embed_url)
        lang_for_playlist = lang_match.group(1) if lang_match else self.lang

        extractor = PlaylistExtractor(self.session, self.BASE_URL,
                                     lang_for_playlist, self.timeout, tracker)
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
                       rich_progress: Optional[tuple] = None,
                       tmdb_id: int = None, season: int = None, episode: int = None) -> bool:
        """
        Download video from HLS playlist URL using yt-dlp or ffmpeg.

        Args:
            playlist_url: The HLS playlist URL
            output_path: Path to save the downloaded video
            quality: Quality selector (best/worst/specific height like 1080)
            progress_bar: Optional tqdm progress bar for tracking download progress
            rich_progress: Optional rich progress tuple for tracking
            tmdb_id: TMDB ID (required for multi-language)
            season: Season number (for TV shows)
            episode: Episode number (for TV shows)

        Returns:
            True if download successful, False otherwise
        """
        output = Path(output_path)

        # Create progress tracker
        tracker = ProgressTracker(progress_bar, rich_progress, self.quiet)

        # Check if multi-language
        if len(self.languages) > 1:
            if not tmdb_id:
                tracker.log("Multi-language requires tmdb_id", "!")
                return False
            return self._download_multi_language(tmdb_id, season, episode,
                                                output_path, quality, tracker)

        # Single language (existing logic)
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

    def _download_multi_language(self, tmdb_id: int, season: Optional[int],
                                episode: Optional[int], output_path: str,
                                quality: str, tracker: ProgressTracker) -> bool:
        """Download with multiple audio tracks"""

        # Get playlist URLs for each language
        playlist_urls = []
        for lang in self.languages:
            tracker.log(f"Fetching playlist for: {lang}")

            # Get embed URL
            if season is not None and episode is not None:
                embed_url = self.get_tv_url(tmdb_id, season, episode, lang)
            else:
                embed_url = self.get_movie_url(tmdb_id, lang)

            # Extract playlist
            playlist_url = self.extract_playlist_url(embed_url, tracker)

            if not playlist_url:
                if lang == self.languages[0]:
                    tracker.log(f"Failed to get primary language: {lang}", "!")
                    return False
                else:
                    tracker.log(f"Warning: Could not get {lang}, skipping", "!")
                    continue

            playlist_urls.append((lang, playlist_url))
            tracker.log(f"Got playlist for {lang}: {playlist_url[:80]}...")

        if not playlist_urls:
            return False

        # Initialize multi-language downloader if needed
        if not self.multi_lang_downloader:
            self.multi_lang_downloader = MultiLanguageDownloader(self, self.executor)

        # Download and merge
        return self.multi_lang_downloader.download_multi_audio(
            playlist_urls, output_path, quality, tracker
        )

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
