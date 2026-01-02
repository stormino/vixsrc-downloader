"""Progress tracking for downloads."""

import re
from typing import Optional, Tuple

from .constants import (
    STATUS_ICON_SUCCESS,
    STATUS_ICON_FAILURE,
    PATTERN_DURATION,
    PATTERN_FFMPEG_TIME,
    PATTERN_FFMPEG_BITRATE,
    PATTERN_YTDLP_PROGRESS
)

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None  # type: ignore

try:
    from rich.progress import Progress, TaskID
except ImportError:
    Progress = None  # type: ignore
    TaskID = None  # type: ignore


class ProgressTracker:
    """Unified progress tracking for both tqdm and rich progress bars"""

    def __init__(self,
                 progress_bar: Optional['tqdm'] = None,
                 rich_progress: Optional[Tuple['Progress', 'TaskID']] = None,
                 quiet: bool = False):
        """
        Initialize tracker with either tqdm or rich progress.

        Args:
            progress_bar: tqdm progress bar (batch mode)
            rich_progress: Tuple of (Progress, TaskID) for rich
            quiet: Suppress console logging
        """
        self.progress_bar = progress_bar
        self.rich_progress = rich_progress
        self.quiet = quiet
        self.last_percent = 0.0

    def log(self, message: str, prefix: str = "*", force: bool = False) -> None:
        """Log message if not quiet (or if forced)"""
        if not self.quiet or force:
            print(f"[{prefix}] {message}")

    def has_progress_ui(self) -> bool:
        """Check if any progress UI is active"""
        return self.progress_bar is not None or self.rich_progress is not None

    def update_percent(self, percent: float, description: Optional[str] = None) -> None:
        """
        Update progress to specific percentage.

        Args:
            percent: Percentage complete (0-100)
            description: Optional description update
        """
        if percent <= self.last_percent:
            return

        if self.rich_progress:
            progress_obj, task_id = self.rich_progress
            update_kwargs = {"completed": percent}
            if description:
                update_kwargs["description"] = f"[bold blue]{description}"
            progress_obj.update(task_id, **update_kwargs)

        elif self.progress_bar:
            delta = percent - self.last_percent
            self.progress_bar.update(delta)
            if description:
                self.progress_bar.set_description(f"{description[:30]} {percent:.1f}%")

        self.last_percent = percent

    def update_with_metadata(self, percent: float, bitrate: str = "",
                            description: Optional[str] = None) -> None:
        """
        Update with additional metadata (bitrate, speed, etc).

        Args:
            percent: Percentage complete
            bitrate: Bitrate string for rich progress
            description: Optional description
        """
        if percent <= self.last_percent:
            return

        if self.rich_progress:
            progress_obj, task_id = self.rich_progress
            update_kwargs = {"completed": percent}
            if bitrate:
                update_kwargs["bitrate"] = bitrate
            if description:
                update_kwargs["description"] = f"[bold blue]{description}"
            progress_obj.update(task_id, **update_kwargs)

        elif self.progress_bar:
            delta = percent - self.last_percent
            self.progress_bar.update(delta)
            if description:
                self.progress_bar.set_description(f"{description[:30]} {percent:.1f}%")

        self.last_percent = percent

    def set_description(self, description: str, status_icon: str = "") -> None:
        """
        Update description only.

        Args:
            description: New description
            status_icon: Icon prefix (✓, ✗, etc)
        """
        full_desc = f"{status_icon} {description}" if status_icon else description

        if self.rich_progress:
            progress_obj, task_id = self.rich_progress
            progress_obj.update(task_id, description=full_desc)
        elif self.progress_bar:
            self.progress_bar.set_description(full_desc[:60])
            self.progress_bar.refresh()

    def mark_complete(self, success: bool, description: str) -> None:
        """
        Mark task as complete with success/failure status.

        Args:
            success: Whether task succeeded
            description: Task description
        """
        icon = STATUS_ICON_SUCCESS if success else STATUS_ICON_FAILURE

        if self.rich_progress:
            progress_obj, task_id = self.rich_progress
            if success:
                progress_obj.update(task_id, completed=100, description=f"{icon} {description}")
            else:
                progress_obj.update(task_id, description=f"{icon} {description}")
        elif self.progress_bar:
            if success and self.last_percent < 100:
                self.progress_bar.update(100 - self.last_percent)
            self.progress_bar.set_description(f"{icon} {description[:50]}")
            self.progress_bar.refresh()


class ProgressParser:
    """Parse yt-dlp/ffmpeg output for progress updates"""

    def __init__(self, tracker: ProgressTracker, filename: str):
        """
        Initialize parser.

        Args:
            tracker: Progress tracker to update
            filename: Output filename for display
        """
        self.tracker = tracker
        self.filename = filename
        self.total_duration: Optional[float] = None

    def parse_line(self, line: str) -> None:
        """Parse a single line of output"""
        # Try to extract total duration from ffmpeg
        if 'Duration:' in line and self.total_duration is None:
            self._parse_duration(line)

        # Parse ffmpeg progress line
        elif 'frame=' in line and 'time=' in line:
            self._parse_ffmpeg_progress(line)

        # Parse yt-dlp progress template
        elif 'PROGRESS:' in line:
            self._parse_ytdlp_progress(line)

    def _parse_duration(self, line: str) -> None:
        """Extract total duration from ffmpeg output"""
        duration_match = re.search(PATTERN_DURATION, line)
        if duration_match:
            hours, minutes, seconds = duration_match.groups()
            self.total_duration = (
                int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            )

    def _parse_ffmpeg_progress(self, line: str) -> None:
        """Parse ffmpeg progress line"""
        if not self.total_duration:
            return

        time_match = re.search(PATTERN_FFMPEG_TIME, line)
        bitrate_match = re.search(PATTERN_FFMPEG_BITRATE, line, re.IGNORECASE)

        if time_match:
            hours, minutes, seconds = time_match.groups()
            current_time = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            percent = (current_time / self.total_duration) * 100

            if percent <= 100:
                bitrate_str = ""
                if bitrate_match:
                    bitrate_val = bitrate_match.group(1)
                    bitrate_unit = bitrate_match.group(2)
                    bitrate_str = f"{bitrate_val}{bitrate_unit}"

                self.tracker.update_with_metadata(percent, bitrate_str)

    def _parse_ytdlp_progress(self, line: str) -> None:
        """Parse yt-dlp progress template output"""
        try:
            percent_match = re.search(PATTERN_YTDLP_PROGRESS, line)
            if percent_match:
                percent = float(percent_match.group(1))
                self.tracker.update_percent(percent)
        except Exception:
            pass

    def finalize_success(self) -> None:
        """Mark download as successful"""
        self.tracker.mark_complete(True, self.filename)

    def finalize_failure(self) -> None:
        """Mark download as failed"""
        self.tracker.mark_complete(False, self.filename)
