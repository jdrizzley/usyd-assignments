"""HTTP fetching: one session, global throttle, retries, on-disk cache, robots.txt.

BUILD-SPEC §6.2 and §11.
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
import urllib.robotparser
from dataclasses import dataclass, field
from pathlib import Path

import requests

from . import config

log = logging.getLogger("scraper.fetch")


class FetchError(Exception):
    """Raised when a URL could not be retrieved after all retries."""


@dataclass
class FetchStats:
    requests: int = 0
    cache_hits: int = 0
    not_found: int = 0
    failures: int = 0
    robots_skipped: int = 0
    failed_urls: list[str] = field(default_factory=list)
    skipped_urls: list[str] = field(default_factory=list)


class Fetcher:
    """A polite HTTP client. Thread-safe; one instance per run."""

    def __init__(
        self,
        cache_dir: str | os.PathLike = config.CACHE_DIR,
        use_cache: bool = True,
        delay_s: float = config.REQUEST_DELAY_S,
        respect_robots: bool = True,
    ) -> None:
        self.session = requests.Session()
        self.session.headers["User-Agent"] = config.USER_AGENT
        self.session.headers["Accept"] = "text/html,application/xhtml+xml"
        self.cache_dir = Path(cache_dir)
        self.use_cache = use_cache
        self.delay_s = delay_s
        self._lock = threading.Lock()
        self._last_request = 0.0
        self.stats = FetchStats()
        self._robots: urllib.robotparser.RobotFileParser | None = None
        if respect_robots:
            self._load_robots()

    # -- robots ----------------------------------------------------------------
    def _load_robots(self) -> None:
        rp = urllib.robotparser.RobotFileParser()
        try:
            body = self._raw_get(config.ROBOTS_URL, allow_cache=True)
            if body is None:
                log.warning("robots.txt returned 404; treating everything as allowed")
                rp.parse([])
            else:
                rp.parse(body.splitlines())
                log.info("robots.txt loaded (%d lines)", len(body.splitlines()))
        except FetchError as exc:
            # Be conservative: if we cannot read robots.txt, treat everything as allowed
            # is the wrong default for a scraper. Fail the run instead.
            raise FetchError(f"Could not fetch robots.txt: {exc}") from exc
        self._robots = rp

    def allowed(self, url: str) -> bool:
        if self._robots is None:
            return True
        return self._robots.can_fetch(config.USER_AGENT, url) and self._robots.can_fetch("*", url)

    # -- cache -----------------------------------------------------------------
    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / (hashlib.sha256(url.encode("utf-8")).hexdigest() + ".html")

    def _cache_read(self, url: str) -> str | None | bool:
        """Return body, None for a cached 404, or False when there is no fresh cache entry."""
        if not self.use_cache:
            return False
        p = self._cache_path(url)
        p404 = p.with_suffix(".404")
        for candidate, value in ((p, None), (p404, None)):
            if candidate.exists():
                age_h = (time.time() - candidate.stat().st_mtime) / 3600
                if age_h < config.CACHE_TTL_H:
                    if candidate is p404:
                        return None
                    return candidate.read_text(encoding="utf-8")
        return False

    def _cache_write(self, url: str, body: str | None) -> None:
        if not self.use_cache:
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        p = self._cache_path(url)
        if body is None:
            p.with_suffix(".404").write_text("", encoding="utf-8")
        else:
            tmp = p.with_suffix(".tmp")
            tmp.write_text(body, encoding="utf-8")
            os.replace(tmp, p)

    # -- throttle --------------------------------------------------------------
    def _throttle(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = self._last_request + self.delay_s - now
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.monotonic()

    # -- core ------------------------------------------------------------------
    def _raw_get(self, url: str, allow_cache: bool = True) -> str | None:
        cached = self._cache_read(url) if allow_cache else False
        if cached is not False:
            self.stats.cache_hits += 1
            log.debug("cache hit  %s", url)
            return cached  # type: ignore[return-value]

        last_exc: Exception | None = None
        for attempt in range(config.MAX_RETRIES + 1):
            self._throttle()
            self.stats.requests += 1
            log.debug("GET %s (attempt %d)", url, attempt + 1)
            try:
                resp = self.session.get(url, timeout=config.TIMEOUT_S)
            except requests.RequestException as exc:
                last_exc = exc
                log.warning("connection error on %s: %s", url, exc)
            else:
                if resp.status_code == 404:
                    self.stats.not_found += 1
                    self._cache_write(url, None)
                    return None
                if resp.status_code == 200:
                    body = resp.text
                    self._cache_write(url, body)
                    return body
                if resp.status_code == 429 or resp.status_code >= 500:
                    last_exc = FetchError(f"HTTP {resp.status_code}")
                    log.warning("HTTP %s on %s", resp.status_code, url)
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        time.sleep(min(int(retry_after), 300))
                else:
                    # 4xx other than 404/429: not retryable
                    raise FetchError(f"HTTP {resp.status_code} for {url}")
            if attempt < config.MAX_RETRIES:
                time.sleep(config.BACKOFF_S[min(attempt, len(config.BACKOFF_S) - 1)])
        raise FetchError(f"gave up on {url}: {last_exc}")

    def get(self, url: str) -> str | None:
        """Fetch a page. Returns the body, or None for 404 / robots-disallowed.

        Raises FetchError after retries are exhausted (and records the failure).
        """
        if not self.allowed(url):
            self.stats.robots_skipped += 1
            self.stats.skipped_urls.append(url)
            log.warning("robots.txt disallows %s; skipping", url)
            return None
        try:
            return self._raw_get(url)
        except FetchError:
            self.stats.failures += 1
            self.stats.failed_urls.append(url)
            raise
