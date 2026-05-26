export const STORICO_PERIOD_OPTIONS = [
  { value: 'week', label: 'Settimana' },
  { value: 'month', label: 'Mese' },
  { value: 'three', label: 'Tre mesi' },
  { value: 'year', label: 'Anno' },
];

/** Periodi grafici dashboard: mese corrente di default, alternativa settimana/anno */
export const REPARTI_CHART_PERIOD_OPTIONS = [
  { value: 'week', label: 'Settimana corrente' },
  { value: 'month', label: 'Mese corrente' },
  { value: 'year', label: 'Anno corrente' },
];

const REPARTI_PERIOD_LABELS = {
  week: 'settimana corrente',
  month: 'mese corrente',
  year: 'anno corrente',
};

export function getRepartiChartPeriodLabel(period) {
  return REPARTI_PERIOD_LABELS[period] || REPARTI_PERIOD_LABELS.month;
}

export function getPeriodStart(period) {
  const now = new Date();
  if (period === 'week') {
    const day = now.getDay() || 7;
    const start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - day + 1);
    start.setHours(0, 0, 0, 0);
    return start;
  }
  if (period === 'month') {
    return new Date(now.getFullYear(), now.getMonth(), 1);
  }
  if (period === 'three') {
    return new Date(now.getFullYear(), now.getMonth() - 2, 1);
  }
  if (period === 'year') {
    return new Date(now.getFullYear(), 0, 1);
  }
  return new Date(0);
}

export function filterByPeriod(items, period, dateField = 'date') {
  const start = getPeriodStart(period);
  return items.filter((item) => {
    const d = new Date(`${item[dateField]}T12:00:00`);
    return !Number.isNaN(d.getTime()) && d.getTime() >= start.getTime();
  });
}
