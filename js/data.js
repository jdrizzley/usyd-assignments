// Data access: loads the pre-scraped JSON, resolves sessions and dates, searches the index.

export const state = {
  index: [],
  weeks: {},
  meta: null,
  units: new Map(),       // availability slug -> unit JSON (or in-flight Promise)
  selected: [],           // ordered availability slugs
  slots: new Map(),       // slug -> colour slot 0..9, stable while selected
  sessionKey: null,
  view: 'list',
};

export const MAX_UNITS = 10;
export const SESSION_LENGTH_WEEKS = 13;
export const EXAM_TAIL_DAYS = 28;   // week 13 Monday + STUVAC + two exam weeks

async function getJSON(url) {
  const res = await fetch(url, { cache: 'no-cache' });
  if (!res.ok) throw new Error(`${url} returned ${res.status}`);
  return res.json();
}

export async function loadCore() {
  const [index, weeks, meta] = await Promise.all([
    getJSON('./data/index.json'),
    getJSON('./data/weeks.json'),
    getJSON('./data/meta.json').catch(() => null),
  ]);
  state.index = index;
  state.weeks = weeks;
  state.meta = meta;
  return { index, weeks, meta };
}

export function loadUnit(entry) {
  const slug = entry.availability;
  const key = `${entry.code}-${slug}`;
  if (state.units.has(key)) return Promise.resolve(state.units.get(key));
  const p = getJSON('./' + entry.file).then((unit) => {
    state.units.set(key, unit);
    return unit;
  });
  p.catch(() => state.units.delete(key));
  state.units.set(key, p);
  return p;
}

export function unitKey(entry) { return `${entry.code}-${entry.availability}`; }
export function entryByKey(key) { return state.index.find((e) => unitKey(e) === key) || null; }

// ---- dates ------------------------------------------------------------------
export function parseISO(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d);
}
export function toISO(date) {
  const p = (n) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${p(date.getMonth() + 1)}-${p(date.getDate())}`;
}
export function addDays(date, n) {
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  d.setDate(d.getDate() + n);
  return d;
}
export function today() {
  const t = new Date();
  return new Date(t.getFullYear(), t.getMonth(), t.getDate());
}

// ---- sessions ---------------------------------------------------------------
export function sessionKeyOf(entry) {
  return `${entry.availability.slice(0, 4)}-${entry.session}`;
}

export function sessionSpan(key) {
  const w = state.weeks[key];
  // A low-confidence map (too few samples, or inconsistent gaps) is worse than none.
  if (!w || !w['1'] || w.confidence === 'low') return null;
  const start = parseISO(w['1']);
  const lastWeek = w[String(SESSION_LENGTH_WEEKS)] || w[String(Object.keys(w).filter((k) => /^\d+$/.test(k)).map(Number).sort((a, b) => b - a)[0])];
  const end = addDays(parseISO(lastWeek), EXAM_TAIL_DAYS);
  return { start, end, weeks: w, confidence: w.confidence };
}

export function sessions() {
  const seen = new Map();
  for (const e of state.index) {
    const key = sessionKeyOf(e);
    if (!seen.has(key)) seen.set(key, { key, label: e.sessionLabel, code: e.session, year: Number(e.availability.slice(0, 4)), count: 0 });
    seen.get(key).count += 1;
  }
  const list = [...seen.values()];
  for (const s of list) s.span = sessionSpan(s.key);
  // Most recent first: by start date when known, else by year then session code.
  list.sort((a, b) => {
    const as = a.span ? a.span.start.getTime() : a.year * 1e13;
    const bs = b.span ? b.span.start.getTime() : b.year * 1e13;
    if (as !== bs) return bs - as;
    return b.code.localeCompare(a.code);
  });
  return list;
}

export function defaultSession(list) {
  const now = today();
  const current = list.find((s) => s.span && now >= s.span.start && now <= s.span.end);
  return (current || list[0] || null)?.key ?? null;
}

// ---- search -----------------------------------------------------------------
export function search(query, sessionKey, limit = 8) {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const pool = state.index.filter((e) => sessionKeyOf(e) === sessionKey && !state.selected.includes(unitKey(e)));
  const scored = [];
  for (const e of pool) {
    const code = e.code.toLowerCase();
    const name = (e.name || '').toLowerCase();
    let rank = null;
    if (code.startsWith(q)) rank = 0;
    else if (code.includes(q)) rank = 1;
    else if (name.includes(q)) rank = 2;
    if (rank !== null) scored.push({ e, rank });
  }
  scored.sort((a, b) => a.rank - b.rank || a.e.code.localeCompare(b.e.code) || a.e.availability.localeCompare(b.e.availability));
  const out = scored.slice(0, limit).map((s) => s.e);
  const codeCounts = new Map();
  for (const e of pool) codeCounts.set(e.code, (codeCounts.get(e.code) || 0) + 1);
  return out.map((e) => ({ entry: e, ambiguous: (codeCounts.get(e.code) || 0) > 1 }));
}

// ---- date resolution --------------------------------------------------------
// Returns { kind: 'fixed' | 'approx' | 'none', date: Date|null, iso, time }
export function resolveDate(a, sessionKey) {
  if (a.dateKind === 'absolute' && a.dueDate) {
    return { kind: 'fixed', date: parseISO(a.dueDate), iso: a.dueDate, time: a.dueTime || '23:59' };
  }
  if (a.dateKind === 'week_only' && a.week != null) {
    const w = state.weeks[sessionKey];
    const monday = w && w.confidence !== 'low' && w[String(a.week)];
    if (monday) {
      const friday = addDays(parseISO(monday), 4);
      return { kind: 'approx', date: friday, iso: toISO(friday), time: '23:59' };
    }
  }
  return { kind: 'none', date: null, iso: null, time: null };
}

// ---- colour slots -----------------------------------------------------------
export const SHAPES = ['square', 'circle', 'diamond', 'triangle', 'bar'];
export function slotStyle(slot) {
  const colour = (slot % 5) + 1;
  const shape = SHAPES[slot % 5];
  const hollow = slot >= 5;
  return { colourVar: `var(--u${colour})`, shape, hollow };
}
export function assignSlot(key) {
  if (state.slots.has(key)) return state.slots.get(key);
  const used = new Set(state.slots.values());
  let slot = 0;
  while (used.has(slot)) slot += 1;
  state.slots.set(key, slot);
  return slot;
}

// ---- URL state --------------------------------------------------------------
export function readURL() {
  const p = new URLSearchParams(location.search);
  const s = p.get('s');
  const u = (p.get('u') || '').split(',').map((x) => x.trim()).filter(Boolean);
  return { session: s, units: u };
}
export function writeURL() {
  const p = new URLSearchParams();
  if (state.sessionKey) p.set('s', state.sessionKey);
  if (state.selected.length) p.set('u', state.selected.join(','));
  if (state.view !== 'list') p.set('v', state.view);
  const qs = p.toString();
  history.replaceState(null, '', qs ? `?${qs}` : location.pathname);
}
