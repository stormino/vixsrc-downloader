#!/usr/bin/env python3
"""
VixSrc Video Downloader

A tool to download videos from vixsrc.to using TMDB IDs.
Downloads HLS streams and converts them to MP4.
Automatically generates descriptive filenames from TMDB metadata.
Supports batch downloads with parallel processing.

Usage:
    # Download a movie (auto-generates: Fight.Club.1999.mp4)
    export TMDB_API_KEY="your_api_key"
    python vixsrc_downloader.py --movie 550

    # Download a TV show episode (auto-generates: Breaking.Bad.S04E04.Ozymandias.mp4)
    python vixsrc_downloader.py --tv 60625 --season 4 --episode 4

    # Batch download from file
    python vixsrc_downloader.py --batch downloads.txt --output-dir ./videos

    # Batch download with 3 parallel jobs
    python vixsrc_downloader.py --batch downloads.txt --parallel 3

    # Just get the playlist URL
    python vixsrc_downloader.py --movie 550 --url-only

    # Use custom filename
    python vixsrc_downloader.py --movie 550 --output fight_club.mp4

WARNING: Only download content you have legal rights to access.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
from urllib.parse import urljoin, urlparse, parse_qs

try:
    import requests
except ImportError:
    print("Error: 'requests' library not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "--break-system-packages"])
    import requests

try:
    import cloudscraper
except ImportError:
    print("Error: 'cloudscraper' library not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "cloudscraper", "--break-system-packages"])
    import cloudscraper

try:
    import tmdbsimple as tmdb
except ImportError:
    print("Error: 'tmdbsimple' library not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "tmdbsimple", "--break-system-packages"])
    import tmdbsimple as tmdb

try:
    from tqdm import tqdm
except ImportError:
    print("Error: 'tqdm' library not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "tqdm", "--break-system-packages"])
    from tqdm import tqdm


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing invalid characters.

    Args:
        filename: The filename to sanitize

    Returns:
        Sanitized filename safe for filesystem use
    """
    # Remove invalid characters for most filesystems
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '')

    # Replace multiple spaces with single space
    filename = re.sub(r'\s+', ' ', filename)

    # Remove leading/trailing spaces and dots
    filename = filename.strip(' .')

    return filename


class TMDBMetadata:
    """Helper class to fetch metadata from TMDB API"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize TMDB metadata fetcher.

        Args:
            api_key: TMDB API key. If not provided, will try to read from
                    TMDB_API_KEY environment variable.
        """
        self.api_key = api_key or os.getenv('TMDB_API_KEY')
        if self.api_key:
            tmdb.API_KEY = self.api_key

    def get_movie_info(self, tmdb_id: int) -> Optional[Dict[str, Any]]:
        """
        Get movie metadata from TMDB.

        Args:
            tmdb_id: TMDB movie ID

        Returns:
            Dictionary with title, year, and other metadata, or None if API key not set
        """
        if not self.api_key:
            return None

        try:
            movie = tmdb.Movies(tmdb_id)
            info = movie.info()

            # Extract year from release_date (format: YYYY-MM-DD)
            year = None
            if info.get('release_date'):
                year = info['release_date'].split('-')[0]

            return {
                'title': info.get('title', ''),
                'year': year,
                'original_title': info.get('original_title', ''),
                'overview': info.get('overview', '')
            }
        except Exception as e:
            print(f"[!] Warning: Failed to fetch movie metadata: {e}")
            return None

    def get_tv_info(self, tmdb_id: int, season: int, episode: int) -> Optional[Dict[str, Any]]:
        """
        Get TV show episode metadata from TMDB.

        Args:
            tmdb_id: TMDB TV show ID
            season: Season number
            episode: Episode number

        Returns:
            Dictionary with show name, episode name, and other metadata, or None if API key not set
        """
        if not self.api_key:
            return None

        try:
            # Get show info
            show = tmdb.TV(tmdb_id)
            show_info = show.info()
            show_name = show_info.get('name', '')

            # Get episode info
            episode_obj = tmdb.TV_Episodes(tmdb_id, season, episode)
            episode_info = episode_obj.info()
            episode_name = episode_info.get('name', '')

            return {
                'show_name': show_name,
                'episode_name': episode_name,
                'season': season,
                'episode': episode,
                'overview': episode_info.get('overview', '')
            }
        except Exception as e:
            print(f"[!] Warning: Failed to fetch TV show metadata: {e}")
            return None

    def generate_movie_filename(self, tmdb_id: int, extension: str = 'mp4') -> str:
        """
        Generate a descriptive filename for a movie.
        Format: Title.Year.mp4

        Args:
            tmdb_id: TMDB movie ID
            extension: File extension (default: mp4)

        Returns:
            Generated filename or fallback if metadata unavailable
        """
        info = self.get_movie_info(tmdb_id)

        if info and info.get('title'):
            title = info['title'].replace(' ', '.')
            title = sanitize_filename(title)

            if info.get('year'):
                filename = f"{title}.{info['year']}.{extension}"
            else:
                filename = f"{title}.{extension}"
        else:
            # Fallback to basic format
            filename = f"movie_{tmdb_id}.{extension}"

        return filename

    def generate_tv_filename(self, tmdb_id: int, season: int, episode: int,
                            extension: str = 'mp4') -> str:
        """
        Generate a descriptive filename for a TV episode.
        Format: Show.S##E##.Episode.mp4

        Args:
            tmdb_id: TMDB TV show ID
            season: Season number
            episode: Episode number
            extension: File extension (default: mp4)

        Returns:
            Generated filename or fallback if metadata unavailable
        """
        info = self.get_tv_info(tmdb_id, season, episode)

        if info and info.get('show_name'):
            show = info['show_name'].replace(' ', '.')
            show = sanitize_filename(show)

            season_ep = f"S{season:02d}E{episode:02d}"

            if info.get('episode_name'):
                ep_name = info['episode_name'].replace(' ', '.')
                ep_name = sanitize_filename(ep_name)
                filename = f"{show}.{season_ep}.{ep_name}.{extension}"
            else:
                filename = f"{show}.{season_ep}.{extension}"
        else:
            # Fallback to basic format
            filename = f"tv_{tmdb_id}_s{season:02d}e{episode:02d}.{extension}"

        return filename


class VixSrcDownloader:
    """Download videos from vixsrc.to"""

    BASE_URL = "https://vixsrc.to"

    def __init__(self, timeout: int = 30, lang: str = 'en', quiet: bool = False, ytdlp_concurrency: int = 5):
        self.timeout = timeout
        self.lang = lang
        self.quiet = quiet  # Suppress verbose logging when using progress bars
        self.ytdlp_concurrency = ytdlp_concurrency
        # Use cloudscraper to bypass Cloudflare protection
        self.session = cloudscraper.create_scraper()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': self.BASE_URL
        })
    
    def get_movie_url(self, tmdb_id: int) -> str:
        """Get the embed URL for a movie"""
        return f"{self.BASE_URL}/movie/{tmdb_id}?lang={self.lang}"
    
    def get_tv_url(self, tmdb_id: int, season: int, episode: int) -> str:
        """Get the embed URL for a TV show episode"""
        return f"{self.BASE_URL}/tv/{tmdb_id}/{season}/{episode}?lang={self.lang}"
    
    def extract_playlist_url(self, embed_url: str) -> Optional[str]:
        """
        Extract the HLS playlist URL from the vixsrc embed page.

        The page loads a player that makes API calls to get the actual playlist.
        We need to reverse-engineer this to get the direct playlist URL.
        """
        if not self.quiet:
            print(f"[*] Fetching embed page: {embed_url}")
        
        try:
            # First, get the embed page
            response = self.session.get(embed_url, timeout=self.timeout)
            response.raise_for_status()
            html_content = response.text
            
            # Look for the playlist endpoint in the page source
            # First try: window.masterPlaylist object with params
            # Extract components separately since order may vary
            # Pattern handles nested braces in the params object
            master_playlist_section = re.search(r'window\.masterPlaylist\s*=\s*\{[^}]*\{[^}]*\}[^}]*\}', html_content)

            if master_playlist_section:
                section_text = master_playlist_section.group(0)

                # Extract URL, token, and expires from the section
                url_match = re.search(r"url:\s*['\"]([^'\"]+)['\"]", section_text)
                token_match = re.search(r"['\"]token['\"]\s*:\s*['\"]([^'\"]+)['\"]", section_text)
                expires_match = re.search(r"['\"]expires['\"]\s*:\s*['\"]([^'\"]+)['\"]", section_text)

                if url_match and token_match and expires_match:
                    playlist_base_url = url_match.group(1)
                    token = token_match.group(1)
                    expires = expires_match.group(1)

                    # Extract ASN if present (usually empty)
                    asn_match = re.search(r"['\"]asn['\"]\s*:\s*['\"]([^'\"]*)['\"]", section_text)
                    asn = asn_match.group(1) if asn_match else ""

                    # Construct full URL with authentication parameters
                    # IMPORTANT: Add h=1 and lang parameters as required by vixsrc.to
                    params = []
                    params.append(f"token={token}")
                    params.append(f"expires={expires}")
                    if asn:  # Only add if not empty
                        params.append(f"asn={asn}")
                    params.append("h=1")  # Required parameter
                    params.append(f"lang={self.lang}")  # Language parameter

                    # Check if base URL already has query parameters
                    separator = '&' if '?' in playlist_base_url else '?'
                    playlist_url = f"{playlist_base_url}{separator}{'&'.join(params)}"

                    # Clean up any HTML entities
                    playlist_url = playlist_url.replace('&amp;', '&')
                    if not self.quiet:
                        print(f"[+] Constructed playlist URL with required parameters")

                    # Verify the playlist URL works
                    try:
                        if not self.quiet:
                            print(f"[*] Verifying playlist URL...")
                        headers = {'Referer': embed_url, 'Accept': '*/*'}
                        playlist_response = self.session.get(playlist_url, headers=headers, timeout=self.timeout)

                        if playlist_response.ok and playlist_response.text.startswith('#EXTM3U'):
                            if not self.quiet:
                                print(f"[+] Playlist URL verified successfully")
                            return playlist_url
                        else:
                            if not self.quiet:
                                print(f"[!] Playlist verification failed: {playlist_response.status_code}")
                    except Exception as e:
                        if not self.quiet:
                            print(f"[!] Playlist verification error: {e}")

                    # Return the URL anyway, it should work
                    return playlist_url

            # Second try: VixSrc typically exposes a playlist endpoint like /playlist/{id}?token=...
            playlist_pattern = r'https://vixsrc\.to/playlist/(\d+)\?[^"\']*'
            match = re.search(playlist_pattern, html_content)

            if match:
                playlist_url = match.group(0)
                # Clean up any HTML entities
                playlist_url = playlist_url.replace('&amp;', '&')
                if not self.quiet:
                    print(f"[+] Found playlist URL: {playlist_url}")
                return playlist_url

            # Alternative: Look for API calls in JavaScript
            # Pattern: /api/source or similar endpoints
            api_pattern = r'["\'](/api/[^"\']+)["\']'
            api_matches = re.findall(api_pattern, html_content)

            if api_matches:
                if not self.quiet:
                    print(f"[*] Found API endpoints: {api_matches}")
                # Try to construct the playlist URL from API responses
                for api_path in api_matches:
                    api_url = urljoin(self.BASE_URL, api_path)
                    try:
                        api_response = self.session.get(api_url, timeout=self.timeout)
                        if api_response.ok:
                            try:
                                data = api_response.json()
                                # Look for HLS/m3u8 URLs in the response
                                if isinstance(data, dict):
                                    for key, value in data.items():
                                        if isinstance(value, str) and ('m3u8' in value or 'playlist' in value):
                                            if not self.quiet:
                                                print(f"[+] Found playlist URL from API: {value}")
                                            return value
                            except json.JSONDecodeError:
                                pass
                    except Exception as e:
                        if not self.quiet:
                            print(f"[!] API call failed for {api_url}: {e}")
            
            # Try to extract video ID and construct playlist URL
            video_id_pattern = r'video[_-]?id["\']?\s*[:=]\s*["\']?(\d+)'
            video_id_match = re.search(video_id_pattern, html_content, re.IGNORECASE)
            
            if video_id_match:
                video_id = video_id_match.group(1)
                # Try common playlist URL patterns
                possible_urls = [
                    f"{self.BASE_URL}/playlist/{video_id}",
                    f"{self.BASE_URL}/api/playlist/{video_id}",
                ]
                
                for test_url in possible_urls:
                    try:
                        test_response = self.session.get(test_url, timeout=self.timeout, allow_redirects=True)
                        if test_response.ok and ('m3u8' in test_response.text or test_response.headers.get('content-type', '').startswith('application/')):
                            if not self.quiet:
                                print(f"[+] Found valid playlist URL: {test_response.url}")
                            return test_response.url
                    except Exception:
                        pass

            if not self.quiet:
                print("[!] Could not extract playlist URL from page")
                print("[*] Page may require JavaScript execution or the format has changed")
            return None

        except requests.RequestException as e:
            if not self.quiet:
                print(f"[!] Error fetching embed page: {e}")
            return None
    
    def get_playlist_url(self, tmdb_id: int, season: Optional[int] = None, 
                         episode: Optional[int] = None) -> Optional[str]:
        """
        Get the HLS playlist URL for a movie or TV show episode.
        
        Args:
            tmdb_id: The Movie Database ID
            season: Season number (for TV shows)
            episode: Episode number (for TV shows)
            
        Returns:
            The HLS playlist URL or None if not found
        """
        if season is not None and episode is not None:
            embed_url = self.get_tv_url(tmdb_id, season, episode)
        else:
            embed_url = self.get_movie_url(tmdb_id)
        
        return self.extract_playlist_url(embed_url)
    
    def download_video(self, playlist_url: str, output_path: str,
                       quality: str = 'best', progress_bar: Optional[tqdm] = None) -> bool:
        """
        Download video from HLS playlist URL using yt-dlp or ffmpeg.

        Args:
            playlist_url: The HLS playlist URL
            output_path: Path to save the downloaded video
            quality: Quality selector (best/worst/specific height like 1080)
            progress_bar: Optional tqdm progress bar for tracking download progress

        Returns:
            True if download successful, False otherwise
        """
        output_path = Path(output_path) # type: ignore

        # Try yt-dlp first (better at handling HLS)
        if self._check_command('yt-dlp'):
            return self._download_with_ytdlp(playlist_url, output_path, quality, progress_bar) # type: ignore

        # Fall back to ffmpeg
        elif self._check_command('ffmpeg'):
            return self._download_with_ffmpeg(playlist_url, output_path) # type: ignore

        else:
            print("[!] Error: Neither yt-dlp nor ffmpeg found.")
            print("[*] Install yt-dlp: pip install yt-dlp --break-system-packages")
            print("[*] Or install ffmpeg: apt-get install ffmpeg")
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
    
    def _download_with_ytdlp(self, url: str, output: Path, quality: str, progress_bar: Optional[tqdm] = None) -> bool:
        """Download using yt-dlp with progress tracking"""

        # Determine format selection based on quality
        if quality.isdigit():
            # Select video with specified height + audio (prefer specified language)
            format_selector = f'bestvideo[height<={quality}]+bestaudio[language={self.lang}]/bestvideo[height<={quality}]+bestaudio/best[height<={quality}]'
        else:
            # For 'best', select best video + audio with language preference
            format_selector = f'bestvideo+bestaudio[language={self.lang}]/bestvideo+bestaudio/best'

        cmd = [
            'yt-dlp',
            '-N', str(self.ytdlp_concurrency),
            '--no-warnings',
            '--newline',
            '--progress',
            '-f', format_selector,
            '--merge-output-format', 'mp4',
            '--referer', self.BASE_URL,
            '--add-header', 'Accept: */*',
            '-o', str(output),
            url
        ]

        try:
            # Run yt-dlp and capture output for progress tracking
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )

            if progress_bar:
                progress_bar.set_description(f"Downloading {output.name}")

            # Parse yt-dlp output for progress
            for line in process.stdout: # type: ignore
                if progress_bar:
                    # Look for download progress patterns
                    # yt-dlp outputs like: [download]  45.2% of   1.23GiB at  2.34MiB/s ETA 00:25
                    if '[download]' in line and '%' in line:
                        try:
                            # Extract percentage
                            match = re.search(r'(\d+\.?\d*)%', line)
                            if match:
                                percent = float(match.group(1))
                                progress_bar.n = percent
                                progress_bar.refresh()
                        except:
                            pass

            process.wait()

            if process.returncode == 0:
                if progress_bar:
                    progress_bar.n = 100
                    progress_bar.set_description(f"✓ {output.name}")
                    progress_bar.refresh()
                return True
            else:
                if progress_bar:
                    progress_bar.set_description(f"✗ {output.name}")
                    progress_bar.refresh()
                return False

        except Exception as e:
            if progress_bar:
                progress_bar.set_description(f"✗ {output.name} - {str(e)}")
                progress_bar.refresh()
            return False
    
    def _download_with_ffmpeg(self, url: str, output: Path) -> bool:
        """Download using ffmpeg"""
        print(f"[*] Downloading with ffmpeg to: {output}")
        
        cmd = [
            'ffmpeg',
            '-i', url,
            '-c', 'copy',
            '-bsf:a', 'aac_adtstoasc',
            '-y',  # Overwrite output file
            str(output)
        ]
        
        try:
            result = subprocess.run(cmd, check=True)
            print(f"[+] Download completed: {output}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"[!] Download failed: {e}")
            return False


@dataclass(frozen=True)
class DownloadTask:
    """Represents a single download task from batch file"""
    content_type: str  # 'tv' or 'movie'
    tmdb_id: int
    season: Optional[int] = None
    episode: Optional[int] = None
    output_file: Optional[str] = None
    lang: Optional[str] = None
    quality: Optional[str] = None
    line_number: int = 0

    def __str__(self):
        if self.content_type == 'tv':
            return f"TV {self.tmdb_id} S{self.season:02d}E{self.episode:02d}"
        return f"Movie {self.tmdb_id}"


class BatchDownloader:
    """Handle batch downloads from a file"""

    def __init__(self, downloader: VixSrcDownloader, tmdb_metadata: Optional[TMDBMetadata] = None):
        self.downloader = downloader
        self.tmdb_metadata = tmdb_metadata

    def parse_batch_file(self, file_path: str) -> List[DownloadTask]:
        """Parse batch download file and return list of tasks"""
        tasks = []

        try:
            with open(file_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()

                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue

                    # Parse line
                    parts = line.split()
                    if len(parts) < 2:
                        print(f"[!] Warning: Invalid format at line {line_num}: {line}")
                        continue

                    content_type = parts[0].lower()

                    if content_type == 'tv':
                        # Format: tv TMDB_ID SEASON EPISODE [OUTPUT_FILE] [LANG] [QUALITY]
                        if len(parts) < 4:
                            print(f"[!] Warning: Invalid TV format at line {line_num}: {line}")
                            continue

                        try:
                            task = DownloadTask(
                                content_type='tv',
                                tmdb_id=int(parts[1]),
                                season=int(parts[2]),
                                episode=int(parts[3]),
                                output_file=parts[4] if len(parts) > 4 and parts[4] != '-' else None,
                                lang=parts[5] if len(parts) > 5 and parts[5] != '-' else None,
                                quality=parts[6] if len(parts) > 6 and parts[6] != '-' else None,
                                line_number=line_num
                            )
                            tasks.append(task)
                        except ValueError as e:
                            print(f"[!] Warning: Invalid values at line {line_num}: {e}")
                            continue

                    elif content_type == 'movie':
                        # Format: movie TMDB_ID [OUTPUT_FILE] [LANG] [QUALITY]
                        try:
                            task = DownloadTask(
                                content_type='movie',
                                tmdb_id=int(parts[1]),
                                output_file=parts[2] if len(parts) > 2 and parts[2] != '-' else None,
                                lang=parts[3] if len(parts) > 3 and parts[3] != '-' else None,
                                quality=parts[4] if len(parts) > 4 and parts[4] != '-' else None,
                                line_number=line_num
                            )
                            tasks.append(task)
                        except ValueError as e:
                            print(f"[!] Warning: Invalid values at line {line_num}: {e}")
                            continue

                    else:
                        print(f"[!] Warning: Unknown content type at line {line_num}: {content_type}")
                        continue

        except FileNotFoundError:
            print(f"[!] Error: File not found: {file_path}")
            return []
        except Exception as e:
            print(f"[!] Error reading file: {e}")
            return []

        return tasks

    def process_single_download(self, task: DownloadTask, output_dir: Optional[str] = None,
                                default_lang: str = 'en', default_quality: str = 'best',
                                progress_bar: Optional[tqdm] = None) -> bool:
        """Process a single download task"""

        # Use task-specific settings or fall back to defaults
        lang = task.lang or default_lang
        quality = task.quality or default_quality

        # Update downloader language if different
        if lang != self.downloader.lang:
            self.downloader.lang = lang

        # Enable quiet mode if using progress bar
        if progress_bar:
            self.downloader.quiet = True

        try:
            # Get playlist URL (suppress output if progress bar is used)
            if task.content_type == 'tv':
                playlist_url = self.downloader.get_playlist_url(task.tmdb_id, task.season, task.episode)
            else:
                playlist_url = self.downloader.get_playlist_url(task.tmdb_id)

            if not playlist_url:
                if progress_bar:
                    progress_bar.set_description(f"✗ {task} - Failed to get URL")
                    progress_bar.refresh()
                return False

            # Determine output path
            if task.output_file:
                output_path = task.output_file
                # If output directory is specified and path is relative, prepend directory
                if output_dir and not os.path.isabs(output_path):
                    output_path = os.path.join(output_dir, output_path)
            else:
                # Generate filename using TMDB metadata
                if task.content_type == 'tv':
                    if self.tmdb_metadata and self.tmdb_metadata.api_key:
                        output_path = self.tmdb_metadata.generate_tv_filename(
                            task.tmdb_id, task.season, task.episode # type: ignore
                        )
                    else:
                        output_path = f"tv_{task.tmdb_id}_s{task.season:02d}e{task.episode:02d}.mp4"
                else:
                    if self.tmdb_metadata and self.tmdb_metadata.api_key:
                        output_path = self.tmdb_metadata.generate_movie_filename(task.tmdb_id)
                    else:
                        output_path = f"movie_{task.tmdb_id}.mp4"

                # Prepend output directory if specified
                if output_dir:
                    output_path = os.path.join(output_dir, output_path)

            # Download the video
            success = self.downloader.download_video(playlist_url, output_path, quality, progress_bar)

            return success

        except Exception as e:
            if progress_bar:
                progress_bar.set_description(f"✗ {task} - {str(e)}")
                progress_bar.refresh()
            return False

    def download_batch(self, tasks: List[DownloadTask], output_dir: Optional[str] = None,
                      parallel_jobs: int = 1, default_lang: str = 'en',
                      default_quality: str = 'best') -> Tuple[int, int]:
        """
        Download all tasks in batch with progress bars

        Returns:
            Tuple of (success_count, failed_count)
        """

        # Create output directory if specified
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        total = len(tasks)
        success_count = 0
        failed_count = 0

        print(f"\nVixSrc Batch Downloader - {total} tasks - {parallel_jobs} parallel jobs\n")

        if parallel_jobs > 1:
            # Parallel execution with multiple progress bars
            # Create a progress bar for each parallel task
            progress_bars = {}

            with ThreadPoolExecutor(max_workers=parallel_jobs) as executor:
                # Submit all tasks with their own progress bars
                future_to_task = {}

                for task in tasks:
                    # Create a progress bar for this task
                    pbar = tqdm(
                        total=100,
                        desc=f"Queued: {task}",
                        position=len(progress_bars),
                        leave=True,
                        bar_format='{desc}: {percentage:3.0f}%|{bar}| [{elapsed}]'
                    )
                    progress_bars[task] = pbar

                    future = executor.submit(
                        self.process_single_download,
                        task, output_dir, default_lang, default_quality, pbar
                    )
                    future_to_task[future] = task

                # Process completed tasks
                for future in as_completed(future_to_task):
                    task = future_to_task[future]
                    pbar = progress_bars[task]

                    try:
                        success = future.result()
                        if success:
                            success_count += 1
                        else:
                            failed_count += 1
                    except Exception as e:
                        pbar.set_description(f"✗ {task} - Exception: {str(e)}")
                        pbar.refresh()
                        failed_count += 1
                    finally:
                        pbar.close()

        else:
            # Sequential execution with single progress bar
            for task in tasks:
                pbar = tqdm(
                    total=100,
                    desc=f"Processing: {task}",
                    leave=True,
                    bar_format='{desc}: {percentage:3.0f}%|{bar}| [{elapsed}]'
                )

                success = self.process_single_download(task, output_dir, default_lang, default_quality, pbar)

                if success:
                    success_count += 1
                else:
                    failed_count += 1

                pbar.close()

        # Print summary
        print(f"\n{'='*60}")
        print(f"Summary")
        print(f"{'='*60}")
        print(f"Total:   {total}")
        print(f"Success: {success_count}")
        print(f"Failed:  {failed_count}")
        print(f"{'='*60}\n")

        return success_count, failed_count


def main():
    parser = argparse.ArgumentParser(
        description='Download videos from vixsrc.to using TMDB IDs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download a movie (auto-generates: Fight.Club.1999.mp4)
  export TMDB_API_KEY="your_api_key"
  %(prog)s --movie 550

  # Download a TV episode (auto-generates: Breaking.Bad.S04E04.Ozymandias.mp4)
  %(prog)s --tv 60625 --season 4 --episode 4

  # Download with custom filename
  %(prog)s --movie 550 --output fight_club.mp4

  # Just print the playlist URL
  %(prog)s --movie 550 --url-only

  # Download with specific quality
  %(prog)s --movie 550 --quality 720

  # Batch download from file
  %(prog)s --batch downloads.txt --output-dir ./videos

  # Batch download with 3 parallel downloads
  %(prog)s --batch downloads.txt --parallel 3

Batch file format (one per line):
  tv TMDB_ID SEASON EPISODE [OUTPUT_FILE] [LANG] [QUALITY]
  movie TMDB_ID [OUTPUT_FILE] [LANG] [QUALITY]

  Example batch file:
    # Breaking Bad Season 4
    tv 60625 4 1 - en 1080
    tv 60625 4 2 bb_s04e02.mp4 en
    # Fight Club
    movie 550 fight_club.mp4 en 720

Note: Get TMDB IDs at https://www.themoviedb.org/
      Get free TMDB API key at https://www.themoviedb.org/settings/api
        """
    )

    content_group = parser.add_mutually_exclusive_group(required=True)
    content_group.add_argument('--movie', type=int, metavar='TMDB_ID',
                              help='TMDB ID for a movie')
    content_group.add_argument('--tv', type=int, metavar='TMDB_ID',
                              help='TMDB ID for a TV show')
    content_group.add_argument('--batch', type=str, metavar='FILE',
                              help='Batch download from file')
    
    parser.add_argument('--season', type=int, metavar='N',
                       help='Season number (required with --tv)')
    parser.add_argument('--episode', type=int, metavar='N',
                       help='Episode number (required with --tv)')
    parser.add_argument('--output', '-o', type=str, metavar='FILE',
                       help='Output file path (default: auto-generated)')
    parser.add_argument('--output-dir', '-d', type=str, metavar='DIR',
                       help='Output directory for auto-generated filenames')
    parser.add_argument('--quality', '-q', type=str, default='best',
                       metavar='QUALITY',
                       help='Video quality: best/worst/720/1080 (default: best)')
    parser.add_argument('--url-only', action='store_true',
                       help='Only print the playlist URL, don\'t download')
    parser.add_argument('--timeout', type=int, default=30, metavar='SEC',
                       help='Request timeout in seconds (default: 30)')
    parser.add_argument('--lang', type=str, default='en', metavar='LANG',
                       help='Language code for audio/subtitles (default: en)')
    parser.add_argument('--tmdb-api-key', type=str, metavar='KEY',
                       help='TMDB API key (or set TMDB_API_KEY env var)')
    parser.add_argument('--no-metadata', action='store_true',
                       help='Disable TMDB metadata fetching for filenames')
    parser.add_argument('--parallel', '-p', type=int, default=1, metavar='N',
                       help='Number of parallel downloads for batch mode (default: 1)')
    parser.add_argument('--ytdlp-concurrency', type=int, default=5, metavar='N',
                       help='Number of concurrent fragment downloads for yt-dlp (default: 5)')

    args = parser.parse_args()

    # Validate arguments
    if args.tv and (args.season is None or args.episode is None):
        parser.error('--tv requires both --season and --episode')

    if args.batch and args.url_only:
        parser.error('--url-only cannot be used with --batch mode')

    # Create downloader
    downloader = VixSrcDownloader(timeout=args.timeout, lang=args.lang, ytdlp_concurrency=args.ytdlp_concurrency)

    # Create TMDB metadata helper
    tmdb_metadata = None
    if not args.no_metadata:
        tmdb_metadata = TMDBMetadata(api_key=args.tmdb_api_key)
        if not tmdb_metadata.api_key:
            print("[!] Warning: TMDB API key not found. Using basic filenames.")
            print("[*] Set TMDB_API_KEY environment variable or use --tmdb-api-key")
            print("[*] Get a free API key at https://www.themoviedb.org/settings/api")
            print()

    # Handle batch download mode
    if args.batch:
        batch_downloader = BatchDownloader(downloader, tmdb_metadata)

        # Parse batch file
        tasks = batch_downloader.parse_batch_file(args.batch)

        if not tasks:
            print("[!] No valid tasks found in batch file")
            return 1

        # Download all tasks
        success_count, failed_count = batch_downloader.download_batch(
            tasks,
            output_dir=args.output_dir,
            parallel_jobs=args.parallel,
            default_lang=args.lang,
            default_quality=args.quality
        )

        # Return non-zero if any downloads failed
        return 0 if failed_count == 0 else 1

    # Get content info and generate filename
    if args.movie:
        tmdb_id = args.movie
        season = None
        episode = None

        # Try to generate enhanced filename from TMDB metadata
        if tmdb_metadata and tmdb_metadata.api_key:
            print(f"[*] Fetching movie metadata from TMDB...")
            default_output = tmdb_metadata.generate_movie_filename(tmdb_id)
        else:
            default_output = f"movie_{tmdb_id}.mp4"
    else:
        tmdb_id = args.tv
        season = args.season
        episode = args.episode

        # Try to generate enhanced filename from TMDB metadata
        if tmdb_metadata and tmdb_metadata.api_key:
            print(f"[*] Fetching TV show metadata from TMDB...")
            default_output = tmdb_metadata.generate_tv_filename(tmdb_id, season, episode)
        else:
            default_output = f"tv_{tmdb_id}_s{season:02d}e{episode:02d}.mp4"
    
    # Get playlist URL
    print(f"[*] Fetching playlist URL for TMDB ID: {tmdb_id}")
    if season is not None:
        print(f"[*] Season: {season}, Episode: {episode}")
    
    playlist_url = downloader.get_playlist_url(tmdb_id, season, episode)
    
    if not playlist_url:
        print("[!] Failed to get playlist URL")
        return 1
    
    print(f"\n[+] Playlist URL: {playlist_url}\n")
    
    # If only URL requested, exit here
    if args.url_only:
        return 0
    
    # Determine output path
    if args.output:
        output_path = args.output
    else:
        output_path = default_output
        # If output directory is specified, prepend it to auto-generated filename
        if args.output_dir:
            os.makedirs(args.output_dir, exist_ok=True)
            output_path = os.path.join(args.output_dir, default_output)

    # Download the video with progress bar
    pbar = tqdm(
        total=100,
        desc=f"Downloading",
        bar_format='{desc}: {percentage:3.0f}%|{bar}| [{elapsed}]'
    )
    success = downloader.download_video(playlist_url, output_path, args.quality, pbar)
    pbar.close()

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
