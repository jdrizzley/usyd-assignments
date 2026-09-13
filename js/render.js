// Rendering: list view, calendar view, term ruler, detail panel, and the four required states.
import {
  state, resolveDate, sessionSpan, sessionKeyOf, today, toISO, addDays, parseISO, slotStyle, unitKey,
  setUserDate, clearUserDate,
} from './data.js';

const $ = (id) => document.getElementById(id);

export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'style' && typeof v === 'object') {
      for (const [prop, val] of Object.entries(v)) {
        if (prop.startsWith('--')) el.style.setProperty(prop, val); else el.style[prop] = val;
      }
    }
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
    else if (k === 'text') el.textContent = v;
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const c of children.flat()) {
    if (c == null || c === false) continue;
    el.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return el;
}

export function swatch(slot, extraClass = '') {
  const s = slotStyle(slot);
  return h('span', {
    class: `swatch swatch--${s.shape}${s.hollow ? ' swatch--hollow' : ''} ${extraClass}`.trim(),
    style: { '--u': s.colourVar },
    'aria-hidden': 'true',
  });
}

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const WD = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const wd = (d) => WD[(d.getDay() + 6) % 7];
const p2 = (n) => String(n).padStart(2, '0');

export function fmtDate(d) { return `${wd(d)} ${d.getDate()} ${MONTHS[d.getMonth()].slice(0, 3)} ${d.getFullYear()}`; }
export function fmtLong(iso) { const d = parseISO(iso); return `${d.getDate()} ${MONTHS[d.getMonth()].slice(0, 3)} ${d.getFullYear()}`; }

function weightText(a) { return a.weightRaw || (a.weight != null ? `${a.weight}%` : ''); }

// ---- item collection --------------------------------------------------------
export function collectItems() {
  const items = [];
  for (const key of state.selected) {
    const unit = state.units.get(key);
    if (!unit || typeof unit.then === 'function') continue;
    const slot = state.slots.get(key) ?? 0;
    const sKey = state.sessionKey;
    for (const a of unit.assessments) {
      items.push({ key, unit, a, slot, res: resolveDate(a, sKey) });
    }
  }
  const dated = items.filter((i) => i.res.kind !== 'none');
  const undated = items.filter((i) => i.res.kind === 'none');
  dated.sort((x, y) => (x.res.date - y.res.date) || x.res.time.localeCompare(y.res.time) || x.unit.code.localeCompare(y.unit.code));
  undated.sort((x, y) => x.unit.code.localeCompare(y.unit.code) || (y.a.weight ?? 0) - (x.a.weight ?? 0));
  return { items, dated, undated };
}

function isoWeekKey(d) {
  const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const day = t.getUTCDay() || 7;
  t.setUTCDate(t.getUTCDate() + 4 - day);
  const y = t.getUTCFullYear();
  const w = Math.ceil(((t - Date.UTC(y, 0, 1)) / 86400e3 + 1) / 7);
  return `${y}-${w}`;
}

// ---- rows -------------------------------------------------------------------
function metaText(item) {
  const { a, res } = item;
  const parts = [];
  const w = weightText(a);
  if (w) parts.push(w);
  if (res.kind === 'fixed' || res.kind === 'user') parts.push(res.time);
  if (a.week != null) parts.push(`Week ${a.week}`);
  return parts.join(' · ');
}

// ---- user-added dates -------------------------------------------------------
const YOUR_DATE_TIP = 'Date added by you. It is not in the unit outline and is kept in this browser only.';

function datesChanged() { document.dispatchEvent(new CustomEvent('dates:change')); }

/** Inline form to add or change the user's date for one assessment. */
export function dateEditor(item, { onDone } = {}) {
  const { a, unit } = item;
  const existing = state.userDates.get(a.id);
  const span = sessionSpan(state.sessionKey);
  const dateIn = h('input', { class: 'input input--small', type: 'date', required: true, 'aria-label': 'Due date', value: existing?.date || '' });
  if (span?.start) dateIn.min = toISO(addDays(span.start, -60));
  if (span?.end) dateIn.max = toISO(addDays(span.end, 120));
  const timeIn = h('input', { class: 'input input--small', type: 'time', 'aria-label': 'Due time', value: existing?.time || '23:59' });
  const err = h('span', { class: 'date-editor__err t-small', role: 'alert' });
  const save = h('button', { type: 'submit', class: 'btn btn--primary btn--small' }, 'Save');
  const cancel = h('button', { type: 'button', class: 'btn btn--small' }, 'Cancel');
  const form = h('form', { class: 'date-editor', 'aria-label': `Add a due date for ${unit.code} ${a.name}` },
    h('div', { class: 'date-editor__fields' }, dateIn, timeIn, save, cancel),
    h('span', { class: 'date-editor__note t-small' }, 'Not from the outline. Saved in this browser only.'),
    err);
  cancel.addEventListener('click', () => onDone?.(false));
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    if (!dateIn.value || Number.isNaN(parseISO(dateIn.value).getTime())) { err.textContent = 'Enter a date.'; dateIn.focus(); return; }
    setUserDate(a.id, dateIn.value, timeIn.value || '23:59');
    onDone?.(true);
    datesChanged();
  });
  form.focusFirst = () => dateIn.focus();
  return form;
}

function removeUserDate(item) {
  clearUserDate(item.a.id);
  datesChanged();
}

export function rowEl(item, { undated = false, now = today() } = {}) {
  const { a, unit, res, slot } = item;
  const past = res.date && res.date < now;
  const s = slotStyle(slot);
  const li = h('li', {
    class: `row${res.kind === 'approx' ? ' row--approx' : ''}${res.kind === 'user' ? ' row--user' : ''}${past ? ' row--past' : ''}`,
    id: `row-${a.id}`,
    style: { '--u': s.colourVar },
    'data-id': a.id,
  });
  const dateCol = res.date
    ? h('span', { class: 'row__date' },
        h('span', { class: 'row__date-wd t-small' }, wd(res.date)),
        h('span', { class: 'row__date-day num' }, p2(res.date.getDate())))
    : null;
  const nameLine = h('span', { class: 'row__top' },
    h('span', { class: 'row__code t-label' }, swatch(slot), unit.code),
    h('span', { class: 'row__name' }, a.name || a.type || 'Assessment'),
    res.kind === 'approx' ? h('span', { class: 'badge badge--approx', title: 'The outline gives only a week number. The exact date is on Canvas.' }, 'approx.') : null,
    res.kind === 'user' ? h('span', { class: 'badge badge--user', title: YOUR_DATE_TIP }, 'your date') : null,
    a.earlyFeedback ? h('span', { class: 'badge badge--early', title: 'Early feedback task' }, 'early') : null,
  );
  const meta = undated
    ? h('span', { class: 'row__meta t-small num' }, [weightText(a), a.dateKind === 'exam_period' ? 'Formal exam period' : (a.dueRaw || 'No date given')].filter(Boolean).join(' · '))
    : h('span', { class: 'row__meta t-small num' }, metaText(item));
  const btn = h('button', { type: 'button', class: 'row__main', 'aria-label': `${unit.code} ${a.name}, details` },
    dateCol,
    h('span', { class: 'row__body' }, nameLine, meta));
  btn.addEventListener('click', () => openDetail(item));
  li.append(btn);
  if (undated) {
    const addBtn = h('button', { type: 'button', class: 'btn btn--small row__add', 'aria-label': `Add a due date for ${unit.code} ${a.name}` }, 'Add date');
    addBtn.addEventListener('click', () => {
      if (li.querySelector('.date-editor')) return;
      addBtn.hidden = true;
      const editor = dateEditor(item, { onDone: () => { editor.remove(); addBtn.hidden = false; addBtn.focus(); } });
      editor.classList.add('row__editor');
      li.append(editor);
      editor.focusFirst();
    });
    li.append(addBtn);
  }
  li.append(h('a', { class: 'row__src', href: unit.sourceUrl, target: '_blank', rel: 'noopener', 'aria-label': `Outline for ${unit.code}, opens in a new tab` }, '↗'));
  return li;
}

// ---- list view --------------------------------------------------------------
export function renderList(root) {
  const { items, dated, undated } = collectItems();
  root.replaceChildren();
  if (!items.length) return false;
  const now = today();
  const list = h('div', { class: 'list' });

  let todayPlaced = false;
  if (dated.length) {
    const groups = new Map();
    for (const it of dated) {
      const k = `${it.res.date.getFullYear()}-${it.res.date.getMonth()}`;
      if (!groups.has(k)) groups.set(k, []);
      groups.get(k).push(it);
    }
    for (const [, group] of groups) {
      const first = group[0].res.date;
      const section = h('section', { class: 'month', 'aria-label': `${MONTHS[first.getMonth()]} ${first.getFullYear()}` },
        h('h2', { class: 'month__label t-h2' }, MONTHS[first.getMonth()], ' ', h('span', { class: 'num' }, String(first.getFullYear()))));
      const ul = h('ul', { class: 'month__rows' });
      let prevWeek = null;
      for (const it of group) {
        if (!todayPlaced && it.res.date >= now && dated[0].res.date < now) {
          ul.append(todayRule());
          todayPlaced = true;
        }
        const li = rowEl(it, { now });
        const wk = isoWeekKey(it.res.date);
        if (prevWeek && wk !== prevWeek) li.classList.add('row--newweek');
        prevWeek = wk;
        ul.append(li);
      }
      section.append(ul);
      list.append(section);
    }
    if (!todayPlaced && dated[dated.length - 1].res.date < now) {
      list.lastChild.querySelector('ul').append(todayRule('All dated assessments have passed'));
    }
  }
  if (undated.length) {
    const sec = h('section', { class: 'nodate', 'aria-label': 'No fixed date' },
      h('h2', { class: 'nodate__label t-label' }, 'No fixed date'),
      h('ul', {}, undated.map((it) => rowEl(it, { undated: true }))));
    list.append(sec);
  }
  root.append(list);
  return true;
}

function todayRule(label = 'Today') {
  return h('li', { class: 'today-rule', role: 'separator', 'aria-label': label },
    h('span', { class: 'today-rule__label' }, label));
}

// ---- calendar view ----------------------------------------------------------
let calMonth = null; // Date at first of month

export function renderCalendar(root) {
  const { items, dated } = collectItems();
  root.replaceChildren();
  const span = sessionSpan(state.sessionKey);
  const now = today();
  let lo, hi;
  if (span) { lo = span.start; hi = span.end; }
  else if (dated.length) { lo = addDays(dated[0].res.date, -14); hi = addDays(dated[dated.length - 1].res.date, 14); }
  else { lo = addDays(now, -45); hi = addDays(now, 90); }
  const first = (d) => new Date(d.getFullYear(), d.getMonth(), 1);
  const minM = first(lo), maxM = first(hi);
  if (!calMonth || calMonth < minM || calMonth > maxM) {
    calMonth = (now >= minM && now <= hi) ? first(now) : minM;
  }

  const byDay = new Map();
  for (const it of dated) {
    const k = it.res.iso;
    if (!byDay.has(k)) byDay.set(k, []);
    byDay.get(k).push(it);
  }

  const title = h('h2', { class: 'cal__title t-h2', id: 'cal-title', 'aria-live': 'polite' }, `${MONTHS[calMonth.getMonth()]} ${calMonth.getFullYear()}`);
  const prev = h('button', { type: 'button', class: 'btn btn--small', 'aria-label': 'Previous month' }, '← Prev');
  const next = h('button', { type: 'button', class: 'btn btn--small', 'aria-label': 'Next month' }, 'Next →');
  prev.disabled = calMonth <= minM;
  next.disabled = calMonth >= maxM;
  prev.addEventListener('click', () => { calMonth = new Date(calMonth.getFullYear(), calMonth.getMonth() - 1, 1); renderCalendar(root); });
  next.addEventListener('click', () => { calMonth = new Date(calMonth.getFullYear(), calMonth.getMonth() + 1, 1); renderCalendar(root); });

  const grid = h('div', { class: 'cal__grid', role: 'grid', 'aria-labelledby': 'cal-title' });
  grid.append(h('div', { class: 'cal__row', role: 'row' }, WD.map((d) => h('div', { class: 'cal__hd', role: 'columnheader' }, d))));

  const startOffset = (calMonth.getDay() + 6) % 7;
  let cursor = addDays(calMonth, -startOffset);
  const monthIdx = calMonth.getMonth();
  do {
    const row = h('div', { class: 'cal__row', role: 'row' });
    for (let i = 0; i < 7; i += 1) {
      const iso = toISO(cursor);
      const out = cursor.getMonth() !== monthIdx;
      const isToday = cursor.getTime() === now.getTime();
      const cell = h('div', {
        class: `cal__cell${out ? ' cal__cell--out' : ''}${isToday ? ' cal__cell--today' : ''}${cursor < now ? ' cal__cell--past' : ''}`,
        role: 'gridcell', 'aria-label': fmtDate(cursor),
      });
      cell.append(h('div', { class: 'cal__day' }, h('span', {}, String(cursor.getDate())), isToday ? h('span', { class: 'cal__today-dot', title: 'Today' }) : null));
      for (const it of byDay.get(iso) || []) {
        const s = slotStyle(it.slot);
        const shortName = it.a.name.length > 28 ? it.a.name.slice(0, 26).trimEnd() + '…' : it.a.name;
        const pill = h('button', {
          type: 'button', class: `pill${it.res.kind === 'approx' ? ' pill--approx' : ''}`,
          style: { '--u': s.colourVar },
          title: `${it.unit.code} · ${it.a.name} · ${weightText(it.a)}${it.res.kind === 'approx' ? ' · approx.' : ''}${it.res.kind === 'user' ? ' · your date' : ''}`,
          'aria-label': `${it.unit.code} ${it.a.name}, ${weightText(it.a)}${it.res.kind === 'approx' ? ', approximate date' : ''}${it.res.kind === 'user' ? ', date added by you' : ''}`,
        },
          swatch(it.slot),
          h('span', { class: 'pill__code t-label' }, it.unit.code),
          h('span', { class: 'pill__name' }, '· ', shortName),
          h('span', { class: 'pill__mini' }, it.unit.code.slice(0, 4)));
        pill.addEventListener('click', () => openDetail(it));
        cell.append(pill);
      }
      row.append(cell);
      cursor = addDays(cursor, 1);
    }
    grid.append(row);
  } while (cursor.getMonth() === monthIdx);

  root.append(h('div', { class: 'cal' },
    h('div', { class: 'cal__nav' }, title, h('div', { class: 'cal__btns' }, prev, next)),
    grid,
    items.length ? null : h('p', { class: 't-small', style: { color: 'var(--ink-500)' } }, 'Add a unit to see its assessments on the grid.')));
}

// ---- term ruler -------------------------------------------------------------
export function renderRuler() {
  const track = $('ruler-track');
  const tip = $('ruler-tip');
  const ruler = $('ruler');
  track.replaceChildren(h('div', { class: 'ruler__baseline' }));
  tip.hidden = true;
  ruler.classList.remove('is-hovering');

  const { dated } = collectItems();
  const span = sessionSpan(state.sessionKey);
  const now = today();
  let lo, hi;
  if (span) { lo = span.start; hi = span.end; }
  else if (dated.length) { lo = addDays(dated[0].res.date, -7); hi = addDays(dated[dated.length - 1].res.date, 7); }
  else { lo = addDays(now, -60); hi = addDays(now, 90); }
  const total = Math.max(1, hi - lo);
  const pct = (d) => `${Math.min(100, Math.max(0, ((d - lo) / total) * 100))}%`;

  if (span) {
    const w = span.weeks;
    const nums = Object.keys(w).filter((k) => /^\d+$/.test(k)).map(Number).sort((a, b) => a - b);
    for (const n of nums) {
      const monday = parseISO(w[String(n)]);
      track.append(h('div', { class: 'ruler__wk', style: { left: pct(monday) }, 'aria-hidden': 'true' }));
      const cls = ['ruler__wk-label'];
      if (n % 3 === 1) cls.push('ruler__wk-label--third');
      if (n === 1 || n === 7 || n === 13) cls.push('ruler__wk-label--key');
      track.append(h('span', { class: cls.join(' '), style: { left: pct(addDays(monday, 3.5)) }, 'aria-hidden': 'true' }, p2(n)));
      const nextMonday = w[String(n + 1)] ? parseISO(w[String(n + 1)]) : null;
      if (nextMonday && Math.round((nextMonday - monday) / 86400e3) >= 14) {
        const bStart = addDays(monday, 7);
        track.append(h('div', { class: 'ruler__break', style: { left: pct(bStart), width: `calc(${pct(nextMonday)} - ${pct(bStart)})` }, title: 'Mid-semester break' }));
      }
    }
    const last = parseISO(w[String(nums[nums.length - 1])]);
    const examStart = addDays(last, 7);
    track.append(h('div', { class: 'ruler__exams', style: { left: pct(examStart), width: `calc(100% - ${pct(examStart)})` }, 'aria-hidden': 'true' }));
    track.append(h('span', { class: 'ruler__exam-label', style: { left: pct(addDays(examStart, 2)) }, 'aria-hidden': 'true' }, 'STUVAC · exams'));
  }

  // Assessment ticks; coincident ones stack side by side.
  const byDay = new Map();
  for (const it of dated) {
    if (!byDay.has(it.res.iso)) byDay.set(it.res.iso, []);
    byDay.get(it.res.iso).push(it);
  }
  for (const [, group] of byDay) {
    group.forEach((it, i) => {
      const wgt = it.a.weight ?? 2;
      const height = Math.round(Math.max(4, Math.min(48, 4 + (wgt - 2) * (40 / 48))));
      const s = slotStyle(it.slot);
      const tick = h('button', {
        type: 'button',
        class: `ruler__tick${it.res.kind === 'approx' ? ' ruler__tick--approx' : ''}`,
        style: { left: `calc(${pct(it.res.date)} + ${i * 3}px)`, height: `${height}px`, '--h': `${height}px`, '--u': s.colourVar },
        'aria-label': `${it.unit.code} ${it.a.name}, ${weightText(it.a)}, ${fmtDate(it.res.date)}`,
      });
      const show = () => {
        tip.replaceChildren(
          h('span', { class: 'ruler__tip-code t-label' }, it.unit.code),
          h('span', {}, it.a.name),
          h('br'),
          h('span', { class: 'ruler__tip-meta num' }, [weightText(it.a), fmtDate(it.res.date), it.res.kind === 'approx' ? 'approx.' : null, it.res.kind === 'user' ? 'your date' : null].filter(Boolean).join(' · ')));
        tip.hidden = false;
        const rect = tick.getBoundingClientRect();
        const rr = ruler.getBoundingClientRect();
        let x = rect.left - rr.left + 6;
        tip.style.left = '0px';
        tip.style.bottom = `${rr.bottom - rect.top + 4}px`;
        const tw = tip.offsetWidth;
        if (x + tw > rr.width - 8) x = Math.max(8, rect.left - rr.left - tw - 6);
        tip.style.left = `${x}px`;
        ruler.classList.add('is-hovering');
      };
      const hide = () => { tip.hidden = true; ruler.classList.remove('is-hovering'); };
      tick.addEventListener('mouseenter', show);
      tick.addEventListener('focus', show);
      tick.addEventListener('mouseleave', hide);
      tick.addEventListener('blur', hide);
      tick.addEventListener('click', () => jumpToRow(it));
      track.append(tick);
    });
  }

  if (now >= lo && now <= hi) {
    track.append(h('div', { class: 'ruler__today', style: { left: pct(now) }, 'aria-hidden': 'true' }));
    const flip = (now - lo) / total > 0.85;
    track.append(h('span', { class: `ruler__today-label${flip ? ' ruler__today-label--flip' : ''}`, style: { left: pct(now) }, 'aria-hidden': 'true' },
      `Today · ${now.getDate()} ${MONTHS[now.getMonth()].slice(0, 3)}`));
  }
}

export function jumpToRow(item) {
  if (state.view !== 'list') {
    document.dispatchEvent(new CustomEvent('view:change', { detail: 'list' }));
  }
  requestAnimationFrame(() => {
    const el = document.getElementById(`row-${item.a.id}`);
    if (!el) { openDetail(item); return; }
    el.scrollIntoView({ block: 'center', behavior: 'smooth' });
    el.classList.remove('is-flash');
    void el.offsetWidth;
    el.classList.add('is-flash');
    el.querySelector('.row__main')?.focus({ preventScroll: true });
  });
}

// ---- detail panel -----------------------------------------------------------
let lastFocus = null;

export function openDetail(item) {
  const panel = $('detail');
  const { a, unit, res, slot } = item;
  lastFocus = document.activeElement;
  const now = today();
  let when = '';
  let countdown = '';
  if (res.kind === 'fixed' || res.kind === 'user') {
    when = `${fmtDate(res.date)} at ${res.time}`;
  } else if (res.kind === 'approx') {
    when = `Week ${a.week} · about ${fmtDate(res.date)}`;
  } else {
    when = a.dateKind === 'exam_period' ? 'Formal exam period' : (a.dueRaw || 'No date given');
  }
  if (res.date) {
    const days = Math.round((res.date - now) / 86400e3);
    countdown = days === 0 ? 'today' : days === 1 ? 'tomorrow' : days > 1 ? `in ${days} days` : days === -1 ? 'yesterday' : `${-days} days ago`;
  }
  const dl = h('dl', { class: 'detail__dl' });
  const add = (k, v, raw) => { if (v) dl.append(h('dt', {}, k), h('dd', { class: raw ? 'detail__raw' : '' }, v)); };
  add('Type', a.type);
  add('Weight', weightText(a));
  add('Due', a.dueRaw, true);
  if (a.closingDate) add('Closing', fmtLong(a.closingDate));
  add('Length', a.length);
  add('AI', a.aiPolicy);
  if (a.timeAssumed && res.kind === 'fixed') add('Time', 'Not stated in the outline; 23:59 assumed');
  if (a.earlyFeedback) add('Note', 'Early feedback task');
  if (unit.censusDate) add('Census', fmtLong(unit.censusDate));

  const close = h('button', { type: 'button', class: 'detail__close', 'aria-label': 'Close details' }, '×');
  close.addEventListener('click', closeDetail);

  // Add / change / remove a date of your own when the outline gives none.
  let mine = null;
  if (res.kind === 'user' || res.kind === 'none') {
    mine = h('div', { class: 'detail__mine' });
    const showButtons = () => {
      const edit = h('button', { type: 'button', class: 'btn btn--small' }, res.kind === 'user' ? 'Change date' : 'Add date');
      edit.addEventListener('click', () => {
        const editor = dateEditor(item, { onDone: (saved) => { if (!saved) showButtons(); } });
        mine.replaceChildren(editor);
        editor.focusFirst();
      });
      const kids = [edit];
      if (res.kind === 'user') {
        const rm = h('button', { type: 'button', class: 'btn btn--small' }, 'Remove date');
        rm.addEventListener('click', () => { closeDetail(); removeUserDate(item); });
        kids.push(rm);
      }
      mine.replaceChildren(
        h('p', { class: 'detail__mine-note t-small' }, res.kind === 'user' ? YOUR_DATE_TIP : 'Know the due date from Canvas or your coordinator? Add it here.'),
        h('div', { class: 'detail__mine-btns' }, ...kids));
    };
    showButtons();
  }

  panel.replaceChildren(...[
    h('div', { class: 'detail__head' },
      h('div', {},
        h('div', { class: 'detail__unit t-label' }, swatch(slot), unit.code, h('span', { class: 'detail__unit-name' }, unit.name)),
        h('h2', { class: 'detail__title t-h2', id: 'detail-title' }, a.name || a.type),
        h('p', { class: 'detail__when t-small' }, when, countdown ? h('span', { class: 'detail__count' }, countdown) : null)),
      close),
    a.description ? h('p', { class: 'detail__desc t-body' }, a.description) : null,
    res.kind === 'approx' ? h('p', { class: 'detail__approx t-small' }, 'The outline gives only a week number. The exact date is on Canvas.') : null,
    dl,
    mine,
    h('a', { class: 'detail__link', href: unit.sourceUrl, target: '_blank', rel: 'noopener' }, 'View the unit outline ↗'),
    h('span', { class: 'detail__src t-small' }, `${unit.sessionLabel} · ${unit.mode} · ${unit.location}`),
  ].filter(Boolean));
  panel.hidden = false;
  close.focus();
}

export function closeDetail() {
  const panel = $('detail');
  if (panel.hidden) return;
  panel.hidden = true;
  panel.replaceChildren();
  if (lastFocus && document.contains(lastFocus)) lastFocus.focus();
}

// ---- states -----------------------------------------------------------------
export function emptyState() {
  return h('div', { class: 'empty' },
    h('h2', { class: 't-display empty__title' }, 'Nothing due yet.'),
    h('p', { class: 'empty__body t-body' }, 'Add a unit code to see every assessment for the semester in one list.'));
}

export function errorState(onRetry) {
  const btn = h('button', { type: 'button', class: 'btn' }, 'Try again');
  btn.addEventListener('click', onRetry);
  return h('div', { class: 'error-card', role: 'alert' },
    h('h2', { class: 't-h2 error-card__title' }, "Couldn't load unit data."),
    h('p', { class: 'error-card__body t-body' }, 'The assessment data failed to download. This is usually temporary.'),
    btn);
}
