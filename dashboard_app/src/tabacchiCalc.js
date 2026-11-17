const GIORNI = [5, 7, 10, 14];
const DEFAULT_SCORTA_PCT = 200;
const SCORTA_PCT_MIN = 10;
const SCORTA_PCT_MAX = 250;
const FAMIGLIE = [
  'Sigarette',
  'Tabacco riscaldato',
  'Trinciati',
  'Sigari e sigaretti',
  'Altri tabacchi',
];

export function normalizzaScortaPct(value, fallback = DEFAULT_SCORTA_PCT) {
  const pct = Number.parseInt(value, 10);
  if (!Number.isFinite(pct)) return fallback;
  return Math.max(SCORTA_PCT_MIN, Math.min(SCORTA_PCT_MAX, pct));
}

export function giorniAllaConsegna(oggi, ultimoChiuso, dataConsegna) {
  const inizio = oggi > ultimoChiuso ? oggi : addDays(ultimoChiuso, 1);
  return Math.max(0, diffDays(dataConsegna, inizio));
}

export function inizioVendite(oggi, ultimoChiuso) {
  return oggi > ultimoChiuso ? oggi : addDays(ultimoChiuso, 1);
}

export function prossimoGiornoConsegna(oggiIso, weekday = 0) {
  // weekday: 0=lunedì … 6=domenica (come Python date.weekday)
  const day = parseIso(oggiIso);
  const jsTarget = (((Number(weekday) % 7) + 7) % 7 + 1) % 7;
  let delta = (jsTarget - day.getDay() + 7) % 7;
  if (delta === 0) delta = 7;
  day.setDate(day.getDate() + delta);
  return isoLocale(day);
}

export function unitaOrdine(prezzo, prezzoKg, minimoGrammi) {
  const p = Number(prezzo) || 0;
  const pkg = Number(prezzoKg) || 0;
  const minimo = Number(minimoGrammi) || 0;
  if (p <= 0 || pkg <= 0 || minimo <= 0) return null;
  const u = Math.round((minimo * pkg) / (1000 * p));
  if (u <= 0) return null;
  return { pacchettiPerUnita: u, kgPerUnita: roundKg(minimo / 1000) };
}

export function propostaUnita(media, giacenza, pacchettiPerUnita, giorniCopertura, giorniAlla, scortaPct = DEFAULT_SCORTA_PCT) {
  const u = Number(pacchettiPerUnita) || 0;
  const fattore = normalizzaScortaPct(scortaPct) / 100;
  const alla = Math.max(0, Number(giacenza) - Number(media) * Number(giorniAlla));
  const target = Number(media) * Number(giorniCopertura) * fattore;
  const mancano = target - alla;
  const soglia = 0.25 * u;
  let unita = 0;
  if (u > 0 && mancano >= soglia - 1e-9) {
    unita = Math.ceil(Math.round((mancano / u) * 1e8) / 1e8 - 1e-9);
  }
  const giorniFine = Number(media) === 0
    ? null
    : Math.floor(Math.max(0, Number(giacenza)) / Number(media));
  return { allaConsegna: alla, unita, giorniFine };
}

export function urgenzaDataFine(giorniFine, giorniAlla, giorniCopertura) {
  if (giorniFine == null) return 'normale';
  if (giorniFine <= Number(giorniAlla)) return 'rossa';
  if (giorniFine < Number(giorniAlla) + Number(giorniCopertura) + 3) return 'arancione';
  return 'normale';
}

export function ricalcolaRighe(righe, { giorniCopertura, oggi, ultimoChiuso, dataConsegna, scortaPct = DEFAULT_SCORTA_PCT }) {
  const distanza = giorniAllaConsegna(oggi, ultimoChiuso, dataConsegna);
  const inizio = inizioVendite(oggi, ultimoChiuso);
  const pct = normalizzaScortaPct(scortaPct);
  return righe.map(riga => {
    const proposta = propostaUnita(
      riga.media, riga.giacenza, riga.pacchetti_per_unita, giorniCopertura, distanza, pct,
    );
    const proposti = proposta.unita;
    const unita = riga.corretto_a_mano ? Number(riga.unita) : proposti;
    const pacchetti = unita * Number(riga.pacchetti_per_unita || 0);
    const dataFine = proposta.giorniFine == null
      ? null
      : addDays(inizio, proposta.giorniFine);
    return {
      ...riga,
      unita_proposte: proposti,
      unita,
      corretto_a_mano: unita !== proposti,
      pacchetti,
      kg: roundKg(unita * Number(riga.kg_per_unita || 0)),
      importo: roundMoney(pacchetti * Number(riga.prezzo || 0)),
      giorni_fine: proposta.giorniFine,
      data_fine: dataFine,
      urgenza: urgenzaDataFine(proposta.giorniFine, distanza, giorniCopertura),
      giorni_alla_consegna: distanza,
    };
  });
}

export function totaliOrdine(righe) {
  const attivi = righe.filter(riga => Number(riga.unita) > 0);
  return {
    articoli: attivi.length,
    stecche: attivi.reduce((sum, riga) => sum + Number(riga.unita || 0), 0),
    kg: roundKg(attivi.reduce((sum, riga) => sum + Number(riga.kg || 0), 0)),
    importo: roundMoney(attivi.reduce((sum, riga) => sum + Number(riga.importo || 0), 0)),
  };
}

export function fraseCopertura(giorniAlla, giorniCopertura, scortaPct = DEFAULT_SCORTA_PCT) {
  const pct = normalizzaScortaPct(scortaPct);
  const vende = giorniAlla <= 0
    ? 'Fino alla consegna non restano giorni di vendita'
    : giorniAlla === 1
      ? 'Fino alla consegna si vende ancora 1 giorno'
      : `Fino alla consegna si vendono ancora ${giorniAlla} giorni`;
  return `${vende}; poi la merce deve bastare ${giorniCopertura} giorni al ${pct}% di scorta. Le quantità sono in stecche da 10 pacchetti (o nella confezione minima per trinciati e sigari).`;
}

export function formattaFinisce(iso) {
  if (!iso) return '—';
  const nomi = ['dom', 'lun', 'mar', 'mer', 'gio', 'ven', 'sab'];
  const day = parseIso(iso);
  const dd = String(day.getDate()).padStart(2, '0');
  const mm = String(day.getMonth() + 1).padStart(2, '0');
  return `${nomi[day.getDay()]} ${dd}/${mm}`;
}

export function formattaChiusura(iso) {
  if (!iso) return '—';
  const day = parseIso(iso);
  const dd = String(day.getDate()).padStart(2, '0');
  const mm = String(day.getMonth() + 1).padStart(2, '0');
  const yyyy = day.getFullYear();
  return `${dd}/${mm}/${yyyy}`;
}

export function elencoCopia(righe) {
  return [...righe]
    .filter(riga => Number(riga.unita) > 0)
    .sort((a, b) => String(a.descrizione).localeCompare(String(b.descrizione), 'it'))
    .map(riga => `${riga.aams}\t${riga.descrizione}\t${Number(riga.kg).toFixed(3)} kg`)
    .join('\n');
}

export function isoLocale(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

export function confrontaRighe(a, b, chiave = 'finisce', direzione = 'asc') {
  const dir = direzione === 'desc' ? -1 : 1;
  let cmp = 0;
  if (chiave === 'descrizione') {
    cmp = String(a.descrizione || '').localeCompare(String(b.descrizione || ''), 'it', { sensitivity: 'base' });
  } else if (chiave === 'importo') {
    cmp = Number(a.importo || 0) - Number(b.importo || 0);
  } else {
    const ga = a.giorni_fine == null ? 1e9 : Number(a.giorni_fine);
    const gb = b.giorni_fine == null ? 1e9 : Number(b.giorni_fine);
    cmp = ga - gb;
    if (cmp === 0) {
      cmp = String(a.descrizione || '').localeCompare(String(b.descrizione || ''), 'it', { sensitivity: 'base' });
    }
  }
  if (cmp === 0) {
    cmp = String(a.aams || '').localeCompare(String(b.aams || ''), 'it');
  }
  return cmp * dir;
}

export function gruppiDaOrdinare(righe, { chiave = 'finisce', direzione = 'asc' } = {}) {
  const attivi = righe.filter(riga => Number(riga.unita) > 0);
  return FAMIGLIE
    .map(famiglia => {
      const items = attivi
        .filter(riga => riga.famiglia === famiglia)
        .sort((a, b) => confrontaRighe(a, b, chiave, direzione));
      const subtotale = roundMoney(items.reduce((sum, riga) => sum + Number(riga.importo || 0), 0));
      return { famiglia, items, subtotale };
    })
    .filter(group => group.items.length > 0);
}

export function altriArticoli(righe, { chiave = 'finisce', direzione = 'asc' } = {}) {
  return [...righe]
    .filter(riga => Number(riga.unita) <= 0)
    .sort((a, b) => confrontaRighe(a, b, chiave, direzione));
}

export { GIORNI, FAMIGLIE, DEFAULT_SCORTA_PCT, SCORTA_PCT_MIN, SCORTA_PCT_MAX };

function roundMoney(value) {
  return Math.round((Number(value) + Number.EPSILON) * 100) / 100;
}

function roundKg(value) {
  return Math.round((Number(value) + Number.EPSILON) * 1000) / 1000;
}

function parseIso(iso) {
  const [y, m, d] = String(iso).slice(0, 10).split('-').map(Number);
  return new Date(y, m - 1, d);
}

function addDays(iso, days) {
  const day = parseIso(iso);
  day.setDate(day.getDate() + days);
  return isoLocale(day);
}

function diffDays(later, earlier) {
  const ms = parseIso(later) - parseIso(earlier);
  return Math.round(ms / 86400000);
}
