/** Applica prospetti portale (Contabile Lotto + Premi Gratta) sulle voci di chiusura. */

function voceKey(name) {
  return String(name || '').trim().toUpperCase().replace(/\s+/g, ' ');
}

function money(value) {
  return Math.round((Number(value) || 0) * 100) / 100;
}

function saldo(item) {
  return money((Number(item.entrate) || 0) - Math.abs(Number(item.uscite) || 0));
}

/**
 * @param {Array} items
 * @param {object|null} portale risposta /api/portale/giornata/
 * @returns {{ items: Array, applied: string[] }}
 */
export function applicaPortaleSuItems(items, portale) {
  if (!portale || !Array.isArray(items)) return { items: items || [], applied: [] };

  const lotto = portale.lotto || portale.contabile_lotto;
  const premi = portale.premi_lotterie_vista || portale.premi_lotterie;
  const next = items.map(item => ({ ...item }));
  const applied = [];

  if (lotto && (lotto.entrate != null || lotto.uscite != null)) {
    const idx = next.findIndex(i => voceKey(i.descrizione) === 'LOTTOMATICA');
    if (idx >= 0) {
      next[idx] = {
        ...next[idx],
        entrate: money(lotto.entrate),
        uscite: Math.abs(money(lotto.uscite)),
        from_portale: true,
      };
      next[idx].saldo = saldo(next[idx]);
      applied.push('LOTTOMATICA');
    }
  }

  const premiImporto = premi?.totale?.importo;
  if (premiImporto != null) {
    const idx = next.findIndex(i => voceKey(i.descrizione) === 'GRATTA E VINCI');
    if (idx >= 0) {
      next[idx] = {
        ...next[idx],
        // Entrate restano da TabaUno/foglio; uscite = premi pagati del giorno
        uscite: Math.abs(money(premiImporto)),
        from_portale: true,
      };
      next[idx].saldo = saldo(next[idx]);
      applied.push('GRATTA E VINCI');
    }
  }

  return { items: next, applied };
}
