import { filterByPeriod } from './dateFilters';

export function normalizeDept(name) {
  return (name || '').toUpperCase().trim().replace(/\s+/g, ' ');
}

export function isTabacchi(name) {
  const n = normalizeDept(name);
  return n === 'TABACCHI' || n.startsWith('TABACCH');
}

export function isGrattaEVinci(name) {
  const n = normalizeDept(name);
  return n.includes('GRATTA') && n.includes('VINCI');
}

export function matchesDept(name, deptKey) {
  return normalizeDept(name) === normalizeDept(deptKey);
}

function itemValue(item) {
  const saldo = Number(item.saldo);
  if (saldo !== 0) return saldo;
  return Number(item.entrate) || 0;
}

export function buildRepartoSeries(closures, matcher) {
  const byDate = new Map();
  for (const closure of closures) {
    let dayTotal = 0;
    for (const item of closure.items || []) {
      if (matcher(item.descrizione)) dayTotal += itemValue(item);
    }
    if (dayTotal === 0) continue;
    const key = closure.date;
    byDate.set(key, (byDate.get(key) || 0) + dayTotal);
  }
  return [...byDate.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, value]) => ({ date, value: Math.round(value * 100) / 100 }));
}

export function getFilteredClosureSeries(closures, period, deptKey) {
  const filtered = filterByPeriod(closures, period);
  return buildRepartoSeries(filtered, (name) => matchesDept(name, deptKey));
}

/** Reparti presenti nelle chiusure, ordinati per etichetta */
export function collectDepartmentsFromClosures(closures) {
  const map = new Map();
  for (const closure of closures) {
    for (const item of closure.items || []) {
      const key = normalizeDept(item.descrizione);
      if (!key) continue;
      if (!map.has(key)) {
        const label = (item.descrizione || key).trim();
        map.set(key, label);
      }
    }
  }
  return [...map.entries()]
    .map(([key, label]) => ({ key, label }))
    .sort((a, b) => a.label.localeCompare(b.label, 'it', { sensitivity: 'base' }));
}

export function getDefaultChartDeptPair(departments) {
  const keys = departments.map((d) => d.key);
  if (!keys.length) return [null, null];

  const first = keys.find(isTabacchi) || keys.find((k) => k.startsWith('TABACCH')) || keys[0];
  const second =
    keys.find((k) => isGrattaEVinci(k) && k !== first)
    || keys.find((k) => k !== first)
    || first;

  return [first, second];
}

export function resolveChartDeptPair(savedPair, departments) {
  const defaults = getDefaultChartDeptPair(departments);
  const available = new Set(departments.map((d) => d.key));

  if (!Array.isArray(savedPair) || savedPair.length < 2) {
    return defaults;
  }

  const a = normalizeDept(savedPair[0]);
  const b = normalizeDept(savedPair[1]);

  if (available.has(a) && available.has(b)) {
    return [a, b];
  }
  if (available.has(a)) {
    const fallback = defaults[1] === a ? defaults[0] : defaults[1];
    return [a, available.has(fallback) && fallback !== a ? fallback : defaults[1]];
  }
  if (available.has(b)) {
    const fallback = defaults[0] === b ? defaults[1] : defaults[0];
    return [available.has(fallback) && fallback !== b ? fallback : defaults[0], b];
  }

  return defaults;
}

export function getDeptLabel(departments, key) {
  return departments.find((d) => d.key === key)?.label || key || '—';
}

export const CHART_SLOT_COLORS = ['#d97706', '#8b5cf6'];

/** Media dei saldi giornalieri nel periodo (solo giorni con movimento). */
export function averageSeriesValue(series) {
  if (!series?.length) return null;
  const sum = series.reduce((acc, p) => acc + p.value, 0);
  return Math.round((sum / series.length) * 100) / 100;
}
