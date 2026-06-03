import { itemIncassato } from './incassatoUtils';
import { isGrattaEVinci, isTabacchi } from './repartiChartUtils';

function fmtMoney(value) {
  return `€ ${Number(value).toFixed(2).replace('.', ',')}`;
}

export function buildClosureIncassoSummary(items, summary = {}) {
  let tabacchi = 0;
  let gratta = 0;
  for (const item of items || []) {
    const inc = itemIncassato(item);
    if (isTabacchi(item.descrizione)) tabacchi += inc;
    if (isGrattaEVinci(item.descrizione)) gratta += inc;
  }
  return {
    tabacchi: Math.round(tabacchi * 100) / 100,
    gratta: Math.round(gratta * 100) / 100,
    differenza: Math.round((Number(summary.differenza) || 0) * 100) / 100,
  };
}

export function buildClosureSavedMessage({
  date,
  operator,
  items,
  summary,
  saldoCassa = 0,
  fondoCassa = 0,
}) {
  const incasso = buildClosureIncassoSummary(items, summary);
  const dateLabel = date
    ? new Date(`${date}T12:00:00`).toLocaleDateString('it-IT')
    : '';
  const titleLine = dateLabel ? `Chiusura registrata · ${dateLabel}` : 'Chiusura registrata';
  return [
    titleLine,
    '',
    `Operatore: ${operator || '—'}`,
    `Incassato tabacchi: ${fmtMoney(incasso.tabacchi)}`,
    `Incassato gratta e vinci: ${fmtMoney(incasso.gratta)}`,
    `Differenza: ${fmtMoney(incasso.differenza)}`,
    `Totale contanti in cassa: ${fmtMoney(saldoCassa)}`,
    `Totale Fondo cassa: ${fmtMoney(fondoCassa)}`,
  ].join('\n');
}

export function buildClosureSavedNotificationPayload({
  date,
  operator,
  items,
  summary,
  saldoCassa = 0,
  fondoCassa = 0,
}) {
  const message = buildClosureSavedMessage({
    date,
    operator,
    items,
    summary,
    saldoCassa,
    fondoCassa,
  });
  const lines = message.split('\n');
  return {
    title: lines[0] || 'Chiusura registrata',
    body: lines.slice(2).join('\n'),
    url: '/?view=chiusure',
    tag: `mytab-closure-local-${Date.now()}`,
  };
}
