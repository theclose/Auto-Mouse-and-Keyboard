"""
Update checker — compares local version with latest GitHub release.

Non-blocking: runs in a background thread, emits result via callback.
Never stalls the UI — fails silently on network errors.
"""

import logging
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# GitHub API endpoint for latest release
_GITHUB_API = "https://api.github.com/repos/theclose/Auto-Mouse-and-Keyboard/releases/latest"


def check_for_update(
    current_version: str,
    on_result: Optional[Callable[[bool, str, str], None]] = None,
    timeout: float = 5.0,
) -> None:
    """Check GitHub for a newer release (non-blocking).

    Args:
        current_version: Current app version, e.g. "3.0.0"
        on_result: Callback(has_update: bool, latest_version: str, download_url: str)
                   Called from a background thread — use signal if updating UI.
        timeout: HTTP request timeout in seconds.
    """

    def _worker() -> None:
        try:
            import json
            import urllib.request

            req = urllib.request.Request(
                _GITHUB_API,
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            tag = data.get("tag_name", "")
            # Strip leading 'v' if present (e.g. "v3.1.0" → "3.1.0")
            latest = tag.lstrip("vV")
            html_url = data.get("html_url", "")

            if not latest:
                logger.debug("Update check: no tag_name in response")
                return

            has_update = _version_compare(latest, current_version) > 0

            if has_update:
                logger.info("New version available: %s (current: %s)", latest, current_version)
            else:
                logger.debug("Up to date: %s", current_version)

            if on_result:
                on_result(has_update, latest, html_url)

        except Exception as e:
            # Fail silently — update check is best-effort
            logger.debug("Update check failed: %s", e)

    thread = threading.Thread(target=_worker, name="UpdateChecker", daemon=True)
    thread.start()


def _version_compare(a: str, b: str) -> int:
    """Compare two semver strings. Returns >0 if a > b, <0 if a < b, 0 if equal."""
    def _parse(v: str) -> tuple[int, ...]:
        parts = []
        for p in v.split("."):
            try:
                parts.append(int(p))
            except ValueError:
                parts.append(0)
        # Pad to at least 3 parts
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts)

    pa, pb = _parse(a), _parse(b)
    if pa > pb:
        return 1
    if pa < pb:
        return -1
    return 0
