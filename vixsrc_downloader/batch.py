"""Batch download functionality."""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional, List, Tuple

from .constants import (
    DEFAULT_LANG,
    DEFAULT_QUALITY,
    DEFAULT_EXTENSION,
    STATUS_ICON_FAILURE
)
from .downloader import VixSrcDownloader
from .metadata import TMDBMetadata
from .progress import ProgressTracker

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None  # type: ignore

try:
    from rich.progress import Progress, BarColumn, TimeRemainingColumn, TimeElapsedColumn, TextColumn
except ImportError:
    Progress = None  # type: ignore
    BarColumn = None  # type: ignore
    TimeRemainingColumn = None  # type: ignore
    TimeElapsedColumn = None  # type: ignore
    TextColumn = None  # type: ignore


@dataclass(frozen=True)
class DownloadTask:
    """Represents a single download task"""
    content_type: str  # 'tv' or 'movie'
    tmdb_id: int
    season: Optional[int] = None
    episode: Optional[int] = None
    output_file: Optional[str] = None
    lang: Optional[str] = None  # Backward compatibility
    languages: Optional[List[str]] = None  # New field for multi-language
    quality: Optional[str] = None
    line_number: int = 0

    @property
    def language_list(self) -> List[str]:
        """Get languages as list, handling both old and new format"""
        from .constants import DEFAULT_LANG
        if self.languages:
            return self.languages
        elif self.lang:
            return [self.lang]
        return [DEFAULT_LANG]

    def __str__(self):
        if self.content_type == 'tv':
            return f"TV {self.tmdb_id} S{self.season:02d}E{self.episode:02d}"
        return f"Movie {self.tmdb_id}"


class BatchDownloader:
    """Handle bulk TV downloads and parallel download orchestration"""

    def __init__(self, downloader: VixSrcDownloader, tmdb_metadata: Optional[TMDBMetadata] = None):
        self.downloader = downloader
        self.tmdb_metadata = tmdb_metadata

    def generate_bulk_tv_tasks(
        self,
        tmdb_id: int,
        season: Optional[int] = None,
        episode: Optional[int] = None,
        lang: Optional[str] = None,
        quality: Optional[str] = None
    ) -> List[DownloadTask]:
        """
        Generate download tasks for bulk TV download.

        Args:
            tmdb_id: TMDB TV show ID
            season: Optional season number (None = all seasons)
            episode: Optional episode number (None = all in season)
            lang: Optional language code
            quality: Optional quality setting

        Returns:
            List of DownloadTask objects
        """
        tasks = []

        # Check if TMDB metadata is available
        if not self.tmdb_metadata or not self.tmdb_metadata.api_key:
            print("[!] Error: TMDB API key required for bulk TV downloads")
            return tasks

        # If both season and episode are provided, return single task
        if season is not None and episode is not None:
            task = DownloadTask(
                content_type='tv',
                tmdb_id=tmdb_id,
                season=season,
                episode=episode,
                lang=lang,
                quality=quality
            )
            tasks.append(task)
            return tasks

        # If season provided but not episode, get all episodes in that season
        if season is not None:
            episodes = self.tmdb_metadata.get_season_episodes(tmdb_id, season)
            if not episodes:
                print(f"[!] Warning: No episodes found for season {season}")
                return tasks

            for ep_num in episodes:
                task = DownloadTask(
                    content_type='tv',
                    tmdb_id=tmdb_id,
                    season=season,
                    episode=ep_num,
                    lang=lang,
                    quality=quality
                )
                tasks.append(task)
            return tasks

        # If neither season nor episode provided, get all seasons and all episodes
        seasons = self.tmdb_metadata.get_all_seasons(tmdb_id)
        if not seasons:
            print("[!] Warning: No seasons found for this TV show")
            return tasks

        for season_info in seasons:
            season_num = season_info['season_number']
            episodes = self.tmdb_metadata.get_season_episodes(tmdb_id, season_num)

            if not episodes:
                print(f"[!] Warning: No episodes found for season {season_num}")
                continue

            for ep_num in episodes:
                task = DownloadTask(
                    content_type='tv',
                    tmdb_id=tmdb_id,
                    season=season_num,
                    episode=ep_num,
                    lang=lang,
                    quality=quality
                )
                tasks.append(task)

        return tasks

    def process_single_download(self, task: DownloadTask, output_dir: Optional[str] = None,
                                default_lang: str = DEFAULT_LANG, default_quality: str = DEFAULT_QUALITY,
                                progress_bar: Optional['tqdm'] = None, rich_progress: Optional[tuple] = None) -> bool:
        """Process a single download task"""

        # Create progress tracker
        tracker = ProgressTracker(progress_bar, rich_progress,
                                 quiet=(progress_bar is not None or rich_progress is not None))

        # Update downloader settings
        self._configure_downloader(task, default_lang, tracker)

        # Fetch metadata and update description
        task_description = self._get_task_description(task, tracker)

        try:
            # Get playlist URL
            playlist_url = self._get_playlist_url(task, tracker, task_description)
            if not playlist_url:
                return False

            # Determine output path
            output_path = self._resolve_output_path(task, output_dir)

            # Download video
            quality = task.quality or default_quality
            success = self.downloader.download_video(
                playlist_url, output_path, quality, progress_bar, rich_progress,
                tmdb_id=task.tmdb_id, season=task.season, episode=task.episode
            )

            # Update final status
            tracker.mark_complete(success, task_description)
            return success

        except Exception as e:
            tracker.set_description(f"{task_description} - {str(e)}", STATUS_ICON_FAILURE)
            return False

    def _configure_downloader(self, task: DownloadTask,
                             default_lang: str,
                             tracker: ProgressTracker) -> None:
        """Configure downloader for this task"""
        languages = task.language_list
        if languages != self.downloader.languages:
            self.downloader.languages = languages
            self.downloader.lang = languages[0]  # Update backward compat field
        if tracker.has_progress_ui():
            self.downloader.quiet = True

    def _get_task_description(self, task: DownloadTask,
                             tracker: ProgressTracker) -> str:
        """Get human-readable task description from TMDB metadata"""
        task_description = str(task)

        if not self.tmdb_metadata or not self.tmdb_metadata.api_key:
            return task_description

        try:
            if task.content_type == 'tv':
                info = self.tmdb_metadata.get_tv_info(
                    task.tmdb_id, task.season, task.episode  # type: ignore
                )
                if info:
                    task_description = f"{info['show_name']} S{info['season']:02d}E{info['episode']:02d}"
                    if info.get('episode_name'):
                        task_description += f" - {info['episode_name']}"
            else:
                info = self.tmdb_metadata.get_movie_info(task.tmdb_id)
                if info and info.get('title'):
                    task_description = f"{info['title']}"
                    if info.get('year'):
                        task_description += f" ({info['year']})"
        except Exception:
            pass

        # Update progress bar description
        tracker.set_description(task_description)
        return task_description

    def _get_playlist_url(self, task: DownloadTask, tracker: ProgressTracker,
                         description: str) -> Optional[str]:
        """Get playlist URL for task"""
        if task.content_type == 'tv':
            playlist_url = self.downloader.get_playlist_url(
                task.tmdb_id, task.season, task.episode, tracker
            )
        else:
            playlist_url = self.downloader.get_playlist_url(
                task.tmdb_id, progress_tracker=tracker
            )

        if not playlist_url:
            tracker.set_description(f"{description} - Failed to get URL", STATUS_ICON_FAILURE)

        return playlist_url

    def _resolve_output_path(self, task: DownloadTask,
                            output_dir: Optional[str]) -> str:
        """Resolve output path for task"""
        if task.output_file:
            output_path = task.output_file
            if output_dir and not os.path.isabs(output_path):
                output_path = os.path.join(output_dir, output_path)
        else:
            # Generate filename
            filename = self._generate_filename(task)

            # For TV shows, create show_name/Season XX/ directory structure
            if task.content_type == 'tv' and self.tmdb_metadata and self.tmdb_metadata.api_key:
                from .utils import sanitize_filename

                # Get show info to extract show name
                info = self.tmdb_metadata.get_tv_info(task.tmdb_id, task.season, task.episode)  # type: ignore
                if info and info.get('show_name'):
                    show_name = info['show_name'].replace(' ', '.')
                    show_name = sanitize_filename(show_name)

                    # Add year to directory name when not using --output-dir
                    if not output_dir and info.get('year'):
                        show_dir = f"{show_name}.{info['year']}"
                    else:
                        show_dir = show_name

                    season_dir = f"Season {task.season:02d}"

                    # Build path: show_dir/Season XX/filename
                    if output_dir:
                        output_path = os.path.join(output_dir, show_dir, season_dir, filename)
                    else:
                        output_path = os.path.join(show_dir, season_dir, filename)

                    # Create directory structure
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                else:
                    # Fallback if metadata fetch fails
                    output_path = filename
                    if output_dir:
                        output_path = os.path.join(output_dir, output_path)
            else:
                # Movies or when no metadata available
                output_path = filename
                if output_dir:
                    output_path = os.path.join(output_dir, output_path)

        return output_path

    def _generate_filename(self, task: DownloadTask) -> str:
        """Generate filename from TMDB metadata or fallback"""
        if task.content_type == 'tv':
            if self.tmdb_metadata and self.tmdb_metadata.api_key:
                return self.tmdb_metadata.generate_tv_filename(
                    task.tmdb_id, task.season, task.episode  # type: ignore
                )
            else:
                return f"tv_{task.tmdb_id}_s{task.season:02d}e{task.episode:02d}.{DEFAULT_EXTENSION}"
        else:
            if self.tmdb_metadata and self.tmdb_metadata.api_key:
                return self.tmdb_metadata.generate_movie_filename(task.tmdb_id)
            else:
                return f"movie_{task.tmdb_id}.{DEFAULT_EXTENSION}"

    def download_batch(self, tasks: List[DownloadTask], output_dir: Optional[str] = None,
                      parallel_jobs: int = 1, default_lang: str = DEFAULT_LANG,
                      default_quality: str = DEFAULT_QUALITY) -> Tuple[int, int]:
        """
        Download all tasks in batch with Rich progress bars

        Returns:
            Tuple of (success_count, failed_count)
        """

        # Create output directory if specified
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        total = len(tasks)
        success_count = 0
        failed_count = 0

        # Print header (skip for single downloads)
        if total > 1:
            print(f"\nVixSrc Batch Downloader - {total} tasks - {parallel_jobs} parallel job(s)\n")

        # Check if Rich is available
        if not Progress:
            print("[!] Warning: Rich library not available, progress bars disabled")
            # Fallback to simple sequential processing
            for task in tasks:
                success = self.process_single_download(task, output_dir, default_lang, default_quality)
                if success:
                    success_count += 1
                else:
                    failed_count += 1
        else:
            # Use Rich Progress for all batch downloads
            with Progress(
                TextColumn("[bold blue]{task.description}", justify="left"),
                BarColumn(bar_width=30),
                "[progress.percentage]{task.percentage:>3.0f}%",
                TextColumn("{task.fields[bitrate]}", justify="right"),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
            ) as progress:

                if parallel_jobs > 1:
                    # Parallel execution with multiple progress bars
                    task_ids = {}
                    future_to_task = {}

                    with ThreadPoolExecutor(max_workers=parallel_jobs) as executor:
                        # Submit all tasks with their own progress bars
                        for task in tasks:
                            # Create a Rich progress task with bitrate field
                            task_id = progress.add_task(f"{task}", total=100, bitrate="")
                            task_ids[task] = task_id

                            future = executor.submit(
                                self.process_single_download,
                                task, output_dir, default_lang, default_quality, None, (progress, task_id)
                            )
                            future_to_task[future] = task

                        # Process completed tasks
                        for future in as_completed(future_to_task):
                            task = future_to_task[future]

                            try:
                                success = future.result()
                                if success:
                                    success_count += 1
                                else:
                                    failed_count += 1
                            except Exception as e:
                                failed_count += 1

                else:
                    # Sequential execution
                    for task in tasks:
                        task_id = progress.add_task(f"{task}", total=100, bitrate="")

                        success = self.process_single_download(task, output_dir, default_lang, default_quality, None, (progress, task_id))

                        if success:
                            success_count += 1
                        else:
                            failed_count += 1

        # Print summary (skip for single downloads)
        if total > 1:
            print(f"\n{'='*60}")
            print(f"Summary")
            print(f"{'='*60}")
            print(f"Total:   {total}")
            print(f"Success: {success_count}")
            print(f"Failed:  {failed_count}")
            print(f"{'='*60}\n")

        return success_count, failed_count
