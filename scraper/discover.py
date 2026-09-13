"""Discover every unit code from the seo.html listing (BUILD-SPEC §3.2, §6.3)."""
from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from . import config
from .fetch import Fetcher

log = logging.getLogger("scraper.discover")

# Links are relative on the live site ("/units/AMME2200") but the spec documents them as
# absolute. Accept both.
RE_UNIT_HREF = re.compile(r"^(?:https?://www\.sydney\.edu\.au)?/units/([A-Z]{4}\d{4})/?$")
RE_PAGE_HREF = re.compile(r"seo\.(\d+)\.html$")
RE_CODE = re.compile(r"^[A-Z]{4}\d{4}$")

EXPECTED_PAGE_COUNT = 15


class DiscoveryError(Exception):
    pass


def extract_codes(html: str) -> set[str]:
    soup = BeautifulSoup(html, "lxml")
    out: set[str] = set()
    for a in soup.find_all("a", href=True):
        m = RE_UNIT_HREF.match(a["href"].strip())
        if m:
            out.add(m.group(1))
    return out


def extract_page_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    pages: dict[int, str] = {}
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        m = RE_PAGE_HREF.search(href)
        if m:
            pages[int(m.group(1))] = urljoin(base_url, href)
    return [pages[n] for n in sorted(pages)]


def discover_codes(fetcher: Fetcher) -> list[str]:
    first = fetcher.get(config.SEO_INDEX_URL)
    if first is None:
        raise DiscoveryError(f"{config.SEO_INDEX_URL} returned 404 or is disallowed")
    codes = extract_codes(first)
    pages = extract_page_links(first, config.SEO_INDEX_URL)
    if len(pages) != EXPECTED_PAGE_COUNT:
        log.warning("expected %d pagination links, found %d", EXPECTED_PAGE_COUNT, len(pages))
    for url in pages:
        body = fetcher.get(url)
        if body is None:
            log.warning("pagination page missing: %s", url)
            continue
        found = extract_codes(body)
        log.debug("%s -> %d codes", url, len(found))
        codes |= found
    bad = [c for c in codes if not RE_CODE.match(c)]
    if bad:
        raise DiscoveryError(f"malformed codes extracted: {bad[:5]}")
    result = sorted(codes)
    log.info("discovered %d unit codes across %d pages", len(result), len(pages) + 1)
    if len(result) < config.MIN_CODES_DISCOVERED:
        raise DiscoveryError(
            f"only {len(result)} codes discovered (< {config.MIN_CODES_DISCOVERED}); "
            "the seo.html page structure has probably changed"
        )
    return result


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    for c in discover_codes(Fetcher()):
        print(c)
