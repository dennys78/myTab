/** Calcolo differenza chiusura (allineato a reconciliation/views.py). */

export const roundMoney = (value) => Math.round((Number(value) || 0) * 100) / 100;

export const calcItemSaldo = (item) =>
  roundMoney((Number(item.entrate) || 0) - Math.abs(Number(item.uscite) || 0));

export const calcSaldoReparti = (items) =>
  roundMoney((items || []).reduce((sum, item) => sum + calcItemSaldo(item), 0));

export const calcTotalsReparti = (items) => ({
  entrate: roundMoney((items || []).reduce((sum, item) => sum + (Number(item.entrate) || 0), 0)),
  uscite: roundMoney((items || []).reduce((sum, item) => sum + Math.abs(Number(item.uscite) || 0), 0)),
  saldo: calcSaldoReparti(items),
});

/** Chiusure 5/6 file: totale_cassetto=0 e differenza coerente con i reparti. */
export function inferWithReports(summary, items) {
  const totaleCassetto = Number(summary?.totale_cassetto) || 0;
  if (totaleCassetto > 0) return false;
  const totale = Number(summary?.totale) || 0;
  if (!items?.length || totale <= 0) return false;
  const saldoReparti = calcSaldoReparti(items);
  const diff = Number(summary?.differenza) || 0;
  return Math.abs(diff - (totale - saldoReparti)) < 2.01;
}

export function calcDifferenzaCassetto(summary) {
  const atteso =
    (Number(summary.totale) || 0) -
    (Number(summary.pag_pos) || 0) -
    (Number(summary.distrib) || 0) -
    (Number(summary.reso_auto) || 0) -
    (Number(summary.reso_cont) || 0);
  return roundMoney((Number(summary.totale_cassetto) || 0) - atteso);
}

export function calcDifferenzaReparti(summary, items) {
  return roundMoney((Number(summary.totale) || 0) - calcSaldoReparti(items));
}

export function calcDifferenza(summary, items, withReports) {
  return withReports ? calcDifferenzaReparti(summary, items) : calcDifferenzaCassetto(summary);
}

/** Contributo di una chiusura al saldo cassa (totale_cassetto + differenza). */
export function closureCashImpact(summary) {
  return roundMoney((Number(summary?.totale_cassetto) || 0) + (Number(summary?.differenza) || 0));
}
