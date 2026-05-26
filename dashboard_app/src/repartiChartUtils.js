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

export function getFilteredClosureSeries(closures, period, matcher) {
  const filtered = filterByPeriod(closures, period);
  return buildRepartoSeries(filtered, matcher);
}
