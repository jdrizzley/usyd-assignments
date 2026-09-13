// App wiring: load data, session selector, unit picker, chips, view toggle, export, URL state.
import {
  state, MAX_UNITS, loadCore, loadUnit, unitKey, entryByKey, sessions, defaultSession, sessionKeyOf,
  search, assignSlot, readURL, writeURL, resolveDate, today,
} from './data.js';
import {
  h, swatch, renderList, renderCalendar, renderRuler, emptyState, errorState, closeDetail, collectItems,
} from './render.js';
import { buildICS, downloadICS } from './ics.js';

const $ = (id) => document.getElementById(id);
const els = {
  session: $('session'), input: $('unit-input'), options: $('unit-options'), chips: $('chips'),
  download: $('download'), exportNote: $('export-note'), updated: $('updated'),
  heading: $('session-heading'), sub: $('session-sub'), listBtn: $('view-list-btn'), calBtn: $('view-cal-btn'),
  viewList: $('view-list'), viewCal: $('view-cal'), skeleton: $('skeleton'), listRoot: $('list-root'),
  live: $('live'), detail: $('detail'), hint: $('picker-hint'),
};

function announce(msg) { els.live.textContent = ''; setTimeout(() => { els.live.textContent = msg; }, 30); }

// ---- boot -------------------------------------------------------------------
async function boot() {
  els.skeleton.hidden = false;
  els.listRoot.replaceChildren();
  try {
    const { meta } = await loadCore();
    if (meta?.generatedAt) {
      const d = new Date(meta.generatedAt);
      els.updated.textContent = `Updated ${d.toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })}.`;
    }
  } catch (err) {
    console.error(err);
    els.skeleton.hidden = true;
    els.listRoot.replaceChildren(errorState(boot));
    return;
  }
  els.skeleton.hidden = true;
  const url = readURL();
  populateSessions(url.session);
  state.view = new URLSearchParams(location.search).get('v') === 'calendar' ? 'calendar' : 'list';
  els.input.disabled = false;
  els.session.disabled = false;
  setView(state.view, false);
  render();
  const initial = url.units.map(entryByKey).filter(Boolean).filter((e) => sessionKeyOf(e) === state.sessionKey).slice(0, MAX_UNITS);
  for (const e of initial) addUnit(e, { fromURL: true });
  if (!initial.length) render();
}

// ---- sessions ---------------------------------------------------------------
function populateSessions(preferred) {
  const list = sessions();
  els.session.replaceChildren(...list.map((s) => h('option', { value: s.key }, s.label)));
  const key = list.some((s) => s.key === preferred) ? preferred : defaultSession(list);
  state.sessionKey = key;
  els.session.value = key ?? '';
  els.session.disabled = list.length < 2;
}

els.session.addEventListener('change', () => {
  state.sessionKey = els.session.value;
  for (const key of [...state.selected]) removeUnit(key, { quiet: true });
  closeDetail();
  els.exportNote.replaceChildren();
  writeURL();
  render();
  announce(`Session changed to ${els.session.selectedOptions[0]?.textContent}. Units cleared.`);
});

// ---- picker / autocomplete --------------------------------------------------
let matches = [];
let active = -1;

function showOptions(list) {
  matches = list;
  active = list.length ? 0 : -1;
  els.options.replaceChildren();
  if (!els.input.value.trim()) { hideOptions(); return; }
  if (!list.length) {
    els.options.append(h('div', { class: 'ac__empty t-small' }, `No units matching “${els.input.value.trim()}” in this session.`));
  }
  list.forEach(({ entry, ambiguous }, i) => {
    const item = h('div', {
      class: 'ac__item', role: 'option', id: `opt-${i}`, 'aria-selected': i === active ? 'true' : 'false',
    },
      h('span', { class: 'ac__code t-label' }, entry.code),
      h('span', { class: 'ac__name' }, entry.name),
      ambiguous ? h('span', { class: 'ac__where t-small' }, `${entry.mode} · ${entry.location}`) : null);
    item.addEventListener('mousedown', (e) => { e.preventDefault(); choose(i); });
    els.options.append(item);
  });
  els.options.hidden = false;
  els.input.setAttribute('aria-expanded', 'true');
  syncActive();
}
function hideOptions() {
  els.options.hidden = true;
  els.input.setAttribute('aria-expanded', 'false');
  els.input.removeAttribute('aria-activedescendant');
  matches = []; active = -1;
}
function syncActive() {
  [...els.options.querySelectorAll('[role=option]')].forEach((el, i) => el.setAttribute('aria-selected', i === active ? 'true' : 'false'));
  if (active >= 0) {
    els.input.setAttribute('aria-activedescendant', `opt-${active}`);
    els.options.querySelector(`#opt-${active}`)?.scrollIntoView({ block: 'nearest' });
  }
}
function choose(i) {
  const m = matches[i];
  if (!m) return;
  addUnit(m.entry);
  els.input.value = '';
  hideOptions();
  els.input.focus();
}

els.input.addEventListener('input', () => showOptions(search(els.input.value, state.sessionKey)));
els.input.addEventListener('focus', () => { if (els.input.value.trim()) showOptions(search(els.input.value, state.sessionKey)); });
els.input.addEventListener('blur', () => setTimeout(hideOptions, 120));
els.input.addEventListener('keydown', (e) => {
  if (e.key === 'ArrowDown') { e.preventDefault(); if (matches.length) { active = (active + 1) % matches.length; syncActive(); } }
  else if (e.key === 'ArrowUp') { e.preventDefault(); if (matches.length) { active = (active - 1 + matches.length) % matches.length; syncActive(); } }
  else if (e.key === 'Enter') {
    e.preventDefault();
    if (els.options.hidden) showOptions(search(els.input.value, state.sessionKey));
    if (matches.length) choose(Math.max(0, active));
  }
  else if (e.key === 'Escape') { if (!els.options.hidden) { hideOptions(); } else { els.input.value = ''; } }
});

// ---- units ------------------------------------------------------------------
function addUnit(entry, { fromURL = false } = {}) {
  const key = unitKey(entry);
  if (state.selected.includes(key)) return;
  if (state.selected.length >= MAX_UNITS) {
    els.hint.textContent = `That's ${MAX_UNITS} units, which is the most this page shows at once. Remove one to add another.`;
    announce(els.hint.textContent);
    return;
  }
  state.selected.push(key);
  assignSlot(key);
  writeURL();
  renderChips();
  loadUnit(entry).then((unit) => {
    if (!state.selected.includes(key)) return;
    renderChips();
    render();
    const n = unit.assessments.length;
    announce(`${entry.code} added. ${n === 0 ? 'No assessments could be read from its outline.' : `${n} assessment${n === 1 ? '' : 's'}.`}`);
  }).catch((err) => {
    console.error(err);
    if (!state.selected.includes(key)) return;
    state.units.set(key, { error: true, code: entry.code, name: entry.name, sourceUrl: `https://www.sydney.edu.au/units/${entry.code}/${entry.availability}`, assessments: [] });
    renderChips();
    render();
    announce(`${entry.code} could not be loaded.`);
  });
  if (!fromURL) render();
}

function removeUnit(key, { quiet = false } = {}) {
  const i = state.selected.indexOf(key);
  if (i < 0) return;
  state.selected.splice(i, 1);
  state.slots.delete(key);
  writeURL();
  renderChips();
  closeDetail();
  render();
  if (!quiet) announce(`${key.slice(0, 8)} removed.`);
  const next = els.chips.querySelector('.chip__remove') || els.input;
  next.focus();
}

function renderChips() {
  els.chips.replaceChildren();
  els.hint.textContent = state.selected.length ? `${state.selected.length} of ${MAX_UNITS} units.` : 'Up to 10 units. Arrow keys move, Enter adds.';
  for (const key of state.selected) {
    const entry = entryByKey(key);
    const unit = state.units.get(key);
    const loading = !unit || typeof unit.then === 'function';
    const slot = state.slots.get(key) ?? 0;
    const li = h('li', { class: 'chip-wrap' });
    const remove = h('button', { type: 'button', class: 'chip__remove', 'aria-label': `Remove ${entry?.code ?? key}` }, '×');
    remove.addEventListener('click', () => removeUnit(key));
    const chip = h('span', { class: `chip${loading ? ' is-loading' : ''}`, 'aria-busy': loading ? 'true' : null },
      swatch(slot),
      h('span', { class: 't-label' }, entry?.code ?? key.slice(0, 8)),
      h('span', { class: 'chip__name t-small' }, loading ? 'Loading' : (entry?.name ?? '')),
      remove);
    li.append(chip);
    if (!loading && unit.error) {
      li.append(h('span', { class: 'chip-note t-small' }, 'This unit’s file could not be downloaded. ', h('a', { href: unit.sourceUrl, target: '_blank', rel: 'noopener' }, 'View the outline ↗')));
    } else if (!loading && unit.assessments.length === 0) {
      li.append(h('span', { class: 'chip-note t-small' }, 'Outline published but no assessments could be read. ', h('a', { href: unit.sourceUrl, target: '_blank', rel: 'noopener' }, 'View the outline ↗')));
    }
    els.chips.append(li);
  }
}

// ---- views ------------------------------------------------------------------
function setView(view, persist = true) {
  state.view = view;
  els.listBtn.setAttribute('aria-pressed', view === 'list' ? 'true' : 'false');
  els.calBtn.setAttribute('aria-pressed', view === 'calendar' ? 'true' : 'false');
  els.viewList.hidden = view !== 'list';
  els.viewCal.hidden = view !== 'calendar';
  if (persist) writeURL();
  render();
}
els.listBtn.addEventListener('click', () => setView('list'));
els.calBtn.addEventListener('click', () => setView('calendar'));
document.addEventListener('view:change', (e) => setView(e.detail));

function suggest(code) {
  let entry = state.index.find((e) => e.code === code && sessionKeyOf(e) === state.sessionKey);
  if (!entry) {
    entry = state.index.find((e) => e.code === code);
    if (!entry) { announce(`${code} is not in the data yet.`); return; }
    state.sessionKey = sessionKeyOf(entry);
    els.session.value = state.sessionKey;
    writeURL();
  }
  addUnit(entry);
}

function render() {
  const sessionLabel = els.session.selectedOptions[0]?.textContent || 'Assessments';
  els.heading.textContent = sessionLabel;
  const { items, dated, undated } = collectItems();
  const loaded = state.selected.filter((k) => { const u = state.units.get(k); return u && typeof u.then !== 'function'; }).length;
  els.sub.textContent = state.selected.length
    ? `${state.selected.length} unit${state.selected.length === 1 ? '' : 's'} · ${items.length} assessment${items.length === 1 ? '' : 's'}${undated.length ? ` · ${undated.length} without a fixed date` : ''}${loaded < state.selected.length ? ' · loading' : ''}`
    : '';
  els.download.disabled = dated.length === 0;

  if (state.view === 'list') {
    const has = renderList(els.listRoot);
    if (!has && !state.selected.length) els.listRoot.replaceChildren(emptyState(suggest));
    else if (!has) els.listRoot.replaceChildren(h('p', { class: 't-small', style: { color: 'var(--ink-500)' } }, loaded < state.selected.length ? 'Loading unit data.' : 'No assessments to show for these units.'));
  } else {
    renderCalendar(els.viewCal);
  }
  renderRuler();
}

window.addEventListener('resize', (() => { let t; return () => { clearTimeout(t); t = setTimeout(renderRuler, 120); }; })());

// ---- export -----------------------------------------------------------------
els.download.addEventListener('click', () => {
  const { items } = collectItems();
  const label = els.session.selectedOptions[0]?.textContent || state.sessionKey;
  const { text, exported, excluded } = buildICS(items, label);
  downloadICS(text, `usyd-assessments-${state.sessionKey}.ics`);
  const note = els.exportNote;
  note.replaceChildren();
  const n = excluded.length;
  const head = `${exported} event${exported === 1 ? '' : 's'} exported.` + (n ? ` ${n} assessment${n === 1 ? ' had' : 's had'} no fixed date and ${n === 1 ? 'was' : 'were'} left out:` : '');
  note.append(h('p', {}, head));
  if (n) {
    note.append(h('ul', {}, excluded.map((x) => h('li', {}, h('span', { class: 't-label' }, x.unit.code), ` ${x.a.name} — ${x.reason}`))));
  }
  announce(head);
});

// ---- global keys ------------------------------------------------------------
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !els.detail.hidden) { e.preventDefault(); closeDetail(); }
});
document.addEventListener('click', (e) => {
  if (els.detail.hidden) return;
  if (els.detail.contains(e.target)) return;
  if (e.target.closest('.row__main, .pill, .ruler__tick')) return;
  closeDetail();
});

boot();
