import { itemIncassato } from './incassatoUtils';
import { isGrattaEVinci, isTabacchi } from './repartiChartUtils';

function fmtMoney(value) {
  return `€ ${Number(value).toFixed(2).replace('.', ',')}`;
}

export function buildClosureIncassoSummary(items, summary = {}) {
  let tabacchi = 0;
  let gratta = 0;
  let totale = 0;
  for (const item of items || []) {
    const inc = itemIncassato(item);
    totale += inc;
    if (isTabacchi(item.descrizione)) tabacchi += inc;
    if (isGrattaEVinci(item.descrizione)) gratta += inc;
  }
  return {
    tabacchi: Math.round(tabacchi * 100) / 100,
    gratta: Math.round(gratta * 100) / 100,
    differenza: Math.round((Number(summary.differenza) || 0) * 100) / 100,
    totale: Math.round(totale * 100) / 100,
  };
}

export function buildClosureSavedNotificationPayload({ date, operator, items, summary }) {
  const incasso = buildClosureIncassoSummary(items, summary);
  const dateLabel = date
    ? new Date(`${date}T12:00:00`).toLocaleDateString('it-IT')
    : '';
  let title = dateLabel ? `Chiusura registrata · ${dateLabel}` : 'Chiusura registrata';
  if (operator) title = `${title} · ${operator}`;
  const body = [
    `Incassato tabacchi: ${fmtMoney(incasso.tabacchi)}`,
    `Incassato gratta e vinci: ${fmtMoney(incasso.gratta)}`,
    `Differenza: ${fmtMoney(incasso.differenza)}`,
    `Totale incassato: ${fmtMoney(incasso.totale)}`,
  ].join('\n');
  return {
    title,
    body,
    url: '/?view=chiusure',
    tag: `mytab-closure-local-${Date.now()}`,
  };
}
