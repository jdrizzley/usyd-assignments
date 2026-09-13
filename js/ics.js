// RFC 5545 calendar export, hand-rolled. BUILD-SPEC §8.

const VTIMEZONE = [
  'BEGIN:VTIMEZONE',
  'TZID:Australia/Sydney',
  'BEGIN:STANDARD',
  'DTSTART:19700405T030000',
  'RRULE:FREQ=YEARLY;BYMONTH=4;BYDAY=1SU',
  'TZOFFSETFROM:+1100',
  'TZOFFSETTO:+1000',
  'TZNAME:AEST',
  'END:STANDARD',
  'BEGIN:DAYLIGHT',
  'DTSTART:19701004T020000',
  'RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=1SU',
  'TZOFFSETFROM:+1000',
  'TZOFFSETTO:+1100',
  'TZNAME:AEDT',
  'END:DAYLIGHT',
  'END:VTIMEZONE',
];

const enc = new TextEncoder();

export function escapeText(s) {
  return String(s ?? '')
    .replace(/\\/g, '\\\\')
    .replace(/;/g, '\\;')
    .replace(/,/g, '\\,')
    .replace(/\r?\n/g, '\\n');
}

// Fold a content line so no physical line exceeds 75 octets; continuation lines
// start with a single space. Never splits a UTF-8 code point.
export function foldLine(line) {
  const out = [];
  let cur = '';
  let curBytes = 0;
  let limit = 75;
  for (const ch of line) {
    const b = enc.encode(ch).length;
    if (curBytes + b > limit) {
      out.push(cur);
      cur = ' ' + ch;
      curBytes = 1 + b;
      limit = 75;
    } else {
      cur += ch;
      curBytes += b;
    }
  }
  out.push(cur);
  return out;
}

function pad(n) { return String(n).padStart(2, '0'); }

export function dtstampUTC(now = new Date()) {
  return `${now.getUTCFullYear()}${pad(now.getUTCMonth() + 1)}${pad(now.getUTCDate())}T${pad(now.getUTCHours())}${pad(now.getUTCMinutes())}${pad(now.getUTCSeconds())}Z`;
}

function compact(iso) { return iso.replace(/-/g, ''); }

// Wall-clock arithmetic on "YYYY-MM-DD" + "HH:MM" without touching the browser's zone.
function shiftMinutes(iso, hhmm, delta) {
  const [h, m] = hhmm.split(':').map(Number);
  let total = h * 60 + m + delta;
  let dayShift = 0;
  while (total < 0) { total += 1440; dayShift -= 1; }
  while (total >= 1440) { total -= 1440; dayShift += 1; }
  const [y, mo, d] = iso.split('-').map(Number);
  const date = new Date(Date.UTC(y, mo - 1, d + dayShift));
  const isoOut = `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}`;
  return { iso: isoOut, hhmm: `${pad(Math.floor(total / 60))}:${pad(total % 60)}` };
}

function localStamp(iso, hhmm) {
  return `${compact(iso)}T${hhmm.replace(':', '')}00`;
}

function fmtLong(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' });
}

/**
 * items: [{ unit, a, res }] where res = resolveDate(...)
 * Returns { text, exported, excluded: [{unit, a, reason}] }
 */
export function buildICS(items, sessionLabel, now = new Date()) {
  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//usyd-assessment-calendar//EN',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
    `X-WR-CALNAME:${escapeText(`USyd Assessments — ${sessionLabel}`)}`,
    'X-WR-TIMEZONE:Australia/Sydney',
    ...VTIMEZONE,
  ];
  const stamp = dtstampUTC(now);
  const excluded = [];
  let exported = 0;

  for (const { unit, a, res } of items) {
    if (res.kind === 'none') {
      excluded.push({ unit, a, reason: a.dateKind === 'exam_period' ? 'Formal exam period' : (a.dueRaw || 'No date in the outline') });
      continue;
    }
    const weight = a.weightRaw || (a.weight != null ? `${a.weight}%` : '');
    const desc = [
      'Unofficial — confirm on Canvas.',
      '',
      ...(res.kind === 'approx' ? ['Approximate date: the outline gives only a week number. The exact date is on Canvas.', ''] : []),
      `Type: ${a.type || '—'}`,
      `Weight: ${weight || '—'}`,
      ...(a.week != null ? [`Week ${a.week}`] : []),
      ...(a.length ? [`Length: ${a.length}`] : []),
      ...(a.aiPolicy ? [`AI: ${a.aiPolicy}`] : []),
      ...(a.closingDate ? [`Closing date: ${fmtLong(a.closingDate)}`] : []),
      ...(a.description ? ['', a.description] : []),
      '',
      unit.sourceUrl,
    ].join('\n');

    lines.push('BEGIN:VEVENT');
    lines.push(`UID:${a.id}@usyd-assessment-calendar`);
    lines.push(`DTSTAMP:${stamp}`);
    if (res.kind === 'fixed') {
      const start = shiftMinutes(res.iso, res.time, -29);
      lines.push(`DTSTART;TZID=Australia/Sydney:${localStamp(start.iso, start.hhmm)}`);
      lines.push(`DTEND;TZID=Australia/Sydney:${localStamp(res.iso, res.time)}`);
      lines.push(`SUMMARY:${escapeText(`${unit.code} — ${a.name}${weight ? ` (${weight})` : ''}`)}`);
    } else {
      const next = shiftMinutes(res.iso, '00:00', 1440);
      lines.push(`DTSTART;VALUE=DATE:${compact(res.iso)}`);
      lines.push(`DTEND;VALUE=DATE:${compact(next.iso)}`);
      lines.push(`SUMMARY:${escapeText(`[~] ${unit.code} — ${a.name}${weight ? ` (${weight})` : ''}`)}`);
    }
    lines.push(`DESCRIPTION:${escapeText(desc)}`);
    lines.push(`URL:${unit.sourceUrl}`);
    lines.push('BEGIN:VALARM');
    lines.push('TRIGGER:-P2D');
    lines.push('ACTION:DISPLAY');
    lines.push(`DESCRIPTION:${escapeText(`${unit.code} — ${a.name} due in 2 days`)}`);
    lines.push('END:VALARM');
    lines.push('END:VEVENT');
    exported += 1;
  }
  lines.push('END:VCALENDAR');

  const text = lines.flatMap(foldLine).join('\r\n') + '\r\n';
  return { text, exported, excluded };
}

export function downloadICS(text, filename) {
  const blob = new Blob([text], { type: 'text/calendar;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
