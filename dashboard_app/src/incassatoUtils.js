const MONTH_LABELS_SHORT = ['Gen', 'Feb', 'Mar', 'Apr', 'Mag', 'Giu', 'Lug', 'Ago', 'Set', 'Ott', 'Nov', 'Dic'];

function roundMoney(n) {
  return Math.round(n * 100) / 100;
}

/** Entrate reparto; se assenti usa saldo positivo (chiusure incomplete). */
export function itemIncassato(item) {
  const entrate = Number(item.entrate) || 0;
  if (entrate > 0) return entrate;
  const saldo = Number(item.saldo) || 0;
  return saldo > 0 ? saldo : 0;
}

export function closureIncassato(closure) {
  return roundMoney((closure.items || []).reduce((sum, item) => sum + itemIncassato(item), 0));
}

export function getMonthLabel(monthIndex) {
  return MONTH_LABELS_SHORT[monthIndex] || '';
}

export function getTotalIncassatoForMonth(closures, year, monthIndex) {
  let total = 0;
  for (const c of closures) {
    const d = new Date(`${c.date}T12:00:00`);
    if (Number.isNaN(d.getTime())) continue;
    if (d.getFullYear() === year && d.getMonth() === monthIndex) {
      total += closureIncassato(c);
    }
  }
  return roundMoney(total);
}

export function getTotalIncassatoForYear(closures, year) {
  let total = 0;
  for (const c of closures) {
    const d = new Date(`${c.date}T12:00:00`);
    if (Number.isNaN(d.getTime())) continue;
    if (d.getFullYear() === year) total += closureIncassato(c);
  }
  return roundMoney(total);
}

/** Serie giornaliera nel mese (solo giorni con chiusure). */
export function getDailyIncassatoSeries(closures, year, monthIndex) {
  const byDate = new Map();
  for (const c of closures) {
    const d = new Date(`${c.date}T12:00:00`);
    if (Number.isNaN(d.getTime())) continue;
    if (d.getFullYear() !== year || d.getMonth() !== monthIndex) continue;
    const inc = closureIncassato(c);
    if (inc <= 0) continue;
    byDate.set(c.date, roundMoney((byDate.get(c.date) || 0) + inc));
  }
  return [...byDate.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, value]) => ({ date, value, label: formatDayLabel(date) }));
}

/** Serie mensile nell'anno (12 mesi, anche a zero). */
export function getMonthlyIncassatoSeries(closures, year) {
  const totals = Array(12).fill(0);
  for (const c of closures) {
    const d = new Date(`${c.date}T12:00:00`);
    if (Number.isNaN(d.getTime())) continue;
    if (d.getFullYear() !== year) continue;
    totals[d.getMonth()] += closureIncassato(c);
  }
  return totals.map((value, monthIndex) => ({
    monthIndex,
    value: roundMoney(value),
    label: getMonthLabel(monthIndex),
  }));
}

function formatDayLabel(iso) {
  const d = new Date(`${iso}T12:00:00`);
  return d.toLocaleDateString('it-IT', { day: '2-digit', month: '2-digit' });
}

export function averageNonZeroValues(series) {
  const values = series.map((p) => p.value).filter((v) => v > 0);
  if (!values.length) return null;
  return roundMoney(values.reduce((a, b) => a + b, 0) / values.length);
}

export const INCASSATO_PERIOD_OPTIONS = [
  { value: 'month', label: 'Mese corrente' },
  { value: 'year', label: 'Anno corrente' },
];

export function getIncassatoPeriodLabel(period) {
  return period === 'year' ? 'anno corrente' : 'mese corrente';
}

export function getCurrentMonthName() {
  const now = new Date();
  return now.toLocaleDateString('it-IT', { month: 'long', year: 'numeric' });
}
