"""TMDB metadata fetching."""

import os
from typing import Optional, Dict, Any

from .constants import DEFAULT_EXTENSION
from .utils import sanitize_filename

try:
    import tmdbsimple as tmdb
except ImportError:
    tmdb = None  # type: ignore


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
        if self.api_key and tmdb:
            tmdb.API_KEY = self.api_key

    def get_movie_info(self, tmdb_id: int) -> Optional[Dict[str, Any]]:
        """
        Get movie metadata from TMDB.

        Args:
            tmdb_id: TMDB movie ID

        Returns:
            Dictionary with title, year, and other metadata, or None if API key not set
        """
        if not self.api_key or not tmdb:
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
        if not self.api_key or not tmdb:
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

    def generate_movie_filename(self, tmdb_id: int, extension: str = DEFAULT_EXTENSION) -> str:
        """
        Generate a descriptive filename for a movie.
        Format: Title.Year.mp4

        Args:
            tmdb_id: TMDB movie ID
            extension: File extension

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
                            extension: str = DEFAULT_EXTENSION) -> str:
        """
        Generate a descriptive filename for a TV episode.
        Format: Show.S##E##.Episode.mp4

        Args:
            tmdb_id: TMDB TV show ID
            season: Season number
            episode: Episode number
            extension: File extension

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
