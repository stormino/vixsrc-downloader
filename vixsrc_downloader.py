#!/usr/bin/env python3
"""
VixSrc Video Downloader

A tool to download videos from vixsrc.to using TMDB IDs.
Downloads HLS streams and converts them to MP4.
Automatically generates descriptive filenames from TMDB metadata.

Usage:
    # Download a movie (auto-generates: Fight.Club.1999.mp4)
    export TMDB_API_KEY="your_api_key"
    python vixsrc_downloader.py --movie 550

    # Download a TV show episode (auto-generates: Breaking.Bad.S04E04.Ozymandias.mp4)
    python vixsrc_downloader.py --tv 60625 --season 4 --episode 4

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
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
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
    
    def __init__(self, timeout: int = 30, lang: str = 'en'):
        self.timeout = timeout
        self.lang = lang
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

                    playlist_url = f"{playlist_base_url}?{'&'.join(params)}"

                    # Clean up any HTML entities
                    playlist_url = playlist_url.replace('&amp;', '&')
                    print(f"[+] Constructed playlist URL with required parameters")

                    # Verify the playlist URL works
                    try:
                        print(f"[*] Verifying playlist URL...")
                        headers = {'Referer': embed_url, 'Accept': '*/*'}
                        playlist_response = self.session.get(playlist_url, headers=headers, timeout=self.timeout)

                        if playlist_response.ok and playlist_response.text.startswith('#EXTM3U'):
                            print(f"[+] Playlist URL verified successfully")
                            return playlist_url
                        else:
                            print(f"[!] Playlist verification failed: {playlist_response.status_code}")
                    except Exception as e:
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
                print(f"[+] Found playlist URL: {playlist_url}")
                return playlist_url
            
            # Alternative: Look for API calls in JavaScript
            # Pattern: /api/source or similar endpoints
            api_pattern = r'["\'](/api/[^"\']+)["\']'
            api_matches = re.findall(api_pattern, html_content)
            
            if api_matches:
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
                                            print(f"[+] Found playlist URL from API: {value}")
                                            return value
                            except json.JSONDecodeError:
                                pass
                    except Exception as e:
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
                            print(f"[+] Found valid playlist URL: {test_response.url}")
                            return test_response.url
                    except Exception:
                        pass
            
            print("[!] Could not extract playlist URL from page")
            print("[*] Page may require JavaScript execution or the format has changed")
            return None
            
        except requests.RequestException as e:
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
                       quality: str = 'best') -> bool:
        """
        Download video from HLS playlist URL using yt-dlp or ffmpeg.
        
        Args:
            playlist_url: The HLS playlist URL
            output_path: Path to save the downloaded video
            quality: Quality selector (best/worst/specific height like 1080)
            
        Returns:
            True if download successful, False otherwise
        """
        output_path = Path(output_path) # type: ignore
        
        # Try yt-dlp first (better at handling HLS)
        if self._check_command('yt-dlp'):
            return self._download_with_ytdlp(playlist_url, output_path, quality) # type: ignore
        
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
    
    def _download_with_ytdlp(self, url: str, output: Path, quality: str) -> bool:
        """Download using yt-dlp"""
        print(f"[*] Downloading with yt-dlp to: {output}")

        # Determine format selection based on quality
        if quality.isdigit():
            # Select video with specified height + audio (prefer Italian based on lang setting)
            format_selector = f'bestvideo[height<={quality}]+bestaudio[language={self.lang}]/bestvideo[height<={quality}]+bestaudio'
        else:
            # For 'best', select best video + audio with language preference
            format_selector = f'bestvideo+bestaudio[language={self.lang}]/bestvideo+bestaudio/best'

        cmd = [
            'yt-dlp',
            '--no-warnings',
            '--newline',
            '-f', format_selector,
            '--merge-output-format', 'mp4',
            '--referer', self.BASE_URL,
            '--add-header', 'Accept: */*',
            '-o', str(output),
            url
        ]

        try:
            result = subprocess.run(cmd, check=True)
            print(f"[+] Download completed: {output}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"[!] Download failed: {e}")
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

Note: Get TMDB IDs at https://www.themoviedb.org/
      Get free TMDB API key at https://www.themoviedb.org/settings/api
        """
    )
    
    content_group = parser.add_mutually_exclusive_group(required=True)
    content_group.add_argument('--movie', type=int, metavar='TMDB_ID',
                              help='TMDB ID for a movie')
    content_group.add_argument('--tv', type=int, metavar='TMDB_ID',
                              help='TMDB ID for a TV show')
    
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

    args = parser.parse_args()

    # Validate TV show arguments
    if args.tv and (args.season is None or args.episode is None):
        parser.error('--tv requires both --season and --episode')

    # Create downloader
    downloader = VixSrcDownloader(timeout=args.timeout, lang=args.lang)

    # Create TMDB metadata helper
    tmdb_metadata = None
    if not args.no_metadata:
        tmdb_metadata = TMDBMetadata(api_key=args.tmdb_api_key)
        if not tmdb_metadata.api_key:
            print("[!] Warning: TMDB API key not found. Using basic filenames.")
            print("[*] Set TMDB_API_KEY environment variable or use --tmdb-api-key")
            print("[*] Get a free API key at https://www.themoviedb.org/settings/api")
            print()

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

    # Download the video
    success = downloader.download_video(playlist_url, output_path, args.quality)
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
