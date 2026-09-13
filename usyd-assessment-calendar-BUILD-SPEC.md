# BUILD SPEC — USyd Assessment Calendar

You are building a complete, working web application from this specification. Build the entire
thing in one pass. Every technical decision below has already been made and verified — implement
it as written rather than proposing alternatives. Where the spec says "verify", write code that
checks the condition and fails loudly.

---

## 1. What this is

A static website where a University of Sydney student types in their unit codes for a semester
(e.g. `AMME2200`, `ELEC3204`, `COMP3308`) and immediately gets:

- a consolidated list/calendar of every assessment due date across those units
- a downloadable `.ics` file they can import into Google Calendar / Apple Calendar / Outlook

The assessment data comes from USyd's public unit-of-study outline pages, scraped ahead of time
by a scheduled job and committed to the repo as static JSON. **No backend server exists.** The
website is pure static files.

### Why the data is pre-scraped

The browser cannot fetch `sydney.edu.au` directly — CORS will block it. And fetching the
university's pages once per page-load would be both slow and abusive. So: a GitHub Actions cron
job scrapes, writes JSON into the repo, and the static site reads that JSON.

```
┌─────────────────────────────┐
│ GitHub Actions (daily cron) │
│   scraper/ (Python)         │
│   → hits sydney.edu.au      │
│   → writes data/*.json      │
│   → git commit + push       │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ GitHub Pages / CF Pages     │
│   web/ (vanilla HTML+JS)    │
│   fetch('data/index.json')  │
│   fetch('data/units/X.json')│
│   → render + build .ics     │
└─────────────────────────────┘
```

---

## 2. Locked-in technology decisions

| Concern | Decision | Rationale |
|---|---|---|
| Scraper language | Python 3.11 | Owner knows Python; parsing libs are mature |
| HTML parsing | `beautifulsoup4` + `lxml` parser | Pages are server-rendered HTML |
| HTTP | `requests` with a `Session` | No JS rendering needed — verified |
| Frontend | Vanilla HTML + CSS + JS (ES modules), **no build step, no framework, no npm** | Owner has no web experience; a build step is pure friction here |
| ICS generation | Hand-rolled in browser JS | ~60 lines; avoids any dependency or server |
| Scheduling | GitHub Actions `schedule` cron | Free, lives beside the code |
| Hosting | GitHub Pages (primary), Cloudflare Pages (documented alternative) | Free, zero config, serves the repo's JSON directly |
| Storage | JSON files committed to git | Free, versioned, diffable, no database |

Do **not** introduce: React, Vite, Tailwind, a bundler, a database, Selenium/Playwright, or a
server framework. The pages are static HTML and `requests` is sufficient — this has been verified
against the live site.

---

## 3. Verified facts about the data source

These were checked against the live site. Build against them, but write defensive code.

### 3.1 URL patterns

| Purpose | URL |
|---|---|
| Master list of all unit codes | `https://www.sydney.edu.au/students/units/seo.html` and `seo.1.html` … `seo.15.html` |
| Unit landing page (lists availabilities) | `https://www.sydney.edu.au/units/{CODE}` |
| Outline for one availability | `https://www.sydney.edu.au/units/{CODE}/{AVAILABILITY}` |

`{AVAILABILITY}` has the form `{YEAR}-{SESSION}-{MOA}-{LOCATION}`, e.g. `2026-S2C-ND-CC`
(2026, Semester 2, Normal Day, Camperdown/Darlington). **Do not construct this string yourself** —
session and location codes vary between units and include intensive/remote variants. Always read
it out of the unit landing page.

### 3.2 The master code listing (`seo.html`)

Paginated across `seo.html` (page 1) and `seo.1.html` through `seo.15.html`. Each page is a flat
list of anchors:

```html
<a href="https://www.sydney.edu.au/units/AMME2200">AMME2200</a>
```

Roughly 6,000 unit codes total. Extract with a regex over hrefs:
`https://www\.sydney\.edu\.au/units/([A-Z]{4}\d{4})$`. Deduplicate and sort.

**Do not hardcode 15 pages.** Parse the pagination links at the bottom of page 1 and follow every
distinct `seo.N.html` you find. If the count differs from 15, log a warning but continue.

### 3.3 The unit landing page

Contains a section headed **"Unit availability"** with two tables: the first is the current year,
the second (under a "Previous years" tab) is historical. Both contain rows of
`Session | MoA | Location | Outline`, where the Outline cell holds a link like:

```html
<a href="https://www.sydney.edu.au/units/AMME2200/2026-S2C-ND-CC">View</a>
```

**Parsing rule:** collect *all* outline links on the page via regex
`/units/([A-Z]{4}\d{4})/(\d{4})-([A-Z0-9]+)-([A-Z]+)-([A-Z]+)`, then filter by the year captured
in the URL rather than trying to work out which HTML table you're in. Keep only links whose year
matches the target year from config. This is robust to the tabbed markup.

Note: the outline is only published ~2 weeks before teaching starts. A unit may have a landing
page but no current-year outline. That is a normal, expected state — record it, don't error.

### 3.4 The outline page — the important one

Contains a section anchored at `#assessment_panel` holding the assessment table. Real structure,
columns in order:

```
Type | Description | Weight | Due | Length | Use of AI
```

Interleaved between data rows are full-width rows reading `Outcomes assessed: LO1 LO2`. **Skip
any row whose first cell's text starts with "Outcomes assessed"**, and skip the final legend row
containing the early-feedback-task icon.

A verified real row (AMME2200, S2 2026), cell by cell:

| Cell | Content |
|---|---|
| Type | `Practical skill` |
| Description | `Assignment-Fluids` then `Assess learning of topics in fluids` |
| Weight | `6%` |
| Due | `Week 05` `Due date: 31 Aug 2026 at 23:59` `Closing date: 13 Nov 2026` |
| Length | `12 hours over 4 weeks.` |
| Use of AI | `AI allowed` |

**Due-cell variants you must handle** (get the cell's text with `get_text(" ", strip=True)` first,
which collapses the internal `<br>`/`<strong>` structure into one space-separated string):

| Raw text | Parse to |
|---|---|
| `Week 03 Due date: 17 Aug 2026 at 23:00 Closing date: 06 Nov 2026` | week 3, due 2026-08-17T23:00 |
| `Week 05 Due date: 04 Sep 2026 at 11:00 Closing date: 04 Sep 2026` | week 5, due 2026-09-04T11:00 |
| `Formal exam period` | no week, no date, `dateKind: "exam_period"` |
| `Week 08` (no absolute date) | week 8, `dateKind: "week_only"` |
| `Multiple weeks` / `Ongoing` / anything else | `dateKind: "unparsed"`, keep raw text |

Regexes:

```python
RE_DUE   = re.compile(r"Due date:\s*(\d{1,2}\s+\w{3}\s+\d{4})(?:\s*at\s*(\d{1,2}:\d{2}))?", re.I)
RE_CLOSE = re.compile(r"Closing date:\s*(\d{1,2}\s+\w{3}\s+\d{4})(?:\s*at\s*(\d{1,2}:\d{2}))?", re.I)
RE_WEEK  = re.compile(r"Week\s*(\d{1,2})", re.I)
RE_EXAM  = re.compile(r"formal exam period", re.I)
```

Parse dates with `datetime.strptime(s, "%d %b %Y")`. If time is absent, default to `23:59`
and set `timeAssumed: true`.

**Other fields on the outline page:**

- Unit title: the `<h1>`, e.g. `AMME2200: Introductory Thermofluids`. Split on the first `: `.
- Session heading: e.g. `Semester 2, 2026 [Normal day] - Camperdown/Darlington, Sydney`.
- Census date: prose reading `The census date for this unit availability is 31 August 2026`.
  Regex: `census date for this unit availability is\s*(\d{1,2}\s+\w+\s+\d{4})` with `%d %B %Y`.
- Early feedback task marker: the Type cell contains an `<img>` whose `alt` or `title` is
  `Early Feedback Task`. Set `earlyFeedback: true`.
- Description cell: first `<strong>` is the assessment *name*; the remaining text is the
  *description*. If no `<strong>`, use the whole text as the name and leave description empty.

---

## 4. Repository layout

```
usyd-assessment-calendar/
├── README.md
├── LICENSE                          # MIT
├── .gitignore
├── scraper/
│   ├── requirements.txt             # requests, beautifulsoup4, lxml
│   ├── config.py                    # YEAR, SESSIONS, rate limits, user agent
│   ├── fetch.py                     # HTTP session, retries, throttle, caching
│   ├── discover.py                  # seo.html → all unit codes
│   ├── availability.py              # unit landing page → outline URLs
│   ├── outline.py                   # outline page → Assessment objects
│   ├── calendar_infer.py            # derive teaching-week → date map
│   ├── build.py                     # orchestrator; writes data/
│   └── tests/
│       ├── fixtures/
│       │   ├── outline_amme2200_2026s2.html
│       │   ├── unit_amme2200.html
│       │   └── seo_page1.html
│       └── test_outline.py
├── data/                            # generated; committed by CI
│   ├── meta.json
│   ├── index.json
│   ├── weeks.json
│   ├── weeks.override.json          # hand-maintained, optional
│   └── units/
│       └── AMME2200-2026-S2C-ND-CC.json
├── web/
│   ├── index.html
│   ├── styles.css
│   └── js/
│       ├── app.js
│       ├── data.js
│       ├── ics.js
│       └── render.js
└── .github/workflows/
    └── scrape.yml
```

GitHub Pages must serve from the repo root so that `web/index.html` can reach `../data/`. To keep
this simple: **put `index.html`, `styles.css` and `js/` at the repo root, not in `web/`**, and
have them fetch `./data/...`. Adjust the tree above accordingly — the root-level layout is the one
to build.

---

## 5. Data model

### 5.1 `data/meta.json`

```json
{
  "generatedAt": "2026-09-13T17:02:11Z",
  "targetYear": 2026,
  "targetSessions": ["S1C", "S2C"],
  "unitsDiscovered": 6042,
  "unitsWithCurrentOutline": 3117,
  "assessmentsTotal": 18455,
  "assessmentsWithAbsoluteDate": 14201,
  "scraperVersion": "1.0.0",
  "errors": 12
}
```

### 5.2 `data/index.json`

Loaded on every page visit, so it must stay small (target < 1 MB). One entry per *availability*
that has a published outline in the target year.

```json
[
  {
    "code": "AMME2200",
    "name": "Introductory Thermofluids",
    "availability": "2026-S2C-ND-CC",
    "session": "S2C",
    "sessionLabel": "Semester 2, 2026",
    "mode": "Normal day",
    "location": "Camperdown/Darlington, Sydney",
    "assessmentCount": 8,
    "file": "data/units/AMME2200-2026-S2C-ND-CC.json"
  }
]
```

Sort by `code`, then `availability`.

### 5.3 `data/units/{CODE}-{AVAILABILITY}.json`

```json
{
  "code": "AMME2200",
  "name": "Introductory Thermofluids",
  "availability": "2026-S2C-ND-CC",
  "session": "S2C",
  "sessionLabel": "Semester 2, 2026",
  "mode": "Normal day",
  "location": "Camperdown/Darlington, Sydney",
  "censusDate": "2026-08-31",
  "sourceUrl": "https://www.sydney.edu.au/units/AMME2200/2026-S2C-ND-CC",
  "scrapedAt": "2026-09-13T17:02:11Z",
  "assessments": [
    {
      "id": "AMME2200-2026-S2C-ND-CC-3",
      "name": "Assignment-Fluids",
      "description": "Assess learning of topics in fluids",
      "type": "Practical skill",
      "weight": 6,
      "weightRaw": "6%",
      "week": 5,
      "dateKind": "absolute",
      "dueDate": "2026-08-31",
      "dueTime": "23:59",
      "timeAssumed": false,
      "closingDate": "2026-11-13",
      "length": "12 hours over 4 weeks.",
      "aiPolicy": "AI allowed",
      "earlyFeedback": false,
      "dueRaw": "Week 05 Due date: 31 Aug 2026 at 23:59 Closing date: 13 Nov 2026"
    }
  ]
}
```

`dateKind` ∈ `"absolute" | "week_only" | "exam_period" | "unparsed"`.
`weight` is a number or `null`; always preserve `weightRaw`.
`id` is stable: availability slug + zero-based row index.
`dueRaw` is always preserved — it is the escape hatch when parsing degrades.

### 5.4 `data/weeks.json`

Maps teaching week numbers to Monday dates, per session. Used to place `week_only` assessments.

```json
{
  "2026-S1C": { "1": "2026-02-23", "2": "2026-03-02", "13": "2026-06-01",
                "confidence": "inferred", "samples": 812 },
  "2026-S2C": { "1": "2026-08-03", "2": "2026-08-10",
                "confidence": "inferred", "samples": 934 }
}
```

---

## 6. Scraper specification

### 6.1 `config.py`

```python
TARGET_YEAR      = 2026          # overridable by env var USYD_YEAR
TARGET_SESSIONS  = None          # None = all sessions for that year
BASE             = "https://www.sydney.edu.au"
USER_AGENT       = ("usyd-assessment-calendar/1.0 (+https://github.com/<owner>/<repo>; "
                    "student project; contact: <email>)")
REQUEST_DELAY_S  = 1.0           # minimum gap between requests
MAX_CONCURRENCY  = 2
TIMEOUT_S        = 30
MAX_RETRIES      = 3
CACHE_DIR        = ".cache"
CACHE_TTL_H      = 20
```

### 6.2 `fetch.py`

- One `requests.Session` with the `User-Agent` above.
- Global throttle: enforce `REQUEST_DELAY_S` between requests (a lock + last-request timestamp).
- Retries on connection errors and HTTP 5xx/429 with exponential backoff (2s, 8s, 32s).
  Honour a `Retry-After` header if present. Give up after `MAX_RETRIES` and record the failure.
- HTTP 404 is not retried — it means the availability doesn't exist. Return `None`.
- **On-disk cache**: key on `sha256(url)`, store the response body under `CACHE_DIR`. Skip the
  network if the cached file is younger than `CACHE_TTL_H`. This makes local development and
  re-runs cheap, and means a failed CI run doesn't re-hammer the university.
- Log every request at DEBUG, every failure at WARNING.

### 6.3 `discover.py`

Fetch `seo.html`, extract unit codes, parse the pagination links, fetch each further page, union
the results. Return a sorted list of codes. Fail the build if fewer than 2,000 codes are found —
that indicates the page structure changed.

### 6.4 `availability.py`

Given a code, fetch `{BASE}/units/{CODE}` and return a list of dicts:
`{code, availability, year, session, mode, location, sessionLabel, outlineUrl}`.

Use the regex from §3.3 over all hrefs, filter to `year == TARGET_YEAR`. For `mode`, `location`
and `sessionLabel`, locate the table row containing the matching link and read its sibling cells;
if that fails, fall back to deriving `mode` and `location` from the code suffixes with a lookup
table (`ND` → Normal day, `CC` → Camperdown/Darlington, `RE` → Remote, `BL` → Block mode) and
leave unknown codes as the raw suffix.

### 6.5 `outline.py`

The core parser. Signature: `parse_outline(html: str, meta: dict) -> dict`.

1. Locate the assessment table. Strategy, in order: (a) the element with id `assessment_panel`,
   then the first `<table>` within it; (b) any `<table>` whose header row contains both `Weight`
   and `Due`. If neither works, return zero assessments and flag the unit as a parse failure.
2. Read the header row to build a **column-name → index map**. Do not hardcode column positions —
   match on header text containing `type`, `description`, `weight`, `due`, `length`, `ai`.
3. Iterate body rows. Skip rows where the first cell text starts with `Outcomes assessed`, rows
   with fewer than 4 cells, and the legend row (contains `early feedback task` in lowercase with
   no other content).
4. For each real row, extract fields per §3.4 and §5.3.
5. Extract unit name, session heading and census date from the surrounding document.
6. Return the unit JSON object.

**Write unit tests against `tests/fixtures/outline_amme2200_2026s2.html`** (save a real copy of
that page). Assert: 8 assessments parsed; the final exam has `dateKind == "exam_period"`; the
Week 3 preliminary assessment has `dueDate == "2026-08-17"` and `dueTime == "23:00"`; the
preliminary assessment has `earlyFeedback == true`; `censusDate == "2026-08-31"`; weights sum
to 100.

### 6.6 `calendar_infer.py` — deriving the teaching-week calendar

Many assessments give only "Week 08" with no date. To place these, you need a week→date map.
Rather than hardcoding or scraping the key-dates page, **derive it from the corpus you already
have**, which is self-calibrating and automatically handles the mid-semester break.

Algorithm, per session:

1. Collect every assessment with both a `week` number and an absolute `dueDate`.
2. For each pair, compute the Monday of that due date's ISO week.
3. Group by week number. For each week number, take the **mode** (most common Monday); break ties
   by taking the earliest.
4. You now have observed Mondays for most week numbers. Fill gaps by linear interpolation between
   the nearest known weeks on each side, in 7-day steps; extrapolate at the ends.
5. **Sanity checks** — fail loudly (log ERROR, mark `confidence: "low"`) if: consecutive weeks are
   not 7 or 14 days apart (14 is legitimate exactly once, at the mid-semester break); any week
   number > 13 appears; fewer than 30 samples support the session.
6. Write the result to `weeks.json` with `confidence` and `samples`.

If `data/weeks.override.json` exists, its entries take precedence — this is the manual escape
hatch. Document in the README that the owner should spot-check the inferred Week 1 dates against
`https://www.sydney.edu.au/students/key-dates.html` once per year.

### 6.7 `build.py` — orchestration

```
1. discover all unit codes
2. for each code (bounded concurrency):
     a. fetch landing page → availabilities for TARGET_YEAR
     b. for each availability: fetch outline → parse → unit JSON
3. infer week calendars across all parsed assessments
4. apply weeks.override.json
5. write data/units/*.json, data/index.json, data/weeks.json, data/meta.json
6. print a summary table; exit non-zero on the failure conditions in §6.8
```

CLI flags:

- `--codes AMME2200,ELEC3204` — scrape only these (for development; skips discovery)
- `--year 2026`
- `--limit 50` — stop after N units
- `--no-cache`
- `--out ./data`

A full run touches roughly 6,000 landing pages plus 3,000+ outline pages. At 1 req/s with
concurrency 2 that is ~1.5 hours. That is acceptable for a nightly job and is deliberately
gentle. Do not raise the rate to speed it up.

### 6.8 Failure conditions (exit non-zero, so CI turns red)

- Fewer than 2,000 unit codes discovered
- Fewer than 500 units with a parsed current-year outline
- More than 10% of outline fetches failed
- More than 20% of outline pages parsed to zero assessments
- Any uncaught exception in the orchestrator

A red CI run is the alarm that USyd changed their HTML. It must never fail silently, and it must
never overwrite good data with empty data — **write to a temp directory and only swap into
`data/` after all checks pass.**

---

## 7. Frontend specification

Single page. No routing, no framework, no build. Mobile-first; most students will use this on a
phone.

### 7.1 Layout

```
┌────────────────────────────────────────────┐
│  USyd Assessment Calendar                  │
│  Not official. Always confirm on Canvas.   │
├────────────────────────────────────────────┤
│  [ Semester 2, 2026            ▾ ]         │
│  [ Add a unit… e.g. AMME2200       ]       │
│    ↳ autocomplete dropdown                  │
│                                             │
│  Your units:                                │
│   ⓧ AMME2200 Introductory Thermofluids     │
│   ⓧ ELEC3204 Power Electronics             │
├────────────────────────────────────────────┤
│  [ List ] [ Calendar ]   [⬇ Download .ics] │
├────────────────────────────────────────────┤
│  AUGUST 2026                                │
│   Mon 17  AMME2200  Preliminary Assessment  │
│           2% · 23:00 · Week 3               │
│   Mon 31  AMME2200  Assignment-Fluids       │
│           6% · 23:59 · Week 5               │
│  SEPTEMBER 2026                             │
│   Fri 04  AMME2200  Written test: fluids    │
│           10% · 11:00 · Week 5              │
│  …                                          │
│  ── No fixed date ──                        │
│   AMME2200  Final exam · 50% · Formal exam  │
│             period                          │
└────────────────────────────────────────────┘
```

### 7.2 Behaviour

**Load.** Fetch `data/index.json` and `data/weeks.json` in parallel. Show a skeleton until both
land. If either fetch fails, show an error card with a retry button.

**Session selector.** Populate from the distinct `sessionLabel` values in the index, most recent
first. Default to the session containing today's date if determinable from `weeks.json`, else the
latest. Filtering by session prevents a student seeing S1 and S2 offerings of the same code.

**Unit input.** Case-insensitive substring match on `code` and `name`, filtered to the selected
session, capped at 8 suggestions. Match on code prefix ranks above match on name. `Enter` selects
the top suggestion. Show the unit code in monospace.

Where a code has multiple availabilities in one session (e.g. Normal day vs Remote), show them as
separate suggestions labelled with the `location`.

**Adding a unit.** Fetch that unit's JSON on demand, cache it in a JS `Map`, add a chip, re-render.
Show a per-chip spinner while loading. Cap at 10 units with a friendly message.

**Persistence.** Store selected availability slugs and the session in the URL query string:
`?s=2026-S2C&u=AMME2200-2026-S2C-ND-CC,ELEC3204-2026-S2C-ND-CC`. Read it on load. This makes the
selection shareable and bookmarkable with no storage API. Do **not** use `localStorage`.

**Date resolution for display and export**, per assessment:

| `dateKind` | Treatment |
|---|---|
| `absolute` | Use `dueDate` + `dueTime`. |
| `week_only` | Look up the session's Week N Monday in `weeks.json`, add 4 days → Friday, time `23:59`. Mark as **approximate**. |
| `exam_period` | Do not place on a date. List under "No fixed date". |
| `unparsed` | Do not place on a date. List under "No fixed date" with `dueRaw` shown verbatim. |

Approximate entries must be visually distinct — dashed left border, an "approx." badge, and the
tooltip "Outline gives only a week number; the exact date is on Canvas."

**List view.** Chronological, grouped by month, with a "No fixed date" group at the end. Each row:
date, unit code (colour-coded per unit), assessment name, weight, time, week number. Past items
are dimmed but still shown. A subtle rule marks today's position.

**Calendar view.** A month grid for the session's span with assessment pills in day cells, and
previous/next month navigation. Pills are colour-coded by unit and show `CODE · short name`.
Clicking a pill opens a detail panel with the full description, type, length, AI policy, closing
date, and a link to the source outline page.

**Colour coding.** Assign each selected unit a colour from a fixed 10-colour palette by index, so
colours are stable within a session.

### 7.3 Every view must carry the disclaimer

Persistent, not dismissible, in the header:

> Unofficial. Dates come from published unit outlines and change without notice. **Canvas is the
> source of truth.** Data last updated {meta.generatedAt}.

And in the `.ics` export, prepend to every event's `DESCRIPTION`:
`Unofficial — confirm on Canvas.`

This matters. Someone will eventually miss a deadline and blame the site.

---

## 8. ICS generation (`js/ics.js`)

Produce RFC 5545 output. Requirements:

- `BEGIN:VCALENDAR` / `VERSION:2.0` / `PRODID:-//usyd-assessment-calendar//EN` / `CALSCALE:GREGORIAN`
- `METHOD:PUBLISH`
- `X-WR-CALNAME:USyd Assessments — Semester 2, 2026`
- CRLF (`\r\n`) line endings throughout
- Fold lines longer than 75 octets: break and prefix the continuation with a single space
- Escape `\`, `;`, `,` and newlines in TEXT values (`\\`, `\;`, `\,`, `\n`)
- `UID` = `{assessment.id}@usyd-assessment-calendar` — stable, so re-importing updates rather than
  duplicates
- `DTSTAMP` = now, in UTC (`YYYYMMDDTHHMMSSZ`)

**Timezone.** Emit a `VTIMEZONE` block and reference it with `TZID`, rather than converting to UTC
or using floating time. Include this block verbatim:

```
BEGIN:VTIMEZONE
TZID:Australia/Sydney
BEGIN:STANDARD
DTSTART:19700405T030000
RRULE:FREQ=YEARLY;BYMONTH=4;BYDAY=1SU
TZOFFSETFROM:+1100
TZOFFSETTO:+1000
TZNAME:AEST
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:19701004T020000
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=1SU
TZOFFSETFROM:+1000
TZOFFSETTO:+1100
TZNAME:AEDT
END:DAYLIGHT
END:VTIMEZONE
```

**Per assessment**, emit a timed 30-minute event:

```
BEGIN:VEVENT
UID:AMME2200-2026-S2C-ND-CC-3@usyd-assessment-calendar
DTSTAMP:20260913T170211Z
DTSTART;TZID=Australia/Sydney:20260831T233000
DTEND;TZID=Australia/Sydney:20260831T235900
SUMMARY:AMME2200 — Assignment-Fluids (6%)
DESCRIPTION:Unofficial — confirm on Canvas.\n\nType: Practical skill\nWeight: 6%\nWeek 5\nLength: 12 hours over 4 weeks.\nAI: AI allowed\nClosing date: 13 Nov 2026\n\nhttps://www.sydney.edu.au/units/AMME2200/2026-S2C-ND-CC
BEGIN:VALARM
TRIGGER:-P2D
ACTION:DISPLAY
DESCRIPTION:AMME2200 — Assignment-Fluids due in 2 days
END:VALARM
END:VEVENT
```

Set `DTSTART` 29 minutes before the due time so the event *ends* at the deadline — this reads
correctly in calendar clients.

For `week_only` assessments, emit an **all-day** event on the inferred Friday
(`DTSTART;VALUE=DATE:20260904`, `DTEND;VALUE=DATE:20260905`) and prefix the summary with `[~]`.

For `exam_period` and `unparsed`, emit no event. Instead, after download, show a note listing what
was excluded and why.

Trigger the download with a `Blob` of type `text/calendar;charset=utf-8` and a temporary `<a download>`.
Filename: `usyd-assessments-2026-S2C.ics`.

---

## 9. GitHub Actions workflow

`.github/workflows/scrape.yml`:

```yaml
name: Scrape unit outlines

on:
  schedule:
    - cron: "0 17 * * *"     # 03:00 Sydney (AEST) / 04:00 (AEDT)
  workflow_dispatch:
    inputs:
      year:
        description: "Target year"
        required: false
        default: "2026"

concurrency:
  group: scrape
  cancel-in-progress: false

jobs:
  scrape:
    runs-on: ubuntu-latest
    timeout-minutes: 330
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - run: pip install -r scraper/requirements.txt
      - run: python -m pytest scraper/tests -q
      - run: python -m scraper.build --year "${{ inputs.year || '2026' }}" --out ./data
      - name: Commit data
        run: |
          git config user.name  "scraper-bot"
          git config user.email "actions@github.com"
          git add data/
          git diff --staged --quiet || git commit -m "data: refresh $(date -u +%Y-%m-%d)"
          git push
```

Notes:
- The `pytest` step runs the fixture-based parser tests **before** scraping. If USyd's structure
  changed enough to break the fixtures, that's caught immediately.
- `timeout-minutes: 330` accommodates the deliberately slow crawl.
- The build writes to a temp dir and only swaps into `data/` after §6.8 checks pass, so a failed
  run leaves the previous good data in place.

---

## 10. Deployment

### Primary: GitHub Pages

1. Repo → Settings → Pages → Source: "Deploy from a branch", branch `main`, folder `/ (root)`.
2. Site is live at `https://<owner>.github.io/<repo>/`.
3. Because the site and the data live in the same repo, `fetch('./data/index.json')` just works —
   no CORS, no config.

Add an empty `.nojekyll` file at the root so Jekyll doesn't interfere.

### Alternative: Cloudflare Pages

Connect the GitHub repo, build command: *(none)*, output directory: `/`. Gives a free custom
domain and faster global CDN. Document both in the README; recommend starting with Pages.

---

## 11. Conduct and legal

Implement all of these — they are not optional:

- Descriptive `User-Agent` with a contact URL (see §6.1).
- Minimum 1 second between requests; concurrency ≤ 2.
- Fetch at most once per day per page; use the on-disk cache.
- Fetch `https://www.sydney.edu.au/robots.txt` at the start of every run, parse it with
  `urllib.robotparser`, and skip any disallowed path. Log what was skipped.
- The outline pages carry `<meta name="robots" content="noindex">`. That governs search indexing,
  not access, but it reinforces the point: do not republish outlines wholesale. Store and display
  only assessment metadata, not the full unit content (no learning outcomes, no weekly schedule,
  no coordinator email addresses — **do not scrape or store staff email addresses at all**).
- README must state the project is unofficial, not affiliated with or endorsed by the University
  of Sydney, and link to each unit's original outline page.
- Every displayed assessment links back to its `sourceUrl`.

---

## 12. Build order and acceptance criteria

Build in this sequence. Each milestone must pass before moving on.

**M1 — Parse one outline.**
`python -m scraper.outline --url https://www.sydney.edu.au/units/AMME2200/2026-S2C-ND-CC`
prints valid JSON with 8 assessments. Fixture tests from §6.5 pass.

**M2 — Resolve availabilities.** Given `AMME2200`, return exactly one 2026 availability:
`2026-S2C-ND-CC`.

**M3 — Discovery.** `seo.html` + pagination yields > 2,000 unique codes, all matching
`^[A-Z]{4}\d{4}$`.

**M4 — Small end-to-end run.**
`python -m scraper.build --codes AMME2200,ELEC3204,COMP3308,MTRX2700 --year 2026`
produces a complete, schema-valid `data/` tree.

**M5 — Week inference.** Run over ≥ 300 units; `weeks.json` has Mondays for weeks 1–13 with
exactly one 14-day gap (the mid-semester break) and `confidence: "inferred"`.

**M6 — Frontend, list view.** Opening `index.html` from a local static server
(`python -m http.server`) lets you add those four units and see a correct merged chronological
list. URL query string round-trips.

**M7 — ICS export.** Downloaded file imports cleanly into Google Calendar *and* Apple Calendar
with correct Sydney local times. Re-importing updates rather than duplicating. Validate against
an RFC 5545 validator before declaring done.

**M8 — Calendar view, polish, mobile.** Renders correctly at 375px wide. Colour coding stable.
Detail panel works.

**M9 — CI + deploy.** `workflow_dispatch` run completes green with `--limit 200`; data is
committed; the Pages site serves the committed data.

**M10 — Full run.** Unthrottled-by-nothing full crawl completes within the timeout and meets
every §6.8 threshold.

---

## 13. Explicitly out of scope

Do not build any of these:

- User accounts, login, or any authentication
- Canvas integration or the Canvas API
- Timetable/class-schedule data (lectures, tutorials) — assessments only
- A hosted subscribable ICS feed URL (download only; a feed would need per-user state)
- Push/email notifications
- Any server, serverless function, or database
- Historical-year browsing
- Grade tracking or weighted-mark calculators

---

## 14. README content

Write a README covering: what it is, the unofficial disclaimer, a screenshot placeholder, how to
run the scraper locally, how to run the site locally, how the data pipeline works, how to add the
next year (change `TARGET_YEAR`, verify `weeks.json`), what to do when USyd changes their HTML
(the parser tests will fail first — update the fixture, fix `outline.py`, rerun), and the MIT
licence.

---

## 15. Reference: verified sample of the source data

Reproduced from the live AMME2200 S2 2026 outline for parser calibration. Your parser must handle
every row here, including the exam row with no date and the icon-bearing early-feedback row.

| Type | Name | Weight | Due (raw) |
|---|---|---|---|
| Written exam | Final exam | 50% | `Formal exam period` |
| Practical skill *(early feedback icon)* | Preliminary Assessment | 2% | `Week 03 Due date: 17 Aug 2026 at 23:00 Closing date: 06 Nov 2026` |
| In-person written or creative task | Written test: fluid mechanics | 10% | `Week 05 Due date: 04 Sep 2026 at 11:00 Closing date: 04 Sep 2026` |
| Practical skill | Assignment-Fluids | 6% | `Week 05 Due date: 31 Aug 2026 at 23:59 Closing date: 13 Nov 2026` |
| In-person written or creative task | Written test: heat transfer | 10% | `Week 09 Due date: 09 Oct 2026 at 11:00 Closing date: 09 Oct 2026` |
| Practical skill | Assignment-Heat Transfer | 6% | `Week 09 Due date: 28 Sep 2026 at 23:59 Closing date: 13 Nov 2026` |
| In-person written or creative task | Written test: thermodynamics | 10% | `Week 13 Due date: 06 Nov 2026 at 11:00 Closing date: 06 Nov 2026` |
| Practical skill | Assignment-Theromdynamics | 6% | `Week 13 Due date: 02 Nov 2026 at 23:59 Closing date: 13 Nov 2026` |

Census date on that page: `31 August 2026`. Note the typo in the last assessment name — it is
real, and your parser must not "correct" it. Store source text verbatim.

---

*End of specification. Build it.*
