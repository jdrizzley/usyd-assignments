"""Scraper configuration. Every value here is deliberate; see BUILD-SPEC §6.1 and §11."""
from __future__ import annotations

import os

TARGET_YEAR: int = int(os.environ.get("USYD_YEAR", "2026"))
TARGET_SESSIONS: list[str] | None = None  # None = every session in TARGET_YEAR

BASE = "https://www.sydney.edu.au"
SEO_INDEX_URL = f"{BASE}/students/units/seo.html"
ROBOTS_URL = f"{BASE}/robots.txt"

REPO_URL = "https://github.com/jdrizzley/usyd-assignments"
# Optional extra contact detail for the User-Agent. Set USYD_CONTACT in the environment
# (for example an email address) if you want one included; the repo URL is always present.
CONTACT = os.environ.get("USYD_CONTACT", "").strip()
USER_AGENT = (
    f"usyd-assessment-calendar/1.0 (+{REPO_URL}; student project"
    + (f"; contact: {CONTACT}" if CONTACT else "")
    + ")"
)

REQUEST_DELAY_S = 1.0   # minimum gap between any two requests, globally
MAX_CONCURRENCY = 2
TIMEOUT_S = 30
MAX_RETRIES = 3
BACKOFF_S = (2, 8, 32)
CACHE_DIR = os.environ.get("USYD_CACHE_DIR", ".cache")
CACHE_TTL_H = 20

SCRAPER_VERSION = "1.0.0"

# Failure thresholds for a FULL run (BUILD-SPEC §6.8).
MIN_CODES_DISCOVERED = 2000
MIN_UNITS_WITH_OUTLINE = 500
MAX_OUTLINE_FETCH_FAIL_RATIO = 0.10
MAX_ZERO_ASSESSMENT_RATIO = 0.20
# Refuse to replace existing data if the new run has fewer than this fraction of the
# previous run's units with outlines (guards against overwriting good data with thin data).
MIN_RELATIVE_UNIT_COUNT = 0.5

# Fallbacks for mode-of-attendance and location codes in availability slugs.
MODE_CODES = {
    "ND": "Normal day",
    "NE": "Normal evening",
    "BL": "Block mode",
    "RE": "Remote",
    "OL": "Online",
    "DE": "Distance education",
    "FE": "Field experience",
    "IN": "Intensive",
    "PR": "Professional practice",
    "SU": "Supervision",
}
LOCATION_CODES = {
    "CC": "Camperdown/Darlington, Sydney",
    "RE": "Remote",
    "OL": "Online",
    "CU": "Cumberland, Sydney",
    "SC": "Sydney Conservatorium of Music",
    "SCA": "Sydney College of the Arts",
    "WM": "Westmead, Sydney",
    "CN": "Camden",
    "CM": "Camden",
    "MQ": "Mallett Street, Sydney",
    "RO": "Rozelle, Sydney",
    "SUR": "Surry Hills, Sydney",
    "SH": "Surry Hills, Sydney",
    "OR": "Orange",
    "DU": "Dubbo",
    "LI": "Lismore",
    "BH": "Broken Hill",
    "NB": "Narrabri",
    "OSC": "Off campus",
}
