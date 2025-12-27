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

    def get_show_name(self, tmdb_id: int) -> Optional[str]:
        """
        Get TV show name for display/logging purposes.

        Args:
            tmdb_id: TMDB TV show ID

        Returns:
            Show name or None if API key not set
        """
        if not self.api_key or not tmdb:
            return None

        try:
            show = tmdb.TV(tmdb_id)
            show_info = show.info()
            return show_info.get('name', '')
        except Exception as e:
            print(f"[!] Warning: Failed to fetch TV show name: {e}")
            return None

    def get_all_seasons(self, tmdb_id: int) -> Optional[list[Dict[str, Any]]]:
        """
        Get all seasons with episode counts for a TV show.

        Args:
            tmdb_id: TMDB TV show ID

        Returns:
            List of dicts with 'season_number' and 'episode_count', or None if API key not set
        """
        if not self.api_key or not tmdb:
            return None

        try:
            show = tmdb.TV(tmdb_id)
            show_info = show.info()

            # Extract seasons, skip Season 0 (specials)
            seasons = []
            for season in show_info.get('seasons', []):
                season_num = season.get('season_number', 0)
                if season_num > 0:  # Skip specials
                    seasons.append({
                        'season_number': season_num,
                        'episode_count': season.get('episode_count', 0)
                    })

            return seasons
        except Exception as e:
            print(f"[!] Warning: Failed to fetch seasons: {e}")
            return None

    def get_season_episodes(self, tmdb_id: int, season: int) -> Optional[list[int]]:
        """
        Get all episode numbers for a specific season.

        Args:
            tmdb_id: TMDB TV show ID
            season: Season number

        Returns:
            List of episode numbers, or None if API key not set
        """
        if not self.api_key or not tmdb:
            return None

        try:
            season_obj = tmdb.TV_Seasons(tmdb_id, season)
            season_info = season_obj.info()

            # Extract episode numbers
            episodes = []
            for episode in season_info.get('episodes', []):
                ep_num = episode.get('episode_number')
                if ep_num is not None:
                    episodes.append(ep_num)

            return episodes
        except Exception as e:
            print(f"[!] Warning: Failed to fetch episodes for season {season}: {e}")
            return None

    def search_movies(self, query: str) -> Optional[list[Dict[str, Any]]]:
        """
        Search for movies by title.

        Args:
            query: Search term

        Returns:
            List of movie results with id, title, year, overview, or None if API key not set
        """
        if not self.api_key or not tmdb:
            return None

        try:
            search = tmdb.Search()
            results = search.movie(query=query)

            movies = []
            for movie in search.results:
                year = None
                if movie.get('release_date'):
                    year = movie['release_date'].split('-')[0]

                movies.append({
                    'id': movie.get('id'),
                    'title': movie.get('title', 'N/A'),
                    'original_title': movie.get('original_title', 'N/A'),
                    'year': year or 'N/A',
                    'overview': movie.get('overview', 'No overview available'),
                    'vote_average': movie.get('vote_average', 0),
                    'popularity': movie.get('popularity', 0)
                })

            return movies
        except Exception as e:
            print(f"[!] Error: Failed to search movies: {e}")
            return None

    def search_tv_shows(self, query: str) -> Optional[list[Dict[str, Any]]]:
        """
        Search for TV shows by title.

        Args:
            query: Search term

        Returns:
            List of TV show results with id, name, year, seasons, episodes, overview, or None if API key not set
        """
        if not self.api_key or not tmdb:
            return None

        try:
            search = tmdb.Search()
            results = search.tv(query=query)

            shows = []
            for show in search.results:
                # Get detailed info for each show to get season/episode counts
                try:
                    show_detail = tmdb.TV(show.get('id'))
                    show_info = show_detail.info()

                    # Count total episodes across all seasons (excluding specials)
                    total_episodes = 0
                    season_count = 0
                    for season in show_info.get('seasons', []):
                        if season.get('season_number', 0) > 0:  # Skip specials
                            season_count += 1
                            total_episodes += season.get('episode_count', 0)

                    year = None
                    if show.get('first_air_date'):
                        year = show['first_air_date'].split('-')[0]

                    shows.append({
                        'id': show.get('id'),
                        'name': show.get('name', 'N/A'),
                        'original_name': show.get('original_name', 'N/A'),
                        'year': year or 'N/A',
                        'seasons': season_count,
                        'total_episodes': total_episodes,
                        'overview': show.get('overview', 'No overview available'),
                        'vote_average': show.get('vote_average', 0),
                        'popularity': show.get('popularity', 0)
                    })
                except Exception as e:
                    # If detailed info fails, add basic info
                    year = None
                    if show.get('first_air_date'):
                        year = show['first_air_date'].split('-')[0]

                    shows.append({
                        'id': show.get('id'),
                        'name': show.get('name', 'N/A'),
                        'original_name': show.get('original_name', 'N/A'),
                        'year': year or 'N/A',
                        'seasons': 'N/A',
                        'total_episodes': 'N/A',
                        'overview': show.get('overview', 'No overview available'),
                        'vote_average': show.get('vote_average', 0),
                        'popularity': show.get('popularity', 0)
                    })

            return shows
        except Exception as e:
            print(f"[!] Error: Failed to search TV shows: {e}")
            return None
