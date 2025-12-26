"""Playlist URL extraction from vixsrc.to."""

import json
import re
from typing import Optional, Any
from urllib.parse import urljoin

from .constants import (
    PATTERN_MASTER_PLAYLIST,
    PATTERN_PLAYLIST_DIRECT,
    PATTERN_API_ENDPOINTS,
    PATTERN_VIDEO_ID
)
from .progress import ProgressTracker


class PlaylistExtractor:
    """Extract HLS playlist URLs from vixsrc.to embed pages"""

    def __init__(self, session: Any, base_url: str, lang: str,
                 timeout: int, tracker: ProgressTracker):
        """
        Initialize extractor.

        Args:
            session: Cloudscraper session for requests
            base_url: VixSrc base URL
            lang: Language code
            timeout: Request timeout
            tracker: Progress tracker for logging
        """
        self.session = session
        self.base_url = base_url
        self.lang = lang
        self.timeout = timeout
        self.tracker = tracker

    def extract(self, embed_url: str) -> Optional[str]:
        """
        Extract playlist URL using multiple strategies.

        Args:
            embed_url: Embed page URL

        Returns:
            Playlist URL or None
        """
        self.tracker.log(f"Fetching embed page: {embed_url}")

        try:
            response = self.session.get(embed_url, timeout=self.timeout)
            response.raise_for_status()
            html_content = response.text

            # Try extraction strategies in order
            strategies = [
                self._extract_from_master_playlist,
                self._extract_from_direct_pattern,
                self._extract_from_api_endpoints,
                self._extract_from_video_id
            ]

            for strategy in strategies:
                playlist_url = strategy(html_content, embed_url)
                if playlist_url:
                    return playlist_url

            self.tracker.log("Could not extract playlist URL from page", "!")
            self.tracker.log("Page may require JavaScript execution or format has changed", "*")
            return None

        except Exception as e:
            self.tracker.log(f"Error fetching embed page: {e}", "!")
            return None

    def _extract_from_master_playlist(self, html: str, embed_url: str) -> Optional[str]:
        """Strategy 1: Extract from window.masterPlaylist object"""
        master_playlist_section = re.search(PATTERN_MASTER_PLAYLIST, html)

        if not master_playlist_section:
            return None

        section_text = master_playlist_section.group(0)

        # Extract components
        url_match = re.search(r"url:\s*['\"]([^'\"]+)['\"]", section_text)
        token_match = re.search(r"['\"]token['\"]\s*:\s*['\"]([^'\"]+)['\"]", section_text)
        expires_match = re.search(r"['\"]expires['\"]\s*:\s*['\"]([^'\"]+)['\"]", section_text)

        if not (url_match and token_match and expires_match):
            return None

        # Build URL with parameters
        playlist_url = self._build_playlist_url(
            url_match.group(1),
            token_match.group(1),
            expires_match.group(1),
            section_text
        )

        # Verify playlist
        if self._verify_playlist(playlist_url, embed_url):
            return playlist_url

        # Return anyway, might work
        return playlist_url

    def _build_playlist_url(self, base: str, token: str, expires: str,
                           section_text: str) -> str:
        """Build complete playlist URL with all required parameters"""
        asn_match = re.search(r"['\"]asn['\"]\s*:\s*['\"]([^'\"]*)['\"]", section_text)
        asn = asn_match.group(1) if asn_match else ""

        params = [
            f"token={token}",
            f"expires={expires}"
        ]
        if asn:
            params.append(f"asn={asn}")
        params.extend([
            "h=1",  # Required parameter
            f"lang={self.lang}"
        ])

        separator = '&' if '?' in base else '?'
        url = f"{base}{separator}{'&'.join(params)}"

        # Clean HTML entities
        return url.replace('&amp;', '&')

    def _verify_playlist(self, url: str, referer: str) -> bool:
        """Verify playlist URL by checking for #EXTM3U header"""
        try:
            self.tracker.log("Verifying playlist URL...")
            headers = {'Referer': referer, 'Accept': '*/*'}
            response = self.session.get(url, headers=headers, timeout=self.timeout)

            if response.ok and response.text.startswith('#EXTM3U'):
                self.tracker.log("Playlist URL verified successfully", "+")
                return True
            else:
                self.tracker.log(f"Playlist verification failed: {response.status_code}", "!")
                return False
        except Exception as e:
            self.tracker.log(f"Playlist verification error: {e}", "!")
            return False

    def _extract_from_direct_pattern(self, html: str, embed_url: str) -> Optional[str]:
        """Strategy 2: Direct regex pattern match"""
        match = re.search(PATTERN_PLAYLIST_DIRECT, html)

        if match:
            url = match.group(0).replace('&amp;', '&')
            self.tracker.log(f"Found playlist URL: {url}", "+")
            return url
        return None

    def _extract_from_api_endpoints(self, html: str, embed_url: str) -> Optional[str]:
        """Strategy 3: Try API endpoints found in JavaScript"""
        api_matches = re.findall(PATTERN_API_ENDPOINTS, html)

        if not api_matches:
            return None

        self.tracker.log(f"Found API endpoints: {api_matches}")

        for api_path in api_matches:
            api_url = urljoin(self.base_url, api_path)
            try:
                api_response = self.session.get(api_url, timeout=self.timeout)
                if api_response.ok:
                    try:
                        data = api_response.json()
                        playlist_url = self._find_playlist_in_json(data)
                        if playlist_url:
                            self.tracker.log(f"Found playlist URL from API: {playlist_url}", "+")
                            return playlist_url
                    except json.JSONDecodeError:
                        pass
            except Exception as e:
                self.tracker.log(f"API call failed for {api_url}: {e}", "!")

        return None

    def _find_playlist_in_json(self, data: Any) -> Optional[str]:
        """Recursively search JSON for playlist URLs"""
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str) and ('m3u8' in value or 'playlist' in value):
                    return value
        return None

    def _extract_from_video_id(self, html: str, embed_url: str) -> Optional[str]:
        """Strategy 4: Extract video ID and try common patterns"""
        video_id_match = re.search(PATTERN_VIDEO_ID, html, re.IGNORECASE)

        if not video_id_match:
            return None

        video_id = video_id_match.group(1)
        possible_urls = [
            f"{self.base_url}/playlist/{video_id}",
            f"{self.base_url}/api/playlist/{video_id}",
        ]

        for test_url in possible_urls:
            try:
                response = self.session.get(test_url, timeout=self.timeout,
                                          allow_redirects=True)
                content_type = response.headers.get('content-type', '')
                if response.ok and ('m3u8' in response.text or
                                   content_type.startswith('application/')):
                    self.tracker.log(f"Found valid playlist URL: {response.url}", "+")
                    return response.url
            except Exception:
                pass

        return None
