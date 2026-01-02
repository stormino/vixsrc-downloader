"""CLI entry point for VixSrc downloader."""

import argparse
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from .batch import BatchDownloader
from .constants import DEFAULT_TIMEOUT, DEFAULT_LANG, DEFAULT_QUALITY, DEFAULT_YTDLP_CONCURRENCY, DEFAULT_EXTENSION
from .downloader import VixSrcDownloader
from .metadata import TMDBMetadata
from .utils import ensure_dependency

# Ensure dependencies are installed
ensure_dependency("requests")
ensure_dependency("cloudscraper")
ensure_dependency("tmdbsimple", "tmdbsimple")
ensure_dependency("tqdm")
ensure_dependency("rich")



def main():
    parser = argparse.ArgumentParser(
        description='Download videos from vixsrc.to using TMDB IDs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Search for content (requires TMDB_API_KEY)
  export TMDB_API_KEY="your_api_key"
  %(prog)s --search "breaking bad"
  %(prog)s --search "fight club"

  # Download a movie (auto-generates: Fight.Club.1999.mp4)
  %(prog)s --movie 550

  # Download entire TV show (all seasons)
  %(prog)s --tv 60625 --output-dir ./breaking_bad --parallel 3

  # Download entire season
  %(prog)s --tv 60625 --season 4 --output-dir ./bb_s4 --parallel 2

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
    content_group.add_argument('--search', type=str, metavar='TERM',
                              help='Search for movies and TV shows by title')

    parser.add_argument('--season', type=int, metavar='N',
                       help='Season number (optional: if omitted with --tv, downloads all seasons)')
    parser.add_argument('--episode', type=int, metavar='N',
                       help='Episode number (optional: if omitted with --tv, downloads whole season)')
    parser.add_argument('--output', '-o', type=str, metavar='FILE',
                       help='Output file path (default: auto-generated)')
    parser.add_argument('--output-dir', '-d', type=str, metavar='DIR',
                       help='Output directory for auto-generated filenames')
    parser.add_argument('--quality', '-q', type=str, default=DEFAULT_QUALITY,
                       metavar='QUALITY',
                       help='Video quality: best/worst/720/1080 (default: best)')
    parser.add_argument('--url-only', action='store_true',
                       help='Only print the playlist URL, don\'t download')
    parser.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT, metavar='SEC',
                       help='Request timeout in seconds (default: 30)')
    parser.add_argument('--lang', type=str, default=DEFAULT_LANG, metavar='LANG',
                       help='Language code for audio/subtitles (default: en)')
    parser.add_argument('--tmdb-api-key', type=str, metavar='KEY',
                       help='TMDB API key (or set TMDB_API_KEY env var)')
    parser.add_argument('--no-metadata', action='store_true',
                       help='Disable TMDB metadata fetching for filenames')
    parser.add_argument('--parallel', '-p', type=int, default=1, metavar='N',
                       help='Number of parallel downloads for bulk TV downloads (default: 1)')
    parser.add_argument('--ytdlp-concurrency', type=int, default=DEFAULT_YTDLP_CONCURRENCY, metavar='N',
                       help='Number of concurrent fragment downloads for yt-dlp (default: 5)')

    args = parser.parse_args()

    # Validate arguments
    # --tv can be used alone (all seasons), with --season (all episodes),
    # or with both --season and --episode (single episode)
    if args.tv and args.episode is not None and args.season is None:
        parser.error('--episode requires --season')

    # Handle search mode
    if args.search:
        # Search requires TMDB API key
        tmdb_metadata = TMDBMetadata(api_key=args.tmdb_api_key)
        if not tmdb_metadata.api_key:
            print("[!] Error: Search requires TMDB API key")
            print("[*] Set TMDB_API_KEY environment variable or use --tmdb-api-key")
            print("[*] Get a free API key at https://www.themoviedb.org/settings/api")
            return 1

        # Create downloader for verification
        downloader = VixSrcDownloader(timeout=args.timeout, lang=args.lang, ytdlp_concurrency=args.ytdlp_concurrency, quiet=True)

        print(f"[*] Searching for: {args.search}")
        print(f"[*] Verifying availability on vixsrc (this may take a moment)...\n")

        # Search movies
        print("=== MOVIES ===\n")
        movies = tmdb_metadata.search_movies(args.search)
        available_movies = 0
        if movies:
            for movie in movies:
                # Verify availability on vixsrc
                playlist_url = downloader.get_playlist_url(movie['id'], None, None)
                if playlist_url:
                    available_movies += 1
                    print(f"ID: {movie['id']}")
                    print(f"Title: {movie['title']}")
                    if movie['title'] != movie['original_title']:
                        print(f"Original Title: {movie['original_title']}")
                    print(f"Year: {movie['year']}")
                    print(f"Rating: {movie['vote_average']}/10")
                    print(f"Overview: {movie['overview'][:150]}{'...' if len(movie['overview']) > 150 else ''}")
                    print()

        if available_movies == 0:
            print("No movies found on vixsrc\n")

        # Search TV shows
        print("=== TV SHOWS ===\n")
        shows = tmdb_metadata.search_tv_shows(args.search)
        available_shows = 0
        if shows:
            for show in shows:
                # Verify availability on vixsrc (check first episode of first season)
                # Get first season number
                seasons = tmdb_metadata.get_all_seasons(show['id'])
                if seasons and len(seasons) > 0:
                    first_season = seasons[0]['season_number']
                    playlist_url = downloader.get_playlist_url(show['id'], first_season, 1)
                    if playlist_url:
                        available_shows += 1
                        print(f"ID: {show['id']}")
                        print(f"Name: {show['name']}")
                        if show['name'] != show['original_name']:
                            print(f"Original Name: {show['original_name']}")
                        print(f"Year: {show['year']}")
                        print(f"Seasons: {show['seasons']}")
                        print(f"Total Episodes: {show['total_episodes']}")
                        print(f"Rating: {show['vote_average']}/10")
                        print(f"Overview: {show['overview'][:150]}{'...' if len(show['overview']) > 150 else ''}")
                        print()

        if available_shows == 0:
            print("No TV shows found on vixsrc\n")

        return 0

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

    # Handle bulk TV download mode (--tv without episode, or without both season and episode)
    if args.tv and (args.season is None or args.episode is None):
        # Bulk TV download - use batch infrastructure

        # Check for TMDB API key (required for discovering episodes)
        if not tmdb_metadata or not tmdb_metadata.api_key:
            print("[!] Error: Bulk TV download requires TMDB API key")
            print("[*] Set TMDB_API_KEY environment variable or use --tmdb-api-key")
            print("[*] Get a free API key at https://www.themoviedb.org/settings/api")
            return 1

        # Show what we're downloading
        show_name = tmdb_metadata.get_show_name(args.tv)
        if args.season:
            print(f"[*] Preparing to download: {show_name or f'TV {args.tv}'} - Season {args.season}")
        else:
            print(f"[*] Preparing to download all seasons of: {show_name or f'TV {args.tv}'}")

        # Create batch downloader
        batch_downloader = BatchDownloader(downloader, tmdb_metadata)

        # Generate tasks for all episodes
        print(f"[*] Fetching episode list from TMDB...")
        tasks = batch_downloader.generate_bulk_tv_tasks(
            tmdb_id=args.tv,
            season=args.season,
            episode=args.episode,
            lang=args.lang,
            quality=args.quality
        )

        if not tasks:
            print("[!] No episodes found")
            return 1

        print(f"[*] Found {len(tasks)} episode(s) to download")
        print(f"[*] Parallel jobs: {args.parallel}")
        print()

        # Download all tasks using batch infrastructure
        success_count, failed_count = batch_downloader.download_batch(
            tasks,
            output_dir=args.output_dir,
            parallel_jobs=args.parallel,
            default_lang=args.lang,
            default_quality=args.quality
        )

        # Print summary
        print()
        print(f"[+] Completed: {success_count} successful, {failed_count} failed")

        return 0 if failed_count == 0 else 1

    # Single movie or TV episode download
    from .batch import DownloadTask

    if args.movie:
        tmdb_id = args.movie
        season = None
        episode = None
    else:
        tmdb_id = args.tv
        season = args.season
        episode = args.episode

    # Handle --url-only mode
    if args.url_only:
        print(f"[*] Fetching playlist URL for TMDB ID: {tmdb_id}")
        if season is not None:
            print(f"[*] Season: {season}, Episode: {episode}")

        playlist_url = downloader.get_playlist_url(tmdb_id, season, episode)

        if not playlist_url:
            print("[!] Failed to get playlist URL")
            return 1

        print(f"\n[+] Playlist URL: {playlist_url}\n")
        return 0

    # Create a download task
    task = DownloadTask(
        content_type='movie' if args.movie else 'tv',
        tmdb_id=tmdb_id,
        season=season,
        episode=episode,
        output_file=args.output,
        lang=args.lang,
        quality=args.quality
    )

    # Use batch downloader infrastructure (handles everything)
    batch_downloader = BatchDownloader(downloader, tmdb_metadata)
    success_count, failed_count = batch_downloader.download_batch(
        [task],
        output_dir=args.output_dir,
        parallel_jobs=1,
        default_lang=args.lang,
        default_quality=args.quality
    )

    return 0 if failed_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
