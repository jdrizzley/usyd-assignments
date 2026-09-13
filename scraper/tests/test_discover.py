import re
from pathlib import Path

from scraper.discover import extract_codes, extract_page_links

FIXTURES = Path(__file__).parent / "fixtures"


def test_seo_page_codes_and_pagination():
    html = (FIXTURES / "seo_page1.html").read_text(encoding="utf-8")
    codes = extract_codes(html)
    assert len(codes) > 100
    assert all(re.match(r"^[A-Z]{4}\d{4}$", c) for c in codes)
    assert "AMME2200" in codes
    pages = extract_page_links(html, "https://www.sydney.edu.au/students/units/seo.html")
    assert len(pages) == 15
    assert pages[0] == "https://www.sydney.edu.au/students/units/seo.1.html"
    assert pages[-1].endswith("seo.15.html")
